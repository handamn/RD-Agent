import json
import fitz  # PyMuPDF
import pdfplumber
from PIL import Image
import pytesseract
import io

def extract_text_from_image(image):
    """Menggunakan Tesseract OCR untuk mengekstrak teks dari gambar."""
    return pytesseract.image_to_string(image)

def process_pdf(pdf_path):
    pdf_document = fitz.open(pdf_path)

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, (fitz_page, plumber_page) in enumerate(zip(pdf_document, pdf.pages)):
            print(f"Processing Page {page_num + 1}")
            
            metadata = {
                "page_number": page_num + 1,
                "content_type": [],
                "layout": None,
                "tables": [],
                "requires_ocr": False
            }
            
            # 1. Deteksi tabel
            tables = plumber_page.extract_tables()
            if tables:
                metadata["content_type"].append("table")
                metadata["tables"] = tables
                print(f"Page {page_num + 1} contains {len(tables)} tables.")

            # 2. Deteksi teks biasa (tanpa tabel yang sudah diekstrak)
            text = plumber_page.extract_text()
            if text:
                metadata["content_type"].append("text")

                # Hapus bagian teks yang mungkin sudah masuk ke tabel
                cleaned_text = text
                for table in tables:
                    for row in table:
                        for cell in row:
                            if cell:
                                cleaned_text = cleaned_text.replace(cell, "")

                metadata["plain_text"] = cleaned_text.strip()  # Hapus spasi ekstra
                print(f"Page {page_num + 1} contains plain text.")

            # 3. Deteksi gambar (scanned pages)
            image_list = fitz_page.get_images(full=True)
            if image_list:
                metadata["content_type"].append("image")
                metadata["requires_ocr"] = True
                print(f"Page {page_num + 1} contains scanned images.")

                extracted_texts = []
                for img_index, img in enumerate(image_list):
                    xref = img[0]
                    base_image = pdf_document.extract_image(xref)
                    image = Image.open(io.BytesIO(base_image["image"]))
                    extracted_text = extract_text_from_image(image)
                    extracted_texts.append(extracted_text)
                    print(f"Extracted text from image {img_index + 1}:\n{extracted_text}")
                
                if extracted_texts:
                    metadata["ocr_text"] = extracted_texts

            # Cetak metadata dalam format JSON
            print(json.dumps(metadata, indent=4, ensure_ascii=False))
            print("-" * 40)

if __name__ == "__main__":
    pdf_path = "studi_kasus/4_Tabel_Satu_Halaman_Normal_V1.pdf"
    process_pdf(pdf_path)