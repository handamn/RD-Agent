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
    """Logger untuk mencatat aktivitas analisis PDF ke file log."""
    def __init__(self, log_dir="logs"):
        os.makedirs(log_dir, exist_ok=True)
        log_filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_PDF_Analyzer.log"
        self.LOG_FILE = os.path.join(log_dir, log_filename)

    def log_info(self, message, status="INFO"):
        """Menyimpan log ke file dengan format timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [{status}] {message}\n"

        with open(self.LOG_FILE, "a", encoding="utf-8") as log_file:
            log_file.write(log_message)
        
        # Juga cetak ke console untuk memudahkan debug
        print(log_message.strip())

class PDFAnalyzer:
    def __init__(self, log_dir="logs"):
        """
        Initialize the PDF Analyzer with custom logger.
        
        Args:
            log_dir: Directory to store log files (default: "logs")
        """
        self.logger = Logger(log_dir)
        self.logger.log_info("PDF Analyzer diinisialisasi")
    
    def detect_horizontal_lines(self, image, min_line_count=1, min_line_length_percent=20):
        """
        Detect horizontal lines in an image.
        
        Args:
            image: Input image
            min_line_count: Minimum number of lines to consider page has lines
            min_line_length_percent: Minimum length of line as percentage of page width
            
        Returns:
            boolean: True if sufficient horizontal lines are detected
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

    def analyze_pdf(self, pdf_path, output_file="hasil_gabungan.json", min_text_length=50, 
                   min_line_count=1, min_line_length_percent=20):
        """
        Analyze a PDF file for text content and horizontal lines.
        
        Args:
            pdf_path: Path to the PDF file
            output_file: Path to save results JSON
            min_text_length: Minimum text length to consider page has readable text
            min_line_count: Minimum number of lines to consider page has lines
            min_line_length_percent: Minimum length of line as percentage of page width
            
        Returns:
            dict: Analysis results for each page
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
                    line_status = self.detect_horizontal_lines(img, min_line_count, min_line_length_percent)

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

    def batch_analyze(self, pdf_dir, output_dir="hasil", **kwargs):
        """
        Analyze multiple PDF files in a directory.
        
        Args:
            pdf_dir: Directory containing PDF files
            output_dir: Directory to save results
            **kwargs: Additional parameters for analyze_pdf method
        
        Returns:
            dict: Mapping of PDF files to their analysis results
        """
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            self.logger.log_info(f"Membuat direktori output: {output_dir}")
            
        results = {}
        pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf')]
        self.logger.log_info(f"Ditemukan {len(pdf_files)} file PDF di {pdf_dir}")
        
        for pdf_file in pdf_files:
            pdf_path = os.path.join(pdf_dir, pdf_file)
            output_file = os.path.join(output_dir, f"{os.path.splitext(pdf_file)[0]}_analisis.json")
            
            self.logger.log_info(f"Mulai analisis batch untuk {pdf_file}")
            try:
                result = self.analyze_pdf(pdf_path, output_file, **kwargs)
                results[pdf_file] = result
                self.logger.log_info(f"Berhasil menganalisis {pdf_file}")
            except Exception as e:
                self.logger.log_info(f"Gagal menganalisis {pdf_file}: {str(e)}", "ERROR")
                results[pdf_file] = {"error": str(e)}
                
        return results


# Contoh penggunaan
if __name__ == "__main__":
    # Inisialisasi analyzer dengan custom logger
    analyzer = PDFAnalyzer(log_dir="logs")
    
    # Analisis file tunggal
    pdf_path = "ABF Indonesia Bond Index Fund.pdf"
    analyzer.analyze_pdf(
        pdf_path, 
        min_text_length=50, 
        min_line_count=3, 
        min_line_length_percent=10
    )
    
    # Uncomment untuk menjalankan analisis batch pada direktori
    # analyzer.batch_analyze(
    #     "direktori_pdf",
    #     min_text_length=50,
    #     min_line_count=3,
    #     min_line_length_percent=10
    # )