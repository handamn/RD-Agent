import fitz
import numpy as np
import cv2
from pathlib import Path

def detect_horizontal_lines(pdf_path, output_dir="output", min_line_length=200, line_thickness=2):
    """
    Mendeteksi garis horizontal di PDF dan menghasilkan gambar dengan garis yang disorot.
    Menggunakan teknik morphology untuk membedakan garis tabel dengan karakter teks.
    
    Args:
        pdf_path (str): Path ke file PDF
        output_dir (str): Direktori untuk menyimpan output
        min_line_length (int): Panjang minimum garis yang akan dideteksi
        line_thickness (int): Ketebalan garis yang akan digambar
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    pdf_document = fitz.open(pdf_path)
    
    for page_num in range(len(pdf_document)):
        page = pdf_document[page_num]
        
        # Convert PDF page ke gambar dengan resolusi lebih tinggi
        zoom = 2  # Tingkatkan resolusi
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, pix.n
        )
        
        # Convert ke grayscale
        if img.shape[2] == 4:  # RGBA
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2GRAY)
        elif img.shape[2] == 3:  # RGB
            img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        
        # Thresholding untuk mendapatkan gambar biner
        _, binary = cv2.threshold(img, 200, 255, cv2.THRESH_BINARY_INV)
        
        # Buat kernel untuk deteksi garis horizontal
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (min_line_length, 1))
        
        # Deteksi garis horizontal menggunakan morphology
        detect_horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)
        
        # Dilasi untuk memperjelas garis
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 1))
        detect_horizontal = cv2.dilate(detect_horizontal, horizontal_kernel, iterations=1)
        
        # Temukan kontur garis
        contours, _ = cv2.findContours(detect_horizontal, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if len(contours) > 0:
            # Convert kembali ke RGB untuk bisa menggambar garis kuning
            output_img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
            
            has_horizontal_lines = False
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                # Filter berdasarkan rasio width/height untuk memastikan ini garis horizontal
                if w/h > 20 and w > min_line_length:  # Minimum ratio dan panjang
                    cv2.rectangle(
                        output_img,
                        (x, y),
                        (x + w, y + h),
                        (0, 255, 255),  # Warna kuning (BGR)
                        line_thickness
                    )
                    has_horizontal_lines = True
            
            # Resize kembali ke ukuran asli
            output_img = cv2.resize(output_img, (0, 0), fx=1/zoom, fy=1/zoom)
            
            # Simpan gambar jika ditemukan garis horizontal
            if has_horizontal_lines:
                output_path = f"{output_dir}/page_{page_num + 1}_with_lines.png"
                cv2.imwrite(output_path, output_img)
                print(f"Garis horizontal ditemukan di halaman {page_num + 1}, disimpan ke {output_path}")
    
    pdf_document.close()

# Contoh penggunaan
if __name__ == "__main__":
    detect_horizontal_lines(
        pdf_path="studi_kasus/8_Tabel_N_Halaman_Merge_V1.pdf",
        output_dir="output_images",
        min_line_length=50,
        line_thickness=1
    )