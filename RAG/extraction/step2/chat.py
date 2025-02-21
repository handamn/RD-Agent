import pdfplumber
from unstructured.partition.pdf import partition_pdf

def extract_text_from_pdf(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text

def extract_tables_from_pdf(pdf_path):
    elements = partition_pdf(filename=pdf_path, strategy="hi_res")
    tables = []
    
    for element in elements:
        if element.category == "Table":
            tables.append(element)
    
    return tables

def main(pdf_path):
    text = extract_text_from_pdf(pdf_path)
    tables = extract_tables_from_pdf(pdf_path)
    
    print("Extracted Text:\n", text)
    print("\nExtracted Tables:")
    for i, table in enumerate(tables):
        print(f"\nTable {i+1}:")
        print(table.text)

if __name__ == "__main__":
    pdf_path = "studi_kasus/7_Tabel_N_Halaman_Normal_V2.pdf"  # Ganti dengan path PDF Anda
    main(pdf_path)
