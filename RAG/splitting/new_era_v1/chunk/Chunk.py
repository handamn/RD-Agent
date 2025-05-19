import os
import json
import uuid
import time
import datetime
import tiktoken
import google.generativeai as genai
from typing import List, Dict, Any, Optional, Tuple, Iterator
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tenacity import retry, stop_after_attempt, wait_exponential
from dotenv import load_dotenv

# ========== KONFIGURASI ==========
class Config:
    # Konfigurasi Model
    GEMINI_MODEL = "gemini-2.5-flash-preview-04-17"
    load_dotenv()
    API_KEY_ENV_VAR = os.getenv('GOOGLE_API_KEY')
    
    # Konfigurasi Chunking
    DEFAULT_MAX_TOKENS = 1000
    DEFAULT_OVERLAP_TOKENS = 100
    DEFAULT_CONTEXT_TOKENS = 100
    
    # Konfigurasi Teknis
    MAX_WORKERS = 5  # Jumlah thread paralel untuk API calls
    MAX_RETRIES = 10  # Jumlah retry jika API call gagal
    
    # Konfigurasi Path
    DEFAULT_INPUT_FOLDER = "database/extracted_result"
    DEFAULT_OUTPUT_FOLDER = "database/chunked_result"
    DEFAULT_LOG_DIR = "logs"


# ========== LOGGER ==========
class Logger:
    def __init__(self, log_dir=Config.DEFAULT_LOG_DIR, verbose=True):
        self.verbose = verbose
        os.makedirs(log_dir, exist_ok=True)
        log_filename = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_Extractor.log"
        self.LOG_FILE = os.path.join(log_dir, log_filename)
        self.current_stage = None
        self.current_task = None
        self.current_subtask = None

    def set_stage(self, stage):
        """Set the current high-level processing stage"""
        self.current_stage = stage
        self.current_task = None
        self.current_subtask = None
        self.log(f"STAGE: {stage}", "STAGE")

    def set_task(self, task):
        """Set the current task within the stage"""
        self.current_task = task
        self.current_subtask = None
        self.log(f"TASK: {task}", "TASK")

    def set_subtask(self, subtask):
        """Set the current subtask within the task"""
        self.current_subtask = subtask
        self.log(f"SUBTASK: {subtask}", "SUBTASK")

    def log(self, message, status="INFO"):
        """Log a message with the current context information"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Create context string based on available context
        context_parts = []
        if self.current_stage:
            context_parts.append(f"Stage: {self.current_stage}")
        if self.current_task:
            context_parts.append(f"Task: {self.current_task}")
        if self.current_subtask:
            context_parts.append(f"Subtask: {self.current_subtask}")
        
        context_str = " | ".join(context_parts)
        
        # Create the log message
        if context_str:
            log_message = f"[{timestamp}] [{status}] [{context_str}] {message}\n"
        else:
            log_message = f"[{timestamp}] [{status}] {message}\n"
        
        with open(self.LOG_FILE, "a", encoding="utf-8") as log_file:
            log_file.write(log_message)
            
        if self.verbose:
            print(log_message.strip())
            
    def success(self, message):
        self.log(f"✅ {message}", "SUCCESS")
        
    def error(self, message):
        self.log(f"❌ {message}", "ERROR")
        
    def warning(self, message):
        self.log(f"⚠️ {message}", "WARNING")
        
    def info(self, message):
        self.log(message, "INFO")
        
    def debug(self, message):
        self.log(message, "DEBUG")

    def start_file_processing(self, file_name, index=None, total=None):
        """Log the start of processing a new file"""
        if index is not None and total is not None:
            self.set_stage(f"Processing file {index}/{total}: {file_name}")
        else:
            self.set_stage(f"Processing file: {file_name}")
    
    def start_page_processing(self, page_num, total_pages):
        """Log the start of processing a new page"""
        self.set_task(f"Processing page {page_num}/{total_pages}")
        
# ========== GEMINI CLIENT ==========
class GeminiClient:
    def __init__(self, api_key=None, model=Config.GEMINI_MODEL, logger=None):
        self.logger = logger or Logger(verbose=False)
        
        # Inisialisasi API key
        api_key = api_key or os.getenv('GOOGLE_API_KEY')
        if not api_key:
            self.logger.error(f"API Key tidak ditemukan. Set environment variable {Config.API_KEY_ENV_VAR}")
            raise ValueError(f"API Key tidak ditemukan. Set environment variable {Config.API_KEY_ENV_VAR}")
        
        # Konfigurasi klien
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model)
        self.request_count = 0
        
    @retry(stop=stop_after_attempt(Config.MAX_RETRIES), 
           wait=wait_exponential(multiplier=1, min=2, max=10))
    def generate_content(self, prompt, response_format=None):
        self.request_count += 1
        try:
            # Tambahkan rate limiting sederhana
            if self.request_count % 10 == 0:
                time.sleep(1)  # Jeda 1 detik setiap 10 request
            
            generation_config = {}
            if response_format:
                generation_config["response_mime_type"] = response_format
                
            response = self.model.generate_content(prompt, generation_config=generation_config)
            
            # Jika response format adalah JSON, parse responsenya
            if response_format == "application/json":
                try:
                    return json.loads(response.text.strip())
                except json.JSONDecodeError:
                    self.logger.warning(f"Respons bukan JSON valid: {response.text[:100]}...")
                    return response.text.strip()
            
            return response.text.strip()
        except Exception as e:
            self.logger.error(f"Gemini API error: {str(e)}")
            raise  # Akan ditangkap oleh decorator retry
            
    def get_request_count(self):
        return self.request_count
    
# ========== PROMPTS ==========
class Prompts:
    @staticmethod
    def table_row_narrative(row: dict) -> str:
        return f"""Kamu bertugas menghasilkan narasi informasi dari data tabel berikut.

INSTRUKSI PENTING:
1. Langsung berikan narasinya saja tanpa kata pengantar atau kalimat pendahuluan
2. Jangan gunakan frasa seperti "Berikut adalah...", "Berdasarkan data...", atau sejenisnya
3. Berikan narasi yang ringkas, informatif, dan menggunakan bahasa formal
4. Jangan menyebutkan bahwa informasi berasal dari tabel
5. Format output harus berupa teks biasa, bukan dalam format Markdown

Data Tabel:
{json.dumps(row, indent=2, ensure_ascii=False)}

Narasi:"""

    @staticmethod
    def structured_table_row_narrative(row: dict) -> str:
        return f"""Kamu akan menghasilkan representasi naratif dari data tabel dalam format JSON yang terstruktur.

Data Tabel:
{json.dumps(row, indent=2, ensure_ascii=False)}

Berikan output dalam format JSON dengan struktur berikut:
{{
  "content": "Narasi lengkap dalam teks biasa tanpa format markdown",
  "keywords": ["kata_kunci1", "kata_kunci2"],
  "entities": ["entitas1", "entitas2"]
}}

INSTRUKSI PENTING:
1. "content" harus berupa narasi lengkap dan informatif yang menjelaskan seluruh konten tabel
2. Langsung berikan narasi utama tanpa kata pengantar seperti "Berikut" atau "Berdasarkan data"
3. "keywords" harus berisi 3-5 kata kunci yang mewakili topik utama dari konten
4. "entities" harus mencakup nama-nama entitas penting yang disebutkan (organisasi, peraturan, dll)
5. Jangan gunakan format markdown dalam output
6. Output harus berupa JSON valid

JSON Output:"""

    @staticmethod
    def flowchart_narrative(elements: List[dict]) -> str:
        desc = "\n".join([
            f"- ({el['type']}) {el['text']} → {', '.join(el.get('next', []) or [])}" for el in elements
        ])
        return f"""Buatlah narasi yang menjelaskan alur proses dari flowchart berikut.

INSTRUKSI PENTING:
1. Langsung berikan narasi utama tanpa kata pengantar seperti "Berikut adalah" atau "Flowchart ini menjelaskan"
2. Jangan gunakan format bullet point atau numbering
3. Gunakan bahasa formal dan lugas
4. Jelaskan proses secara berurutan dan jelas keterkaitannya
5. Jangan menyebutkan bahwa informasi ini berasal dari flowchart

Elemen Flowchart:
{desc}

Narasi:"""

    @staticmethod
    def structured_flowchart_narrative(flowchart_elements: Dict) -> str:
        elements = flowchart_elements.get("flowchart_elements", [])
        desc = "\n".join([
            f"- ({el['type']}) {el['text']} → {', '.join([str(n) for n in el.get('next', []) if n is not None])}" for el in elements
        ])
        return f"""Kamu akan menghasilkan representasi naratif dari flowchart dalam format JSON yang terstruktur.

    Elemen Flowchart:
    {desc}

    Berikan output dalam format JSON dengan struktur berikut:
    {{
    "content": "Narasi lengkap dalam teks biasa tanpa format markdown",
    "process_steps": ["langkah1", "langkah2", "langkah3"],
    "process_name": "Nama proses yang digambarkan"
    }}

    INSTRUKSI PENTING:
    1. "content" harus berupa narasi lengkap dan informatif yang menjelaskan alur proses secara berurutan
    2. Narasi harus langsung ke intinya tanpa kata pengantar seperti "Berikut" atau "Flowchart ini"
    3. "process_steps" harus berisi urutan langkah-langkah utama dalam flowchart (3-7 langkah)
    4. "process_name" harus singkat dan menggambarkan keseluruhan proses dalam 3-5 kata
    5. Output harus berupa JSON valid

    JSON Output:"""

# ========== CONTENT PROCESSOR ==========
class ContentProcessor:
    def __init__(self, gemini_client, logger=None, use_structured_output=True):
        self.gemini_client = gemini_client
        self.logger = logger or Logger(verbose=False)
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        self.use_structured_output = use_structured_output
        
    def count_tokens(self, text):
        if not text:
            return 0
        return len(self.tokenizer.encode(text))
        
    def clean_text(self, text):
        if not text:
            return ""
        return text.replace("\n", " ").strip()
    
    def generate_narrative(self, structured_data: Any, content_type: str) -> Any:
        if not structured_data:
            return ""
            
        try:
            if content_type == "table":
                if self.use_structured_output:
                    prompt = Prompts.structured_table_row_narrative(structured_data)
                    return self.gemini_client.generate_content(prompt, response_format="application/json")
                else:
                    prompt = Prompts.table_row_narrative(structured_data)
                    return self.gemini_client.generate_content(prompt)
            elif content_type == "flowchart":
                if self.use_structured_output:
                    prompt = Prompts.structured_flowchart_narrative(structured_data)
                    return self.gemini_client.generate_content(prompt, response_format="application/json")
                else:
                    prompt = Prompts.flowchart_narrative(structured_data)
                    return self.gemini_client.generate_content(prompt)
            else:
                self.logger.warning(f"Tipe konten tidak didukung: {content_type}")
                return ""
        except Exception as e:
            self.logger.warning(f"Gagal generate narrative untuk {content_type}: {str(e)}")
            return ""
    
    def convert_table_to_structured(self, table_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not table_data:
            return []
            
        return [
            {key.lower().replace(" ", "_"): val for key, val in row.items() if val}
            for row in table_data if row  # Filter rows yang kosong
        ]

    def convert_flowchart_to_structured(self, elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not elements:
            return []
            
        return [
            {
                "id": el.get("id", f"node_{i}"),  # Pastikan selalu ada ID
                "text": el.get("text", ""),
                "type": el.get("type", "unknown"),
                "next": [conn if isinstance(conn, str) else conn.get("target") 
                        for conn in el.get("connects_to", []) if conn]
            } for i, el in enumerate(elements) if el
        ]
        
    def extract_text_content_from_structured_response(self, structured_response):
        """Ekstrak konten teks dari respons terstruktur JSON"""
        if isinstance(structured_response, dict) and "content" in structured_response:
            return structured_response["content"]
        elif isinstance(structured_response, str):
            return structured_response
        else:
            self.logger.warning(f"Format respons tidak sesuai: {type(structured_response)}")
            return str(structured_response)

# ========== TEXT CHUNKER ==========
class TextChunker:
    def __init__(self, tokenizer, max_tokens=Config.DEFAULT_MAX_TOKENS, overlap_tokens=Config.DEFAULT_OVERLAP_TOKENS):
        self.tokenizer = tokenizer
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
    
    # Tambahkan fungsi generate_chunk_id sebagai metode statis
    @staticmethod
    def generate_chunk_id(document_name="unknown"):
        """
        Helper function to generate a standardized chunk ID that includes:
        - document name (sanitized)
        - current date in YYYYMMDD format
        - current time in HHMMSS format
        - random UUID segment
        
        Args:
            document_name: Name of the document, defaults to "unknown"
        
        Returns:
            Formatted chunk ID string
        """
        # Sanitize document name by removing spaces and special characters
        clean_document_name = "".join(c for c in document_name if c.isalnum())
        
        # Get current date and time
        now = datetime.datetime.now()
        date_str = now.strftime("%Y%m%d")
        time_str = now.strftime("%H%M%S")
        
        # Generate random UUID segment
        random_id = uuid.uuid4().hex[:8]
        
        # Combine all components
        return f"chunk_{clean_document_name}_{date_str}_{time_str}_{random_id}"
        
    def chunk_text(self, text_blocks: List[Dict]) -> List[Dict]:
        """
        Membuat chunks dari blok-blok teks dengan mempertimbangkan batas token maksimum dan overlap
        
        Args:
            text_blocks: List dari dict yang berisi konten teks dan metadata
                         Format: [{"content": "teks...", "metadata": {...}}, ...]
        
        Returns:
            List chunks teks yang sudah dibagi berdasarkan token
        """
        if not text_blocks:
            return []
            
        chunks = []
        current_chunk_text = ""
        current_chunk_tokens = 0
        current_chunk_blocks = []
        
        # Urutkan blok berdasarkan nomor halaman dan posisi blok
        sorted_blocks = sorted(text_blocks, key=lambda x: (
            x.get("metadata", {}).get("page", 0), 
            x.get("metadata", {}).get("block_position", 0)
        ))
        
        for block in sorted_blocks:
            content = block.get("content", "")
            if not content:
                continue
                
            block_tokens = len(self.tokenizer.encode(content))
            
            # Jika blok tunggal lebih besar dari max_tokens, pecah lebih kecil
            if block_tokens > self.max_tokens:
                # Selesaikan chunk yang sedang berjalan
                if current_chunk_text:
                    chunks.append(self._create_text_chunk(
                        current_chunk_text, 
                        current_chunk_blocks
                    ))
                    current_chunk_text = ""
                    current_chunk_tokens = 0
                    current_chunk_blocks = []
                    
                # Pecah blok besar menjadi chunks lebih kecil
                block_chunks = self._split_large_text_block(block)
                chunks.extend(block_chunks)
                continue
            
            # Jika menambahkan blok ini akan melebihi max_tokens
            if current_chunk_tokens + block_tokens > self.max_tokens:
                # Simpan chunk yang sedang berjalan
                chunks.append(self._create_text_chunk(
                    current_chunk_text, 
                    current_chunk_blocks
                ))
                
                # Mulai chunk baru dengan overlap dari chunk sebelumnya jika ada
                if self.overlap_tokens > 0 and current_chunk_text:
                    overlap_text = self._get_overlap_text(current_chunk_text)
                    current_chunk_text = overlap_text
                    current_chunk_tokens = len(self.tokenizer.encode(overlap_text))
                    
                    # Tentukan metadata blok mana yang masuk ke overlap
                    overlap_blocks = self._get_overlap_blocks(current_chunk_blocks)
                    current_chunk_blocks = overlap_blocks
                else:
                    current_chunk_text = ""
                    current_chunk_tokens = 0
                    current_chunk_blocks = []
            
            # Tambahkan blok ke chunk yang sedang berjalan
            if current_chunk_text:
                current_chunk_text += " " + content
            else:
                current_chunk_text = content
                
            current_chunk_tokens = len(self.tokenizer.encode(current_chunk_text))
            current_chunk_blocks.append(block)
        
        # Jangan lupa untuk menambahkan chunk terakhir jika ada
        if current_chunk_text:
            chunks.append(self._create_text_chunk(
                current_chunk_text, 
                current_chunk_blocks
            ))
            
        return chunks
    
    def _split_large_text_block(self, block: Dict) -> List[Dict]:
        """Memecah blok teks yang terlalu besar menjadi beberapa chunk"""
        content = block.get("content", "")
        metadata = block.get("metadata", {})
        tokens = self.tokenizer.encode(content)
        
        chunks = []
        for i in range(0, len(tokens), self.max_tokens - self.overlap_tokens):
            # Tentukan batas token untuk chunk ini
            end_idx = min(i + self.max_tokens, len(tokens))
            
            # Decode token kembali menjadi teks
            chunk_tokens = tokens[i:end_idx]
            chunk_text = self.tokenizer.decode(chunk_tokens)
            
            # Buat chunk baru dengan metadata yang sama tapi indikasi part
            chunk_metadata = metadata.copy()
            chunk_metadata["part"] = f"{i // (self.max_tokens - self.overlap_tokens) + 1}"
            
            chunks.append(self._create_text_chunk(
                chunk_text, 
                [{"content": chunk_text, "metadata": chunk_metadata}]
            ))
        
        return chunks
    
    def _get_overlap_text(self, text: str) -> str:
        """
        Mendapatkan teks overlap dari akhir chunk sebelumnya
        
        Ideally, chunk berdasarkan batas kalimat atau paragraf
        tetapi untuk implementasi sederhana, kita gunakan token saja
        """
        tokens = self.tokenizer.encode(text)
        if len(tokens) <= self.overlap_tokens:
            return text
            
        overlap_tokens = tokens[-self.overlap_tokens:]
        return self.tokenizer.decode(overlap_tokens)
    
    def _get_overlap_blocks(self, blocks: List[Dict]) -> List[Dict]:
        """
        Mendapatkan blok-blok yang masuk ke dalam overlap berdasarkan token
        
        Implementasi sederhana: ambil blok terakhir saja
        """
        if not blocks:
            return []
            
        # Untuk implementasi sederhana, kita ambil blok terakhir saja
        return [blocks[-1]]
    
    def _create_text_chunk(self, text: str, blocks: List[Dict]) -> Dict:
        """Membuat objek chunk dari teks yang sudah digabungkan"""
        # Gabungkan metadata dari semua blok
        block_ids = []
        pages = set()
        
        # Get document name for the chunk ID
        document_name = "unknown"
        
        for block in blocks:
            metadata = block.get("metadata", {})
            if "block_id" in metadata:
                block_ids.append(metadata["block_id"])
            if "page" in metadata:
                pages.add(metadata["page"])
            # Extract document name if available
            if "document" in metadata and metadata["document"] != "unknown":
                document_name = metadata["document"]
        
        # Sortir pages dan convert ke list
        pages = sorted(list(pages))
        
        return {
            "chunk_id": self.generate_chunk_id(document_name),  # Panggil sebagai self.generate_chunk_id
            "content": text,
            "structured_repr": None,
            "narrative_repr": text,
            "metadata": {
                "document": blocks[0].get("metadata", {}).get("document", "unknown") if blocks else "unknown",
                "pages": pages,
                "type": "text",
                "block_ids": block_ids,
                "blocks_count": len(blocks)
            }
        }

# ========== CHUNK CREATOR ==========
class ChunkCreator:
    def __init__(self, content_processor, max_workers=Config.MAX_WORKERS, 
                 max_tokens=Config.DEFAULT_MAX_TOKENS, overlap_tokens=Config.DEFAULT_OVERLAP_TOKENS, 
                 logger=None):
        self.content_processor = content_processor
        self.max_workers = max_workers
        self.logger = logger or Logger(verbose=False)
        self.text_chunker = TextChunker(
            content_processor.tokenizer, max_tokens, overlap_tokens
        )
        
    def create_document_chunks(self, json_data: Dict) -> List[Dict]:
        """Membuat chunk dari data JSON dokumen dengan mempertahankan urutan"""
        doc_meta = json_data.get("metadata", {})
        pages = json_data.get("pages", {})
        
        # Validasi input
        if not pages:
            self.logger.warning("Tidak ada data halaman dalam dokumen")
            return []
        
        doc_name = doc_meta.get("filename", "unknown")
        self.logger.set_task(f"Creating chunks for document: {doc_name}")
        
        # Kumpulkan semua blok dengan urutan asli
        self.logger.set_subtask("Collecting blocks from all pages")
        all_blocks = []
        
        # Hitung total halaman untuk tracking
        total_pages = len(pages)
        page_nums = sorted([int(pn) for pn in pages.keys()])
        
        # Iterasi melalui halaman untuk mengumpulkan blok
        for i, page_num in enumerate(page_nums):
            try:
                self.logger.info(f"Collecting blocks from page {page_num}/{total_pages}")
                page_data = pages.get(str(page_num), {})
                page_blocks = self._collect_page_blocks_with_order(page_num, page_data, doc_meta)
                all_blocks.extend(page_blocks)
                
            except Exception as e:
                self.logger.error(f"Gagal mengumpulkan blok halaman {page_num}: {str(e)}")
        
        # Proses blok-blok menjadi chunks
        self.logger.set_subtask(f"Processing {len(all_blocks)} blocks")
        self.logger.info(f"Processing blocks by type and creating chunks")
        
        # Kumpulkan chunks akhir
        final_chunks = []
        
        # Kumpulkan blok teks yang berdekatan untuk chunking
        current_text_blocks = []
        
        # Jumlah total blok untuk info
        total_blocks = len(all_blocks)
        processed_blocks = 0
        
        # Group blok berdasarkan tipe untuk logging
        block_types = {}
        for block in all_blocks:
            block_type = block.get("metadata", {}).get("type", "unknown")
            if block_type not in block_types:
                block_types[block_type] = 0
            block_types[block_type] += 1
        
        self.logger.info(f"Block type distribution: {block_types}")
        
        for block_obj in all_blocks:
            block_type = block_obj.get("metadata", {}).get("type")
            
            # Update processed count
            processed_blocks += 1
            
            # Log every 10% of progress or for every 100 blocks
            if processed_blocks % max(1, min(100, total_blocks // 10)) == 0:
                self.logger.info(f"Processed {processed_blocks}/{total_blocks} blocks ({processed_blocks/total_blocks:.1%})")
            
            if block_type == "text":
                # Tambahkan ke kumpulan blok teks yang sedang diproses
                current_text_blocks.append(block_obj)
            else:
                # Jika sebelumnya ada text blocks, proses dulu
                if current_text_blocks:
                    self.logger.debug(f"Creating text chunks from {len(current_text_blocks)} text blocks")
                    text_chunks = self.text_chunker.chunk_text(current_text_blocks)
                    final_chunks.extend(text_chunks)
                    current_text_blocks = []  # Reset
                
                # Proses non-text block
                self.logger.debug(f"Processing {block_type} block")
                chunk = self._process_non_text_block(block_obj)
                if chunk:
                    if isinstance(chunk, list):
                        final_chunks.extend(chunk)
                    else:
                        final_chunks.append(chunk)
        
        # Jangan lupa memproses text blocks terakhir jika ada
        if current_text_blocks:
            self.logger.debug(f"Creating text chunks from remaining {len(current_text_blocks)} text blocks")
            text_chunks = self.text_chunker.chunk_text(current_text_blocks)
            final_chunks.extend(text_chunks)
        
        self.logger.success(f"Created {len(final_chunks)} total chunks from document")
        return final_chunks
    
    def _collect_page_blocks_with_order(self, page_num: int, page_data: Dict, doc_meta: Dict) -> List[Dict]:
        """Mengumpulkan blok dari halaman dengan mempertahankan urutan asli"""
        page_blocks = []
        content_blocks = page_data.get("extraction", {}).get("content_blocks", [])
        
        if not content_blocks:
            return page_blocks
            
        # Tambahkan informasi posisi blok (untuk pengurutan)
        for i, block in enumerate(content_blocks):
            block_type = block.get("type")
            
            # Buat objek blok dengan metadata lengkap
            block_obj = {
                "original_block": block,
                "metadata": {
                    "document": doc_meta.get("filename", "unknown"),
                    "page": page_num,
                    "type": block_type,
                    "block_id": block.get("block_id", f"block_{uuid.uuid4().hex[:6]}"),
                    "block_position": i
                }
            }
            
            # Tambahkan konten untuk blok teks
            if block_type == "text":
                content = self.content_processor.clean_text(block.get("content", ""))
                if content:
                    block_obj["content"] = content
            
            page_blocks.append(block_obj)
            
        return page_blocks
    
    def _process_non_text_block(self, block_obj: Dict) -> Optional[Dict]:
        """Memproses blok non-teks (tabel, flowchart, gambar)"""
        original_block = block_obj.get("original_block", {})
        metadata = block_obj.get("metadata", {})
        block_type = metadata.get("type")
        
        try:
            if block_type == "table" and "data" in original_block:
                return self._process_table_block(original_block, metadata)
            elif block_type == "flowchart" and "elements" in original_block:
                return self._process_flowchart_block(original_block, metadata)
            elif block_type == "image":
                return self._process_image_block(original_block, metadata)
            else:
                self.logger.warning(f"Tipe blok tidak didukung: {block_type}")
                return None
        except Exception as e:
            self.logger.error(f"Gagal memproses blok {metadata.get('block_id')} tipe {block_type}: {str(e)}")
            return None
    
    def _process_table_block(self, block: Dict, metadata: Dict) -> List[Dict]:
        """Memproses blok tabel"""
        chunks = []
        
        # Set subtask for this specific table
        block_id = metadata.get("block_id", "unknown")
        page_num = metadata.get("page", "unknown")
        self.logger.set_subtask(f"Processing table block (ID: {block_id}, Page: {page_num})")
        
        # Convert table to structured format
        self.logger.debug("Converting table data to structured format")
        structured_rows = self.content_processor.convert_table_to_structured(block.get("data", []))
        
        # Jika tabel kosong
        if not structured_rows:
            self.logger.warning("Table is empty, skipping")
            return []
        
        # Buat satu representasi tabel lengkap (semua baris)
        table_struct = {"table_rows": structured_rows}
        
        # Generate narrative using Gemini API
        self.logger.debug(f"Generating narrative for table with {len(structured_rows)} rows using Gemini API")
        narration = self.content_processor.generate_narrative(table_struct, "table")
        
        # Process the response based on its type
        if isinstance(narration, dict):
            self.logger.debug("Received structured response from Gemini API")
            content = self.content_processor.extract_text_content_from_structured_response(narration)
            chunks.append(self._create_chunk_object(
                content=content,
                structured_repr=table_struct,
                narrative_repr=narration,  # Simpan respons lengkap
                metadata={
                    **metadata,
                    "row_count": len(structured_rows),
                    "has_context": True
                }
            ))
        else:
            self.logger.debug("Received plain text response from Gemini API")
            chunks.append(self._create_chunk_object(
                content=narration,
                structured_repr=table_struct,
                narrative_repr=narration,
                metadata={
                    **metadata,
                    "row_count": len(structured_rows),
                    "has_context": True
                }
            ))
        
        self.logger.debug(f"Created {len(chunks)} chunk(s) for table block")
        return chunks

    def _process_flowchart_block(self, block: Dict, metadata: Dict) -> List[Dict]:
        """Memproses blok flowchart, dengan penanganan yang mirip dengan tabel"""
        # Set subtask for this specific flowchart
        block_id = metadata.get("block_id", "unknown")
        page_num = metadata.get("page", "unknown")
        self.logger.set_subtask(f"Processing flowchart block (ID: {block_id}, Page: {page_num})")
        
        # Convert to structured format
        self.logger.debug("Converting flowchart elements to structured format")
        structured = self.content_processor.convert_flowchart_to_structured(block.get("elements", []))
        
        # Jika flowchart kosong
        if not structured:
            self.logger.warning("Flowchart is empty, skipping")
            return []
        
        # Buat satu representasi flowchart lengkap
        flowchart_struct = {"flowchart_elements": structured}
        
        # Generate narrative using Gemini API
        self.logger.info(f"Generating narrative for flowchart with {len(structured)} elements using Gemini API")
        
        # Panggil API dengan lebih eksplisit menangkap hasilnya
        narration = self.content_processor.generate_narrative(flowchart_struct, "flowchart")
        
        # Log API response type
        self.logger.debug(f"Gemini API response type: {type(narration)}")
        if isinstance(narration, dict):
            self.logger.debug(f"Structured response keys: {narration.keys()}")
        elif isinstance(narration, str):
            self.logger.debug(f"Plain text response length: {len(narration)}")
        else:
            self.logger.warning(f"Unexpected response type: {type(narration)}")
        
        chunks = []
        
        # Periksa apakah narasi kosong dan log warning jika iya
        if not narration:
            self.logger.warning("Narration is empty! Check API response and prompt.")
            # Gunakan fallback text untuk konten
            fallback_text = f"Diagram alur yang menunjukkan proses dengan {len(structured)} langkah."
            chunks.append(self._create_chunk_object(
                content=fallback_text,
                structured_repr=flowchart_struct,
                narrative_repr=fallback_text,
                metadata={
                    **metadata,
                    "element_count": len(structured),
                    "has_context": True,
                    "generated_narrative": False  # Flag untuk menandai narasi tidak berhasil digenerate
                }
            ))
            return chunks
        
        if isinstance(narration, dict):
            self.logger.debug("Processing structured response")
            content = self.content_processor.extract_text_content_from_structured_response(narration)
            if not content:  # Double check konten tidak kosong
                self.logger.warning("Content extracted from structured response is empty!")
                content = f"Diagram alur yang menunjukkan proses dengan {len(structured)} langkah."
                
            chunks.append(self._create_chunk_object(
                content=content,
                structured_repr=flowchart_struct,
                narrative_repr=narration,
                metadata={
                    **metadata,
                    "element_count": len(structured),
                    "has_context": True
                }
            ))
        else:
            self.logger.debug("Processing plain text response")
            # Pastikan narration tidak kosong sebelum menyimpannya
            if isinstance(narration, str) and not narration.strip():
                narration = f"Diagram alur yang menunjukkan proses dengan {len(structured)} langkah."
                
            chunks.append(self._create_chunk_object(
                content=narration,
                structured_repr=flowchart_struct,
                narrative_repr=narration,
                metadata={
                    **metadata,
                    "element_count": len(structured),
                    "has_context": True
                }
            ))
        
        self.logger.debug(f"Created {len(chunks)} chunk(s) for flowchart block")
        return chunks
        
    def _process_image_block(self, block: Dict, metadata: Dict) -> Optional[Dict]:
        """Memproses blok gambar"""
        desc = self.content_processor.clean_text(block.get("description_image", ""))
        
        if not desc:
            return None
            
        return self._create_chunk_object(
            content=desc,
            structured_repr=None,
            narrative_repr=desc,
            metadata=metadata
        )
        
    def _create_chunk_object(self, content, structured_repr, narrative_repr, metadata):
        """Helper untuk membuat objek chunk standar dengan pembersihan karakter newline"""
        # Bersihkan karakter newline dari seluruh konten teks
        if content:
            content = self.content_processor.clean_text(content)
        
        if isinstance(narrative_repr, str):
            narrative_repr = self.content_processor.clean_text(narrative_repr)
        
        # Untuk structured_repr, kita perlu rekursif karena bisa berisi nested structures
        if structured_repr:
            structured_repr = self._clean_structured_data(structured_repr)
        
        # Extract document name for chunk ID
        document_name = metadata.get("document", "unknown")
        
        return {
            "chunk_id": self.text_chunker.generate_chunk_id(document_name),  # Akses melalui self.text_chunker
            "content": content,
            "structured_repr": structured_repr,
            "narrative_repr": narrative_repr,
            "metadata": metadata
        }
    
    def _clean_structured_data(self, data):
        """Membersihkan karakter newline dari struktur data nested"""
        if isinstance(data, str):
            return self.content_processor.clean_text(data)
        elif isinstance(data, list):
            return [self._clean_structured_data(item) for item in data]
        elif isinstance(data, dict):
            return {k: self._clean_structured_data(v) for k, v in data.items()}
        else:
            return data

# ========== UTAMA ==========
class PDFChunkProcessor:
    def __init__(self, 
                 input_names=None,
                 input_folder=Config.DEFAULT_INPUT_FOLDER, 
                 output_folder=Config.DEFAULT_OUTPUT_FOLDER,
                 max_tokens=Config.DEFAULT_MAX_TOKENS, 
                 overlap_tokens=Config.DEFAULT_OVERLAP_TOKENS,
                 api_key=None,
                 continue_from_last=True,
                 max_workers=Config.MAX_WORKERS,
                 use_structured_output=True,
                 verbose=True):
        
        self.input_names = input_names or []
        self.input_folder = input_folder
        self.output_folder = output_folder
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self.continue_from_last = continue_from_last
        self.max_workers = max_workers
        self.use_structured_output = use_structured_output
        
        # Buat direktori output jika belum ada
        os.makedirs(self.output_folder, exist_ok=True)
        
        # Inisialisasi komponen
        self.logger = Logger(verbose=verbose)
        self.gemini_client = GeminiClient(api_key=api_key, logger=self.logger)
        self.content_processor = ContentProcessor(
            self.gemini_client, 
            logger=self.logger,
            use_structured_output=use_structured_output
        )
        self.chunk_creator = ChunkCreator(
            self.content_processor, 
            max_workers=self.max_workers, 
            max_tokens=self.max_tokens,
            overlap_tokens=self.overlap_tokens,
            logger=self.logger
        )
    
    def validate_input_file(self, input_path):
        """Memvalidasi file input"""
        path = Path(input_path)
        
        if not path.exists():
            self.logger.error(f"File tidak ditemukan: {input_path}")
            return False
            
        if not path.is_file():
            self.logger.error(f"Path bukan file: {input_path}")
            return False
            
        if path.suffix.lower() != '.json':
            self.logger.error(f"File bukan JSON: {input_path}")
            return False
            
        # Cek apakah file dapat dibuka dan berisi JSON valid
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                json.load(f)
            return True
        except json.JSONDecodeError:
            self.logger.error(f"File bukan JSON valid: {input_path}")
            return False
        except Exception as e:
            self.logger.error(f"Error saat membuka file {input_path}: {str(e)}")
            return False
    
    def should_process_file(self, input_path, output_path):
        """Memeriksa apakah file perlu diproses"""
        # Jika output sudah ada dan kita tidak ingin melanjutkan dari terakhir
        if Path(output_path).exists() and not self.continue_from_last:
            self.logger.warning(f"Output sudah ada dan continue_from_last=False: {output_path}")
            return False
            
        return True
    
    def process(self):
        """Memproses semua file yang ditentukan"""
        if not self.input_names:
            self.logger.error("Tidak ada file yang ditentukan untuk diproses")
            return False
            
        success_count = 0
        failed_count = 0
        total_files = len(self.input_names)
        start_time = time.time()
        
        # Log the start of the entire processing job
        self.logger.set_stage(f"DOCUMENT PROCESSING JOB: {total_files} file(s)")
        self.logger.info(f"Starting processing of {total_files} file(s) with max_tokens={self.max_tokens}, overlap_tokens={self.overlap_tokens}")
        
        for i, name_list in enumerate(self.input_names):
            name = name_list[0]
            input_path = os.path.join(self.input_folder, f"{name}_extracted.json")
            output_path = os.path.join(self.output_folder, f"{name}_chunked.json")
            
            # Update current stage to this file (i+1 of total)
            self.logger.start_file_processing(name, i+1, total_files)
            
            # Validasi dan pemeriksaan file
            self.logger.set_task("Validating input file")
            if not self.validate_input_file(input_path):
                self.logger.error(f"File validation failed: {input_path}")
                failed_count += 1
                continue
                
            if not self.should_process_file(input_path, output_path):
                self.logger.info(f"Skipping file (already processed): {input_path}")
                continue
                
            # Process file
            self.logger.set_task("Processing file content")
            if self.process_pdf_json(input_path, output_path):
                success_count += 1
            else:
                failed_count += 1
                
        # Final report
        elapsed_time = time.time() - start_time
        self.logger.set_stage("JOB COMPLETED")
        self.logger.success(
            f"Processing complete! Summary:\n"
            f"- Files processed successfully: {success_count}\n"
            f"- Files failed: {failed_count}\n"
            f"- Total time: {elapsed_time:.2f} seconds\n"
            f"- Total API requests: {self.gemini_client.get_request_count()}"
        )
        
        return success_count > 0
        
    def process_pdf_json(self, input_path, output_path):
        """Memproses satu file JSON"""
        try:
            # Start file processing stage
            self.logger.start_file_processing(Path(input_path).stem)
            
            # Read input file task
            self.logger.set_task("Reading input file")
            with open(input_path, 'r', encoding='utf-8') as f:
                pdf_data = json.load(f)
                    
            # Get metadata
            doc_name = pdf_data.get("metadata", {}).get("filename", Path(input_path).stem)
            total_pages = len(pdf_data.get("pages", {}))
            
            self.logger.info(f"Dokumen: {doc_name}, Total halaman: {total_pages}")
            
            # Generate chunks task
            self.logger.set_task("Generating document chunks")
            chunks = self.chunk_creator.create_document_chunks(pdf_data)
            
            if not chunks:
                self.logger.warning(f"Tidak ada chunks yang dihasilkan dari {input_path}")
                return False
                    
            # Create output data task
            self.logger.set_task("Creating output data structure")
            output_data = {
                "document_metadata": {
                    "filename": pdf_data.get("metadata", {}).get("filename", Path(input_path).stem),
                    "total_pages": pdf_data.get("metadata", {}).get("total_pages", 0),
                    "extraction_date": pdf_data.get("metadata", {}).get("extraction_date", 
                                                                datetime.datetime.now().isoformat()),
                    "processing_date": datetime.datetime.now().isoformat(),
                    "chunk_count": len(chunks)
                },
                "chunks": chunks
            }
            
            # Save output task
            self.logger.set_task("Saving output file")
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
                    
            self.logger.success(f"Berhasil: {len(chunks)} chunk disimpan ke {output_path}")
            return True
                
        except Exception as e:
            self.logger.error(f"Gagal memproses {input_path}: {str(e)}")
            return False

# ========== CONTOH PENGGUNAAN ==========
if __name__ == "__main__":
    # Daftar file yang akan diproses
    pdf_files = [
        # ['ABF Indonesia Bond Index Fund'],
        # ['ABF Indonesia Bond Index Fund Update June 2024'],
        # ['Avrist Ada Kas Mutiara'],
        # ['Avrist Ada Saham Blue Safir Kelas A'],
        # ['Avrist IDX30'],
        # ['Avrist Prime Bond Fund'],
        # ['Bahana Dana Likuid Kelas G'],
        # ['Bahana Likuid Plus'],
        # ['Bahana Likuid Syariah Kelas G'],
        # ['Bahana MES Syariah Fund Kelas G'],
        # ['Bahana Pendapatan Tetap Makara Prima kelas G'],
        # ['Bahana Primavera 99 Kelas G'],
        # ['Batavia Dana Kas Maxima'],
        # ['Batavia Dana Likuid'],
        # ['Batavia Dana Obligasi Ultima'],
        # ['Batavia Dana Saham'],
        # ['Batavia Dana Saham Syariah'],
        # ['Batavia Index PEFINDO I-Grade'],
        # ['Batavia Obligasi Platinum Plus'],
        # ['Batavia Technology Sharia Equity USD'],
        # ['BNI-AM Dana Lancar Syariah'],
        # ['BNI-AM Dana Likuid Kelas A'],
        # ['BNI-AM Dana Pendapatan Tetap Makara Investasi'],
        # ['BNI-AM Dana Pendapatan Tetap Syariah Ardhani'],
        # ['BNI-AM Dana Saham Inspiring Equity Fund'],
        # ['BNI-AM IDX PEFINDO Prime Bank Kelas R1'],
        # ['BNI-AM Indeks IDX30'],
        # ['BNI-AM ITB Harmoni'],
        # ['BNI-AM PEFINDO I-Grade Kelas R1'],
        # ['BNI-AM Short Duration Bonds Index Kelas R1'],
        # ['BNI-AM SRI KEHATI Kelas R1'],
        # ['BNP Paribas Cakra Syariah USD Kelas RK1'],
        # ['BNP Paribas Ekuitas'],
        # ['BNP Paribas Greater China Equity Syariah USD'],
        # ['BNP Paribas Infrastruktur Plus'],
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
        # ['BRI Melati Pendapatan Utama'], 
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
        # ['Grow Dana Optima Kas Utama'], ####
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
        # ['Manulife Syariah Sektoral Amanah Kelas A'], 
        # ['Manulife USD Fixed Income Kelas A'], 
        # ['Principal Cash Fund'], 
        # ['Principal Index IDX30 Kelas O'], 
        # ['Principal Islamic Equity Growth Syariah'], 
        # ['Schroder 90 Plus Equity Fund'],
        # ['Schroder Dana Andalan II'],
        # ['Schroder Dana Istimewa'],
        # ['Schroder Dana Likuid'],
        # ['Schroder Dana Likuid Syariah'],
        # ['Schroder Dana Mantap Plus II'],
        # ['Schroder Dana Prestasi'],
        ['Schroder Dana Prestasi Plus'],
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
    
    # Inisialisasi processor dengan konfigurasi default
    processor = PDFChunkProcessor(
        input_names=pdf_files,
        continue_from_last=True,         # Lewati file yang sudah diproses
        max_tokens=Config.DEFAULT_MAX_TOKENS,
        overlap_tokens=Config.DEFAULT_OVERLAP_TOKENS,
        use_structured_output=True,      # Gunakan output terstruktur (JSON) dari Gemini
        verbose=True                     # Tampilkan log
    )
    
    # Jalankan pemrosesan
    processor.process()