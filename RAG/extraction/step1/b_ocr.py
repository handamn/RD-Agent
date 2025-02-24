import pdfplumber
import openai
import cv2
import numpy as np
import os
from PIL import Image
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def extract_text_from_pdf(pdf_path):
    text_data = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_data += text + "\n"
    return text_data

def detect_tables(pdf_path):
    tables = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            table_boxes = page.extract_tables()
            if table_boxes:
                tables.append((page_num, page.bbox))
    return tables

def crop_table_from_pdf(pdf_path, table_info, output_folder="tables"):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    table_images = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, (page_num, bbox) in enumerate(table_info):
            page = pdf.pages[page_num]
            img = page.to_image().annotated
            cropped_img = img.crop((bbox[0], bbox[1], bbox[2], bbox[3]))
            img_path = os.path.join(output_folder, f"table_{i}.png")
            cropped_img.save(img_path)
            table_images.append(img_path)
    return table_images

def extract_table_from_image(image_path, openai_api_key):
    with open(image_path, "rb") as image_file:
        image_data = image_file.read()
    
    client = openai.OpenAI(api_key=openai_api_key)
    response = client.chat.completions.create(
    model="gpt-4-turbo",
    messages=[
        {"role": "system", "content": "Extract table data from the image."},
        {"role": "user", "content": [
            {"type": "image_url", "image_url": f"data:image/png;base64,{image_data}"}
        ]}
    ]
)

    return response.choices[0].message.content

def process_pdf(pdf_path, openai_api_key):
    text = extract_text_from_pdf(pdf_path)
    tables = detect_tables(pdf_path)
    table_images = crop_table_from_pdf(pdf_path, tables)
    
    extracted_tables = []
    for img_path in table_images:
        extracted_tables.append(extract_table_from_image(img_path, openai_api_key))
    
    return text, extracted_tables

if __name__ == "__main__":
    pdf_path = "studi_kasus/7_Tabel_N_Halaman_Normal_V1.pdf"  # Ganti dengan path PDF yang ingin diproses
    openai_api_key = os.getenv('OPENAI_API_KEY')  # Mengambil API Key dari environment variables
    text, tables = process_pdf(pdf_path, openai_api_key)
    
    print("Extracted Text:")
    print(text)
    print("\nExtracted Tables:")
    for table in tables:
        print(table)
