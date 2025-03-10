import fitz  # PyMuPDF

def convert_opencv_to_pymupdf(coords, page_width):
    """
    Konversi koordinat hasil OpenCV (y_top, y_bottom) ke format PyMuPDF (x0, y0, x1, y1).
    Karena hanya garis horizontal yang dideteksi, kita asumsikan x0 = 0 dan x1 = page_width.
    
    :param coords: List [(y_top, y_bottom)]
    :param page_width: Lebar halaman PDF
    :return: List of fitz.Rect
    """
    return [fitz.Rect(0, y_top, page_width, y_bottom) for (y_top, y_bottom) in coords]

def split_and_merge_pdf(input_pdf, output_pdf, quarter_coords):
    """
    Memotong halaman PDF berdasarkan quarter_coords lalu menggabungkan hasilnya.

    :param input_pdf: Path file PDF input
    :param output_pdf: Path file PDF hasil
    :param quarter_coords: List [(y_top, y_bottom)] dari hasil deteksi garis OpenCV
    """
    
    # Buka PDF asli
    doc = fitz.open(input_pdf)
    new_doc = fitz.open()
    page = doc[0]  # Ambil halaman pertama
    rect = page.rect  # Ukuran halaman asli
    
    # Pastikan quarter_coords diberikan
    if not quarter_coords:
        raise ValueError("quarter_coords harus diberikan!")

    # Konversi koordinat ke format PyMuPDF
    quarters = convert_opencv_to_pymupdf(quarter_coords, rect.width)

    # Hitung tinggi halaman baru berdasarkan quarter yang dipilih
    new_height = sum(q.height for q in quarters)

    # Buat halaman baru dengan tinggi yang baru
    new_page = new_doc.new_page(width=rect.width, height=new_height)

    # Tempelkan quarter yang dipilih
    y_offset = 0
    for quarter_rect in quarters:
        new_page.show_pdf_page(
            fitz.Rect(rect.x0, y_offset, rect.x1, y_offset + quarter_rect.height),
            doc, 0, clip=quarter_rect
        )
        y_offset += quarter_rect.height

    # Simpan PDF baru
    new_doc.save(output_pdf)
    new_doc.close()
    doc.close()

# Contoh penggunaan hanya dengan quarter_coords
split_and_merge_pdf(
    "studi_kasus/v2.pdf", "output.pdf",
    quarter_coords=[
        (0, 300),    # Ambil bagian dari y=0 sampai y=150
        (500, 800)   # Ambil bagian dari y=500 sampai y=800
    ]
)
