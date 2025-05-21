import os
import json
import PyPDF2
import pytesseract
from PIL import Image
import fitz  # PyMuPDF
import cv2
import numpy as np
from io import BytesIO
from datetime import datetime

class Logger:
    """Logger untuk mencatat aktivitas analisis PDF ke file log yang sama."""
    def __init__(self, log_dir="log"):
        os.makedirs(log_dir, exist_ok=True)
        log_filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_Classify.log"
        self.LOG_FILE = os.path.join(log_dir, log_filename)

    def log_info(self, message, status="INFO"):
        """Menyimpan log ke file dengan format timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [{status}] {message}\n"

        with open(self.LOG_FILE, "a", encoding="utf-8") as log_file:
            log_file.write(log_message)
        
        # Juga cetak ke console untuk memudahkan debug
        print(log_message.strip())

class Classify:
    def __init__(self, output_dir="hasil_analisis"):
        """Inisialisasi analyzer dengan lokasi folder output dan logger."""
        self.logger = Logger()
        self.output_dir = os.path.join(os.getcwd(), output_dir)
        os.makedirs(self.output_dir, exist_ok=True)
        self.logger.log_info("PDF Analyzer diinisialisasi")
    
    def _detect_horizontal_lines(self, image, min_line_count=1, min_line_length_percent=20):
        """
        Deteksi garis horizontal dalam gambar.
        
        Parameters:
        image: Gambar input
        min_line_count: Jumlah minimum garis untuk dianggap ada garis
        min_line_length_percent: Panjang minimum garis sebagai persentase dari lebar halaman
        
        Returns:
        boolean: True jika ditemukan garis horizontal yang cukup
        """
        height, width = image.shape[:2]
        min_line_length = int((min_line_length_percent / 100.0) * width)
        
        self.logger.log_info(f"Mendeteksi garis horizontal dengan min_count={min_line_count}, min_length={min_line_length_percent}%", "DEBUG")

        # Convert to grayscale if not already
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image
            
        _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
        detected_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel, iterations=1)

        contours, _ = cv2.findContours(detected_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        valid_lines = [
            cv2.boundingRect(cnt)[2]
            for cnt in contours
            if cv2.boundingRect(cnt)[2] >= min_line_length
        ]
        
        result = len(valid_lines) >= min_line_count
        self.logger.log_info(f"Ditemukan {len(valid_lines)} garis valid, hasil: {result}", "DEBUG")
        return result

    def _file_exists(self, pdf_name):
        """Memeriksa apakah file hasil analisis sudah ada di direktori."""
        expected_file = os.path.join(self.output_dir, f"{pdf_name}_analyzed.json")
        return os.path.exists(expected_file)

    def analyze(self, pdf_paths, min_text_length=50, min_line_count=1, min_line_length_percent=20):
        """
        Fungsi utama untuk menganalisis daftar file PDF.
        
        Parameters:
        pdf_paths (list): List berisi [nama_file, path_file] untuk setiap file PDF.
        min_text_length: Panjang minimum teks untuk dianggap memiliki teks
        min_line_count: Jumlah minimum garis untuk dianggap memiliki garis
        min_line_length_percent: Panjang minimum garis sebagai persentase dari lebar halaman
        
        Returns:
        dict: Hasil analisis untuk setiap file PDF
        """
        hasil_all = {}
        
        for pdf_name, pdf_path in pdf_paths:
            output_file = os.path.join(self.output_dir, f"{pdf_name}_classified.json")
            
            # Periksa apakah file hasil analisis sudah ada
            if self._file_exists(pdf_name):
                self.logger.log_info(f"File hasil analisis untuk {pdf_name} sudah ada, melewati proses.")
                
                # Baca hasil yang sudah ada
                with open(output_file, 'r', encoding='utf-8') as f:
                    hasil_gabungan = json.load(f)
                    hasil_all[pdf_name] = hasil_gabungan
                continue
            
            try:
                hasil_gabungan = self._analyze_single_pdf(
                    pdf_path, 
                    output_file, 
                    min_text_length, 
                    min_line_count, 
                    min_line_length_percent
                )
                hasil_all[pdf_name] = hasil_gabungan
                
            except Exception as e:
                self.logger.log_info(f"Error menganalisis {pdf_name}: {str(e)}", "ERROR")
                hasil_all[pdf_name] = {"error": str(e)}
                
        return hasil_all

    def _analyze_single_pdf(self, pdf_path, output_file, min_text_length=50, 
                           min_line_count=1, min_line_length_percent=20):
        """
        Analisis file PDF tunggal untuk konten teks dan garis horizontal.
        
        Parameters:
        pdf_path: Path ke file PDF
        output_file: Path untuk menyimpan hasil JSON
        min_text_length: Panjang minimum teks untuk dianggap memiliki teks
        min_line_count: Jumlah minimum garis untuk dianggap memiliki garis
        min_line_length_percent: Panjang minimum garis sebagai persentase dari lebar halaman
        
        Returns:
        dict: Hasil analisis untuk setiap halaman
        """
        hasil_gabungan = {}
        start_time = datetime.now()
        
        self.logger.log_info(f"Mulai analisis file {pdf_path}")
        self.logger.log_info(f"Parameter: min_text_length={min_text_length}, min_line_count={min_line_count}, "
                         f"min_line_length_percent={min_line_length_percent}")

        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                doc = fitz.open(pdf_path)
                total_pages = len(pdf_reader.pages)
                
                self.logger.log_info(f"PDF memiliki {total_pages} halaman")

                for i in range(total_pages):
                    page_index = i + 1
                    self.logger.log_info(f"Memproses halaman {page_index}/{total_pages}")
                    
                    # Extract text using PyPDF2
                    pdf_page = pdf_reader.pages[i]
                    text = pdf_page.extract_text()

                    # Render image using PyMuPDF
                    page = doc[i]
                    pix = page.get_pixmap(dpi=200)
                    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
                    if pix.n == 4:
                        img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
                    else:
                        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

                    # Check text content
                    if text and len(text.strip()) >= min_text_length:
                        ocr_status = False
                        self.logger.log_info(f"Halaman {page_index}: Teks mencukupi tanpa OCR", "DEBUG")
                    else:
                        self.logger.log_info(f"Halaman {page_index}: Teks tidak mencukupi, mencoba OCR", "DEBUG")
                        pil_img = Image.fromarray(img)
                        text_from_ocr = pytesseract.image_to_string(pil_img)
                        
                        if text_from_ocr and len(text_from_ocr.strip()) >= min_text_length:
                            ocr_status = True
                            self.logger.log_info(f"Halaman {page_index}: OCR berhasil, teks mencukupi", "DEBUG")
                        else:
                            ocr_status = "halaman kosong/gambar saja"
                            self.logger.log_info(f"Halaman {page_index}: OCR gagal, halaman mungkin kosong atau hanya gambar", "DEBUG")

                    # Line detection
                    line_status = self._detect_horizontal_lines(img, min_line_count, min_line_length_percent)

                    # Decision logic
                    if isinstance(ocr_status, bool):
                        ai_status = (ocr_status and line_status) or (not ocr_status and line_status)
                    else:
                        ai_status = False  # Default if OCR failed or results ambiguous

                    hasil_gabungan[str(page_index)] = {
                        "ocr_status": ocr_status,
                        "line_status": line_status,
                        "ai_status": ai_status
                    }

                    self.logger.log_info(f"Hasil halaman {page_index}: OCR={ocr_status}, LINE={line_status}, AI={ai_status}")

            # Save results to JSON file
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(hasil_gabungan, f, indent=4, ensure_ascii=False)
                
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            self.logger.log_info(f"Analisis selesai dalam {duration:.2f} detik")
            self.logger.log_info(f"Hasil disimpan ke {output_file}")
            
            return hasil_gabungan
            
        except Exception as e:
            self.logger.log_info(f"Error menganalisis PDF: {str(e)}", "ERROR")
            raise


# Contoh penggunaan
if __name__ == "__main__":
    # Inisialisasi analyzer
    analyzer = Classify(output_dir="database/classified_result")
    
    # List file PDF untuk dianalisis [nama_file, path_file]
    pdf_files = [
        # ['ABF Indonesia Bond Index Fund','database/prospectus/ABF Indonesia Bond Index Fund.pdf'],
        # ['Avrist Ada Kas Mutiara','database/prospectus/Avrist Ada Kas Mutiara.pdf'],
        # ['Trimegah Kas Syariah','database/prospectus/Trimegah Kas Syariah.pdf']


    ]
    
    # Proses analisis
    hasil = analyzer.analyze(
        pdf_files,
        min_text_length=50, 
        min_line_count=3, 
        min_line_length_percent=10
    )
    
    # Output hasil
    print("Rangkuman hasil analisis:")
    for pdf_name, result in hasil.items():
        if "error" in result:
            print(f"- {pdf_name}: Error - {result['error']}")
        else:
            ai_pages = sum(1 for page_data in result.values() if page_data.get("ai_status", False))
            total_pages = len(result)
            print(f"- {pdf_name}: {ai_pages}/{total_pages} halaman memenuhi kriteria AI")