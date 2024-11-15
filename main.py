import os
import shutil
from core.agent import CodeGenerator

WORKSPACE_DIR = "workspace"
MAX_ITERATIONS = 15


# Clean up existing workspace directory if it exists
if os.path.exists(WORKSPACE_DIR):
    shutil.rmtree(WORKSPACE_DIR)

# Create workspace directory
os.makedirs(WORKSPACE_DIR, exist_ok=True)

def main():
    code_generator = CodeGenerator(WORKSPACE_DIR, MAX_ITERATIONS)

    user_prompt = "Open YouTube Music in Chrome and play a funk playlist."

    # Define a handler for clarification responses, if desired
    def my_clarification_handler(question):
        # Implement logic to respond to clarification questions
        # For example, map known questions to predefined answers
        # Or integrate with another interface to obtain user responses
        print(f"Clarification Question: {question}")
        # For this example, return a fixed response
        return "Use libraries that can interact with the Chrome browser and play music."

    code_generator.run(user_prompt, clarification_handler=my_clarification_handler)


if __name__ == "__main__":
    main()
