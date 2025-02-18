import pytesseract
from pdf2image import convert_from_path
import cv2
import numpy as np
import pandas as pd
import os
import re

def extract_tables_with_ocr(pdf_path, output_folder="ocr_results"):
    # Buat folder output jika belum ada
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    # Konversi PDF ke gambar
    print("Mengkonversi PDF ke gambar...")
    images = convert_from_path(pdf_path, 300)  # Resolusi 300 DPI untuk OCR
    
    all_tables = []
    
    for page_num, image in enumerate(images, 1):
        print(f"\nMemproses halaman {page_num}...")
        
        # Simpan gambar sementara
        image_path = f"{output_folder}/page_{page_num}.png"
        image.save(image_path)
        
        # Preprocess gambar untuk memperjelas struktur
        processed_image_path = preprocess_for_table_detection(image_path, f"{output_folder}/processed_page_{page_num}.png")
        
        # Deteksi area tabel dalam gambar
        table_regions = detect_table_regions(processed_image_path)
        
        if table_regions:
            print(f"Terdeteksi {len(table_regions)} area tabel dalam halaman {page_num}")
            
            # Proses setiap area tabel
            for idx, region in enumerate(table_regions, 1):
                # Potong area tabel dari gambar asli
                table_img = extract_table_region(image_path, region, f"{output_folder}/table_{page_num}_{idx}.png")
                
                # Baca teks dengan OCR
                ocr_text = pytesseract.image_to_string(table_img)
                
                # Konversi hasil OCR ke struktur tabel
                table_data = parse_ocr_to_table(ocr_text)
                
                if table_data:
                    # Konversi ke DataFrame
                    df = pd.DataFrame(table_data)
                    
                    # Simpan hasil
                    output_path = f"{output_folder}/table_{page_num}_{idx}.csv"
                    df.to_csv(output_path, index=False)
                    all_tables.append(df)
                    print(f"Tabel {idx} dari halaman {page_num} disimpan ke {output_path}")
        else:
            print(f"Tidak terdeteksi tabel dalam halaman {page_num}")
    
    return all_tables

def preprocess_for_table_detection(image_path, output_path):
    # Baca gambar
    img = cv2.imread(image_path)
    
    # Konversi ke grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Thresholding adaptif
    binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                  cv2.THRESH_BINARY_INV, 11, 2)
    
    # Deteksi dan perkuat garis
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (50, 1))
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 50))
    
    horizontal_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)
    vertical_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel, iterations=2)
    
    # Gabung garis horizontal dan vertikal
    table_structure = cv2.addWeighted(horizontal_lines, 0.5, vertical_lines, 0.5, 0.0)
    
    # Dilasi untuk menebalkan garis
    kernel = np.ones((3,3), np.uint8)
    table_structure = cv2.dilate(table_structure, kernel, iterations=1)
    
    # Simpan gambar hasil
    cv2.imwrite(output_path, table_structure)
    
    return output_path

def detect_table_regions(processed_image_path):
    # Baca gambar hasil preprocessing
    img = cv2.imread(processed_image_path, 0)  # 0 untuk grayscale
    
    # Temukan kontur
    contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Filter kontur berdasarkan ukuran (hanya ambil yang cukup besar = tabel)
    table_regions = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if w > 100 and h > 100:  # Filter ukuran minimal
            table_regions.append((x, y, w, h))
    
    return table_regions

def extract_table_region(original_image_path, region, output_path):
    # Baca gambar asli
    img = cv2.imread(original_image_path)
    
    # Ekstrak region
    x, y, w, h = region
    table_img = img[y:y+h, x:x+w]
    
    # Simpan region
    cv2.imwrite(output_path, table_img)
    
    return table_img

def parse_ocr_to_table(ocr_text):
    if not ocr_text.strip():
        return None
    
    # Split berdasarkan baris baru
    lines = ocr_text.split('\n')
    lines = [line.strip() for line in lines if line.strip()]
    
    if not lines:
        return None
    
    # Coba deteksi pemisah kolom (misalnya spasi berlebih atau tab)
    table_data = []
    for line in lines:
        # Split berdasarkan dua atau lebih spasi berturut-turut
        row = re.split(r'\s{2,}', line)
        table_data.append(row)
    
    return table_data

# Contoh penggunaan
pdf_path = "studi_kasus/4_Tabel_Satu_Halaman_Normal_V1.pdf"
tables = extract_tables_with_ocr(pdf_path)