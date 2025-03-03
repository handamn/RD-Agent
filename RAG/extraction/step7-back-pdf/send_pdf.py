import google.generativeai as genai
import os
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
try:
    model = genai.GenerativeModel('gemini-2.0-flash')  # atau sesuaikan jika gemini-2.0-flash tersedia
except Exception as e:
    print(f"Error initializing model: {e}")
    exit()

# Load PDF data
file_path = "studi_kasus/v2.pdf"  # Ganti dengan path file PDF Anda

try:
    with open(file_path, "rb") as pdf_file:
        doc_data = pdf_file.read()
except FileNotFoundError:
    print(f"Error: File tidak ditemukan di {file_path}")
    exit()

# Tentukan MIME type secara otomatis
mime_type, _ = mimetypes.guess_type(file_path)
if not mime_type:
    mime_type = 'application/pdf'  # Default jika tidak terdeteksi


# Prepare content with PDF data
content = [
    {"mime_type": mime_type, "data": doc_data},
    "in this pdf, there are table. can you extract it and give me an output with json format?"
]

# Generate content
try:
    response = model.generate_content(content)
except Exception as e:
    print(f"Error generating content: {e}")
    exit()

# Process the response
try:
    response_text = response.text
    print(f"API Response received. Length: {len(response_text)} characters")
    print(response_text)  # Tampilkan hasil
except Exception as e:
    print(f"Error processing response: {e}")