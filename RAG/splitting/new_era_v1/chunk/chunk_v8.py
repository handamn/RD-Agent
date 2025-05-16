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
    def structured_flowchart_narrative(elements: List[dict]) -> str:
        desc = "\n".join([
            f"- ({el['type']}) {el['text']} → {', '.join(el.get('next', []) or [])}" for el in elements
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
        
        for block in blocks:
            metadata = block.get("metadata", {})
            if "block_id" in metadata:
                block_ids.append(metadata["block_id"])
            if "page" in metadata:
                pages.add(metadata["page"])
        
        # Sortir pages dan convert ke list
        pages = sorted(list(pages))
        
        return {
            "chunk_id": f"chunk_{uuid.uuid4().hex[:8]}",
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
        """Membuat chunk dari data JSON dokumen"""
        chunks = []
        doc_meta = json_data.get("metadata", {})
        pages = json_data.get("pages", {})
        
        # Validasi input
        if not pages:
            self.logger.warning("Tidak ada data halaman dalam dokumen")
            return []
        
        # Kumpulkan semua blok terlebih dahulu
        text_blocks = []
        non_text_blocks = []
        
        # Hitung total halaman untuk tracking progress
        total_pages = len(pages)
        page_nums = sorted([int(pn) for pn in pages.keys()])
        
        # Iterasi melalui halaman untuk mengumpulkan blok
        for i, page_num in enumerate(page_nums):
            try:
                page_data = pages.get(str(page_num), {})
                self._collect_page_blocks(page_num, page_data, doc_meta, text_blocks, non_text_blocks)
                
                # Update progress pengumpulan blok
                self.logger.progress(
                    i + 1, 
                    total_pages, 
                    f"Mengumpulkan blok halaman {page_num}"
                )
                
            except Exception as e:
                self.logger.error(f"Gagal mengumpulkan blok halaman {page_num}: {str(e)}")
        
        # Proses blok teks secara khusus (gabungkan yang berurutan)
        self.logger.info(f"Memproses {len(text_blocks)} blok teks dengan chunking...")
        text_chunks = self.text_chunker.chunk_text(text_blocks)
        chunks.extend(text_chunks)
        
        # Proses blok non-teks secara paralel
        self.logger.info(f"Memproses {len(non_text_blocks)} blok non-teks...")
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [
                executor.submit(self._process_non_text_block, block)
                for block in non_text_blocks
            ]
            
            for i, future in enumerate(as_completed(futures)):
                try:
                    result = future.result()
                    if result:
                        if isinstance(result, list):
                            chunks.extend(result)
                        else:
                            chunks.append(result)
                except Exception as e:
                    self.logger.error(f"Error saat memproses blok non-teks: {str(e)}")
                    
                # Update progress
                self.logger.progress(
                    i + 1, 
                    len(futures), 
                    "Memproses blok non-teks"
                )
                
        return chunks
        
    def _collect_page_blocks(self, page_num: int, page_data: Dict, doc_meta: Dict, 
                            text_blocks: List, non_text_blocks: List):
        """Mengumpulkan blok dari halaman dan memisahkan antara teks dan non-teks"""
        content_blocks = page_data.get("extraction", {}).get("content_blocks", [])
        
        if not content_blocks:
            return
            
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
            
            # Pisahkan berdasarkan tipe konten
            if block_type == "text":
                content = self.content_processor.clean_text(block.get("content", ""))
                if content:
                    block_obj["content"] = content
                    text_blocks.append(block_obj)
            else:
                non_text_blocks.append(block_obj)
    
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
        structured_rows = self.content_processor.convert_table_to_structured(block.get("data", []))
        
        # Jika tabel kosong
        if not structured_rows:
            return []
        
        # Buat satu representasi tabel lengkap (semua baris)
        table_struct = {"table_rows": structured_rows}
        narration = self.content_processor.generate_narrative(table_struct, "table")
        
        if isinstance(narration, dict):
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
                
        return chunks
        
    def _process_flowchart_block(self, block: Dict, metadata: Dict) -> Optional[Dict]:
        """Memproses blok flowchart"""
        structured = self.content_processor.convert_flowchart_to_structured(block.get("elements", []))
        
        if not structured:
            return None
        
        flowchart_struct = {"steps": structured}
        narration = self.content_processor.generate_narrative(flowchart_struct, "flowchart")
        
        if not narration:
            return None
            
        if isinstance(narration, dict):
            content = self.content_processor.extract_text_content_from_structured_response(narration)
            return self._create_chunk_object(
                content=content,
                structured_repr=flowchart_struct,
                narrative_repr=narration,  # Simpan respons lengkap
                metadata={
                    **metadata,
                    "element_count": len(structured)
                }
            )
        else:
            return self._create_chunk_object(
                content=narration,
                structured_repr=flowchart_struct,
                narrative_repr=narration,
                metadata=metadata
            )
        
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
        continue_from_last=True,         # Lewati file yang sudah diproses
        max_tokens=Config.DEFAULT_MAX_TOKENS,
        overlap_tokens=Config.DEFAULT_OVERLAP_TOKENS,
        use_structured_output=True,      # Gunakan output terstruktur (JSON) dari Gemini
        verbose=True                     # Tampilkan log
    )
    
    # Jalankan pemrosesan
    processor.process()