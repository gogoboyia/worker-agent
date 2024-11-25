import json
import os
import re
import subprocess
import sys
import asyncio
from huggingface_hub import InferenceClient
from stdlib_list import stdlib_list
from bs4 import BeautifulSoup, Comment

from worker_agent.prompt_rules import CLARIFY_PROMPT, PROGRAMMER_PROMPT, REQUIREMENTS_PROMPT, ROADMAP_PROMPT, TESTER_PROMPT

client = InferenceClient(timeout=60 * 5)


def fast_chat_programmer(messages, temperature=0.2):
    response = client.chat.completions.create(
        model="Qwen/Qwen2.5-Coder-32B-Instruct",
        messages=messages,
        temperature=temperature,
        max_tokens=20000,
        stream=False,
    )

    return response.choices[0].message.content

os.environ["TOKENIZERS_PARALLELISM"] = "false"

class ClarifierAgent:
    """
    Agent responsible for clarifying the initial prompt and providing a roadmap for problem resolution.
    """

    def clarify(self, instructions, previous_clarifications=None):
        """
        Determines if the instructions need additional clarifications.

        Args:
            instructions (str): The instructions provided by the user.
            previous_clarifications (list of dict, optional): Previous clarification questions and answers.

        Returns:
            str: "Nothing to clarify" or a single clarification question.
        """
        messages = [
            {"role": "system", "content": CLARIFY_PROMPT},
            {"role": "user", "content": instructions},
        ]
        if previous_clarifications:
            for qa in previous_clarifications:
                messages.append({"role": "assistant", "content": qa['question']})
                messages.append({"role": "user", "content": qa['answer']})

        response = fast_chat_programmer(messages, temperature=0.1)
        return response.strip()

    def generate_roadmap(self, problem_description):
        """
        Generates a roadmap to resolve the described problem.

        Args:
            problem_description (str): The problem description provided by the user.

        Returns:
            str: A step-by-step roadmap.
        """
        messages = [
            {"role": "system", "content": ROADMAP_PROMPT},
            {"role": "user", "content": problem_description},
        ]

        response = fast_chat_programmer(messages, temperature=0.2)
        return response.strip()

class CodeGenerator:
    def __init__(self, workspace_dir, max_iterations=5, clarifier_agent=None, generate_tests=True):
        self.workspace_dir = workspace_dir
        self.env_dir = os.path.join(self.workspace_dir, "env")
        self.max_iterations = max_iterations
        self.prompt = None
        self.generate_tests = generate_tests

        self.create_virtualenv(self.env_dir)
        self.clarifier = clarifier_agent if clarifier_agent else ClarifierAgent()

    def create_virtualenv(self, env_dir):
        """
        Creates a virtual environment in the specified directory.
        """
        import venv

        builder = venv.EnvBuilder(with_pip=True)
        builder.create(env_dir)
        print(f"Virtual environment created at {env_dir}")

    def get_env_python(self):
        """
        Retrieves the path to the Python executable in the virtual environment.

        Returns:
            str: Path to the Python executable.
        """
        if os.name == "nt":
            python_executable = os.path.join(self.env_dir, "Scripts", "python.exe")
        else:
            python_executable = os.path.join(self.env_dir, "bin", "python")
        return python_executable

    def extract_code(self, text):
        """
        Extracts the main code blocks from the provided text, along with their language types and file extensions.
        This method handles nested code blocks by including them as part of the main code block content.

        Args:
            text (str): The text containing the code.

        Returns:
            list: A list of dictionaries with 'content', 'type', and 'extension' keys.
        """
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
        """
        Extracts the file path from the first line of the file content.

        Args:
            file_content (str): The content of the file.

        Returns:
            str or None: The extracted file path or None if not found.
        """
        first_line = file_content.split("\n")[0].strip()

        if first_line.startswith("#"):
            path_info = re.sub(r"^#\s*\.?\/?", "", first_line).strip()
            return path_info
        else:
            return None

    def generate_code(self, prompt, role="programmer", files=None, error_feedback=None):
        """
        Generates code based on the provided prompt using the fast_chat_programmer function.

        Args:
            prompt (str): The prompt to generate code for.
            role (str): The role of the agent ('programmer', 'tester', 'requirements').
            files (list of dict, optional): A list of dictionaries containing 'path', 'type', and 'content' of each file.
            error_feedback (str, optional): The error feedback.

        Returns:
            str: The generated code.
        """
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
            files_formatted = "\n\n".join(
                [f"```python\n{file['content']}\n```" for file in files]
            )
            messages.append({"role": "user", "content": files_formatted})
        if error_feedback:
            messages.append({"role": "user", "content": f"Error:\n{error_feedback}"})

        response = fast_chat_programmer(messages, temperature=0.1)
        return response

    def write_to_file(self, filepath, content):
        """
        Writes the provided content to a file at the specified filepath.

        Args:
            filepath (str): The path to the file.
        """
        if filepath is None:
            raise ValueError("No file path specified in code content.")

        # Remove existing file path comments and add the new one
        content = re.sub(r"^(\s*#.*\n)+", "", content)
        content = f"# {filepath}\n" + content

        full_path = os.path.join(self.workspace_dir, filepath)
        # Ensure the directory exists
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"File saved at: {full_path}")

    def filter_requirements(self, requirements_content):
        """
        Filters out standard library modules from the requirements.

        Args:
            requirements_content (str): The content of the requirements.txt file.

        Returns:
            str: Filtered non-standard packages.
        """
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        standard_lib_modules = set(stdlib_list(python_version))
        standard_lib_modules.update({"unittest", "mock"})
        packages = requirements_content.splitlines()
        non_standard_packages = [
            pkg.split("==")[0] for pkg in packages if pkg.split("==")[0] not in standard_lib_modules
        ]

        return "\n".join(non_standard_packages)

    def install_requirements(self):
        """
        Installs the packages listed in the requirements.txt file.
        """
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
        """
        Executes the script at the given filepath.

        Args:
            filepath (str): The path to the script to execute.

        Returns:
            tuple: A tuple containing a boolean indicating success and any error output.
        """
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

    async def run(self, user_prompt, max_clarifications=10, clarification_handler=None, verbose_handler=None):
        """
        Executes the code generation process based on the user's prompt.

        Args:
            user_prompt (str): The instructions provided by the user.
            clarification_handler (callable, optional): A callback function that receives a clarification question and returns the answer.
                                                        Should have the signature: func(question: str) -> str
                                                        If not provided, uses input() for interactions.
            verbose_handler (callable, optional): A callback function for verbose output.
                                                  Can be synchronous or asynchronous.
        """
        if verbose_handler is None:
            verbose_handler = lambda s: print(s)

        async def handle_verbose(message):
            if asyncio.iscoroutinefunction(verbose_handler):
                await verbose_handler(message)
            else:
                verbose_handler(message)

        clarification_interview = []
        for _ in range(max_clarifications):
            clarification = self.clarifier.clarify(user_prompt, clarification_interview)
            if clarification == "Nothing to clarify":
                break
            else:
                if clarification_handler and callable(clarification_handler):
                    if asyncio.iscoroutinefunction(clarification_handler):
                        clarification_response = await clarification_handler(clarification)
                    else:
                        clarification_response = clarification_handler(clarification)
                else:
                    clarification_response = input(f"Please answer the clarification question: {clarification}\n")
                clarification_interview.append({'question': clarification, 'answer': clarification_response})

        if clarification_interview:
            clarifications_text = "\n".join([f"Q: {qa['question']}\nA: {qa['answer']}" for qa in clarification_interview])
            roadmap_prompt = f"Prompt: {user_prompt}\nClarifications:\n{clarifications_text}"
        else:
            roadmap_prompt = f"Prompt: {user_prompt}"

        roadmap = self.clarifier.generate_roadmap(roadmap_prompt)
        
        print(f"Roadmap:\n{roadmap}")

        self.prompt = f"prompt: {user_prompt}\nroadmap:\n{roadmap}"
        test_prompt = "Write unit tests for the generated code."

        files = []
        error_feedback = None

        for iteration in range(1, self.max_iterations + 1):
            await handle_verbose(f"Starting iteration {iteration}...")
            files = [f for f in files if f["type"] == "code" or f["type"] == "test"]

            if error_feedback:
                self.prompt = "Resolve the errors and problems based on the feedback."
                test_prompt = "Resolve the errors and problems based on the feedback."
            code = self.generate_code(
                self.prompt,
                role="programmer",
                files=files,
                error_feedback=error_feedback,
            )
            code_blocks = self.extract_code(code)
            for code_block in code_blocks:
                path = self.extract_path(code_block['content'])
                self.write_to_file(path, code_block['content'])

                existing_file = next((f for f in files if f["path"] == path), None)
                if existing_file:
                    existing_file["content"] = code_block['content']
                else:
                    file = {"path": path, "type": "code", "content": code_block['content']}
                    files.append(file)

                if self.generate_tests:
                    test_code = self.generate_code(
                        test_prompt,
                        role="tester",
                        files=files,
                    )
                    test_blocks = self.extract_code(test_code)
                    if test_blocks:
                        test_content = test_blocks[0]['content']
                        test_path = self.extract_path(test_content)
                        self.write_to_file(test_path, test_content)

                        existing_test_file = next((f for f in files if f["path"] == test_path), None)
                        if existing_test_file:
                            existing_test_file["content"] = test_content
                        else:
                            test_file = {"path": test_path, "type": "test", "content": test_content}
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
                        await handle_verbose(
                            "Tests failed. The model will try to adjust the code based on the feedback."
                        )
                        print(error_feedback)
                        break  # Stop executing tests if one fails
            else:
                # If all tests pass, execute code files
                for file in files:
                    if file["type"] == "code":
                        script_success, run_info = self.execute_script(
                            file["path"]
                        )
                        if not script_success:
                            code_objects = self.extract_code(run_info)
                            if code_objects:
                                code_objects = [code_objects[-1]]
                            code_blocks = "\n".join(
                                #f"```{obj['type']}\n{clean_html_with_bs(obj['content']) if obj['type'] == 'html' else obj['content']}\n```"
                                f"```xpath map\n{json.dumps(generate_xpath_list(obj['content'])) if obj['type'] == 'html' else obj['content']}\n```"
                                for obj in code_objects
                            )
                            cleaned_text = re.sub(r"```html.*?```", "", run_info, flags=re.DOTALL)
                            error_feedback += (
                                f"Script errors in {file['path']}:\n{cleaned_text}\n"
                            )
                            error_feedback += f"use de path map to resolve find_element problems:\n{code_blocks}"
                            await handle_verbose(
                                "Script execution failed. The model will try to adjust the code based on the feedback."
                            )
                            print(error_feedback)
                            break
                else:
                    await handle_verbose(
                        "Task completed successfully! The code and tests work correctly."
                    )
                    return

        await handle_verbose(
            "Could not complete the task after several attempts. Consider providing more details or revising your description."
        )

def clean_html_with_bs(content):
    soup = BeautifulSoup(content, "html.parser")
    
    for element in soup.find_all("path"):
        element.decompose()
        
    for element in soup.find_all("script"):
        element.decompose()
        
    for element in soup.find_all("style"):
        element.decompose()
        
    for element in soup.find_all("link"):
        element.decompose()
        
    for element in soup.find_all("meta"):
        element.decompose()
        
    for element in soup.find_all("svg"):
        element.decompose()
    for element in soup.find_all("noscript"):
        element.decompose()
    
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
        
    allowed_attributes = {"id", "href", "src", "alt", "title", "name", "type", "value", "placeholder"}
    
    for element in soup.find_all():
        attributes_to_remove = [attr for attr in element.attrs if attr not in allowed_attributes]
        for attr in attributes_to_remove:
            element.attrs.pop(attr)
    
    return str(soup)


def generate_xpath_list(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    xpath_list = []

    def get_xpath(element):
        components = []
        for parent in element.parents:
            if parent.name:
                siblings = parent.find_all(element.name, recursive=False)
                if len(siblings) > 1:
                    index = siblings.index(element) + 1
                    components.append(f"{parent.name}[{index}]")
                else:
                    components.append(parent.name)
        components.reverse()
        components.append(element.name)
        xpath = "/" + "/".join(components)
        return xpath.replace("[document]/", "", 1)

    interactive_elements = soup.find_all(["a", "button", "input", "textarea", "select"])

    for element in interactive_elements:
        xpath = get_xpath(element)
        attributes = {key: value for key, value in element.attrs.items() if key in ["placeholder", "id", "href"]}
        details = {
            "xpath": xpath,
            "attributes": attributes,
            "text": element.get_text(strip=True),
        }
        xpath_list.append(details)

    return xpath_list