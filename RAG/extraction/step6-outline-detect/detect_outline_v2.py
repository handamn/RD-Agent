import fitz
import numpy as np
import cv2
from pathlib import Path

def detect_and_highlight_lines(pdf_path, output_dir="output", min_line_length=200, line_thickness=2):
    """
    Mendeteksi garis horizontal di PDF dan menghasilkan PDF baru dengan garis yang disorot.
    
    Args:
        pdf_path (str): Path ke file PDF
        output_dir (str): Direktori untuk menyimpan output
        min_line_length (int): Panjang minimum garis yang akan dideteksi
        line_thickness (int): Ketebalan garis highlight dalam point (pt)
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Buka PDF source
    src_doc = fitz.open(pdf_path)
    
    for page_num in range(len(src_doc)):
        page = src_doc[page_num]
        
        # Buat PDF baru untuk halaman ini
        dest_doc = fitz.open()
        dest_page = dest_doc.new_page(width=page.rect.width, height=page.rect.height)
        
        # Salin konten halaman asli ke halaman baru
        dest_page.show_pdf_page(page.rect, src_doc, page_num)
        
        # Get pixmap untuk deteksi garis
        zoom = 2
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, pix.n
        )
        
        # Convert ke grayscale
        if img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2GRAY)
        elif img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        
        # Threshold dan deteksi garis
        _, binary = cv2.threshold(img, 200, 255, cv2.THRESH_BINARY_INV)
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (min_line_length, 1))
        detect_horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 1))
        detect_horizontal = cv2.dilate(detect_horizontal, horizontal_kernel, iterations=1)
        
        # Temukan kontur
        contours, _ = cv2.findContours(detect_horizontal, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        has_lines = False
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w/h > 20 and w > min_line_length:
                has_lines = True
                # Konversi koordinat kembali ke skala asli
                x1 = x / zoom
                y1 = (y / zoom) - (line_thickness / 2)
                x2 = (x + w) / zoom
                y2 = (y / zoom) + (line_thickness / 2)
                
                # Gambar garis kuning di PDF
                rect = fitz.Rect(x1, y1, x2, y2)
                # Gunakan warna kuning dengan alpha 0.3 (30% opacity)
                yellow = (1, 1, 0)
                dest_page.draw_rect(rect, color=yellow, fill=yellow)
                
        # Simpan halaman jika ada garis yang terdeteksi
        if has_lines:
            output_path = f"{output_dir}/page_{page_num + 1}_with_lines.pdf"
            dest_doc.save(output_path)
            print(f"Garis horizontal ditemukan di halaman {page_num + 1}, disimpan ke {output_path}")
        
        dest_doc.close()
    
    src_doc.close()

# Contoh penggunaan
if __name__ == "__main__":
    detect_and_highlight_lines(
        pdf_path="studi_kasus/8_Tabel_N_Halaman_Merge_V1.pdf",
        output_dir="output_images",
        min_line_length=50,
        line_thickness=1
    )