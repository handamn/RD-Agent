import os
import json
import hashlib
from datetime import datetime
from tqdm import tqdm
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from dotenv import load_dotenv
import shutil

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

# ===== QdrantInserter with separate output files =====
class QdrantInserter:
    def __init__(self,
                 collection_name: str,
                 api_key=None,
                 host="localhost",
                 port=6333,
                 index_path="database/index.json",
                 json_dir="database/chunked_result",
                 output_dir="database/embedded_result"):
        self.qdrant = QdrantClient(host=host, port=port)
        self.collection_name = collection_name
        self.logger = Logger()
        self.embedder = Embedder(api_key=api_key)
        # prepare index file
        self.index_path = index_path
        self.json_dir = json_dir
        self.output_dir = output_dir
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        os.makedirs(self.json_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
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

    def check_existing_embedding(self, item_id, json_filename):
        """Check if item has embedding in output directory"""
        output_json_path = os.path.join(self.output_dir, os.path.basename(json_filename))
        
        if os.path.exists(output_json_path):
            try:
                with open(output_json_path, "r", encoding="utf-8") as f:
                    output_data = json.load(f)
                
                # Check if data is in the new format or old format
                if "chunks" in output_data:
                    items = output_data["chunks"]
                    for item in items:
                        if item.get("chunk_id") == item_id and "embedding" in item and item["embedding"]:
                            return True, item["embedding"]
                else:
                    # Old format (list of items)
                    for item in output_data:
                        if item.get("id") == item_id and "embedding" in item and item["embedding"]:
                            return True, item["embedding"]
            except Exception as e:
                self.logger.log_info(f"Error checking existing embedding: {e}", status="WARNING")
        
        return False, None

    def insert_from_json(self, json_path: str):
        if not os.path.isfile(json_path):
            self.logger.log_info(f"File not found: {json_path}", status="ERROR")
            return

        # Load the JSON data
        with open(json_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                self.logger.log_info(f"Invalid JSON in {json_path}: {e}", status="ERROR")
                return

        # Check if data is in the new format (has "document_metadata" and "chunks")
        is_new_format = "document_metadata" in data and "chunks" in data
        
        if is_new_format:
            self.logger.log_info(f"Detected new JSON format with document metadata")
            items = data["chunks"]
            doc_metadata = data["document_metadata"]
        else:
            self.logger.log_info(f"Detected old JSON format (list of items)")
            items = data
            doc_metadata = {}
        
        # Create a copy of the data for the output file
        output_data = data.copy() if not is_new_format else {
            "document_metadata": doc_metadata.copy(),
            "chunks": [item.copy() for item in items]
        }
        
        # Get the filename for the output file
        output_json_path = os.path.join(self.output_dir, os.path.basename(json_path))
        
        # If output file exists, load it instead of creating a new one
        if os.path.exists(output_json_path):
            try:
                with open(output_json_path, "r", encoding="utf-8") as f:
                    output_data = json.load(f)
                self.logger.log_info(f"Loaded existing output file: {output_json_path}")
            except Exception as e:
                self.logger.log_info(f"Error loading existing output file: {e}. Creating new one.", status="WARNING")
        
        total_embedded = 0
        total_reused = 0
        total_skipped = 0
        total_failed = 0
        modified = False
        
        # Process each chunk/item
        for item_index, item in enumerate(tqdm(items, desc="Processing items")):
            # Get chunk_id or id based on format
            if is_new_format:
                item_id = item.get("chunk_id")
                content_field = "content"
                metadata_field = "metadata"
            else:
                item_id = item.get("id")
                content_field = "text"
                metadata_field = "metadata"

            if not item_id:
                self.logger.log_info(f"SKIP: missing id in item", status="SKIP")
                total_skipped += 1
                continue
                
            if item_id in self.inserted_ids:
                self.logger.log_info(f"SKIP: ID {item_id} already in index.json", status="SKIP")
                total_skipped += 1
                continue

            text = item.get(content_field, "")
            metadata = item.get(metadata_field, {})
            point_id = self.get_point_id(item_id)
            
            try:
                # Check if item already has embedding in source file
                has_embedding_in_source = "embedding" in item and item["embedding"]
                
                # Check if item has embedding in output directory
                has_embedding_in_output, existing_embedding = self.check_existing_embedding(item_id, json_path)
                
                if has_embedding_in_source or has_embedding_in_output:
                    # Use existing embedding
                    vector = item["embedding"] if has_embedding_in_source else existing_embedding
                    self.logger.log_info(f"REUSE: Using existing embedding for ID {item_id}")
                    total_reused += 1
                else:
                    # Generate new embedding
                    self.logger.log_info(f"EMBED: Generating new embedding for ID {item_id}")
                    vector = self.embedder.embed_text(text)
                    total_embedded += 1
                
                # Update the embedding in output_data
                if is_new_format:
                    output_data["chunks"][item_index]["embedding"] = vector
                else:
                    output_data[item_index]["embedding"] = vector
                
                modified = True

                # Prepare payload for Qdrant
                payload = {
                    "item_id": item_id,
                    "text": text,
                    "metadata": metadata
                }
                
                if is_new_format:
                    # Add document metadata to the payload
                    payload["document_metadata"] = {
                        "filename": doc_metadata.get("filename", ""),
                        "total_pages": doc_metadata.get("total_pages", 0),
                        "extraction_date": doc_metadata.get("extraction_date", "")
                    }
                
                # Create point and upsert to Qdrant
                point = PointStruct(id=point_id, vector=vector, payload=payload)
                self.qdrant.upsert(collection_name=self.collection_name, points=[point])
                
                # Update our index
                self.inserted_ids.add(item_id)
                self.logger.log_info(f"INSERT: ID {item_id} added to Qdrant")
            
            except Exception as e:
                self.logger.log_info(f"ERROR processing ID {item_id}: {e}", status="ERROR")
                total_failed += 1
        
        # Save the output file with embeddings
        if modified:
            self.logger.log_info(f"Saving JSON with embeddings to: {output_json_path}")
            with open(output_json_path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2)
        
        # Save the index at the end
        self._save_index()
        
        # Log summary
        self.logger.log_info(
            f"Done: {total_embedded} newly embedded, {total_reused} reused embeddings, "
            f"{total_skipped} skipped, {total_failed} failed"
        )

    def process_files(self, file_list):
        """Process a list of file names, looking for their chunked JSON files"""
        self.logger.log_info(f"Starting to process {len(file_list)} files")
        
        processed_count = 0
        failed_count = 0
        
        for file_name in file_list:
            # Get just the name if it's in a list format like your example
            if isinstance(file_name, list):
                file_name = file_name[0]
                
            # Construct the path to the chunked JSON file
            json_path = os.path.join(self.json_dir, f"{file_name}_chunked.json")
            
            self.logger.log_info(f"\n--- Processing: {file_name} ---")
            
            try:
                if os.path.exists(json_path):
                    self.insert_from_json(json_path)
                    self.logger.log_info(f"✓ Successfully processed: {file_name}")
                    processed_count += 1
                else:
                    self.logger.log_info(f"✗ JSON file not found: {json_path}", status="ERROR")
                    failed_count += 1
            except Exception as e:
                self.logger.log_info(f"✗ Failed to process {file_name}: {e}", status="ERROR")
                failed_count += 1
        
        self.logger.log_info(f"\nProcessing complete: {processed_count} successful, {failed_count} failed")
        return processed_count, failed_count

# ===== Main =====
if __name__ == "__main__":
    # Load environment variables
    load_dotenv()
    openai_api_key = os.getenv('OPENAI_API_KEY')
    
    # Collection name
    collection = "openai_db"  # ganti nama collection jika perlu
    
    # List file untuk diproses [name]
    files_to_process = [
        ['ABF Indonesia Bond Index Fund'],
    ]
    
    # Inisialisasi QdrantInserter
    inserter = QdrantInserter(
        collection_name=collection, 
        api_key=openai_api_key,
        json_dir="database/chunked_result",  # Direktori input
        output_dir="database/embedded_result"  # Direktori output untuk file dengan embedding
    )
    
    # Proses semua file dalam daftar
    print("\nMemulai proses memasukkan data ke Qdrant...\n")
    inserter.process_files(files_to_process)