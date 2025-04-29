"""
integrated_pdf_extractor.py - Modul terintegrasi untuk ekstraksi teks PDF
Menggabungkan metode ekstraksi langsung, OCR, dan multimodal AI dalam struktur kelas
Dengan kemampuan logging ke file
"""

import os
import json
import time
import datetime
import PyPDF2
import fitz  # PyMuPDF
import pytesseract
import numpy as np
import cv2
from pathlib import Path
from PIL import Image
import google.generativeai as genai
from dotenv import load_dotenv
import uuid
import logging

class PdfExtractorLogger:
    """Logger untuk mencatat aktivitas ekstraksi PDF ke file log yang sama."""
    def __init__(self, log_dir="logs"):
        os.makedirs(log_dir, exist_ok=True)
        log_filename = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_Extractor.log"
        self.LOG_FILE = os.path.join(log_dir, log_filename)

    def log(self, message, status="INFO"):
        """Menyimpan log ke file dengan format timestamp."""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [{status}] {message}\n"

        with open(self.LOG_FILE, "a", encoding="utf-8") as log_file:
            log_file.write(log_message)
        
        # Juga cetak ke console untuk memudahkan debug
        print(log_message.strip())

class IntegratedPdfExtractor:
    """
    Kelas untuk mengekstrak teks dari file PDF menggunakan beberapa metode:
    1. Ekstraksi langsung untuk halaman sederhana
    2. OCR untuk halaman dengan teks sebagai gambar
    3. Multimodal AI untuk halaman dengan struktur kompleks
    """
    
    def __init__(self, temp_dir="temporary_dir", dpi=300, log_dir="logs"):
        """
        Inisialisasi PDF Extractor
        
        Args:
            temp_dir (str): Direktori untuk menyimpan file temporer
            dpi (int): Resolusi untuk merender PDF ke gambar
            log_dir (str): Direktori untuk menyimpan file log
        """
        # Setup logging
        self._setup_logging(log_dir)
        
        # Setup parameter
        self.temp_dir = temp_dir
        self.dpi = dpi
        self.ensure_directory_exists(temp_dir)
        
        # Setup environment untuk Google API
        self._setup_google_api()
    
    def _setup_logging(self, log_dir):
        """Konfigurasi logging yang lebih komprehensif."""
        # Setup file logger
        self.file_logger = PdfExtractorLogger(log_dir)
        
        # Setup console logger
        self.console_logger = logging.getLogger(__name__)
        self.console_logger.setLevel(logging.INFO)
        
        # Create console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        
        # Create formatter and add it to the handlers
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        
        # Add the handlers to the logger
        self.console_logger.addHandler(ch)
    
    def log_info(self, message):
        """Log info message to both file and console."""
        self.file_logger.log(message, "INFO")
        self.console_logger.info(message)
    
    def log_warning(self, message):
        """Log warning message to both file and console."""
        self.file_logger.log(message, "WARNING")
        self.console_logger.warning(message)
    
    def log_error(self, message):
        """Log error message to both file and console."""
        self.file_logger.log(message, "ERROR")
        self.console_logger.error(message)
    
    def log_debug(self, message):
        """Log debug message to both file and console."""
        self.file_logger.log(message, "DEBUG")
        self.console_logger.debug(message)

    def _setup_google_api(self):
        """Setup API Google untuk metode multimodal."""
        load_dotenv()
        self.google_api_key = os.getenv('GOOGLE_API_KEY')
        
        # Configure Gemini API jika API key tersedia
        if self.google_api_key:
            genai.configure(api_key=self.google_api_key)
            self.log_info("Google Generative AI API berhasil dikonfigurasi")
        else:
            self.log_warning("Google API Key tidak ditemukan. Metode multimodal tidak akan berfungsi.")
    
    def ensure_directory_exists(self, directory_path):
        """Memastikan direktori yang ditentukan ada, membuat jika perlu."""
        try:
            os.makedirs(directory_path, exist_ok=True)
            self.log_debug(f"Memastikan direktori {directory_path} ada")
        except Exception as e:
            self.log_error(f"Gagal membuat direktori {directory_path}: {str(e)}")
            raise
    
    def render_pdf_page_to_image(self, pdf_path, page_num):
        """
        Merender halaman PDF ke file gambar dan mengembalikan path ke gambar.
        
        Args:
            pdf_path (str): Path ke file PDF
            page_num (int): Nomor halaman PDF (1-based indexing)
            
        Returns:
            str: Path ke file gambar yang dihasilkan
        """
        try:
            # Ensure output directory exists
            self.ensure_directory_exists(self.temp_dir)
            
            # Open PDF document
            doc = fitz.open(pdf_path)
            
            # Convert to 0-based indexing for PyMuPDF
            pdf_page_index = page_num - 1
            
            if pdf_page_index < 0 or pdf_page_index >= len(doc):
                error_msg = f"Page {page_num} does not exist in PDF with {len(doc)} pages"
                self.log_error(error_msg)
                raise ValueError(error_msg)
            
            # Get the page
            page = doc[pdf_page_index]
            
            # Create a unique filename to avoid overwriting
            image_filename = f"image_page_{page_num}_{uuid.uuid4().hex[:8]}.png"
            image_path = os.path.join(self.temp_dir, image_filename)
            
            # Render page to image with specified DPI
            pix = page.get_pixmap(dpi=self.dpi)
            pix.save(image_path)
            
            self.log_info(f"Rendered page {page_num} to {image_path}")
            
            return image_path
        
        except Exception as e:
            self.log_error(f"Error rendering PDF page {page_num} to image: {str(e)}")
            raise
    
    def clean_temporary_images(self):
        """Hapus semua file gambar di direktori sementara setelah pemrosesan selesai."""
        try:
            # Check if directory exists
            if not os.path.exists(self.temp_dir):
                self.log_info(f"Temporary directory {self.temp_dir} does not exist. Nothing to clean.")
                return
                
            # Get list of all files in directory
            image_extensions = ['.png', '.jpg', '.jpeg', '.tiff', '.bmp']
            file_count = 0
            
            for filename in os.listdir(self.temp_dir):
                file_path = os.path.join(self.temp_dir, filename)
                # Check if it's a file and has image extension
                if os.path.isfile(file_path) and any(filename.lower().endswith(ext) for ext in image_extensions):
                    os.remove(file_path)
                    file_count += 1
                    
            self.log_info(f"Cleaned up {file_count} temporary image files from {self.temp_dir}")
            
        except Exception as e:
            self.log_error(f"Error cleaning temporary images: {str(e)}")
    
    def extract_with_direct_method(self, pdf_path, page_num, existing_result=None):
        """
        Ekstraksi teks langsung dari PDF menggunakan PyPDF2 untuk halaman yang tidak memerlukan pemrosesan khusus.
        
        Args:
            pdf_path (str): Path ke file PDF
            page_num (int): Nomor halaman yang akan diekstrak
            existing_result (dict, optional): Hasil yang sudah ada untuk diperbarui
            
        Returns:
            dict: Hasil ekstraksi
        """
        start_time = time.time()
        
        # Create result structure if not provided
        if existing_result is None:
            result = {
                "analysis": {
                    "ocr_status": False,
                    "line_status": False,
                    "ai_status": False
                },
                "extraction": {
                    "method": "direct_extraction",
                    "processing_time": None,
                    "content_blocks": []
                }
            }
        else:
            result = existing_result
            # Set extraction method and initialize content blocks
            result["extraction"] = {
                "method": "direct_extraction",
                "processing_time": None,
                "content_blocks": []
            }
        
        try:
            # Open PDF and extract text from the specific page
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                # Adjust for 0-based indexing in PyPDF2
                pdf_page_index = page_num - 1
                
                if pdf_page_index < 0 or pdf_page_index >= len(pdf_reader.pages):
                    error_msg = f"Page {page_num} does not exist in PDF with {len(pdf_reader.pages)} pages"
                    self.log_error(error_msg)
                    raise ValueError(error_msg)
                
                pdf_page = pdf_reader.pages[pdf_page_index]
                text = pdf_page.extract_text()
                
                # Create a single content block for the extracted text, regardless of paragraphs
                if text and text.strip():
                    result["extraction"]["content_blocks"] = [{
                        "block_id": 1,
                        "type": "text",
                        "content": text.strip()
                    }]
                    self.log_info(f"Direct extraction successful for page {page_num}")
                else:
                    result["extraction"]["content_blocks"] = [{
                        "block_id": 1,
                        "type": "text",
                        "content": "No text content could be extracted directly from this page."
                    }]
                    self.log_warning(f"No text extracted directly from page {page_num}")
                    
        except Exception as e:
            # Handle extraction errors
            error_msg = f"Error during direct extraction: {str(e)}"
            result["extraction"]["content_blocks"] = [{
                "block_id": 1,
                "type": "text",
                "content": error_msg
            }]
            self.log_error(error_msg)
        
        # Calculate and record processing time
        processing_time = time.time() - start_time
        result["extraction"]["processing_time"] = f"{processing_time:.2f} seconds"
        self.log_debug(f"Direct extraction for page {page_num} took {processing_time:.2f} seconds")
        
        return result
    
    def extract_with_ocr_method(self, pdf_path, page_num, existing_result=None):
        """
        Ekstraksi teks dari PDF menggunakan OCR untuk halaman yang membutuhkan pemrosesan OCR 
        tapi tidak memiliki format kompleks.
        
        Args:
            pdf_path (str): Path ke file PDF
            page_num (int): Nomor halaman yang akan diekstrak
            existing_result (dict, optional): Hasil yang sudah ada untuk diperbarui
            
        Returns:
            dict: Hasil ekstraksi
        """
        start_time = time.time()
        
        # Create result structure if not provided
        if existing_result is None:
            result = {
                "analysis": {
                    "ocr_status": True,
                    "line_status": False,
                    "ai_status": False
                },
                "extraction": {
                    "method": "ocr",
                    "processing_time": None,
                    "content_blocks": []
                }
            }
        else:
            result = existing_result
            # Set extraction method and initialize content blocks if they don't exist
            result["extraction"] = {
                "method": "ocr",
                "processing_time": None,
                "content_blocks": []
            }
        
        try:
            # Convert PDF page to image using PyMuPDF
            doc = fitz.open(pdf_path)
            
            # Adjust for 0-based indexing
            pdf_page_index = page_num - 1
            
            if pdf_page_index < 0 or pdf_page_index >= len(doc):
                error_msg = f"Page {page_num} does not exist in PDF with {len(doc)} pages"
                self.log_error(error_msg)
                raise ValueError(error_msg)
            
            page = doc[pdf_page_index]
            
            # Render page to image at specified DPI
            pix = page.get_pixmap(dpi=self.dpi)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            
            # Convert to RGB if needed
            if pix.n == 4:  # RGBA
                img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
            elif pix.n == 1:  # Grayscale
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
            
            # Convert to PIL image for Tesseract
            pil_img = Image.fromarray(img)
            
            # Perform OCR
            text = pytesseract.image_to_string(pil_img)
            
            # For OCR case, we only create one content block with all the text
            # regardless of paragraphs or line breaks
            if text and text.strip():
                result["extraction"]["content_blocks"] = [{
                    "block_id": 1,
                    "type": "text",
                    "content": text.strip()
                }]
                self.log_info(f"OCR extraction successful for page {page_num}")
            else:
                result["extraction"]["content_blocks"] = [{
                    "block_id": 1,
                    "type": "text",
                    "content": "No text content could be extracted via OCR from this page."
                }]
                self.log_warning(f"No text extracted via OCR from page {page_num}")
                    
        except Exception as e:
            # Handle extraction errors
            error_msg = f"Error during OCR extraction: {str(e)}"
            result["extraction"]["content_blocks"] = [{
                "block_id": 1,
                "type": "text",
                "content": error_msg
            }]
            self.log_error(error_msg)
        
        # Calculate and record processing time
        processing_time = time.time() - start_time
        result["extraction"]["processing_time"] = f"{processing_time:.2f} seconds"
        self.log_debug(f"OCR extraction for page {page_num} took {processing_time:.2f} seconds")
        
        return result
    
    def create_multimodal_prompt(self, page_analysis):
        """
        Membuat prompt yang sesuai untuk model AI multimodal berdasarkan analisis halaman.
        
        Args:
            page_analysis (dict): Analisis halaman yang berisi status OCR, line, dan AI
            
        Returns:
            str: Prompt untuk model AI multimodal
        """
        # Base prompt with expanded content structure
        prompt = ("Analisis gambar ini secara detail dan ekstrak semua konten dengan mempertahankan struktur aslinya. "
                "Identifikasi dan berikan output dalam format berikut:\n\n"
                "1. Semua teks, termasuk heading, paragraf dan caption.\n"
                "2. Tabel lengkap dengan data seluruh baris dan kolom beserta judulnya.\n"
                "3. Grafik dan diagram, termasuk judul, label, nilai data, dan deskripsi visual.\n"
                "4. Flowchart dengan elemen-elemen dan hubungannya.\n"
                "5. Gambar dengan deskripsi dan caption (jika ada).\n\n"
                "Berikan output yang lengkap dan terstruktur dalam format JSON seperti contoh berikut:\n"
                "```json\n"
                "{\n"
                "  \"content_blocks\": [\n"
                "    {\n"
                "      \"block_id\": 1,\n"
                "      \"type\": \"text\",\n"
                "      \"content\": \"Teks lengkap dari bagian ini...\"\n"
                "    },\n"
                "    {\n"
                "      \"block_id\": 2,\n"
                "      \"type\": \"table\",\n"
                "      \"title\": \"Judul tabel (jika ada)\",\n"
                "      \"data\": [\n"
                "        {\"header_1\": \"nilai_baris_1_kolom_1\", \"header_2\": \"nilai_baris_1_kolom_2\"},\n"
                "        {\"header_1\": \"nilai_baris_2_kolom_1\", \"header_2\": \"nilai_baris_2_kolom_2\"}\n"
                "      ],\n"
                "      \"summary_table\": \"Deskripsi singkat tentang tabel\"\n"
                "    },\n"
                "    {\n"
                "      \"block_id\": 3,\n"
                "      \"type\": \"chart\",\n"
                "      \"chart_type\": \"line\",\n"
                "      \"title\": \"Judul grafik\",\n"
                "      \"data\": {\n"
                "        \"labels\": [\"label_1\", \"label_2\", \"label_3\"],\n"
                "        \"datasets\": [\n"
                "          {\n"
                "            \"label\": \"Dataset 1\",\n"
                "            \"values\": [5.2, 6.3, 7.1]\n"
                "          }\n"
                "        ]\n"
                "      },\n"
                "      \"summary_chart\": \"Deskripsi singkat tentang grafik\"\n"
                "    },\n"
                "    {\n"
                "      \"block_id\": 4,\n"
                "      \"type\": \"flowchart\",\n"
                "      \"title\": \"Judul flowchart\",\n"
                "      \"elements\": [\n"
                "        {\"type\": \"node\", \"id\": \"1\", \"text\": \"Langkah 1\", \"connects_to\": [\"2\"]},\n"
                "        {\"type\": \"node\", \"id\": \"2\", \"text\": \"Langkah 2\", \"connects_to\": [\"3\"]},\n"
                "        {\"type\": \"node\", \"id\": \"3\", \"text\": \"Langkah 3\", \"connects_to\": []}\n"
                "      ],\n"
                "      \"summary_flowchart\": \"Deskripsi singkat tentang flowchart\"\n"
                "    },\n"
                "    {\n"
                "      \"block_id\": 5,\n"
                "      \"type\": \"image\",\n"
                "      \"description_image\": \"Deskripsi detail tentang gambar\"\n"
                "    }\n"
                "  ]\n"
                "}\n"
                "```\n"
                "Pastikan mengekstrak SEMUA konten termasuk angka, teks lengkap, dan struktur dengan tepat sesuai format di atas.")
        
        # Customize prompt further based on specific page characteristics if needed
        if page_analysis.get("ocr_status", False):
            prompt += "\nPerhatikan bahwa halaman ini mungkin mengandung teks hasil scan/OCR, pastikan untuk mengekstrak semua teks dengan tepat."
        
        if page_analysis.get("line_status", False):
            prompt += "\nPerhatikan garis-garis dan elemen visual untuk mengidentifikasi struktur tabel, diagram, atau flowchart dengan benar."
        
        # self.log_debug(f"Created multimodal prompt: {prompt}")
        return prompt
    
    def process_with_multimodal_api(self, image_path, prompt):
        """
        Memproses gambar menggunakan API Gemini multimodal.
        
        Args:
            image_path (str): Path ke file gambar
            prompt (str): Prompt untuk model AI
            
        Returns:
            dict: Hasil pemrosesan multimodal
        """
        try:
            # Load the image
            pil_image = Image.open(image_path)
            
            # Get model
            model = genai.GenerativeModel('gemini-2.5-flash-preview-04-17')
            
            
            # Generate content
            response = model.generate_content([prompt, pil_image])
            
            
            # Extract and parse JSON content using the new function
            response_text = response.text
            parse_json = self.extract_json_content(response_text)

            # Need try divide and conquer?
            if parse_json != "try_divide_and_conquer":
                return parse_json
            
            else:
                segments = [
                    (0.0, 0.26),  # Segmen 1: 0% - 26% 
                    (0.16, 0.38),  # Segmen 2: 16% - 38%
                    (0.28, 0.50),   # Segmen 3: 28% - 50%
                    (0.40, 0.64),   # Segmen 4: 40% - 64%
                    (0.52, 0.76),   # Segmen 5: 52% - 76%
                    (0.66, 0.88),   # Segmen 6: 66% - 88%
                    (0.78, 1.00),   # Segmen 7: 78% - 100%
                ]

                print()
                print()
                print("========================")
                print()
                print("---")
                print(segments[0])
                print("===")
                print(segments[0][0])
                print(segments[0][1])
                print("---")
                print()

                # Segment 1
                segment1_path = self.crop_image_segment(image_path, segments[0])
                segment1_image = Image.open(segment1_path)
                segment1_prompt = f"""{prompt}
                CATATAN PENTING:
                - Ini adalah bagian pertama ({segments[0][0]*100:.0f}%-{segments[0][1]*100:.0f}%) dari dokumen
                - Ekstrak SEMUA informasi yang terlihat dalam format JSON
                - Jika tabel terpotong di bagian bawah, itu normal, ekstrak sebanyak yang terlihat
                """                

                response1 = model.generate_content([segment1_prompt, segment1_image])
                response1_text = response1.text
                parse1_json = self.extract_json_content(response1_text)
                
                print(parse1_json)
                print()
                print("========================")
                print()
                print()
                with open(("database/extracted_result/yuhuu1.json"), 'w', encoding='utf-8') as f:
                    json.dump(parse1_json, f, indent=4, ensure_ascii=False)




                print()
                print()
                print("========================")
                print()
                print("---")
                print(segments[1])
                print("===")
                print(segments[1][0])
                print(segments[1][1])
                print("---")
                print()

                # Segment 2
                segment2_path = self.crop_image_segment(image_path, segments[1])
                segment2_image = Image.open(segment2_path)
                segment2_prompt = f"""
                {prompt}
                
                CATATAN PENTING:
                - Ini adalah bagian 2 dari 7 ({segments[1][0]*100:.0f}%-{segments[1][1]*100:.0f}%) dari dokumen
                - Berikut hasil ekstraksi gabungan sejauh ini:
                {parse1_json}
                
                INSTRUKSI KHUSUS UNTUK PENGGABUNGAN:
                1. Identifikasi "OVERLAP BREAK" - baris terakhir yang sudah ada di JSON sebelumnya
                2. Mulai ekstraksi dari baris SETELAH OVERLAP BREAK
                3. Untuk TABEL:
                - Jika ini kelanjutan tabel yang sudah dimulai, gunakan struktur header yang sama
                - Tambahkan baris baru ke "rows" yang sudah ada
                - Jangan duplikasi baris yang sudah ada
                4. Untuk TEKS:
                - Lanjutkan dari konten yang sudah ada
                - Hindari pengulangan paragraf atau poin yang sama
                5. Hasilkan JSON lengkap termasuk semua data sebelumnya + data baru dari segmen ini

                INSTRUKSI KHUSUS UNTUK TABEL KOMPLEKS:
                - Prioritaskan struktur tabel yang konsisten
                - Jika header tabel sudah ada di JSON sebelumnya, gunakan struktur yang sama
                - Perhatikan nomor baris/urutan untuk memastikan kelengkapan
                - Jika menemukan tabel baru, buat blok baru dengan "type": "table"
                
                TEKNIK PENDETEKSIAN OVERLAP:
                - Bandingkan 2-3 baris pertama yang Anda lihat dengan JSON sebelumnya
                - OVERLAP BREAK adalah konten terakhir yang sama persis antara JSON dan gambar ini
                - Fokus pada angka, tanggal, atau frasa unik untuk memastikan deteksi yang akurat
                - Jangan ekstrak ulang data yang sudah ada di JSON sebelumnya
                
                PENTING: Hasilkan JSON LENGKAP sebagai output, termasuk semua data sebelumnya + data baru
                """

                response2 = model.generate_content([segment2_prompt, segment2_image])
                response2_text = response2.text
                parse2_json = self.extract_json_content(response2_text)

                print(parse2_json)
                print()
                print("========================")
                print()
                print()
                with open(("database/extracted_result/yuhuu2.json"), 'w', encoding='utf-8') as f:
                    json.dump(parse2_json, f, indent=4, ensure_ascii=False)





                print()
                print()
                print("========================")
                print()
                print("---")
                print(segments[2])
                print("===")
                print(segments[2][0])
                print(segments[2][1])
                print("---")
                print()

                # Segment 3
                segment3_path = self.crop_image_segment(image_path, segments[2])
                segment3_image = Image.open(segment3_path)
                segment3_prompt = f"""
                {prompt}
                
                CATATAN PENTING:
                - Ini adalah bagian 3 dari 7 ({segments[2][0]*100:.0f}%-{segments[2][1]*100:.0f}%) dari dokumen
                - Berikut hasil ekstraksi gabungan sejauh ini:
                {parse2_json}
                
                INSTRUKSI KHUSUS UNTUK PENGGABUNGAN:
                1. Identifikasi "OVERLAP BREAK" - baris terakhir yang sudah ada di JSON sebelumnya
                2. Mulai ekstraksi dari baris SETELAH OVERLAP BREAK
                3. Untuk TABEL:
                - Jika ini kelanjutan tabel yang sudah dimulai, gunakan struktur header yang sama
                - Tambahkan baris baru ke "rows" yang sudah ada
                - Jangan duplikasi baris yang sudah ada
                4. Untuk TEKS:
                - Lanjutkan dari konten yang sudah ada
                - Hindari pengulangan paragraf atau poin yang sama
                5. Hasilkan JSON lengkap termasuk semua data sebelumnya + data baru dari segmen ini

                INSTRUKSI KHUSUS UNTUK TABEL KOMPLEKS:
                - Prioritaskan struktur tabel yang konsisten
                - Jika header tabel sudah ada di JSON sebelumnya, gunakan struktur yang sama
                - Perhatikan nomor baris/urutan untuk memastikan kelengkapan
                - Jika menemukan tabel baru, buat blok baru dengan "type": "table"
                
                TEKNIK PENDETEKSIAN OVERLAP:
                - Bandingkan 2-3 baris pertama yang Anda lihat dengan JSON sebelumnya
                - OVERLAP BREAK adalah konten terakhir yang sama persis antara JSON dan gambar ini
                - Fokus pada angka, tanggal, atau frasa unik untuk memastikan deteksi yang akurat
                - Jangan ekstrak ulang data yang sudah ada di JSON sebelumnya
                
                PENTING: Hasilkan JSON LENGKAP sebagai output, termasuk semua data sebelumnya + data baru
                """

                response3 = model.generate_content([segment3_prompt, segment3_image])
                response3_text = response3.text
                parse3_json = self.extract_json_content(response3_text)

                print(parse3_json)
                print()
                print("========================")
                print()
                print()
                with open(("database/extracted_result/yuhuu3.json"), 'w', encoding='utf-8') as f:
                    json.dump(parse3_json, f, indent=4, ensure_ascii=False)
                




                print()
                print()
                print("========================")
                print()
                print("---")
                print(segments[3])
                print("===")
                print(segments[3][0])
                print(segments[3][1])
                print("---")
                print()

                # Segment 4
                segment4_path = self.crop_image_segment(image_path, segments[3])
                segment4_image = Image.open(segment4_path)
                segment4_prompt = f"""
                {prompt}
                
                CATATAN PENTING:
                - Ini adalah bagian 4 dari 7 ({segments[3][0]*100:.0f}%-{segments[3][1]*100:.0f}%) dari dokumen
                - Berikut hasil ekstraksi gabungan sejauh ini:
                {parse3_json}
                
                INSTRUKSI KHUSUS UNTUK PENGGABUNGAN:
                1. Identifikasi "OVERLAP BREAK" - baris terakhir yang sudah ada di JSON sebelumnya
                2. Mulai ekstraksi dari baris SETELAH OVERLAP BREAK
                3. Untuk TABEL:
                - Jika ini kelanjutan tabel yang sudah dimulai, gunakan struktur header yang sama
                - Tambahkan baris baru ke "rows" yang sudah ada
                - Jangan duplikasi baris yang sudah ada
                4. Untuk TEKS:
                - Lanjutkan dari konten yang sudah ada
                - Hindari pengulangan paragraf atau poin yang sama
                5. Hasilkan JSON lengkap termasuk semua data sebelumnya + data baru dari segmen ini

                INSTRUKSI KHUSUS UNTUK TABEL KOMPLEKS:
                - Prioritaskan struktur tabel yang konsisten
                - Jika header tabel sudah ada di JSON sebelumnya, gunakan struktur yang sama
                - Perhatikan nomor baris/urutan untuk memastikan kelengkapan
                - Jika menemukan tabel baru, buat blok baru dengan "type": "table"
                
                TEKNIK PENDETEKSIAN OVERLAP:
                - Bandingkan 2-3 baris pertama yang Anda lihat dengan JSON sebelumnya
                - OVERLAP BREAK adalah konten terakhir yang sama persis antara JSON dan gambar ini
                - Fokus pada angka, tanggal, atau frasa unik untuk memastikan deteksi yang akurat
                - Jangan ekstrak ulang data yang sudah ada di JSON sebelumnya
                
                PENTING: Hasilkan JSON LENGKAP sebagai output, termasuk semua data sebelumnya + data baru
                """

                response4 = model.generate_content([segment4_prompt, segment4_image])
                response4_text = response4.text
                print()
                print(response4_text)
                print()
                parse4_json = self.extract_json_content(response4_text)

                print(parse4_json)
                print()
                print("========================")
                print()
                print()
                with open(("database/extracted_result/yuhuu4.json"), 'w', encoding='utf-8') as f:
                    json.dump(parse4_json, f, indent=4, ensure_ascii=False)


                # # Segment 5
                # segment5_path = self.crop_image_segment(image_path, segments[4])
                # segment5_image = Image.open(segment5_path)
                # segment5_prompt = f"""
                # Gambar ini merupakan Potongan kelima dari sebuah gambar halaman
                # Potongan pertama sampai keempat telah dilakukan ekstraksi dan disimpan dalam bentuk dictionary sebagai berikut :
                # {parse4_json}

                # tugasmu adalah :
                # 1. melakukan ekstraksi gambar ini dengan aturan yang saya buat {prompt}
                # 2. identifikasi kesamaan pola atau data antara hasil Potongan pertama sampai keempat dengan hasil ekstraksi gambar potongan kelima ini
                # 3. jika ditemukan kesamaan pola atau data maka gabungkan sedemikian rupa sehingga menjadi data yang lengkap dengan acuan format pada aturan yang saya sebutkan pada poin nomer 1
                # """

                # response5 = model.generate_content([segment5_prompt, segment5_image])
                # response5_text = response5.text
                # parse5_json = self.extract_json_content(response5_text)


                # # Segment 6
                # segment6_path = self.crop_image_segment(image_path, segments[5])
                # segment6_image = Image.open(segment6_path)
                # segment6_prompt = f"""
                # Gambar ini merupakan Potongan keenam dari sebuah gambar halaman
                # Potongan pertama sampai kelima telah dilakukan ekstraksi dan disimpan dalam bentuk dictionary sebagai berikut :
                # {parse5_json}

                # tugasmu adalah :
                # 1. melakukan ekstraksi gambar ini dengan aturan yang saya buat {prompt}
                # 2. identifikasi kesamaan pola atau data antara hasil Potongan pertama sampai keenam dengan hasil ekstraksi gambar potongan keenam ini
                # 3. jika ditemukan kesamaan pola atau data maka gabungkan sedemikian rupa sehingga menjadi data yang lengkap dengan acuan format pada aturan yang saya sebutkan pada poin nomer 1
                # """

                # response6 = model.generate_content([segment6_prompt, segment6_image])
                # response6_text = response6.text
                # parse6_json = self.extract_json_content(response6_text)


                # # Segment 7
                # segment7_path = self.crop_image_segment(image_path, segments[6])
                # segment7_image = Image.open(segment7_path)
                # segment7_prompt = f"""
                # Gambar ini merupakan Potongan ketujuh dari sebuah gambar halaman
                # Potongan pertama sampai keenam telah dilakukan ekstraksi dan disimpan dalam bentuk dictionary sebagai berikut :
                # {parse6_json}

                # tugasmu adalah :
                # 1. melakukan ekstraksi gambar ini dengan aturan yang saya buat {prompt}
                # 2. identifikasi kesamaan pola atau data antara hasil Potongan pertama sampai keenam dengan hasil ekstraksi gambar potongan ketujuh ini
                # 3. jika ditemukan kesamaan pola atau data maka gabungkan sedemikian rupa sehingga menjadi data yang lengkap dengan acuan format pada aturan yang saya sebutkan pada poin nomer 1
                # """

                # response7 = model.generate_content([segment7_prompt, segment7_image])
                # response7_text = response7.text
                # parse7_json = self.extract_json_content(response7_text)


                # ### Gabung
                # gabung_prompt = f"""
                # saya memiliki sebuah gambar halaman yang telah saya lakukan ekstraksi.
                # ekstraksi yang saya lakukan saya bagi segmentasi sebanyak 7 segmen.
                # hal ini dilakukan karena halaman memiliki banyak tulisan berukuran kecil. 
                # adapun saya melakukan segmentasi dengan persentase dan data hasil ekstraksinya seperti ini :
                # Segmen 1: 0% - 26% 
                # Segmen 2: 16% - 38%
                # Segmen 3: 28% - 50%
                # Segmen 4: 40% - 64%
                # Segmen 5: 52% - 76%
                # Segmen 6: 66% - 88%
                # Segmen 7: 78% - 100%

                # jika diperhatikan maka antara setiap segmee terdsapat overlap
            
                # adapun data ekstraksi dari setiap segmentasi adalah sebagai berikut :
                # Segmen 1: {parse1_json}
                # Segmen 2: {parse2_json}
                # Segmen 3: {parse3_json}
                # Segmen 4: {parse4_json}
                # Segmen 5: {parse5_json}
                # Segmen 6: {parse6_json}
                # Segmen 7: {parse7_json}

                # Tugasmu adalah mengidentifikasi 
                # """



                return parse4_json
        
        except Exception as e:
            self.log_error(f"Error processing image with multimodal API: {str(e)}")
            return {
                "content_blocks": [
                    {
                        "block_id": 1,
                        "type": "text",
                        "content": f"Error during multimodal processing: {str(e)}"
                    }
                ]
            }

    def extract_json_content(self, response_text):
        """
        Extract and parse JSON content from a text response.
        Handles various formats including code blocks with or without language specifiers.
        """
        # Case 1: Check for ```json format first
        if "```json" in response_text and "```" in response_text.split("```json", 1)[1]:
            parts = response_text.split("```json", 1)[1].split("```", 1)
            json_content = parts[0].strip()
        
        # Case 2: Check for any code block format (```python, ```javascript, etc)
        elif "```" in response_text:
            # Get all content between first and second ``` markers
            code_blocks = response_text.split("```")
            if len(code_blocks) >= 3:  # Ensure we have opening and closing markers
                # If language specifier is present, remove it
                content = code_blocks[1].strip()
                if content.split("\n", 1)[0].strip() and not content.split("\n", 1)[0].startswith("{"):
                    # Remove the first line (language specifier)
                    json_content = content.split("\n", 1)[1].strip() if "\n" in content else ""
                else:
                    json_content = content
            else:
                json_content = response_text
        
        # Case 3: Look for JSON-like content with curly braces
        elif "{" in response_text and "}" in response_text:
            # Try to extract content between first { and last }
            try:
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                if start >= 0 and end > start:
                    json_content = response_text[start:end]
                else:
                    json_content = response_text
            except:
                json_content = response_text
        
        # Case 4: No special format detected
        else:
            json_content = response_text
        
        try:
            # Try to parse as JSON
            content_json = json.loads(json_content)
            self.log_info(f"Successfully parsed JSON from API response: {type(content_json)}")
            return content_json
        except json.JSONDecodeError as e:
            # Log the error details for debugging
            self.log_warning(f"JSON parsing error: {str(e)} in content: {json_content[:100]}...")
            
            # # If JSON parsing fails, return as raw text with structured format
            # return {
            #     "content_blocks": [
            #         {
            #             "block_id": 1,
            #             "type": "text",
            #             "content": response_text
            #         }
            #     ],
            #     "parsing_error": str(e)
            # }

            return "try_divide_and_conquer"
    
    def crop_image_segment(self, image_path, segment_range):
        """Crop image based on percentage range (start_percent, end_percent)"""
        start_percent, end_percent = segment_range
        img = Image.open(image_path)
        width, height = img.size
        
        top = int(height * start_percent)
        bottom = int(height * end_percent)
        
        segment = img.crop((0, top, width, bottom))
        segment_path = f"{image_path.split('.')[0]}_seg_{start_percent:.2f}_{end_percent:.2f}.png"
        segment.save(segment_path)
        
        return segment_path
    
    def extract_with_multimodal_method(self, pdf_path, page_num, existing_result=None):
        """
        Ekstraksi konten dari PDF menggunakan AI multimodal untuk halaman dengan format kompleks.
        
        Args:
            pdf_path (str): Path ke file PDF
            page_num (int): Nomor halaman yang akan diekstrak
            existing_result (dict, optional): Hasil yang sudah ada untuk diperbarui
            
        Returns:
            dict: Hasil ekstraksi
        """
        start_time = time.time()
        
        # Create result structure if not provided
        if existing_result is None:
            # Default to both flags being True since this is a fallback case
            result = {
                "analysis": {
                    "ocr_status": True,
                    "line_status": True,
                    "ai_status": True
                },
                "extraction": {
                    "method": "multimodal_llm",
                    "model": "gemini-2.5-flash-preview-04-17",
                    "processing_time": None,
                    "content_blocks": []
                }
            }
        else:
            result = existing_result
            # Set extraction method and initialize content blocks
            result["extraction"] = {
                "method": "multimodal_llm",
                "model": "gemini-2.5-flash-preview-04-17",
                "processing_time": None,
                "content_blocks": []
            }
        
        try:
            # Render PDF page to image
            image_path = self.render_pdf_page_to_image(pdf_path, page_num)
            
            # Create prompt based on page analysis
            prompt = self.create_multimodal_prompt(result["analysis"])
            
            # Process with multimodal API
            content_result = self.process_with_multimodal_api(image_path, prompt)

            print(content_result)
            
            # Update the result with content blocks
            if "content_blocks" in content_result:
                result["extraction"]["content_blocks"] = content_result["content_blocks"]
                self.log_info(f"Multimodal extraction successful for page {page_num}")
            else:
                # Fallback if we didn't get content blocks
                result["extraction"]["content_blocks"] = [{
                    "block_id": 1,
                    "type": "text",
                    "content": "No structured content could be extracted via multimodal processing."
                }]
                self.log_warning(f"No structured content from multimodal processing for page {page_num}")
            
        except Exception as e:
            # Handle extraction errors
            error_message = f"Error during multimodal extraction: {str(e)}"
            self.log_error(error_message)
            
            result["extraction"]["content_blocks"] = [{
                "block_id": 1,
                "type": "text",
                "content": error_message
            }]
        
        # Calculate and record processing time
        processing_time = time.time() - start_time
        result["extraction"]["processing_time"] = f"{processing_time:.2f} seconds"
        self.log_debug(f"Multimodal extraction for page {page_num} took {processing_time:.2f} seconds")
        
        return result
    
    def initialize_output_data(self, pdf_path, analysis_data):
        """
        Inisialisasi struktur data output dengan metadata PDF dan data analisis.
        
        Args:
            pdf_path (str): Path ke file PDF
            analysis_data (dict): Data analisis per halaman
            
        Returns:
            dict: Struktur output awal
        """
        # Get PDF metadata
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            total_pages = len(pdf_reader.pages)
        
        # Create new output structure
        output_data = {
            "metadata": {
                "filename": Path(pdf_path).name,
                "total_pages": total_pages,
                "extraction_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "processing_time": "0 seconds"  # Will be updated later
            },
            "pages": {}
        }
        
        # Initialize pages structure with analysis data
        for page_num, page_analysis in analysis_data.items():
            output_data["pages"][page_num] = {
                "analysis": page_analysis
            }
        
        self.log_info(f"Initialized output data structure for {Path(pdf_path).name}")
        return output_data
    
    def process_pdf(self, pdf_path, analysis_json_path, output_json_path):
        """
        Memproses halaman PDF menggunakan metode ekstraksi yang paling sesuai berdasarkan analisis.
        
        Args:
            pdf_path (str): Path ke file PDF
            analysis_json_path (str): Path ke file JSON analisis
            output_json_path (str): Path untuk menyimpan hasil ekstraksi
            
        Returns:
            dict: Hasil ekstraksi lengkap
        """
        # Ensure temp directory exists
        self.ensure_directory_exists(self.temp_dir)
        
        # Load analysis results
        self.log_info(f"Loading analysis data from {analysis_json_path}")
        with open(analysis_json_path, 'r', encoding='utf-8') as f:
            analysis_data = json.load(f)
        
        # Create or load output JSON
        if os.path.exists(output_json_path):
            self.log_info(f"Loading existing output data from {output_json_path}")
            with open(output_json_path, 'r', encoding='utf-8') as f:
                output_data = json.load(f)
        else:
            self.log_info(f"Initializing new output data structure")
            output_data = self.initialize_output_data(pdf_path, analysis_data)
        
        # Process start time
        start_time = time.time()
        processed_count = {"direct": 0, "ocr": 0, "multimodal": 0}
        
        # Process all pages based on analysis flags
        for page_num, page_data in analysis_data.items():
            # Get extraction type flags
            ocr_status = page_data.get("ocr_status", False)
            line_status = page_data.get("line_status", False)
            ai_status = page_data.get("ai_status", False)
            
            # Check if this page has already been processed
            page_processed = (
                page_num in output_data["pages"] and 
                "extraction" in output_data["pages"][page_num]
            )
            
            if page_processed:
                method = output_data["pages"][page_num]["extraction"]["method"]
                self.log_info(f"Page {page_num} already processed with {method}. Skipping.")
                continue
            
            # Decide which method to use based on flags:
            existing_result = output_data["pages"].get(page_num, {"analysis": page_data})
            
            # Case 1: Direct extraction (no OCR, no lines, no AI)
            if not ocr_status and not line_status and not ai_status:
                self.log_info(f"Processing page {page_num} with direct extraction...")
                result = self.extract_with_direct_method(pdf_path, int(page_num), existing_result)
                processed_count["direct"] += 1
            
            # Case 2: OCR only (OCR needed, but no complex structure)
            elif ocr_status and not line_status and not ai_status:
                self.log_info(f"Processing page {page_num} with OCR extraction...")
                result = self.extract_with_ocr_method(pdf_path, int(page_num), existing_result)
                processed_count["ocr"] += 1
            
            # Case 3 & 4: Multimodal (complex cases with lines or AI needed)
            elif ((ocr_status and line_status and ai_status) or 
                (not ocr_status and line_status and ai_status)):
                self.log_info(f"Processing page {page_num} with multimodal extraction...")
                result = self.extract_with_multimodal_method(pdf_path, int(page_num), existing_result)
                processed_count["multimodal"] += 1
            
            # Default case: Use multimodal as fallback for any other combination
            else:
                self.log_info(f"Processing page {page_num} with multimodal extraction (fallback)...")
                result = self.extract_with_multimodal_method(pdf_path, int(page_num), existing_result)
                processed_count["multimodal"] += 1
            
            # Update output data
            output_data["pages"][page_num] = result
        
        # Update metadata
        total_processing_time = time.time() - start_time
        output_data["metadata"]["processing_time"] = f"{total_processing_time:.2f} seconds"
        
        # Save output data
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=4, ensure_ascii=False)
        
        # Clean up temporary files
        self.clean_temporary_images()
        
        # Log completion
        total_processed = sum(processed_count.values())
        self.log_info(f"PDF processing completed. Total pages processed: {total_processed}")
        self.log_info(f"Direct: {processed_count['direct']}, OCR: {processed_count['ocr']}, Multimodal: {processed_count['multimodal']}")
        
        return output_data
    
    def process_multiple_pdfs(self, pdf_files, analysis_dir="hasil_analisis", output_dir="hasil_ekstraksi"):
        """
        Memproses banyak file PDF sekaligus.
        
        Args:
            pdf_files (list): List berisi [nama_file, path_file] untuk setiap file PDF
            analysis_dir (str): Direktori tempat file analisis JSON disimpan
            output_dir (str): Direktori untuk menyimpan hasil ekstraksi
            
        Returns:
            dict: Hasil ekstraksi untuk semua file PDF
        """
        # Pastikan direktori output ada
        self.ensure_directory_exists(output_dir)
        
        hasil_ekstraksi = {}
        
        for pdf_name, pdf_path in pdf_files:
            try:
                self.log_info(f"Memulai pemrosesan untuk {pdf_name}")
                
                # Path untuk file analisis dan output
                analysis_json_path = os.path.join(analysis_dir, f"{pdf_name}_analisis.json")
                output_json_path = os.path.join(output_dir, f"{pdf_name}_ekstraksi.json")
                
                # Proses PDF
                result = self.process_pdf(pdf_path, analysis_json_path, output_json_path)
                hasil_ekstraksi[pdf_name] = result
                
                self.log_info(f"Pemrosesan selesai untuk {pdf_name}")
                
            except Exception as e:
                self.log_error(f"Gagal memproses {pdf_name}: {str(e)}")
                hasil_ekstraksi[pdf_name] = {"error": str(e)}
        
        return hasil_ekstraksi

# Contoh penggunaan
if __name__ == "__main__":
    # Inisialisasi extractor
    extractor = IntegratedPdfExtractor(temp_dir="temporary_dir", dpi=300)
    
    # List file PDF untuk diproses [nama_file, path_file]
    pdf_files = [
        # ['ABF Indonesia Bond Index Fund', 'database/prospectus/ABF Indonesia Bond Index Fund.pdf']
        # ['Sucorinvest Money Market Fund', 'database/prospectus/Sucorinvest Money Market Fund.pdf']
        ['ABF latihan', 'database/prospectus/ABF latihan.pdf']
    ]
    
    # Proses semua PDF
    hasil = extractor.process_multiple_pdfs(
        pdf_files,
        analysis_dir="database/classified_result",
        output_dir="database/extracted_result"
    )
    
    # Output ringkasan
    print("\nRingkasan Hasil Ekstraksi:")
    for pdf_name, result in hasil.items():
        if "error" in result:
            print(f"- {pdf_name}: Error - {result['error']}")
        else:
            total_pages = result['metadata']['total_pages']
            print(f"- {pdf_name}: {total_pages} halaman diproses")