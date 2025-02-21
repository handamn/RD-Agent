import pdfplumber
import camelot
import pandas as pd

def extract_text_from_pdf(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text

def extract_tables_from_pdf(pdf_path):
    tables = camelot.read_pdf(pdf_path, pages='all', strip_text='\n')
    extracted_tables = []
    
    for table in tables:
        df = table.df  # Convert to Pandas DataFrame
        extracted_tables.append(df)
    
    return extracted_tables

def merge_broken_tables(tables):
    merged_tables = []
    temp_table = None
    
    for table in tables:
        if temp_table is None:
            temp_table = table
        else:
            # If header is similar, append the table
            if table.iloc[0].equals(temp_table.iloc[0]):
                temp_table = pd.concat([temp_table, table.iloc[1:]], ignore_index=True)
            else:
                merged_tables.append(temp_table)
                temp_table = table
    
    if temp_table is not None:
        merged_tables.append(temp_table)
    
    return merged_tables

def format_extracted_data(tables):
    formatted_tables = []
    
    for table in tables:
        table.columns = table.iloc[0]  # Set first row as header
        table = table[1:].reset_index(drop=True)  # Remove duplicated header row
        formatted_tables.append(table)
    
    return formatted_tables

def main(pdf_path):
    text = extract_text_from_pdf(pdf_path)
    tables = extract_tables_from_pdf(pdf_path)
    merged_tables = merge_broken_tables(tables)
    formatted_tables = format_extracted_data(merged_tables)
    
    print("Extracted Text:\n", text)
    print("\nExtracted Tables:")
    for i, table in enumerate(formatted_tables):
        print(f"\nTable {i+1}:")
        print(table.to_string(index=False))

if __name__ == "__main__":
    pdf_path = "studi_kasus/7_Tabel_N_Halaman_Normal_V1.pdf"  # Ganti dengan path PDF Anda
    main(pdf_path)
