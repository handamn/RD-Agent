import json
import os
from datetime import datetime
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
import openai


# === Logger sesuai standar perusahaan ===
class Logger:
    def __init__(self, log_dir="logs"):
        os.makedirs(log_dir, exist_ok=True)
        log_filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_InsertQdrant.log"
        self.LOG_FILE = os.path.join(log_dir, log_filename)

    def log_info(self, message, status="INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [{status}] {message}\n"
        with open(self.LOG_FILE, "a", encoding="utf-8") as log_file:
            log_file.write(log_message)
        print(log_message.strip())


# === Kelas utama untuk insert ke Qdrant ===
class QdrantInserter:
    def __init__(self, collection_name="my_collection", embedding_model="text-embedding-ada-002", embedding_dim=1536, log=None):
        self.logger = log or Logger()
        self.collection_name = collection_name
        self.embedding_model = embedding_model
        self.embedding_dim = embedding_dim

        # Proteksi jika OPENAI_API_KEY belum diset
        openai.api_key = os.getenv("OPENAI_API_KEY")
        if not openai.api_key:
            raise RuntimeError("OPENAI_API_KEY belum diset di environment variable.")

        # Koneksi ke Qdrant lokal
        self.client = QdrantClient(host="localhost", port=6333)

        # Inisialisasi collection jika belum ada
        if not self.client.collection_exists(self.collection_name):
            self.logger.log_info(f"Membuat collection baru: {self.collection_name}")
            self.client.recreate_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.embedding_dim, distance=Distance.COSINE)
            )
        else:
            self.logger.log_info(f"Collection '{self.collection_name}' sudah ada")

        # Ambil semua ID yang sudah ada
        self.existing_ids = self._fetch_existing_ids()

    def _fetch_existing_ids(self):
        self.logger.log_info("Mengambil daftar ID yang sudah ada di Qdrant...")
        existing_ids = set()
        offset = None
        while True:
            scroll_result, offset = self.client.scroll(
                collection_name=self.collection_name,
                limit=1000,
                offset=offset,
                with_payload=False
            )
            if not scroll_result:
                break
            for point in scroll_result:
                existing_ids.add(str(point.id))
        self.logger.log_info(f"Total ID yang ditemukan: {len(existing_ids)}")
        return existing_ids

    def embed_text(self, text):
        result = openai.Embedding.create(input=[text], model=self.embedding_model)
        return result["data"][0]["embedding"]

    def insert_from_json(self, json_path):
        self.logger.log_info(f"Memuat file: {json_path}")
        if not os.path.exists(json_path):
            self.logger.log_info("File tidak ditemukan!", status="ERROR")
            return

        with open(json_path, "r", encoding="utf-8") as f:
            try:
                items = json.load(f)
            except json.JSONDecodeError as e:
                self.logger.log_info(f"Gagal membaca JSON: {e}", status="ERROR")
                return

        inserted = 0
        skipped = 0

        for item in items:
            if not isinstance(item, dict) or not all(k in item for k in ("id", "text", "metadata")):
                self.logger.log_info(f"SKIP - Data tidak lengkap atau format salah: {item}", status="SKIP")
                continue

            point_id = item["id"]
            text = item["text"]
            metadata = item["metadata"]

            if str(point_id) in self.existing_ids:
                self.logger.log_info(f"SKIP - ID {point_id} sudah ada di Qdrant", status="SKIP")
                skipped += 1
                continue

            try:
                vector = self.embed_text(text)
                point = PointStruct(id=point_id, vector=vector, payload=metadata)
                self.client.upsert(collection_name=self.collection_name, points=[point])
                self.logger.log_info(f"INSERT - ID {point_id} berhasil dimasukkan ke Qdrant")
                inserted += 1
            except Exception as e:
                self.logger.log_info(f"ERROR saat proses ID {point_id}: {e}", status="ERROR")

        self.logger.log_info(f"Proses selesai: {inserted} inserted, {skipped} skipped")


# === Contoh pemakaian ===
if __name__ == "__main__":
    inserter = QdrantInserter()
    inserter.insert_from_json("database/folder_json_extract/extract_a.json")
