import cv2
import numpy as np
import pdf2image
import os

def detect_horizontal_lines(image, min_length=100, max_thickness=3, header_ratio=0.2, footer_ratio=0.1):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Gunakan operasi morfologi untuk menghilangkan noise
    kernel = np.ones((1, 5), np.uint8)
    gray = cv2.morphologyEx(gray, cv2.MORPH_OPEN, kernel)
    
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=100, minLineLength=min_length, maxLineGap=5)
    horizontal_lines = []
    
    if lines is not None:
        img_height, img_width = gray.shape
        header_limit = int(img_height * header_ratio)
        footer_limit = int(img_height * (1 - footer_ratio))
        min_valid_length = img_width * 0.5  # Hanya deteksi garis lebih panjang dari 50% lebar halaman
        
        for line in lines:
            x1, y1, x2, y2 = line[0]
            thickness = abs(y2 - y1)
            line_length = abs(x2 - x1)
            
            # Abaikan garis di header, footer, atau yang terlalu pendek
            if thickness <= max_thickness and line_length >= min_valid_length:
                if header_limit <= y1 <= footer_limit and header_limit <= y2 <= footer_limit:
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
        # cv2.line(image_cv, (50, 50), (150, 50), (0, 0, 255), 2)  # Garis merah sepanjang 100 piksel
        
        lines = detect_horizontal_lines(image_cv, min_length, max_thickness)
        
        if lines:
            # Urutkan garis berdasarkan panjang dari yang terpanjang ke terpendek
            sorted_lines = sorted(lines, key=lambda line: abs(line[2] - line[0]), reverse=True)
            
            for idx, (x1, y1, x2, y2) in enumerate(sorted_lines):
                if idx < 3:  # 3 garis terpanjang
                    color = (255, 255, 0)  # Biru untuk 3 garis terpanjang
                    font_scale = 1.0  # Ukuran teks lebih besar
                    thickness = 2
                else:
                    color = (0, 255, 255)  # Kuning untuk garis lainnya
                    font_scale = 0.5  # Ukuran teks lebih kecil
                    thickness = 1
                
                cv2.line(image_cv, (x1, y1), (x2, y2), color, 2)
                
                # Tambahkan teks peringkat hanya untuk garis 1-3 terpanjang
                if idx < 3:
                    text_position = (x2 + 10, y1)
                    cv2.putText(image_cv, f"{idx+1}", text_position, cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 255), thickness, cv2.LINE_AA)
            
            output_path = os.path.join(output_dir, f"page_{i+1}.png")
            cv2.imwrite(output_path, image_cv)
            print(f"Saved: {output_path}")

################
if __name__ == "__main__":
    pdf_file = "studi_kasus/5_Tabel_Satu_Halaman_Merge_V1.pdf"  # Ganti dengan path PDF Anda
    process_pdf(pdf_file, min_length=100, max_thickness=1)
