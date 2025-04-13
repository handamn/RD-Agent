import os
import json
import PyPDF2
from pdf2image import convert_from_path
import pytesseract
import cv2
import numpy as np
from PIL import Image

def detect_table_in_image(image, min_vertical_lines=3, min_horizontal_lines=3, min_intersections=4):
    """
    Mendeteksi tabel dengan kriteria ketat:
    - Harus ada minimal beberapa garis vertikal DAN horizontal
    - Harus ada cukup banyak persimpangan garis
    - Garis harus membentuk pola grid
    """
    try:
        # Konversi ke grayscale
        gray = cv2.cvtColor(np.array(image), cv2.COLOR_BGR2GRAY)
        
        # Thresholding untuk mendapatkan edges
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
        
        # Deteksi garis vertikal
        vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 50))
        vertical_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, vertical_kernel, iterations=2)
        
        # Deteksi garis horizontal
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (50, 1))
        horizontal_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)
        
        # Hitung jumlah garis
        v_lines = cv2.countNonZero(vertical_lines)
        h_lines = cv2.countNonZero(horizontal_lines)
        
        # Jika tidak memenuhi minimal garis, bukan tabel
        if v_lines < min_vertical_lines or h_lines < min_horizontal_lines:
            return False
            
        # Gabungkan garis untuk deteksi persimpangan
        table_mask = cv2.add(vertical_lines, horizontal_lines)
        
        # Temukan contours untuk analisis lebih lanjut
        contours, _ = cv2.findContours(table_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filter berdasarkan area dan aspect ratio
        table_contours = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            aspect_ratio = w / float(h)
            area = cv2.contourArea(cnt)
            
            # Filter bentuk yang terlalu memanjang (garis tunggal)
            if 0.2 < aspect_ratio < 5 and area > 100:
                table_contours.append(cnt)
        
        # Jika menemukan cukup banyak contours yang memenuhi syarat
        if len(table_contours) >= min_intersections:
            return True
            
        return False
        
    except Exception as e:
        print(f"Error in table detection: {str(e)}")
        return False

def detect_table_from_text(text):
    """Deteksi tabel dari pola teks (baris dengan banyak tab/space)"""
    lines = [line for line in text.split('\n') if line.strip()]
    if len(lines) < 2:  # Minimal 2 baris untuk dianggap tabel
        return False
    
    # Hitung jumlah kolom berdasarkan split whitespace
    col_counts = []
    for line in lines:
        cols = [c for c in line.split() if c.strip()]
        col_counts.append(len(cols))
    
    # Jika minimal 3 kolom dan konsisten
    if max(col_counts) >= 3 and len(set(col_counts)) <= 2:
        return True
    return False

def check_page_needs_ocr(pdf_path, min_text_length=50, dpi=200):
    """
    Fungsi utama untuk memeriksa halaman PDF dengan prioritas:
    1. Terindikasi ada tabel
    2. Perlu OCR
    3. Cukup scan biasa
    """
    results = {}
    
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            total_pages = len(pdf_reader.pages)
            
            print(f"Menganalisis PDF dengan {total_pages} halaman...")
            
            # Konversi semua halaman ke gambar untuk deteksi tabel
            images = convert_from_path(pdf_path, dpi=dpi)
            
            for page_num in range(total_pages):
                page = pdf_reader.pages[page_num]
                text = page.extract_text() or ""
                
                # Cek tabel dari gambar (jika ada gambar)
                table_in_image = False
                if page_num < len(images):
                    table_in_image = detect_table_in_image(images[page_num])
                
                # Cek tabel dari teks (jika ada teks)
                table_in_text = detect_table_from_text(text)
                
                # Prioritas: tabel > ocr > normal
                if table_in_image or table_in_text:
                    results[page_num + 1] = "terindikasi ada tabel"
                elif text and len(text.strip()) >= min_text_length:
                    results[page_num + 1] = "cukup scan biasa"
                else:
                    # Gunakan OCR jika diperlukan
                    if page_num < len(images):
                        text_from_ocr = pytesseract.image_to_string(images[page_num])
                        
                        # Cek lagi tabel dari hasil OCR
                        if detect_table_from_text(text_from_ocr):
                            results[page_num + 1] = "terindikasi ada tabel"
                        elif text_from_ocr and len(text_from_ocr.strip()) >= min_text_length:
                            results[page_num + 1] = "perlu ocr"
                        else:
                            results[page_num + 1] = "cukup scan biasa"
                    else:
                        results[page_num + 1] = "cukup scan biasa"
    
    except Exception as e:
        print(f"Error processing PDF: {str(e)}")
        return {}
    
    return results

def main():
    pdf_path = "ABF Indonesia Bond Index Fund.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"File {pdf_path} tidak ditemukan!")
        return
    
    # Mendapatkan hasil analisis
    analysis_results = check_page_needs_ocr(pdf_path)
    
    if not analysis_results:
        print("Gagal menganalisis PDF.")
        return
    
    # Simpan hasil sebagai JSON
    output_file = os.path.splitext(pdf_path)[0] + "_enhanced_analysis.json"
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(analysis_results, f, indent=4, ensure_ascii=False)
        
        print("\nHasil analisis:")
        for page, status in sorted(analysis_results.items(), key=lambda x: x[0]):
            print(f"Halaman {page}: {status}")
        
        print(f"\nHasil analisis telah disimpan ke {output_file}")
    except Exception as e:
        print(f"Gagal menyimpan hasil: {str(e)}")

if __name__ == "__main__":
    main()