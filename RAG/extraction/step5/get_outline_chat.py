import pdfplumber
import pandas as pd

def extract_text_and_tables(pdf_path):
    extracted_text = ""
    all_tables = []
    
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # Ekstraksi teks biasa
            extracted_text += page.extract_text() + "\n\n"
            
            # Ekstraksi tabel (meskipun tanpa border)
            tables = page.extract_tables()
            for table in tables:
                df = pd.DataFrame(table)
                all_tables.append(df)
    
    return extracted_text, all_tables

# Contoh penggunaan
pdf_path = "studi_kasus/8_Tabel_N_Halaman_Merge_V1.pdf"
text, tables = extract_text_and_tables(pdf_path)

# Simpan teks ke file
with open("extracted_text.txt", "w", encoding="utf-8") as f:
    f.write(text)

# Simpan tabel ke file CSV atau Excel
for idx, table in enumerate(tables):
    table.to_csv(f"table_{idx+1}.csv", index=False, header=False)
    # Alternatif: Simpan ke Excel
    # table.to_excel(f"table_{idx+1}.xlsx", index=False, header=False)

print("Ekstraksi selesai. Teks disimpan di extracted_text.txt dan tabel disimpan dalam file CSV.")
