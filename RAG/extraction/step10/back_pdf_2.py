import fitz
import numpy as np
import cv2
from pathlib import Path
from typing import List, Tuple, Dict, Union, Optional
import os
import json
from PIL import Image
import io
import base64
from unstructured.partition.pdf import partition_pdf
import pytesseract

class PDFExtractor:
    def __init__(
        self,
        pdf_path: str,
        output_dir: str = "output",
        min_line_length: int = 200,
        line_thickness: int = 2,
        header_threshold: float = 50,
        footer_threshold: float = 50,
        scan_header_threshold: float = 100,
        scan_footer_threshold: float = 100,
        min_lines_per_page: int = 2,
        api_provider: str = "google",
        save_images: bool = True,  # Opsi untuk menyimpan gambar fisik
        save_pdf_splits: bool = True,  # Opsi untuk menyimpan split PDF
        draw_line_highlights: bool = True,  # Opsi untuk menggambar garis highlight
        cleanup_temp_files: bool = True  # Opsi untuk membersihkan file sementara
    ):
        self.pdf_path = pdf_path
        self.output_dir = output_dir
        self.min_line_length = min_line_length
        self.line_thickness = line_thickness
        self.header_threshold = header_threshold
        self.footer_threshold = footer_threshold
        self.scan_header_threshold = scan_header_threshold
        self.scan_footer_threshold = scan_footer_threshold
        self.min_lines_per_page = min_lines_per_page
        self.api_provider = api_provider
        self.save_images = save_images
        self.save_pdf_splits = save_pdf_splits
        self.draw_line_highlights = draw_line_highlights
        self.cleanup_temp_files = cleanup_temp_files
        
        # Buat direktori output
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        self.img_output_dir = Path(output_dir) / "images"
        self.img_output_dir.mkdir(parents=True, exist_ok=True)
        
        # Buat direktori untuk PDF splits
        self.pdf_output_dir = Path(output_dir) / "pdf_splits"
        self.pdf_output_dir.mkdir(parents=True, exist_ok=True)
        
        # Inisialisasi objek dokumen
        self.doc = fitz.open(pdf_path)
        self.total_pages = len(self.doc)
        
        # Struktur data hasil
        self.result = {
            "metadata": {
                "filename": os.path.basename(pdf_path),
                "total_pages": self.total_pages,
                "extraction_method": None
            },
            "pages": []
        }
        
        # Untuk melacak grup halaman berurutan dengan garis
        self.current_table_group = []
        self.table_groups = []
        self.pages_with_tables = []
        # Menyimpan gambar yang sudah diproses (hanya untuk deteksi garis)
        self.page_images = {}

    def save_pdf_split(self, page_group: List[int], group_id: str) -> str:
        """
        Menyimpan halaman-halaman tertentu dari PDF sebagai file PDF baru.
        
        Args:
            page_group: List nomor halaman yang akan disimpan (berbasis indeks 0)
            group_id: Identifier untuk grup halaman
            
        Returns:
            Path file PDF yang disimpan atau None jika opsi dinonaktifkan
        """
        # Jika opsi save_pdf_splits dinonaktifkan, kembalikan None
        if not self.save_pdf_splits:
            print(f"  * Opsi save_pdf_splits dinonaktifkan, tidak menyimpan split PDF")
            return None
            
        output_filename = f"split_{os.path.basename(self.pdf_path).replace('.pdf', '')}_{group_id}.pdf"
        output_path = os.path.join(self.pdf_output_dir, output_filename)
        
        # Buat dokumen baru
        new_doc = fitz.open()
        
        try:
            # Salin halaman yang diinginkan ke dokumen baru
            for page_num in page_group:
                new_doc.insert_pdf(self.doc, from_page=page_num, to_page=page_num)
            
            # Simpan dokumen baru
            new_doc.save(output_path)
            print(f"  * PDF split disimpan: {output_path}")
            
            return output_path
        except Exception as e:
            print(f"  * Error saat menyimpan PDF split: {e}")
            return None
        finally:
            # Tutup dokumen
            new_doc.close()
    
    def process(self):
        """
        Proses utama untuk ekstraksi dokumen PDF.
        """
        print(f"Memulai proses ekstraksi PDF: {self.pdf_path}")
        print(f"Total halaman: {self.total_pages}")
        
        for page_num in range(self.total_pages):
            print(f"\nMemproses halaman {page_num + 1}...")
            page_data = self.process_page(page_num)
            self.result["pages"].append(page_data)
            
            # Jika halaman memiliki tabel dan belum ada grup tabel aktif
            if page_data["has_table"] and not self.current_table_group:
                self.current_table_group = [page_num]
                self.pages_with_tables.append(page_num)
            
            # Jika halaman memiliki tabel dan melanjutkan grup tabel sebelumnya
            elif page_data["has_table"] and self.current_table_group and page_num == self.current_table_group[-1] + 1:
                self.current_table_group.append(page_num)
                self.pages_with_tables.append(page_num)
            
            # Jika halaman tidak memiliki tabel tetapi ada grup tabel aktif
            elif not page_data["has_table"] and self.current_table_group:
                # Selesaikan grup tabel ini
                self.table_groups.append(self.current_table_group.copy())
                
                # Proses ekstraksi tabel untuk grup ini
                self.extract_tables_from_group(self.current_table_group)
                
                # Reset grup tabel
                self.current_table_group = []
        
        # Periksa jika masih ada grup tabel aktif di akhir dokumen
        if self.current_table_group:
            self.table_groups.append(self.current_table_group.copy())
            self.extract_tables_from_group(self.current_table_group)
        
        # Simpan hasil ekstraksi
        self.save_results()

        # Bersihkan file sementara di akhir proses
        try:
            self.cleanup()
        except Exception as e:
            print(f"Peringatan: Gagal membersihkan file sementara: {e}")
        
        print("\nProses ekstraksi selesai!")
        return self.result
    
    def process_page(self, page_num: int) -> Dict:
        """
        Memproses satu halaman PDF dan mengembalikan data ekstraksi.
        """
        page = self.doc[page_num]
        page_width, page_height = page.rect.width, page.rect.height
        rotation = page.rotation
        
        # Cek jenis dokumen: asli atau scan
        text = page.get_text()
        is_scanned = len(text.strip()) < 50  # Anggap scan jika sedikit teks
        
        print(f"- Tipe halaman: {'Hasil scan' if is_scanned else 'Dokumen asli'}")
        print(f"- Rotasi halaman: {rotation} derajat")
        
        # Penentuan threshold header/footer
        current_header = self.scan_header_threshold if is_scanned else self.header_threshold
        current_footer = self.scan_footer_threshold if is_scanned else self.footer_threshold
        
        # Persiapan image
        zoom = 2
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        
        # Simpan gambar asli
        original_img = img.copy()
        
        # Konversi ke grayscale
        if img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2GRAY)
            original_img = cv2.cvtColor(original_img, cv2.COLOR_RGBA2BGR)
        elif img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            original_img = cv2.cvtColor(original_img, cv2.COLOR_RGB2BGR)
        
        # Rotasi gambar jika perlu
        if rotation == 180:
            img = cv2.rotate(img, cv2.ROTATE_180)
            original_img = cv2.rotate(original_img, cv2.ROTATE_180)
        
        # Deteksi garis
        has_table, lines = self.detect_table_lines(
            img, 
            original_img, 
            zoom, 
            page_width, 
            page_height, 
            current_header, 
            current_footer,
            rotation
        )
        
        # Simpan gambar jika halaman memiliki tabel
        if has_table:
            self.page_images[page_num] = original_img
        
        # Ekstrak teks jika tidak ada tabel terdeteksi
        page_text = None
        if not has_table:
            page_text = self.extract_text_from_page(page_num, is_scanned)
        
        # Kembalikan data halaman
        return {
            "page_num": page_num + 1,
            "is_scanned": is_scanned,
            "rotation": rotation,
            "has_table": has_table,
            "text": page_text if not has_table else None,  # Teks disimpan sebagai list string
            "table_data": None  # Akan diisi nanti oleh API LLM jika memiliki tabel
        }
    
    def detect_table_lines(
        self, 
        img: np.ndarray, 
        original_img: np.ndarray,
        zoom: int, 
        page_width: float, 
        page_height: float,
        header_threshold: float,
        footer_threshold: float,
        rotation: int
    ) -> Tuple[bool, List[Dict]]:
        """
        Deteksi garis pada gambar dan tentukan apakah halaman memiliki tabel.
        """
        # Threshold untuk membuat gambar biner
        _, binary = cv2.threshold(img, 200, 255, cv2.THRESH_BINARY_INV)
        
        # Kernel morfologi untuk deteksi garis horizontal
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (self.min_line_length, self.line_thickness))
        detect_horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, self.line_thickness))
        detect_horizontal = cv2.dilate(detect_horizontal, horizontal_kernel, iterations=1)
        
        # Deteksi kontur
        contours, _ = cv2.findContours(detect_horizontal, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        print(f"- Total garis terdeteksi awal: {len(contours)}")
        
        # Proses eliminasi garis
        valid_lines = []
        eliminated_by_length = 0
        eliminated_by_position = 0
        
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            y_pdf = y / zoom
            
            # Check panjang minimum
            if w < self.min_line_length:
                eliminated_by_length += 1
                continue
                
            # Check posisi header/footer
            if (y_pdf < header_threshold) or (y_pdf > page_height - footer_threshold):
                eliminated_by_position += 1
                continue
            
            # Tambahkan ke garis valid dengan menyesuaikan posisi berdasarkan rotasi
            x1 = x / zoom
            y1 = y / zoom - 0.5
            x2 = (x + w) / zoom
            y2 = y / zoom + 0.5
            
            if rotation == 90:
                x1, y1, x2, y2 = y1, page_width - x2, y2, page_width - x1
            elif rotation == 180:
                x1, y1, x2, y2 = page_width - x2, page_height - y2, page_width - x1, page_height - y1
            elif rotation == 270:
                x1, y1, x2, y2 = page_height - y2, x1, page_height - y1, x2
            
            valid_lines.append({
                'y_position': y / zoom,
                'x_min': x1,
                'x_max': x2
            })
        
        print("- Hasil eliminasi:")
        print(f"  * Eliminasi karena panjang < {self.min_line_length}: {eliminated_by_length} garis")
        print(f"  * Eliminasi karena posisi di header/footer: {eliminated_by_position} garis")
        print(f"  * Garis valid setelah eliminasi: {len(valid_lines)}")
        
        # Tentukan apakah halaman memiliki tabel berdasarkan jumlah garis valid
        has_table = len(valid_lines) >= self.min_lines_per_page
    
        if not has_table:
            print(f"  * Halaman tidak memiliki tabel: jumlah garis valid ({len(valid_lines)}) < minimum ({self.min_lines_per_page})")
        else:
            print(f"  * Halaman memiliki tabel: {len(valid_lines)} garis terdeteksi")
            
            # Draw lines on image only if option is enabled
            if self.draw_line_highlights:
                for line in valid_lines:
                    x1, y1 = int(line['x_min'] * zoom), int(line['y_position'] * zoom)
                    x2, y2 = int(line['x_max'] * zoom), int(line['y_position'] * zoom)
                    cv2.line(original_img, (x1, y1), (x2, y2), (0, 255, 255), 2)
        
        return has_table, valid_lines
    
    def extract_text_from_page(self, page_num: int, is_scanned: bool) -> list:
        """
        Ekstrak teks dari halaman PDF berdasarkan jenisnya (scan atau asli)
        Mengembalikan list string, di mana setiap elemen mewakili satu baris teks.
        """
        page = self.doc[page_num]
        
        if not is_scanned:
            # Untuk dokumen asli, gunakan PyMuPDF
            print(f"- Mengekstrak teks dari dokumen asli")
            text = page.get_text("text")  # Menggunakan "text" untuk mendapatkan teks per baris
            
            # Split teks menjadi list berdasarkan newline
            text_lines = text.split('\n')
            
            return text_lines
        else:
            # Untuk dokumen hasil scan, gunakan OCR
            print(f"- Mengekstrak teks dari dokumen scan dengan OCR")
            try:
                # Coba menggunakan unstructured
                temp_dir = os.path.join(self.output_dir, "temp")
                Path(temp_dir).mkdir(parents=True, exist_ok=True)
                
                # Save temporary PDF with just this page
                temp_pdf = os.path.join(temp_dir, f"page_{page_num+1}.pdf")
                temp_doc = fitz.open()
                temp_doc.insert_pdf(self.doc, from_page=page_num, to_page=page_num)
                temp_doc.save(temp_pdf)
                temp_doc.close()
                
                try:
                    elements = partition_pdf(
                        filename=temp_pdf,
                        strategy="hi_res",
                        infer_table_structure=True,
                        temp_dir=temp_dir,
                        use_ocr=True,
                        ocr_languages="eng",  # Sesuaikan dengan bahasa dokumen
                        ocr_mode="entire_page"
                    )
                    
                    # Gabungkan semua teks dari elements
                    text = "\n".join([str(element) for element in elements])
                    
                    # Jika teks masih kosong atau terlalu pendek, coba dengan tesseract langsung
                    if len(text.strip()) < 50:
                        raise Exception("Hasil unstructured terlalu sedikit, coba dengan tesseract")
                    
                    # Split teks menjadi list berdasarkan newline
                    text_lines = text.split('\n')
                    
                    return text_lines
                finally:
                    # Bersihkan file sementara jika opsi diaktifkan
                    if self.cleanup_temp_files and os.path.exists(temp_pdf):
                        os.remove(temp_pdf)
                        print(f"  * File sementara {temp_pdf} dibersihkan")
                    
            except Exception as e:
                print(f"  * Gagal menggunakan unstructured: {e}")
                print(f"  * Mencoba dengan tesseract langsung")
                
                # Gunakan pytesseract sebagai fallback
                zoom = 2
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                text = pytesseract.image_to_string(img, lang='eng')  # Sesuaikan bahasa
                
                # Split teks menjadi list berdasarkan newline
                text_lines = text.split('\n')
                
                return text_lines
    
    def extract_tables_from_group(self, page_group: List[int]):
        """
        Ekstrak tabel dari sekelompok halaman menggunakan API LLM
        """
        if not page_group:
            return
                
        group_start = page_group[0] + 1  # +1 untuk tampilan
        group_end = page_group[-1] + 1
        
        group_id = f"{group_start}" if len(page_group) == 1 else f"{group_start}-{group_end}"
        print(f"\nMengekstrak tabel dari halaman {group_id} menggunakan API {self.api_provider}...")
        
        # Simpan halaman sebagai split PDF
        pdf_split_path = self.save_pdf_split(page_group, group_id)
        
        # Jika PDF split berhasil disimpan atau dibuat, gunakan API untuk ekstraksi
        if pdf_split_path:
            # Jika gambar sudah diproses dan opsi save_images diaktifkan, simpan gambar untuk visualisasi
            if self.save_images:
                for i, page_num in enumerate(page_group):
                    if page_num in self.page_images:
                        img_filename = f"table_pages_{group_id}_part{i+1}.png"
                        img_path = os.path.join(self.img_output_dir, img_filename)
                        cv2.imwrite(img_path, self.page_images[page_num])
                        print(f"  * Gambar untuk visualisasi disimpan: {img_path}")
        
            # Panggil API LLM dengan PDF split
            api_result = self.call_llm_api_with_pdf(pdf_split_path, page_group)
            
            # Update hasil untuk setiap halaman dalam grup
            for page_num in page_group:
                page_idx = page_num  # Indeks dalam self.result["pages"]
                # Cari halaman yang sesuai
                for idx, page_data in enumerate(self.result["pages"]):
                    if page_data["page_num"] == page_num + 1:
                        page_idx = idx
                        break
                
                # Update data tabel
                self.result["pages"][page_idx]["table_data"] = api_result.get(f"page_{page_num+1}", {})
                
                # Tambahkan informasi path split PDF ke hasil
                self.result["pages"][page_idx]["pdf_split_path"] = pdf_split_path
        else:
            print(f"  * Tidak dapat membuat atau menyimpan PDF split untuk halaman {group_id}")
    
    def call_llm_api_with_pdf(self, pdf_path: str, page_group: List[int]) -> Dict:
        """
        Panggil API dengan file PDF yang sudah di-split
        
        Args:
            pdf_path: Path ke file PDF split
            page_group: List nomor halaman yang ada dalam PDF split (berbasis indeks 0)
            
        Returns:
            Dict hasil ekstraksi dari API
        """
        print(f"Memanggil API {self.api_provider} untuk ekstraksi tabel dari PDF split...")
        print(f"PDF path: {pdf_path}")
        print(f"Jumlah halaman: {len(page_group)}")
        
        try:
            import google.generativeai as genai
            from dotenv import load_dotenv
            import mimetypes
            
            # Load environment variables
            load_dotenv()
            
            # Get API key from environment variables
            GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
            if not GOOGLE_API_KEY:
                raise ValueError("Google API Key tidak ditemukan. Pastikan variabel GOOGLE_API_KEY ada di file .env")
            
            # Configure API key
            genai.configure(api_key=GOOGLE_API_KEY)
            
            # Initialize model
            model = genai.GenerativeModel('gemini-2.0-flash')
            
            # Determine MIME type
            mime_type, _ = mimetypes.guess_type(pdf_path)
            if not mime_type:
                mime_type = 'application/pdf'  # Default if not detected
            
            # Read the PDF file
            with open(pdf_path, "rb") as pdf_file:
                pdf_data = pdf_file.read()
            
            # Prepare content with PDF and prompt
            content = [
                """
                Anda adalah sistem ahli dalam mengekstrak informasi dari dokumen PDF. Dokumen yang diberikan dapat berisi teks biasa, tabel, dan/atau flowchart.
                Tugas Anda adalah menganalisis dokumen dan mengekstrak informasi yang terkandung di dalamnya dalam format JSON.

                1. **Analisis Konten:** Identifikasi *semua* jenis konten yang ada dalam dokumen. Sebuah dokumen dapat berisi:
                    *   Teks biasa (text)
                    *   Tabel (table)
                    *   Flowchart (flowchart)
                    *   Kombinasi dari jenis-jenis konten tersebut

                2. **Ekstraksi Informasi:** Untuk *setiap* jenis konten yang teridentifikasi, lakukan langkah-langkah berikut:

                    *   **Ekstraksi Teks (jika ada):** Ekstrak semua teks yang dapat dibaca dan simpan dalam format berikut:
                        ```json
                        {
                        "type": "text",
                        "page_number": [Nomor Halaman (jika diketahui, jika tidak, biarkan kosong)],
                        "text": [
                            "Baris 1 teks",
                            "Baris 2 teks",
                            ...
                        ]
                        }
                        ```
                        Setiap baris teks harus menjadi elemen terpisah dalam array "text".

                    *   **Ekstraksi Tabel (jika ada):** Ekstrak struktur dan data tabel dan simpan dalam format berikut:
                        ```json
                        {
                        "type": "table",
                        "page_number": [Nomor Halaman (jika diketahui, jika tidak, biarkan kosong)],
                        "title": [Judul tabel (jika ada, jika tidak, biarkan kosong)],
                        "description": [Deskripsi singkat tabel (jika ada, jika tidak, biarkan kosong)],
                        "headers": [
                            "Header Kolom 1",
                            "Header Kolom 2",
                            ...
                        ],
                        "rows": [
                            {
                            "Header Kolom 1": "Data baris 1 kolom 1",
                            "Header Kolom 2": "Data baris 1 kolom 2",
                            ...
                            },
                            {
                            "Header Kolom 1": "Data baris 2 kolom 1",
                            "Header Kolom 2": "Data baris 2 kolom 2",
                            ...
                            }
                        ],
                        "footer": [Catatan kaki tabel (jika ada, jika tidak, biarkan kosong)],
                        "is_continued": [true jika tabel berlanjut dari halaman sebelumnya atau ke halaman berikutnya, false jika tidak]
                        }
                        ```
                        *   `is_continued`:  **Sangat penting.** Setel ke `true` jika tabel ini adalah kelanjutan dari tabel di halaman sebelumnya, atau jika tabel ini berlanjut ke halaman berikutnya. Setel ke `false` jika ini adalah tabel lengkap dalam satu gambar.

                    *   **Ekstraksi Flowchart (jika ada):** Ekstrak elemen-elemen flowchart dan simpan dalam format berikut:
                        ```json
                        {
                        "type": "flowchart",
                        "page_number": [Nomor Halaman (jika diketahui, jika tidak, biarkan kosong)],
                        "title": [Judul flowchart (jika ada, jika tidak, biarkan kosong)],
                        "structured_data": [
                            {
                            "entity": [Nama Entitas],
                            "input": [Input (jika ada)],
                            "processes": [
                                {
                                "name": [Nama Proses],
                                "description": [Deskripsi Proses]
                                }
                            ],
                            "description": [Deskripsi Entitas]
                            }
                        ],
                        "narrative": [Ringkasan naratif dari flowchart]
                        }
                        ```

                3. **Output:**  Keluarkan *semua* informasi yang diekstraksi sebagai *satu* array JSON. Setiap elemen dalam array mewakili satu bagian konten (teks, tabel, atau flowchart) yang diekstraksi dari dokumen. Pastikan JSON tersebut valid dan dapat diurai dengan benar.

                **Instruksi Tambahan:**

                *   Fokus pada akurasi ekstraksi data.
                *   Jika Anda tidak yakin dengan tipe konten atau bagaimana cara mengekstrak informasi, berikan output JSON dengan bidang yang sesuai sebanyak mungkin dan sertakan catatan di bagian "extraction_notes" (yang belum ada di contoh format, mohon ditambahkan ke semua format data).
                *   **Prioritaskan deteksi *semua* elemen yang ada di dokumen.** Jika dokumen berisi teks *dan* tabel, hasilkan *dua* objek JSON terpisah: satu untuk teks, dan satu lagi untuk tabel.
                *   Jika ada teks di luar tabel atau flowchart, identifikasi apakah teks tersebut merupakan judul/catatan kaki yang terkait dengan tabel/flowchart. Jika ya, gabungkan informasi tersebut ke dalam objek JSON tabel/flowchart yang sesuai. Jika tidak, perlakukan teks tersebut sebagai elemen "text" yang terpisah.
                *   Jika dokumen berisi *sebagian* tabel atau flowchart, usahakan untuk mengekstrak informasi sebanyak mungkin dan gunakan `is_continued: true` pada tabel yang terpotong.
                """
                ,
                {"mime_type": mime_type, "data": pdf_data},
                "Ekstrak semua tabel dan informasi penting dari dokumen PDF ini, berikan output dalam format JSON yang valid."
            ]

            # Call the API
            response = model.generate_content(content)
            
            # Process the response
            response_text = response.text
            print(f"API Response received. Length: {len(response_text)} characters")

            print()
            print("---")
            print(len(response_text))
            print(type(response_text))
            print("---")
            print(response_text)
            print("---")
            print()
            
            # Parse the JSON response
            parsed_result = self._parse_potentially_incomplete_json(response_text)
            
            # Structure the result by page
            result = {}
            
            # Check if the response has page-based structure
            if isinstance(parsed_result, dict) and any(key.startswith('page_') for key in parsed_result.keys()):
                # The response already has the correct structure
                result = parsed_result
            elif isinstance(parsed_result, dict) and 'pages' in parsed_result:
                # Convert from {'pages': [{...page1...}, {...page2...}]} format to page_N format
                for i, page_data in enumerate(parsed_result['pages']):
                    page_num = page_data.get('page_num', i + 1)
                    result[f'page_{page_num}'] = page_data
            else:
                # Create a structured response for each page
                for i, page_num in enumerate(page_group):
                    actual_page_num = page_num + 1
                    result[f'page_{actual_page_num}'] = {
                        "table_type": "extracted_table",
                        "extracted_data": parsed_result if isinstance(parsed_result, list) else [parsed_result]
                    }
                    
            return result
            
        except ImportError as e:
            print(f"Error: Modul yang diperlukan tidak tersedia - {e}")
            print("Pastikan modul google-generativeai, pillow, dan python-dotenv sudah diinstal.")
            print("Instal dengan: pip install google-generativeai pillow python-dotenv")
            return self._create_mock_result(page_group)
            
        except Exception as e:
            print(f"Error saat memanggil API Google Gemini: {e}")
            import traceback
            traceback.print_exc()
            # Return mock data as fallback
            return self._create_mock_result(page_group)

    def _parse_potentially_incomplete_json(self, text: str) -> Dict:
        """
        Mengurai JSON yang mungkin tidak lengkap, mencoba menemukan JSON valid terbesar
        
        Args:
            text: Teks yang berisi JSON (mungkin tidak lengkap)
            
        Returns:
            Dictionary hasil parsing dari JSON yang valid
        """
        # Coba parse seluruh teks sebagai JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # Coba ekstrak JSON dari markdown code block
        import re
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', text)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                # JSON dalam code block juga tidak valid, lanjut ke metode berikutnya
                json_text = json_match.group(1)
            else:
                # JSON dalam code block valid
                return json.loads(json_match.group(1))
        else:
            # Tidak ada code block, gunakan seluruh teks
            json_text = text
        
        # Fungsi untuk memeriksa dan memperbaiki array JSON tidak lengkap
        def fix_incomplete_array(text):
            if not text.strip().startswith('['):
                return text
            
            result = []
            current_item = ""
            open_braces = 0
            open_brackets = 0
            in_string = False
            escape_next = False
            
            i = 0
            # Abaikan '[' awal
            if text[0] == '[':
                i = 1
            
            complete_items = 0
            
            while i < len(text):
                char = text[i]
                
                # Tangani string dengan escape character
                if char == '\\' and not escape_next:
                    escape_next = True
                    current_item += char
                    i += 1
                    continue
                
                if char == '"' and not escape_next:
                    in_string = not in_string
                elif not in_string:
                    if char == '{':
                        open_braces += 1
                    elif char == '}':
                        open_braces -= 1
                    elif char == '[':
                        open_brackets += 1
                    elif char == ']':
                        open_brackets -= 1
                
                current_item += char
                escape_next = False
                
                # Jika kita sampai pada koma di level paling luar (bukan dalam objek atau array bersarang)
                # dan tidak dalam string, maka kita telah mencapai akhir item
                if (char == ',' and open_braces == 0 and open_brackets == 0 and not in_string):
                    # Coba parse item ini
                    try:
                        item_text = current_item[:-1].strip()  # Buang koma
                        json_item = json.loads(item_text)
                        result.append(json_item)
                        complete_items += 1
                        current_item = ""
                    except:
                        # Item tidak valid, simpan sementara dan lanjutkan
                        current_item = ""
                
                # Jika kita sampai pada akhir array (']')
                elif (char == ']' and open_braces == 0 and open_brackets == 0 and not in_string):
                    # Coba parse item terakhir (jika ada)
                    try:
                        item_text = current_item[:-1].strip()  # Buang ']'
                        if item_text and not item_text.endswith(','):
                            json_item = json.loads(item_text)
                            result.append(json_item)
                            complete_items += 1
                    except:
                        pass
                    break
                
                i += 1
            
            # Jika ada item yang belum selesai di akhir dan bukan koma atau spasi
            last_non_whitespace = current_item.rstrip()
            if last_non_whitespace and last_non_whitespace[-1] not in [',', '}', ']']:
                # Coba temukan objek yang masih valid
                try:
                    # Periksa jika ada objek yang belum lengkap di akhir
                    if '{' in current_item:
                        # Temukan posisi pembuka kurawal terakhir
                        last_open_brace = current_item.rstrip().rfind('{')
                        last_close_brace = current_item.rstrip().rfind('}')
                        
                        # Jika pembukaan kurawal terakhir tidak memiliki penutup pasangannya
                        if last_open_brace > last_close_brace:
                            # Potong item yang tidak lengkap
                            current_item = current_item[:last_open_brace].rstrip()
                            
                            # Jika masih ada isi dan berakhir dengan koma, parse sebagai item terpisah
                            if current_item and current_item[-1] == ',':
                                item_text = current_item[:-1].strip()
                                try:
                                    json_item = json.loads(item_text)
                                    result.append(json_item)
                                    complete_items += 1
                                except:
                                    pass
                except:
                    pass
            
            # Jika kita berhasil mengurai setidaknya satu item
            if result:
                print(f"Berhasil mengurai {complete_items} item JSON lengkap dari array yang terpotong")
                return result
            
            return None
        
        # Fungsi untuk memperbaiki objek nested dalam array JSON
        def fix_json_array_with_incomplete_objects(text):
            try:
                # Regex untuk mencocokkan objek JSON dalam array
                array_match = re.search(r'\[\s*(.*?)\]', text, re.DOTALL)
                if not array_match:
                    return None
                    
                array_content = array_match.group(1)
                
                # Split berdasarkan pola objek JSON yang diakhiri dengan koma
                # Kita perlu berhati-hati dengan koma dalam string
                items = []
                current_item = ""
                open_braces = 0
                in_string = False
                escape_next = False
                
                for char in array_content:
                    if escape_next:
                        escape_next = False
                        current_item += char
                        continue
                        
                    if char == '\\':
                        escape_next = True
                    
                    if char == '"' and not escape_next:
                        in_string = not in_string
                    
                    elif not in_string:
                        if char == '{':
                            open_braces += 1
                        elif char == '}':
                            open_braces -= 1
                            
                            # Jika kita baru saja menutup objek (brace level 0),
                            # lihat karakter berikutnya untuk koma
                            if open_braces == 0:
                                current_item += char
                                # Tambahkan objek yang sudah lengkap
                                items.append(current_item.strip())
                                current_item = ""
                                continue
                    
                    current_item += char
                    
                    # Jika ada konten yang tersisa, tambahkan ke items untuk pemeriksaan
                    if current_item.strip() and len(items) == 0:
                        items.append(current_item.strip())
                
                # Hapus koma di akhir setiap item dan pastikan valid
                valid_items = []
                for item in items:
                    item = item.strip()
                    if item.endswith(','):
                        item = item[:-1]
                    
                    try:
                        # Pastikan ini adalah JSON yang valid
                        json.loads(item)
                        valid_items.append(item)
                    except json.JSONDecodeError:
                        # Jika bukan JSON yang valid, coba tambahkan kurung penutup yang hilang
                        open_count = item.count('{')
                        close_count = item.count('}')
                        
                        if open_count > close_count:
                            # Tambahkan kurung tutup
                            fixed_item = item + ('}' * (open_count - close_count))
                            try:
                                json.loads(fixed_item)
                                valid_items.append(fixed_item)
                            except:
                                pass
                
                if valid_items:
                    # Rekonstruksi array dengan objek yang valid
                    fixed_json = "[" + ",".join(valid_items) + "]"
                    try:
                        return json.loads(fixed_json)
                    except:
                        pass
                    
            except Exception as e:
                print(f"Error saat memperbaiki array JSON: {e}")
            
            return None
        
        # Coba memproses sebagai array JSON yang terpotong
        array_result = fix_incomplete_array(json_text)
        if array_result:
            return array_result
        
        # Coba memperbaiki array dengan objek tidak lengkap
        nested_array_result = fix_json_array_with_incomplete_objects(json_text)
        if nested_array_result:
            return nested_array_result
        
        # Percobaan untuk objek JSON tidak lengkap
        if json_text.strip().startswith('{'):
            # Inisialisasi counter untuk kurung kurawal
            open_braces = 0
            last_valid_pos = 0
            
            for i, char in enumerate(json_text):
                if char == '{':
                    open_braces += 1
                elif char == '}':
                    open_braces -= 1
                    # Jika kurung kurawal sudah seimbang, tandai posisi ini sebagai valid
                    if open_braces == 0:
                        last_valid_pos = i + 1

            # Coba parse JSON sampai posisi valid terakhir
            if last_valid_pos > 0:
                try:
                    return json.loads(json_text[:last_valid_pos])
                except json.JSONDecodeError:
                    pass
        
        # Percobaan untuk array JSON
        if json_text.strip().startswith('['):
            # Inisialisasi counter untuk kurung siku
            open_brackets = 0
            last_valid_pos = 0
            
            for i, char in enumerate(json_text):
                if char == '[':
                    open_brackets += 1
                elif char == ']':
                    open_brackets -= 1
                    # Jika kurung siku sudah seimbang, tandai posisi ini sebagai valid
                    if open_brackets == 0:
                        last_valid_pos = i + 1

            # Coba parse JSON sampai posisi valid terakhir
            if last_valid_pos > 0:
                try:
                    return json.loads(json_text[:last_valid_pos])
                except json.JSONDecodeError:
                    pass
        
        # Percobaan: Gunakan library jsonfix untuk memperbaiki JSON yang rusak (jika tersedia)
        try:
            import jsonfix
            try:
                return jsonfix.fix(json_text)
            except:
                pass
        except ImportError:
            print("Library jsonfix tidak tersedia. Untuk hasil lebih baik, install dengan: pip install jsonfix")
        
        # Percobaan: Gunakan JSON5 yang lebih toleran (jika tersedia)
        try:
            import json5
            try:
                return json5.loads(json_text)
            except:
                pass
        except ImportError:
            print("Library json5 tidak tersedia. Untuk hasil lebih baik, install dengan: pip install json5")
        
        print("Tidak dapat menemukan JSON yang valid dalam respons. Menggunakan struktur default.")
        return self._create_fallback_json_structure(json_text, [0])  # Asumsi setidaknya ada 1 halaman

    def _create_fallback_json_structure(self, response_text: str, page_group: List[int]) -> Dict:
        """
        Membuat struktur JSON fallback dari teks respons
        
        Args:
            response_text: Teks respons dari API
            page_group: Daftar halaman dalam grup
            
        Returns:
            Struktur JSON fallback
        """
        result = {}
        
        # Coba ekstrak informasi tabel dari respons teks
        lines = response_text.strip().split('\n')
        current_table = []
        
        for line in lines:
            if line.strip():
                # Asumsikan line berisi data tabel jika ada karakter pemisah seperti | atau tab
                if '|' in line or '\t' in line:
                    # Hapus spasi dan karakter | berlebih
                    cleaned_line = [cell.strip() for cell in re.split(r'\||\t', line) if cell.strip()]
                    if cleaned_line:
                        current_table.append(cleaned_line)
        
        # Ambil representasi teks dari tabel jika tidak ada, gunakan teks dasar
        if not current_table:
            current_table = [response_text]
        
        # Buat struktur JSON sederhana untuk setiap halaman
        for i, page_num in enumerate(page_group):
            actual_page_num = page_num + 1
            result[f'page_{actual_page_num}'] = {
                "table_type": "extracted_text",
                "warning": "Format JSON tidak valid, menggunakan ekstraksi teks sederhana",
                "extracted_data": {
                    "table": current_table if current_table else [],
                    "raw_text": response_text
                }
            }
        
        return result

    # def call_llm_api(self, images_data: List[Dict]) -> Dict:
    #     """
    #     Panggil API Google Gemini untuk ekstraksi tabel
    #     """
    #     print(f"Memanggil API {self.api_provider} untuk ekstraksi tabel...")
    #     print(f"Jumlah gambar: {len(images_data)}")
        
    #     try:
    #         import PIL.Image
    #         import google.generativeai as genai
    #         from dotenv import load_dotenv
            
    #         # Load environment variables
    #         load_dotenv()
            
    #         # Get API key from environment variables
    #         GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    #         if not GOOGLE_API_KEY:
    #             raise ValueError("Google API Key tidak ditemukan. Pastikan variabel GOOGLE_API_KEY ada di file .env")
            
    #         # Configure API key
    #         genai.configure(api_key=GOOGLE_API_KEY)
            
    #         # Initialize model
    #         model = genai.GenerativeModel('gemini-2.0-flash')
            
    #         # Prepare content for the API call with all images
    #         contents = [
    #             """
    #             Anda adalah sistem ahli dalam mengekstrak informasi dari gambar halaman PDF. Gambar yang diberikan adalah potongan halaman PDF dan bisa berisi teks biasa, tabel, dan/atau flowchart.
    #             Tugas Anda adalah menganalisis gambar dan mengekstrak informasi yang terkandung di dalamnya dalam format JSON.

    #             1. **Analisis Konten:** Identifikasi *semua* jenis konten yang ada dalam gambar. Sebuah gambar dapat berisi:
    #                 *   Teks biasa (text)
    #                 *   Tabel (table)
    #                 *   Flowchart (flowchart)
    #                 *   Kombinasi dari jenis-jenis konten tersebut

    #             2. **Ekstraksi Informasi:** Untuk *setiap* jenis konten yang teridentifikasi, lakukan langkah-langkah berikut:

    #                 *   **Ekstraksi Teks (jika ada):** Ekstrak semua teks yang dapat dibaca dan simpan dalam format berikut:
    #                     ```json
    #                     {
    #                     "type": "text",
    #                     "page_number": [Nomor Halaman (jika diketahui, jika tidak, biarkan kosong)],
    #                     "text": [
    #                         "Baris 1 teks",
    #                         "Baris 2 teks",
    #                         ...
    #                     ]
    #                     }
    #                     ```
    #                     Setiap baris teks harus menjadi elemen terpisah dalam array "text".

    #                 *   **Ekstraksi Tabel (jika ada):** Ekstrak struktur dan data tabel dan simpan dalam format berikut:
    #                     ```json
    #                     {
    #                     "type": "table",
    #                     "page_number": [Nomor Halaman (jika diketahui, jika tidak, biarkan kosong)],
    #                     "title": [Judul tabel (jika ada, jika tidak, biarkan kosong)],
    #                     "description": [Deskripsi singkat tabel (jika ada, jika tidak, biarkan kosong)],
    #                     "headers": [
    #                         "Header Kolom 1",
    #                         "Header Kolom 2",
    #                         ...
    #                     ],
    #                     "rows": [
    #                         {
    #                         "Header Kolom 1": "Data baris 1 kolom 1",
    #                         "Header Kolom 2": "Data baris 1 kolom 2",
    #                         ...
    #                         },
    #                         {
    #                         "Header Kolom 1": "Data baris 2 kolom 1",
    #                         "Header Kolom 2": "Data baris 2 kolom 2",
    #                         ...
    #                         }
    #                     ],
    #                     "footer": [Catatan kaki tabel (jika ada, jika tidak, biarkan kosong)],
    #                     "is_continued": [true jika tabel berlanjut dari halaman sebelumnya atau ke halaman berikutnya, false jika tidak]
    #                     }
    #                     ```
    #                     *   `is_continued`:  **Sangat penting.** Setel ke `true` jika tabel ini adalah kelanjutan dari tabel di halaman sebelumnya, atau jika tabel ini berlanjut ke halaman berikutnya. Setel ke `false` jika ini adalah tabel lengkap dalam satu gambar.

    #                 *   **Ekstraksi Flowchart (jika ada):** Ekstrak elemen-elemen flowchart dan simpan dalam format berikut:
    #                     ```json
    #                     {
    #                     "type": "flowchart",
    #                     "page_number": [Nomor Halaman (jika diketahui, jika tidak, biarkan kosong)],
    #                     "title": [Judul flowchart (jika ada, jika tidak, biarkan kosong)],
    #                     "structured_data": [
    #                         {
    #                         "entity": [Nama Entitas],
    #                         "input": [Input (jika ada)],
    #                         "processes": [
    #                             {
    #                             "name": [Nama Proses],
    #                             "description": [Deskripsi Proses]
    #                             }
    #                         ],
    #                         "description": [Deskripsi Entitas]
    #                         }
    #                     ],
    #                     "narrative": [Ringkasan naratif dari flowchart]
    #                     }
    #                     ```

    #             3. **Output:**  Keluarkan *semua* informasi yang diekstraksi sebagai *satu* array JSON. Setiap elemen dalam array mewakili satu bagian konten (teks, tabel, atau flowchart) yang diekstraksi dari gambar. Pastikan JSON tersebut valid dan dapat diurai dengan benar.

    #             **Instruksi Tambahan:**

    #             *   Fokus pada akurasi ekstraksi data.
    #             *   Jika Anda tidak yakin dengan tipe konten atau bagaimana cara mengekstrak informasi, berikan output JSON dengan bidang yang sesuai sebanyak mungkin dan sertakan catatan di bagian "extraction_notes" (yang belum ada di contoh format, mohon ditambahkan ke semua format data).
    #             *   **Prioritaskan deteksi *semua* elemen yang ada di gambar.** Jika gambar berisi teks *dan* tabel, hasilkan *dua* objek JSON terpisah: satu untuk teks, dan satu lagi untuk tabel.
    #             *   Jika ada teks di luar tabel atau flowchart, identifikasi apakah teks tersebut merupakan judul/catatan kaki yang terkait dengan tabel/flowchart. Jika ya, gabungkan informasi tersebut ke dalam objek JSON tabel/flowchart yang sesuai. Jika tidak, perlakukan teks tersebut sebagai elemen "text" yang terpisah.
    #             *   Jika gambar berisi *sebagian* tabel atau flowchart, usahakan untuk mengekstrak informasi sebanyak mungkin dan gunakan `is_continued: true` pada tabel yang terpotong.
    #             """
    #         ]
            
    #         # Add all images to the content
    #         for img_data in images_data:
    #             contents.append(img_data["pil_image"])
            
    #         # Call the Gemini API
    #         response = model.generate_content(contents)
            
    #         # Process the response
    #         response_text = response.text
    #         print(f"API Response received. Length: {len(response_text)} characters")
            
    #         print()
    #         print("---")
    #         print(len(response_text))
    #         print(type(response_text))
    #         print("---")
    #         print(response_text)
    #         print("---")
    #         print()
    #         # Parse the JSON response
    #         # Try to extract JSON from the response text if it's not already in JSON format
    #         try:
    #             # Try to parse the entire response as JSON
    #             parsed_result = json.loads(response_text)
    #         except json.JSONDecodeError:
    #             # If not valid JSON, try to extract JSON part from the text
    #             import re
    #             json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response_text)
    #             if json_match:
    #                 try:
    #                     parsed_result = json.loads(json_match.group(1))
    #                 except json.JSONDecodeError:
    #                     print("Tidak dapat memparsing JSON dari respons yang diekstrak")
    #                     parsed_result = self._create_fallback_json_structure(response_text, images_data)
    #             else:
    #                 # Create structured data from text as best as possible
    #                 parsed_result = self._create_fallback_json_structure(response_text, images_data)
            
    #         # Structure the result by page
    #         result = {}
            
    #         # Check if the response has page-based structure
    #         if isinstance(parsed_result, dict) and any(key.startswith('page_') for key in parsed_result.keys()):
    #             # The response already has the correct structure
    #             result = parsed_result
    #         elif isinstance(parsed_result, dict) and 'pages' in parsed_result:
    #             # Convert from {'pages': [{...page1...}, {...page2...}]} format to page_N format
    #             for i, page_data in enumerate(parsed_result['pages']):
    #                 page_num = page_data.get('page_num', i + 1)
    #                 result[f'page_{page_num}'] = page_data
    #         else:
    #             # Create a structured response for each page
    #             for i, img_data in enumerate(images_data):
    #                 page_num = img_data["page_num"]
    #                 result[f'page_{page_num}'] = {
    #                     "table_type": "extracted_table",
    #                     "extracted_data": parsed_result if isinstance(parsed_result, list) else [parsed_result]
    #                 }
                    
    #         return result
            
    #     except ImportError as e:
    #         print(f"Error: Modul yang diperlukan tidak tersedia - {e}")
    #         print("Pastikan modul google-generativeai, pillow, dan python-dotenv sudah diinstal.")
    #         print("Instal dengan: pip install google-generativeai pillow python-dotenv")
    #         return self._create_mock_result(images_data)
            
    #     except Exception as e:
    #         print(f"Error saat memanggil API Google Gemini: {e}")
    #         import traceback
    #         traceback.print_exc()
    #         # Return mock data as fallback
    #         return self._create_mock_result(images_data)

    def _create_fallback_json_structure(self, text, page_group):
        """
        Create a structured JSON from unstructured text response
        """
        print("Membuat struktur JSON dari teks respons...")
        
        # Simple parsing logic - can be enhanced
        lines = text.split('\n')
        
        # Remove empty lines and trim whitespace
        lines = [line.strip() for line in lines if line.strip()]
        
        # Create a simple structure
        extracted_data = []
        current_item = {}
        
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                current_item[key.strip()] = value.strip()
            elif line.startswith('- ') or line.startswith('* '):
                # New list item
                if current_item and len(current_item) > 0:
                    extracted_data.append(current_item)
                    current_item = {}
                current_item['item'] = line[2:].strip()
            elif line.startswith('#') or line.startswith('##'):
                # Heading - start new section
                if current_item and len(current_item) > 0:
                    extracted_data.append(current_item)
                    current_item = {}
                current_item['heading'] = line.strip('# ')
        
        # Add the last item if it exists
        if current_item and len(current_item) > 0:
            extracted_data.append(current_item)
        
        return extracted_data

    def _create_mock_result(self, page_group):
        """
        Create mock result when API call fails
        """
        print("Membuat hasil ekstraksi mock sebagai fallback...")
        result = {}
        
        for page_num in page_group:
            actual_page_num = page_num + 1
            result[f"page_{actual_page_num}"] = {
                "table_type": "unknown",
                "extraction_status": "failed",
                "error": "Tidak dapat mengekstrak data menggunakan API. Coba lagi nanti.",
                "extracted_data": []
            }
        
        return result
    
    def save_results(self):
        """
        Simpan hasil ekstraksi ke file JSON.
        Nama file JSON diambil dari nama file PDF yang diproses.
        """
        # Tentukan metode ekstraksi berdasarkan hasil
        if self.pages_with_tables:
            if len(self.pages_with_tables) == self.total_pages:
                self.result["metadata"]["extraction_method"] = "table_detection_only"
            else:
                self.result["metadata"]["extraction_method"] = "mixed"
        else:
            self.result["metadata"]["extraction_method"] = "text_extraction_only"
        
        # Simpan metadata tabel
        self.result["metadata"]["tables"] = {
            "total_pages_with_tables": len(self.pages_with_tables),
            "table_groups": [
                {
                    "group_id": f"{group[0]+1}" if len(group) == 1 else f"{group[0]+1}-{group[-1]+1}",
                    "pages": [p+1 for p in group]
                }
                for group in self.table_groups
            ]
        }
        
        # Hapus objek PIL image sebelum menyimpan ke JSON
        for page in self.result["pages"]:
            if "pil_image" in page:
                del page["pil_image"]
        
        # Buat nama file JSON berdasarkan nama file PDF
        pdf_filename = os.path.basename(self.pdf_path)  # Ambil nama file PDF (misal: "1_Teks_Biasa.pdf")
        json_filename = pdf_filename.replace(".pdf", ".json")  # Ganti ekstensi .pdf dengan .json
        output_json = os.path.join(self.output_dir, json_filename)  # Gabungkan dengan direktori output
        
        # Simpan ke file JSON
        # output_json = os.path.join(self.output_dir, "extraction_results.json")
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(self.result, f, ensure_ascii=False, indent=2)
        
        print(f"\nHasil ekstraksi disimpan ke: {output_json}")

    def cleanup(self):
        """
        Membersihkan semua file sementara
        """
        if self.cleanup_temp_files:
            temp_dir = os.path.join(self.output_dir, "temp")
            if os.path.exists(temp_dir):
                for file in os.listdir(temp_dir):
                    file_path = os.path.join(temp_dir, file)
                    try:
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                    except Exception as e:
                        print(f"Gagal menghapus file {file_path}: {e}")
                
                try:
                    os.rmdir(temp_dir)
                    print(f"Direktori sementara {temp_dir} dibersihkan")
                except:
                    print(f"Tidak dapat menghapus direktori {temp_dir}")


if __name__ == "__main__":
    extractor = PDFExtractor(
        pdf_path="studi_kasus/v2.pdf",
        output_dir="output_ekstraksi",
        min_line_length=30,
        line_thickness=1,
        header_threshold=50,
        footer_threshold=50,
        scan_header_threshold=50,
        scan_footer_threshold=50,
        min_lines_per_page=1,
        api_provider="google",  # Using Google Gemini API
        save_images=True,
        draw_line_highlights=False,
        cleanup_temp_files=True
    )
    
    results = extractor.process()
    
    # Summary of results
    print("\nRingkasan hasil ekstraksi:")
    print(f"Total halaman: {results['metadata']['total_pages']}")
    print(f"Metode ekstraksi: {results['metadata']['extraction_method']}")
    