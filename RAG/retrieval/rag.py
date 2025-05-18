import os
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from dotenv import load_dotenv
import json

load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

# ===== Config =====
COLLECTION_NAME = "tomoro_try"
TOP_K = 5
EMBEDDING_MODEL = "text-embedding-3-small"
COMPLETION_MODEL = "gpt-4o-mini"  # atau gpt-3.5-turbo

# ===== Clients =====
client = OpenAI(api_key=openai_api_key)
qdrant = QdrantClient(host="localhost", port=6333)

# ===== Embedder =====
def get_embedding(text: str) -> list[float]:
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=[text]
    )
    return response.data[0].embedding

# ===== Searcher =====
def search_qdrant(query: str, top_k=TOP_K):
    embedding = get_embedding(query)
    search_result = qdrant.search(
        collection_name=COLLECTION_NAME,
        query_vector=embedding,
        limit=top_k
    )
    return search_result

# ===== Prompt Builder =====
def build_prompt(query: str, context_chunks: list[dict]) -> str:
    context_texts = []
    for i, chunk in enumerate(context_chunks, 1):
        meta = chunk.payload
        filename = meta.get("document_metadata", {}).get("filename", "Unknown")
        page = meta.get("metadata", {}).get("page", "?")
        text = meta.get("text", "")
        context_texts.append(
            f"[{i}] From file: '{filename}', page {page}\n{text}"
        )
    context_block = "\n\n".join(context_texts)
    return f"""
Jawablah pertanyaan berikut berdasarkan konteks yang diberikan. Jika tidak ditemukan jawabannya, katakan "Maaf, saya tidak tahu".

### KONTEKS ###
{context_block}

### PERTANYAAN ###
{query}

### JAWABAN ###
"""

# ===== Completion =====
def get_answer(prompt: str) -> str:
    response = client.chat.completions.create(
        model=COMPLETION_MODEL,
        messages=[
            {"role": "system", "content": "Kamu adalah asisten cerdas yang menjawab berdasarkan dokumen."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        stream=False
    )
    return response.choices[0].message.content.strip()

# ===== CLI Chat Loop =====
def chat_loop():
    print("🧠 RAG Chatbot (Qdrant + OpenAI) — ketik 'exit' untuk keluar\n")
    history = []
    while True:
        try:
            user_input = input("👤 Kamu: ").strip()
            if user_input.lower() == "exit":
                print("👋 Sampai jumpa!")
                break

            search_results = search_qdrant(user_input)
            if not search_results:
                print("🤖 Bot: Maaf, tidak ditemukan informasi relevan.")
                continue

            prompt = build_prompt(user_input, search_results)
            answer = get_answer(prompt)
            print(f"\n🤖 Bot: {answer}\n")

            print("📄 Dokumen sumber:")
            for i, res in enumerate(search_results, 1):
                meta = res.payload
                filename = meta.get("document_metadata", {}).get("filename", "Unknown")
                page = meta.get("metadata", {}).get("page", "?")
                print(f"[{i}] File: {filename}, Page: {page}")

        except KeyboardInterrupt:
            print("\n👋 Exit dengan Ctrl+C")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

# ===== Run App =====
if __name__ == "__main__":
    chat_loop()
