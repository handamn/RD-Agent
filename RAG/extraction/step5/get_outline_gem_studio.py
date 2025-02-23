import fitz  # PyMuPDF
from PIL import Image
import io

def detect_and_crop_tables(pdf_path, output_folder="tables"):
    """
    Mendeteksi tabel dalam PDF dan menghasilkan crop/screenshot dari area tabel.

    Args:
        pdf_path: Path ke file PDF.
        output_folder: Folder untuk menyimpan gambar tabel.
    """

    doc = fitz.open(pdf_path)
    for page_num in range(doc.page_count):
        page = doc.load_page(page_num)
        blocks = page.get_text("blocks")  # Mendapatkan blok-blok teks

        # === DETEKSI TABEL (Perlu ditingkatkan) ===
        # Ini adalah deteksi tabel sederhana berdasarkan deteksi garis.
        # Untuk deteksi yang lebih akurat, Anda mungkin perlu menggunakan
        # model machine learning atau algoritma yang lebih kompleks.
        table_rects = []
        for block in blocks:
            if block[4].count('\n') > 3 and len(block[4]) > 50:  #Heuristik sederhana
                table_rects.append(block[:4]) # (x0, y0, x1, y1)

        # === CROPPING TABEL ===
        for i, rect in enumerate(table_rects):
            x0, y0, x1, y1 = rect
            # Konversi koordinat ke integer
            x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)

            # Render halaman ke gambar (resolusi lebih tinggi untuk kualitas lebih baik)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # Skala 2x
            img = Image.open(io.BytesIO(pix.tobytes("png")))

            # Crop area tabel
            table_image = img.crop((x0, y0, x1, y1))

            # Simpan gambar tabel
            output_path = f"{output_folder}/page_{page_num + 1}_table_{i + 1}.png"
            table_image.save(output_path)
            print(f"Tabel disimpan di: {output_path}")

# === PENGGUNAAN ===
pdf_file = "studi_kasus/8_Tabel_N_Halaman_Merge_V1.pdf"  # Ganti dengan path PDF Anda
output_dir = "result"  # Folder untuk menyimpan tabel

import os
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

detect_and_crop_tables(pdf_file, output_dir)