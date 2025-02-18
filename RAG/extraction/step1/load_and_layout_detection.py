import fitz  # PyMuPDF
from pdfminer.high_level import extract_text
import pytesseract
from PIL import Image
import io

def load_pdf(file_path):
    """Load PDF and extract raw text."""
    doc = fitz.open(file_path)
    return doc

def has_extractable_text(doc):
    """Check if the PDF has extractable text."""
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        text = page.get_text()
        if text.strip():
            return True
    return False

def perform_ocr(page):
    """Perform OCR on a page."""
    pix = page.get_pixmap()
    img = Image.open(io.BytesIO(pix.tobytes()))
    text = pytesseract.image_to_string(img)
    return text

def detect_layout(page):
    """Detect layout (single or multi-column)."""
    # This is a simplified example. In practice, you might need a more sophisticated approach.
    text = page.get_text("blocks")
    if len(text) > 1:
        return "multi"
    return "single"

def split_sections(page, layout):
    """Split sections based on layout."""
    if layout == "single":
        return [page.get_text()]
    else:
        # Implement multi-column splitting logic here
        return page.get_text("blocks")

def process_pdf(file_path):
    """Process PDF according to the flowchart."""
    doc = load_pdf(file_path)
    metadata = []

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        if has_extractable_text(doc):
            layout = detect_layout(page)
            sections = split_sections(page, layout)
        else:
            ocr_text = perform_ocr(page)
            sections = [ocr_text]

        metadata.append({
            "page": page_num + 1,
            "layout": layout,
            "sections": sections,
            "extractable": has_extractable_text(doc)
        })

    return metadata

# Example usage
file_path = "studi_kasus/1_Teks_Biasa.pdf"
metadata = process_pdf(file_path)
print(metadata)