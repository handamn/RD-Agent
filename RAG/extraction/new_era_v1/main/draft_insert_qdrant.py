import json
import os
import openai
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct

# ==== Konfigurasi ====
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
COLLECTION_NAME = "my_collection"
EMBEDDING_MODEL = "text-embedding-ada-002"
EMBEDDING_DIM = 1536  # tergantung model, sesuaikan kalau pakai model lain
INPUT_JSON = "database/folder_json_extract/extract_a.json"

openai.api_key = os.getenv("OPENAI_API_KEY")  # atau langsung isi string (tidak disarankan)

# ==== Load Data ====
with open(INPUT_JSON, "r", encoding="utf-8") as f:
    items = json.load(f)

# ==== Inisialisasi Qdrant ====
client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

if not client.collection_exists(COLLECTION_NAME):
    client.recreate_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE)
    )

# ==== Proses dan Insert ====
points = []

for item in items:
    text = item["text"]
    vector = openai.Embedding.create(
        input=[text],
        model=EMBEDDING_MODEL
    )["data"][0]["embedding"]

    points.append(PointStruct(
        id=item["id"],
        vector=vector,
        payload=item["metadata"]  # metadata akan tersimpan di Qdrant sebagai payload
    ))

# Masukkan ke Qdrant
client.upsert(collection_name=COLLECTION_NAME, points=points)
print(f"Sukses menambahkan {len(points)} data ke collection '{COLLECTION_NAME}'.")
