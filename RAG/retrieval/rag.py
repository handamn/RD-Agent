import os
from typing import List
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, SearchParams, PointStruct
from dotenv import load_dotenv

# ===== Load API Key and Setup =====
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
assert openai_api_key, "Please set OPENAI_API_KEY in .env"

# ===== Embedder =====
class Embedder:
    def __init__(self, api_key, model="text-embedding-3-small"):
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def embed(self, text: str) -> List[float]:
        response = self.client.embeddings.create(
            input=[text],
            model=self.model
        )
        return response.data[0].embedding

# ===== RAG Pipeline =====
class RAG:
    def __init__(self, collection_name: str, api_key: str, host="localhost", port=6333):
        self.embedder = Embedder(api_key=api_key)
        self.qdrant = QdrantClient(host=host, port=port)
        self.collection = collection_name
        self.client = OpenAI(api_key=api_key)

    def retrieve(self, query: str, top_k=5) -> List[dict]:
        vector = self.embedder.embed(query)
        hits = self.qdrant.search(
            collection_name=self.collection,
            query_vector=vector,
            limit=top_k,
            search_params=SearchParams(hnsw_ef=128),
        )
        return hits

    def build_context(self, hits: List[dict]) -> str:
        context = ""
        for i, hit in enumerate(hits):
            payload = hit.payload
            filename = payload.get("document_metadata", {}).get("filename", "Unknown File")
            page = payload.get("metadata", {}).get("page_number", "Unknown Page")
            text = payload.get("text", "")
            context += f"\n### Source {i+1}: {filename} (Page {page})\n{text.strip()}\n"
        return context.strip()

    def ask(self, query: str, top_k=5) -> str:
        hits = self.retrieve(query, top_k=top_k)
        context = self.build_context(hits)
        prompt = (
            f"Konteks berikut diambil dari beberapa dokumen perusahaan:\n\n"
            f"{context}\n\n"
            f"Pertanyaan: {query}\n"
            f"Jawaban yang berdasarkan konteks di atas:"
        )
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",  # or "gpt-3.5-turbo" if more cost-efficient
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return response.choices[0].message.content.strip()

# ===== CLI Entry Point =====
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RAG System - Qdrant + OpenAI")
    parser.add_argument("--query", "-q", type=str, required=True, help="Pertanyaan pengguna")
    parser.add_argument("--collection", "-c", type=str, default="tomoro_try", help="Nama koleksi Qdrant")
    parser.add_argument("--topk", "-k", type=int, default=5, help="Jumlah konteks yang diambil")
    args = parser.parse_args()

    rag = RAG(collection_name=args.collection, api_key=openai_api_key)
    answer = rag.ask(query=args.query, top_k=args.topk)
    print("\n========== JAWABAN ==========")
    print(answer)
