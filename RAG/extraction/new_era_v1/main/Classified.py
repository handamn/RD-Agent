import os
import json
import logging
import PyPDF2
import pytesseract
from PIL import Image
import fitz  # PyMuPDF
import cv2
import numpy as np
from io import BytesIO
from datetime import datetime

class PDFAnalyzer:
    def __init__(self, log_level=logging.INFO, log_file=None):
        """
        Initialize the PDF Analyzer with logging configuration.
        
        Args:
            log_level: Logging level (default: logging.INFO)
            log_file: Path to log file (default: None, logs to console)
        """
        # Set up logging
        self.logger = self._setup_logging(log_level, log_file)
        self.logger.info("PDF Analyzer initialized")
        
    def _setup_logging(self, log_level, log_file):
        """Set up logging configuration."""
        logger = logging.getLogger('PDFAnalyzer')
        logger.setLevel(log_level)
        
        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # Create file handler if log file is specified
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            
        return logger
    
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
        
        self.logger.debug(f"Detecting horizontal lines with min_count={min_line_count}, min_length={min_line_length_percent}%")

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
        self.logger.debug(f"Found {len(valid_lines)} valid lines, result: {result}")
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
        
        self.logger.info(f"Starting analysis of {pdf_path}")
        self.logger.info(f"Parameters: min_text_length={min_text_length}, min_line_count={min_line_count}, "
                         f"min_line_length_percent={min_line_length_percent}")

        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                doc = fitz.open(pdf_path)
                total_pages = len(pdf_reader.pages)
                
                self.logger.info(f"PDF has {total_pages} pages")

                for i in range(total_pages):
                    page_index = i + 1
                    self.logger.info(f"Processing page {page_index}/{total_pages}")
                    
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
                        self.logger.debug(f"Page {page_index}: Sufficient text found without OCR")
                    else:
                        self.logger.debug(f"Page {page_index}: Insufficient text, attempting OCR")
                        pil_img = Image.fromarray(img)
                        text_from_ocr = pytesseract.image_to_string(pil_img)
                        
                        if text_from_ocr and len(text_from_ocr.strip()) >= min_text_length:
                            ocr_status = True
                            self.logger.debug(f"Page {page_index}: OCR successful, found sufficient text")
                        else:
                            ocr_status = "halaman kosong/gambar saja"
                            self.logger.debug(f"Page {page_index}: OCR failed, page may be empty or image-only")

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

                    self.logger.info(f"Page {page_index} results: OCR={ocr_status}, LINE={line_status}, AI={ai_status}")

            # Save results to JSON file
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(hasil_gabungan, f, indent=4, ensure_ascii=False)
                
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            self.logger.info(f"Analysis completed in {duration:.2f} seconds")
            self.logger.info(f"Results saved to {output_file}")
            
            return hasil_gabungan
            
        except Exception as e:
            self.logger.error(f"Error analyzing PDF: {str(e)}", exc_info=True)
            raise

    def batch_analyze(self, pdf_dir, output_dir="results", **kwargs):
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
            self.logger.info(f"Created output directory: {output_dir}")
            
        results = {}
        pdf_files = [f for f in os.listdir(pdf_dir) if f.lower().endswith('.pdf')]
        self.logger.info(f"Found {len(pdf_files)} PDF files in {pdf_dir}")
        
        for pdf_file in pdf_files:
            pdf_path = os.path.join(pdf_dir, pdf_file)
            output_file = os.path.join(output_dir, f"{os.path.splitext(pdf_file)[0]}_analysis.json")
            
            self.logger.info(f"Starting batch analysis of {pdf_file}")
            try:
                result = self.analyze_pdf(pdf_path, output_file, **kwargs)
                results[pdf_file] = result
                self.logger.info(f"Successfully analyzed {pdf_file}")
            except Exception as e:
                self.logger.error(f"Failed to analyze {pdf_file}: {str(e)}")
                results[pdf_file] = {"error": str(e)}
                
        return results


# Example usage
if __name__ == "__main__":
    # Create a log file with timestamp
    log_filename = f"pdf_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    # Initialize the analyzer with both console and file logging
    analyzer = PDFAnalyzer(log_level=logging.INFO, log_file=log_filename)
    
    # Single file analysis
    pdf_path = "ABF Indonesia Bond Index Fund.pdf"
    analyzer.analyze_pdf(
        pdf_path, 
        min_text_length=50, 
        min_line_count=3, 
        min_line_length_percent=10
    )
    
    # Uncomment to run batch analysis on a directory
    # analyzer.batch_analyze(
    #     "pdf_directory",
    #     min_text_length=50,
    #     min_line_count=3,
    #     min_line_length_percent=10
    # )