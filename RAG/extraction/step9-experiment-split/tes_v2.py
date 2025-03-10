import fitz  # PyMuPDF

def crop_and_merge_pdf(input_pdf, output_pdf):
    doc = fitz.open(input_pdf)
    new_doc = fitz.open()
    
    page = doc[0]  # Ambil halaman pertama
    rect = page.rect  # Ukuran halaman asli
    
    quarter_height = rect.height / 4  # Hitung tinggi setiap quarter
    new_height = rect.height - quarter_height  # Tinggi halaman baru (karena quarter 2 dihapus)

    # Definisikan koordinat untuk setiap quarter yang dipertahankan
    quarter_1 = fitz.Rect(rect.x0, rect.y0, rect.x1, rect.y0 + quarter_height)
    quarter_3 = fitz.Rect(rect.x0, rect.y0 + 2 * quarter_height, rect.x1, rect.y0 + 3 * quarter_height)
    quarter_4 = fitz.Rect(rect.x0, rect.y0 + 3 * quarter_height, rect.x1, rect.y1)

    # Buat halaman baru dengan tinggi yang lebih kecil
    new_page = new_doc.new_page(width=rect.width, height=new_height)

    # Tempelkan quarter 1 pada posisi awal
    new_page.show_pdf_page(quarter_1, doc, 0, clip=quarter_1)

    # Tempelkan quarter 3 tepat di bawah quarter 1
    new_page.show_pdf_page(
        fitz.Rect(rect.x0, quarter_height, rect.x1, 2 * quarter_height), doc, 0, clip=quarter_3
    )

    # Tempelkan quarter 4 tepat di bawah quarter 3
    new_page.show_pdf_page(
        fitz.Rect(rect.x0, 2 * quarter_height, rect.x1, new_height), doc, 0, clip=quarter_4
    )

    # Simpan hasil
    new_doc.save(output_pdf)
    new_doc.close()
    doc.close()

# Contoh penggunaan
crop_and_merge_pdf("studi_kasus/v2.pdf", "output.pdf")

