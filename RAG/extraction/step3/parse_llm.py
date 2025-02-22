import PIL.Image
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

image_path_1 = "image/7_Tabel_N_Halaman_Normal_V1_page-0001.jpg"  # Replace with the actual path to your first image
image_path_2 = "image/7_Tabel_N_Halaman_Normal_V1_page-0002.jpg" # Replace with the actual path to your second image

pil_image_1 = PIL.Image.open(image_path_1)
pil_image_2 = PIL.Image.open(image_path_2)


client = genai.Client(api_key=GOOGLE_API_KEY)
response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents=["apakah kamu bisa melakukan ekstraksi tabel dari file pdf yang saya berikan ini? serta outputnya kalau bisa dalam bentuk json",
              pil_image_1, pil_image_2])

print(response.text)