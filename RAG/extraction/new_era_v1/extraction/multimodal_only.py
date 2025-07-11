"""
multimodal_only.py - Module for multimodal AI-based PDF text extraction
For pages with complex layouts, tables, charts, or images that require AI understanding
"""

import os
import json
import time
import datetime
import fitz  # PyMuPDF
import PyPDF2
import numpy as np
import cv2
from pathlib import Path
from PIL import Image
import google.generativeai as genai
from dotenv import load_dotenv
import uuid
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# Configure Gemini API
genai.configure(api_key=GOOGLE_API_KEY)

# --- Image processing --- #
def ensure_directory_exists(directory_path):
    """
    Ensure that the specified directory exists, creating it if necessary.
    
    Args:
        directory_path (str): Path to the directory
    """
    os.makedirs(directory_path, exist_ok=True)

def render_pdf_page_to_image(pdf_path, page_num, output_dir, dpi=300):
    """
    Render a PDF page to an image file and return the path to the image.
    
    Args:
        pdf_path (str): Path to the PDF file
        page_num (int): Page number to render (1-based indexing)
        output_dir (str): Directory to save the rendered image
        dpi (int): DPI resolution for rendering PDF to image
        
    Returns:
        str: Path to the rendered image file
    """
    try:
        # Ensure output directory exists
        ensure_directory_exists(output_dir)
        
        # Open PDF document
        doc = fitz.open(pdf_path)
        
        # Convert to 0-based indexing for PyMuPDF
        pdf_page_index = page_num - 1
        
        if pdf_page_index < 0 or pdf_page_index >= len(doc):
            raise ValueError(f"Page {page_num} does not exist in PDF with {len(doc)} pages")
        
        # Get the page
        page = doc[pdf_page_index]
        
        # Create a unique filename to avoid overwriting
        image_filename = f"image_page_{page_num}_{uuid.uuid4().hex[:8]}.png"
        image_path = os.path.join(output_dir, image_filename)
        
        # Render page to image with specified DPI
        pix = page.get_pixmap(dpi=dpi)
        pix.save(image_path)
        
        logger.info(f"Rendered page {page_num} to {image_path}")
        
        return image_path
    
    except Exception as e:
        logger.error(f"Error rendering PDF page {page_num} to image: {str(e)}")
        raise

def clean_temporary_images(temp_dir):
    """
    Delete all image files in the temporary directory after processing is complete.
    
    Args:
        temp_dir (str): Directory containing temporary images
    """
    try:
        # Check if directory exists
        if not os.path.exists(temp_dir):
            logger.info(f"Temporary directory {temp_dir} does not exist. Nothing to clean.")
            return
            
        # Get list of all files in directory
        image_extensions = ['.png', '.jpg', '.jpeg', '.tiff', '.bmp']
        file_count = 0
        
        for filename in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, filename)
            # Check if it's a file and has image extension
            if os.path.isfile(file_path) and any(filename.lower().endswith(ext) for ext in image_extensions):
                os.remove(file_path)
                file_count += 1
                
        logger.info(f"Cleaned up {file_count} temporary image files from {temp_dir}")
        
    except Exception as e:
        logger.error(f"Error cleaning temporary images: {str(e)}")


# --- LLM Processing --- #
def create_multimodal_prompt(page_analysis):
    """
    Create an appropriate prompt for the multimodal AI model based on page analysis.
    
    Args:
        page_analysis (dict): Analysis of the page content
        
    Returns:
        str: Prompt for the multimodal model
    """
    # Base prompt with expanded content structure
    prompt = ("Analisis gambar ini secara detail dan ekstrak semua konten dengan mempertahankan struktur aslinya. "
             "Identifikasi dan berikan output dalam format berikut:\n\n"
             "1. Semua teks, termasuk heading, paragraf dan caption.\n"
             "2. Tabel lengkap dengan data seluruh baris dan kolom beserta judulnya.\n"
             "3. Grafik dan diagram, termasuk judul, label, nilai data, dan deskripsi visual.\n"
             "4. Flowchart dengan elemen-elemen dan hubungannya.\n"
             "5. Gambar dengan deskripsi dan caption (jika ada).\n\n"
             "Berikan output yang lengkap dan terstruktur dalam format JSON seperti contoh berikut:\n"
             "```json\n"
             "{\n"
             "  \"content_blocks\": [\n"
             "    {\n"
             "      \"block_id\": 1,\n"
             "      \"type\": \"text\",\n"
             "      \"content\": \"Teks lengkap dari bagian ini...\"\n"
             "    },\n"
             "    {\n"
             "      \"block_id\": 2,\n"
             "      \"type\": \"table\",\n"
             "      \"title\": \"Judul tabel (jika ada)\",\n"
             "      \"data\": [\n"
             "        {\"header_1\": \"nilai_baris_1_kolom_1\", \"header_2\": \"nilai_baris_1_kolom_2\"},\n"
             "        {\"header_1\": \"nilai_baris_2_kolom_1\", \"header_2\": \"nilai_baris_2_kolom_2\"}\n"
             "      ],\n"
             "      \"summary_table\": \"Deskripsi singkat tentang tabel\"\n"
             "    },\n"
             "    {\n"
             "      \"block_id\": 3,\n"
             "      \"type\": \"chart\",\n"
             "      \"chart_type\": \"line\",\n"
             "      \"title\": \"Judul grafik\",\n"
             "      \"data\": {\n"
             "        \"labels\": [\"label_1\", \"label_2\", \"label_3\"],\n"
             "        \"datasets\": [\n"
             "          {\n"
             "            \"label\": \"Dataset 1\",\n"
             "            \"values\": [5.2, 6.3, 7.1]\n"
             "          }\n"
             "        ]\n"
             "      },\n"
             "      \"summary_chart\": \"Deskripsi singkat tentang grafik\"\n"
             "    },\n"
             "    {\n"
             "      \"block_id\": 4,\n"
             "      \"type\": \"flowchart\",\n"
             "      \"title\": \"Judul flowchart\",\n"
             "      \"elements\": [\n"
             "        {\"type\": \"node\", \"id\": \"1\", \"text\": \"Langkah 1\", \"connects_to\": [\"2\"]},\n"
             "        {\"type\": \"node\", \"id\": \"2\", \"text\": \"Langkah 2\", \"connects_to\": [\"3\"]},\n"
             "        {\"type\": \"node\", \"id\": \"3\", \"text\": \"Langkah 3\", \"connects_to\": []}\n"
             "      ],\n"
             "      \"summary_flowchart\": \"Deskripsi singkat tentang flowchart\"\n"
             "    },\n"
             "    {\n"
             "      \"block_id\": 5,\n"
             "      \"type\": \"image\",\n"
             "      \"description_image\": \"Deskripsi detail tentang gambar\"\n"
             "    }\n"
             "  ]\n"
             "}\n"
             "```\n"
             "Pastikan mengekstrak SEMUA konten termasuk angka, teks lengkap, dan struktur dengan tepat sesuai format di atas.")
    
    # Customize prompt further based on specific page characteristics if needed
    if page_analysis.get("ocr_status", False):
        prompt += "\nPerhatikan bahwa halaman ini mungkin mengandung teks hasil scan/OCR, pastikan untuk mengekstrak semua teks dengan tepat."
    
    if page_analysis.get("line_status", False):
        prompt += "\nPerhatikan garis-garis dan elemen visual untuk mengidentifikasi struktur tabel, diagram, atau flowchart dengan benar."
    
    return prompt

def process_with_multimodal_api(image_path, prompt):
    """
    Process an image using the Gemini multimodal API.
    
    Args:
        image_path (str): Path to the image file
        prompt (str): Prompt for the multimodal model
        
    Returns:
        dict: The extracted content from the multimodal model
    """
    try:
        # Load the image
        pil_image = Image.open(image_path)
        
        # Get model
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Generate content
        response = model.generate_content([prompt, pil_image])
        
        # Extract and parse JSON content
        response_text = response.text
        
        # Try to extract JSON from the response if it's wrapped in code blocks
        if "```json" in response_text and "```" in response_text:
            json_content = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            json_content = response_text.split("```")[1].split("```")[0].strip()
        else:
            json_content = response_text
        
        try:
            # Try to parse as JSON
            content_json = json.loads(json_content)
            return content_json
        except json.JSONDecodeError:
            # If JSON parsing fails, return as raw text
            logger.warning("Failed to parse JSON from model response, returning raw text")
            return {
                "content_blocks": [
                    {
                        "block_id": 1,
                        "type": "text",
                        "content": response_text
                    }
                ]
            }
    
    except Exception as e:
        logger.error(f"Error processing image with multimodal API: {str(e)}")
        return {
            "content_blocks": [
                {
                    "block_id": 1,
                    "type": "text",
                    "content": f"Error during multimodal processing: {str(e)}"
                }
            ]
        }

def extract_with_multimodal_method(pdf_path, page_num, existing_result=None, dpi=300, temp_dir="temporary_dir"):
    """
    Extract content from PDF using multimodal AI for pages with complex formatting.
    
    Args:
        pdf_path (str): Path to the PDF file
        page_num (int): Page number to extract (1-based indexing)
        existing_result (dict, optional): Existing extraction result to update
        dpi (int): DPI resolution for rendering PDF to image
        temp_dir (str): Directory to store temporary images
        
    Returns:
        dict: The extraction result for the specified page
    """
    start_time = time.time()
    
    # Create result structure if not provided
    if existing_result is None:
        # Default to both flags being True since this is a fallback case
        result = {
            "analysis": {
                "ocr_status": True,
                "line_status": True,
                "ai_status": True
            },
            "extraction": {
                "method": "multimodal_llm",
                "model": "gemini-2.0-flash",
                "processing_time": None,
                "content_blocks": []
            }
        }
    else:
        result = existing_result
        # Set extraction method and initialize content blocks
        result["extraction"] = {
            "method": "multimodal_llm",
            "model": "gemini-2.0-flash",
            "processing_time": None,
            "content_blocks": []
        }
    
    try:
        # Render PDF page to image
        image_path = render_pdf_page_to_image(pdf_path, page_num, temp_dir, dpi)
        
        # Create prompt based on page analysis
        prompt = create_multimodal_prompt(result["analysis"])
        # result["extraction"]["prompt_used"] = prompt
        
        # Process with multimodal API
        content_result = process_with_multimodal_api(image_path, prompt)
        
        # Update the result with content blocks
        if "content_blocks" in content_result:
            result["extraction"]["content_blocks"] = content_result["content_blocks"]
        else:
            # Fallback if we didn't get content blocks
            result["extraction"]["content_blocks"] = [{
                "block_id": 1,
                "type": "text",
                "content": "No structured content could be extracted via multimodal processing."
            }]
        
    except Exception as e:
        # Handle extraction errors
        error_message = f"Error during multimodal extraction: {str(e)}"
        logger.error(error_message)
        
        result["extraction"]["content_blocks"] = [{
            "block_id": 1,
            "type": "text",
            "content": error_message
        }]
    
    # Calculate and record processing time
    processing_time = time.time() - start_time
    result["extraction"]["processing_time"] = f"{processing_time:.2f} seconds"
    
    return result


# --- Main Process --- #
def process_pdf_pages(pdf_path, analysis_json_path, output_json_path, temp_dir="temporary_dir", dpi=300):
    """
    Process all PDF pages that need multimodal extraction based on analysis results
    
    Args:
        pdf_path (str): Path to the PDF file
        analysis_json_path (str): Path to the analysis JSON file
        output_json_path (str): Path to save the extraction results
        temp_dir (str): Directory to store temporary images
        dpi (int): DPI resolution for rendering PDF to image
    """
    # Ensure temp directory exists
    ensure_directory_exists(temp_dir)
    
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
    
    # Process pages that need multimodal extraction based on the two rules
    for page_num, page_data in analysis_data.items():
        # Rule 1: ocr_status=True, line_status=True, ai_status=True
        # Rule 3: ocr_status=False, line_status=True, ai_status=True
        if ((page_data.get("ocr_status", False) and 
             page_data.get("line_status", False) and 
             page_data.get("ai_status", False)) or 
            (not page_data.get("ocr_status", True) and 
             page_data.get("line_status", False) and 
             page_data.get("ai_status", False))):
            
            # Check if this page has already been processed with multimodal extraction
            if (page_num in output_data["pages"] and 
                "extraction" in output_data["pages"][page_num] and 
                output_data["pages"][page_num]["extraction"]["method"] == "multimodal_llm"):
                logger.info(f"Page {page_num} already processed with multimodal extraction. Skipping.")
                continue
            
            logger.info(f"Processing page {page_num} with multimodal extraction...")
            
            # Get existing result if available, otherwise create new
            existing_result = output_data["pages"].get(page_num, {"analysis": page_data})
            
            # Extract content
            result = extract_with_multimodal_method(pdf_path, int(page_num), existing_result, dpi, temp_dir)
            
            # Update output data
            output_data["pages"][page_num] = result
            processed_count += 1
    
    # Update metadata
    total_processing_time = time.time() - start_time
    output_data["metadata"]["processing_time"] = f"{total_processing_time:.2f} seconds"
    
    # Save output data
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=4, ensure_ascii=False)
    
    clean_temporary_images(temp_dir)

    logger.info(f"Multimodal extraction completed. Processed {processed_count} pages.")
    return output_data

if __name__ == "__main__":
    # Example usage
    pdf_path = "ABF Indonesia Bond Index Fund.pdf"  # Replace with your PDF path
    analysis_json_path = "sample.json"  # Path to analysis JSON
    output_json_path = "hasil_ekstraksi.json"  # Path to save extraction results
    temp_dir = "temporary_dir"  # Directory for temporary images
    
    process_pdf_pages(pdf_path, analysis_json_path, output_json_path, temp_dir)