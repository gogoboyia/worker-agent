import os
from huggingface_hub import InferenceClient

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