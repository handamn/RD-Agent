import os
import json
import PyPDF2
import pytesseract
from PIL import Image
import fitz  # PyMuPDF
import cv2
import numpy as np
from io import BytesIO

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
    hasil_gabungan = {}

    with open(pdf_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        doc = fitz.open(pdf_path)
        total_pages = len(pdf_reader.pages)

        for i in range(total_pages):
            page_index = i + 1
            pdf_page = pdf_reader.pages[i]
            text = pdf_page.extract_text()

            # render image sekali saja pakai PyMuPDF
            page = doc[i]
            pix = page.get_pixmap(dpi=200)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            if pix.n == 4:
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
            else:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            # OCR
            if text and len(text.strip()) >= min_text_length:
                ocr_status = False
            else:
                pil_img = Image.fromarray(img)
                text_from_ocr = pytesseract.image_to_string(pil_img)
                if text_from_ocr and len(text_from_ocr.strip()) >= min_text_length:
                    ocr_status = True
                else:
                    ocr_status = "halaman kosong/gambar saja"

            # Line detection
            line_status = detect_horizontal_lines(img, min_line_count, min_line_length_percent)

            # Decision logic
            if isinstance(ocr_status, bool):
                ai_status = (ocr_status and line_status) or (not ocr_status and line_status)
            else:
                ai_status = False  # Default jika OCR gagal atau hasil ambigu

            hasil_gabungan[str(page_index)] = {
                "ocr_status": ocr_status,
                "line_status": line_status,
                "ai_status": ai_status
            }

            print(f"Halaman {page_index} diproses: OCR={ocr_status}, LINE={line_status}, AI={ai_status}")


    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(hasil_gabungan, f, indent=4, ensure_ascii=False)

    print(f"Hasil gabungan disimpan di {output_file}")

# Contoh penggunaan
if __name__ == "__main__":
    pdf_path = "ABF Indonesia Bond Index Fund.pdf"  # Ganti sesuai path file
    analyze_pdf(pdf_path, min_text_length=50, min_line_count=3, min_line_length_percent=10)
