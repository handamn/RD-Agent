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


    def save_pdf_split(self, page_group: List[int], group_id: str, split_index: int = 0, quarter_coords_list: List = None) -> List[str]:
        """
        Menyimpan halaman-halaman tertentu dari PDF sebagai file PDF baru.
        Dapat melakukan multiple split jika quarter_coords_list diberikan.
        
        Args:
            page_group: List nomor halaman yang akan disimpan (berbasis indeks 0)
            group_id: Identifier untuk grup halaman
            split_index: Indeks split untuk penamaan file jika melakukan multiple split
            quarter_coords_list: List dari quarter_coords untuk multiple split
            
        Returns:
            List path file PDF yang disimpan atau [] jika opsi dinonaktifkan
        """
        # Jika opsi save_pdf_splits dinonaktifkan, kembalikan list kosong
        if not self.save_pdf_splits:
            print(f"  * Opsi save_pdf_splits dinonaktifkan, tidak menyimpan split PDF")
            return []
        
        saved_paths = []
        
        # Cek apakah kita perlu menggunakan alur baru (dengan gap detection)
        use_new_flow = False
        
        # Jika quarter_coords_list diberikan, gunakan itu
        if quarter_coords_list:
            use_new_flow = True
        # Jika tidak, coba deteksi gap seperti sebelumnya
        elif len(page_group) == 1:
            page_num = page_group[0]
            # Cari data halaman yang sesuai
            page_data = None
            for p in self.result["pages"]:
                if p["page_num"] == page_num + 1:
                    page_data = p
                    break
            
            if page_data and "valid_lines" in page_data:
                valid_lines = page_data["valid_lines"]
                page = self.doc[page_num]
                page_height = page.rect.height
                
                # Panggil check_large_y_gaps
                upper_line_coord, lower_line_coord, max_gap = self.check_large_y_gaps(valid_lines, page_height)
                
                # Jika gap cukup besar, gunakan alur baru
                if max_gap > (page_height * 0.1):  # Misalnya, jika gap > 10% dari tinggi halaman
                    use_new_flow = True
                    print(f"\n  * Halaman {page_num+1} memiliki gap besar: {max_gap} poin")
                    print(f"    - Garis atas: {upper_line_coord}")
                    print(f"    - Garis bawah: {lower_line_coord}\n")
                    
                    # Buat koordinat untuk split_and_merge_pdf
                    quarter_coords_list = [
                        [(0, upper_line_coord/2),  # Dari atas halaman ke garis atas
                         (upper_line_coord/2, lower_line_coord-upper_line_coord)],  # Dari garis bawah ke bawah halaman
                        [(0, upper_line_coord),
                         (lower_line_coord-upper_line_coord, page_height)]
                    ]
        
        # Jika dapat menggunakan alur baru
        if use_new_flow:
            try:
                # Buat PDF sementara dengan halaman yang diinginkan
                temp_dir = os.path.join(self.output_dir, "temp")
                Path(temp_dir).mkdir(parents=True, exist_ok=True)
                temp_pdf = os.path.join(temp_dir, f"temp_{group_id}.pdf")
                
                # Buat dokumen sementara dengan halaman yang diperlukan
                temp_doc = fitz.open()
                temp_doc.insert_pdf(self.doc, from_page=page_group[0], to_page=page_group[0])
                temp_doc.save(temp_pdf)
                temp_doc.close()
                
                # Loop untuk setiap set koordinat jika ada multiple split
                coords_to_process = quarter_coords_list if quarter_coords_list else [quarter_coords_list[0]]
                
                for idx, quarter_coords in enumerate(coords_to_process):
                    # Buat nama file unik untuk setiap split
                    split_suffix = f"_part{idx+1}" if len(coords_to_process) > 1 or split_index > 0 else ""
                    output_filename = f"split_{os.path.basename(self.pdf_path).replace('.pdf', '')}_{group_id}{split_suffix}.pdf"
                    output_path = os.path.join(self.pdf_output_dir, output_filename)
                    
                    # Panggil fungsi split_and_merge_pdf
                    print(f"  * Menggunakan alur baru dengan split_and_merge_pdf (split {idx+1})")
                    self.split_and_merge_pdf(temp_pdf, output_path, quarter_coords)
                    
                    saved_paths.append(output_path)
                    print(f"  * PDF split disimpan: {output_path}")
                
                # Hapus file sementara jika diperlukan
                if self.cleanup_temp_files and os.path.exists(temp_pdf):
                    os.remove(temp_pdf)
                
                return saved_paths
                
            except Exception as e:
                print(f"  * Error saat menggunakan alur baru: {e}")
                print(f"  * Menggunakan alur lama sebagai fallback...")
                use_new_flow = False  # Fallback ke alur lama
        
        # Jika tidak menggunakan alur baru, gunakan alur lama
        if not use_new_flow:
            # Buat nama file
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
                
                saved_paths.append(output_path)
                return saved_paths
            except Exception as e:
                print(f"  * Error saat menyimpan PDF split: {e}")
                return []
            finally:
                # Tutup dokumen
                new_doc.close()

    
    def convert_opencv_to_pymupdf(self, coords, page_width):
        """
        Mengkonversi koordinat (y_top, y_bottom) ke format PyMuPDF Rect
        """
        return [fitz.Rect(0, y_top, page_width, y_bottom) for (y_top, y_bottom) in coords]

    def split_and_merge_pdf(self, input_pdf, output_pdf, quarter_coords):
        """
        Membagi dan menggabungkan PDF berdasarkan koordinat yang diberikan
        """
        doc = fitz.open(input_pdf)
        new_doc = fitz.open()
        page = doc[0]  # Ambil halaman pertama
        rect = page.rect  # Ukuran halaman asli
        
        if not quarter_coords:
            raise ValueError("quarter_coords harus diberikan!")
        
        quarters = self.convert_opencv_to_pymupdf(quarter_coords, rect.width)
        new_height = sum(q.height for q in quarters)
        new_page = new_doc.new_page(width=rect.width, height=new_height)
        
        y_offset = 0
        for quarter_rect in quarters:
            new_page.show_pdf_page(
                fitz.Rect(rect.x0, y_offset, rect.x1, y_offset + quarter_rect.height),
                doc, 0, clip=quarter_rect
            )
            y_offset += quarter_rect.height
        
        new_doc.save(output_pdf)
        new_doc.close()
        doc.close()
    
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
            "valid_lines": lines,
            "text": page_text if not has_table else None,  # Teks disimpan sebagai list string
            "table_data": None  # Akan diisi nanti oleh API LLM jika memiliki tabel
        }
    
    def check_large_y_gaps(self, valid_lines, page_height):
        if len(valid_lines) < 2:
            return 0,0,0

        y_positions = sorted(set(line['y_position'] for line in valid_lines))
        threshold = page_height / 2
        max_gap = 0
        selected_pair = None

        for i in range(len(y_positions) - 1):
            gap = y_positions[i + 1] - y_positions[i]
            if gap > threshold and gap > max_gap:
                max_gap = gap
                selected_pair = (y_positions[i], y_positions[i + 1])

        if selected_pair:
            upper_line_coord = selected_pair[0]
            lower_line_coord = selected_pair[1]
            return upper_line_coord, lower_line_coord, max_gap

        return 0,0,0
    
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
    

    def extract_tables_from_group(self, page_group: List[int], quarter_coords_list: List = None):
        """
        Ekstrak tabel dari sekelompok halaman menggunakan API LLM
        Dapat melakukan multiple split jika quarter_coords_list diberikan
        """
        if not page_group:
            return
                
        group_start = page_group[0] + 1  # +1 untuk tampilan
        group_end = page_group[-1] + 1
        
        group_id = f"{group_start}" if len(page_group) == 1 else f"{group_start}-{group_end}"
        print(f"\nMengekstrak tabel dari halaman {group_id} menggunakan API {self.api_provider}...")
        
        # Simpan halaman sebagai split PDF (mungkin multiple)
        pdf_split_paths = self.save_pdf_split(page_group, group_id, quarter_coords_list=quarter_coords_list)
        
        all_table_data = {}  # Dictionary untuk menyimpan hasil dari semua split
        
        # Jika PDF split berhasil disimpan atau dibuat, gunakan API untuk ekstraksi
        if pdf_split_paths:
            # Jika gambar sudah diproses dan opsi save_images diaktifkan, simpan gambar untuk visualisasi
            if self.save_images:
                for i, page_num in enumerate(page_group):
                    if page_num in self.page_images:
                        img_filename = f"table_pages_{group_id}_part{i+1}.png"
                        img_path = os.path.join(self.img_output_dir, img_filename)
                        cv2.imwrite(img_path, self.page_images[page_num])
                        print(f"  * Gambar untuk visualisasi disimpan: {img_path}")
        
            # Panggil API LLM dengan setiap PDF split secara berurutan
            for idx, pdf_split_path in enumerate(pdf_split_paths):
                print(f"  * Memproses split PDF {idx+1} dari {len(pdf_split_paths)}: {pdf_split_path}")
                
                # Panggil API LLM dengan PDF split
                api_result = self.call_llm_api_with_pdf(pdf_split_path, page_group)
                
                # Untuk setiap halaman dalam grup, simpan hasilnya di all_table_data
                for page_num in page_group:
                    page_key = f"page_{page_num+1}"
                    if page_key in api_result:
                        # Buat key untuk hasil split ini
                        split_key = f"split_{idx+1}"
                        
                        # Inisialisasi dictionary untuk halaman ini jika belum ada
                        if page_num not in all_table_data:
                            all_table_data[page_num] = {}
                        
                        # Simpan hasil untuk split ini
                        all_table_data[page_num][split_key] = api_result[page_key]
            
            # Update hasil untuk setiap halaman dalam grup
            for page_num in page_group:
                page_idx = page_num  # Indeks dalam self.result["pages"]
                # Cari halaman yang sesuai
                for idx, page_data in enumerate(self.result["pages"]):
                    if page_data["page_num"] == page_num + 1:
                        page_idx = idx
                        break
                
                # Update data tabel dengan semua hasil untuk halaman ini
                if page_num in all_table_data:
                    self.result["pages"][page_idx]["table_data"] = all_table_data[page_num]
                else:
                    self.result["pages"][page_idx]["table_data"] = {}
                
                # Tambahkan informasi path split PDF ke hasil
                self.result["pages"][page_idx]["pdf_split_paths"] = pdf_split_paths
        else:
            print(f"  * Tidak dapat membuat atau menyimpan PDF split untuk halaman {group_id}")


    def _process_pdf_split(self, pdf_split_path, page_group, identifier):
        """
        Proses PDF split dan panggil API LLM
        
        Args:
            pdf_split_path: Path ke file PDF split
            page_group: List nomor halaman
            identifier: Pengenal untuk hasil (bisa berisi info tentang bagian)
        """
        # Jika PDF split berhasil disimpan atau dibuat, gunakan API untuk ekstraksi
        if pdf_split_path:
            # Jika gambar sudah diproses dan opsi save_images diaktifkan, simpan gambar untuk visualisasi
            if self.save_images:
                for i, page_num in enumerate(page_group):
                    if page_num in self.page_images:
                        img_filename = f"table_pages_{identifier}_part{i+1}.png"
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
                result_key = f"page_{page_num+1}"
                if result_key in api_result:
                    # Jika belum ada data tabel, inisialisasi sebagai list
                    if "table_data" not in self.result["pages"][page_idx]:
                        self.result["pages"][page_idx]["table_data"] = []
                    
                    # Tambahkan hasil sebagai item dalam list
                    table_entry = {
                        "split_id": identifier,
                        "data": api_result[result_key],
                        "pdf_split_path": pdf_split_path
                    }
                    
                    self.result["pages"][page_idx]["table_data"].append(table_entry)
        else:
            print(f"  * Tidak dapat membuat atau menyimpan PDF split untuk halaman {identifier}")
    
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
                """,
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
            try:
                # Try to parse the entire response as JSON
                parsed_result = json.loads(response_text)
            except json.JSONDecodeError:
                # If not valid JSON, try to extract JSON part from the text
                import re
                json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response_text)
                if json_match:
                    try:
                        parsed_result = json.loads(json_match.group(1))
                    except json.JSONDecodeError:
                        print("Tidak dapat memparsing JSON dari respons yang diekstrak")
                        parsed_result = self._create_fallback_json_structure(response_text, page_group)
                else:
                    # Create structured data from text as best as possible
                    parsed_result = self._create_fallback_json_structure(response_text, page_group)
            
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
        draw_line_highlights=True,
        cleanup_temp_files=True
    )
    
    results = extractor.process()
    
    # Summary of results
    print("\nRingkasan hasil ekstraksi:")
    print(f"Total halaman: {results['metadata']['total_pages']}")
    print(f"Metode ekstraksi: {results['metadata']['extraction_method']}")
    