import os
import json
import PyPDF2
from pdf2image import convert_from_path
import pytesseract
from PIL import Image

def check_page_needs_ocr(pdf_path):
    """
    Fungsi untuk memeriksa halaman PDF yang memerlukan OCR atau tidak.
    
    Args:
        pdf_path: Path ke file PDF
        
    Returns:
        Dictionary berisi nomor halaman dan status kebutuhan OCR
    """
    results = {}
    
    # Buka file PDF
    with open(pdf_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        total_pages = len(pdf_reader.pages)
        
        print(f"Menganalisis PDF dengan {total_pages} halaman...")
        
        # Loop melalui setiap halaman
        for page_num in range(total_pages):
            page = pdf_reader.pages[page_num]
            
            # Coba ekstrak teks dari halaman
            text = page.extract_text()
            
            # Jika teks tidak kosong dan panjangnya signifikan, kita asumsikan 
            # halaman tersebut tidak perlu OCR
            if text and len(text.strip()) > 50:
                results[page_num + 1] = "cukup scan biasa"
            else:
                # Konversi halaman PDF ke gambar
                images = convert_from_path(pdf_path, first_page=page_num+1, last_page=page_num+1)
                
                # Periksa menggunakan OCR untuk mendapatkan teks
                for img in images:
                    text_from_ocr = pytesseract.image_to_string(img)
                    
                    # Jika OCR dapat mendeteksi teks, halaman memerlukan OCR
                    if text_from_ocr and len(text_from_ocr.strip()) > 50:
                        results[page_num + 1] = "perlu ocr"
                    else:
                        # Ini adalah kasus halaman kosong atau berisi hanya gambar tanpa teks
                        results[page_num + 1] = "cukup scan biasa"
    
    return results

def main():
    # Path ke file PDF
    # pdf_path = input("Masukkan path file PDF yang akan dianalisis: ")
    
    # # Periksa apakah file ada
    # if not os.path.exists(pdf_path):
    #     print(f"Error: File {pdf_path} tidak ditemukan.")
    #     return
    
    pdf_path = "ABF Indonesia Bond Index Fund.pdf"
    
    # Mendapatkan hasil analisis
    ocr_analysis = check_page_needs_ocr(pdf_path)
    
    # Simpan hasil sebagai JSON
    output_file = os.path.splitext(pdf_path)[0] + "_ocr_analysis.json"
    with open(output_file, 'w') as f:
        json.dump(ocr_analysis, f, indent=4)
    
    print(f"\nHasil analisis:")
    for page, status in ocr_analysis.items():
        print(f"Halaman {page}: {status}")
    
    print(f"\nHasil analisis telah disimpan ke {output_file}")

if __name__ == "__main__":
    main()