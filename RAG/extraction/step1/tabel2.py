from unstructured.partition.pdf import partition_pdf

# File PDF yang akan diekstrak
pdf_files = [
    "studi_kasus/7_Tabel_N_Halaman_Normal_V1.pdf",
    # "/mnt/data/4_Tabel_Satu_Halaman_Normal_V2.pdf"
]

# Fungsi untuk mengekstrak teks dan tabel dari PDF
def extract_text_and_tables(pdf_path):
    elements = partition_pdf(pdf_path, strategy="hi_res")  # Menggunakan strategi hi_res untuk deteksi tabel yang lebih baik
    extracted_text = []
    extracted_tables = []

    for element in elements:
        if "Table" in element.category:  # Menyimpan tabel yang terdeteksi
            extracted_tables.append(element)
        else:  # Menyimpan teks lainnya
            extracted_text.append(element.text)

    return extracted_text, extracted_tables

# Proses ekstraksi untuk setiap PDF
for pdf in pdf_files:
    text, tables = extract_text_and_tables(pdf)
    print(f"=== Ekstraksi dari {pdf} ===\n")

    # Cetak teks
    print("== Teks ==\n")
    print("\n".join(text))

    # Cetak tabel jika ada
    print("\n== Tabel ==\n")
    for i, table in enumerate(tables):
        print(f"Tabel {i + 1}:")
        print(table.text)
        print("\n" + "=" * 50 + "\n")
