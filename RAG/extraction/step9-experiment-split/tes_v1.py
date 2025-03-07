import google.generativeai as genai
import os
from dotenv import load_dotenv
import mimetypes
import json
import time
from google.api_core import exceptions

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
    "studi_kasus/v2.pdf"
    # "studi_kasus/v2-cropped-v1.pdf",
    # "studi_kasus/v2-cropped-v2.pdf",
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

    try:
        response = model.generate_content(content, stream=False)
        
        response_text = response.text
        print(response_text)

        # return full_response
        
    except exceptions.DeadlineExceeded:
        print("Error: Permintaan melebihi batas waktu (timeout).")
    except Exception as e:
        print(f"Error saat memproses file {file_path}: {e}")
        return None

# Proses semua file PDF dan simpan hasilnya
results = {}

for pdf_file in pdf_files:
    result = process_pdf(pdf_file)
