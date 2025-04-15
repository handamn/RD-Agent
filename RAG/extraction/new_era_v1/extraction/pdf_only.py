"""
direct_extractor.py - Module for direct PDF text extraction
For pages where OCR isn't needed and no special formatting is detected
"""

import os
import json
import PyPDF2
import datetime
import time
from pathlib import Path

def extract_with_direct_method(pdf_path, page_num, existing_result=None):
    """
    Extract text directly from PDF using PyPDF2 for pages that don't need 
    special processing.
    
    Args:
        pdf_path (str): Path to the PDF file
        page_num (int): Page number to extract (1-based indexing)
        existing_result (dict, optional): Existing extraction result to update
        
    Returns:
        dict: The extraction result for the specified page
    """
    start_time = time.time()
    
    # Create result structure if not provided
    if existing_result is None:
        result = {
            "analysis": {
                "ocr_status": False,
                "line_status": False,
                "ai_status": False
            },
            "extraction": {
                "method": "direct_extraction",
                "processing_time": None,
                "content_blocks": []
            }
        }
    else:
        result = existing_result
        # Set extraction method and initialize content blocks
        result["extraction"] = {
            "method": "direct_extraction",
            "processing_time": None,
            "content_blocks": []
        }
    
    try:
        # Open PDF and extract text from the specific page
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            # Adjust for 0-based indexing in PyPDF2
            pdf_page_index = page_num - 1
            
            if pdf_page_index < 0 or pdf_page_index >= len(pdf_reader.pages):
                raise ValueError(f"Page {page_num} does not exist in PDF with {len(pdf_reader.pages)} pages")
            
            pdf_page = pdf_reader.pages[pdf_page_index]
            text = pdf_page.extract_text()
            
            # Create a single content block for the extracted text, regardless of paragraphs
            if text and text.strip():
                result["extraction"]["content_blocks"] = [{
                    "block_id": 1,
                    "type": "text",
                    "content": text.strip()
                }]
            else:
                result["extraction"]["content_blocks"] = [{
                    "block_id": 1,
                    "type": "text",
                    "content": "No text content could be extracted directly from this page."
                }]
                
    except Exception as e:
        # Handle extraction errors
        result["extraction"]["content_blocks"] = [{
            "block_id": 1,
            "type": "text",
            "content": f"Error during direct extraction: {str(e)}"
        }]
    
    # Calculate and record processing time
    processing_time = time.time() - start_time
    result["extraction"]["processing_time"] = f"{processing_time:.2f} seconds"
    
    return result

def process_pdf_pages(pdf_path, analysis_json_path, output_json_path):
    """
    Process all PDF pages that need direct extraction based on analysis results
    
    Args:
        pdf_path (str): Path to the PDF file
        analysis_json_path (str): Path to the analysis JSON file
        output_json_path (str): Path to save the extraction results
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
    
    # Process pages that need direct extraction
    for page_num, page_data in analysis_data.items():
        # Check if this page needs direct extraction
        if (not page_data.get("ocr_status", True) and 
            not page_data.get("line_status", True) and 
            not page_data.get("ai_status", True)):
            
            # Check if this page has already been processed with direct extraction
            if (page_num in output_data["pages"] and 
                "extraction" in output_data["pages"][page_num] and 
                output_data["pages"][page_num]["extraction"]["method"] == "direct_extraction"):
                print(f"Page {page_num} already processed with direct extraction. Skipping.")
                continue
            
            print(f"Processing page {page_num} with direct extraction...")
            
            # Get existing result if available, otherwise create new
            existing_result = output_data["pages"].get(page_num, {"analysis": page_data})
            
            # Extract content
            result = extract_with_direct_method(pdf_path, int(page_num), existing_result)
            
            # Update output data
            output_data["pages"][page_num] = result
            processed_count += 1
    
    # Update metadata
    total_processing_time = time.time() - start_time
    output_data["metadata"]["processing_time"] = f"{total_processing_time:.2f} seconds"
    
    # Save output data
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=4, ensure_ascii=False)
    
    print(f"Direct extraction completed. Processed {processed_count} pages.")
    return output_data

if __name__ == "__main__":
    # Example usage
    pdf_path = "ABF Indonesia Bond Index Fund.pdf"  # Replace with your PDF path
    analysis_json_path = "sample.json"  # Path to analysis JSON
    output_json_path = "hasil_ekstraksi.json"  # Path to save extraction results
    
    process_pdf_pages(pdf_path, analysis_json_path, output_json_path)