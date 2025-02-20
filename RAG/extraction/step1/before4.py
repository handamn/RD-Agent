import tempfile
import os
from unstructured.partition.pdf import partition_pdf
from unstructured.partition.pdf import partition_pdf
# from unstructured.partition.utils import convert_to_isd
import pytesseract
import camelot
import gc
import shutil
from contextlib import contextmanager
import time
import csv
from dotenv import load_dotenv
import re
import statistics
from langchain_openai import ChatOpenAI
from langchain_openai import OpenAIEmbeddings
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

embd = OpenAIEmbeddings(model="text-embedding-3-small")

model = ChatOpenAI(model_name="gpt-4o-mini", temperature=0)



LANGCHAIN_TRACING_V2 = os.getenv('LANGCHAIN_TRACING_V2')
LANGCHAIN_ENDPOINT = os.getenv('LANGCHAIN_ENDPOINT')
LANGCHAIN_API_KEY = os.getenv('LANGCHAIN_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')



def convert_to_structured_string(data):
    # Ambil header (kolom) dari data
    columns = data[0]
    
    # Buat list untuk menyimpan string terstruktur
    structured_strings = []
    
    # Loop melalui setiap baris data (mulai dari indeks 1 karena indeks 0 adalah header)
    for row in data[1:]:
        # Buat string terstruktur untuk setiap baris
        row_string = ", ".join([f"{columns[i]}: {row[i]}" for i in range(len(columns))])
        structured_strings.append(row_string)
    
    # Kembalikan hasil dalam bentuk list of strings
    return structured_strings

def convert_to_json(data):
    # Ambil header (kolom) dari data
    columns = data[0]
    
    # Buat list untuk menyimpan baris data
    rows = []
    
    # Loop melalui setiap baris data (mulai dari indeks 1 karena indeks 0 adalah header)
    for row in data[1:]:
        # Buat dictionary untuk setiap baris
        row_dict = {columns[i]: row[i] for i in range(len(columns))}
        rows.append(row_dict)
    
    # Kembalikan hasil dalam format JSON
    return {"columns": columns, "rows": rows}

def remove_newlines_and_double_spaces(text):
    """
    Menghilangkan newline (\n) dan double spasi dari teks.
    """
    text = text.replace("\n", " ")
    while "  " in text:
        text = text.replace("  ", " ")
    while "—__" in text:
        text = text.replace("—__", " ")
    return text.strip()

def remove_newlines_and_double_spaces_from_table(table):
    """
    Menghilangkan newline (\n) dan double spasi dari tabel.
    """
    return [[remove_newlines_and_double_spaces(cell) for cell in row] for row in table]

def normalize_table(table):
    """
    Normalisasi tabel dengan mengisi kolom kosong menggunakan nilai dari baris lengkap sebelumnya.
    """
    normalized_table = []
    last_full_row = None

    for row in table:
        if all(cell.strip() for cell in row):
            last_full_row = row
            normalized_table.append(row)
        else:
            if last_full_row:
                normalized_row = []
                for idx, cell in enumerate(row):
                    if not cell.strip() and idx < len(last_full_row):
                        normalized_row.append(last_full_row[idx])
                    else:
                        normalized_row.append(cell)
                normalized_table.append(normalized_row)
            else:
                normalized_table.append(row)

    return normalized_table

def is_text_part_of_table_substring(text, table):
    """
    Cek apakah teks merupakan kombinasi dari beberapa elemen dalam list di tabel.
    """
    for row in table:
        combined_row = " ".join([cell.strip() for cell in row if cell.strip()])
        if text in combined_row:
            return True
    return False

def is_nomor_halaman(teks):
    """
    Cek apakah teks hanya berisi angka (nomor halaman).
    """
    return teks.strip().isdigit()



def gabungkan_tabel(tabel_sebelum, tabel_sesudah):
    """
    Gabungkan dua tabel dengan deteksi lanjutan untuk kasus tanpa header berulang.
    """
    if not tabel_sebelum or not tabel_sesudah:
        return None
    
    # Cek apakah header sama (kasus normal)
    if tabel_sebelum[0] == tabel_sesudah[0]:
        return tabel_sebelum + tabel_sesudah[1:]
    
    # Kasus header tidak diulang: deteksi berdasarkan jumlah kolom dan tipe data
    kolom_tabel_sebelum = len(tabel_sebelum[0])
    kolom_tabel_sesudah = len(tabel_sesudah[0])
    
    # Periksa jumlah kolom apakah sama atau mendekati
    if abs(kolom_tabel_sebelum - kolom_tabel_sesudah) <= 1:
        # Analisis pola data untuk menentukan apakah ini kelanjutan tabel
        if is_continuation_by_pattern(tabel_sebelum, tabel_sesudah):
            # Jika ini adalah kelanjutan, gunakan header dari tabel sebelumnya
            if kolom_tabel_sebelum == kolom_tabel_sesudah:
                # Jumlah kolom sama, gabungkan langsung
                return tabel_sebelum + tabel_sesudah
            elif kolom_tabel_sebelum > kolom_tabel_sesudah:
                # Tabel kedua memiliki kolom kurang, padding dengan empty cells
                padded_table = pad_table(tabel_sesudah, kolom_tabel_sebelum)
                return tabel_sebelum + padded_table
            else:
                # Tabel kedua memiliki kolom lebih, truncate atau sesuaikan
                truncated_table = truncate_table(tabel_sesudah, kolom_tabel_sebelum)
                return tabel_sebelum + truncated_table
    
    return None

def is_continuation_by_pattern(tabel_sebelum, tabel_sesudah):
    """
    Menganalisis pola data untuk menentukan apakah tabel kedua adalah kelanjutan dari tabel pertama.
    """
    if len(tabel_sebelum) < 2 or len(tabel_sesudah) < 1:
        return False
    
    # Ekstrak beberapa karakteristik untuk analisis
    # 1. Periksa tipe data pada kolom yang sama
    data_types_match = check_data_types_compatibility(tabel_sebelum[1:], tabel_sesudah)
    
    # 2. Periksa format penomoran atau ID jika ada
    numbering_continues = check_if_numbering_continues(tabel_sebelum, tabel_sesudah)
    
    # 3. Periksa apakah tabel sesudah memiliki header yang berbeda dari data normal
    has_data_not_header = not looks_like_header(tabel_sesudah[0], tabel_sesudah[1:] if len(tabel_sesudah) > 1 else [])
    
    # Buat keputusan berdasarkan kombinasi faktor
    return (data_types_match and (numbering_continues or has_data_not_header))

def check_data_types_compatibility(rows_sebelum, tabel_sesudah):
    """
    Memeriksa kompatibilitas tipe data antara dua tabel.
    """
    if not rows_sebelum or not tabel_sesudah:
        return False
    
    num_cols_sebelum = len(rows_sebelum[0]) if rows_sebelum[0] else 0
    num_cols_sesudah = len(tabel_sesudah[0]) if tabel_sesudah[0] else 0
    
    # Jika jumlah kolom sangat berbeda, kemungkinan bukan kelanjutan
    if abs(num_cols_sebelum - num_cols_sesudah) > 1:
        return False
    
    # Ambil sampel dari tabel sebelum untuk analisis
    sample_rows_sebelum = rows_sebelum[-min(3, len(rows_sebelum)):]
    
    # Hitung pola tipe data (angka, teks, tanggal, dll) untuk setiap kolom
    patterns_sebelum = analyze_data_patterns(sample_rows_sebelum)
    
    # Ambil sampel dari tabel sesudah (asumsikan baris pertama bisa jadi header atau data)
    sample_rows_sesudah = tabel_sesudah[:min(3, len(tabel_sesudah))]
    patterns_sesudah = analyze_data_patterns(sample_rows_sesudah)
    
    # Bandingkan pola
    min_cols = min(len(patterns_sebelum), len(patterns_sesudah))
    matches = sum(1 for i in range(min_cols) if patterns_sebelum[i] == patterns_sesudah[i])
    match_ratio = matches / min_cols if min_cols > 0 else 0
    
    # Hitung setidaknya 60% kolom memiliki pola data yang sama
    return match_ratio >= 0.6

def analyze_data_patterns(rows):
    """
    Menganalisis pola data dari sampel baris.
    """
    if not rows or not rows[0]:
        return []
    
    num_cols = len(rows[0])
    patterns = []
    
    for col_idx in range(num_cols):
        col_values = [row[col_idx] if col_idx < len(row) else "" for row in rows]
        
        # Tentukan pola untuk kolom ini
        num_count = sum(1 for val in col_values if is_numeric(val))
        date_count = sum(1 for val in col_values if is_date(val))
        
        if num_count > len(col_values) / 2:
            patterns.append("numeric")
        elif date_count > len(col_values) / 2:
            patterns.append("date")
        else:
            patterns.append("text")
    
    return patterns

def is_numeric(value):
    """
    Cek apakah nilai adalah angka.
    """
    # Hapus format seperti koma dan persen
    clean_val = value.replace(',', '').replace('%', '').replace(' ', '')
    try:
        float(clean_val)
        return True
    except (ValueError, TypeError):
        return False

def is_date(value):
    """
    Cek apakah nilai kemungkinan format tanggal.
    """
    import re
    # Pola sederhana untuk tanggal (bisa diperluas)
    date_patterns = [
        r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',  # dd/mm/yyyy atau dd-mm-yyyy
        r'\d{1,2}\s+[A-Za-z]{3,}\s+\d{2,4}',  # dd Month yyyy
        r'\d{2,4}[/-]\d{1,2}[/-]\d{1,2}'  # yyyy/mm/dd atau yyyy-mm-dd
    ]
    
    for pattern in date_patterns:
        if re.search(pattern, value):
            return True
    return False

def check_if_numbering_continues(tabel_sebelum, tabel_sesudah):
    """
    Cek apakah ada pola penomoran yang berlanjut antara dua tabel.
    """
    if len(tabel_sebelum) < 2 or not tabel_sesudah:
        return False
    
    # Cari kolom yang mungkin berisi nomor urut
    num_col_idx = find_numbering_column(tabel_sebelum)
    if num_col_idx is None:
        return False
    
    # Pastikan kolom itu juga ada di tabel sesudah
    if tabel_sesudah[0] and num_col_idx < len(tabel_sesudah[0]):
        # Ambil nomor terakhir dari tabel sebelum
        last_num = extract_number(tabel_sebelum[-1][num_col_idx])
        # Ambil nomor pertama dari tabel sesudah
        first_num = extract_number(tabel_sesudah[0][num_col_idx])
        
        # Cek apakah nomor berlanjut
        if last_num is not None and first_num is not None:
            # Toleransi untuk missing numbers
            return abs(first_num - last_num) <= 3
    
    return False

def find_numbering_column(table):
    """
    Mencari kolom yang kemungkinan berisi nomor urut.
    """
    if len(table) < 3 or not table[0]:
        return None
    
    num_cols = len(table[0])
    best_col = None
    max_numeric_ratio = 0
    
    for col_idx in range(num_cols):
        values = [row[col_idx] if col_idx < len(row) else "" for row in table[1:]]  # Skip header
        
        # Hitung berapa yang bisa dikonversi ke angka
        numeric_values = [extract_number(val) for val in values]
        valid_nums = [num for num in numeric_values if num is not None]
        
        if not valid_nums:
            continue
            
        numeric_ratio = len(valid_nums) / len(values)
        
        # Cek apakah ada pola kenaikan
        is_increasing = all(valid_nums[i] < valid_nums[i+1] for i in range(len(valid_nums)-1))
        
        if numeric_ratio > 0.7 and is_increasing and numeric_ratio > max_numeric_ratio:
            max_numeric_ratio = numeric_ratio
            best_col = col_idx
    
    return best_col

def extract_number(text):
    """
    Ekstrak angka dari teks.
    """
    import re
    if not text:
        return None
    
    # Coba ekstrak angka dari berbagai format
    match = re.search(r'^[.\s]*(\d+)[.\s]*$', text.strip())
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass
    return None

def looks_like_header(row, data_rows):
    """
    Tentukan apakah baris terlihat seperti header berdasarkan perbedaan format dengan data.
    """
    if not row or not data_rows:
        return False
    
    # Cek karakteristik header
    header_characteristics = [
        all(cell.strip().istitle() for cell in row if cell.strip()),  # Title case
        all(len(cell.strip()) < 30 for cell in row if cell.strip()),  # Header biasanya pendek
        sum(1 for cell in row if cell.strip() and any(char.isupper() for char in cell)) > len(row) / 2  # Banyak huruf kapital
    ]
    
    # Bandingkan dengan data rows
    data_characteristics = []
    for data_row in data_rows[:3]:  # Ambil sampel 3 baris data
        if len(data_row) == len(row):
            chars = [
                all(cell.strip().istitle() for cell in data_row if cell.strip()),
                all(len(cell.strip()) < 30 for cell in data_row if cell.strip()),
                sum(1 for cell in data_row if cell.strip() and any(char.isupper() for char in cell)) > len(data_row) / 2
            ]
            data_characteristics.append(chars)
    
    if not data_characteristics:
        return sum(1 for char in header_characteristics if char) >= 2
    
    # Jika karakteristik header berbeda dari karakteristik data
    header_score = sum(1 for char in header_characteristics if char)
    data_scores = [sum(1 for char in chars if char) for chars in data_characteristics]
    avg_data_score = sum(data_scores) / len(data_scores) if data_scores else 0
    
    return header_score > avg_data_score + 1

def pad_table(table, target_cols):
    """
    Pad table dengan kolom kosong sampai mencapai jumlah kolom target.
    """
    if not table:
        return table
    
    result = []
    for row in table:
        if len(row) < target_cols:
            new_row = row + [""] * (target_cols - len(row))
            result.append(new_row)
        else:
            result.append(row)
    
    return result

def truncate_table(table, target_cols):
    """
    Potong table menjadi jumlah kolom target.
    """
    if not table:
        return table
    
    return [row[:target_cols] for row in table]

@contextmanager
def managed_pdf_processing():
    """Context manager untuk mengelola resources dan cleanup"""
    temp_dir = tempfile.mkdtemp()
    try:
        yield temp_dir
    finally:
        # Tunggu sebentar untuk memastikan semua proses selesai
        time.sleep(1)
        
        # Bersihkan sumber daya
        gc.collect()
        
        # Coba hapus direktori temporary beberapa kali
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                if os.path.exists(temp_dir):
                    # Pastikan semua file ditutup
                    for root, dirs, files in os.walk(temp_dir):
                        for name in files:
                            file_path = os.path.join(root, name)
                            try:
                                with open(file_path, 'rb'):
                                    pass
                            except:
                                pass
                    
                    time.sleep(1)
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    
                    if not os.path.exists(temp_dir):
                        print(f"Successfully removed temporary directory on attempt {attempt + 1}")
                        break
            except Exception as e:
                print(f"Attempt {attempt + 1} to remove directory failed: {e}")
                if attempt == max_attempts - 1:
                    print(f"Could not remove temporary directory {temp_dir} after {max_attempts} attempts")
                time.sleep(1)

def is_heading(text):
    """
    Cek apakah teks adalah heading berdasarkan karakteristiknya.
    """
    # Menghilangkan spasi di awal dan akhir
    cleaned_text = text.strip()
    
    # Cek pola heading umum
    heading_patterns = [
        r'^BAB\s+[IVXivx0-9]+\s*:?\s*\w+',  # Contoh: "BAB I: Definisi"
        r'^BAB\s+[IVXivx0-9]+',  # Contoh: "BAB I"
        r'^[0-9]+\.\s*[A-Z]',  # Contoh: "1. Definisi"
        r'^[A-Z][A-Za-z\s]+(\.|\:)$',  # Heading yang diakhiri dengan titik atau titik dua
        r'^[IVXivx]+\.\s*[A-Z]'  # Heading dengan angka romawi
    ]
    
    for pattern in heading_patterns:
        if re.match(pattern, cleaned_text):
            return True
    
    # Cek karakteristik lainnya
    if len(cleaned_text) < 100 and cleaned_text.isupper():
        return True
    
    # Cek apakah ini merupakan item daftar dengan konten pendek
    list_patterns = [
        r'^[0-9]+\.\s+\w+$',  # Contoh: "1. Item"
        r'^[a-z]\.\s+\w+$',   # Contoh: "a. Item"
        r'^[A-Z]\.\s+\w+$',   # Contoh: "A. Item"
        r'^[-•]\s+\w+$'       # Contoh: "- Item" atau "• Item"
    ]
    
    for pattern in list_patterns:
        if re.match(pattern, cleaned_text) and len(cleaned_text.split()) < 5:
            return True
    
    return False

def contains_multiple_sentences(text):
    """
    Cek apakah teks mengandung beberapa kalimat (indikasi paragraf, bukan tabel).
    """
    # Hitung jumlah tanda baca yang mengakhiri kalimat
    sentence_end_count = len(re.findall(r'[.!?][\s)]', text))
    return sentence_end_count > 1

def is_likely_table(text):
    """
    Cek apakah teks kemungkinan adalah tabel dengan memperhatikan pola heading.
    """
    # Cek jika teks sangat pendek (< 50 karakter), kemungkinan besar bukan tabel
    if len(text) < 50:
        return False
    
    # Cek jika teks dimulai dengan kata "BAB" atau pola heading lainnya
    if is_heading(text):
        return False
    
    # Cek pola seperti tabel (dengan pemisah kolom)
    if "|" in text or "\t" in text:
        return True
    
    # Hitung jumlah angka dan kata dalam teks
    words = text.split()
    num_words = len(words)
    num_digits = sum(1 for word in words if word.isdigit())
    
    # Cek apakah ada tanda-tanda formatif tabel lainnya
    has_multiple_colons = text.count(':') > 2
    has_multiple_commas = text.count(',') > 4
    
    # Jika terlalu banyak digit relatif terhadap kata, mungkin ini tabel
    if num_digits > num_words * 0.3 and num_words > 10:
        return True
    
    # Jika teks mengandung banyak spasi (indikasi kolom) dan kata panjang
    if num_words > 15 and any(len(word) > 20 for word in words) and (has_multiple_colons or has_multiple_commas):
        return True
    
    # Deteksi pola tabel berdasarkan baris yang memiliki struktur konsisten
    lines = text.split('\n')
    if len(lines) > 3:  # Setidaknya memiliki beberapa baris
        # Hitung jumlah kata per baris
        words_per_line = [len(line.split()) for line in lines if line.strip()]
        # Jika jumlah kata konsisten antar baris, mungkin ini tabel
        if len(set(words_per_line)) < 3 and len(words_per_line) > 0 and statistics.mean(words_per_line) > 3:
            return True
    
    return False

def validate_table(table_content):
    """
    Memvalidasi apakah konten benar-benar tabel.
    """
    # Jika kurang dari 2 baris, mungkin bukan tabel
    if len(table_content) < 2:
        return False
    
    # Jika hanya ada 1 kolom di semua baris, mungkin bukan tabel
    num_columns = [len(row) for row in table_content]
    if max(num_columns) < 2:
        return False
    
    # Periksa konsistensi jumlah kolom (indikasi kuat tabel)
    if len(set(num_columns)) <= 2:  # Izinkan perbedaan kecil
        return True
    
    # Periksa apakah ada konten numerik yang signifikan (ciri tabel data)
    numeric_cells = 0
    total_cells = 0
    
    for row in table_content:
        for cell in row:
            total_cells += 1
            if isinstance(cell, str):
                # Cek apakah sel berisi angka atau pola numerik (tanggal, persentase, dll.)
                if re.search(r'\d+(\.\d+)?%?', cell) or cell.strip().isdigit():
                    numeric_cells += 1
    
    # Jika proporsi sel numerik cukup tinggi, kemungkinan ini tabel data
    if total_cells > 0 and numeric_cells / total_cells > 0.3:
        return True
    
    return False



# Template prompt
template = """
Anda adalah AI Agent yang bertugas membuat **summary informatif** dari sebuah tabel beserta 1-2 kalimat konteks yang diberikan. Tugas Anda adalah:
1. Membaca dan memahami konteks dari 1-2 kalimat yang diberikan.
2. Menganalisis tabel yang disediakan.
3. Menghasilkan summary yang **informal, akurat, dan relevan** dengan konteks dan tabel tersebut.
4. Summary harus fokus pada informasi yang ada di tabel dan kalimat konteks, **tanpa menambahkan informasi baru** yang tidak ada dalam input.
5. Summary harus ringkas dan jelas, karena akan digunakan untuk proses indexing pada sistem RAG.

- Jangan membuat asumsi atau menambahkan informasi yang tidak ada di tabel atau kalimat konteks.
- Tetap fokus pada data yang disediakan.
- Gunakan bahasa formal dan informatif.
- Format hasil harus mencakup:
  - Deskripsi umum tentang konteks tabel.
  - Detail spesifik tentang data yang relevan.
  - Ringkasan distribusi atau pola data yang terlihat dari tabel.

**Konteks:**
{kalimat_konteks}

**Tabel:**
{tabel}
"""

prompt = ChatPromptTemplate.from_template(template)
chain = prompt | model | StrOutputParser()

def process_pdf(filename):
    """Fungsi utama untuk memproses PDF dengan deteksi struktur yang lebih baik"""
    with managed_pdf_processing() as temp_dir:
        try:
            # Proses dengan Unstructured untuk mendapatkan semua elemen
            elements = partition_pdf(
                filename=filename,
                strategy="hi_res",
                infer_table_structure=True,
                temp_dir=temp_dir,
                use_ocr=True,  # Aktifkan OCR
                ocr_languages="eng",  # Sesuaikan dengan bahasa dokumen
                ocr_mode="entire_page"  # Gunakan OCR untuk seluruh halaman
            )

            # Inisialisasi variabel untuk menyimpan hasil akhir
            hasil_detail = []
            hasil_akhir = []

            # Dapatkan daftar nomor halaman unik
            halaman_unik = set(element.metadata.page_number for element in elements if hasattr(element, 'metadata'))

            # Proses setiap halaman
            for page_num in halaman_unik:
                print(f"Memproses halaman {page_num}...")

                # Inisialisasi list untuk satu halaman
                urutan_elemen = []
                hasil_teks = []
                hasil_tabel = []

                # Memproses setiap elemen di halaman ini
                for element in elements:
                    if (
                        hasattr(element, 'metadata') and
                        element.metadata is not None and
                        element.metadata.page_number == page_num
                    ):
                        if (
                            hasattr(element.metadata, "text_as_html") and
                            element.metadata.text_as_html is not None and
                            "table" in element.metadata.text_as_html.lower()
                        ):
                            urutan_elemen.append("tabel")
                        else:
                            cleaned_text = remove_newlines_and_double_spaces(element.text)
                            if not is_nomor_halaman(cleaned_text):
                                # Periksa apakah ini heading atau paragraf sebelum mencoba klasifikasi tabel
                                if is_heading(cleaned_text):
                                    urutan_elemen.append("teks")
                                    hasil_teks.append(cleaned_text)
                                elif contains_multiple_sentences(cleaned_text):
                                    urutan_elemen.append("teks")
                                    hasil_teks.append(cleaned_text)
                                elif is_likely_table(cleaned_text):
                                    urutan_elemen.append("tabel")
                                    hasil_tabel.append([cleaned_text.split()])  # Simpan sebagai tabel
                                else:
                                    urutan_elemen.append("teks")
                                    hasil_teks.append(cleaned_text)

                # Ekstrak semua tabel di halaman ini menggunakan Camelot
                try:
                    tables = camelot.read_pdf(filename, pages=str(page_num))
                    if len(tables) > 0:
                        for table in tables:
                            cleaned_table = remove_newlines_and_double_spaces_from_table(table.df.values.tolist())
                            if cleaned_table and len(cleaned_table) > 1:  # Pastikan setidaknya ada 2 baris (header + data)
                                hasil_tabel.append(cleaned_table)
                    tables._tbls = []
                    del tables
                except Exception as e:
                    print(f"Error extracting tables on page {page_num}: {e}")
                    continue  # Skip to next page if table extraction fails

                # Validate indices before creating hasil_gabungan
                hasil_gabungan = []
                idx_teks = 0
                idx_tabel = 0

                for elemen in urutan_elemen:
                    if elemen == "teks" and idx_teks < len(hasil_teks):
                        hasil_gabungan.append(("teks", hasil_teks[idx_teks]))
                        idx_teks += 1
                    elif elemen == "tabel" and idx_tabel < len(hasil_tabel):
                        hasil_gabungan.append(("tabel", hasil_tabel[idx_tabel]))
                        idx_tabel += 1

                # Process text between tables with proper error handling
                i = 0
                while i < len(hasil_gabungan):
                    try:
                        if hasil_gabungan[i][0] == "teks":
                            cleaned_text = remove_newlines_and_double_spaces(hasil_gabungan[i][1])

                            tabel_sebelum = None
                            tabel_sesudah = None

                            # Look for previous table
                            j = i - 1
                            while j >= 0:
                                if hasil_gabungan[j][0] == "tabel":
                                    tabel_sebelum = hasil_gabungan[j][1]
                                    break
                                j -= 1

                            # Look for next table
                            j = i + 1
                            while j < len(hasil_gabungan):
                                if hasil_gabungan[j][0] == "tabel":
                                    tabel_sesudah = hasil_gabungan[j][1]
                                    break
                                j += 1

                            if tabel_sebelum and is_text_part_of_table_substring(cleaned_text, tabel_sebelum):
                                hasil_gabungan.pop(i)
                                i -= 1
                            elif tabel_sesudah and is_text_part_of_table_substring(cleaned_text, tabel_sesudah):
                                hasil_gabungan.pop(i)
                                i -= 1
                    except Exception as e:
                        print(f"Error processing text at index {i}: {e}")
                        i += 1
                        continue
                    i += 1

                # Add combined results to final results
                hasil_detail.extend(hasil_gabungan)

            # Merge tables across pages with proper error handling
            i = 0
            while i < len(hasil_detail) - 1:
                try:
                    if (
                        hasil_detail[i][0] == "tabel" and
                        hasil_detail[i + 1][0] == "tabel"
                    ):
                        tabel_gabungan = gabungkan_tabel(hasil_detail[i][1], hasil_detail[i + 1][1])
                        if tabel_gabungan:
                            hasil_detail[i] = ("tabel", tabel_gabungan)
                            hasil_detail.pop(i + 1)
                        else:
                            i += 1
                    else:
                        i += 1
                except Exception as e:
                    print(f"Error merging tables at index {i}: {e}")
                    i += 1

            # Pemrosesan akhir dengan validasi tambahan
            for idx, (jenis, konten) in enumerate(hasil_detail):
                try:
                    if jenis == "teks":
                        hasil_akhir.append(konten)

                    if jenis == "tabel":
                        # Validasi lanjutan untuk memastikan ini benar-benar tabel
                        if isinstance(konten, list) and len(konten) == 1 and isinstance(konten[0], list) and len(konten[0]) == 1:
                            # Ini kemungkinan heading yang salah klasifikasi sebagai tabel (satu baris, satu kolom)
                            if is_heading(konten[0][0]):
                                hasil_akhir.append(konten[0][0])  # Tambahkan sebagai teks biasa
                                continue
                            
                        # Validasi struktur tabel
                        if not validate_table(konten):
                            # Jika gagal validasi, perlakukan sebagai teks
                            if isinstance(konten, list) and len(konten) > 0:
                                teks_gabungan = " ".join([" ".join(row) for row in konten if isinstance(row, list)])
                                hasil_akhir.append(teks_gabungan)
                                continue

                        normalisasi_tabel = normalize_table(konten)
                        hasil_detail[idx] = ("tabel", normalisasi_tabel)

                        prev_content = ""
                        if idx > 0 and hasil_detail[idx-1][0] == "teks":
                            prev_content = hasil_detail[idx-1][1]
                        else:
                            prev_content = "No previous content"

                        # Proses summary tabel
                        hasil_summary = chain.invoke({"kalimat_konteks": prev_content, "tabel": normalisasi_tabel})
                        hasil_summary = remove_newlines_and_double_spaces(hasil_summary)
                        hasil_summary = "(START_ACCEESS_DB) " + hasil_summary + " (END_ACCESS_DB)"
                        hasil_akhir.append(hasil_summary)

                        # Write to CSV
                        csv_filename = f'tabel_{idx}.csv'
                        with open(csv_filename, mode='w', newline='', encoding='utf-8') as file:
                            writer = csv.writer(file)
                            writer.writerows(normalisasi_tabel)

                except Exception as e:
                    print(f"Error processing content at index {idx}: {e}")
                    continue

            return hasil_detail, hasil_akhir

        except Exception as e:
            print(f"An error occurred: {e}")
            return None
        finally:
            # Clean up
            if 'elements' in locals():
                del elements
            gc.collect()

if __name__ == "__main__":
    filename = "studi_kasus/7_Tabel_N_Halaman_Normal_V3.pdf"  # Ganti dengan nama file PDF Anda
    detail, hasil = process_pdf(filename)
  
    if hasil:
        print("Hasil Ekstraksi")
        for x in hasil:
            print()
            print("---")
            print(x)
            print("---")
            print()

 