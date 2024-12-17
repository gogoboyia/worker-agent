# agent.py
import os
import re
import subprocess
import sys
import asyncio
from stdlib_list import stdlib_list

from worker_agent.llm import fast_chat_programmer
from worker_agent.prompt_rules import CLARIFY_PROMPT, PROGRAMMER_PROMPT, REQUIREMENTS_PROMPT, ROADMAP_PROMPT, TESTER_PROMPT
from worker_agent.qwen import slow_local_chat_programmer
from worker_agent.utils.html import generate_xpath_map

def is_file_relevant(user_prompt, file_path, file_content):
    messages = [
        {"role": "system", "content": (
            "You are a Python assistant that decides if a given file is relevant to a given user prompt.\n"
            "We will provide a user prompt and a file content.\n"
            "You must respond strictly with 'True' or 'False' without quotes or explanations.\n"
            "Criteria: The file is relevant if it may need to be read, edited, or could influence the changes required by the prompt.\n"
            "If unsure, return True. Be inclusive rather than exclusive.\n"
            "Only respond with True or False."
        )},
        {"role": "user", "content": f"User prompt: {user_prompt}\nFile path: {file_path}\nFile content:\n{file_content}"}
    ]
    response = slow_local_chat_programmer(messages, temperature=0.1)
    response = response.strip()

    return response.startswith("True")

class ClarifierAgent:
    """
    Agent responsible for clarifying the initial prompt and providing a roadmap for problem resolution.
    It now takes into account project files to generate clarifications and roadmap.
    """

    def __init__(self, workspace_dir):
        self.workspace_dir = workspace_dir

    def load_project_files(self):
        """
        Load all project files from the workspace_dir recursively, ignoring irrelevant directories.
        """
        ignored_dirs = {"node_modules", ".git", "__pythoncode__"}
        project_files = []
        for root, dirs, files in os.walk(self.workspace_dir):
            # Filter out ignored directories
            dirs[:] = [d for d in dirs if d not in ignored_dirs]

            for file in files:
                full_path = os.path.join(root, file)
                if os.path.isfile(full_path) and os.path.getsize(full_path) < 2_000_000:
                    try:
                        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                        rel_path = os.path.relpath(full_path, self.workspace_dir)
                        project_files.append({"path": rel_path, "content": content})
                    except:
                        pass
        return project_files

    def filter_relevant_files(self, user_prompt):
        """
        Instead of a simple keyword-based filter, we will use the LLM to decide if each file is relevant.
        For each file, call the model and ask if it's relevant. If True, keep it.
        This is more sophisticated and precise.
        """
        all_files = self.load_project_files()
        relevant_files = []
        for f in all_files:
            if is_file_relevant(user_prompt, f["path"], f["content"]):
                relevant_files.append(f)
        return relevant_files

    def clarify(self, instructions, previous_clarifications=None, relevant_files=None):
        """
        Determines if the instructions need additional clarifications.
        Includes relevant project files in the prompt if available to help the model clarify.
        """
        messages = [
            {"role": "system", "content": CLARIFY_PROMPT},
            {"role": "user", "content": instructions},
        ]
        if previous_clarifications:
            for qa in previous_clarifications:
                messages.append({"role": "assistant", "content": qa['question']})
                messages.append({"role": "user", "content": qa['answer']})

        if relevant_files:
            max_chars = 30_000
            current_len = 0
            filtered_files_content = []
            for f in relevant_files:
                file_data = f"File: {f['path']}\n{f['content']}\n\n"
                if current_len + len(file_data) > max_chars:
                    break
                filtered_files_content.append(file_data)
                current_len += len(file_data)
            if filtered_files_content:
                messages.append({"role": "user", "content": "Relevant project files:\n" + "".join(filtered_files_content)})

        response = fast_chat_programmer(messages, temperature=0.1)
        return response.strip()

    def generate_roadmap(self, problem_description, relevant_files=None):
        """
        Generates a roadmap to resolve the described problem.
        Includes relevant project files to provide context.
        """
        messages = [
            {"role": "system", "content": ROADMAP_PROMPT},
            {"role": "user", "content": problem_description},
        ]

        if relevant_files:
            max_chars = 30_000
            current_len = 0
            filtered_files_content = []
            for f in relevant_files:
                file_data = f"File: {f['path']}\n{f['content']}\n\n"
                if current_len + len(file_data) > max_chars:
                    break
                filtered_files_content.append(file_data)
                current_len += len(file_data)
            if filtered_files_content:
                messages.append({"role": "user", "content": "Relevant project files:\n" + "".join(filtered_files_content)})

        response = fast_chat_programmer(messages, temperature=0.2)
        return response.strip()

    async def conduct_clarification_interview(
        self, user_prompt, max_clarifications=10, clarification_handler=None
    ):
        """
        Conducts the clarification interview process.
        Uses the LLM-based relevance filtering for files.
        """
        relevant_files = self.filter_relevant_files(user_prompt)

        clarification_interview = []
        for _ in range(max_clarifications):
            clarification = self.clarify(user_prompt, clarification_interview, relevant_files=relevant_files)
            if clarification == "Nothing to clarify":
                break
            else:
                if clarification_handler and callable(clarification_handler):
                    if asyncio.iscoroutinefunction(clarification_handler):
                        clarification_response = await clarification_handler(
                            clarification
                        )
                    else:
                        clarification_response = clarification_handler(clarification)
                else:
                    clarification_response = input(
                        f"Please answer the clarification question: {clarification}\n"
                    )
                clarification_interview.append(
                    {"question": clarification, "answer": clarification_response}
                )

        if clarification_interview:
            clarifications_text = "\n".join(
                [f"Q: {qa['question']}\nA: {qa['answer']}" for qa in clarification_interview]
            )
            roadmap_prompt = f"Prompt: {user_prompt}\nClarifications:\n{clarifications_text}"
        else:
            roadmap_prompt = f"Prompt: {user_prompt}"

        roadmap = self.generate_roadmap(roadmap_prompt, relevant_files=relevant_files)

        return roadmap_prompt, roadmap


class CodeGenerator:
    def __init__(
        self,
        workspace_dir,
        max_iterations=5,
        clarifier_agent=None,
        generate_tests=True,
        messages=None,
    ):
        self.workspace_dir = workspace_dir
        self.env_dir = os.path.join(self.workspace_dir, "env")
        self.max_iterations = max_iterations
        self.prompt = None
        self.generate_tests = generate_tests

        self.clarifier = clarifier_agent

        self.create_virtualenv(self.env_dir)

        default_messages = {
            "starting_iteration": "Starting iteration {iteration}...",
            "tests_failed": "Tests failed. The model will try to adjust the code based on the feedback.",
            "script_execution_failed": "Script execution failed. The model will try to adjust the code based on the feedback.",
            "task_completed": "Task completed successfully! The code and tests work correctly.",
            "task_failed": "Could not complete the task after several attempts. Consider providing more details or revising your description.",
        }

        self.messages = messages if messages else default_messages

    def load_project_files(self):
        ignored_dirs = {"node_modules", ".git", "__pythoncode__"}
        project_files = []
        for root, dirs, files in os.walk(self.workspace_dir):
            dirs[:] = [d for d in dirs if d not in ignored_dirs]
            for file in files:
                full_path = os.path.join(root, file)
                if os.path.isfile(full_path) and os.path.getsize(full_path) < 2_000_000:
                    try:
                        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                        rel_path = os.path.relpath(full_path, self.workspace_dir)
                        project_files.append({"path": rel_path, "content": content})
                    except:
                        pass
        return project_files

    def filter_relevant_files(self, user_prompt):
        # Use the same sophisticated approach as ClarifierAgent
        all_files = self.load_project_files()
        relevant_files = []
        for f in all_files:
            if is_file_relevant(user_prompt, f["path"], f["content"]):
                relevant_files.append(f)
        return relevant_files

    def create_virtualenv(self, env_dir):
        import venv
        builder = venv.EnvBuilder(with_pip=True)
        builder.create(env_dir)
        print(f"Virtual environment created at {env_dir}")

    def get_env_python(self):
        if os.name == "nt":
            python_executable = os.path.join(self.env_dir, "Scripts", "python.exe")
        else:
            python_executable = os.path.join(self.env_dir, "bin", "python")
        return python_executable

    def extract_code(self, text):
        LANGUAGE_EXTENSION_MAP = {
            'python': 'py',
            'html': 'html',
            'javascript': 'js',
            'js': 'js',
            'php': 'php',
            'java': 'java',
            'c++': 'cpp',
            'cpp': 'cpp',
            'c#': 'cs',
            'cs': 'cs',
            'bash': 'sh',
            'shell': 'sh',
            'go': 'go',
            'ruby': 'rb',
            'perl': 'pl',
            'rust': 'rs',
        }

        result = []
        code_block_started = False
        code = ''
        lang = ''
        lines = text.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i]
            if not code_block_started:
                if line.startswith('```'):
                    code_block_started = True
                    lang = line[3:].strip()
                    if not lang:
                        lang = None
                    i += 1
                    continue
            else:
                if line.startswith('```'):
                    code_block_started = False
                    extension = LANGUAGE_EXTENSION_MAP.get(lang.lower() if lang else '', lang)
                    result.append({'content': code.rstrip('\n'), 'type': lang, 'extension': extension})
                    code = ''
                    lang = ''
                    i += 1
                    continue
                else:
                    code += line + '\n'
            i += 1

        return result

    def extract_path(self, file_content):
        first_line = file_content.split("\n")[0].strip()
        if first_line.startswith("#"):
            path_info = re.sub(r"^#\s*\.?\/?", "", first_line).strip()
            return path_info
        else:
            return None

    def generate_code(self, prompt, role="programmer", files=None, error_feedback=None):
        if role == "programmer":
            system_prompt = PROGRAMMER_PROMPT
        elif role == "tester":
            system_prompt = TESTER_PROMPT
        elif role == "requirements":
            system_prompt = REQUIREMENTS_PROMPT
        else:
            system_prompt = PROGRAMMER_PROMPT

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        if files:
            max_chars = 30_000
            current_len = 0
            filtered_files_content = []
            for file in files:
                file_data = f"File: {file['path']}\n{file['content']}\n\n"
                if current_len + len(file_data) > max_chars:
                    break
                filtered_files_content.append(file_data)
                current_len += len(file_data)
            if filtered_files_content:
                messages.append({"role": "user", "content": "Relevant project files:\n" + "".join(filtered_files_content)})

        if error_feedback:
            messages.append({"role": "user", "content": f"Error:\n{error_feedback}"})

        response = fast_chat_programmer(messages, temperature=0.1)
        return response

    def write_to_file(self, filepath, content):
        if filepath is None:
            raise ValueError("No file path specified in code content.")

        content = re.sub(r"^(\s*#.*\n)+", "", content)
        content = f"# {filepath}\n" + content

        full_path = os.path.join(self.workspace_dir, filepath)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"File saved at: {full_path}")

    def filter_requirements(self, requirements_content):
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        standard_lib_modules = set(stdlib_list(python_version))
        standard_lib_modules.update({"unittest", "mock"})
        packages = requirements_content.splitlines()
        non_standard_packages = [
            pkg.split("==")[0] for pkg in packages if pkg.split("==")[0] not in standard_lib_modules
        ]
        return "\n".join(non_standard_packages)

    def install_requirements(self):
        requirements_file = os.path.join(self.workspace_dir, "requirements.txt")
        if os.path.exists(requirements_file):
            print("Installing requirements from requirements.txt...")
            python_executable = self.get_env_python()
            try:
                result = subprocess.run(
                    [
                        python_executable,
                        "-m",
                        "pip",
                        "install",
                        "-r",
                        requirements_file,
                    ],
                    capture_output=True,
                    text=True,
                )
                print(result.stdout)
                if result.stderr:
                    print(result.stderr)
            except Exception as e:
                print(f"Error installing requirements: {e}")
                return
        else:
            print("No requirements.txt file found.")

    def execute_script(self, filepath):
        python_executable = self.get_env_python()
        full_path = os.path.join(self.workspace_dir, filepath)
        try:
            result = subprocess.run(
                [python_executable, full_path], capture_output=True, text=True
            )
            print(f"Execution output of {os.path.basename(filepath)}:\n{result.stdout}")
            if result.stderr:
                print(
                    f"Errors during execution of {os.path.basename(filepath)}:\n{result.stderr}"
                )
            return len(result.stderr) == 0, f"Result:\n{result.stdout}\nErrors:\n{result.stderr}"
        except Exception as e:
            print(f"Error executing {os.path.basename(filepath)}: {e}")
            return False, str(e)

    async def run(
        self,
        user_prompt,
        max_clarifications=10,
        clarification_handler=None,
        verbose_handler=None,
    ):
        if verbose_handler is None:
            verbose_handler = lambda s: print(s)

        async def handle_verbose(message):
            if asyncio.iscoroutinefunction(verbose_handler):
                await verbose_handler(message)
            else:
                verbose_handler(message)

        # Clarification and roadmap
        roadmap_prompt, roadmap = await self.clarifier.conduct_clarification_interview(
            user_prompt, max_clarifications, clarification_handler
        )

        print(f"Roadmap:\n{roadmap}")

        self.prompt = f"prompt: {user_prompt}\nroadmap:\n{roadmap}"
        test_prompt = "Write unit tests for the generated code."

        # Load relevant files again with new approach
        relevant_files = self.filter_relevant_files(user_prompt)

        files = []
        error_feedback = None

        for iteration in range(1, self.max_iterations + 1):
            await handle_verbose(
                self.messages["starting_iteration"].format(iteration=iteration)
            )
            files = [f for f in files if f.get("type") in ["code", "test"]]

            if error_feedback:
                self.prompt = "Resolve the errors and problems based on the feedback."
                test_prompt = "Resolve the errors and problems based on the feedback."

            code = self.generate_code(
                self.prompt,
                role="programmer",
                files=relevant_files,
                error_feedback=error_feedback,
            )
            code_blocks = self.extract_code(code)
            for code_block in code_blocks:
                path = self.extract_path(code_block["content"])
                self.write_to_file(path, code_block["content"])

                existing_file = next((f for f in files if f["path"] == path), None)
                if existing_file:
                    existing_file["content"] = code_block["content"]
                else:
                    file = {
                        "path": path,
                        "type": "code",
                        "content": code_block["content"],
                    }
                    files.append(file)

                if self.generate_tests:
                    test_code = self.generate_code(
                        test_prompt,
                        role="tester",
                        files=files,
                    )
                    test_blocks = self.extract_code(test_code)
                    if test_blocks:
                        test_content = test_blocks[0]["content"]
                        test_path = self.extract_path(test_content)
                        self.write_to_file(test_path, test_content)

                        existing_test_file = next(
                            (f for f in files if f["path"] == test_path), None
                        )
                        if existing_test_file:
                            existing_test_file["content"] = test_content
                        else:
                            test_file = {
                                "path": test_path,
                                "type": "test",
                                "content": test_content,
                            }
                            files.append(test_file)

            requirements_content = self.generate_code(
                "Create a requirements.txt file based on the dependencies in the code and test files provided.",
                role="requirements",
                files=files,
            )

            if len(requirements_content) > 3:
                requirements_content = self.filter_requirements(requirements_content)
                self.write_to_file("requirements.txt", requirements_content)

                existing_requirements_file = next((f for f in files if f["path"] == "requirements.txt"), None)
                if existing_requirements_file:
                    existing_requirements_file["content"] = requirements_content
                else:
                    files.append(
                        {
                            "path": "requirements.txt",
                            "type": "requirements",
                            "content": requirements_content,
                        }
                    )

                self.install_requirements()

            error_feedback = ""
            for file in files:
                if file["type"] == "test":
                    test_success, run_info = self.execute_script(file["path"])
                    if not test_success:
                        code_objects = self.extract_code(run_info)
                        code_blocks = "\n".join(
                            f"```{obj['type']}\n{obj['content']}\n```"
                            for obj in code_objects
                        )
                        cleaned_text = re.sub(r"```html.*?```", "", run_info, flags=re.DOTALL)
                        error_feedback += (
                            f"Test errors in {file['path']}:\n{cleaned_text}\n"
                        )

                        error_feedback += code_blocks
                        await handle_verbose(self.messages["tests_failed"])
                        print(error_feedback)
                        break
            else:
                # If all tests pass, execute code files
                for file in files:
                    if file["type"] == "code":
                        script_success, run_info = self.execute_script(file["path"])
                        if not script_success:
                            cleaned_text = re.sub(r"```html.*?```", "", run_info, flags=re.DOTALL)
                            error_feedback += (
                                f"Script errors in {file['path']}:\n{cleaned_text}\n"
                            )

                            code_objects = self.extract_code(run_info)
                            if code_objects:
                                code_objects = [code_objects[-1]]
                            code_blocks = "\n".join(
                                f"```xpath map\n{generate_xpath_map(obj['content']) if obj['type'] == 'html' else obj['content']}\n```"
                                for obj in code_objects
                            )
                            if code_blocks:
                                error_feedback += f"use de path map to resolve find_element problems:\n{code_blocks}"
                            await handle_verbose(self.messages["script_execution_failed"])
                            print(error_feedback)
                            break
                else:
                    await handle_verbose(self.messages["task_completed"])
                    return

        await handle_verbose(self.messages["task_failed"])
