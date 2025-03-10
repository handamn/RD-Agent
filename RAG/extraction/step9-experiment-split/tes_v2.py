import fitz  # PyMuPDF

def split_and_merge_pdf(input_pdf, output_pdf, split_count=4, include_quarters=None, quarter_ratios=None):
    """
    Memotong halaman PDF menjadi beberapa bagian, kemudian menggabungkan quarter yang dipilih.

    :param input_pdf: Path file PDF input
    :param output_pdf: Path file PDF hasil
    :param split_count: Berapa banyak bagian yang ingin dibuat (default: 4)
    :param include_quarters: List quarter yang ingin disertakan, berbasis indeks (default: [0, 2, 3])
    :param quarter_ratios: List proporsi tinggi setiap quarter (default: sama rata)
    """
    
    # Buka PDF asli
    doc = fitz.open(input_pdf)
    new_doc = fitz.open()
    page = doc[0]  # Ambil halaman pertama
    rect = page.rect  # Ukuran halaman asli
    
    # Jika tidak diberikan, gunakan pemisahan yang sama rata
    if quarter_ratios is None:
        quarter_ratios = [1/split_count] * split_count  # Semua bagian sama besar

    # Pastikan jumlah quarter dan rasio sesuai
    if len(quarter_ratios) != split_count:
        raise ValueError("Panjang quarter_ratios harus sama dengan split_count")

    # Hitung tinggi tiap quarter berdasarkan rasio
    quarter_heights = [rect.height * ratio for ratio in quarter_ratios]

    # Buat koordinat quarter
    quarters = []
    y_start = rect.y0
    for height in quarter_heights:
        quarters.append(fitz.Rect(rect.x0, y_start, rect.x1, y_start + height))
        y_start += height

    # Jika tidak diberikan, gunakan default quarter 1, 3, dan 4
    if include_quarters is None:
        include_quarters = [0, 2, 3]

    # Hitung tinggi halaman baru
    new_height = sum(quarter_heights[i] for i in include_quarters)
    
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

# Contoh penggunaan:
split_and_merge_pdf(
    "studi_kasus/v2.pdf", 
    "output.pdf",
    split_count=3,                   # Bagi halaman menjadi 5 bagian
    include_quarters=[0, 2],       # Ambil quarter 1, 2, dan 5
    # quarter_ratios=[0.2, 0.2, 0.2, 0.2, 0.2]  # Setiap quarter punya 20% dari tinggi halaman
)


