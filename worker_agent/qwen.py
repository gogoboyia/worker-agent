import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

# Carregar o modelo e o tokenizer do Qwen
model_name = "Qwen/Qwen2.5-Coder-3B-Instruct"

model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype=torch.bfloat16,  # Ajuste o dtype conforme necessário
    #device_map="auto"
)
tokenizer = AutoTokenizer.from_pretrained(model_name)

def slow_local_chat_programmer(messages, temperature=0.2):
    # Preparar o prompt no formato esperado pelo Qwen
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )
    
    # Tokenizar a entrada
    model_inputs = tokenizer([text], return_tensors="pt").to(model.device)
    
    # Gerar a resposta
    generated_ids = model.generate(
        **model_inputs,
        max_new_tokens=100000,
        temperature=temperature,
        do_sample=True,  # Necessário para que a temperatura tenha efeito
        top_p=0.9,       # Você pode ajustar esses parâmetros conforme necessário
        top_k=40
    )
    
    # Remover os tokens de entrada para obter apenas a resposta gerada
    generated_ids = [
        output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
    ]
    
    # Decodificar os tokens gerados para texto
    response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
    
    return response
