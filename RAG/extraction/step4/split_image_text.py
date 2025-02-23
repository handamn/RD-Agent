import tempfile
import os
from unstructured.partition.pdf import partition_pdf
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
from PIL import Image
import fitz  # PyMuPDF

load_dotenv()

embd = OpenAIEmbeddings(model="text-embedding-3-small")
model = ChatOpenAI(model_name="gpt-4o-mini", temperature=0)

LANGCHAIN_TRACING_V2 = os.getenv('LANGCHAIN_TRACING_V2')
LANGCHAIN_ENDPOINT = os.getenv('LANGCHAIN_ENDPOINT')
LANGCHAIN_API_KEY = os.getenv('LANGCHAIN_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

def convert_to_structured_string(data):
    columns = data[0]
    structured_strings = []
    for row in data[1:]:
        row_string = ", ".join([f"{columns[i]}: {row[i]}" for i in range(len(columns))])
        structured_strings.append(row_string)
    return structured_strings

def convert_to_json(data):
    columns = data[0]
    rows = []
    for row in data[1:]:
        row_dict = {columns[i]: row[i] for i in range(len(columns))}
        rows.append(row_dict)
    return {"columns": columns, "rows": rows}

def remove_newlines_and_double_spaces(text):
    text = text.replace("\n", " ")
    while "  " in text:
        text = text.replace("  ", " ")
    while "—__" in text:
        text = text.replace("—__", " ")
    return text.strip()

def remove_newlines_and_double_spaces_from_table(table):
    return [[remove_newlines_and_double_spaces(cell) for cell in row] for row in table]

def normalize_table(table):
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
    for row in table:
        combined_row = " ".join([cell.strip() for cell in row if cell.strip()])
        if text in combined_row:
            return True
    return False

def is_nomor_halaman(teks):
    return teks.strip().isdigit()

def calculate_column_similarity(row1, row2):
    if abs(len(row1) - len(row2)) > 2:
        return 0.0
    max_cols = max(len(row1), len(row2))
    min_cols = min(len(row1), len(row2))
    column_count_similarity = min_cols / max_cols if max_cols > 0 else 0
    data_type_matches = 0
    checked_columns = min(len(row1), len(row2))
    for i in range(checked_columns):
        cell1_is_numeric = bool(re.match(r'^[-+]?\d+(\.\d+)?%?$', row1[i].strip()))
        cell2_is_numeric = bool(re.match(r'^[-+]?\d+(\.\d+)?%?$', row2[i].strip()))
        if cell1_is_numeric == cell2_is_numeric:
            data_type_matches += 1
    data_type_similarity = data_type_matches / checked_columns if checked_columns > 0 else 0
    length_similarity_scores = []
    for i in range(checked_columns):
        len1 = len(row1[i].strip())
        len2 = len(row2[i].strip())
        max_len = max(len1, len2)
        if max_len > 0:
            length_similarity_scores.append(min(len1, len2) / max_len)
    avg_length_similarity = (
        sum(length_similarity_scores) / len(length_similarity_scores)
        if length_similarity_scores else 0
    )
    weights = {
        'column_count': 0.4,
        'data_type': 0.4,
        'length': 0.2
    }
    similarity = (
        weights['column_count'] * column_count_similarity +
        weights['data_type'] * data_type_similarity +
        weights['length'] * avg_length_similarity
    )
    return similarity

def is_data_row_not_header(row):
    if not row or all(not cell.strip() for cell in row):
        return False
    header_indicators = ['jenis', 'nama', 'keterangan', 'nomor', 'jumlah', 'total']
    header_pattern_count = 0
    for cell in row:
        cell_lower = cell.lower().strip()
        if any(ind in cell_lower for ind in header_indicators):
            header_pattern_count += 1
    if header_pattern_count >= 2 or header_pattern_count > len(row) / 3:
        return False
    non_empty_cells = [cell for cell in row if cell.strip()]
    if not non_empty_cells:
        return False
    numeric_cells = 0
    data_pattern_cells = 0
    for cell in non_empty_cells:
        cell = cell.strip()
        if re.match(r'^[-+]?\d+(\.\d+)?%?$', cell):
            numeric_cells += 1
            data_pattern_cells += 1
            continue
        if "Maks." in cell or "maks." in cell:
            data_pattern_cells += 1
            continue
        if re.search(r'(Rp\.?\s*\d+|\d+\s*%|\$\s*\d+)', cell):
            data_pattern_cells += 1
            continue
        continuation_phrases = ["dari", "untuk", "dengan", "sampai", "hingga", "oleh", "pada", "dalam"]
        if any(phrase in cell.lower() for phrase in continuation_phrases):
            data_pattern_cells += 1
            continue
    data_ratio = data_pattern_cells / len(non_empty_cells) if non_empty_cells else 0
    return data_ratio > 0.25 or numeric_cells >= 1

def detect_header_row(table):
    if not table or len(table) < 2:
        return None
    candidate_rows = min(3, len(table))
    for i in range(candidate_rows):
        row = table[i]
        non_numeric_cells = sum(1 for cell in row if not re.match(r'^[-+]?\d+(\.\d+)?%?$', cell.strip()))
        is_likely_header = (
            i == 0 or
            non_numeric_cells == len(row) or
            all(len(cell.strip()) < 30 for cell in row)
        )
        if is_likely_header:
            return i
    return 0

def gabungkan_tabel(tabel_sebelum, tabel_sesudah):
    if not tabel_sebelum or not tabel_sesudah:
        return None
    header_idx_first = detect_header_row(tabel_sebelum)
    if header_idx_first is None:
        header_idx_first = 0
    header_first_table = tabel_sebelum[header_idx_first]
    if tabel_sebelum[0] == tabel_sesudah[0]:
        return tabel_sebelum + tabel_sesudah[1:]
    if len(tabel_sesudah) > 0:
        last_row_first_table = tabel_sebelum[-1]
        first_row_second_table = tabel_sesudah[0]
        is_truncated_text = False
        if len(last_row_first_table) > 0:
            last_cell = last_row_first_table[-1].strip()
            if (last_cell.endswith("dan") or last_cell.endswith("atau") or
                last_cell.endswith(",") or last_cell.endswith(";") or
                not any(c in ".!?" for c in last_cell)):
                is_truncated_text = True
        is_continuation_data = False
        if len(first_row_second_table) > 0:
            is_data_row = is_data_row_not_header(first_row_second_table)
            col_similarity = calculate_column_similarity(last_row_first_table, first_row_second_table)
            first_cell_second_table = first_row_second_table[0].strip() if len(first_row_second_table) > 0 else ""
            continuation_indicators = ["Penyertaan", "dan", "atau", "jika", "serta", "dengan", "oleh", "yang", "untuk"]
            starts_with_lowercase = first_cell_second_table and first_cell_second_table[0].islower()
            starts_with_continuation = any(first_cell_second_table.startswith(ind) for ind in continuation_indicators)
            is_continuation_data = (is_data_row or col_similarity > 0.5 or
                                  starts_with_lowercase or starts_with_continuation or
                                  is_truncated_text)
        if is_continuation_data:
            tabel_sesudah_adjusted = []
            for row in tabel_sesudah:
                if len(row) < len(header_first_table):
                    adjusted_row = row + [''] * (len(header_first_table) - len(row))
                elif len(row) > len(header_first_table):
                    if len(row) <= len(header_first_table) + 2:
                        excess_content = ' '.join(row[len(header_first_table):])
                        adjusted_row = row[:len(header_first_table)-1] + [row[len(header_first_table)-1] + " " + excess_content]
                    else:
                        adjusted_row = row[:len(header_first_table)]
                else:
                    adjusted_row = row
                tabel_sesudah_adjusted.append(adjusted_row)
            return tabel_sebelum + tabel_sesudah_adjusted
    if len(tabel_sebelum) > 0 and len(tabel_sesudah) > 0:
        if abs(len(tabel_sebelum[0]) - len(tabel_sesudah[0])) <= 2:
            if len(tabel_sesudah) >= 1 and len(tabel_sesudah[0]) >= 2:
                adjusted_second_table = []
                for row in tabel_sesudah:
                    if len(row) < len(header_first_table):
                        adjusted_row = row + [''] * (len(header_first_table) - len(row))
                    elif len(row) > len(header_first_table):
                        adjusted_row = row[:len(header_first_table)]
                    else:
                        adjusted_row = row
                    adjusted_second_table.append(adjusted_row)
                return tabel_sebelum + adjusted_second_table
    return None

@contextmanager
def managed_pdf_processing():
    temp_dir = tempfile.mkdtemp()
    try:
        yield temp_dir
    finally:
        time.sleep(1)
        gc.collect()
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                if os.path.exists(temp_dir):
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
    cleaned_text = text.strip()
    heading_patterns = [
        r'^BAB\s+[IVXivx0-9]+\s*:?\s*\w+',
        r'^BAB\s+[IVXivx0-9]+',
        r'^[0-9]+\.\s*[A-Z]',
        r'^[A-Z][A-Za-z\s]+(\.|\:)$',
        r'^[IVXivx]+\.\s*[A-Z]'
    ]
    for pattern in heading_patterns:
        if re.match(pattern, cleaned_text):
            return True
    if len(cleaned_text) < 100 and cleaned_text.isupper():
        return True
    list_patterns = [
        r'^[0-9]+\.\s+\w+$',
        r'^[a-z]\.\s+\w+$',
        r'^[A-Z]\.\s+\w+$',
        r'^[-•]\s+\w+$'
    ]
    for pattern in list_patterns:
        if re.match(pattern, cleaned_text) and len(cleaned_text.split()) < 5:
            return True
    return False

def contains_multiple_sentences(text):
    sentence_end_count = len(re.findall(r'[.!?][\s)]', text))
    return sentence_end_count > 1

def is_likely_table(text):
    if len(text) < 50:
        return False
    if is_heading(text):
        return False
    if "|" in text or "\t" in text:
        return True
    words = text.split()
    num_words = len(words)
    num_digits = sum(1 for word in words if word.isdigit())
    has_multiple_colons = text.count(':') > 2
    has_multiple_commas = text.count(',') > 4
    if num_digits > num_words * 0.3 and num_words > 10:
        return True
    if num_words > 15 and any(len(word) > 20 for word in words) and (has_multiple_colons or has_multiple_commas):
        return True
    lines = text.split('\n')
    if len(lines) > 3:
        words_per_line = [len(line.split()) for line in lines if line.strip()]
        if len(set(words_per_line)) < 3 and len(words_per_line) > 0 and statistics.mean(words_per_line) > 3:
            return True
    return False

def validate_table(table_content):
    if len(table_content) < 2:
        return False
    num_columns = [len(row) for row in table_content]
    if max(num_columns) < 2:
        return False
    if len(set(num_columns)) <= 2:
        return True
    numeric_cells = 0
    total_cells = 0
    for row in table_content:
        for cell in row:
            total_cells += 1
            if isinstance(cell, str):
                if re.search(r'\d+(\.\d+)?%?', cell) or cell.strip().isdigit():
                    numeric_cells += 1
    if total_cells > 0 and numeric_cells / total_cells > 0.3:
        return True
    return False

def is_table_continued(previous_table, next_table):
    if not previous_table or not next_table:
        return False
    last_row_previous = previous_table[-1]
    first_row_next = next_table[0]
    last_cell_previous = last_row_previous[-1].strip()
    is_truncated = (last_cell_previous.endswith("dan") or
                    last_cell_previous.endswith("atau") or
                    last_cell_previous.endswith(",") or
                    last_cell_previous.endswith(";") or
                    not any(c in ".!?" for c in last_cell_previous))
    first_cell_next = first_row_next[0].strip()
    is_continuation = (first_cell_next.startswith("dan") or
                       first_cell_next.startswith("atau") or
                       first_cell_next.startswith("jika") or
                       first_cell_next.startswith("serta") or
                       first_cell_next[0].islower())
    return is_truncated and is_continuation

def take_screenshot(pdf_path, page_num, bbox, output_path):
    doc = fitz.open(pdf_path)
    page = doc.load_page(page_num - 1)
    zoom = 2  # Zoom factor for better quality
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, clip=bbox)
    pix.save(output_path)
    doc.close()

def process_pdf(filename):
    with managed_pdf_processing() as temp_dir:
        try:
            elements = partition_pdf(
                filename=filename,
                strategy="hi_res",
                infer_table_structure=True,
                temp_dir=temp_dir,
                use_ocr=True,
                ocr_languages="eng",
                ocr_mode="entire_page"
            )

            hasil_detail = []
            hasil_akhir = []
            halaman_unik = set(element.metadata.page_number for element in elements if hasattr(element, 'metadata'))

            for page_num in halaman_unik:
                print(f"Memproses halaman {page_num}...")
                urutan_elemen = []
                hasil_teks = []
                hasil_tabel = []

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
                                if is_heading(cleaned_text):
                                    urutan_elemen.append("teks")
                                    hasil_teks.append(cleaned_text)
                                elif contains_multiple_sentences(cleaned_text):
                                    urutan_elemen.append("teks")
                                    hasil_teks.append(cleaned_text)
                                elif is_likely_table(cleaned_text):
                                    urutan_elemen.append("tabel")
                                    hasil_tabel.append([cleaned_text.split()])
                                else:
                                    urutan_elemen.append("teks")
                                    hasil_teks.append(cleaned_text)

                try:
                    tables = camelot.read_pdf(filename, pages=str(page_num))
                    if len(tables) > 0:
                        for table in tables:
                            cleaned_table = remove_newlines_and_double_spaces_from_table(table.df.values.tolist())
                            if cleaned_table and len(cleaned_table) > 1:
                                hasil_tabel.append(cleaned_table)
                                # Take screenshot of the table
                                bbox = table._bbox
                                output_path = f"table_page_{page_num}_{len(hasil_tabel)}.png"
                                take_screenshot(filename, page_num, bbox, output_path)
                    tables._tbls = []
                    del tables
                except Exception as e:
                    print(f"Error extracting tables on page {page_num}: {e}")
                    continue

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

                hasil_detail.extend(hasil_gabungan)

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

            for idx, (jenis, konten) in enumerate(hasil_detail):
                try:
                    if jenis == "teks":
                        hasil_akhir.append(konten)

                    if jenis == "tabel":
                        if isinstance(konten, list) and len(konten) == 1 and isinstance(konten[0], list) and len(konten[0]) == 1:
                            if is_heading(konten[0][0]):
                                hasil_akhir.append(konten[0][0])
                                continue
                        if not validate_table(konten):
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

                        hasil_summary = chain.invoke({"kalimat_konteks": prev_content, "tabel": normalisasi_tabel})
                        hasil_summary = remove_newlines_and_double_spaces(hasil_summary)
                        hasil_summary = "(START_ACCEESS_DB) " + hasil_summary + " (END_ACCESS_DB)"
                        hasil_akhir.append(hasil_summary)

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
            if 'elements' in locals():
                del elements
            gc.collect()

if __name__ == "__main__":
    filename = "studi_kasus/7_Tabel_N_Halaman_Normal_V1.pdf"
    detail, hasil = process_pdf(filename)
  
    if hasil:
        print("Hasil Ekstraksi")
        for x in hasil:
            print()
            print("---")
            print(x)
            print("---")
            print()