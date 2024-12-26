import os
import platform

def get_chrome_profile_path():
    """
    Retorna o caminho padrão do perfil de usuário do Google Chrome
    baseado no sistema operacional.
    
    Returns:
        str: Caminho do perfil do Chrome para o sistema operacional detectado.
    """
    user_home = os.path.expanduser("~")
    system = platform.system()
    if system == "Darwin":
        chrome_profile_path = os.path.join(user_home, "Library", "Application Support", "Google", "Chrome", "worker-agent")
    elif system == "Windows":
        chrome_profile_path = os.path.join(user_home, "AppData", "Local", "Google", "Chrome", "User Data")
    elif system == "Linux":
        chrome_profile_path = os.path.join(user_home, ".config", "google-chrome")
    else:
        raise ValueError(f"Sistema operacional não suportado: {system}")

    return chrome_profile_path

PROGRAMMER_PROMPT = (
    "The scripts/programmer should be designed to work on macOS, Windows, and Linux. "
    "You are a Python programmer that writes code blocks (```python\\ncontent\\n```) to solve specific tasks. "
    "Return only the code block, without any explanations or additional comments. "
    "Always generate Python code in English. "
    "Every code block represent one single file. "
    "Every code block must start with a comment indicating the path of the file, e.g., '# YOUR_SCRIPT_NAME.py'. "
    "Output must be strictly limited to code blocks. "
    "Do not return text outside of code blocks or additional explanations. "
    "For new code blocks, the name 'YOUR_SCRIPT_NAME' should be replaced with another name that makes sense for what the script does. "
    "Service(ChromeDriverManager().install()) "
    'add the options:\nchrome_options.add_argument("--log-level=3") '
    f'chrome_options.add_argument("--user-data-dir={get_chrome_profile_path()}") '
    "chrome_options.add_argument(\"--disable-blink-features=AutomationControlled\") "
    "chrome_options.add_experimental_option(\"excludeSwitches\", [\"enable-automation\"]) "
    "chrome_options.add_experimental_option(\"useAutomationExtension\", False) "
    "service.command_line_args().append(\"--detach\") # Keep browser open "
    'every time after exception get page content for debugging: sys.stdout.write(f"page source:\\n```html\\n{driver.page_source}\\n```\\n") '
    "Do not use `print`, use `sys.stdout.write()` or `sys.stderr.write()` instead. "
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
    "Do not return packages with code blocks or additional explanations. "
)

system_info = "macos"
default_browser = "chrome"

CLARIFY_PROMPT = (
    "Given some instructions that will be executed by another programming AI, determine if anything needs to be clarified, do not carry them out. "
    "Include potential issues, obstacles, and considerations,"
    "ask a single clarification question. "
    "respond in the same language as the prompt was made. "
    "ask short questions. "
    "My operating System: {system_info}"
    "My default Browser: {default_browser}"
    'Otherwise state: "Nothing to clarify"'
)
ROADMAP_PROMPT = (
    "Given a problem description, create a step-by-step roadmap to be executed by another programming AI. "
    "Include potential issues, obstacles, and considerations for each step. "
    "The roadmap should focus on clarity and practicality. "
    "return only the roadmap, without any explanations or additional comments. "
)


AGENT_DOC_PROMPT = """"
Given the content of a script, your task is to document its callable functions in JSON format.

The JSON should include:
- description: A brief summary of what the script does.
- filepath: The full path to the script.
- arguments: A dictionary of the script's arguments with example values.

Output:
```json
{
    "description": "Opens YouTube in Chrome and searches for a specified term.",
    "filepath": "example/open_chrome_example.py",
    "arguments": {
        "search_term": "TERM_TO_SEARCH",
    }
}
```
"""

AGENT_SCRIPT_RUNNER_PROMPT = """"
Given a user prompt, select the script description that best corresponds to the prompt.
You will receive a list of script calls in JSON format. For example:

Input exemple:
prompt: play romantic music
```json
[
    {
        "description": "Open YouTube in Chrome and search for a term",
        "filepath": "example/open_chrome_example.py",
        "arguments": {
            "search_term": "TERM_TO_SEARCH",
            "arg2": "..."
        }
    }
]
```
Output:
```json
{
    "description": "Open YouTube in Chrome and search for a term",
    "filepath": "example/open_chrome_example.py",
    "arguments": {
        "arg1": "romantic music",
        "arg2": "..."
    }
}
```
Otherwise state: "Nothing to run"
"""