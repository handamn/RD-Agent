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
pdf_path = "studi_kasus/4_Tabel_Satu_Halaman_Normal_V2.pdf"
extract_pdf_content(pdf_path)

print()
print("---------------------------------")
print()


# from pdfplumber.utils import read_pdf

def extract_pdf_content_with_custom_settings(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                print("\n--- TEXT ---\n")
                print(text)
            
            # Mengatur opsi ekstraksi tabel
            table_settings = {
                "vertical_strategy": "lines",
                "horizontal_strategy": "lines",
                "snap_tolerance": 3,
            }

            # Ekstraksi tabel dengan pengaturan kustom
            tables = page.extract_tables(table_settings=table_settings)
            if tables:
                print("\n--- TABLE ---\n")
                for table in tables:
                    df = pd.DataFrame(table)
                    if not df.empty:
                        print(tabulate(df, headers='keys', tablefmt='grid', showindex=False))

extract_pdf_content_with_custom_settings(pdf_path)