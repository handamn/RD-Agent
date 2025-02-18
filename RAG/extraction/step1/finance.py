import pdfplumber
import pandas as pd
from tabulate import tabulate

def extract_pdf_content(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # Ekstraksi teks
            text = page.extract_text()
            if text:
                print("\n--- TEXT ---\n")
                print(text)
            
            # Ekstraksi tabel
            tables = page.extract_tables()
            if tables:
                print("\n--- TABLE ---\n")
                for table in tables:
                    df = pd.DataFrame(table)
                    if not df.empty:
                        print(tabulate(df, headers='keys', tablefmt='grid', showindex=False))

# Path ke file PDF yang diunggah
pdf_path = "studi_kasus/4_Tabel_Satu_Halaman_Normal_V1.pdf"
extract_pdf_content(pdf_path)
