import fitz
import numpy as np
import cv2
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass

@dataclass
class Line:
    x1: float
    y1: float
    x2: float
    y2: float
    width: float
    
@dataclass
class Table:
    top: float      # Koordinat y teratas
    bottom: float   # Koordinat y terbawah
    lines: List[Line]  # Daftar garis dalam tabel
    
def detect_tables_in_pdf(pdf_path: str, output_dir: str = "output", 
                        min_line_length: int = 200, 
                        line_thickness: int = 2,
                        max_line_gap: int = 50):  # Jarak maksimum antar garis dalam satu tabel
    """
    Mendeteksi multiple tabel dalam PDF berdasarkan garis horizontal.
    
    Args:
        pdf_path: Path ke file PDF
        output_dir: Direktori untuk output
        min_line_length: Panjang minimum garis yang dideteksi
        line_thickness: Ketebalan garis highlight
        max_line_gap: Jarak maksimum antar garis untuk dianggap satu tabel (dalam points)
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    src_doc = fitz.open(pdf_path)
    
    for page_num in range(len(src_doc)):
        page = src_doc[page_num]
        
        # Deteksi garis
        lines = detect_horizontal_lines(page, min_line_length)
        
        if not lines:
            continue
            
        # Kelompokkan garis menjadi tabel
        tables = group_lines_into_tables(lines, max_line_gap)
        
        # Identifikasi header dan footer
        header_region = identify_header_region(tables, page.rect.height)
        footer_region = identify_footer_region(tables, page.rect.height)
        
        # Buat PDF output
        dest_doc = fitz.open()
        dest_page = dest_doc.new_page(width=page.rect.width, height=page.rect.height)
        dest_page.show_pdf_page(page.rect, src_doc, page_num)
        
        # Highlight setiap tabel dengan warna berbeda
        colors = [(1,1,0), (0,1,1), (1,0,1), (0.5,1,0)]  # Yellow, Cyan, Magenta, Lime
        
        for idx, table in enumerate(tables):
            color = colors[idx % len(colors)]
            region_type = "Header" if table == header_region else "Footer" if table == footer_region else f"Table {idx + 1}"
            
            # Gambar highlight untuk setiap garis
            for line in table.lines:
                rect = fitz.Rect(line.x1, line.y1, line.x2, line.y2)
                dest_page.draw_rect(rect, color=color, fill=color)
            
            # Tambahkan label
            text_point = fitz.Point(50, table.top - 5)
            dest_page.insert_text(text_point, region_type, color=color)
        
        # Simpan hasil
        output_path = f"{output_dir}/page_{page_num + 1}_tables.pdf"
        dest_doc.save(output_path)
        print(f"Halaman {page_num + 1}: Terdeteksi {len(tables)} region (saved to {output_path})")
        dest_doc.close()
    
    src_doc.close()

def detect_horizontal_lines(page: fitz.Page, min_line_length: int) -> List[Line]:
    """Deteksi garis horizontal dalam halaman"""
    zoom = 2
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height, pix.width, pix.n
    )
    
    if img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2GRAY)
    elif img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    
    _, binary = cv2.threshold(img, 200, 255, cv2.THRESH_BINARY_INV)
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (min_line_length, 1))
    detect_horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)
    
    contours, _ = cv2.findContours(detect_horizontal, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    lines = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if w/h > 20 and w > min_line_length:
            lines.append(Line(
                x1=x/zoom,
                y1=y/zoom,
                x2=(x+w)/zoom,
                y2=y/zoom,
                width=w/zoom
            ))
    
    return sorted(lines, key=lambda l: l.y1)  # Sort by vertical position

def group_lines_into_tables(lines: List[Line], max_gap: float) -> List[Table]:
    """Kelompokkan garis menjadi tabel berdasarkan jarak vertikal"""
    if not lines:
        return []
    
    tables = []
    current_table = Table(
        top=lines[0].y1,
        bottom=lines[0].y2,
        lines=[lines[0]]
    )
    
    for line in lines[1:]:
        if line.y1 - current_table.bottom > max_gap:
            # Jarak terlalu jauh, ini tabel baru
            tables.append(current_table)
            current_table = Table(
                top=line.y1,
                bottom=line.y2,
                lines=[line]
            )
        else:
            # Masih bagian dari tabel yang sama
            current_table.bottom = line.y2
            current_table.lines.append(line)
    
    tables.append(current_table)
    return tables

def identify_header_region(tables: List[Table], page_height: float) -> Table:
    """Identifikasi region header (jika ada)"""
    if not tables:
        return None
    
    # Anggap tabel paling atas adalah header jika posisinya < 20% tinggi halaman
    if tables[0].top < (page_height * 0.2):
        return tables[0]
    return None

def identify_footer_region(tables: List[Table], page_height: float) -> Table:
    """Identifikasi region footer (jika ada)"""
    if not tables:
        return None
    
    # Anggap tabel paling bawah adalah footer jika posisinya > 80% tinggi halaman
    if tables[-1].bottom > (page_height * 0.8):
        return tables[-1]
    return None

# Contoh penggunaan
if __name__ == "__main__":
    detect_tables_in_pdf(
        pdf_path="studi_kasus/4_Tabel_Satu_Halaman_Normal_V1.pdf",
        output_dir="output_images",
        min_line_length=50,
        line_thickness=1,
        max_line_gap=50  # Sesuaikan dengan kebutuhan
    )