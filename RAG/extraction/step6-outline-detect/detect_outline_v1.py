import cv2
import numpy as np
import pdf2image
import os

def detect_horizontal_lines(image, min_length=100, max_thickness=3):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Gunakan operasi morfologi untuk menghilangkan noise
    kernel = np.ones((1, 5), np.uint8)
    gray = cv2.morphologyEx(gray, cv2.MORPH_OPEN, kernel)
    
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=100, minLineLength=min_length, maxLineGap=5)
    horizontal_lines = []
    
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            thickness = abs(y2 - y1)
            if thickness <= max_thickness and abs(x2 - x1) >= min_length:  # Filter garis berdasarkan ketebalan dan panjang
                horizontal_lines.append((x1, y1, x2, y2))
    
    return horizontal_lines

def process_pdf(pdf_path, output_dir="output_images", min_length=100, max_thickness=3):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    images = pdf2image.convert_from_path(pdf_path)
    
    for i, img in enumerate(images):
        image_cv = np.array(img)
        image_cv = cv2.cvtColor(image_cv, cv2.COLOR_RGB2BGR)
        
        # Tambahkan garis referensi sepanjang 100 piksel di awal gambar
        cv2.line(image_cv, (50, 50), (150, 50), (0, 0, 255), 2)  # Garis merah sepanjang 100 piksel
        
        lines = detect_horizontal_lines(image_cv, min_length, max_thickness)
        
        if lines:
            # Urutkan garis berdasarkan panjang dari yang terpanjang ke terpendek
            sorted_lines = sorted(lines, key=lambda line: abs(line[2] - line[0]), reverse=True)
            
            for idx, (x1, y1, x2, y2) in enumerate(sorted_lines):
                if idx < 3:  # 3 garis terpanjang
                    color = (255, 255, 0)  # Biru untuk 3 garis terpanjang
                else:
                    color = (0, 255, 255)  # Kuning untuk garis lainnya
                cv2.line(image_cv, (x1, y1), (x2, y2), color, 2)
            
            output_path = os.path.join(output_dir, f"page_{i+1}.png")
            cv2.imwrite(output_path, image_cv)
            print(f"Saved: {output_path}")

################
if __name__ == "__main__":
    pdf_file = "studi_kasus/8_Tabel_N_Halaman_Merge_V1.pdf"  # Ganti dengan path PDF Anda
    process_pdf(pdf_file, min_length=100, max_thickness=3)
