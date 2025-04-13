import os
import json
import PyPDF2
from pdf2image import convert_from_path
import pytesseract
from PIL import Image
import fitz  # PyMuPDF
import cv2
import numpy as np

def check_page_needs_ocr(pdf_path, min_text_length=50, dpi=200):
    results = {}
    with open(pdf_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        total_pages = len(pdf_reader.pages)
        images = convert_from_path(pdf_path, dpi=dpi)
        
        for page_num in range(total_pages):
            page = pdf_reader.pages[page_num]
            text = page.extract_text()

            if text and len(text.strip()) >= min_text_length:
                results[page_num + 1] = "cukup scan biasa"
            else:
                if page_num < len(images):
                    text_from_ocr = pytesseract.image_to_string(images[page_num])
                    if text_from_ocr and len(text_from_ocr.strip()) >= min_text_length:
                        results[page_num + 1] = "perlu ocr"
                    else:
                        results[page_num + 1] = "halaman kosong/gambar saja"
                else:
                    results[page_num + 1] = "gagal diproses"
    return results

def detect_horizontal_lines(image, min_line_count=1, min_line_length_percent=20):
    height, width = image.shape[:2]
    min_line_length = int((min_line_length_percent / 100.0) * width)

    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
    detected_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel, iterations=1)

    contours, _ = cv2.findContours(detected_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    panjang_valid = [
        cv2.boundingRect(cnt)[2]
        for cnt in contours
        if cv2.boundingRect(cnt)[2] >= min_line_length
    ]
    return len(panjang_valid) >= min_line_count

def analyze_pdf(pdf_path, output_file="hasil_gabungan.json", min_text_length=50, min_line_count=1, min_line_length_percent=20):
    ocr_results = check_page_needs_ocr(pdf_path, min_text_length)
    garis_results = {}

    doc = fitz.open(pdf_path)
    for i, page in enumerate(doc, start=1):
        pix = page.get_pixmap(dpi=150)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if pix.n == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
        else:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        garis_results[i] = "ada garis" if detect_horizontal_lines(img, min_line_count, min_line_length_percent) else "tidak"

    # Gabungkan hasil
    hasil_gabungan = {}
    all_pages = set(ocr_results.keys()).union(set(garis_results.keys()))
    for page in sorted(all_pages):
        hasil_gabungan[str(page)] = {
            "ocr_status": ocr_results.get(page, "tidak diketahui"),
            "garis_status": garis_results.get(page, "tidak diketahui")
        }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(hasil_gabungan, f, indent=4, ensure_ascii=False)

    print(f"Hasil gabungan disimpan di {output_file}")

# Contoh penggunaan
if __name__ == "__main__":
    pdf_path = "ABF Indonesia Bond Index Fund.pdf"  # Ganti sesuai path file
    analyze_pdf(pdf_path, min_text_length=50, min_line_count=3, min_line_length_percent=10)
