# Perhatian: Kode ini memerlukan instalasi library tambahan!
# pip install pdf2image opencv-python pandas tabledetect

import os
import tempfile
from pdf2image import convert_from_path
import cv2
import numpy as np
import pandas as pd
from tabledetect import TableDetect

def extract_tables_with_dl(pdf_path, output_folder="dl_results"):
    # Buat folder output jika belum ada
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    # Inisialisasi model deteksi tabel
    model = TableDetect()
    
    # Konversi PDF ke gambar
    print("Mengkonversi PDF ke gambar...")
    images = convert_from_path(pdf_path, 300)  # Resolusi 300 DPI
    
    all_tables = []
    
    for page_num, image in enumerate(images, 1):
        print(f"\nMemproses halaman {page_num}...")
        
        # Simpan gambar sementara
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_img:
            image_path = tmp_img.name
            image.save(image_path)
        
        # Deteksi tabel dengan model DL
        detections = model.detect(image_path)
        
        if detections:
            print(f"Terdeteksi {len(detections)} tabel dalam halaman {page_num}")
            
            # Proses setiap area tabel terdeteksi
            for idx, detection in enumerate(detections, 1):
                # Potong area tabel dari gambar
                table_img_path = f"{output_folder}/table_{page_num}_{idx}.png"
                table_img = extract_table_region(image_path, detection, table_img_path)
                
                # Ekstrak struktur dan isi tabel
                extracted_df = model.extract_table(table_img_path)
                
                if not extracted_df.empty:
                    # Simpan hasil ekstraksi
                    output_path = f"{output_folder}/table_{page_num}_{idx}.csv"
                    extracted_df.to_csv(output_path, index=False)
                    all_tables.append(extracted_df)
                    print(f"Tabel {idx} dari halaman {page_num} disimpan ke {output_path}")
        else:
            print(f"Tidak terdeteksi tabel dalam halaman {page_num}")
    
    # Bersihkan file sementara
    if os.path.exists(image_path):
        os.remove(image_path)
    
    return all_tables

def extract_table_region(image_path, detection, output_path):
    # Baca gambar
    img = cv2.imread(image_path)
    
    # Dapatkan koordinat bounding box
    x, y, w, h = detection.bbox
    
    # Ekstrak region (tambah margin 5 piksel)
    margin = 5
    y1 = max(0, y - margin)
    y2 = min(img.shape[0], y + h + margin)
    x1 = max(0, x - margin)
    x2 = min(img.shape[1], x + w + margin)
    
    table_img = img[y1:y2, x1:x2]
    
    # Simpan region
    cv2.imwrite(output_path, table_img)
    
    return table_img

# Contoh penggunaan (perhatikan: TableDetect adalah library fiktif untuk ilustrasi)
pdf_path = "studi_kasus/4_Tabel_Satu_Halaman_Normal_V1.pdf"
tables = extract_tables_with_dl(pdf_path)