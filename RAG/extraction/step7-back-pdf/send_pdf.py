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
    # Coba beberapa model yang mungkin. Lebih spesifik lebih baik.
    model_name = 'gemini-2.0-flash'  # Atau model lain yang sesuai
    model = genai.GenerativeModel(model_name)
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


# Hitung Token
try:
    token_count = model.count_tokens(content)
    print(f"Perkiraan jumlah token: {token_count.total_tokens}")
    # Tambahkan pengecekan batas token di sini, jika perlu.
    if token_count.total_tokens > 8192:  #Ganti dengan token limit
        print("Jumlah token melewati batas")
        exit()
except Exception as e:
     print(f"Error calculating token: {e}")


# Generate content
try:
    # Gunakan streaming jika didukung dan sering timeout.
    # response = model.generate_content(content, stream=True)  # Ubah ke True jika ingin streaming
    
    response = model.generate_content(content, stream=True)
    full_response = ""
    for chunk in response:
        full_response += chunk.text
        print(chunk.text, end="", flush=True)
    
    
    #Jika streaming
    # for chunk in response:
    #      print(chunk.text, end="", flush=True) #flush=True agar output tidak di buffer
    # print()

except genai.APIError as e:
    print(f"API Error: {e}")  # Tangani error API secara spesifik
    if e.code == 429:
        print("Rate limit exceeded.  Implement retry with backoff.")
    elif e.code == 504:
        print("Request timed out.  Optimize prompt or use streaming.")
    # Tambahkan penanganan error lain sesuai kebutuhan.
    exit()
except Exception as e:
    print(f"General error generating content: {e}")
    exit()

# Process the response
try:
    response_text = response.text #Kalau tidak streaming
    print(f"API Response received. Length: {len(response_text)} characters")
    print(response_text)
except Exception as e:
    print(f"Error processing response: {e}")