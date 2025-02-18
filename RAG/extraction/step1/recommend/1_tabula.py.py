import tabula
import pandas as pd
import os

def extract_tables_with_tabula(pdf_path, output_folder="tabula_results"):
    # Buat folder output jika belum ada
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    # Ekstrak semua tabel dari semua halaman dengan deteksi otomatis tabel
    print("Mengekstrak tabel dengan Tabula (mode otomatis)...")
    tables_auto = tabula.read_pdf(pdf_path, pages='all', multiple_tables=True)
    
    print(f"Terdeteksi {len(tables_auto)} tabel dalam mode otomatis")
    
    # Simpan hasil
    for idx, table in enumerate(tables_auto, 1):
        if not table.empty:
            output_path = f"{output_folder}/table_auto_{idx}.csv"
            table.to_csv(output_path, index=False)
            print(f"Tabel {idx} disimpan ke {output_path}")
    
    # Coba dengan area deteksi yang lebih agresif
    print("\nMengekstrak tabel dengan Tabula (mode area)...")
    tables_area = tabula.read_pdf(pdf_path, pages='all', multiple_tables=True, area=(0, 0, 100, 100), relative_area=True)
    
    print(f"Terdeteksi {len(tables_area)} tabel dalam mode area")
    
    # Simpan hasil area
    for idx, table in enumerate(tables_area, 1):
        if not table.empty:
            output_path = f"{output_folder}/table_area_{idx}.csv"
            table.to_csv(output_path, index=False)
            print(f"Tabel {idx} (area) disimpan ke {output_path}")
    
    # Coba dengan mode lattice specifik untuk tabel dengan border
    print("\nMengekstrak tabel dengan Tabula (mode lattice)...")
    tables_lattice = tabula.read_pdf(pdf_path, pages='all', multiple_tables=True, lattice=True)
    
    print(f"Terdeteksi {len(tables_lattice)} tabel dalam mode lattice")
    
    # Simpan hasil lattice
    for idx, table in enumerate(tables_lattice, 1):
        if not table.empty:
            output_path = f"{output_folder}/table_lattice_{idx}.csv"
            table.to_csv(output_path, index=False)
            print(f"Tabel {idx} (lattice) disimpan ke {output_path}")
    
    return tables_auto, tables_area, tables_lattice

# Contoh penggunaan
pdf_path = "studi_kasus/4_Tabel_Satu_Halaman_Normal_V1.pdf"
tables_auto, tables_area, tables_lattice = extract_tables_with_tabula(pdf_path)