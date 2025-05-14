import json
import os
import uuid
import datetime
import tiktoken
from typing import List, Dict, Any

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

    def convert_table_to_structured_repr(self, table_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        structured = []
        for idx, row in enumerate(table_data):
            item = {key.lower().replace(" ", "_"): value for key, value in row.items() if value}
            structured.append({"row_index": idx, **item})
        return structured

    def convert_table_to_narrative(self, table_data: List[Dict[str, Any]]) -> List[str]:
        narrations = []
        for row in table_data:
            try:
                uraian = row.get("Uraian", "")
                pajak = row.get("Perlakuan Pajak", "")
                hukum = row.get("Dasar Hukum", "")
                if uraian and pajak:
                    sentence = f"{uraian.strip()} dikenai perlakuan pajak: {pajak.strip()}"
                    if hukum:
                        sentence += f" sesuai {hukum.strip()}"
                    sentence += "."
                    narrations.append(sentence)
            except Exception:
                continue
        return narrations

    def convert_flowchart_to_structured_repr(self, elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        structured = []
        for el in elements:
            structured.append({
                "id": el.get("id"),
                "text": el.get("text"),
                "type": el.get("type"),
                "next": [conn if isinstance(conn, str) else conn.get("target") for conn in el.get("connects_to", [])]
            })
        return structured

    def generate_narrative_with_llm(self, structured_data: Any, content_type: str) -> str:
        prompt = ""
        if content_type == "table":
            prompt = f"Buatlah narasi ringkas dan formal dari data tabel berikut:\n{structured_data}"
        elif content_type == "flowchart":
            prompt = f"Jelaskan secara ringkas dan terstruktur alur proses berikut:\n{structured_data}"

        # Di sini kamu bisa panggil Gemini API
        # Contoh dummy:
        # response = gemini.generate_content(prompt)
        # return response.text
        return f"[LLM Narrative] {prompt[:100]}..."

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
                if block_type == "table" and "data" in block:
                    structured = self.convert_table_to_structured_repr(block["data"])
                    narrations = self.convert_table_to_narrative(block["data"])
                    for i, (structure, narration) in enumerate(zip(structured, narrations)):
                        chunks.append({
                            "chunk_id": f"chunk_{uuid.uuid4().hex[:8]}",
                            "content": narration,
                            "structured_repr": structure,
                            "narrative_repr": narration,
                            "metadata": {
                                "document": doc_meta.get("filename", "unknown"),
                                "page": page_num,
                                "type": "table",
                                "block_id": block.get("block_id"),
                                "row_index": i
                            }
                        })

                elif block_type == "flowchart" and "elements" in block:
                    structured = self.convert_flowchart_to_structured_repr(block["elements"])
                    narration = self.generate_narrative_with_llm(structured, "flowchart")
                    chunks.append({
                        "chunk_id": f"chunk_{uuid.uuid4().hex[:8]}",
                        "content": narration,
                        "structured_repr": {"steps": structured},
                        "narrative_repr": narration,
                        "metadata": {
                            "document": doc_meta.get("filename", "unknown"),
                            "page": page_num,
                            "type": "flowchart",
                            "block_id": block.get("block_id")
                        }
                    })

                elif block_type == "text":
                    content = self.clean_text(block.get("content", ""))
                    if not content:
                        continue
                    chunks.append({
                        "chunk_id": f"chunk_{uuid.uuid4().hex[:8]}",
                        "content": content,
                        "structured_repr": None,
                        "narrative_repr": content,
                        "metadata": {
                            "document": doc_meta.get("filename", "unknown"),
                            "page": page_num,
                            "type": "text",
                            "block_id": block.get("block_id")
                        }
                    })

        return chunks

# Contoh penggunaan
pdf_files = [
    ["extracted_b"]
]

processor = PDFChunkProcessor(input_names=pdf_files)
processor.process()
