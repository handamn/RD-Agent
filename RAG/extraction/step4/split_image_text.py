import fitz
import os
from datetime import datetime
import re

class PDFExtractor:
    def __init__(self, pdf_path, output_dir):
        """
        Inisialisasi PDFExtractor
        :param pdf_path: Path ke file PDF
        :param output_dir: Directory untuk menyimpan hasil ekstraksi
        """
        self.pdf_path = pdf_path
        self.output_dir = output_dir
        self.doc = fitz.open(pdf_path)
        
        # Buat directory output jika belum ada
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(os.path.join(output_dir, "tables"), exist_ok=True)
        os.makedirs(os.path.join(output_dir, "text"), exist_ok=True)
        
        # Generate timestamp untuk unique identifier
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
    def is_table_row(self, line):
        """
        Deteksi apakah sebuah baris kemungkinan bagian dari tabel
        berdasarkan pola spacing dan karakter
        """
        # Cek pola spacing yang teratur
        spaces = [m.start() for m in re.finditer(' {2,}', line)]
        if len(spaces) >= 2:
            # Cek apakah jarak antar spasi relatif konsisten
            gaps = [spaces[i+1] - spaces[i] for i in range(len(spaces)-1)]
            avg_gap = sum(gaps) / len(gaps)
            deviation = sum(abs(gap - avg_gap) for gap in gaps) / len(gaps)
            if deviation < avg_gap * 0.5:  # Toleransi deviasi 50%
                return True
        
        # Cek karakter yang umum dalam tabel
        table_chars = '|+-═━┃┏┓┗┛┣┫┳┻╋'
        if any(char in line for char in table_chars):
            return True
            
        return False
    
    def detect_table_region(self, page, blocks):
        """
        Deteksi region tabel berdasarkan blocks teks dan garis
        """
        table_regions = []
        current_region = None
        
        # Dapatkan semua garis di halaman
        lines = page.get_drawings()
        horizontal_lines = [l for l in lines if abs(l['rect'][1] - l['rect'][3]) < 2]
        vertical_lines = [l for l in lines if abs(l['rect'][0] - l['rect'][2]) < 2]
        
        for block in blocks:
            block_bbox = fitz.Rect(block[:4])
            text = block[4]
            
            # Cek apakah block berada di antara garis
            is_between_lines = any(
                l['rect'][1] <= block_bbox.y0 <= l['rect'][3] or
                l['rect'][1] <= block_bbox.y1 <= l['rect'][3]
                for l in horizontal_lines
            )
            
            # Cek apakah teks memiliki pola tabel
            is_table_text = self.is_table_row(text)
            
            if is_between_lines or is_table_text:
                if current_region is None:
                    current_region = block_bbox
                else:
                    current_region.include_rect(block_bbox)
            elif current_region is not None:
                table_regions.append(current_region)
                current_region = None
        
        if current_region is not None:
            table_regions.append(current_region)
        
        return table_regions
    
    def process_pdf(self):
        """
        Proses PDF untuk mengekstrak teks dan tabel
        """
        current_table = None
        table_count = 0
        text_content = []
        
        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            blocks = page.get_text("blocks")
            table_regions = self.detect_table_region(page, blocks)
            
            # Tambahkan margin untuk region tabel
            margin = 20
            table_regions = [region + (margin, margin, margin, margin) for region in table_regions]
            
            # Proses setiap block
            for block in blocks:
                block_bbox = fitz.Rect(block[:4])
                text = block[4]
                
                # Cek apakah block berada dalam region tabel
                is_in_table = any(region.contains(block_bbox) for region in table_regions)
                
                if is_in_table:
                    # Jika menemukan tabel baru
                    if current_table is None:
                        table_count += 1
                        current_table = {
                            'rect': block_bbox,
                            'start_page': page_num
                        }
                    else:
                        current_table['rect'].include_rect(block_bbox)
                else:
                    # Jika sebelumnya ada tabel yang sedang diproses
                    if current_table is not None:
                        self.save_table_screenshot(
                            current_table['start_page'],
                            page_num - 1,
                            current_table['rect'],
                            table_count
                        )
                        current_table = None
                    
                    # Simpan teks non-tabel
                    text_content.append(f"[Halaman {page_num + 1}]\n{text}\n")
            
            # Handle tabel di akhir halaman
            if current_table is not None and page_num == len(self.doc) - 1:
                self.save_table_screenshot(
                    current_table['start_page'],
                    page_num,
                    current_table['rect'],
                    table_count
                )
        
        # Simpan semua teks non-tabel
        self.save_text_content(text_content)
        
    def save_table_screenshot(self, start_page, end_page, rect, table_num):
        """
        Simpan screenshot tabel
        """
        for page_num in range(start_page, end_page + 1):
            page = self.doc[page_num]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x scaling for better quality
            
            # Generate nama file unik
            filename = f"table_{self.timestamp}_{table_num}_{page_num-start_page+1}.png"
            filepath = os.path.join(self.output_dir, "tables", filename)
            
            pix.save(filepath)
    
    def save_text_content(self, text_content):
        """
        Simpan konten teks
        """
        filename = f"text_{self.timestamp}.txt"
        filepath = os.path.join(self.output_dir, "text", filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(text_content))

# Contoh penggunaan
def process_pdf_file(pdf_path, output_dir):
    extractor = PDFExtractor(pdf_path, output_dir)
    extractor.process_pdf()


pdf_path = "studi_kasus/4_Tabel_Satu_Halaman_Normal_V1.pdf"
output_dir = "result"
process_pdf_file(pdf_path, output_dir)