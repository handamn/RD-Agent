import fitz
import numpy as np
import cv2
from pathlib import Path

def detect_and_highlight_lines(
    pdf_path, 
    output_dir="output", 
    min_line_length=200, 
    line_thickness=2,  # Now controls detection thickness
    header_threshold=50,
    footer_threshold=50
):
    """
    Membuat salinan PDF dengan highlight pada garis horizontal yang terdeteksi.
    Semua halaman akan tetap ada dalam output PDF.
    
    Args:
        pdf_path (str): Path ke file PDF
        output_dir (str): Direktori untuk menyimpan output
        min_line_length (int): Panjang minimum garis yang akan dideteksi
        line_thickness (int): Ketebalan garis yang akan dideteksi
        header_threshold (float): Ukuran area header yang akan diabaikan (dalam points)
        footer_threshold (float): Ukuran area footer yang akan diabaikan (dalam points)
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Buka PDF source
    src_doc = fitz.open(pdf_path)
    
    # Buat PDF baru untuk output
    dest_doc = fitz.open()
    
    pages_with_lines = []
    total_pages = len(src_doc)
    
    for page_num in range(total_pages):
        page = src_doc[page_num]
        
        # Get page dimensions
        page_height = page.rect.height
        
        # Buat halaman baru di PDF tujuan
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
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (min_line_length, line_thickness))
        detect_horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, line_thickness))
        detect_horizontal = cv2.dilate(detect_horizontal, horizontal_kernel, iterations=1)
        
        # Temukan kontur
        contours, _ = cv2.findContours(detect_horizontal, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        has_lines = False
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            # Konversi y ke skala PDF
            y_pdf = y / zoom
            
            # Skip jika garis berada di area header atau footer
            if (y_pdf < header_threshold) or (y_pdf > page_height - footer_threshold):
                continue
                
            if w/h > 20 and w > min_line_length:
                has_lines = True
                
                # Konversi koordinat kembali ke skala asli
                x1 = x / zoom
                y1 = y / zoom - 0.5  # Minimum highlight thickness (0.5 point)
                x2 = (x + w) / zoom
                y2 = y / zoom + 0.5  # Minimum highlight thickness (0.5 point)
                
                # Gambar garis kuning di PDF dengan ketebalan minimal
                rect = fitz.Rect(x1, y1, x2, y2)
                yellow = (1, 1, 0)
                dest_page.draw_rect(rect, color=yellow, fill=yellow)
                
                print(f"Garis terdeteksi di halaman {page_num + 1} pada posisi y: {y_pdf:.2f} points")
        
        if has_lines:
            pages_with_lines.append(page_num + 1)
    
    # Simpan hasil
    output_path = f"{output_dir}/document_with_lines.pdf"
    dest_doc.save(output_path)
    
    # Print summary
    print("\nRingkasan deteksi garis horizontal:")
    print(f"Total halaman dalam dokumen: {total_pages}")
    print(f"Jumlah halaman yang memiliki garis: {len(pages_with_lines)}")
    if pages_with_lines:
        print("Garis horizontal ditemukan di halaman:", ", ".join(map(str, pages_with_lines)))
    print(f"\nHasil disimpan ke: {output_path}")
    print(f"Area yang diabaikan:")
    print(f"- Header: {header_threshold} points dari atas")
    print(f"- Footer: {footer_threshold} points dari bawah")
    
    dest_doc.close()
    src_doc.close()

# Contoh penggunaan
if __name__ == "__main__":
    detect_and_highlight_lines(
        pdf_path="studi_kasus/ABF Indonesia Bond Index Fund.pdf",
        output_dir="output_images",
        min_line_length=50,
        line_thickness=1,
        header_threshold=100,  # Sesuaikan dengan kebutuhan
        footer_threshold=100   # Sesuaikan dengan kebutuhan
    )