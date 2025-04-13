import os
import json
import PyPDF2
import fitz  # PyMuPDF
import pandas as pd
from tabulate import tabulate

def extract_text_with_pypdf2(pdf_path, page_num):
    """Ekstrak teks dari halaman PDF menggunakan PyPDF2"""
    with open(pdf_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        # Konversi nomor halaman ke indeks (0-based)
        page_index = page_num - 1
        if page_index < 0 or page_index >= len(pdf_reader.pages):
            return None
        page = pdf_reader.pages[page_index]
        text = page.extract_text()
        return text.strip() if text else ""

def extract_text_with_pymupdf(pdf_path, page_num):
    """Ekstrak teks dari halaman PDF menggunakan PyMuPDF"""
    doc = fitz.open(pdf_path)
    # Konversi nomor halaman ke indeks (0-based)
    page_index = page_num - 1
    if page_index < 0 or page_index >= len(doc):
        return None
    page = doc[page_index]
    text = page.get_text()
    return text.strip() if text else ""

def extract_tables_with_pymupdf(pdf_path, page_num):
    """
    Coba ekstrak tabel dengan PyMuPDF
    Mengembalikan daftar tabel dalam format DataFrame pandas
    """
    doc = fitz.open(pdf_path)
    page_index = page_num - 1
    if page_index < 0 or page_index >= len(doc):
        return []
    
    page = doc[page_index]
    tables = []
    
    # Ekstrak tabel menggunakan PyMuPDF
    # Ini adalah ekstraksi tabel sederhana, mungkin tidak sempurna
    tab = page.find_tables()
    if tab and tab.tables:
        for idx, table in enumerate(tab.tables):
            rows_data = []
            for row in table.rows:
                row_data = []
                for cell in row.cells:
                    rect = fitz.Rect(cell)
                    text = page.get_text("text", clip=rect)
                    row_data.append(text.strip())
                rows_data.append(row_data)
            if rows_data:
                # Konversi ke DataFrame pandas
                try:
                    df = pd.DataFrame(rows_data[1:], columns=rows_data[0] if rows_data else None)
                    tables.append({
                        "table_id": idx + 1,
                        "data": df.to_dict(orient="records"),
                        "text_representation": tabulate(df, headers="keys", tablefmt="grid")
                    })
                except Exception as e:
                    # Jika gagal menggunakan baris pertama sebagai header
                    df = pd.DataFrame(rows_data)
                    tables.append({
                        "table_id": idx + 1,
                        "data": df.to_dict(orient="records"),
                        "text_representation": tabulate(df, headers="firstrow", tablefmt="grid")
                    })
    
    return tables

def process_pdf_by_analysis(analysis_json_path, pdf_path, output_json_path="result_extraction.json"):
    """
    Proses PDF berdasarkan hasil analisis dan ekstrak teks sesuai metode yang tepat
    """
    # Baca file JSON hasil analisis
    with open(analysis_json_path, 'r', encoding='utf-8') as f:
        analysis_data = json.load(f)
    
    extraction_results = {}
    
    # Iterasi setiap halaman
    for page_num, page_data in analysis_data.items():
        # Lewati entri 'summary' dan pastikan page_num adalah angka
        if page_num == "summary" or not page_num.isdigit():
            continue
        
        page_num_int = int(page_num)
        ocr_status = page_data.get("ocr_status")
        line_status = page_data.get("line_status")
        ai_status = page_data.get("ai_status")  # Asumsi ini sama dengan decision_status
        
        # Inisialisasi hasil untuk halaman ini
        extraction_results[page_num] = {
            "extraction_method": None,
            "content": None,
            "tables": [],
            "analysis": {
                "ocr_status": ocr_status,
                "line_status": line_status,
                "ai_status": ai_status
            }
        }
        
        # Case yang kita implementasikan: "ocr_status", "line_status", "ai_status" semuanya False
        if ocr_status is False and line_status is False and ai_status is False:
            print(f"Halaman {page_num}: Menggunakan ekstraksi PDF langsung")
            
            # Gunakan PyMuPDF untuk ekstraksi teks karena umumnya lebih baik
            text_content = extract_text_with_pymupdf(pdf_path, page_num_int)
            
            # Jika PyMuPDF tidak memberikan hasil baik, coba PyPDF2 sebagai cadangan
            if not text_content or len(text_content) < 50:
                text_content = extract_text_with_pypdf2(pdf_path, page_num_int)
                extraction_results[page_num]["extraction_method"] = "PyPDF2"
            else:
                extraction_results[page_num]["extraction_method"] = "PyMuPDF"
            
            extraction_results[page_num]["content"] = text_content
        else:
            # Untuk kasus lain, kita akan mengimplementasikannya nanti
            extraction_results[page_num]["extraction_method"] = "pending_implementation"
            extraction_results[page_num]["content"] = "Metode ekstraksi belum diimplementasikan untuk konfigurasi ini"
    
    # Simpan hasil ekstraksi
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(extraction_results, f, indent=4, ensure_ascii=False)
    
    print(f"Hasil ekstraksi disimpan ke {output_json_path}")
    return extraction_results

# Contoh penggunaan
if __name__ == "__main__":
    analysis_json_path = "sample.json"  # Path ke file JSON hasil analisis
    pdf_path = "ABF Indonesia Bond Index Fund.pdf"  # Path ke file PDF yang dianalisis
    output_json_path = "result_extraction.json"  # Path untuk menyimpan hasil ekstraksi
    
    process_pdf_by_analysis(analysis_json_path, pdf_path, output_json_path)