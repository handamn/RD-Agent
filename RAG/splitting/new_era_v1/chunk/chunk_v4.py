import os
import json
import uuid
import datetime
import tiktoken
import google.generativeai as genai
from typing import List, Dict, Any

# ========== KONFIGURASI GEMINI ==========
GEMINI_MODEL = "gemini-pro"
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
gemini = genai.GenerativeModel(GEMINI_MODEL)

# ========== LOGGER ==========
class PdfExtractorLogger:
    def __init__(self, log_dir="logs"):
        os.makedirs(log_dir, exist_ok=True)
        log_filename = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_Extractor.log"
        self.LOG_FILE = os.path.join(log_dir, log_filename)

    def log(self, message, status="INFO"):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [{status}] {message}\n"
        with open(self.LOG_FILE, "a", encoding="utf-8") as log_file:
            log_file.write(log_message)
        print(log_message.strip())

# ========== UTAMA ==========
class PDFChunkProcessor:
    def __init__(self, input_names, input_folder="database/extracted_result", output_folder="database/chunk_result",
                 max_tokens=1000, overlap_tokens=100):
        self.input_names = input_names
        self.input_folder = input_folder
        self.output_folder = output_folder
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self.logger = PdfExtractorLogger()
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        os.makedirs(self.output_folder, exist_ok=True)

    def count_tokens(self, text):
        return len(self.tokenizer.encode(text))

    def clean_text(self, text):
        return text.replace("\n", " ").strip()

    def prompt_table_row(self, row: dict) -> str:
        return f"""Buatlah narasi ringkas dan profesional dari data tabel berikut. Narasi harus informatif, jelas, dan ditulis dalam bahasa Indonesia formal:

Data:
{json.dumps(row, indent=2, ensure_ascii=False)}

Output:"""

    def prompt_flowchart(self, elements: List[dict]) -> str:
        desc = "\n".join([
            f"- ({el['type']}) {el['text']} → {', '.join(el.get('next', []) or [])}" for el in elements
        ])
        return f"""Berikut adalah elemen dan koneksi dari suatu flowchart. Buatlah narasi ringkas dan terstruktur dalam bahasa Indonesia formal yang menjelaskan alur proses tersebut:

{desc}

Output:"""

    def generate_narrative(self, structured_data: Any, content_type: str) -> str:
        try:
            if content_type == "table":
                prompt = self.prompt_table_row(structured_data)
            elif content_type == "flowchart":
                prompt = self.prompt_flowchart(structured_data)
            else:
                return ""
            response = gemini.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            self.logger.log(f"Gagal generate narrative: {str(e)}", status="WARNING")
            return ""

    def convert_table_to_structured(self, table_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {key.lower().replace(" ", "_"): val for key, val in row.items() if val}
            for row in table_data
        ]

    def convert_flowchart_to_structured(self, elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {
                "id": el.get("id"),
                "text": el.get("text"),
                "type": el.get("type"),
                "next": [conn if isinstance(conn, str) else conn.get("target") for conn in el.get("connects_to", [])]
            } for el in elements
        ]

    def process(self):
        for name_list in self.input_names:
            name = name_list[0]
            input_path = os.path.join(self.input_folder, f"{name}.json")
            output_path = os.path.join(self.output_folder, f"chunked_{name}.json")
            self.process_pdf_json(input_path, output_path)

    def process_pdf_json(self, input_path, output_path):
        try:
            self.logger.log(f"Memproses file: {input_path}")
            with open(input_path, 'r', encoding='utf-8') as f:
                pdf_data = json.load(f)
            chunks = self.create_chunks(pdf_data)

            output_data = {
                "document_metadata": {
                    "filename": pdf_data.get("metadata", {}).get("filename", "unknown"),
                    "total_pages": pdf_data.get("metadata", {}).get("total_pages", 0),
                    "extraction_date": pdf_data.get("metadata", {}).get("extraction_date", ""),
                    "chunk_count": len(chunks)
                },
                "chunks": chunks
            }
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            self.logger.log(f"✔ Berhasil: {len(chunks)} chunk disimpan ke {output_path}")
        except Exception as e:
            self.logger.log(f"❌ Gagal memproses {input_path}: {str(e)}", status="ERROR")

    def create_chunks(self, json_data):
        chunks = []
        doc_meta = json_data.get("metadata", {})

        for page_num_str, page_data in sorted(json_data.get("pages", {}).items(), key=lambda x: int(x[0])):
            page_num = int(page_num_str)
            content_blocks = page_data.get("extraction", {}).get("content_blocks", [])

            for block in content_blocks:
                block_type = block["type"]
                block_id = block.get("block_id")

                if block_type == "table" and "data" in block:
                    structured_rows = self.convert_table_to_structured(block["data"])
                    for i, row_struct in enumerate(structured_rows):
                        narration = self.generate_narrative(row_struct, "table")
                        chunks.append({
                            "chunk_id": f"chunk_{uuid.uuid4().hex[:8]}",
                            "content": narration,
                            "structured_repr": row_struct,
                            "narrative_repr": narration,
                            "metadata": {
                                "document": doc_meta.get("filename", "unknown"),
                                "page": page_num,
                                "type": "table",
                                "block_id": block_id,
                                "row_index": i
                            }
                        })

                elif block_type == "flowchart" and "elements" in block:
                    structured = self.convert_flowchart_to_structured(block["elements"])
                    narration = self.generate_narrative(structured, "flowchart")
                    chunks.append({
                        "chunk_id": f"chunk_{uuid.uuid4().hex[:8]}",
                        "content": narration,
                        "structured_repr": {"steps": structured},
                        "narrative_repr": narration,
                        "metadata": {
                            "document": doc_meta.get("filename", "unknown"),
                            "page": page_num,
                            "type": "flowchart",
                            "block_id": block_id
                        }
                    })

                elif block_type == "text":
                    content = self.clean_text(block.get("content", ""))
                    if content:
                        chunks.append({
                            "chunk_id": f"chunk_{uuid.uuid4().hex[:8]}",
                            "content": content,
                            "structured_repr": None,
                            "narrative_repr": content,
                            "metadata": {
                                "document": doc_meta.get("filename", "unknown"),
                                "page": page_num,
                                "type": "text",
                                "block_id": block_id
                            }
                        })

                elif block_type == "image":
                    desc = self.clean_text(block.get("description_image", ""))
                    if desc:
                        chunks.append({
                            "chunk_id": f"chunk_{uuid.uuid4().hex[:8]}",
                            "content": desc,
                            "structured_repr": None,
                            "narrative_repr": desc,
                            "metadata": {
                                "document": doc_meta.get("filename", "unknown"),
                                "page": page_num,
                                "type": "image",
                                "block_id": block_id
                            }
                        })
        return chunks

# ========== CONTOH PENGGUNAAN ==========
pdf_files = [
    ["extracted_b"]
]

processor = PDFChunkProcessor(input_names=pdf_files)
processor.process()