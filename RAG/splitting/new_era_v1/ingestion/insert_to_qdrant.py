import os
import json
import hashlib
from datetime import datetime
from tqdm import tqdm
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance

# ===== Logger =====
class Logger:
    def __init__(self, log_dir="log"):
        os.makedirs(log_dir, exist_ok=True)
        log_filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_InsertQdrant.log"
        self.LOG_FILE = os.path.join(log_dir, log_filename)

    def log_info(self, message, status="INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [{status}] {message}\n"
        with open(self.LOG_FILE, "a", encoding="utf-8") as log_file:
            log_file.write(log_message)
        print(log_message.strip())

# ===== Embedder =====
class Embedder:
    def __init__(self, api_key=None, embedding_model="text-embedding-3-small"):
        # Use the provided API key or look for it in environment variables
        self.client = OpenAI(api_key=api_key)
        self.embedding_model = embedding_model

    def embed_text(self, text: str) -> list[float]:
        response = self.client.embeddings.create(
            input=[text],
            model=self.embedding_model
        )
        return response.data[0].embedding

# ===== QdrantInserter with index.json caching =====
class QdrantInserter:
    def __init__(self,
                 collection_name: str,
                 api_key=None,
                 host="localhost",
                 port=6333,
                 index_path="database/index.json"):
        self.qdrant = QdrantClient(host=host, port=port)
        self.collection_name = collection_name
        self.logger = Logger()
        self.embedder = Embedder(api_key=api_key)
        # prepare index file
        self.index_path = index_path
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        self.inserted_ids = self._load_index()
        self.ensure_collection()

    def _load_index(self) -> set:
        if os.path.exists(self.index_path):
            try:
                with open(self.index_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.logger.log_info(f"Loaded index.json, {len(data)} IDs")
                    return set(data)
            except Exception as e:
                self.logger.log_info(f"Failed to read index.json: {e}", status="WARNING")
        return set()

    def _save_index(self):
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(sorted(self.inserted_ids), f, indent=2)
        self.logger.log_info(f"Saved index.json, total {len(self.inserted_ids)} IDs")

    def ensure_collection(self):
        if not self.qdrant.collection_exists(self.collection_name):
            self.qdrant.recreate_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
            )
            self.logger.log_info(f"Created new collection: {self.collection_name}")
        else:
            self.logger.log_info(f"Collection '{self.collection_name}' exists")

    def get_point_id(self, item_id: str) -> int:
        # deterministic numeric ID from string
        return int(hashlib.sha256(item_id.encode()).hexdigest(), 16) % (10**18)

    def insert_from_json(self, json_path: str):
        if not os.path.isfile(json_path):
            self.logger.log_info(f"File not found: {json_path}", status="ERROR")
            return

        with open(json_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                self.logger.log_info(f"Invalid JSON in {json_path}: {e}", status="ERROR")
                return

        total_inserted = 0
        total_skipped = 0

        for item in tqdm(data, desc="Processing items"):
            item_id = item.get("id")
            if not item_id:
                self.logger.log_info(f"SKIP: missing 'id' in item {item}", status="SKIP")
                total_skipped += 1
                continue

            if item_id in self.inserted_ids:
                self.logger.log_info(f"SKIP: ID {item_id} already in index.json", status="SKIP")
                total_skipped += 1
                continue

            text = item.get("text", "")
            metadata = item.get("metadata", {})
            point_id = self.get_point_id(item_id)

            try:
                vector = self.embedder.embed_text(text)
                payload = {
                    "item_id": item_id,
                    "text": text,
                    "metadata": metadata,
                }
                point = PointStruct(id=point_id, vector=vector, payload=payload)
                self.qdrant.upsert(collection_name=self.collection_name, points=[point])

                # update index
                self.inserted_ids.add(item_id)
                total_inserted += 1
                self.logger.log_info(f"INSERT: ID {item_id} succeeded")

            except Exception as e:
                self.logger.log_info(f"ERROR processing ID {item_id}: {e}", status="ERROR")

        # save index at end
        self._save_index()
        self.logger.log_info(f"Done: {total_inserted} inserted, {total_skipped} skipped")

# ===== Main =====
if __name__ == "__main__":
    # Your OpenAI API key
    openai_api_key = "xxx"  # Replace with your actual API key
    
    json_file = "database/chunk_result/ABF Indonesia Bond Index Fund_chunk.json"  # sesuaikan path
    collection = "try_first"  # ganti nama collection jika perlu

    inserter = QdrantInserter(collection_name=collection, api_key=openai_api_key)
    inserter.insert_from_json(json_file)