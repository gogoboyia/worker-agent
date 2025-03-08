import os
import requests
from openai import OpenAI

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

def get_chatgpt_response(messages, max_retries=5, temperature=0.5):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}",
    }

    response_text = ""
    retries = 0

    while retries < max_retries:
        payload = {
            "model": "gpt-4o-mini",
            "messages": messages,
            "temperature": temperature
        }

        response = requests.post(
            "https://api.openai.com/v1/chat/completions", headers=headers, json=payload
        )
        response_data = response.json()

        if 'error' in response_data:
            raise Exception(f"Erro na API: {response_data['error']['message']}")

        new_text = response_data["choices"][0]["message"]["content"].replace("**", "")
        finish_reason = response_data["choices"][0]["finish_reason"]

        response_text += new_text

        if finish_reason != "length":
            break
        else:
            messages.append({"role": "assistant", "content": new_text})
            messages.append({"role": "user", "content": "Continue."})
            retries += 1

    return response_text

clientOpenIa = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def fast_chat_programmer(messages, temperature = 0) -> str:
    accumulated_content = ""
    while True:
        response = clientOpenIa.chat.completions.create(
            model="o3-mini",
            messages=messages,
        )
        chunk = response.choices[0].message.content
        finish_reason = response.choices[0].finish_reason
        accumulated_content += chunk
        if finish_reason == "stop":
            break
        if finish_reason == "length":
            messages.append({"role": "assistant", "content": chunk})
            messages.append({"role": "user", "content": "Continue from where you left off."})
            continue
        break
    return accumulated_content.strip()
