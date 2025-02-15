import os
from unstructured.partition.pdf import partition_pdf
from pdf2image import convert_from_path
import pytesseract

def extract_text_from_pdf(pdf_path):
    # Ekstrak teks menggunakan unstructured
    elements = partition_pdf(filename=pdf_path)
    extracted_text = "\n".join([str(el) for el in elements])
    
    # Jika hasil ekstraksi kosong, coba OCR
    if not extracted_text.strip():
        print("No text found, performing OCR...")
        images = convert_from_path(pdf_path)
        ocr_text = "\n".join([pytesseract.image_to_string(img) for img in images])
        return ocr_text
    
    return extracted_text

if __name__ == "__main__":
    pdf_file = "ABF Indonesia Bond Index Fund.pdf"  # Ganti dengan path file PDF Anda
    if not os.path.exists(pdf_file):
        print("File PDF tidak ditemukan.")
    else:
        text = extract_text_from_pdf(pdf_file)
        print("Extracted Text:\n", text)
