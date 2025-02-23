import cv2
import numpy as np
import pdf2image
import os

def detect_horizontal_lines(image, min_length=100):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=100, minLineLength=min_length, maxLineGap=5)
    horizontal_lines = []
    
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            if abs(y2 - y1) < 5 and abs(x2 - x1) >= min_length:  # Garis horizontal dengan panjang minimal
                horizontal_lines.append((x1, y1, x2, y2))
    
    return horizontal_lines

def process_pdf(pdf_path, output_dir="output_images", min_length=100):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    images = pdf2image.convert_from_path(pdf_path)
    
    for i, img in enumerate(images):
        image_cv = np.array(img)
        image_cv = cv2.cvtColor(image_cv, cv2.COLOR_RGB2BGR)
        
        lines = detect_horizontal_lines(image_cv, min_length)
        
        if lines:
            for x1, y1, x2, y2 in lines:
                cv2.line(image_cv, (x1, y1), (x2, y2), (0, 255, 255), 2)  # Tambahkan garis kuning
            
            output_path = os.path.join(output_dir, f"page_{i+1}.png")
            cv2.imwrite(output_path, image_cv)
            print(f"Saved: {output_path}")

if __name__ == "__main__":
    pdf_file = "studi_kasus/8_Tabel_N_Halaman_Merge_V1.pdf"  # Ganti dengan path PDF Anda
    process_pdf(pdf_file)
