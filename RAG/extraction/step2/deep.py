import pdfplumber
import pandas as pd

def extract_tables_from_pdf(pdf_path):
    tables = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages):
            # Extract tables from the page
            page_tables = page.extract_tables()
            for table in page_tables:
                # Convert the table to a pandas DataFrame
                df = pd.DataFrame(table[1:], columns=table[0])
                tables.append(df)
    return tables

def extract_text_from_pdf(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text()
    return text

def main(pdf_path):
    # Extract text
    text = extract_text_from_pdf(pdf_path)
    print("Extracted Text:")
    print(text)

    # Extract tables
    tables = extract_tables_from_pdf(pdf_path)
    for i, table in enumerate(tables):
        print(f"\nTable {i+1}:")
        print(table)

if __name__ == "__main__":
    pdf_path = "studi_kasus/7_Tabel_N_Halaman_Normal_V2.pdf"
    main(pdf_path)