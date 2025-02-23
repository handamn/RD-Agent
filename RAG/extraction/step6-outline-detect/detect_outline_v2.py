import fitz  # PyMuPDF
import numpy as np
import cv2
from pathlib import Path

def detect_horizontal_lines(pdf_path, output_dir="output", min_line_length=100, line_thickness=2):
    """
    Mendeteksi garis horizontal di PDF dan menghasilkan gambar dengan garis yang disorot.
    
    Args:
        pdf_path (str): Path ke file PDF
        output_dir (str): Direktori untuk menyimpan output
        min_line_length (int): Panjang minimum garis yang akan dideteksi
        line_thickness (int): Ketebalan garis yang akan digambar
    """
    # Buat direktori output jika belum ada
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Buka PDF
    pdf_document = fitz.open(pdf_path)
    
    for page_num in range(len(pdf_document)):
        page = pdf_document[page_num]
        
        # Convert PDF page ke gambar
        pix = page.get_pixmap()
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, pix.n
        )
        
        # Convert ke grayscale jika gambar berwarna
        if img.shape[2] == 4:  # RGBA
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2GRAY)
        elif img.shape[2] == 3:  # RGB
            img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            
        # Deteksi garis menggunakan HoughLinesP
        edges = cv2.Canny(img, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(
            edges,
            1,
            np.pi/180,
            threshold=100,
            minLineLength=min_line_length,
            maxLineGap=10
        )
        
        if lines is not None:
            # Convert kembali ke RGB untuk bisa menggambar garis kuning
            output_img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
            
            has_horizontal_lines = False
            for line in lines:
                x1, y1, x2, y2 = line[0]
                # Cek apakah garis horizontal (slope mendekati 0)
                if abs(y2 - y1) < 5:  # toleransi untuk garis yang sedikit miring
                    cv2.line(
                        output_img,
                        (x1, y1),
                        (x2, y2),
                        (0, 255, 255),  # Warna kuning (BGR)
                        line_thickness
                    )
                    has_horizontal_lines = True
            
            # Simpan gambar jika ditemukan garis horizontal
            if has_horizontal_lines:
                output_path = f"{output_dir}/page_{page_num + 1}_with_lines.png"
                cv2.imwrite(output_path, output_img)
                print(f"Garis horizontal ditemukan di halaman {page_num + 1}, disimpan ke {output_path}")
    
    pdf_document.close()

# Contoh penggunaan
if __name__ == "__main__":
    detect_horizontal_lines(
        pdf_path="dokumen.pdf",
        output_dir="output_images",
        min_line_length=100,
        line_thickness=2
    )