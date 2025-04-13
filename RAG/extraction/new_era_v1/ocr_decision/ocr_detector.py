import os
import json
import PyPDF2
from pdf2image import convert_from_path
import pytesseract
from PIL import Image

def detect_table_from_text(text):
    """Deteksi tabel dari pola teks sederhana"""
    lines = [line for line in text.split('\n') if line.strip()]
    if len(lines) < 2:  # Minimal 2 baris
        return False
    
    # Hitung jumlah kolom berdasarkan split whitespace
    col_counts = []
    for line in lines:
        cols = [c for c in line.split() if c.strip()]
        col_counts.append(len(cols))
    
    # Minimal 3 kolom pada salah satu baris
    return max(col_counts) >= 3

def check_page_needs_ocr(pdf_path, min_text_length=50, dpi=200):
    """
    Fungsi untuk memeriksa halaman PDF yang memerlukan OCR atau tidak.
    
    Args:
        pdf_path: Path ke file PDF
        min_text_length: Panjang teks minimum untuk dianggap berisi teks
        dpi: Resolusi untuk konversi PDF ke gambar
        
    Returns:
        Dictionary berisi nomor halaman dan status kebutuhan OCR
    """
    results = {}
    
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            total_pages = len(pdf_reader.pages)
            
            print(f"Menganalisis PDF dengan {total_pages} halaman...")
            
            # Konversi semua halaman sekaligus untuk efisiensi
            images = convert_from_path(pdf_path, dpi=dpi)
            
            for page_num in range(total_pages):
                page = pdf_reader.pages[page_num]
                text = page.extract_text()
                
                if text and len(text.strip()) >= min_text_length:
                    results[page_num + 1] = "cukup scan biasa"
                else:
                    # Gunakan gambar yang sudah dikonversi
                    if page_num < len(images):
                        text_from_ocr = pytesseract.image_to_string(images[page_num])
                        
                        # Cek lagi tabel dari hasil OCR
                        if detect_table_from_text(text_from_ocr):
                            results[page_num + 1] = "terindikasi ada tabel"
                        elif text_from_ocr and len(text_from_ocr.strip()) >= min_text_length:
                            results[page_num + 1] = "perlu ocr"
                        else:
                            results[page_num + 1] = "halaman kosong/gambar saja"
                    else:
                        results[page_num + 1] = "gagal diproses"
    
    except Exception as e:
        print(f"Error processing PDF: {str(e)}")
        return {}
    
    return results

def main():
    pdf_path = "ABF Indonesia Bond Index Fund.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"File {pdf_path} tidak ditemukan!")
        return
    
    analysis_results = check_page_needs_ocr(pdf_path)
    
    if not analysis_results:
        print("Gagal menganalisis PDF.")
        return
    
    # Simpan hasil sebagai JSON
    output_file = os.path.splitext(pdf_path)[0] + "_ocr_analysis.json"
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