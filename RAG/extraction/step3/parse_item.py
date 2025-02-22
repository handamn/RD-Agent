import fitz
import cv2
import numpy as np
import os

def deteksi_tabel(halaman):
    """Mendeteksi tabel di halaman PDF."""
    teks = halaman.get_text("blocks")
    tabel = []

    # Deteksi tabel berdasarkan pola teks dan spasi
    for i, blok in enumerate(teks):
        if len(blok[4].split("\n")) > 2 and len(blok[4].split(" ")) > 5:
            tabel.append(blok[:4])  # Ambil koordinat tabel

    return tabel

def potong_gambar_tabel(nama_file_pdf, nomor_halaman, koordinat_tabel, folder_output="potongan_tabel"):
    """Memotong gambar tabel dari halaman PDF dan menyimpannya ke folder."""
    if not os.path.exists(folder_output):
        os.makedirs(folder_output)

    doc = fitz.open(nama_file_pdf)
    halaman = doc[nomor_halaman]
    pix = halaman.get_pixmap()
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

    # Konversi koordinat ke integer
    x0, y0, x1, y1 = map(int, koordinat_tabel)

    potongan_tabel = img[y0:y1, x0:x1]

    nama_file_potongan = f"tabel_halaman_{nomor_halaman + 1}.png"
    jalur_file_potongan = os.path.join(folder_output, nama_file_potongan)
    cv2.imwrite(jalur_file_potongan, potongan_tabel)
    print(f"Gambar tabel disimpan: {jalur_file_potongan}")

    doc.close()

def proses_pdf(nama_file_pdf):
    """Memproses PDF dan mengekstrak tabel."""
    doc = fitz.open(nama_file_pdf)
    for nomor_halaman in range(len(doc)):
        halaman = doc[nomor_halaman]
        tabel = deteksi_tabel(halaman)
        if tabel:
            for koordinat in tabel:
                potong_gambar_tabel(nama_file_pdf, nomor_halaman, koordinat)
    doc.close()

# Contoh penggunaan
nama_file_pdf = "studi_kasus/4_Tabel_Satu_Halaman_Normal_V1.pdf"  # Ganti dengan nama file PDF Anda
proses_pdf(nama_file_pdf)


# pdf_path = "studi_kasus/4_Tabel_Satu_Halaman_Normal_V1.pdf"
# extract_text_from_pdf(pdf_path)
# detect_and_screenshot_tables(pdf_path)
# ocr_text_and_tables_from_pdf(pdf_path)
