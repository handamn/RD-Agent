import fitz  # PyMuPDF

def split_and_merge_pdf(input_pdf, output_pdf):
    doc = fitz.open(input_pdf)
    new_doc = fitz.open()
    
    page = doc[0]  # Ambil halaman pertama
    rect = page.rect  # Ambil ukuran halaman
    
    # Hitung tinggi setiap quarter
    quarter_height = rect.height / 4

    # Definisikan koordinat untuk setiap quarter
    quarters = [
        fitz.Rect(rect.x0, rect.y0, rect.x1, rect.y0 + quarter_height),  # Q1
        fitz.Rect(rect.x0, rect.y0 + quarter_height, rect.x1, rect.y0 + 2 * quarter_height),  # Q2
        fitz.Rect(rect.x0, rect.y0 + 2 * quarter_height, rect.x1, rect.y0 + 3 * quarter_height),  # Q3
        fitz.Rect(rect.x0, rect.y0 + 3 * quarter_height, rect.x1, rect.y1)  # Q4
    ]

    # Ambil quarter 1, 3, dan 4 saja
    selected_quarters = [0, 2, 3]

    for i in selected_quarters:
        new_page = new_doc.new_page(width=rect.width, height=quarter_height)
        new_page.show_pdf_page(new_page.rect, doc, 0, clip=quarters[i])

    # Simpan sebagai PDF baru
    new_doc.save(output_pdf)
    new_doc.close()
    doc.close()

# Contoh penggunaan
split_and_merge_pdf("studi_kasus/v2-cropped-v1.pdf", "output.pdf")
