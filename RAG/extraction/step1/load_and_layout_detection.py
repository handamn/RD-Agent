import fitz  # PyMuPDF
import pytesseract
from pdf2image import convert_from_path
from unstructured.partition.pdf import partition_pdf

def load_pdf_extract_text(pdf_path):
    """Load PDF and try to extract raw text."""
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text("text")
    return text.strip()

def perform_ocr(pdf_path):
    """Perform OCR using Tesseract if text extraction fails."""
    images = convert_from_path(pdf_path)
    extracted_text = ""
    for img in images:
        extracted_text += pytesseract.image_to_string(img, lang="eng")
    return extracted_text.strip()

def detect_layout(pdf_path):
    print("Detecting Layout...")
    # Pastikan hanya satu parameter yang digunakan
    elements = partition_pdf(filename=pdf_path)  # Hanya filename, tanpa 'file'
    # Proses elemen yang diekstrak
    layout_info = [element.to_dict() for element in elements]
    return layout_info

def process_pdf(pdf_path):
    """Main processing function to handle layout detection and text extraction."""
    print("Loading PDF...")
    extracted_text = load_pdf_extract_text(pdf_path)
    
    if extracted_text:
        print("Text extracted successfully.")
    else:
        print("No extractable text found, performing OCR...")
        extracted_text = perform_ocr(pdf_path)
    
    print("Detecting Layout...")
    layout = detect_layout(pdf_path)
    print(f"Layout detected: {layout}")
    
    return {"text": extracted_text, "layout": layout}

if __name__ == "__main__":
    pdf_file = "studi_kasus/1_Teks_Biasa.pdf"  # Replace with your PDF path
    result = process_pdf(pdf_file)
    print("Final Result:", result)
