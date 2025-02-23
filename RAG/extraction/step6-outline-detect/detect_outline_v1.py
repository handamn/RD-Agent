import cv2
import numpy as np
import fitz  # PyMuPDF

def detect_and_draw_horizontal_lines(image):
    # Konversi gambar ke grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Gunakan Canny edge detection
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    
    # Gunakan Hough Line Transform untuk mendeteksi garis
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=100, minLineLength=100, maxLineGap=10)
    
    # Gambar garis horizontal yang terdeteksi dengan warna kuning
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            # Cek apakah garis horizontal (y1 dan y2 hampir sama)
            if abs(y1 - y2) < 5:
                cv2.line(image, (x1, y1), (x2, y2), (0, 255, 255), 2)  # Warna kuning (BGR)
    
    return image, lines is not None

def process_pdf(pdf_path, output_folder):
    # Buka file PDF
    pdf_document = fitz.open(pdf_path)
    
    for page_num in range(len(pdf_document)):
        page = pdf_document.load_page(page_num)
        pix = page.get_pixmap()
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
        
        # Konversi gambar ke format BGR (OpenCV menggunakan BGR)
        img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        
        # Deteksi dan gambar garis horizontal
        img_with_lines, has_lines = detect_and_draw_horizontal_lines(img_bgr)
        
        # Jika ada garis horizontal, simpan gambar
        if has_lines:
            output_path = f"{output_folder}/page_{page_num + 1}.png"
            cv2.imwrite(output_path, cv2.cvtColor(img_with_lines, cv2.COLOR_BGR2RGB))
            print(f"Garis horizontal terdeteksi pada halaman {page_num + 1}. Gambar disimpan di {output_path}")
        else:
            print(f"Tidak ada garis horizontal pada halaman {page_num + 1}")

# Path ke file PDF dan folder output
pdf_path = "studi_kasus/8_Tabel_N_Halaman_Merge_V1.pdf"
output_folder = "output_images"

# Proses PDF
process_pdf(pdf_path, output_folder)
