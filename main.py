import asyncio
import os
import shutil
from worker_agent.agent import ClarifierAgent, CodeGenerator

WORKSPACE_DIR = "workspace"
MAX_ITERATIONS = 15


# Clean up existing workspace directory if it exists
if os.path.exists(WORKSPACE_DIR):
    shutil.rmtree(WORKSPACE_DIR)

# Create workspace directory
os.makedirs(WORKSPACE_DIR, exist_ok=True)


def main():
    clarifier_agent = ClarifierAgent(workspace_dir=WORKSPACE_DIR)
    code_generator = CodeGenerator(
        WORKSPACE_DIR,
        MAX_ITERATIONS,
        generate_tests=False,
        clarifier_agent=clarifier_agent,
    )

    user_prompt = "Open YouTube Music in Chrome and play the music 'caneta azul'."

    # Define a handler for clarification responses, if desired
    async def my_clarification_handler(question):
        """
        Handles clarification questions by prompting the user for input or
        returning a default response if none is provided.
        """
        # Prompt user for clarification
        response = input(f"Clarification Question (empty to deduce): {question}")

        # Provide a default response if the input is empty
        if not response:
            response = "make reasonable assumption."

        return response

    asyncio.run(
        code_generator.run(user_prompt, clarification_handler=my_clarification_handler)
    )


if __name__ == "__main__":
    main()
