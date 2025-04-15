import os
import json
import time
import datetime
import fitz  # PyMuPDF
import PIL.Image
import google.generativeai as genai
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)

# Gunakan model yang disarankan
model = genai.GenerativeModel("gemini-2.0-flash")

TEMP_DIR = "temporary_dir"
LOG_FILE = "multimodal_log.txt"

PROMPT = (
    "Saya ingin Anda mengekstrak semua informasi dari gambar halaman dokumen ini. "
    "Informasi mencakup teks, tabel, grafik, diagram alur, dan gambar.\n"
    "Tolong kembalikan hasil ekstraksi dalam format JSON dengan struktur:\n"
    "{\n"
    "  \"content_blocks\": [\n"
    "    {\n"
    "      \"block_id\": int,\n"
    "      \"type\": \"text\" | \"table\" | \"chart\" | \"flowchart\" | \"image\",\n"
    "      \"content\": \"...\",\n"
    "      \"title\": \"...\",\n"
    "      \"data\": {...}\n"
    "    }\n"
    "  ]\n"
    "}\n"
    "Jika suatu elemen tidak ditemukan di halaman, tidak perlu dimasukkan. Pastikan JSON valid dan bisa di-parse langsung."
)

def render_page_to_image(pdf_path, page_num, output_path, dpi=300):
    doc = fitz.open(pdf_path)
    page = doc[page_num - 1]  # 1-based to 0-based
    pix = page.get_pixmap(dpi=dpi)
    pix.save(output_path)
    return output_path

def extract_with_multimodal_method(image_path):
    image = PIL.Image.open(image_path)
    response = model.generate_content([PROMPT, image])
    try:
        content = response.text
        return json.loads(content)
    except Exception as e:
        print(f"[WARNING] Gagal parse JSON dari hasil Gemini: {e}")
        return {"content_blocks": [{"block_id": 1, "type": "text", "content": content.strip()}]}

def process_pdf_pages(pdf_path, analysis_json_path, output_json_path):
    with open(analysis_json_path, 'r', encoding='utf-8') as f:
        analysis_data = json.load(f)

    if os.path.exists(output_json_path):
        with open(output_json_path, 'r', encoding='utf-8') as f:
            output_data = json.load(f)
    else:
        from PyPDF2 import PdfReader
        total_pages = len(PdfReader(pdf_path).pages)
        output_data = {
            "metadata": {
                "filename": Path(pdf_path).name,
                "total_pages": total_pages,
                "extraction_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "processing_time": "0 seconds"
            },
            "pages": {page_num: {"analysis": val} for page_num, val in analysis_data.items()}
        }

    start_time = time.time()
    os.makedirs(TEMP_DIR, exist_ok=True)
    processed_count = 0
    log_lines = []

    for page_num, page_data in analysis_data.items():
        ocr = page_data.get("ocr_status", False)
        line = page_data.get("line_status", False)
        ai = page_data.get("ai_status", False)

        if (ocr and line and ai) or (not ocr and line and ai):
            if page_num in output_data["pages"] and \
               "extraction" in output_data["pages"][page_num] and \
               output_data["pages"][page_num]["extraction"].get("method") == "multimodal_llm":
                print(f"[SKIP] Page {page_num} sudah diproses.")
                continue

            print(f"[PROCESS] Page {page_num} dengan multimodal...")
            page_start = time.time()

            try:
                image_file = os.path.join(TEMP_DIR, f"image_page_{page_num}.png")
                render_page_to_image(pdf_path, int(page_num), image_file)
                content_blocks = extract_with_multimodal_method(image_file)

                page_result = {
                    "analysis": page_data,
                    "extraction": {
                        "method": "multimodal_llm",
                        "processing_time": f"{time.time() - page_start:.2f} seconds",
                        "content_blocks": content_blocks.get("content_blocks", [])
                    }
                }

                output_data["pages"][page_num] = page_result
                processed_count += 1
                log_lines.append(f"[SUCCESS] Page {page_num} processed.")

            except Exception as e:
                log_lines.append(f"[ERROR] Page {page_num} gagal diproses: {e}")
                print(f"[ERROR] {e}")

    output_data["metadata"]["processing_time"] = f"{time.time() - start_time:.2f} seconds"

    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=4, ensure_ascii=False)

    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        f.write("\n".join(log_lines))

    print(f"[DONE] Multimodal extraction selesai. {processed_count} halaman diproses.")
    return output_data

if __name__ == "__main__":
    pdf_path = "ABF Indonesia Bond Index Fund.pdf"
    analysis_json_path = "sample.json"
    output_json_path = "hasil_ekstraksi.json"
    process_pdf_pages(pdf_path, analysis_json_path, output_json_path)
