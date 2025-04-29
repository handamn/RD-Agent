import json
from tiktoken import encoding_for_model  # pip install tiktoken

# Ganti dengan nama model yang tokenizernya paling mirip dengan Gemini (misal gpt-3.5-turbo)
MODEL_NAME = "gpt-3.5-turbo"

def count_tokens(text, model=MODEL_NAME):
    enc = encoding_for_model(model)
    return len(enc.encode(text))

def read_json_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def count_tokens_in_json(file_path, prompt=""):
    data = read_json_file(file_path)
    json_str = json.dumps(data, ensure_ascii=False, indent=2)  # Lebih readable
    full_input = prompt + "\n" + json_str
    token_count = count_tokens(full_input)
    return token_count

# Contoh penggunaan
if __name__ == "__main__":
    file_path = "yuhuu3.json"
    prompt = "Silakan ringkas informasi penting dari data berikut ini:"
    token_count = count_tokens_in_json(file_path, prompt)
    print(f"Total token input (prompt + JSON): {token_count}")
