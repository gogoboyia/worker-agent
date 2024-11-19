import os
from worker_agent.agent import CodeGenerator
from worker_agent.agent import ClarifierAgent

def main():
    workspace = os.path.join(os.getcwd(), "workspace")
    os.makedirs(workspace, exist_ok=True)

    clarifier = ClarifierAgent()
    generator = CodeGenerator(workspace_dir=workspace, clarifier_agent=clarifier)

    user_prompt = input("Enter your prompt for code generation: ")
    generator.run(user_prompt)

if __name__ == "__main__":
    main()
