import os
import re
import subprocess
import sys

from huggingface_hub import InferenceClient
from stdlib_list import stdlib_list

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


# Disable tokenizers parallelism to avoid potential issues
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# System prompts for different roles
PROGRAMMER_PROMPT = (
    "The scripts should be designed to work on macOS, Windows, and Linux. "
    "You are a Python programmer that writes code to solve specific tasks. "
    "Return only the Python code, without any explanations or additional comments. "
    "Do not remove the existing comments. "
    "Always generate Python code in English. "
    "Every Python file must start with a comment indicating the path of the file, e.g., '# YOUR_SCRIPT_NAME.py'. "
    "Output must be strictly limited to Python code blocks. "
    "The generated Python code should be structured to facilitate unit testing and allow dependency mocking, do not create tests. "
    "Do not return text outside of code blocks or additional explanations. "
    "For new files, the name 'YOUR_SCRIPT_NAME' should be replaced with another name that makes sense for what the script does. "
    "The errors from the generated scripts should not be entirely suppressed, allowing them to be captured in stderr for further analysis. "
    "If you don't find any problems in the script that gave an error in the feedback, try another approach to solve it. "
)

TESTER_PROMPT = (
    "The scripts should be designed to work on macOS, Windows, and Linux. "
    "You are a Python tester that writes unit tests for given code. "
    "Return only the unit test code, without any explanations or additional comments. "
    "Do not remove the existing comments. "
    "Always generate Python code in English. "
    "Every test file must start with a comment indicating the path of the file, e.g., '# test_YOUR_SCRIPT_NAME.py'. "
    "Output must be strictly limited to Python code blocks. "
    "The generated unit tests should cover various test cases and facilitate dependency mocking. "
    "Do not return text outside of code blocks or additional explanations. "
    "if all tests succeed do not allow stderr. "
    "If you don't find any problems in the script that gave an error in the feedback, try another approach to solve it. "
)

REQUIREMENTS_PROMPT = (
    "The scripts should be designed to work on macOS, Windows, and Linux. "
    "You are a requirements.txt creator that lists the required packages for a Python project. "
    "Use the provided code and test files to determine the required packages. "
    "Return only the contents of the requirements.txt file, without any explanations or additional comments. "
    "Output must be strictly limited to the contents of the requirements.txt file. "
    "Do not return text outside of code blocks or additional explanations. "
)


class ClarifierAgent:
    """
    Agent responsible for clarifying the initial prompt and providing a roadmap for problem resolution.
    """

    def __init__(self):
        self.agent_prompt = (
            "Given some instructions for building a Python script, determine if anything needs to be clarified, do not carry them out. "
            "You can make reasonable assumptions, but if you are unsure, ask a single clarification question. "
            'Otherwise state: "Nothing to clarify"'
        )
        self.roadmap_prompt = (
            "Given a problem description, create a step-by-step roadmap to build a Python script and fulfill the initial prompt. "
            "Include potential technologies, tools, and considerations for each step. "
            "The roadmap should focus on clarity and practicality."
        )

    def clarify(self, instructions):
        """
        Determines if the instructions need additional clarifications.

        Args:
            instructions (str): The instructions provided by the user.

        Returns:
            str: "Nothing to clarify" or a single clarification question.
        """
        messages = [
            {"role": "system", "content": self.agent_prompt},
            {"role": "user", "content": instructions},
        ]

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
            {"role": "system", "content": self.roadmap_prompt},
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
        Extracts code blocks from the provided text.

        Args:
            text (str): The text containing the code.

        Returns:
            list: A list of extracted code blocks.
        """
        code_blocks = re.findall(r"```(?:python)?\n(.*?)```", text, re.DOTALL)
        code_blocks = [block for block in code_blocks if block.strip()]
        if code_blocks:
            return code_blocks
        else:
            return [text]

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
        # Choose the appropriate system prompt based on the role
        if role == "programmer":
            system_prompt = PROGRAMMER_PROMPT
        elif role == "tester":
            system_prompt = TESTER_PROMPT
        elif role == "requirements":
            system_prompt = REQUIREMENTS_PROMPT
        else:
            system_prompt = PROGRAMMER_PROMPT  # Default to programmer prompt

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
            content (str): The content to write.
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
            return len(result.stderr) == 0, result.stderr
        except Exception as e:
            print(f"Error executing {os.path.basename(filepath)}: {e}")
            return False, str(e)

    def run(self, user_prompt, clarification_handler=None):
        """
        Executes the code generation process based on the user's prompt.

        Args:
            user_prompt (str): The instructions provided by the user.
            clarification_handler (callable, optional): A callback function that receives a clarification question and returns the answer.
                                                        Should have the signature: func(question: str) -> str
                                                        If not provided, uses input() for interactions.
        """
        # First step: clarify the prompt
        clarification = self.clarifier.clarify(user_prompt)
        print(f"ClarifierAgent response: {clarification}")

        if clarification != "Nothing to clarify":
            print(f"Clarification needed: {clarification}")
            if clarification_handler and callable(clarification_handler):
                user_response = clarification_handler(clarification)
                print(f"Received clarification response: {user_response}")
                user_prompt = f"{user_prompt} {user_response}"
            else:
                # Fallback to input() if no handler is provided
                user_response = input("Please answer the clarification question: ")
                user_prompt = f"{user_prompt} {user_response}"
        else:
            print("Nothing to clarify")
            
        roadmap = self.clarifier.generate_roadmap(user_prompt)

        self.prompt = f"prompt: {user_prompt}\nroadmap:\n{roadmap}"
        test_prompt = "Write unit tests for the generated code."

        # Initialize the list of files
        files = []
        error_feedback = None

        for iteration in range(1, self.max_iterations + 1):
            print(f"\nIteration {iteration}:")
            # Filter files to include only code and test types
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
            code_contents = self.extract_code(code)
            for code_content in code_contents:
                path = self.extract_path(code_content)
                self.write_to_file(path, code_content)

                existing_file = next((f for f in files if f["path"] == path), None)
                if existing_file:
                    existing_file["content"] = code_content
                else:
                    file = {"path": path, "type": "code", "content": code_content}
                    files.append(file)

                if self.generate_tests:
                    test_code = self.generate_code(
                        test_prompt,
                        role="tester",
                        files=files,
                    )
                    test_contents = self.extract_code(test_code)
                    if test_contents:
                        test_content = test_contents[0]
                        test_path = self.extract_path(test_content)
                        self.write_to_file(test_path, test_content)

                        existing_test_file = next((f for f in files if f["path"] == test_path), None)
                        if existing_test_file:
                            existing_test_file["content"] = test_content
                        else:
                            test_file = {"path": test_path, "type": "test", "content": test_content}
                            files.append(test_file)

            # Generate requirements.txt based on dependencies
            requirements = self.generate_code(
                "Create a requirements.txt file based on the dependencies in the code and test files provided.",
                role="requirements",
                files=files,
            )

            requirements_contents = self.extract_code(requirements)
            if requirements_contents:
                requirements_content = requirements_contents[0]

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
                    test_success, test_errors = self.execute_script(file["path"])
                    if not test_success:
                        error_feedback += (
                            f"Test errors in {file['path']}:\n{test_errors}\n"
                        )
                        print(
                            "Tests failed. The model will try to adjust the code based on the feedback."
                        )
                        print(error_feedback)
                        break  # Stop executing tests if one fails
            else:
                # If all tests pass, execute code files
                for file in files:
                    if file["type"] == "code":
                        script_success, script_errors = self.execute_script(
                            file["path"]
                        )
                        if not script_success:
                            error_feedback += (
                                f"Script errors in {file['path']}:\n{script_errors}\n"
                            )
                            print(
                                "Script execution failed. The model will try to adjust the code based on the feedback."
                            )
                            print(error_feedback)
                            break
                else:
                    print(
                        "\nTask completed successfully! The code and tests work correctly."
                    )
                    return  # Exit if successful

        print(
            "\nCould not complete the task after several attempts. Consider providing more details or revising your description."
        )