import fitz  # PyMuPDF
import numpy as np
import cv2
from PIL import Image
import io
import os

class PDFProcessor:
    def __init__(self):
        # Hardcode lokasi PDF dan output
        self.pdf_path = "studi_kasus/7_Tabel_N_Halaman_Normal_V3.pdf"  # Sesuaikan dengan lokasi PDF Anda
        self.output_dir = "result"  # Sesuaikan dengan lokasi output yang diinginkan
        self.doc = fitz.open(self.pdf_path)
        
        # Membuat direktori output jika belum ada
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        
        # Variabel untuk tracking tabel multi-halaman
        self.previous_table_bottom = None
        self.current_table_image = None
        self.table_counter = 0

    def detect_table_boundaries(self, page_image):
        """Mendeteksi batas-batas tabel menggunakan deteksi garis"""
        gray = cv2.cvtColor(page_image, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
        
        # Deteksi garis horizontal dan vertikal
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
        vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
        
        horizontal_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, horizontal_kernel)
        vertical_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, vertical_kernel)
        
        table_mask = cv2.addWeighted(horizontal_lines, 0.5, vertical_lines, 0.5, 0.0)
        contours, _ = cv2.findContours(table_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        table_boundaries = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w > 100 and h > 50:  # Menurunkan minimum height untuk mendeteksi bagian tabel
                table_boundaries.append((x, y, w, h))
        
        return sorted(table_boundaries, key=lambda x: x[1])  # Sort by y-coordinate

    def extract_text_blocks(self, page, table_boundaries):
        """Ekstrak teks dari area non-tabel dengan mempertahankan struktur"""
        text_blocks = []
        blocks = page.get_text("blocks")
        
        # Konversi koordinat tabel ke format rect untuk pengecekan overlap
        table_rects = [(b[0], b[1], b[0] + b[2], b[1] + b[3]) for b in table_boundaries]
        
        for block in blocks:
            block_rect = block[:4]  # (x0, y0, x1, y1)
            is_in_table = False
            
            # Cek apakah block berada dalam area tabel
            for table_rect in table_rects:
                if (block_rect[0] < table_rect[2] and block_rect[2] > table_rect[0] and
                    block_rect[1] < table_rect[3] and block_rect[3] > table_rect[1]):
                    is_in_table = True
                    break
            
            if not is_in_table:
                text_blocks.append(block[4])  # block[4] contains the text
        
        return text_blocks

    def capture_table(self, page, boundary):
        """Mengambil screenshot area tabel"""
        x, y, w, h = boundary
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # Scale 2x untuk kualitas lebih baik
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        table_img = img.crop((x*2, y*2, (x+w)*2, (y+h)*2))
        return table_img

    def save_current_table(self):
        """Menyimpan tabel yang sedang diproses"""
        if self.current_table_image is not None:
            self.table_counter += 1
            output_path = os.path.join(self.output_dir, f"table_{self.table_counter}.png")
            self.current_table_image.save(output_path)
            print(f"\nTabel tersimpan: {output_path}")
            self.current_table_image = None
            self.previous_table_bottom = None

    def process_pdf(self):
        """Proses utama untuk ekstraksi teks dan tabel"""
        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            print(f"\n{'='*50}")
            print(f"Memproses halaman {page_num + 1}")
            print(f"{'='*50}")
            
            # Konversi halaman ke gambar untuk deteksi tabel
            pix = page.get_pixmap()
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            img_np = np.array(img)
            
            # Deteksi tabel
            table_boundaries = self.detect_table_boundaries(img_np)
            
            # Ekstrak teks dari area non-tabel
            text_blocks = self.extract_text_blocks(page, table_boundaries)
            
            # Print teks non-tabel
            if text_blocks:
                print("\nTeks yang diekstrak:")
                print("-" * 50)
                for block in text_blocks:
                    # Hapus karakter newline berlebih dan whitespace
                    clean_text = ' '.join(block.split())
                    if clean_text:
                        print(clean_text)
                        print("-" * 50)
            
            # Proses tabel yang ditemukan
            for boundary in table_boundaries:
                table_img = self.capture_table(page, boundary)
                self.current_table_image = table_img
                self.save_current_table()

    def close(self):
        """Tutup dokumen PDF"""
        self.doc.close()

# Jalankan proses
def main():
    processor = PDFProcessor()
    processor.process_pdf()
    processor.close()

if __name__ == "__main__":
    main()