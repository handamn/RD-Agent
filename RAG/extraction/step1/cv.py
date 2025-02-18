import pdfplumber
import pandas as pd
import camelot
import cv2
import numpy as np
from tabulate import tabulate
from PIL import Image

def extract_pdf_content_improved(pdf_path):
    # Metode 1: Menggunakan pdfplumber (untuk tabel dengan border lengkap)
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            print(f"\n=== HALAMAN {page_num} ===")
            
            # Ekstraksi teks
            text = page.extract_text()
            if text:
                print("\n--- TEXT (pdfplumber) ---\n")
                print(text)
            
            # Ekstraksi tabel menggunakan pdfplumber
            tables = page.extract_tables()
            if tables:
                print("\n--- TABLE (pdfplumber) ---\n")
                for idx, table in enumerate(tables, 1):
                    df = pd.DataFrame(table)
                    if not df.empty:
                        print(f"Tabel {idx}:")
                        print(tabulate(df, headers='keys', tablefmt='grid', showindex=False))
            
    # Metode 2: Menggunakan camelot (lebih baik untuk tabel tanpa border lengkap)
    print("\n\n=== EKSTRAKSI DENGAN CAMELOT ===\n")
    
    # Mode 'lattice' untuk tabel dengan border
    tables_lattice = camelot.read_pdf(pdf_path, pages='all', flavor='lattice')
    if len(tables_lattice) > 0:
        print("\n--- TABLES (camelot-lattice) ---\n")
        for idx, table in enumerate(tables_lattice, 1):
            print(f"Tabel Lattice {idx} (Halaman {table.page}):")
            print(tabulate(table.df, tablefmt='grid', showindex=False))
            print(f"Accuracy: {table.accuracy}")
    
    # Mode 'stream' untuk tabel tanpa border atau hanya border horizontal
    tables_stream = camelot.read_pdf(pdf_path, pages='all', flavor='stream')
    if len(tables_stream) > 0:
        print("\n--- TABLES (camelot-stream) ---\n")
        for idx, table in enumerate(tables_stream, 1):
            print(f"Tabel Stream {idx} (Halaman {table.page}):")
            print(tabulate(table.df, tablefmt='grid', showindex=False))
            print(f"Accuracy: {table.accuracy}")
            
def preprocess_image_for_ocr(image_path, output_path):
    # Baca gambar
    img = cv2.imread(image_path)
    
    # Ubah ke grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Threshold untuk memperjelas garis
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
    
    # Deteksi garis
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 1))
    detected_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)
    
    # Perbaiki garis
    cnts = cv2.findContours(detected_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = cnts[0] if len(cnts) == 2 else cnts[1]
    for c in cnts:
        cv2.drawContours(img, [c], -1, (0, 0, 0), 2)
    
    # Simpan gambar hasil preprocessing
    cv2.imwrite(output_path, img)
    
    return output_path

# Path ke file PDF yang diunggah
pdf_path = "studi_kasus/5_Tabel_Satu_Halaman_Merge_V2.pdf"

# Jalankan ekstraksi dengan metode yang lebih baik
extract_pdf_content_improved(pdf_path)

# Jika ingin menambahkan preprocessing image (opsional)
# Pertama konversi PDF ke gambar menggunakan pdf2image, lalu:
# preprocessed_image = preprocess_image_for_ocr("input_image.png", "preprocessed_image.png")
# Setelah itu gunakan preprocessed_image dengan Tesseract OCR