import os
import pandas as pd
from PyPDF2 import PdfReader
import camelot
import pdfplumber

# HARDCODED PATHS
PDF_FILE_PATH = "studi_kasus/7_Tabel_N_Halaman_Normal_V2.pdf"  # Ganti dengan path file PDF Anda
OUTPUT_DIRECTORY = "ekstraksi"  # Ganti dengan direktori output yang diinginkan

class PDFExtractor:
    def __init__(self, pdf_path):
        """
        Inisialisasi ekstractor PDF
        
        Args:
            pdf_path (str): Path ke file PDF
        """
        self.pdf_path = pdf_path
        self.pdf_reader = PdfReader(pdf_path)
        self.num_pages = len(self.pdf_reader.pages)
        
    def extract_all_text(self):
        """
        Ekstraksi semua teks dari PDF
        
        Returns:
            dict: Dictionary dengan nomor halaman sebagai key dan teks sebagai value
        """
        text_by_page = {}
        
        for page_num in range(self.num_pages):
            page = self.pdf_reader.pages[page_num]
            text = page.extract_text()
            text_by_page[page_num + 1] = text
            
        return text_by_page
    
    def extract_tables_camelot(self, pages='all'):
        """
        Ekstraksi tabel menggunakan library camelot
        
        Args:
            pages (str or list): Halaman yang akan diekstrak ('all' atau list halaman)
            
        Returns:
            list: List dari DataFrame pandas yang berisi tabel
        """
        if pages == 'all':
            pages = '1-' + str(self.num_pages)
        elif isinstance(pages, list):
            pages = ','.join(map(str, pages))
        
        # Mode lattice untuk tabel dengan garis pembatas
        tables_lattice = camelot.read_pdf(
            self.pdf_path,
            pages=pages,
            flavor='lattice'
        )
        
        # Mode stream untuk tabel tanpa garis pembatas
        tables_stream = camelot.read_pdf(
            self.pdf_path,
            pages=pages,
            flavor='stream'
        )
        
        # Konversi ke pandas DataFrame
        all_tables = []
        
        for table in tables_lattice:
            df = table.df
            # Bersihkan DataFrame
            df = self._clean_table(df)
            all_tables.append(df)
            
        for table in tables_stream:
            df = table.df
            # Bersihkan DataFrame
            df = self._clean_table(df)
            # Periksa apakah tabel unik
            if not any(df.equals(t) for t in all_tables):
                all_tables.append(df)
        
        return all_tables
    
    def extract_tables_pdfplumber(self, pages='all'):
        """
        Ekstraksi tabel menggunakan library pdfplumber
        
        Args:
            pages (str or list): Halaman yang akan diekstrak ('all' atau list halaman)
            
        Returns:
            list: List dari DataFrame pandas yang berisi tabel
        """
        all_tables = []
        
        with pdfplumber.open(self.pdf_path) as pdf:
            if pages == 'all':
                pages_to_extract = range(len(pdf.pages))
            else:
                pages_to_extract = [p-1 for p in pages]  # pdfplumber uses 0-indexing
            
            for page_num in pages_to_extract:
                if page_num < len(pdf.pages):
                    page = pdf.pages[page_num]
                    tables = page.extract_tables()
                    
                    for table_data in tables:
                        # Konversi ke DataFrame pandas
                        df = pd.DataFrame(table_data)
                        
                        # Gunakan baris pertama sebagai header jika memungkinkan
                        if not df.empty:
                            df.columns = df.iloc[0]
                            df = df.iloc[1:]
                            df = df.reset_index(drop=True)
                            all_tables.append(df)
        
        return all_tables
    
    def _clean_table(self, df):
        """
        Membersihkan DataFrame tabel
        
        Args:
            df (pandas.DataFrame): DataFrame yang akan dibersihkan
            
        Returns:
            pandas.DataFrame: DataFrame yang sudah dibersihkan
        """
        # Gunakan baris pertama sebagai header jika bukan header
        if df.iloc[0].astype(str).str.contains(r'[A-Za-z]').all():
            df.columns = df.iloc[0]
            df = df.iloc[1:]
        
        # Reset index
        df = df.reset_index(drop=True)
        
        # Hapus kolom yang hanya berisi NaN
        df = df.dropna(axis=1, how='all')
        
        # Hapus baris yang hanya berisi NaN
        df = df.dropna(axis=0, how='all')
        
        return df
    
    def extract_all(self, output_dir):
        """
        Ekstrak semua konten (teks dan tabel) dari PDF dan simpan hasilnya
        
        Args:
            output_dir (str): Direktori untuk menyimpan hasil ekstraksi
            
        Returns:
            dict: Dictionary berisi semua hasil ekstraksi
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # Ekstrak teks
        text_by_page = self.extract_all_text()
        
        # Simpan teks
        with open(os.path.join(output_dir, "extracted_text.txt"), "w", encoding="utf-8") as f:
            for page_num, text in text_by_page.items():
                f.write(f"\n--- HALAMAN {page_num} ---\n\n")
                f.write(text)
                f.write("\n")
        
        # Ekstrak tabel menggunakan camelot dan pdfplumber
        tables_camelot = self.extract_tables_camelot()
        tables_pdfplumber = self.extract_tables_pdfplumber()
        
        # Gabungkan hasil dari berbagai metode
        all_tables = []
        all_tables.extend(tables_camelot)
        
        # Tambahkan tabel dari pdfplumber yang belum terdeteksi
        for table in tables_pdfplumber:
            if not any(table.equals(t) for t in all_tables):
                all_tables.append(table)
        
        # Simpan tabel
        for i, table in enumerate(all_tables):
            # Simpan dalam CSV
            table.to_csv(os.path.join(output_dir, f"table_{i+1}.csv"), index=False)
            # Simpan dalam Excel
            table.to_excel(os.path.join(output_dir, f"table_{i+1}.xlsx"), index=False)
        
        result = {
            "text": text_by_page,
            "tables": all_tables
        }
        
        return result


def main():
    """
    Fungsi utama untuk menjalankan ekstraksi PDF dengan path hardcoded
    """
    print(f"Memproses file: {PDF_FILE_PATH}")
    extractor = PDFExtractor(PDF_FILE_PATH)
    result = extractor.extract_all(output_dir=OUTPUT_DIRECTORY)
    
    print(f"\nEkstraksi selesai! Hasil disimpan di folder: {OUTPUT_DIRECTORY}")
    print(f"Total halaman: {extractor.num_pages}")
    print(f"Total tabel yang diekstrak: {len(result['tables'])}")


if __name__ == "__main__":
    main()