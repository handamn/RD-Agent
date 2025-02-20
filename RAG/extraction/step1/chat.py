import pdfplumber
import pandas as pd

def extract_text_and_tables(pdf_path):
    extracted_text = ""
    tables = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            extracted_text += page.extract_text() + "\n"
            
            # Mendeteksi tabel secara otomatis
            standard_tables = page.extract_tables()
            for table in standard_tables:
                df = pd.DataFrame(table)
                tables.append(df)
                
            # Mendeteksi tabel laporan keuangan (hanya garis horizontal)
            words = page.extract_words()
            horizontal_lines = page.lines  # Garis horizontal
            
            # Logika tambahan untuk menangani tabel tanpa garis vertikal bisa dimasukkan di sini
            
    return extracted_text, tables

# Contoh penggunaan
pdf_path = "studi_kasus/5_Tabel_Satu_Halaman_Merge_V2.pdf"
text, tables = extract_text_and_tables(pdf_path)

# Menampilkan hasil
print("Extracted Text:")
print(text[:1000])  # Menampilkan sebagian teks agar tidak terlalu panjang

print("\nExtracted Tables:")
for i, table in enumerate(tables):
    print(f"Table {i+1}:")
    print(table)
    print("-" * 50)
