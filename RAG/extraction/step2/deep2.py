import pdfplumber
import pandas as pd

def extract_tables_from_pdf(pdf_path):
    # Buka file PDF
    with pdfplumber.open(pdf_path) as pdf:
        all_tables = []
        
        # Iterasi melalui setiap halaman
        for page_num, page in enumerate(pdf.pages):
            print(f"Processing page {page_num + 1}...")
            
            # Ekstrak teks dari halaman
            text = page.extract_text()
            if text:
                print(f"Text from page {page_num + 1}:\n{text}\n")
            
            # Ekstrak tabel dari halaman
            tables = page.extract_tables()
            for table_num, table in enumerate(tables):
                print(f"Table {table_num + 1} from page {page_num + 1}:")
                
                # Konversi tabel ke DataFrame pandas
                df = pd.DataFrame(table[1:], columns=table[0])
                print(df)
                all_tables.append(df)
                print("\n")
    
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