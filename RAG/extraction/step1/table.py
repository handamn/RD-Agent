from unstructured.partition.pdf import partition_pdf
from unstructured.documents.elements import Table
import os

# Fungsi untuk ekstraksi teks dan tabel dari PDF
def extract_pdf_elements(pdf_path):
    # Memastikan file PDF ada
    if not os.path.exists(pdf_path):
        print(f"File {pdf_path} tidak ditemukan.")
        return
    
    # Ekstraksi konten dari PDF
    elements = partition_pdf(pdf_path)

    # Pisahkan elemen-elemen dalam dokumen
    teks = []
    tabel = []

    # Iterasi untuk mencari elemen teks dan tabel
    for element in elements:
        if isinstance(element, Table):
            tabel.append(element)
        else:
            teks.append(element)

    return teks, tabel

# Path ke file PDF yang ingin diekstraksi
pdf_path = 'studi_kasus/4_Tabel_Satu_Halaman_Normal_V2.pdf'

# Ekstraksi teks dan tabel
teks, tabel = extract_pdf_elements(pdf_path)

# Menampilkan hasil ekstraksi teks
print("Teks yang diekstraksi:")
for item in teks:
    print(item.text)

# Menampilkan hasil ekstraksi tabel
print("\nTabel yang diekstraksi:")
for idx, table in enumerate(tabel, start=1):
    print(f"Tabel {idx}:")
    for row in table.rows:
        print(row)
