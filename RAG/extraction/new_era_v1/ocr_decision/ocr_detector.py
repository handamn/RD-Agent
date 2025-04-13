import os
import json
import PyPDF2
from pdf2image import convert_from_path
import pytesseract
from PIL import Image
import cv2
import numpy as np

def detect_table_in_image(image):
    """
    Mendeteksi indikasi tabel dalam gambar menggunakan pengolahan citra
    """
    try:
        # Konversi ke grayscale
        gray = cv2.cvtColor(np.array(image), cv2.COLOR_BGR2GRAY)
        
        # Thresholding untuk mendapatkan edges
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
        
        # Deteksi garis vertikal dan horizontal
        vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 50))
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (50, 1))
        
        vertical_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, vertical_kernel, iterations=2)
        horizontal_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)
        
        # Hitung jumlah garis yang terdeteksi
        v_lines = cv2.countNonZero(vertical_lines)
        h_lines = cv2.countNonZero(horizontal_lines)
        
        # Jika ditemukan cukup banyak garis vertikal/horizontal, indikasi tabel
        return (v_lines > 100) or (h_lines > 100)
    except:
        return False

def check_page_needs_ocr(pdf_path, min_text_length=50, dpi=200):
    """
    Fungsi untuk memeriksa halaman PDF dengan prioritas:
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
                
                # Pertama, cek indikasi tabel dari gambar
                if page_num < len(images) and detect_table_in_image(images[page_num]):
                    results[page_num + 1] = "terindikasi ada tabel"
                    continue
                
                # Jika tidak ada tabel, lanjutkan pemeriksaan teks
                text = page.extract_text()
                
                if text and len(text.strip()) >= min_text_length:
                    results[page_num + 1] = "cukup scan biasa"
                else:
                    # Gunakan OCR jika diperlukan
                    if page_num < len(images):
                        text_from_ocr = pytesseract.image_to_string(images[page_num])
                        
                        if text_from_ocr and len(text_from_ocr.strip()) >= min_text_length:
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
    ocr_analysis = check_page_needs_ocr(pdf_path)
    
    if not ocr_analysis:
        print("Gagal menganalisis PDF.")
        return
    
    # Simpan hasil sebagai JSON
    output_file = os.path.splitext(pdf_path)[0] + "_enhanced_analysis.json"
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(ocr_analysis, f, indent=4, ensure_ascii=False)
        
        print("\nHasil analisis:")
        for page, status in sorted(ocr_analysis.items(), key=lambda x: x[0]):
            print(f"Halaman {page}: {status}")
        
        print(f"\nHasil analisis telah disimpan ke {output_file}")
    except Exception as e:
        print(f"Gagal menyimpan hasil: {str(e)}")

if __name__ == "__main__":
    main()