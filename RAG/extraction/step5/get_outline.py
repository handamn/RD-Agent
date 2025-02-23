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
        
        return table_boundaries

    def is_continuation_of_previous_table(self, current_boundary, page_num):
        """Cek apakah tabel merupakan lanjutan dari halaman sebelumnya"""
        x, y, w, h = current_boundary
        
        # Jika ini adalah awal halaman (y kecil) dan ada tabel sebelumnya
        if y < 50 and self.previous_table_bottom is not None and page_num > 0:
            return True
        return False

    def merge_table_images(self, img1, img2):
        """Menggabungkan dua gambar tabel secara vertikal"""
        if img1 is None:
            return img2
        if img2 is None:
            return img1
            
        # Konversi ke format PIL Image jika perlu
        if isinstance(img1, np.ndarray):
            img1 = Image.fromarray(img1)
        if isinstance(img2, np.ndarray):
            img2 = Image.fromarray(img2)
            
        # Sesuaikan lebar gambar
        if img1.width != img2.width:
            # Pilih lebar terbesar
            max_width = max(img1.width, img2.width)
            # Resize kedua gambar ke lebar yang sama
            img1 = img1.resize((max_width, int(img1.height * max_width / img1.width)))
            img2 = img2.resize((max_width, int(img2.height * max_width / img2.width)))
        
        # Buat gambar baru dengan tinggi gabungan
        new_img = Image.new('RGB', (img1.width, img1.height + img2.height))
        new_img.paste(img1, (0, 0))
        new_img.paste(img2, (0, img1.height))
        
        return new_img

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
            print(f"Tabel tersimpan: {output_path}")
            self.current_table_image = None
            self.previous_table_bottom = None

    def process_pdf(self):
        """Proses utama untuk ekstraksi teks dan tabel"""
        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            print(f"\nMemproses halaman {page_num + 1}")
            
            # Ekstrak teks dari halaman
            text = page.get_text()
            
            # Konversi halaman ke gambar untuk deteksi tabel
            pix = page.get_pixmap()
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            img_np = np.array(img)
            
            # Deteksi tabel
            table_boundaries = self.detect_table_boundaries(img_np)
            
            if not table_boundaries:
                # Jika tidak ada tabel di halaman ini, simpan tabel sebelumnya (jika ada)
                self.save_current_table()
                # Print teks jika tidak ada tabel
                if text.strip():
                    print("\nTeks yang diekstrak:")
                    print("-" * 50)
                    print(text.strip())
                    print("-" * 50)
            else:
                for boundary in table_boundaries:
                    table_img = self.capture_table(page, boundary)
                    
                    if self.is_continuation_of_previous_table(boundary, page_num):
                        # Gabungkan dengan tabel sebelumnya
                        self.current_table_image = self.merge_table_images(
                            self.current_table_image, table_img)
                    else:
                        # Simpan tabel sebelumnya jika ada
                        self.save_current_table()
                        # Mulai tabel baru
                        self.current_table_image = table_img
                    
                    # Update posisi terakhir tabel
                    self.previous_table_bottom = boundary[1] + boundary[3]
        
        # Simpan tabel terakhir jika ada
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