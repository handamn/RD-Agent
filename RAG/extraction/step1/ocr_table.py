import pytesseract
from pdf2image import convert_from_path
import cv2
import numpy as np
import re

def preprocess_image(image):
    # Convert to grayscale
    gray = cv2.cvtColor(np.array(image), cv2.COLOR_BGR2GRAY)
    
    # Apply thresholding to get a binary image
    _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
    
    # Noise reduction using morphological operations
    kernel = np.ones((1, 1), np.uint8)
    processed_image = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    
    return processed_image

def extract_text_with_tesseract(pdf_path):
    # Konversi PDF ke gambar
    images = convert_from_path(pdf_path)
    
    # Ekstrak teks dari setiap gambar menggunakan Tesseract OCR
    extracted_text = ""
    for image in images:
        # Preprocess the image
        processed_image = preprocess_image(image)
        
        # Use Tesseract OCR with custom configuration
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(processed_image, config=custom_config)
        extracted_text += text + "\n"
    
    return extracted_text

def clean_ocr_text(text):
    # Remove unwanted characters and normalize spaces
    text = re.sub(r'\s+', ' ', text)  # Normalize spaces
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)  # Remove non-ASCII characters
    return text.strip()

def extract_tables_from_text(text):
    # Split text into lines
    lines = text.split('\n')
    
    # Initialize variables to store tables
    tables = []
    current_table = []
    
    # Iterate through lines to detect tables
    for line in lines:
        if re.match(r'^\s*[\d.,]+\s+[\d.,]+\s+[\d.,]+\s*$', line):  # Detect lines with numbers
            current_table.append(line.split())
        else:
            if current_table:
                tables.append(current_table)
                current_table = []
    
    if current_table:
        tables.append(current_table)
    
    return tables

def process_pdf(filename):
    try:
        # Extract text from PDF using Tesseract OCR
        text = extract_text_with_tesseract(filename)
        
        # Clean the OCR text
        cleaned_text = clean_ocr_text(text)
        
        # Extract tables from the cleaned text
        tables = extract_tables_from_text(cleaned_text)
        
        # Process and print tables
        for i, table in enumerate(tables):
            print(f"Table {i+1}:")
            for row in table:
                print(row)
            print()
        
        return tables
    
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

if __name__ == "__main__":
    filename = "studi_kasus/25_OCR_Tabel_Satu_Halaman_Merge_V1.pdf"  # Ganti dengan nama file PDF Anda
    tables = process_pdf(filename)