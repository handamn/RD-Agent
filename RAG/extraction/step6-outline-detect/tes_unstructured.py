from unstructured.partition.pdf import partition_pdf

# Path ke file PDF yang ingin diekstrak
pdf_path = "studi_kasus/1_Teks_Biasa.pdf"

# Ekstraksi teks dari PDF
elements = partition_pdf(pdf_path)

# Menampilkan teks yang diekstrak
# for element in elements:
#     print(element.text)

print(elements.text)

