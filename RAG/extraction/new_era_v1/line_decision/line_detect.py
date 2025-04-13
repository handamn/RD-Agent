import fitz  # PyMuPDF
import cv2
import numpy as np
import json
from pathlib import Path

def detect_horizontal_lines(image):
    """Mendeteksi garis horizontal menggunakan OpenCV."""
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    
    # Kernel horizontal
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
    detected_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel, iterations=1)
    
    contours, _ = cv2.findContours(detected_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    return len(contours) > 0

def process_pdf(pdf_path, output_json='hasil_deteksi.json'):
    doc = fitz.open(pdf_path)
    hasil = {}

    for i, page in enumerate(doc, start=1):
        pix = page.get_pixmap(dpi=150)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)

        if pix.n == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
        else:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        if detect_horizontal_lines(img):
            hasil[str(i)] = "ada garis"
        else:
            hasil[str(i)] = "tidak"

    with open(output_json, 'w') as f:
        json.dump(hasil, f, indent=4)
    
    print(f"Hasil disimpan di {output_json}")

# Contoh penggunaan
if __name__ == "__main__":
    pdf_file = "ABF Indonesia Bond Index Fund.pdf"  # Ganti dengan path ke PDF kamu
    process_pdf(pdf_file)
