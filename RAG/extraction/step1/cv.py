import pdfplumber
import pandas as pd
import camelot
import cv2
import numpy as np
from tabulate import tabulate
from PyPDF2 import PdfReader
import os
from pdf2image import convert_from_path
import tempfile

def extract_pdf_with_complex_structure(pdf_path, output_folder="extracted_results"):
    # Buat folder output jika belum ada
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    # Simpan hasil dalam dictionary
    results = {}
    
    # Dapatkan ukuran halaman untuk mengatur area tabel dalam koordinat absolut
    with pdfplumber.open(pdf_path) as pdf:
        page_width = float(pdf.pages[0].width)
        page_height = float(pdf.pages[0].height)
    
    
    # 3. Ekstraksi dengan camelot (stream mode) - FIX: menggunakan koordinat absolut, bukan persentase
    print("\n=== EKSTRAKSI DENGAN CAMELOT (STREAM) ===")
    try:
        # Gunakan koordinat absolut untuk area tabel - seluruh halaman
        table_area = [0, 0, page_width, page_height]
        tables_stream = camelot.read_pdf(pdf_path, pages='all', flavor='stream', 
                                         )
        
        if len(tables_stream) > 0:
            for idx, table in enumerate(tables_stream, 1):
                page_num = table.page
                print(f"Tabel Stream {idx} terdeteksi di halaman {page_num} dengan akurasi {table.accuracy}")
                
                # Filter tabel dengan akurasi rendah atau terlalu sedikit kolom
                if table.accuracy < 50 or table.df.shape[1] < 2:
                    print(f"  - Tabel memiliki akurasi rendah atau terlalu sedikit kolom, mungkin bukan tabel sebenarnya")
                    continue
                
                # Simpan tabel sebagai CSV
                table.to_csv(f"{output_folder}/page_{page_num}_table_stream_{idx}.csv")
                
                # Tambahkan ke hasil jika belum ada
                page_key = f"page_{page_num}"
                if page_key not in results:
                    results[page_key] = {"text": [], "tables": []}
                results[page_key]["tables"].append(table.df)
    except Exception as e:
        print(f"Error dalam ekstraksi camelot stream: {e}")
    
    # 4. Untuk kasus yang kompleks - coba ekstrak dengan camelot stream tanpa area tertentu
    print("\n=== EKSTRAKSI DENGAN CAMELOT (STREAM) TANPA AREA ===")
    try:
        tables_stream_auto = camelot.read_pdf(pdf_path, pages='all', flavor='stream')
        if len(tables_stream_auto) > 0:
            for idx, table in enumerate(tables_stream_auto, 1):
                page_num = table.page
                print(f"Tabel Stream Auto {idx} terdeteksi di halaman {page_num} dengan akurasi {table.accuracy}")
                
                # Filter tabel dengan akurasi rendah
                if table.accuracy < 50:
                    print(f"  - Tabel memiliki akurasi rendah, mungkin bukan tabel sebenarnya")
                    continue
                
                # Simpan tabel sebagai CSV
                table.to_csv(f"{output_folder}/page_{page_num}_table_stream_auto_{idx}.csv")
                
                # Tambahkan ke hasil jika belum ada
                page_key = f"page_{page_num}"
                if page_key not in results:
                    results[page_key] = {"text": [], "tables": []}
                results[page_key]["tables"].append(table.df)
    except Exception as e:
        print(f"Error dalam ekstraksi camelot stream auto: {e}")
    
    # 5. Untuk kasus yang kompleks - Konversi halaman PDF ke gambar dan preprocessing
    problem_pages = identify_problem_pages(results)
    if problem_pages:
        print(f"\nHalaman bermasalah yang ditemukan: {problem_pages}")
        for problem_page in problem_pages:
            print(f"\n=== MENERAPKAN PREPROCESSING UNTUK HALAMAN {problem_page} ===")
            
            # Konversi halaman PDF ke gambar
            try:
                images = convert_from_path(pdf_path, first_page=problem_page, last_page=problem_page)
                
                if images:
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_img:
                        tmp_img_path = tmp_img.name
                        images[0].save(tmp_img_path)
                        
                        # Preprocessing gambar
                        processed_img_path = f"{output_folder}/page_{problem_page}_processed.png"
                        preprocess_image_for_ocr(tmp_img_path, processed_img_path)
                        print(f"Preprocessing berhasil diterapkan untuk halaman {problem_page}")
            except Exception as e:
                print(f"Error dalam preprocessing halaman {problem_page}: {e}")
    
    return results

def identify_problem_pages(results):
    """Identifikasi halaman yang bermasalah (tabel tidak terdeteksi dengan baik)"""
    problem_pages = []
    
    for page_key, page_data in results.items():
        # Ekstrak nomor halaman dari key
        page_num = int(page_key.split('_')[1])
        
        # Jika tidak ada tabel terdeteksi tapi ada teks yang kemungkinan tabel
        if not page_data.get("tables") and page_data.get("text"):
            for text in page_data["text"]:
                # Heuristik sederhana: jika banyak karakter tab atau baris dengan pola tertentu, mungkin tabel
                if text.count('\t') > 5 or len([line for line in text.split('\n') if line.count('  ') > 3]) > 3:
                    problem_pages.append(page_num)
                    break
    
    return problem_pages

def preprocess_image_for_ocr(image_path, output_path):
    """Fungsi preprocessing untuk memperjelas struktur tabel dalam gambar"""
    # Baca gambar
    img = cv2.imread(image_path)
    
    # Konversi ke grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Thresholding adaptif untuk menangani variasi pencahayaan
    binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                  cv2.THRESH_BINARY_INV, 11, 2)
    
    # Deteksi dan perkuat garis horizontal dan vertikal
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (50, 1))
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 50))
    
    horizontal_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)
    vertical_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel, iterations=2)
    
    # Gabung garis horizontal dan vertikal
    table_structure = cv2.addWeighted(horizontal_lines, 0.5, vertical_lines, 0.5, 0.0)
    
    # Dilasi untuk menebalkan garis
    kernel = np.ones((3,3), np.uint8)
    table_structure = cv2.dilate(table_structure, kernel, iterations=1)
    
    # Invers gambar untuk mendapatkan garis hitam pada latar putih
    table_structure = cv2.bitwise_not(table_structure)
    
    # Overlay struktur tabel pada gambar asli
    result = cv2.addWeighted(gray, 0.7, table_structure, 0.3, 0)
    
    # Thresholding akhir untuk memperjelas
    _, result = cv2.threshold(result, 150, 255, cv2.THRESH_BINARY)
    
    # Simpan gambar hasil
    cv2.imwrite(output_path, result)
    print(f"Gambar yang dipreprocess disimpan di: {output_path}")
    
    return output_path

# Contoh penggunaan
pdf_path = "studi_kasus/7_Tabel_N_Halaman_Normal_V2.pdf"
results = extract_pdf_with_complex_structure(pdf_path)