import pdfplumber
import pandas as pd

def extract_text_from_pdf(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text

def clean_table_data(df):
    df = df.applymap(lambda x: " ".join(str(x).split()) if pd.notnull(x) else "")  # Hapus newline & whitespace berlebih
    df = df.dropna(how='all', axis=1)  # Hapus kolom kosong
    df = df.dropna(how='all', axis=0)  # Hapus baris kosong
    return df

def extract_tables_from_pdf(pdf_path):
    tables = []
    header_detected = None
    
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            extracted_tables = page.extract_tables()
            for table in extracted_tables:
                df = pd.DataFrame(table)
                df = clean_table_data(df)
                
                # Jika tabel kosong, abaikan
                if df.empty:
                    continue
                
                # Simpan header dari halaman pertama jika tidak berubah
                if header_detected is None:
                    header_detected = df.iloc[0].tolist()
                else:
                    if df.iloc[0].tolist() == header_detected:
                        df = df[1:].reset_index(drop=True)
                
                # Pisahkan isi sel panjang menjadi beberapa kolom jika memungkinkan
                df = df.applymap(lambda x: x.replace(" - ", "\n") if isinstance(x, str) else x)
                
                tables.append(df)
    
    return tables

def merge_broken_tables(tables):
    merged_tables = []
    temp_table = None
    
    for table in tables:
        if temp_table is None:
            temp_table = table
        else:
            # Gabungkan tabel jika jumlah kolomnya sama
            if table.shape[1] == temp_table.shape[1]:
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
