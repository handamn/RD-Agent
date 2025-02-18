import pdfplumber
import camelot
import tabula
import pandas as pd
import cv2
import numpy as np
from pdf2image import convert_from_path
import pytesseract
import os
import re
import tempfile

def extract_tables_hybrid(pdf_path, output_folder="hybrid_results"):
    # Buat folder output jika belum ada
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    # Dictionary untuk menyimpan semua hasil
    results = {
        "pdfplumber": [],
        "camelot_lattice": [],
        "camelot_stream": [],
        "tabula": [],
        "ocr": []
    }
    
    # LANGKAH 1: Ekstraksi dengan pdfplumber
    print("\n=== EKSTRAKSI DENGAN PDFPLUMBER ===")
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            tables = page.extract_tables()
            if tables:
                for idx, table in enumerate(tables, 1):
                    df = pd.DataFrame(table)
                    if not df.empty:
                        output_path = f"{output_folder}/pdfplumber_page_{page_num}_table_{idx}.csv"
                        df.to_csv(output_path, index=False)
                        results["pdfplumber"].append({
                            "page": page_num,
                            "table_index": idx, 
                            "path": output_path,
                            "dataframe": df
                        })
                        print(f"pdfplumber: Halaman {page_num}, Tabel {idx} disimpan")
    
    # LANGKAH 2: Ekstraksi dengan camelot (lattice)
    print("\n=== EKSTRAKSI DENGAN CAMELOT (LATTICE) ===")
    try:
        tables_lattice = camelot.read_pdf(pdf_path, pages='all', flavor='lattice')
        if len(tables_lattice) > 0:
            for idx, table in enumerate(tables_lattice, 1):
                page_num = table.page
                output_path = f"{output_folder}/camelot_lattice_page_{page_num}_table_{idx}.csv"
                table.to_csv(output_path)
                results["camelot_lattice"].append({
                    "page": page_num,
                    "table_index": idx, 
                    "path": output_path,
                    "dataframe": table.df,
                    "accuracy": table.accuracy
                })
                print(f"camelot lattice: Halaman {page_num}, Tabel {idx} disimpan (Akurasi: {table.accuracy})")
    except Exception as e:
        print(f"Error dalam ekstraksi camelot lattice: {e}")
    
    # LANGKAH 3: Ekstraksi dengan camelot (stream)
    print("\n=== EKSTRAKSI DENGAN CAMELOT (STREAM) ===")
    try:
        tables_stream = camelot.read_pdf(pdf_path, pages='all', flavor='stream')
        if len(tables_stream) > 0:
            for idx, table in enumerate(tables_stream, 1):
                page_num = table.page
                # Filter tabel berdasarkan akurasi
                if table.accuracy < 50:
                    print(f"camelot stream: Halaman {page_num}, Tabel {idx} diabaikan (Akurasi: {table.accuracy})")
                    continue
                    
                output_path = f"{output_folder}/camelot_stream_page_{page_num}_table_{idx}.csv"
                table.to_csv(output_path)
                results["camelot_stream"].append({
                    "page": page_num,
                    "table_index": idx, 
                    "path": output_path,
                    "dataframe": table.df,
                    "accuracy": table.accuracy
                })
                print(f"camelot stream: Halaman {page_num}, Tabel {idx} disimpan (Akurasi: {table.accuracy})")
    except Exception as e:
        print(f"Error dalam ekstraksi camelot stream: {e}")
    
    # LANGKAH 4: Ekstraksi dengan tabula
    print("\n=== EKSTRAKSI DENGAN TABULA ===")
    try:
        tables_tabula = tabula.read_pdf(pdf_path, pages='all', multiple_tables=True)
        for idx, table in enumerate(tables_tabula, 1):
            if not table.empty:
                output_path = f"{output_folder}/tabula_table_{idx}.csv"
                table.to_csv(output_path, index=False)
                results["tabula"].append({
                    "table_index": idx, 
                    "path": output_path,
                    "dataframe": table
                })
                print(f"tabula: Tabel {idx} disimpan")
    except Exception as e:
        print(f"Error dalam ekstraksi tabula: {e}")
    
    # LANGKAH 5: OCR untuk halaman yang bermasalah
    print("\n=== MENCARI HALAMAN BERMASALAH UNTUK OCR ===")
    problem_pages = identify_problem_pages(results)
    
    if problem_pages:
        print(f"Halaman bermasalah terdeteksi: {problem_pages}")
        
        # Konversi PDF ke gambar
        print("\n=== EKSTRAKSI DENGAN OCR ===")
        images = convert_from_path(pdf_path, 300)  # Resolusi 300 DPI
        
        for page_num in problem_pages:
            if page_num <= len(images):
                image = images[page_num-1]  # Indeks dimulai dari 0
                
                # Simpan gambar sementara
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_img:
                    image_path = tmp_img.name
                    image.save(image_path)
                
                # Preprocess gambar
                processed_image_path = f"{output_folder}/processed_page_{page_num}.png"
                preprocess_for_ocr(image_path, processed_image_path)
                
                # Ekstraksi teks dengan OCR
                ocr_text = pytesseract.image_to_string(processed_image_path)
                
                # Coba konversi teks OCR ke tabel
                table_data = parse_ocr_to_table(ocr_text)
                
                if table_data:
                    df = pd.DataFrame(table_data)
                    output_path = f"{output_folder}/ocr_page_{page_num}_table.csv"
                    df.to_csv(output_path, index=False)
                    results["ocr"].append({
                        "page": page_num,
                        "path": output_path,
                        "dataframe": df
                    })
                    print(f"OCR: Halaman {page_num}, tabel berhasil diekstrak")
    
    # LANGKAH 6: Evaluasi dan pilih hasil terbaik untuk setiap halaman
    print("\n=== HASIL AKHIR ===")
    best_results = evaluate_and_select_best_results(results)
    
    # Simpan hasil terbaik
    for page, data in best_results.items():
        method = data["method"]
        df = data["dataframe"]
        output_path = f"{output_folder}/best_result_page_{page}.csv"
        df.to_csv(output_path, index=False)
        print(f"Halaman {page}: Metode terbaik adalah {method}")
    
    return best_results

def identify_problem_pages(results):
    """Identifikasi halaman yang bermasalah (hasil berbeda antar metode atau tidak ada tabel terdeteksi)"""
    # Set untuk menyimpan semua halaman
    all_pages = set()
    
    # Kumpulkan semua halaman dari hasil pdfplumber, camelot lattice, dan camelot stream
    for method in ["pdfplumber", "camelot_lattice", "camelot_stream"]:
        for result in results[method]:
            if "page" in result:
                all_pages.add(result["page"])
    
    # Identifikasi halaman bermasalah
    problem_pages = []
    
    for page in all_pages:
        # Hitung berapa metode yang mendeteksi tabel di halaman ini
        methods_with_tables = sum(1 for method in ["pdfplumber", "camelot_lattice", "camelot_stream"] 
                                if any(r.get("page") == page for r in results[method]))
        
        # Jika hanya satu atau dua metode yang mendeteksi tabel, mungkin bermasalah
        if 0 < methods_with_tables < 3:
            problem_pages.append(page)
    
    return problem_pages

def preprocess_for_ocr(image_path, output_path):
    # Baca gambar
    img = cv2.imread(image_path)
    
    # Konversi ke grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Thresholding adaptif
    binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                  cv2.THRESH_BINARY, 11, 2)
    
    # Simpan gambar hasil preprocessing
    cv2.imwrite(output_path, binary)
    
    return output_path

def parse_ocr_to_table(ocr_text):
    if not ocr_text.strip():
        return None
    
    # Split berdasarkan baris baru
    lines = ocr_text.split('\n')
    lines = [line.strip() for line in lines if line.strip()]
    
    if not lines:
        return None
    
    # Deteksi pemisah kolom
    table_data = []
    for line in lines:
        # Split berdasarkan dua atau lebih spasi berturut-turut
        row = re.split(r'\s{2,}', line)
        if len(row) > 1:  # Pastikan punya minimal 2 kolom
            table_data.append(row)
    
    # Standarisasi jumlah kolom
    if table_data:
        max_cols = max(len(row) for row in table_data)
        for i, row in enumerate(table_data):
            if len(row) < max_cols:
                table_data[i] = row + [''] * (max_cols - len(row))
    
    return table_data

def evaluate_and_select_best_results(results):
    """Evaluasi dan pilih hasil terbaik untuk setiap halaman"""
    best_results = {}
    
    # Kumpulkan semua halaman
    all_pages = set()
    
    for method in ["pdfplumber", "camelot_lattice", "camelot_stream", "ocr"]:
        for result in results[method]:
            if "page" in result:
                all_pages.add(result["page"])
    
    # Evaluasi setiap halaman
    for page in all_pages:
        best_score = -1
        best_method = None
        best_df = None
        
        # Cek hasil pdfplumber
        pdfplumber_results = [r for r in results["pdfplumber"] if r.get("page") == page]
        if pdfplumber_results:
            # Heuristik: jumlah sel (baris * kolom) dan tidak ada sel kosong
            for result in pdfplumber_results:
                df = result["dataframe"]
                score = df.shape[0] * df.shape[1] - df.isna().sum().sum()
                if score > best_score:
                    best_score = score
                    best_method = "pdfplumber"
                    best_df = df
        
        # Cek hasil camelot lattice
        camelot_lattice_results = [r for r in results["camelot_lattice"] if r.get("page") == page]
        if camelot_lattice_results:
            for result in camelot_lattice_results:
                # Heuristik: ukuran tabel * akurasi
                df = result["dataframe"]
                score = df.shape[0] * df.shape[1] * result["accuracy"] / 100
                if score > best_score:
                    best_score = score
                    best_method = "camelot_lattice"
                    best_df = df
        
        # Cek hasil camelot stream
        camelot_stream_results = [r for r in results["camelot_stream"] if r.get("page") == page]
        if camelot_stream_results:
            for result in camelot_stream_results:
                # Heuristik: ukuran tabel * akurasi
                df = result["dataframe"]
                score = df.shape[0] * df.shape[1] * result["accuracy"] / 100
                if score > best_score:
                    best_score = score
                    best_method = "camelot_stream"
                    best_df = df
        
        # Cek hasil OCR
        ocr_results = [r for r in results["ocr"] if r.get("page") == page]
        if ocr_results and not best_method:  # OCR adalah pilihan terakhir
            for result in ocr_results:
                df = result["dataframe"]
                score = df.shape[0] * df.shape[1] - df.isna().sum().sum()
                if score > 0:  # Minimal ada beberapa sel dengan data
                    best_score = score
                    best_method = "ocr"
                    best_df = df
        
        # Tambahkan hasil terbaik
        if best_method:
            best_results[page] = {
                "method": best_method,
                "dataframe": best_df,
                "score": best_score
            }
    
    return best_results

# Contoh penggunaan
pdf_path = "studi_kasus/4_Tabel_Satu_Halaman_Normal_V1.pdf"
best_results = extract_tables_hybrid(pdf_path)