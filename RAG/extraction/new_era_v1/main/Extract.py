"""
integrated_pdf_extractor.py - Modul terintegrasi untuk ekstraksi teks PDF
Menggabungkan metode ekstraksi langsung, OCR, dan multimodal AI
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

class PDFExtractor:
    """Class untuk ekstraksi teks dari PDF dengan berbagai metode: langsung, OCR, dan multimodal AI."""
    
    def __init__(self, temp_dir="temporary_dir", dpi=300):
        """
        Inisialisasi PDFExtractor dengan konfigurasi default.
        
        Args:
            temp_dir (str): Direktori untuk menyimpan file sementara
            dpi (int): Resolusi DPI untuk render gambar PDF
        """
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Simpan parameter
        self.temp_dir = temp_dir
        self.dpi = dpi
        
        # Load environment variables untuk Google API (untuk metode multimodal)
        load_dotenv()
        self.GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
        
        # Configure Gemini API jika API key tersedia
        if self.GOOGLE_API_KEY:
            genai.configure(api_key=self.GOOGLE_API_KEY)
            
        # Pastikan direktori temporary ada
        self._ensure_directory_exists(self.temp_dir)
        
        self.logger.info("PDF Extractor diinisialisasi")
    
    def _ensure_directory_exists(self, directory_path):
        """Memastikan bahwa direktori yang ditentukan ada, membuat jika perlu."""
        os.makedirs(directory_path, exist_ok=True)
    
    def _render_pdf_page_to_image(self, pdf_path, page_num, output_dir, dpi=None):
        """
        Render halaman PDF ke file gambar dan mengembalikan path ke gambar.
        
        Args:
            pdf_path (str): Path ke file PDF
            page_num (int): Nomor halaman (mulai dari 1)
            output_dir (str): Direktori output untuk gambar
            dpi (int, optional): Resolusi DPI untuk render. Default menggunakan self.dpi
            
        Returns:
            str: Path ke file gambar yang dihasilkan
        """
        try:
            # Pastikan direktori output ada
            self._ensure_directory_exists(output_dir)
            
            # Gunakan DPI default jika tidak ditentukan
            if dpi is None:
                dpi = self.dpi
            
            # Buka dokumen PDF
            doc = fitz.open(pdf_path)
            
            # Convert to 0-based indexing for PyMuPDF
            pdf_page_index = page_num - 1
            
            if pdf_page_index < 0 or pdf_page_index >= len(doc):
                raise ValueError(f"Page {page_num} does not exist in PDF with {len(doc)} pages")
            
            # Ambil halaman
            page = doc[pdf_page_index]
            
            # Buat filename unik untuk menghindari overwrite
            image_filename = f"image_page_{page_num}_{uuid.uuid4().hex[:8]}.png"
            image_path = os.path.join(output_dir, image_filename)
            
            # Render halaman ke gambar dengan DPI yang ditentukan
            pix = page.get_pixmap(dpi=dpi)
            pix.save(image_path)
            
            self.logger.info(f"Rendered page {page_num} to {image_path}")
            
            return image_path
        
        except Exception as e:
            self.logger.error(f"Error rendering PDF page {page_num} to image: {str(e)}")
            raise
    
    def _clean_temporary_images(self):
        """Hapus semua file gambar di direktori sementara setelah pemrosesan selesai."""
        try:
            # Periksa apakah direktori ada
            if not os.path.exists(self.temp_dir):
                self.logger.info(f"Direktori sementara {self.temp_dir} tidak ada. Tidak ada yang dibersihkan.")
                return
                
            # Dapatkan daftar semua file di direktori
            image_extensions = ['.png', '.jpg', '.jpeg', '.tiff', '.bmp']
            file_count = 0
            
            for filename in os.listdir(self.temp_dir):
                file_path = os.path.join(self.temp_dir, filename)
                # Periksa apakah itu adalah file dan memiliki ekstensi gambar
                if os.path.isfile(file_path) and any(filename.lower().endswith(ext) for ext in image_extensions):
                    os.remove(file_path)
                    file_count += 1
                    
            self.logger.info(f"Cleaned up {file_count} temporary image files from {self.temp_dir}")
            
        except Exception as e:
            self.logger.error(f"Error cleaning temporary images: {str(e)}")
    
    def extract_with_direct_method(self, pdf_path, page_num, existing_result=None):
        """
        Ekstrak teks langsung dari PDF menggunakan PyPDF2 untuk halaman yang tidak memerlukan pemrosesan khusus.
        
        Args:
            pdf_path (str): Path ke file PDF
            page_num (int): Nomor halaman (mulai dari 1)
            existing_result (dict, optional): Hasil yang sudah ada untuk diperbarui
            
        Returns:
            dict: Hasil ekstraksi dengan metode langsung
        """
        start_time = time.time()
        
        # Buat struktur hasil jika tidak disediakan
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
            # Set metode ekstraksi dan inisialisasi content blocks
            result["extraction"] = {
                "method": "direct_extraction",
                "processing_time": None,
                "content_blocks": []
            }
        
        try:
            # Buka PDF dan ekstrak teks dari halaman tertentu
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                # Sesuaikan untuk indexing 0-based di PyPDF2
                pdf_page_index = page_num - 1
                
                if pdf_page_index < 0 or pdf_page_index >= len(pdf_reader.pages):
                    raise ValueError(f"Page {page_num} does not exist in PDF with {len(pdf_reader.pages)} pages")
                
                pdf_page = pdf_reader.pages[pdf_page_index]
                text = pdf_page.extract_text()
                
                # Buat satu blok konten untuk teks yang diekstrak
                if text and text.strip():
                    result["extraction"]["content_blocks"] = [{
                        "block_id": 1,
                        "type": "text",
                        "content": text.strip()
                    }]
                else:
                    result["extraction"]["content_blocks"] = [{
                        "block_id": 1,
                        "type": "text",
                        "content": "No text content could be extracted directly from this page."
                    }]
                    
        except Exception as e:
            # Tangani error ekstraksi
            result["extraction"]["content_blocks"] = [{
                "block_id": 1,
                "type": "text",
                "content": f"Error during direct extraction: {str(e)}"
            }]
        
        # Hitung dan catat waktu pemrosesan
        processing_time = time.time() - start_time
        result["extraction"]["processing_time"] = f"{processing_time:.2f} seconds"
        
        return result
    
    def extract_with_ocr_method(self, pdf_path, page_num, existing_result=None, dpi=None):
        """
        Ekstrak teks dari PDF menggunakan OCR untuk halaman yang membutuhkan pemrosesan OCR tetapi tidak memiliki format kompleks.
        
        Args:
            pdf_path (str): Path ke file PDF
            page_num (int): Nomor halaman (mulai dari 1)
            existing_result (dict, optional): Hasil yang sudah ada untuk diperbarui
            dpi (int, optional): Resolusi DPI untuk render. Default menggunakan self.dpi
            
        Returns:
            dict: Hasil ekstraksi dengan metode OCR
        """
        start_time = time.time()
        
        # Gunakan DPI default jika tidak ditentukan
        if dpi is None:
            dpi = self.dpi
        
        # Buat struktur hasil jika tidak disediakan
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
            # Set metode ekstraksi dan inisialisasi content blocks
            result["extraction"] = {
                "method": "ocr",
                "processing_time": None,
                "content_blocks": []
            }
        
        try:
            # Konversi halaman PDF ke gambar menggunakan PyMuPDF
            doc = fitz.open(pdf_path)
            
            # Sesuaikan untuk indexing 0-based
            pdf_page_index = page_num - 1
            
            if pdf_page_index < 0 or pdf_page_index >= len(doc):
                raise ValueError(f"Page {page_num} does not exist in PDF with {len(doc)} pages")
            
            page = doc[pdf_page_index]
            
            # Render halaman ke gambar dengan DPI yang ditentukan
            pix = page.get_pixmap(dpi=dpi)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            
            # Konversi ke RGB jika diperlukan
            if pix.n == 4:  # RGBA
                img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
            elif pix.n == 1:  # Grayscale
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
            
            # Konversi ke gambar PIL untuk Tesseract
            pil_img = Image.fromarray(img)
            
            # Lakukan OCR
            text = pytesseract.image_to_string(pil_img)
            
            # Untuk kasus OCR, hanya buat satu blok konten dengan semua teks
            if text and text.strip():
                result["extraction"]["content_blocks"] = [{
                    "block_id": 1,
                    "type": "text",
                    "content": text.strip()
                }]
            else:
                result["extraction"]["content_blocks"] = [{
                    "block_id": 1,
                    "type": "text",
                    "content": "No text content could be extracted via OCR from this page."
                }]
                    
        except Exception as e:
            # Tangani error ekstraksi
            result["extraction"]["content_blocks"] = [{
                "block_id": 1,
                "type": "text",
                "content": f"Error during OCR extraction: {str(e)}"
            }]
        
        # Hitung dan catat waktu pemrosesan
        processing_time = time.time() - start_time
        result["extraction"]["processing_time"] = f"{processing_time:.2f} seconds"
        
        return result
    
    def _create_multimodal_prompt(self, page_analysis):
        """
        Buat prompt yang sesuai untuk model AI multimodal berdasarkan analisis halaman.
        
        Args:
            page_analysis (dict): Hasil analisis halaman
            
        Returns:
            str: Prompt untuk model AI multimodal
        """
        # Prompt dasar dengan struktur konten yang diperluas
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
        
        # Kustomisasi prompt lebih lanjut berdasarkan karakteristik halaman spesifik jika diperlukan
        if page_analysis.get("ocr_status", False):
            prompt += "\nPerhatikan bahwa halaman ini mungkin mengandung teks hasil scan/OCR, pastikan untuk mengekstrak semua teks dengan tepat."
        
        if page_analysis.get("line_status", False):
            prompt += "\nPerhatikan garis-garis dan elemen visual untuk mengidentifikasi struktur tabel, diagram, atau flowchart dengan benar."
        
        return prompt
    
    def _process_with_multimodal_api(self, image_path, prompt):
        """
        Proses gambar menggunakan API Gemini multimodal.
        
        Args:
            image_path (str): Path ke file gambar
            prompt (str): Prompt untuk model AI
            
        Returns:
            dict: Hasil pemrosesan dari API multimodal
        """
        try:
            # Load gambar
            pil_image = Image.open(image_path)
            
            # Dapatkan model
            model = genai.GenerativeModel('gemini-2.0-flash')
            
            # Generate content
            response = model.generate_content([prompt, pil_image])
            
            # Ekstrak dan parse konten JSON
            response_text = response.text
            
            # Coba ekstrak JSON dari respons jika dibungkus dalam blok kode
            if "```json" in response_text and "```" in response_text:
                json_content = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_content = response_text.split("```")[1].split("```")[0].strip()
            else:
                json_content = response_text
            
            try:
                # Coba parse sebagai JSON
                content_json = json.loads(json_content)
                return content_json
            except json.JSONDecodeError:
                # Jika parsing JSON gagal, kembalikan sebagai raw text
                self.logger.warning("Failed to parse JSON from model response, returning raw text")
                return {
                    "content_blocks": [
                        {
                            "block_id": 1,
                            "type": "text",
                            "content": response_text
                        }
                    ]
                }
        
        except Exception as e:
            self.logger.error(f"Error processing image with multimodal API: {str(e)}")
            return {
                "content_blocks": [
                    {
                        "block_id": 1,
                        "type": "text",
                        "content": f"Error during multimodal processing: {str(e)}"
                    }
                ]
            }
    
    def extract_with_multimodal_method(self, pdf_path, page_num, existing_result=None, dpi=None):
        """
        Ekstrak konten dari PDF menggunakan AI multimodal untuk halaman dengan format kompleks.
        
        Args:
            pdf_path (str): Path ke file PDF
            page_num (int): Nomor halaman (mulai dari 1)
            existing_result (dict, optional): Hasil yang sudah ada untuk diperbarui
            dpi (int, optional): Resolusi DPI untuk render. Default menggunakan self.dpi
            
        Returns:
            dict: Hasil ekstraksi dengan metode multimodal
        """
        start_time = time.time()
        
        # Gunakan DPI default jika tidak ditentukan
        if dpi is None:
            dpi = self.dpi
        
        # Buat struktur hasil jika tidak disediakan
        if existing_result is None:
            # Default ke kedua flag adalah True karena ini adalah kasus fallback
            result = {
                "analysis": {
                    "ocr_status": True,
                    "line_status": True,
                    "ai_status": True
                },
                "extraction": {
                    "method": "multimodal_llm",
                    "model": "gemini-2.0-flash",
                    "processing_time": None,
                    "content_blocks": []
                }
            }
        else:
            result = existing_result
            # Set metode ekstraksi dan inisialisasi content blocks
            result["extraction"] = {
                "method": "multimodal_llm",
                "model": "gemini-2.0-flash",
                "processing_time": None,
                "content_blocks": []
            }
        
        try:
            # Render halaman PDF ke gambar
            image_path = self._render_pdf_page_to_image(pdf_path, page_num, self.temp_dir, dpi)
            
            # Buat prompt berdasarkan analisis halaman
            prompt = self._create_multimodal_prompt(result["analysis"])
            
            # Proses dengan API multimodal
            content_result = self._process_with_multimodal_api(image_path, prompt)
            
            # Perbarui hasil dengan blok konten
            if "content_blocks" in content_result:
                result["extraction"]["content_blocks"] = content_result["content_blocks"]
            else:
                # Fallback jika tidak mendapatkan blok konten
                result["extraction"]["content_blocks"] = [{
                    "block_id": 1,
                    "type": "text",
                    "content": "No structured content could be extracted via multimodal processing."
                }]
            
        except Exception as e:
            # Tangani error ekstraksi
            error_message = f"Error during multimodal extraction: {str(e)}"
            self.logger.error(error_message)
            
            result["extraction"]["content_blocks"] = [{
                "block_id": 1,
                "type": "text",
                "content": error_message
            }]
        
        # Hitung dan catat waktu pemrosesan
        processing_time = time.time() - start_time
        result["extraction"]["processing_time"] = f"{processing_time:.2f} seconds"
        
        return result
    
    def _initialize_output_data(self, pdf_path, analysis_data):
        """
        Inisialisasi struktur data output dengan metadata PDF dan data analisis.
        
        Args:
            pdf_path (str): Path ke file PDF
            analysis_data (dict): Data analisis untuk setiap halaman
            
        Returns:
            dict: Struktur data output yang diinisialisasi
        """
        # Dapatkan metadata PDF
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            total_pages = len(pdf_reader.pages)
        
        # Buat struktur output baru
        output_data = {
            "metadata": {
                "filename": Path(pdf_path).name,
                "total_pages": total_pages,
                "extraction_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "processing_time": "0 seconds"  # Akan diperbarui nanti
            },
            "pages": {}
        }
        
        # Inisialisasi struktur halaman dengan data analisis
        for page_num, page_analysis in analysis_data.items():
            output_data["pages"][page_num] = {
                "analysis": page_analysis
            }
        
        return output_data
    
    def process_pdf(self, pdf_path, analysis_json_path, output_json_path):
        """
        Proses halaman PDF menggunakan metode ekstraksi yang paling sesuai berdasarkan analisis.
        
        Args:
            pdf_path (str): Path ke file PDF
            analysis_json_path (str): Path ke file JSON analisis
            output_json_path (str): Path untuk menyimpan hasil ekstraksi
            
        Returns:
            dict: Hasil ekstraksi lengkap
        """
        # Pastikan direktori temp ada
        self._ensure_directory_exists(self.temp_dir)
        
        # Muat hasil analisis
        self.logger.info(f"Loading analysis data from {analysis_json_path}")
        with open(analysis_json_path, 'r', encoding='utf-8') as f:
            analysis_data = json.load(f)
        
        # Buat atau muat JSON output
        if os.path.exists(output_json_path):
            self.logger.info(f"Loading existing output data from {output_json_path}")
            with open(output_json_path, 'r', encoding='utf-8') as f:
                output_data = json.load(f)
        else:
            self.logger.info(f"Initializing new output data structure")
            output_data = self._initialize_output_data(pdf_path, analysis_data)
        
        # Waktu mulai proses
        start_time = time.time()
        processed_count = {"direct": 0, "ocr": 0, "multimodal": 0}
        
        # Proses semua halaman berdasarkan flag analisis
        for page_num, page_data in analysis_data.items():
            # Dapatkan flag tipe ekstraksi
            ocr_status = page_data.get("ocr_status", False)
            line_status = page_data.get("line_status", False)
            ai_status = page_data.get("ai_status", False)
            
            # Periksa apakah halaman ini sudah diproses
            page_processed = (
                page_num in output_data["pages"] and 
                "extraction" in output_data["pages"][page_num]
            )
            
            if page_processed:
                method = output_data["pages"][page_num]["extraction"]["method"]
                self.logger.info(f"Page {page_num} already processed with {method}. Skipping.")
                continue
            
            # Tentukan metode yang akan digunakan berdasarkan flag:
            existing_result = output_data["pages"].get(page_num, {"analysis": page_data})
            
            # Kasus 1: Ekstraksi langsung (tanpa OCR, tanpa garis, tanpa AI)
            if not ocr_status and not line_status and not ai_status:
                self.logger.info(f"Processing page {page_num} with direct extraction...")
                result = self.extract_with_direct_method(pdf_path, int(page_num), existing_result)
                processed_count["direct"] += 1
            
            # Kasus 2: OCR saja (OCR diperlukan, tetapi tidak ada struktur kompleks)
            elif ocr_status and not line_status and not ai_status:
                self.logger.info(f"Processing page {page_num} with OCR extraction...")
                result = self.extract_with_ocr_method(pdf_path, int(page_num), existing_result)
                processed_count["ocr"] += 1
            
            # Kasus 3 & 4: Multimodal (kasus kompleks dengan garis atau AI diperlukan)
            elif ((ocr_status and line_status and ai_status) or 
                  (not ocr_status and line_status and ai_status)):
                self.logger.info(f"Processing page {page_num} with multimodal extraction...")
                result = self.extract_with_multimodal_method(pdf_path, int(page_num), existing_result)
                processed_count["multimodal"] += 1
            
            # Kasus default: Gunakan multimodal sebagai fallback untuk kombinasi lainnya
            else:
                self.logger.info(f"Processing page {page_num} with multimodal extraction (fallback)...")
                result = self.extract_with_multimodal_method(pdf_path, int(page_num), existing_result)
                processed_count["multimodal"] += 1
            
            # Perbarui data output
            output_data["pages"][page_num] = result
        
        # Perbarui metadata
        total_processing_time = time.time() - start_time
        output_data["metadata"]["processing_time"] = f"{total_processing_time:.2f} seconds"
        
        # Simpan data output
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=4, ensure_ascii=False)
        
        # Bersihkan file sementara
        self._clean_temporary_images()
        
        # Log selesai
        total_processed = sum(processed_count.values())
        self.logger.info(f"PDF processing completed. Total pages processed: {total_processed}")
        self.logger.info(f"Direct: {processed_count['direct']}, OCR: {processed_count['ocr']}, Multimodal: {processed_count['multimodal']}")
        
        return output_data


# Contoh penggunaan
if __name__ == "__main__":
    # Inisialisasi extractor
    extractor = PDFExtractor(temp_dir="temporary_dir", dpi=300)
    
    # Example usage
    pdf_path = "ABF Indonesia Bond Index Fund.pdf"  # Update with your PDF path
    analysis_json_path = "sample.json"  # Path to analysis JSON
    output_json_path = "hasil_ekstraksi.json"  # Path to save extraction results
    
    # Proses PDF
    extractor.process_pdf(pdf_path, analysis_json_path, output_json_path)