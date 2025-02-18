import pdfplumber
import pytesseract
from pdf2image import convert_from_path
from unstructured.partition.pdf import partition_pdf
import json
import os

def detect_page_content(pdf_path):
    metadata = []

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            page_info = {"page": i + 1, "content_blocks": [], "requires_OCR": False}

            # 1️⃣ Coba ekstraksi teks biasa
            text = page.extract_text()
            if text and text.strip():
                page_info["content_blocks"].append({"type": "text", "position": "full"})
            
            # 2️⃣ Coba deteksi tabel
            tables = page.extract_tables()
            if tables and any(len(row) > 1 for table in tables for row in table):
                page_info["content_blocks"].append({"type": "table", "position": "full", "format": "normal"})
            
            # 3️⃣ Coba gunakan unstructured untuk deteksi tambahan
            elements = partition_pdf(filename=pdf_path, strategy="fast")
            for el in elements:
                if "Table" in str(el):
                    page_info["content_blocks"].append({"type": "table", "position": "unknown", "format": "unknown"})

            # 4️⃣ Jika tidak ada teks yang bisa diekstrak, tandai untuk OCR
            if not text.strip() and not tables:
                page_info["requires_OCR"] = True
                
                # Konversi halaman ke gambar dan jalankan OCR
                images = convert_from_path(pdf_path, first_page=i+1, last_page=i+1)
                ocr_text = pytesseract.image_to_string(images[0])
                
                if ocr_text.strip():
                    page_info["content_blocks"].append({"type": "ocr_text", "position": "full"})
                else:
                    page_info["content_blocks"].append({"type": "ocr_table", "position": "full"})

            metadata.append(page_info)

    return metadata

if __name__ == "__main__":
    
    file_name = "7_Tabel_N_Halaman_Normal_V1"

    pdf_path = f"E:/belajar-RAG/RD-Agent/RAG/extraction/studi_kasus/{file_name}.pdf"  # Ganti dengan file PDF yang ingin diproses
    if not os.path.exists(pdf_path):
        print("File PDF tidak ditemukan.")
    else:
        metadata = detect_page_content(pdf_path)
        
        # Simpan metadata sebagai JSON untuk dipakai di Step 2
        with open("metadata.json", "w") as json_file:
            json.dump(metadata, json_file, indent=4)

        print("Metadata hasil scanning:")
        print(json.dumps(metadata, indent=4))
