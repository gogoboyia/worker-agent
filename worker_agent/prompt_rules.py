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
    "The generated Python code should be structured to facilitate unit testing and allow dependency mocking, do not create tests. "
    "Do not return text outside of code blocks or additional explanations. "
    "For new code blocks, the name 'YOUR_SCRIPT_NAME' should be replaced with another name that makes sense for what the script does. "
    "Do not use placeholder paths like 'path/to/dependency' or 'C:/path/to/dependency'. "
    "Instead, handle dependencies and paths dynamically within the code or use methods that manage resources automatically. "
    "Service(ChromeDriverManager().install()) "
    'add the options:\nchrome_options.add_argument("--log-level=3") '
    #"options.add_argument(\"user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36\")"
    f'chrome_options.add_argument("--user-data-dir={get_chrome_profile_path()}") '
    "chrome_options.add_argument(\"--disable-blink-features=AutomationControlled\") "
    "chrome_options.add_experimental_option(\"excludeSwitches\", [\"enable-automation\"]) "
    "chrome_options.add_experimental_option(\"useAutomationExtension\", False) "
    'only one time, after driver.get, on the next line, get page content for debugging: sys.stdout.write(f"page source:\\n```html\\n{driver.page_source}\\n```\\n") '
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


CLARIFY_PROMPT = (
    "Given some instructions for building a Python script, determine if anything needs to be clarified, do not carry them out. "
    "Include potential issues, obstacles, and considerations,"
    "You can make reasonable assumptions, but if you are unsure, ask a single clarification question. "
    "respond in the same language as the prompt was made. "
    "ask short questions. "
    'Otherwise state: "Nothing to clarify"'
)
ROADMAP_PROMPT = (
    "Given a problem description, create a step-by-step roadmap to build script and fulfill the initial prompt. "
    "Include potential issues, obstacles, and considerations for each step. "
    "The roadmap should focus on clarity and practicality. "
    "return only the roadmap, without any explanations or additional comments. "
)
