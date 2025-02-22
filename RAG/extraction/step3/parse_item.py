import fitz  # PyMuPDF
import cv2
import numpy as np
from pdf2image import convert_from_path
import pytesseract

# Fungsi untuk mendeteksi dan mengekstrak teks dari PDF
def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    extracted_text = ""
    
    for page in doc:
        extracted_text += page.get_text("text") + "\n"
    
    print("Extracted Text:")
    print(extracted_text)

# Fungsi untuk mendeteksi tabel dalam PDF dan mengambil screenshot tabel
def detect_and_screenshot_tables(pdf_path):
    doc = fitz.open(pdf_path)
    table_images = []
    
    for page_num in range(len(doc)):
        text_blocks = doc[page_num].get_text("blocks")
        table_detected = any("|" in block[4] or "─" in block[4] for block in text_blocks)
        
        if table_detected:
            images = convert_from_path(pdf_path, first_page=page_num+1, last_page=page_num+1)
            img_array = np.array(images[0])
            table_images.append(img_array)
            print(f"Table detected on page {page_num+1}: Screenshot taken")
    
    return table_images

# Fungsi untuk melakukan OCR dan membedakan antara teks biasa dan tabel
def ocr_text_and_tables_from_pdf(pdf_path):
    images = convert_from_path(pdf_path)
    
    for page_num, img in enumerate(images):
        extracted_text = pytesseract.image_to_string(img)
        table_text = pytesseract.image_to_string(img, config="--psm 6")
        
        if "|" in extracted_text or "─" in extracted_text:
            print(f"OCR Table on page {page_num+1}:")
            print(table_text)
        else:
            print(f"OCR Text on page {page_num+1}:")
            print(extracted_text)

# Main program
pdf_path = "studi_kasus/4_Tabel_Satu_Halaman_Normal_V1.pdf"
extract_text_from_pdf(pdf_path)
detect_and_screenshot_tables(pdf_path)
ocr_text_and_tables_from_pdf(pdf_path)
