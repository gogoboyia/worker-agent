import os
import google.generativeai as genai

def extract_system_instructions(messages):
    instructions = []
    for message in messages:
        if message.get("role") == "system":
            if "parts" in message:
                instructions.append("".join(message["parts"]))
            elif "content" in message:
                content = message["content"]
                if isinstance(content, dict) and "parts" in content:
                    instructions.append("".join(content["parts"]))
                else:
                    instructions.append(str(content))
    return "\n".join(instructions)

def format_messages(messages):
    formatted = []
    for message in messages:
        role = message.get("role")
        # Ignora mensagens do sistema, pois já foram extraídas separadamente
        if role == "system":
            continue
        # Converte "assistant" para "model"
        if role == "assistant":
            role = "model"
        if "parts" in message:
            parts = message["parts"]
        elif "content" in message:
            content = message["content"]
            if isinstance(content, dict) and "parts" in content:
                parts = content["parts"]
            else:
                parts = [content]
        else:
            parts = []
        formatted.append({"role": role, "parts": parts})
    return formatted

def extract_prompt(message):
    if "parts" in message:
        return "".join(message["parts"])
    elif "content" in message:
        content = message["content"]
        if isinstance(content, dict) and "parts" in content:
            return "".join(content["parts"])
        else:
            return str(content)
    return ""

def fast_chat_programmer(messages, temperature=0.2):
    if not messages:
        raise ValueError("Nenhuma mensagem fornecida.")

    # Extrai e concatena as mensagens de sistema para formar o system_instruction
    system_instruction = extract_system_instructions(messages)

    # A última mensagem é o prompt que será enviado
    prompt_message = messages[-1]
    # O restante compõe o histórico da conversa (excluindo as mensagens de sistema)
    history_messages = messages[:-1]

    # Configura a API key usando a variável de ambiente GEMINI_API_KEY
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])

    generation_config = {
        "temperature": temperature,
        "top_p": 0.95,
        "top_k": 64,
        "max_output_tokens": 20000,
        "response_mime_type": "text/plain",
    }

    # Cria o modelo Gemini 2.0 Flash Thinking, passando o system_instruction extraído
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash-thinking-exp-01-21",
        generation_config=generation_config,
        system_instruction=system_instruction,
    )

    # Formata as mensagens do histórico para o formato esperado
    formatted_history = format_messages(history_messages)

    # Inicia uma sessão de chat com o histórico fornecido
    chat_session = model.start_chat(history=formatted_history)

    # Extrai o texto do prompt da última mensagem
    prompt = extract_prompt(prompt_message)

    # Envia o prompt extraído e retorna a resposta
    response = chat_session.send_message(prompt)
    return response.text
