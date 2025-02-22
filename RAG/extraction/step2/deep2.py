import pdfplumber
import pandas as pd

def extract_tables_from_pdf(pdf_path):
    # Buka file PDF
    with pdfplumber.open(pdf_path) as pdf:
        all_tables = []
        current_table = []  # Untuk menangani tabel yang terpisah di beberapa halaman
        header = None  # Untuk menyimpan header tabel
        
        # Iterasi melalui setiap halaman
        for page_num, page in enumerate(pdf.pages):
            print(f"Processing page {page_num + 1}...")
            
            # Ekstrak teks dari halaman
            text = page.extract_text()
            if text:
                print(f"Text from page {page_num + 1}:\n{text}\n")
            
            # Ekstrak tabel dari halaman
            tables = page.extract_tables()
            for table in tables:
                if not table:
                    continue
                
                # Jika header belum disimpan, simpan header dari tabel pertama
                if header is None:
                    header = table[0]
                    current_table.extend(table[1:])  # Tambahkan baris data setelah header
                else:
                    # Jika header sudah ada, tambahkan baris data ke tabel saat ini
                    current_table.extend(table)
            
            # Jika tabel selesai di halaman ini, simpan ke all_tables
            if current_table:
                df = pd.DataFrame(current_table, columns=header)
                all_tables.append(df)
                current_table = []  # Reset tabel saat ini
                header = None  # Reset header
        
    return all_tables

# Path ke file PDF Anda
pdf_path = "studi_kasus/7_Tabel_N_Halaman_Normal_V1.pdf"

# Ekstrak tabel dari PDF
extracted_tables = extract_tables_from_pdf(pdf_path)

# Simpan tabel ke file Excel (opsional)
with pd.ExcelWriter("extracted_tables.xlsx") as writer:
    for i, table in enumerate(extracted_tables):
        table.to_excel(writer, sheet_name=f"Table_{i+1}", index=False)

print("Extraction completed and saved to 'extracted_tables.xlsx'.")