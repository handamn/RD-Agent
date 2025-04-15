"""
multimodal_extractor.py - Module for AI-based multimodal PDF text extraction
For pages with complex formatting, tables, charts or other elements that require AI interpretation
"""

import os
import json
import time
import datetime
import fitz  # PyMuPDF
import PIL.Image
import tempfile
import numpy as np
import google.generativeai as genai
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get API key from environment variable
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY environment variable not set. Please set it in your .env file.")

# Configure the Gemini API
genai.configure(api_key=GOOGLE_API_KEY)

def extract_with_multimodal_method(pdf_path, page_num, existing_result=None, model_name='gemini-2.0-flash', dpi=300):
    """
    Extract content from PDF using AI multimodal model for pages with complex formatting,
    tables, charts, or other elements.
    
    Args:
        pdf_path (str): Path to the PDF file
        page_num (int): Page number to extract (1-based indexing)
        existing_result (dict, optional): Existing extraction result to update
        model_name (str): The name of the AI model to use
        dpi (int): DPI resolution for rendering PDF to image
        
    Returns:
        dict: The extraction result for the specified page
    """
    start_time = time.time()
    
    # Create result structure if not provided
    if existing_result is None:
        result = {
            "analysis": {
                "ocr_status": False,
                "line_status": True,
                "ai_status": True
            },
            "extraction": {
                "method": "multimodal_llm",
                "model": model_name,
                "processing_time": None,
                "content_blocks": []
            }
        }
    else:
        result = existing_result
        # Set extraction method and initialize content blocks
        result["extraction"] = {
            "method": "multimodal_llm",
            "model": model_name,
            "processing_time": None,
            "content_blocks": []
        }
    
    try:
        # Load the model
        model = genai.GenerativeModel(model_name)
        
        # Convert PDF page to image using PyMuPDF
        doc = fitz.open(pdf_path)
        
        # Adjust for 0-based indexing
        pdf_page_index = page_num - 1
        
        if pdf_page_index < 0 or pdf_page_index >= len(doc):
            raise ValueError(f"Page {page_num} does not exist in PDF with {len(doc)} pages")
        
        page = doc[pdf_page_index]
        
        # Create a temporary directory for storing the rendered image
        with tempfile.TemporaryDirectory() as temp_dir:
            # Render page to image at specified DPI
            pix = page.get_pixmap(dpi=dpi)
            temp_image_path = os.path.join(temp_dir, f"page_{page_num}.png")
            pix.save(temp_image_path)
            
            # Load the image for the AI model
            pil_image = PIL.Image.open(temp_image_path)
            
            # Prepare prompt for the AI model based on the page characteristics
            prompt = create_extraction_prompt(result["analysis"])
            
            # Generate content using the AI model
            response = model.generate_content([prompt, pil_image])
            
            # Process AI response and structure the content
            content_blocks = process_ai_response(response.text)
            
            # Add the processed content blocks to the result
            result["extraction"]["content_blocks"] = content_blocks
            
            # Store the prompt used
            result["extraction"]["prompt_used"] = prompt
        
    except Exception as e:
        # Handle extraction errors
        result["extraction"]["content_blocks"] = [{
            "block_id": 1,
            "type": "text",
            "content": f"Error during multimodal extraction: {str(e)}"
        }]
    
    # Calculate and record processing time
    processing_time = time.time() - start_time
    result["extraction"]["processing_time"] = f"{processing_time:.2f} seconds"
    
    return result

def create_extraction_prompt(page_analysis):
    """
    Create an appropriate prompt for the AI model based on page analysis.
    
    Args:
        page_analysis (dict): Analysis results for the page
        
    Returns:
        str: A prompt tailored to the page characteristics
    """
    base_prompt = "Please extract all content from this PDF page, maintaining the original structure and formatting."
    
    # Add specific instructions based on page characteristics
    if page_analysis.get("ocr_status", False) and page_analysis.get("line_status", False):
        # For pages with both text requiring OCR and complex formatting
        prompt = base_prompt + " This page contains both text that might need OCR and complex formatting elements. "
        prompt += "Extract and organize ALL content including: text paragraphs, headings, lists, tables, charts, "
        prompt += "diagrams, and any other visual elements. For tables, please convert them to a structured JSON format. "
        prompt += "For charts and diagrams, provide detailed descriptions."
    elif page_analysis.get("line_status", False) and page_analysis.get("ai_status", False):
        # For pages with complex formatting but clear text
        prompt = base_prompt + " This page contains complex formatting elements like tables, charts, or diagrams. "
        prompt += "Extract and organize ALL content including: text paragraphs, headings, lists, tables, charts, "
        prompt += "diagrams, and any other visual elements. For tables, please convert them to a structured JSON format "
        prompt += "with column headers as keys and row data as values. For charts and diagrams, provide detailed descriptions "
        prompt += "of what they represent."
    else:
        # Generic prompt for other cases
        prompt = base_prompt + " Please extract all text content, tables, charts, and other elements. "
        prompt += "Format tables as structured JSON with rows and columns. Describe any charts, images, or diagrams."
    
    # Add output format instructions
    prompt += "\n\nPlease structure your response in JSON format with the following structure:"
    prompt += "\n{\n  \"text\": \"[All plain text content]\","
    prompt += "\n  \"tables\": [\n    {\n      \"table_id\": 1,"
    prompt += "\n      \"title\": \"[Table title if present]\","
    prompt += "\n      \"data\": [[row1col1, row1col2, ...], [row2col1, row2col2, ...], ...],"
    prompt += "\n      \"text_representation\": \"[Plain text representation of the table]\""
    prompt += "\n    }\n  ],"
    prompt += "\n  \"charts\": [\n    {\n      \"chart_id\": 1,"
    prompt += "\n      \"type\": \"[line/bar/pie/etc.]\","
    prompt += "\n      \"title\": \"[Chart title if present]\","
    prompt += "\n      \"description\": \"[Detailed description of what the chart shows]\""
    prompt += "\n    }\n  ],"
    prompt += "\n  \"diagrams\": [\n    {\n      \"diagram_id\": 1,"
    prompt += "\n      \"type\": \"[flowchart/process/organization/etc.]\","
    prompt += "\n      \"description\": \"[Detailed description of the diagram]\""
    prompt += "\n    }\n  ],"
    prompt += "\n  \"other_elements\": [\n    {\n      \"element_id\": 1,"
    prompt += "\n      \"type\": \"[image/logo/etc.]\","
    prompt += "\n      \"description\": \"[Description of the element]\""
    prompt += "\n    }\n  ]"
    prompt += "\n}"
    
    return prompt

def process_ai_response(response_text):
    """
    Process and structure the AI model's response.
    
    Args:
        response_text (str): Text response from the AI model
        
    Returns:
        list: Structured content blocks
    """
    content_blocks = []
    block_id = 1
    
    # Try to parse JSON response if available
    try:
        # Check if the response contains a JSON object
        # First, try to find JSON inside the response (it might be surrounded by text)
        json_start = response_text.find('{')
        json_end = response_text.rfind('}')
        
        if json_start != -1 and json_end != -1:
            json_text = response_text[json_start:json_end+1]
            data = json.loads(json_text)
            
            # Extract text content
            if "text" in data and data["text"]:
                content_blocks.append({
                    "block_id": block_id,
                    "type": "text",
                    "content": data["text"]
                })
                block_id += 1
            
            # Extract tables
            if "tables" in data and data["tables"]:
                for table in data["tables"]:
                    table_content = {
                        "block_id": block_id,
                        "type": "table",
                    }
                    
                    if "title" in table:
                        table_content["title"] = table["title"]
                    
                    if "data" in table:
                        table_content["data"] = table["data"]
                    
                    if "text_representation" in table:
                        table_content["text_representation"] = table["text_representation"]
                    
                    content_blocks.append(table_content)
                    block_id += 1
            
            # Extract charts
            if "charts" in data and data["charts"]:
                for chart in data["charts"]:
                    chart_content = {
                        "block_id": block_id,
                        "type": "chart",
                    }
                    
                    if "type" in chart:
                        chart_content["chart_type"] = chart["type"]
                    
                    if "title" in chart:
                        chart_content["title"] = chart["title"]
                    
                    if "description" in chart:
                        chart_content["description"] = chart["description"]
                    
                    content_blocks.append(chart_content)
                    block_id += 1
            
            # Extract diagrams
            if "diagrams" in data and data["diagrams"]:
                for diagram in data["diagrams"]:
                    diagram_content = {
                        "block_id": block_id,
                        "type": "diagram",
                    }
                    
                    if "type" in diagram and diagram["type"].lower() == "flowchart":
                        diagram_content["type"] = "flowchart"
                    
                    if "title" in diagram:
                        diagram_content["title"] = diagram["title"]
                    
                    if "description" in diagram:
                        diagram_content["description"] = diagram["description"]
                    
                    content_blocks.append(diagram_content)
                    block_id += 1
            
            # Extract other elements
            if "other_elements" in data and data["other_elements"]:
                for element in data["other_elements"]:
                    if "type" in element and element["type"].lower() in ["image", "logo"]:
                        image_content = {
                            "block_id": block_id,
                            "type": "image",
                        }
                        
                        if "description" in element:
                            image_content["description"] = element["description"]
                        
                        content_blocks.append(image_content)
                        block_id += 1
        else:
            # If no valid JSON is found, treat the entire response as text
            content_blocks.append({
                "block_id": block_id,
                "type": "text",
                "content": response_text.strip()
            })
            
    except json.JSONDecodeError:
        # If JSON parsing fails, treat the entire response as text
        content_blocks.append({
            "block_id": block_id,
            "type": "text",
            "content": response_text.strip()
        })
    
    return content_blocks

def process_pdf_pages(pdf_path, analysis_json_path, output_json_path, model_name='gemini-2.0-flash', dpi=300):
    """
    Process all PDF pages that need multimodal extraction based on analysis results
    
    Args:
        pdf_path (str): Path to the PDF file
        analysis_json_path (str): Path to the analysis JSON file
        output_json_path (str): Path to save the extraction results
        model_name (str): The name of the AI model to use
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
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        
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
    
    # Process pages that need multimodal extraction
    for page_num, page_data in analysis_data.items():
        # Check if this page needs multimodal extraction based on the defined rules
        # Rule 1: ocr_status=True, line_status=True, ai_status=True
        # Rule 3: ocr_status=False, line_status=True, ai_status=True
        if ((page_data.get("ocr_status", False) and page_data.get("line_status", False) and page_data.get("ai_status", False)) or
            (not page_data.get("ocr_status", True) and page_data.get("line_status", False) and page_data.get("ai_status", False))):
            
            # Check if this page has already been processed with multimodal extraction
            if (page_num in output_data["pages"] and 
                "extraction" in output_data["pages"][page_num] and 
                output_data["pages"][page_num]["extraction"]["method"] == "multimodal_llm"):
                print(f"Page {page_num} already processed with multimodal extraction. Skipping.")
                continue
            
            print(f"Processing page {page_num} with multimodal extraction...")
            
            # Get existing result if available, otherwise create new
            existing_result = output_data["pages"].get(page_num, {"analysis": page_data})
            
            # Extract content
            result = extract_with_multimodal_method(pdf_path, int(page_num), existing_result, model_name, dpi)
            
            # Update output data
            output_data["pages"][page_num] = result
            processed_count += 1
            
            # Save after each page to ensure progress is not lost if the process is interrupted
            with open(output_json_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=4, ensure_ascii=False)
    
    # Update metadata
    total_processing_time = time.time() - start_time
    output_data["metadata"]["processing_time"] = f"{total_processing_time:.2f} seconds"
    
    # Final save of output data
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=4, ensure_ascii=False)
    
    print(f"Multimodal extraction completed. Processed {processed_count} pages.")
    return output_data

if __name__ == "__main__":
    # Example usage
    pdf_path = "ABF Indonesia Bond Index Fund.pdf"  # Replace with your PDF path
    analysis_json_path = "sample.json"  # Path to analysis JSON
    output_json_path = "hasil_ekstraksi.json"  # Path to save extraction results
    
    process_pdf_pages(pdf_path, analysis_json_path, output_json_path)