import os
import json
import uuid
import time
import datetime
import tiktoken
import google.generativeai as genai
from typing import List, Dict, Any, Optional, Tuple
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
    DEFAULT_CONTEXT_TOKENS = 100  # Token untuk konteks dari chunk sebelumnya
    
    # Konfigurasi Teknis
    MAX_WORKERS = 1  # Jumlah thread paralel untuk API calls
    MAX_RETRIES = 3  # Jumlah retry jika API call gagal
    
    # Konfigurasi Path
    DEFAULT_INPUT_FOLDER = "database/extracted_result"
    DEFAULT_OUTPUT_FOLDER = "database/chunk_result"
    DEFAULT_LOG_DIR = "logs"

# ========== LOGGER ==========
class Logger:
    def __init__(self, log_dir=Config.DEFAULT_LOG_DIR, verbose=True):
        self.verbose = verbose
        os.makedirs(log_dir, exist_ok=True)
        log_filename = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_Extractor.log"
        self.LOG_FILE = os.path.join(log_dir, log_filename)
        self.last_progress = 0  # Untuk tracking progress terakhir yang ditampilkan

    def log(self, message, status="INFO"):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
    
    def progress(self, current, total, message="", min_update=5):
        """
        Menampilkan dan mencatat progress
        
        Args:
            current: Nilai saat ini
            total: Nilai total
            message: Pesan tambahan
            min_update: Persentase minimal untuk update (mencegah terlalu banyak log)
        """
        if total <= 0:
            return
            
        percent = int((current / total) * 100)
        
        # Hanya update jika ada perubahan signifikan atau sudah selesai
        if percent - self.last_progress >= min_update or percent >= 100:
            self.last_progress = percent
            
            # Buat progress bar
            bar_length = 30
            filled_length = int(bar_length * current // total)
            bar = '█' * filled_length + '░' * (bar_length - filled_length)
            
            # Format pesan progress
            prog_message = f"Progress: [{bar}] {percent}% ({current}/{total}) {message}"
            
            # Log ke file tanpa status khusus
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_message = f"[{timestamp}] [PROGRESS] {prog_message}\n"
            
            with open(self.LOG_FILE, "a", encoding="utf-8") as log_file:
                log_file.write(log_message)
            
            # Tampilkan di terminal dengan carriage return untuk update in-place
            if self.verbose:
                print(f"\r{prog_message}", end="", flush=True)
                if percent >= 100:
                    print()  # Baris baru setelah selesai
    
    def reset_progress(self):
        """Reset progress tracking untuk file baru"""
        self.last_progress = 0
        if self.verbose:
            print()  # Baris baru untuk memastikan progress bar berikutnya tampil dengan benar

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
    def generate_content(self, prompt):
        self.request_count += 1
        try:
            # Tambahkan rate limiting sederhana
            if self.request_count % 10 == 0:
                time.sleep(1)  # Jeda 1 detik setiap 10 request
                
            response = self.model.generate_content(prompt)
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
        return f"""Buatlah narasi ringkas dan profesional dari data tabel berikut. Narasi harus informatif, jelas, dan ditulis dalam bahasa Indonesia formal:

Data:
{json.dumps(row, indent=2, ensure_ascii=False)}"""

    @staticmethod
    def full_table_narrative(table_data: dict) -> str:
        rows = table_data.get("table_rows", [])
        return f"""Buatlah narasi ringkas dan profesional dari seluruh tabel berikut. Narasi harus informatif, jelas, dan menjelaskan hubungan antar data. Gunakan bahasa Indonesia formal:

Data Tabel ({len(rows)} baris):
{json.dumps(rows, indent=2, ensure_ascii=False)}"""

    @staticmethod
    def flowchart_narrative(elements: List[dict]) -> str:
        desc = "\n".join([
            f"- ({el['type']}) {el['text']} → {', '.join(str(n) for n in (el.get('next', []) or []) if n is not None)}" 
            for el in elements
        ])
        return f"""Berikut adalah elemen dan koneksi dari suatu flowchart. Buatlah narasi ringkas dan terstruktur dalam bahasa Indonesia formal yang menjelaskan alur proses tersebut:

    {desc}"""

# ========== CONTENT PROCESSOR ==========
class ContentProcessor:
    def __init__(self, gemini_client, logger=None):
        self.gemini_client = gemini_client
        self.logger = logger or Logger(verbose=False)
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
    def count_tokens(self, text):
        if not text:
            return 0
        return len(self.tokenizer.encode(text))
        
    def clean_text(self, text):
        if not text:
            return ""
        return text.replace("\n", " ").strip()
    
    def generate_narrative(self, structured_data: Any, content_type: str) -> str:
        if not structured_data:
            return ""
            
        try:
            if content_type == "table":
                prompt = Prompts.table_row_narrative(structured_data)
            elif content_type == "full_table":
                prompt = Prompts.full_table_narrative(structured_data)
            elif content_type == "flowchart":
                prompt = Prompts.flowchart_narrative(structured_data)
            else:
                self.logger.warning(f"Tipe konten tidak didukung: {content_type}")
                return ""
                
            return self.gemini_client.generate_content(prompt)
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

# ========== CHUNK CREATOR ==========
class ChunkCreator:
    def __init__(self, content_processor, max_workers=Config.MAX_WORKERS, logger=None, add_context=True, context_tokens=Config.DEFAULT_CONTEXT_TOKENS):
        self.content_processor = content_processor
        self.max_workers = max_workers
        self.logger = logger or Logger(verbose=False)
        self.add_context = add_context
        self.context_tokens = context_tokens
        self.prev_chunk_context = None  # Untuk menyimpan konteks dari chunk sebelumnya
        
    def create_document_chunks(self, json_data: Dict) -> List[Dict]:
        """Membuat chunk dari data JSON dokumen"""
        chunks = []
        doc_meta = json_data.get("metadata", {})
        pages = json_data.get("pages", {})
        
        # Validasi input
        if not pages:
            self.logger.warning("Tidak ada data halaman dalam dokumen")
            return []
        
        # Hitung total halaman dan blok untuk tracking progress    
        total_pages = len(pages)
        page_nums = sorted([int(pn) for pn in pages.keys()])
        
        # Reset konteks dari chunk sebelumnya
        self.prev_chunk_context = None
            
        # Iterasi melalui halaman
        for i, page_num in enumerate(page_nums):
            try:
                page_data = pages.get(str(page_num), {})
                page_chunks = self._process_page(page_num, page_data, doc_meta)
                chunks.extend(page_chunks)
                
                # Update progress
                self.logger.progress(
                    i + 1, 
                    total_pages, 
                    f"Halaman {page_num} ({len(page_chunks)} chunks)"
                )
                
            except Exception as e:
                self.logger.error(f"Gagal memproses halaman {page_num}: {str(e)}")
                
        return chunks
        
    def _process_page(self, page_num: int, page_data: Dict, doc_meta: Dict) -> List[Dict]:
        """Memproses satu halaman dokumen"""
        page_chunks = []
        content_blocks = page_data.get("extraction", {}).get("content_blocks", [])
        
        if not content_blocks:
            return []
        
        total_blocks = len(content_blocks)
        processed_blocks = 0
        
        # Proses blok secara berurutan untuk menangani konteks
        for block in content_blocks:
            try:
                result = self._process_block(block, page_num, doc_meta)
                processed_blocks += 1
                
                if result:
                    if isinstance(result, list):
                        page_chunks.extend(result)
                    else:
                        page_chunks.append(result)
                        
            except Exception as e:
                self.logger.error(f"Error saat memproses blok: {str(e)}")
                processed_blocks += 1  # Tetap increment untuk progress tracking
                
        return page_chunks
    
    def _process_block(self, block: Dict, page_num: int, doc_meta: Dict) -> List[Dict]:
        """Memproses satu blok konten"""
        block_chunks = []
        block_type = block.get("type")
        block_id = block.get("block_id", f"block_{uuid.uuid4().hex[:6]}")
        
        if not block_type:
            return []
            
        try:
            if block_type == "table" and "data" in block:
                chunk = self._process_table_block(block, page_num, doc_meta, block_id)
                if chunk:
                    block_chunks.append(chunk)
            elif block_type == "flowchart" and "elements" in block:
                chunk = self._process_flowchart_block(block, page_num, doc_meta, block_id)
                if chunk:
                    block_chunks.append(chunk)
            elif block_type == "text":
                chunk = self._process_text_block(block, page_num, doc_meta, block_id)
                if chunk:
                    # Simpan konten teks sebagai konteks untuk chunk berikutnya
                    self.prev_chunk_context = chunk.get("content", "")
                    block_chunks.append(chunk)
            elif block_type == "image":
                chunk = self._process_image_block(block, page_num, doc_meta, block_id)
                if chunk:
                    block_chunks.append(chunk)
        except Exception as e:
            self.logger.error(f"Gagal memproses blok {block_id} tipe {block_type}: {str(e)}")
            
        return block_chunks
    
    def _process_table_block(self, block: Dict, page_num: int, doc_meta: Dict, block_id: str) -> Optional[Dict]:
        """Memproses blok tabel sebagai satu chunk utuh"""
        structured_rows = self.content_processor.convert_table_to_structured(block.get("data", []))
        
        # Jika tabel kosong
        if not structured_rows:
            return None
        
        # Generate narasi untuk seluruh tabel
        narration = self.content_processor.generate_narrative(
            {"table_rows": structured_rows}, 
            "full_table"  # Tipe konten baru untuk tabel lengkap
        )
        
        if not narration:
            return None
        
        # Tambahkan konteks dari chunk sebelumnya jika diperlukan
        content = narration
        if self.add_context and self.prev_chunk_context:
            # Potong konteks ke jumlah token yang ditentukan
            context_text = self.prev_chunk_context
            if self.context_tokens > 0:
                # Hitung token dalam konteks
                tokens = self.content_processor.tokenizer.encode(context_text)
                if len(tokens) > self.context_tokens:
                    # Ambil token terakhir sesuai jumlah yang ditentukan
                    tokens = tokens[-self.context_tokens:]
                    context_text = self.content_processor.tokenizer.decode(tokens)
            
            content = f"{context_text} {narration}"
        
        # Buat satu chunk untuk seluruh tabel
        return self._create_chunk_object(
            content=content,
            structured_repr={"table_rows": structured_rows},
            narrative_repr=narration,
            metadata={
                "document": doc_meta.get("filename", "unknown"),
                "page": page_num,
                "type": "table",
                "block_id": block_id,
                "row_count": len(structured_rows),
                "has_context": self.add_context and bool(self.prev_chunk_context)
            }
        )
        
    def _process_flowchart_block(self, block: Dict, page_num: int, doc_meta: Dict, block_id: str) -> Optional[Dict]:
        """Memproses blok flowchart"""
        structured = self.content_processor.convert_flowchart_to_structured(block.get("elements", []))
        
        if not structured:
            return None
        
        # Validate structured data before generating narrative
        for i, element in enumerate(structured):
            if "next" in element and element["next"] is None:
                element["next"] = []  # Replace None with empty list
            elif "next" in element:
                # Filter out None values in next list
                element["next"] = [n for n in element["next"] if n is not None]
        
        narration = self.content_processor.generate_narrative(structured, "flowchart")
        if not narration:
            return None
        
        # Tambahkan konteks dari chunk sebelumnya jika diperlukan
        content = narration
        if self.add_context and self.prev_chunk_context:
            # Potong konteks ke jumlah token yang ditentukan
            context_text = self.prev_chunk_context
            if self.context_tokens > 0:
                # Hitung token dalam konteks
                tokens = self.content_processor.tokenizer.encode(context_text)
                if len(tokens) > self.context_tokens:
                    # Ambil token terakhir sesuai jumlah yang ditentukan
                    tokens = tokens[-self.context_tokens:]
                    context_text = self.content_processor.tokenizer.decode(tokens)
            
            content = f"{context_text} {narration}"
            
        return self._create_chunk_object(
            content=content,
            structured_repr={"steps": structured},
            narrative_repr=narration,
            metadata={
                "document": doc_meta.get("filename", "unknown"),
                "page": page_num,
                "type": "flowchart",
                "block_id": block_id,
                "has_context": self.add_context and bool(self.prev_chunk_context)
            }
        )
        
    def _process_text_block(self, block: Dict, page_num: int, doc_meta: Dict, block_id: str) -> Optional[Dict]:
        """Memproses blok teks"""
        content = self.content_processor.clean_text(block.get("content", ""))
        
        if not content:
            return None
            
        return self._create_chunk_object(
            content=content,
            structured_repr=None,
            narrative_repr=content,
            metadata={
                "document": doc_meta.get("filename", "unknown"),
                "page": page_num,
                "type": "text",
                "block_id": block_id
            }
        )
        
    def _process_image_block(self, block: Dict, page_num: int, doc_meta: Dict, block_id: str) -> Optional[Dict]:
        """Memproses blok gambar"""
        desc = self.content_processor.clean_text(block.get("description_image", ""))
        
        if not desc:
            return None
            
        return self._create_chunk_object(
            content=desc,
            structured_repr=None,
            narrative_repr=desc,
            metadata={
                "document": doc_meta.get("filename", "unknown"),
                "page": page_num,
                "type": "image",
                "block_id": block_id
            }
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
        
        return {
            "chunk_id": f"chunk_{uuid.uuid4().hex[:8]}",
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
                 add_context=True,
                 context_tokens=Config.DEFAULT_CONTEXT_TOKENS,
                 api_key=None,
                 continue_from_last=True,
                 max_workers=Config.MAX_WORKERS,
                 verbose=True):
        
        self.input_names = input_names or []
        self.input_folder = input_folder
        self.output_folder = output_folder
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self.add_context = add_context
        self.context_tokens = context_tokens
        self.continue_from_last = continue_from_last
        self.max_workers = max_workers
        
        # Buat direktori output jika belum ada
        os.makedirs(self.output_folder, exist_ok=True)
        
        # Inisialisasi komponen
        self.logger = Logger(verbose=verbose)
        self.gemini_client = GeminiClient(api_key=api_key, logger=self.logger)
        self.content_processor = ContentProcessor(self.gemini_client, logger=self.logger)
        self.chunk_creator = ChunkCreator(
            self.content_processor, 
            max_workers=self.max_workers, 
            logger=self.logger,
            add_context=self.add_context,
            context_tokens=self.context_tokens
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
        
        # Tampilkan progress keseluruhan
        self.logger.info(f"Memulai pemrosesan {total_files} file...")
        
        for i, name_list in enumerate(self.input_names):
            name = name_list[0]
            input_path = os.path.join(self.input_folder, f"{name}.json")
            output_path = os.path.join(self.output_folder, f"chunked_{name}.json")
            
            # Reset progress untuk file baru
            self.logger.reset_progress()
            
            # Update progress antar file
            self.logger.info(f"File {i+1}/{total_files}: {name}")
            
            # Validasi dan pemeriksaan file
            if not self.validate_input_file(input_path):
                failed_count += 1
                continue
                
            if not self.should_process_file(input_path, output_path):
                self.logger.info(f"Melewati file: {input_path}")
                continue
                
            # Proses file
            if self.process_pdf_json(input_path, output_path):
                success_count += 1
            else:
                failed_count += 1
                
        # Laporan akhir
        elapsed_time = time.time() - start_time
        self.logger.success(
            f"Selesai! {success_count} berhasil, {failed_count} gagal dalam {elapsed_time:.2f} detik. "
            f"Total {self.gemini_client.get_request_count()} API requests"
        )
        
        return success_count > 0
        
    def process_pdf_json(self, input_path, output_path):
        """Memproses satu file JSON"""
        try:
            self.logger.info(f"Memproses file: {input_path}")
            
            # Baca file input
            with open(input_path, 'r', encoding='utf-8') as f:
                pdf_data = json.load(f)
                
            # Ambil metadata untuk ditampilkan di progress
            doc_name = pdf_data.get("metadata", {}).get("filename", Path(input_path).stem)
            total_pages = len(pdf_data.get("pages", {}))
            
            self.logger.info(f"Dokumen: {doc_name}, Total halaman: {total_pages}")
            
            # Buat chunks
            self.logger.info(f"Membuat chunks dari {input_path}...")
            chunks = self.chunk_creator.create_document_chunks(pdf_data)
            
            if not chunks:
                self.logger.warning(f"Tidak ada chunks yang dihasilkan dari {input_path}")
                return False
                
            # Buat output data
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
            
            # Simpan output
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
        ["extracted_b"]
    ]
    
    # Inisialisasi processor dengan konfigurasi default
    processor = PDFChunkProcessor(
        input_names=pdf_files,
        continue_from_last=True,  # Lewati file yang sudah diproses
        add_context=True,         # Tambahkan konteks dari chunk sebelumnya untuk tabel dan flowchart
        context_tokens=100,       # Jumlah token konteks yang ditambahkan
        verbose=True              # Tampilkan log
    )
    
    # Jalankan pemrosesan
    processor.process()