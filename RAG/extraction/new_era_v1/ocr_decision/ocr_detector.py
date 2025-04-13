import os
import json
import PyPDF2
from pdf2image import convert_from_path
import pytesseract
from PIL import Image

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
                        
                        if text_from_ocr and len(text_from_ocr.strip()) >= min_text_length:
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
    
    # Mendapatkan hasil analisis
    ocr_analysis = check_page_needs_ocr(pdf_path)
    
    if not ocr_analysis:
        print("Gagal menganalisis PDF.")
        return
    
    # Simpan hasil sebagai JSON
    output_file = os.path.splitext(pdf_path)[0] + "_ocr_analysis.json"
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