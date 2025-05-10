import json
import os
import uuid
import datetime
import tiktoken

# ====== Logger Class (Standar Perusahaan) ======
class PdfExtractorLogger:
    """Logger untuk mencatat aktivitas ekstraksi PDF ke file log yang sama."""
    def __init__(self, log_dir="logs"):
        os.makedirs(log_dir, exist_ok=True)
        log_filename = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_Extractor.log"
        self.LOG_FILE = os.path.join(log_dir, log_filename)

    def log(self, message, status="INFO"):
        """Menyimpan log ke file dengan format timestamp."""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [{status}] {message}\n"
        with open(self.LOG_FILE, "a", encoding="utf-8") as log_file:
            log_file.write(log_message)
        print(log_message.strip())

# ====== Parameter Hardcoded ======
INPUT_PATH = "database/extracted_result/extracted_b.json"
OUTPUT_PATH = "database/output_chunks"
MAX_TOKENS = 1000
OVERLAP_TOKENS = 100

logger = PdfExtractorLogger()

tokenizer = tiktoken.get_encoding("cl100k_base")

def count_tokens(text):
    return len(tokenizer.encode(text))

def clean_text(text):
    return text.replace("\n", " ").strip()

def create_chunks(json_data, max_tokens=MAX_TOKENS, overlap_tokens=OVERLAP_TOKENS):
    chunks = []
    document_metadata = {
        "filename": json_data.get("metadata", {}).get("filename", "unknown"),
        "total_pages": json_data.get("metadata", {}).get("total_pages", 0),
    }

    for page_num_str, page_data in sorted(json_data.get("pages", {}).items(), key=lambda x: int(x[0])):
        page_num = int(page_num_str)
        if "extraction" not in page_data or "content_blocks" not in page_data["extraction"]:
            continue

        content_blocks = page_data["extraction"]["content_blocks"]
        i = 0
        while i < len(content_blocks):
            block = content_blocks[i]
            # Proses image/table/flowchart
            if block["type"] in ["image", "table", "flowchart"]:
                context_before, context_after = "", ""
                if i > 0 and content_blocks[i-1]["type"] == "text":
                    context_before = clean_text(content_blocks[i-1]["content"])
                if i < len(content_blocks)-1 and content_blocks[i+1]["type"] == "text":
                    context_after = clean_text(content_blocks[i+1]["content"])

                chunk_content = ""
                if context_before:
                    chunk_content += context_before + "\n\n"

                if block.get("title"):
                    chunk_content += f"Title: {clean_text(block['title'])}\n\n"
                elif block.get("description_image"):
                    chunk_content += f"Description: {clean_text(block['description_image'])}\n\n"

                if block["type"] == "table" and "data" in block:
                    chunk_content += "Table Content:\n"
                    if isinstance(block["data"], list) and block["data"] and isinstance(block["data"][0], dict):
                        columns = sorted(set().union(*[row.keys() for row in block["data"]]))
                        chunk_content += " | ".join(columns) + "\n"
                        chunk_content += "-" * (sum(len(c) for c in columns) + 3 * (len(columns)-1)) + "\n"
                        for row in block["data"]:
                            row_data = [str(row.get(col, "")) for col in columns]
                            chunk_content += " | ".join(row_data) + "\n"
                    if block.get("summary_table"):
                        chunk_content += f"\nTable Summary: {clean_text(block['summary_table'])}\n"

                elif block["type"] == "flowchart":
                    chunk_content += "Flowchart Elements:\n"
                    for element in block.get("elements", []):
                        chunk_content += f"- {element.get('type', 'Element')}: {clean_text(element.get('text', ''))}\n"
                        connects = element.get("connects_to")
                        if isinstance(connects, list):
                            if all(isinstance(item, str) for item in connects):
                                chunk_content += f"  Connects to: {', '.join(connects)}\n"
                            else:
                                for conn in connects:
                                    chunk_content += f"  Connects to: {conn.get('target', '')} ({conn.get('label', '')})\n"
                    if block.get("summary_flowchart"):
                        chunk_content += f"\nFlowchart Summary: {clean_text(block['summary_flowchart'])}\n"

                if context_after:
                    chunk_content += f"\n\n{context_after}"

                chunks.append({
                    "chunk_id": f"chunk_{uuid.uuid4().hex[:8]}",
                    "content": chunk_content,
                    "metadata": {
                        "document": document_metadata["filename"],
                        "page": page_num,
                        "type": block["type"],
                        "block_id": block.get("block_id"),
                        "page_location": f"Page {page_num}"
                    }
                })
                i += 1

            # Proses text biasa
            elif block["type"] == "text":
                current_chunk_text = clean_text(block["content"])
                current_chunk_blocks = [i]
                current_token_count = count_tokens(current_chunk_text)

                j = i + 1
                while j < len(content_blocks) and content_blocks[j]["type"] == "text":
                    next_text = clean_text(content_blocks[j]["content"])
                    next_token_count = count_tokens(next_text)
                    if current_token_count + next_token_count > max_tokens:
                        break
                    current_chunk_text += " " + next_text
                    current_chunk_blocks.append(j)
                    current_token_count += next_token_count
                    j += 1

                chunks.append({
                    "chunk_id": f"chunk_{uuid.uuid4().hex[:8]}",
                    "content": current_chunk_text,
                    "metadata": {
                        "document": document_metadata["filename"],
                        "page": page_num,
                        "type": "text",
                        "block_ids": [content_blocks[idx].get("block_id") for idx in current_chunk_blocks],
                        "page_location": f"Page {page_num}"
                    }
                })
                i = current_chunk_blocks[-1] + 1
            else:
                i += 1
    return chunks

def process_pdf_json(input_path, output_path, max_tokens=MAX_TOKENS, overlap_tokens=OVERLAP_TOKENS):
    try:
        logger.log(f"Memproses file: {input_path}")
        with open(input_path, 'r', encoding='utf-8') as f:
            pdf_data = json.load(f)

        chunks = create_chunks(pdf_data, max_tokens, overlap_tokens)

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

        logger.log(f"✔ Berhasil: {len(chunks)} chunk disimpan ke {output_path}")
    except Exception as e:
        logger.log(f"❌ Gagal memproses {input_path}: {str(e)}", status="ERROR")

def process_directory(input_dir, output_dir, max_tokens=MAX_TOKENS, overlap_tokens=OVERLAP_TOKENS):
    os.makedirs(output_dir, exist_ok=True)
    for filename in os.listdir(input_dir):
        if filename.endswith('.json'):
            input_path = os.path.join(input_dir, filename)
            output_filename = f"chunked_{filename}"
            output_path = os.path.join(output_dir, output_filename)
            process_pdf_json(input_path, output_path, max_tokens, overlap_tokens)

if __name__ == "__main__":
    if os.path.isdir(INPUT_PATH):
        process_directory(INPUT_PATH, OUTPUT_PATH)
    else:
        process_pdf_json(INPUT_PATH, OUTPUT_PATH)
