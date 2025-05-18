import os
from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient

# === Setup ===
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=openai_api_key)
qdrant = QdrantClient(host="localhost", port=6333)

EMBED_MODEL = "text-embedding-3-small"
GPT_MODEL = "gpt-4o-mini"
COLLECTION_NAME = "tomoro_try"
TOP_K = 5

# === Langkah: Embedding query ===
def embed_query(text: str) -> list[float]:
    response = client.embeddings.create(
        input=[text],
        model=EMBED_MODEL
    )
    return response.data[0].embedding

# === Langkah: Ambil konteks dari Qdrant ===
def retrieve_context(query: str, top_k=TOP_K) -> list[str]:
    query_vector = embed_query(query)
    results = qdrant.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        limit=top_k
    )
    return [hit.payload["text"] for hit in results if "text" in hit.payload]

# === Langkah: Prompt dan minta jawaban ke GPT ===
def ask_with_context(question: str, contexts: list[str]) -> str:
    context_block = "\n\n".join(contexts)
    prompt = f"""Gunakan konteks berikut untuk menjawab pertanyaan.

Konteks:
{context_block}

Pertanyaan: {question}
Jawaban:"""

    response = client.chat.completions.create(
        model=GPT_MODEL,
        messages=[
            {"role": "system", "content": "Kamu adalah asisten cerdas. Jawablah hanya berdasarkan konteks yang tersedia. Jika tidak ada cukup informasi, jawab 'Maaf, saya tidak tahu.'"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )
    return response.choices[0].message.content.strip()

# === Main ===
if __name__ == "__main__":
    question = input("Masukkan pertanyaan: ")
    context = retrieve_context(question)

    if not context:
        print("Tidak ditemukan konteks relevan.")
    else:
        answer = ask_with_context(question, context)
        print("\nJawaban:\n", answer)
