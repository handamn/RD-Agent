import fitz
import numpy as np
import cv2
from pathlib import Path

def detect_and_highlight_lines(
    pdf_path, 
    output_dir="output", 
    min_line_length=200, 
    line_thickness=2,
    header_threshold=50,
    footer_threshold=50,
    scan_header_threshold=100,
    scan_footer_threshold=100
):
    """
    Membuat salinan PDF dengan highlight pada garis horizontal yang terdeteksi.
    Menyesuaikan threshold berdasarkan jenis halaman (scan atau asli), dan menangani rotasi halaman.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    src_doc = fitz.open(pdf_path)
    dest_doc = fitz.open()
    
    pages_with_lines = []
    total_pages = len(src_doc)
    
    for page_num in range(total_pages):
        page = src_doc[page_num]
        page_width, page_height = page.rect.width, page.rect.height
        
        # Deteksi apakah halaman adalah hasil scan atau asli
        text = page.get_text()
        is_scanned = len(text.strip()) == 0
        
        # Pilih threshold yang sesuai
        if is_scanned:
            current_header_threshold = scan_header_threshold
            current_footer_threshold = scan_footer_threshold
        else:
            current_header_threshold = header_threshold
            current_footer_threshold = footer_threshold
        
        # Cek rotasi halaman
        rotation = page.rotation
        
        # Buat halaman baru di PDF tujuan dengan rotasi yang diperbaiki
        dest_page = dest_doc.new_page(width=page_width, height=page_height)
        dest_page.show_pdf_page(page.rect, src_doc, page_num, rotate=-rotation)
        
        # Get pixmap untuk deteksi garis
        zoom = 2
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        
        # Convert ke grayscale
        if img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2GRAY)
        elif img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        
        # Jika halaman memiliki rotasi 180 derajat, balik gambar
        if rotation == 180:
            img = cv2.rotate(img, cv2.ROTATE_180)
        
        # Threshold dan deteksi garis
        _, binary = cv2.threshold(img, 200, 255, cv2.THRESH_BINARY_INV)
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (min_line_length, line_thickness))
        detect_horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, line_thickness))
        detect_horizontal = cv2.dilate(detect_horizontal, horizontal_kernel, iterations=1)
        
        contours, _ = cv2.findContours(detect_horizontal, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        has_lines = False
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            y_pdf = y / zoom
            
            # Skip garis di area header atau footer
            if (y_pdf < current_header_threshold) or (y_pdf > page_height - current_footer_threshold):
                continue
                
            if w/h > 20 and w > min_line_length:
                has_lines = True
                
                x1, y1 = x / zoom, y / zoom - 0.5
                x2, y2 = (x + w) / zoom, y / zoom + 0.5
                rect = fitz.Rect(x1, y1, x2, y2)
                yellow = (1, 1, 0)
                
                # Sesuaikan koordinat garis berdasarkan rotasi halaman
                if rotation == 90:
                    x1, y1, x2, y2 = y1, page_width - x2, y2, page_width - x1
                elif rotation == 180:
                    x1, y1, x2, y2 = page_width - x2, page_height - y2, page_width - x1, page_height - y1
                elif rotation == 270:
                    x1, y1, x2, y2 = page_height - y2, x1, page_height - y1, x2
                
                dest_page.draw_rect(fitz.Rect(x1, y1, x2, y2), color=yellow, fill=yellow)
                
                print(f"Garis terdeteksi di halaman {page_num + 1} (Scan: {is_scanned}, Rotasi: {rotation}) pada posisi y: {y_pdf:.2f} points")
        
        if has_lines:
            pages_with_lines.append(page_num + 1)
    
    output_path = f"{output_dir}/document_with_lines.pdf"
    dest_doc.save(output_path)
    
    print("\nRingkasan deteksi garis horizontal:")
    print(f"Total halaman dalam dokumen: {total_pages}")
    print(f"Jumlah halaman yang memiliki garis: {len(pages_with_lines)}")
    if pages_with_lines:
        print("Garis horizontal ditemukan di halaman:", ", ".join(map(str, pages_with_lines)))
    print(f"\nHasil disimpan ke: {output_path}")
    dest_doc.close()
    src_doc.close()

# Contoh penggunaan
if __name__ == "__main__":
    detect_and_highlight_lines(
        pdf_path="studi_kasus/Bahana Pendapatan Tetap Makara Prima kelas G.pdf",
        output_dir="output_images",
        min_line_length=50,
        line_thickness=1,
        header_threshold=120,
        footer_threshold=120,
        scan_header_threshold=120,
        scan_footer_threshold=120
    )
