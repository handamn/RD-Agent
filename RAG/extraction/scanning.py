import fitz  # PyMuPDF
import pdfplumber
from PIL import Image
import pytesseract
import json

def extract_text_from_image(image):
    """Menggunakan Tesseract OCR untuk mengekstrak teks dari gambar."""
    return pytesseract.image_to_string(image)

def process_pdf(pdf_path):
    # Buka PDF dengan PyMuPDF
    pdf_document = fitz.open(pdf_path)
    
    # Buka PDF dengan pdfplumber untuk deteksi tabel
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, (fitz_page, plumber_page) in enumerate(zip(pdf_document, pdf.pages)):
            print(f"Processing Page {page_num + 1}")
            
            # Metadata halaman
            metadata = {
                "page_number": page_num + 1,
                "content_type": [],
                "layout": None,
                "tables": [],
                "requires_ocr": False
            }
            
            # Deteksi gambar hasil scan
            image_list = fitz_page.get_images(full=True)
            if image_list:
                metadata["content_type"].append("image")
                metadata["requires_ocr"] = True
                print(f"Page {page_num + 1} contains scanned images.")
                
                # Ekstrak teks dari gambar menggunakan OCR
                for img_index, img in enumerate(image_list):
                    xref = img[0]
                    base_image = pdf_document.extract_image(xref)
                    image = Image.open(io.BytesIO(base_image["image"]))
                    extracted_text = extract_text_from_image(image)
                    print(f"Extracted text from image {img_index + 1}:\n{extracted_text}")
            
            # Deteksi tabel menggunakan pdfplumber
            tables = plumber_page.extract_tables()
            if tables:
                metadata["content_type"].append("table")
                metadata["tables"] = tables
                print(f"Page {page_num + 1} contains {len(tables)} tables.")
            
            # Deteksi teks biasa
            text = plumber_page.extract_text()
            if text:
                metadata["content_type"].append("text")
                print(f"Page {page_num + 1} contains plain text.")
            
            # Simpan metadata atau lakukan proses lebih lanjut
            print(json.dumps(metadata, indent=4, ensure_ascii=False))
            print("-" * 40)

if __name__ == "__main__":
    pdf_path = "studi_kasus/4_Tabel_Satu_Halaman_Normal_V1.pdf"
    process_pdf(pdf_path)