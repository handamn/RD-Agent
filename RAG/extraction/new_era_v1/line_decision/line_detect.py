import fitz  # PyMuPDF
import cv2
import numpy as np
import json
from pathlib import Path

def detect_horizontal_lines(image, min_line_count=1, min_line_length_percent=20):
    """
    Mendeteksi garis horizontal berdasarkan jumlah minimum dan panjang (dalam persen dari lebar halaman).
    
    Args:
        image: Gambar halaman PDF.
        min_line_count: Minimum jumlah garis yang dianggap sah.
        min_line_length_percent: Panjang minimum garis dalam persen dari lebar halaman.
    
    Returns:
        True jika memenuhi syarat, False jika tidak.
    """
    height, width = image.shape[:2]
    min_line_length = int((min_line_length_percent / 100.0) * width)

    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

    # Kernel horizontal
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
    detected_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel, iterations=1)

    contours, _ = cv2.findContours(detected_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    panjang_valid = [
        cv2.boundingRect(cnt)[2]
        for cnt in contours
        if cv2.boundingRect(cnt)[2] >= min_line_length
    ]

    return len(panjang_valid) >= min_line_count

def process_pdf(pdf_path, output_json='hasil_deteksi.json', min_line_count=1, min_line_length_percent=20):
    """Proses seluruh halaman PDF dan deteksi garis horizontal per halaman."""
    doc = fitz.open(pdf_path)
    hasil = {}

    for i, page in enumerate(doc, start=1):
        pix = page.get_pixmap(dpi=150)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)

        if pix.n == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
        else:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        if detect_horizontal_lines(img, min_line_count=min_line_count, min_line_length_percent=min_line_length_percent):
            hasil[str(i)] = "ada garis"
        else:
            hasil[str(i)] = "tidak"

    with open(output_json, 'w') as f:
        json.dump(hasil, f, indent=4)
    
    print(f"Hasil disimpan di {output_json}")

# Contoh penggunaan
if __name__ == "__main__":
    pdf_file = "ABF Indonesia Bond Index Fund.pdf"  # Ganti path sesuai file PDF kamu
    process_pdf(pdf_file, min_line_count=3, min_line_length_percent=10)  # 50% dari lebar halaman
