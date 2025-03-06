import google.generativeai as genai
import os
from dotenv import load_dotenv
import mimetypes
import json
import time

# Load environment variables
load_dotenv()

# Get API key from environment variables
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    raise ValueError("Google API Key tidak ditemukan. Pastikan variabel GOOGLE_API_KEY ada di file .env")

# Configure API key
genai.configure(api_key=GOOGLE_API_KEY)

# Initialize model
try:
    model_name = 'gemini-2.0-flash'  # Atau model lain yang sesuai
    model = genai.GenerativeModel(model_name)
except Exception as e:
    print(f"Error initializing model: {e}")
    exit()

# Daftar path file PDF yang ingin diproses
pdf_files = [
    "studi_kasus/v2-cropped-v1.pdf",
    "studi_kasus/v2-cropped-v2.pdf",
    # Tambahkan path file PDF lainnya di sini
]

# Fungsi untuk memproses satu file PDF
def process_pdf(file_path):
    print(f"\n=== Memproses file: {file_path} ===\n")
    
    # Load PDF data
    try:
        with open(file_path, "rb") as pdf_file:
            doc_data = pdf_file.read()
    except FileNotFoundError:
        print(f"Error: File tidak ditemukan di {file_path}")
        return None
    
    # Tentukan MIME type secara otomatis
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = 'application/pdf'  # Default jika tidak terdeteksi
    
    # Prepare content with PDF data
    content = [
        {"mime_type": mime_type, "data": doc_data},
        "in this pdf, there are table. can you extract it and give me an output with json format?"
    ]
    
    # Hitung Token
    try:
        token_count = model.count_tokens(content)
        print(f"Perkiraan jumlah token: {token_count.total_tokens}")
        if token_count.total_tokens > 8192:  # Ganti dengan token limit
            print("Jumlah token melewati batas")
            return None
    except Exception as e:
        print(f"Error calculating token: {e}")
    
    # Generate content dengan streaming
    start_time = time.time()
    print("Memulai ekstraksi dengan mode streaming...")
    
    try:
        response = model.generate_content(content, stream=True)
        
        # Kumpulkan respons dari streaming
        full_response = ""
        for chunk in response:
            full_response += chunk.text
            print(chunk.text, end="", flush=True)
        
        print("\n")  # Baris baru di akhir output
        
        # Hitung waktu pemrosesan
        elapsed_time = time.time() - start_time
        print(f"Waktu pemrosesan: {elapsed_time:.2f} detik")
        
        # Simpan hasil ke file JSON
        output_filename = os.path.basename(file_path).replace('.pdf', '.json')
        with open(output_filename, 'w', encoding='utf-8') as json_file:
            json_file.write(full_response)
        
        print(f"Hasil disimpan ke file: {output_filename}")
        return full_response
        
    except Exception as e:
        print(f"Error saat memproses file {file_path}: {e}")
        return None

# Proses semua file PDF dan simpan hasilnya
results = {}

for pdf_file in pdf_files:
    result = process_pdf(pdf_file)
    if result:
        # Mencoba parse hasil sebagai JSON
        try:
            # Simpan hasil dalam dictionary dengan nama file sebagai key
            filename = os.path.basename(pdf_file)
            results[filename] = json.loads(result)
        except json.JSONDecodeError:
            print(f"Warning: Hasil dari {pdf_file} bukan format JSON yang valid")
            # Simpan hasil mentah jika bukan JSON valid
            results[os.path.basename(pdf_file)] = result

# Simpan semua hasil ke satu file JSON gabungan
try:
    with open("all_results.json", 'w', encoding='utf-8') as all_json:
        json.dump(results, all_json, indent=2, ensure_ascii=False)
    print("\nSemua hasil telah digabung dan disimpan ke all_results.json")
except Exception as e:
    print(f"Error saat menyimpan file gabungan: {e}")