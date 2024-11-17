from huggingface_hub import InferenceClient

# Initialize the inference client
client = InferenceClient(timeout=60*5)

# Read the file content
file_path = "./worker_agent/agent.py"
try:
    with open(file_path, "r") as file:
        file_contents = file.read()

    # Prepare the messages for the model
    messages = [{"role": "user", "content": f"Retorne o arquivo inteiro alterado. O ClarifierAgent além de resolver lacunas deve montar um roadmap para a resolucao do problema, abordando possiveis tecnologias para a resolucao do problemas. Montar uma seria de itens a serem resolvidos e considerados  :\n{file_contents}"}]

    # Generate a response using the model
    response = client.chat.completions.create(
        model="Qwen/Qwen2.5-Coder-32B-Instruct",
        messages=messages,
        max_tokens=20000,
        stream=False,
    )

    # Extract the refactored content from the response
    refactored_content = response.choices[0].message.content

    # Write the refactored content back to the file
    with open(file_path, "w") as file:
        file.write(refactored_content)

    print(f"The file {file_path} has been refactored successfully.")

except FileNotFoundError:
    print(f"The file at {file_path} was not found.")
except Exception as e:
    print(f"An error occurred: {e}")
