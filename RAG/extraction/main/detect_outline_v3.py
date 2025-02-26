import fitz
import numpy as np
import cv2
from pathlib import Path
from typing import List, Tuple, Dict
import os

def detect_and_highlight_lines(
    pdf_path: str, 
    output_dir: str = "output", 
    min_line_length: int = 200, 
    line_thickness: int = 2,
    header_threshold: float = 50,
    footer_threshold: float = 50,
    scan_header_threshold: float = 100,
    scan_footer_threshold: float = 100,
    min_lines_per_page: int = 2
):
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    src_doc = fitz.open(pdf_path)
    dest_doc = fitz.open()  # PDF dengan semua halaman
    
    pages_info = []
    total_pages = len(src_doc)
    pages_with_lines = []  # Untuk melacak halaman mana yang memiliki garis
    
    for page_num in range(total_pages):
        print(f"\nAnalisis Halaman {page_num + 1}:")
        
        page = src_doc[page_num]
        page_width, page_height = page.rect.width, page.rect.height
        
        # Cek dokumen asli atau hasil scan
        text = page.get_text()
        is_scanned = len(text.strip()) == 0
        print(f"- Tipe halaman: {'Hasil scan' if is_scanned else 'Dokumen asli'}")
        
        # Penentuan threshold
        current_header = scan_header_threshold if is_scanned else header_threshold
        current_footer = scan_footer_threshold if is_scanned else footer_threshold
        print(f"- Threshold yang digunakan: Header={current_header}, Footer={current_footer}")
        
        # Cek rotasi
        rotation = page.rotation
        print(f"- Rotasi halaman: {rotation} derajat")
        
        dest_page = dest_doc.new_page(width=page_width, height=page_height)
        dest_page.show_pdf_page(page.rect, src_doc, page_num, rotate=-rotation)
        
        # Persiapan image
        zoom = 2
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        
        if img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2GRAY)
        elif img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            
        if rotation == 180:
            img = cv2.rotate(img, cv2.ROTATE_180)
        
        # Deteksi Garis
        _, binary = cv2.threshold(img, 200, 255, cv2.THRESH_BINARY_INV)
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (min_line_length, line_thickness))
        detect_horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, line_thickness))
        detect_horizontal = cv2.dilate(detect_horizontal, horizontal_kernel, iterations=1)
        
        contours, _ = cv2.findContours(detect_horizontal, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        print(f"- Total garis terdeteksi awal: {len(contours)}")
        
        # Proses eliminasi garis
        valid_lines = []
        eliminated_by_length = 0
        eliminated_by_position = 0
        
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            y_pdf = y / zoom
            
            # Check panjang minimum
            if w < min_line_length:
                eliminated_by_length += 1
                continue
                
            # Check posisi header/footer
            if (y_pdf < current_header) or (y_pdf > page_height - current_footer):
                eliminated_by_position += 1
                continue
            
            valid_lines.append((x, y, w, h))
        
        print("- Hasil eliminasi:")
        print(f"  * Eliminasi karena panjang < {min_line_length}: {eliminated_by_length} garis")
        print(f"  * Eliminasi karena posisi di header/footer: {eliminated_by_position} garis")
        print(f"  * Garis valid setelah eliminasi: {len(valid_lines)}")
        
        has_valid_lines = len(valid_lines) >= min_lines_per_page
        
        # Check minimum lines per page
        if not has_valid_lines:
            print(f"  * Halaman dilewati: jumlah garis valid ({len(valid_lines)}) < minimum ({min_lines_per_page})")
        else:
            # Tandai halaman ini memiliki garis
            pages_with_lines.append(page_num)
            
            # Gambar garis yang valid
            yellow = (1, 1, 0)
            line_info = []
            
            for x, y, w, h in valid_lines:
                x1 = x / zoom
                y1 = y / zoom - 0.5
                x2 = (x + w) / zoom
                y2 = y / zoom + 0.5
                
                if rotation == 90:
                    x1, y1, x2, y2 = y1, page_width - x2, y2, page_width - x1
                elif rotation == 180:
                    x1, y1, x2, y2 = page_width - x2, page_height - y2, page_width - x1, page_height - y1
                elif rotation == 270:
                    x1, y1, x2, y2 = page_height - y2, x1, page_height - y1, x2
                
                rect = fitz.Rect(x1, y1, x2, y2)
                dest_page.draw_rect(rect, color=yellow, fill=yellow)
                
                line_info.append({
                    'y_position': y / zoom,
                    'x_min': x1,
                    'x_max': x2
                })
            
            if line_info:
                pages_info.append({
                    'page_num': page_num + 1,
                    'is_scanned': is_scanned,
                    'rotation': rotation,
                    'lines': line_info
                })
    
    # Simpan hasil PDF 1 (semua halaman dengan garis yang di-highlight)
    output_path_all = f"{output_dir}/document_with_lines.pdf"
    dest_doc.save(output_path_all)
    
    # Generate PDF 2 (hanya halaman dengan garis, dikelompokkan jika berurutan)
    generate_grouped_pdfs(src_doc, pages_with_lines, output_dir)
    
    # Print ringkasan akhir
    print("\nRINGKASAN AKHIR:")
    print(f"Total halaman dalam dokumen: {total_pages}")
    print(f"Jumlah halaman yang memiliki garis: {len(pages_with_lines)}")
    
    if pages_info:
        print("\nDetail garis yang terdeteksi:")
        for page in pages_info:
            print(f"\nHalaman {page['page_num']} (Scan: {page['is_scanned']}, Rotasi: {page['rotation']})")
            for i, line in enumerate(page['lines'], 1):
                print(f"  Garis {i}:")
                print(f"    Posisi Y: {line['y_position']:.2f} points")
                print(f"    X_min: {line['x_min']:.2f}, X_max: {line['x_max']:.2f}")
    
    print(f"\nHasil PDF dengan semua halaman disimpan ke: {output_path_all}")
    
    dest_doc.close()
    src_doc.close()

def generate_grouped_pdfs(src_doc, pages_with_lines, output_dir):
    """
    Menghasilkan PDF yang hanya berisi halaman dengan garis, dikelompokkan jika berurutan.
    
    Args:
        src_doc: Dokumen PDF sumber
        pages_with_lines: List nomor halaman yang memiliki garis
        output_dir: Direktori tempat menyimpan hasil
    """
    if not pages_with_lines:
        print("Tidak ada halaman dengan garis terdeteksi.")
        return
    
    # Mencari grup halaman berurutan
    groups = []
    current_group = [pages_with_lines[0]]
    
    for i in range(1, len(pages_with_lines)):
        # Jika halaman berurutan (selisih 1), tambahkan ke grup saat ini
        if pages_with_lines[i] == pages_with_lines[i-1] + 1:
            current_group.append(pages_with_lines[i])
        else:
            # Jika tidak berurutan, simpan grup saat ini dan buat grup baru
            groups.append(current_group)
            current_group = [pages_with_lines[i]]
    
    # Tambahkan grup terakhir
    if current_group:
        groups.append(current_group)
    
    # Buat PDF untuk setiap grup
    for i, group in enumerate(groups):
        dest_doc = fitz.open()
        
        for page_num in group:
            page = src_doc[page_num]
            dest_doc.insert_pdf(src_doc, from_page=page_num, to_page=page_num)
        
        # Simpan PDF grup
        group_start = group[0] + 1  # +1 untuk nomor halaman yang dimulai dari 1
        group_end = group[-1] + 1
        
        if len(group) == 1:
            filename = f"{output_dir}/pages_with_lines_page_{group_start}.pdf"
        else:
            filename = f"{output_dir}/pages_with_lines_pages_{group_start}-{group_end}.pdf"
        
        dest_doc.save(filename)
        print(f"PDF untuk halaman {group_start}" + (f"-{group_end}" if len(group) > 1 else "") + f" disimpan ke: {filename}")
        dest_doc.close()

# Contoh penggunaan
if __name__ == "__main__":
    detect_and_highlight_lines(
        pdf_path="studi_kasus/Batavia Dana Likuid.pdf",
        output_dir="output_images",
        min_line_length=30,
        line_thickness=1,
        header_threshold=120,
        footer_threshold=100,
        scan_header_threshold=120,
        scan_footer_threshold=100
    )