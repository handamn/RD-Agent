import pdfplumber

def extract_text_and_tables(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages):
            print(f"Page {page_number + 1}")
            
            # Extract text
            text = page.extract_text()
            if text:
                print("Text:")
                print(text)
            
            # Extract tables
            tables = page.extract_tables()
            for table_number, table in enumerate(tables):
                print(f"Table {table_number + 1}:")
                for row in table:
                    print(row)
                print("\n")

# Path to your PDF file
pdf_path = "studi_kasus/4_Tabel_Satu_Halaman_Normal_V2.pdf"
extract_text_and_tables(pdf_path)