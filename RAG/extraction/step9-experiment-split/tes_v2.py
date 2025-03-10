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

def split_and_merge_pdf(input_pdf, output_pdf, include_quarters=None, quarter_coords=None):
    """
    Memotong halaman PDF berdasarkan koordinat OpenCV lalu menggabungkan quarter yang dipilih.

    :param input_pdf: Path file PDF input
    :param output_pdf: Path file PDF hasil
    :param include_quarters: List quarter yang ingin disertakan (opsional)
    :param quarter_coords: List [(y_top, y_bottom)] dari hasil deteksi garis OpenCV
    """
    
    # Buka PDF asli
    doc = fitz.open(input_pdf)
    new_doc = fitz.open()
    page = doc[0]  # Ambil halaman pertama
    rect = page.rect  # Ukuran halaman asli
    
    # Pastikan quarter_coords diberikan
    if quarter_coords is None:
        raise ValueError("quarter_coords harus diberikan jika tidak menggunakan rasio.")

    # Konversi koordinat ke format PyMuPDF
    quarters = convert_opencv_to_pymupdf(quarter_coords, rect.width)

    # Jika tidak diberikan, gunakan semua quarter yang terdeteksi
    if include_quarters is None:
        include_quarters = list(range(len(quarters)))

    # Hitung tinggi halaman baru berdasarkan quarter yang dipilih
    new_height = sum(quarters[i].height for i in include_quarters)

    # Buat halaman baru dengan tinggi yang baru
    new_page = new_doc.new_page(width=rect.width, height=new_height)

    # Tempelkan quarter yang dipilih
    y_offset = 0
    for i in include_quarters:
        quarter_rect = quarters[i]
        new_page.show_pdf_page(
            fitz.Rect(rect.x0, y_offset, rect.x1, y_offset + quarter_rect.height),
            doc, 0, clip=quarter_rect
        )
        y_offset += quarter_rect.height

    # Simpan PDF baru
    new_doc.save(output_pdf)
    new_doc.close()
    doc.close()

# Contoh penggunaan dengan koordinat hasil OpenCV (garis horizontal)
split_and_merge_pdf(
    "studi_kasus/v2.pdf", "output_opencv.pdf",
    include_quarters=[0, 2],  # Pilih quarter ke-1 dan ke-3
    quarter_coords=[
        (0, 200),    # Quarter 1 (dari y=0 sampai y=200)
        (200, 400),  # Quarter 2 (dari y=200 sampai y=400)
        (400, 600),  # Quarter 3 (dari y=400 sampai y=600)
        (600, 800)   # Quarter 4 (dari y=600 sampai y=800)
    ]
)