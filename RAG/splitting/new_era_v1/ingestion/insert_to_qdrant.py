import os
import json
import hashlib
from datetime import datetime
from tqdm import tqdm
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from dotenv import load_dotenv

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
                 index_path="database/index.json",
                 json_dir="database/chunked_result"):
        self.qdrant = QdrantClient(host=host, port=port)
        self.collection_name = collection_name
        self.logger = Logger()
        self.embedder = Embedder(api_key=api_key)
        # prepare index file
        self.index_path = index_path
        self.json_dir = json_dir
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        os.makedirs(self.json_dir, exist_ok=True)
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
        
        total_embedded = 0
        total_reused = 0
        total_skipped = 0
        total_failed = 0
        modified = False
        
        # Process each chunk/item
        for item in tqdm(items, desc="Processing items"):
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
                # Check if item already has embedding
                if "embedding" in item and item["embedding"]:
                    self.logger.log_info(f"REUSE: Using existing embedding for ID {item_id}")
                    vector = item["embedding"]
                    total_reused += 1
                else:
                    # Generate new embedding
                    self.logger.log_info(f"EMBED: Generating new embedding for ID {item_id}")
                    vector = self.embedder.embed_text(text)
                    # Save embedding back to the JSON structure
                    item["embedding"] = vector
                    modified = True
                    total_embedded += 1

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
        
        # Save the updated JSON with embeddings back to file if modified
        if modified:
            self.logger.log_info(f"Saving updated JSON with embeddings back to {json_path}")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        
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
    collection = "tomoro_try"  # ganti nama collection jika perlu
    
    # List file untuk diproses [name]
    files_to_process = [
        ['ABF Indonesia Bond Index Fund'],
        ['ABF Indonesia Bond Index Fund Update June 2024'],
        ['Avrist Ada Kas Mutiara'],
        ['Avrist Ada Saham Blue Safir Kelas A'],
        ['Avrist IDX30'],
        ['Avrist Prime Bond Fund'],
        ['Bahana Dana Likuid Kelas G'],
        ['Bahana Likuid Plus'],
        ['Bahana Likuid Syariah Kelas G'],
        ['Bahana MES Syariah Fund Kelas G'],
        ['Bahana Pendapatan Tetap Makara Prima kelas G'],
        ['Bahana Primavera 99 Kelas G'],
        ['Batavia Dana Kas Maxima'],
        ['Batavia Dana Likuid'],
        ['Batavia Dana Obligasi Ultima'],
        ['Batavia Dana Saham'],
        ['Batavia Dana Saham Syariah'],
        ['Batavia Index PEFINDO I-Grade'],
        ['Batavia Obligasi Platinum Plus'],
        ['Batavia Technology Sharia Equity USD'],
        ['BNI-AM Dana Lancar Syariah'],
        ['BNI-AM Dana Likuid Kelas A'],
        ['BNI-AM Dana Pendapatan Tetap Makara Investasi'],
        ['BNI-AM Dana Pendapatan Tetap Syariah Ardhani'],
        ['BNI-AM Dana Saham Inspiring Equity Fund'],
        ['BNI-AM IDX PEFINDO Prime Bank Kelas R1'],
        ['BNI-AM Indeks IDX30'],
        ['BNI-AM ITB Harmoni'],
        ['BNI-AM PEFINDO I-Grade Kelas R1'],
        ['BNI-AM Short Duration Bonds Index Kelas R1'],
        ['BNI-AM SRI KEHATI Kelas R1'],
        ['BNP Paribas Cakra Syariah USD Kelas RK1'],
        ['BNP Paribas Ekuitas'],
        ['BNP Paribas Greater China Equity Syariah USD'],
        ['BNP Paribas Infrastruktur Plus'],
        # ['BNP Paribas Pesona'],
        # ['BNP Paribas Pesona Syariah'],
        # ['BNP Paribas Prima II Kelas RK1'],
        # ['BNP Paribas Prima USD Kelas RK1'],
        # ['BNP Paribas Rupiah Plus'],
        # ['BNP Paribas Solaris'],
        # ['BNP Paribas SRI KEHATI'],
        # ['BNP Paribas Sukuk Negara Kelas RK1'],
        # ['BRI Indeks Syariah'],
        # ['BRI Mawar Konsumer 10 Kelas A'],
        # ['BRI Melati Pendapatan Utama'], ###############################
        # ['BRI MSCI Indonesia ESG Screened Kelas A'],
        # ['BRI Seruni Pasar Uang II Kelas A'],
        # ['BRI Seruni Pasar Uang III'],
        # ['BRI Seruni Pasar Uang Syariah'],
        # ['Danamas Pasti'],
        # ['Danamas Rupiah Plus'],
        # ['Danamas Stabil'],
        # ['Eastspring IDR Fixed Income Fund Kelas A'],
        # ['Eastspring IDX ESG Leaders Plus Kelas A'],
        # ['Eastspring Investments Cash Reserve Kelas A'],
        # ['Eastspring Investments Value Discovery Kelas A'],
        # ['Eastspring Investments Yield Discovery Kelas A'],
        # ['Eastspring Syariah Fixed Income Amanah Kelas A'],
        # ['Eastspring Syariah Greater China Equity USD Kelas A'],
        # ['Eastspring Syariah Money Market Khazanah Kelas A'],
        # ['Grow Dana Optima Kas Utama'],
        # ['Grow Obligasi Optima Dinamis Kelas O'],
        # ['Grow Saham Indonesia Plus Kelas O'],
        # ['Grow SRI KEHATI Kelas O'],
        # ['Jarvis Balanced Fund'],
        # ['Jarvis Money Market Fund'],
        # ['Majoris Pasar Uang Indonesia'],
        # ['Majoris Pasar Uang Syariah Indonesia'],
        # ['Majoris Saham Alokasi Dinamik Indonesia'],
        # ['Majoris Sukuk Negara Indonesia'],
        # ['Mandiri Indeks FTSE Indonesia ESG Kelas A'],
        # ['Mandiri Investa Atraktif-Syariah'],
        # ['Mandiri Investa Dana Syariah Kelas A'],
        # ['Mandiri Investa Dana Utama Kelas D'],
        # ['Mandiri Investa Pasar Uang Kelas A'],
        # ['Mandiri Investa Syariah Berimbang'],
        # ['Mandiri Pasar Uang Syariah Ekstra'],
        # ['Manulife Dana Kas II Kelas A'],
        # ['Manulife Dana Kas Syariah'],
        # ['Manulife Dana Saham Kelas A'],
        # ['Manulife Obligasi Negara Indonesia II Kelas A'],
        # ['Manulife Obligasi Unggulan Kelas A'],
        # ['Manulife Saham Andalan'],
        # ['Manulife Syariah Sektoral Amanah Kelas A'], #########################
        # ['Manulife USD Fixed Income Kelas A'], #######################
        # ['Principal Cash Fund'], ################
        # ['Principal Index IDX30 Kelas O'], ##################
        # ['Principal Islamic Equity Growth Syariah'], ##################
        # ['Schroder 90 Plus Equity Fund'],
        # ['Schroder Dana Andalan II'],
        # ['Schroder Dana Istimewa'],
        # ['Schroder Dana Likuid'],
        # ['Schroder Dana Likuid Syariah'],
        # ['Schroder Dana Mantap Plus II'],
        # ['Schroder Dana Prestasi'],
        # ['Schroder Dana Prestasi Plus'],
        # ['Schroder Dynamic Balanced Fund'],
        # ['Schroder Global Sharia Equity Fund USD'],
        # ['Schroder Syariah Balanced Fund'],
        # ['Schroder USD Bond Fund Kelas A'],
        # ['Simas Saham Unggulan'],
        # ['Simas Satu'],
        # ['Simas Syariah Unggulan'],
        # ['Sucorinvest Bond Fund'],
        # ['Sucorinvest Citra Dana Berimbang'],
        # ['Sucorinvest Equity Fund'],
        # ['Sucorinvest Flexi Fund'],
        # ['Sucorinvest Money Market Fund'],
        # ['Sucorinvest Premium Fund'],
        # ['Sucorinvest Sharia Balanced Fund'],
        # ['Sucorinvest Sharia Equity Fund'],
        # ['Sucorinvest Sharia Money Market Fund'],
        # ['Sucorinvest Sharia Sukuk Fund'],
        # ['Sucorinvest Stable Fund'],
        # ['TRAM Consumption Plus Kelas A'],
        # ['TRAM Strategic Plus Kelas A'],
        # ['TRIM Dana Tetap 2 Kelas A'],
        # ['TRIM Kapital'],
        # ['TRIM Kapital Plus'],
        # ['TRIM Kas 2 Kelas A'],
        # ['TRIM Syariah Saham'],
        # ['Trimegah Dana Tetap Syariah Kelas A'],
        # ['Trimegah FTSE Indonesia Low Volatility Factor Index'],
        # ['Trimegah Kas Syariah'],
        
    ]
    
    # Inisialisasi QdrantInserter
    inserter = QdrantInserter(
        collection_name=collection, 
        api_key=openai_api_key,
        json_dir="database/chunked_result"  # Sesuaikan dengan direktori Anda
    )
    
    # Proses semua file dalam daftar
    print("\nMemulai proses memasukkan data ke Qdrant...\n")
    inserter.process_files(files_to_process)