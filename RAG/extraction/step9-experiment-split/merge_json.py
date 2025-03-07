import json
import pandas as pd
from glob import glob

def merge_json_files(input_files, output_file):
    """
    Menggabungkan beberapa file JSON hasil ekstraksi PDF yang dipotong.
    - Menyatukan teks & tabel secara urut.
    - Menggunakan header dari file pertama sebagai acuan.
    - File kedua dan seterusnya akan mengganti headernya mengikuti urutan header file pertama.
    - Menghapus duplikasi data akibat overlap potongan PDF.
    """
    merged_data = []
    tables = []
    reference_headers = None
    first_table = True
    
    for file in input_files:
        with open(file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for item in data:
            if item['type'] == 'text':
                merged_data.append(item)  # Tambahkan teks secara langsung
            elif item['type'] == 'table':
                if first_table and item['headers']:
                    reference_headers = item['headers']  # Simpan header pertama sebagai acuan
                    first_table = False
                
                # Jika file kedua dan seterusnya memiliki header berbeda, ubah sesuai urutan file pertama
                if not first_table and len(item['headers']) == len(reference_headers):
                    column_mapping = dict(zip(item['headers'], reference_headers))
                    item['rows'] = [
                        {column_mapping.get(k, k): v for k, v in row.items()} for row in item['rows']
                    ]
                    item['headers'] = reference_headers  # Gunakan header dari file pertama
                
                tables.extend(item['rows'])  # Kumpulkan semua data tabel
    
    # Konversi tabel menjadi DataFrame untuk menghapus duplikasi
    df = pd.DataFrame(tables, columns=reference_headers)
    
    df.drop_duplicates(inplace=True)  # Hapus duplikasi akibat overlap
    
    # Tambahkan tabel ke hasil akhir
    merged_data.append({
        "type": "table",
        "page_number": [],
        "headers": reference_headers,
        "rows": df.to_dict(orient='records')
    })
    
    # Simpan hasil sebagai JSON baru
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(merged_data, f, indent=4, ensure_ascii=False)
    
    print(f"Merge selesai! Hasil disimpan di {output_file}")

# Contoh penggunaan
input_files = glob("temp_json/*.json")  # Ganti folder menjadi 'temp_json'
merge_json_files(input_files, "merged_result.json")
