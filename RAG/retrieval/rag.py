import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from openai import OpenAI

# === Load environment variable ===
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# === Inisialisasi OpenAI Client ===
client = OpenAI(api_key=OPENAI_API_KEY)

# === Konfigurasi Qdrant ===
COLLECTION_NAME = "my_collection"
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
TOP_K = 5

# === Inisialisasi Qdrant Client ===
qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

# === Embedding dengan OpenAI ===
def get_openai_embedding(text: str) -> list[float]:
    response = client.embeddings.create(
        input=[text],
        model="text-embedding-ada-002"
    )
    return response.data[0].embedding

# === Retrieve konteks dari Qdrant ===
def retrieve_chunks(question: str) -> list[str]:
    query_vector = get_openai_embedding(question)

    results = qdrant.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        limit=TOP_K
    )

    return [hit.payload.get("text", "") for hit in results if hit.payload and "text" in hit.payload]

# === Tanyakan ke GPT dengan konteks ===
def ask_gpt(question: str, contexts: list[str]) -> str:
    context_text = "\n\n".join(contexts)
    prompt = f"""Gunakan informasi berikut untuk menjawab pertanyaan secara akurat dan ringkas.

Konteks:
{context_text}

Pertanyaan: {question}
Jawaban:"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Kamu adalah asisten cerdas yang hanya boleh menjawab berdasarkan konteks yang diberikan."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )

    return response.choices[0].message.content.strip()

# === Main CLI ===
if __name__ == "__main__":
    question = input("Masukkan pertanyaan: ")
    chunks = retrieve_chunks(question)

    if not chunks:
        print("Tidak ditemukan konteks yang relevan.")
    else:
        answer = ask_gpt(question, chunks)
        print("\nJawaban:\n", answer)
