"""
ocr_extractor.py - Module for OCR-based PDF text extraction
For pages where OCR is needed but no special formatting is detected
"""

import os
import json
import time
import datetime
import pytesseract
import fitz  # PyMuPDF
import PyPDF2
import numpy as np
import cv2
from PIL import Image
from pathlib import Path

def extract_with_ocr_method(pdf_path, page_num, existing_result=None, dpi=300):
    """
    Extract text from PDF using OCR for pages that need OCR processing
    but don't have complex formatting.
    
    Args:
        pdf_path (str): Path to the PDF file
        page_num (int): Page number to extract (1-based indexing)
        existing_result (dict, optional): Existing extraction result to update
        dpi (int): DPI resolution for rendering PDF to image
        
    Returns:
        dict: The extraction result for the specified page
    """
    start_time = time.time()
    
    # Create result structure if not provided
    if existing_result is None:
        result = {
            "analysis": {
                "ocr_status": True,
                "line_status": False,
                "ai_status": False
            },
            "extraction": {
                "method": "ocr",
                "processing_time": None,
                "content_blocks": []
            }
        }
    else:
        result = existing_result
        # Set extraction method and initialize content blocks if they don't exist
        result["extraction"] = {
            "method": "ocr",
            "processing_time": None,
            "content_blocks": []
        }
    
    try:
        # Convert PDF page to image using PyMuPDF
        doc = fitz.open(pdf_path)
        
        # Adjust for 0-based indexing
        pdf_page_index = page_num - 1
        
        if pdf_page_index < 0 or pdf_page_index >= len(doc):
            raise ValueError(f"Page {page_num} does not exist in PDF with {len(doc)} pages")
        
        page = doc[pdf_page_index]
        
        # Render page to image at specified DPI
        pix = page.get_pixmap(dpi=dpi)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        
        # Convert to RGB if needed
        if pix.n == 4:  # RGBA
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
        elif pix.n == 1:  # Grayscale
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
        
        # Convert to PIL image for Tesseract
        pil_img = Image.fromarray(img)
        
        # Perform OCR
        text = pytesseract.image_to_string(pil_img)
        
        # Get text blocks with position information
        ocr_data = pytesseract.image_to_data(pil_img, output_type=pytesseract.Output.DICT)
        
        # Process OCR data to extract structured content
        content_blocks = process_ocr_data(ocr_data, text)
        
        # Add content blocks to result
        if content_blocks:
            result["extraction"]["content_blocks"] = content_blocks
        else:
            # Fallback if structured extraction fails
            result["extraction"]["content_blocks"].append({
                "block_id": 1,
                "type": "text",
                "content": text.strip() if text and text.strip() else "No text content could be extracted via OCR from this page."
            })
                
    except Exception as e:
        # Handle extraction errors
        result["extraction"]["content_blocks"].append({
            "block_id": 1,
            "type": "text",
            "content": f"Error during OCR extraction: {str(e)}"
        })
    
    # Calculate and record processing time
    processing_time = time.time() - start_time
    result["extraction"]["processing_time"] = f"{processing_time:.2f} seconds"
    
    return result

def process_ocr_data(ocr_data, full_text):
    """
    Process OCR data to extract structured content blocks
    
    Args:
        ocr_data (dict): Dictionary with OCR data from pytesseract
        full_text (str): Full text extracted via OCR
        
    Returns:
        list: List of content blocks
    """
    content_blocks = []
    
    try:
        # Process recognized text into blocks
        current_block = {"text": "", "conf": 0, "count": 0}
        blocks = []
        
        # Group text by paragraph/block
        for i, text in enumerate(ocr_data["text"]):
            if text.strip():
                current_block["text"] += f"{text} "
                current_block["conf"] += ocr_data["conf"][i]
                current_block["count"] += 1
            elif current_block["text"].strip():
                # End of a block
                current_block["conf"] = current_block["conf"] / current_block["count"] if current_block["count"] > 0 else 0
                blocks.append(current_block)
                current_block = {"text": "", "conf": 0, "count": 0}
        
        # Add the last block if it contains text
        if current_block["text"].strip():
            current_block["conf"] = current_block["conf"] / current_block["count"] if current_block["count"] > 0 else 0
            blocks.append(current_block)
        
        # Create content blocks
        for i, block in enumerate(blocks):
            content_blocks.append({
                "block_id": i + 1,
                "type": "text",
                "content": block["text"].strip(),
                "confidence": f"{block['conf']:.2f}%"
            })
        
        # If no blocks were created, create a single block with the full text
        if not content_blocks and full_text.strip():
            content_blocks.append({
                "block_id": 1,
                "type": "text",
                "content": full_text.strip()
            })
            
    except Exception as e:
        # If processing fails, create a single block with the full text
        if full_text and full_text.strip():
            content_blocks.append({
                "block_id": 1,
                "type": "text",
                "content": full_text.strip()
            })
    
    return content_blocks

def process_pdf_pages(pdf_path, analysis_json_path, output_json_path, dpi=300):
    """
    Process all PDF pages that need OCR extraction based on analysis results
    
    Args:
        pdf_path (str): Path to the PDF file
        analysis_json_path (str): Path to the analysis JSON file
        output_json_path (str): Path to save the extraction results
        dpi (int): DPI resolution for rendering PDF to image
    """
    # Load analysis results
    with open(analysis_json_path, 'r', encoding='utf-8') as f:
        analysis_data = json.load(f)
    
    # Create or load output JSON
    if os.path.exists(output_json_path):
        with open(output_json_path, 'r', encoding='utf-8') as f:
            output_data = json.load(f)
    else:
        # Get PDF metadata
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            total_pages = len(pdf_reader.pages)
        
        # Create new output structure
        output_data = {
            "metadata": {
                "filename": Path(pdf_path).name,
                "total_pages": total_pages,
                "extraction_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "processing_time": "0 seconds"  # Will be updated later
            },
            "pages": {}
        }
        
        # Initialize pages structure with analysis data
        for page_num, page_analysis in analysis_data.items():
            output_data["pages"][page_num] = {
                "analysis": page_analysis
            }
    
    start_time = time.time()
    processed_count = 0
    
    # Process pages that need OCR extraction
    for page_num, page_data in analysis_data.items():
        # Check if this page needs OCR extraction
        if (page_data.get("ocr_status", False) and 
            not page_data.get("line_status", True) and 
            not page_data.get("ai_status", True)):
            
            # Check if this page has already been processed with OCR extraction
            if (page_num in output_data["pages"] and 
                "extraction" in output_data["pages"][page_num] and 
                output_data["pages"][page_num]["extraction"]["method"] == "ocr"):
                print(f"Page {page_num} already processed with OCR extraction. Skipping.")
                continue
            
            print(f"Processing page {page_num} with OCR extraction...")
            
            # Get existing result if available, otherwise create new
            existing_result = output_data["pages"].get(page_num, {"analysis": page_data})
            
            # Extract content
            result = extract_with_ocr_method(pdf_path, int(page_num), existing_result, dpi)
            
            # Update output data
            output_data["pages"][page_num] = result
            processed_count += 1
    
    # Update metadata
    total_processing_time = time.time() - start_time
    output_data["metadata"]["processing_time"] = f"{total_processing_time:.2f} seconds"
    
    # Save output data
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=4, ensure_ascii=False)
    
    print(f"OCR extraction completed. Processed {processed_count} pages.")
    return output_data

if __name__ == "__main__":
    # Example usage
    pdf_path = "ABF Indonesia Bond Index Fund.pdf"  # Replace with your PDF path
    analysis_json_path = "sample.json"  # Path to analysis JSON
    output_json_path = "hasil_ekstraksi.json"  # Path to save extraction results
    
    process_pdf_pages(pdf_path, analysis_json_path, output_json_path)