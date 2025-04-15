"""
multimodal_only.py - Module for multimodal LLM-based PDF extraction
For pages with complex layouts, tables, charts or images that need AI-powered interpretation
"""

import os
import json
import time
import datetime
import fitz  # PyMuPDF
import PIL.Image
import numpy as np
import PyPDF2
from pathlib import Path
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get API key from environment
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# Configure the API client
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
else:
    print("Warning: GOOGLE_API_KEY not found in environment variables")

def render_pdf_page_to_image(pdf_path, page_num, output_dir="temporary_dir", dpi=300):
    """
    Render a specific page from a PDF to an image
    
    Args:
        pdf_path (str): Path to the PDF file
        page_num (int): Page number to render (1-based indexing)
        output_dir (str): Directory to save the rendered image
        dpi (int): DPI resolution for rendering
        
    Returns:
        str: Path to the saved image
    """
    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate output image path
    output_image_path = os.path.join(output_dir, f"image_page_{page_num}.png")
    
    # Open the PDF document
    doc = fitz.open(pdf_path)
    
    # Adjust for 0-based indexing
    pdf_page_index = page_num - 1
    
    if pdf_page_index < 0 or pdf_page_index >= len(doc):
        raise ValueError(f"Page {page_num} does not exist in PDF with {len(doc)} pages")
    
    # Get the page
    page = doc[pdf_page_index]
    
    # Render page to image at specified DPI
    pix = page.get_pixmap(dpi=dpi)
    
    # Save the image
    pix.save(output_image_path)
    
    doc.close()
    return output_image_path

def extract_with_multimodal_llm(pdf_path, page_num, existing_result=None, dpi=300):
    """
    Extract content from PDF page using a multimodal LLM API
    
    Args:
        pdf_path (str): Path to the PDF file
        page_num (int): Page number to extract (1-based indexing)
        existing_result (dict, optional): Existing extraction result to update
        dpi (int): DPI resolution for rendering PDF to image
        
    Returns:
        dict: The extraction result for the specified page
    """
    start_time = time.time()
    image_path = None
    
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
                "processing_time": None,
                "content_blocks": []
            }
        }
    else:
        result = existing_result
        # Set extraction method and initialize content blocks
        result["extraction"] = {
            "method": "multimodal_llm",
            "processing_time": None,
            "content_blocks": []
        }
    
    try:
        # Render PDF page to image
        image_path = render_pdf_page_to_image(pdf_path, page_num, dpi=dpi)
        
        # Check if the API key is configured
        if not GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY not found in environment variables")
        
        # Load the image
        pil_image = None
        try:
            pil_image = PIL.Image.open(image_path)
            
            # Initialize the model
            model = genai.GenerativeModel('gemini-2.0-flash')  # Use appropriate model
            
            # Create a structured prompt for the model
            prompt = """
            Extract all content from this PDF page. Identify and structure the following elements:
            
            1. All textual content
            2. Tables with headers and data
            3. Charts or graphs with data points
            4. Flowcharts or diagrams
            5. Images with descriptions
            
            Format the response as follows:
            
            1. For text blocks, provide the content
            2. For tables, provide a title if present, structured data with headers and rows, and a brief summary
            3. For charts, specify chart type, title, data (labels, datasets), and a brief summary
            4. For flowcharts, provide a title, elements (nodes and connections), and a brief summary
            5. For images, provide a detailed description
            
            Organize these as separate blocks in the response.
            """
            
            # Generate content
            response = model.generate_content([prompt, pil_image])
            
            # Process the response and extract structured data
            processed_blocks = parse_llm_response(response.text, page_num)
            
            # Update the extraction result with the processed blocks
            result["extraction"]["content_blocks"] = processed_blocks
            
        finally:
            # Make sure to close the image before attempting to delete it
            if pil_image:
                pil_image.close()
            
            # Add a small delay to ensure file handles are completely released
            time.sleep(0.1)
            
            # Try to clean up temporary image file with extra error handling
            try:
                if image_path and os.path.exists(image_path):
                    os.remove(image_path)
            except Exception as cleanup_error:
                print(f"Warning: Could not delete temporary file {image_path}: {cleanup_error}")
                # If deletion fails, we'll just let Windows clean it up later
                pass
                
    except Exception as e:
        # Handle extraction errors
        result["extraction"]["content_blocks"] = [{
            "block_id": 1,
            "type": "text",
            "content": f"Error during multimodal LLM extraction: {str(e)}"
        }]
        
        # Try cleanup again in case of early exception
        try:
            if image_path and os.path.exists(image_path):
                os.remove(image_path)
        except:
            pass
    
    # Calculate and record processing time
    processing_time = time.time() - start_time
    result["extraction"]["processing_time"] = f"{processing_time:.2f} seconds"
    
    return result

def parse_llm_response(response_text, page_num):
    """
    Parse the response from the LLM and convert it to structured content blocks
    
    Args:
        response_text (str): Raw text response from the LLM
        page_num (int): Page number for reference
        
    Returns:
        list: List of structured content blocks
    """
    # Initialize content blocks
    content_blocks = []
    block_id_counter = 1
    
    # This is a placeholder implementation that creates a simple text block
    # In a real implementation, you would need to parse the LLM response to identify
    # different types of content (text, tables, charts, etc.)
    
    # For demonstration, we'll implement a basic parser that attempts to identify
    # tables and different content types from the response text
    
    # Split the response into sections based on common patterns
    lines = response_text.split('\n')
    current_block_type = "text"
    current_block_content = []
    current_block_title = ""
    
    for line in lines:
        line = line.strip()
        
        # Skip empty lines
        if not line:
            continue
        
        # Check for block type indicators
        if "Table:" in line or "TABLE" in line or line.lower().startswith("table "):
            # Save the previous block if it exists
            if current_block_content:
                content_blocks.append(create_content_block(
                    block_id_counter, current_block_type, current_block_content, current_block_title
                ))
                block_id_counter += 1
                current_block_content = []
            
            current_block_type = "table"
            current_block_title = line.replace("Table:", "").strip()
            
        elif "Chart:" in line or "CHART" in line or line.lower().startswith("chart ") or "Graph:" in line:
            # Save the previous block if it exists
            if current_block_content:
                content_blocks.append(create_content_block(
                    block_id_counter, current_block_type, current_block_content, current_block_title
                ))
                block_id_counter += 1
                current_block_content = []
            
            current_block_type = "chart"
            current_block_title = line.replace("Chart:", "").replace("Graph:", "").strip()
            
        elif "Flowchart:" in line or "FLOWCHART" in line or line.lower().startswith("flowchart ") or "Diagram:" in line:
            # Save the previous block if it exists
            if current_block_content:
                content_blocks.append(create_content_block(
                    block_id_counter, current_block_type, current_block_content, current_block_title
                ))
                block_id_counter += 1
                current_block_content = []
            
            current_block_type = "flowchart"
            current_block_title = line.replace("Flowchart:", "").replace("Diagram:", "").strip()
            
        elif "Image:" in line or "IMAGE" in line or line.lower().startswith("image description"):
            # Save the previous block if it exists
            if current_block_content:
                content_blocks.append(create_content_block(
                    block_id_counter, current_block_type, current_block_content, current_block_title
                ))
                block_id_counter += 1
                current_block_content = []
            
            current_block_type = "image"
            current_block_content = [line.replace("Image:", "").strip()]
            
        else:
            # If we're in a text block and encounter something that looks like a header/section
            if current_block_type == "text" and line.endswith(":") and len(line) < 50:
                # Save the previous block if it exists
                if current_block_content:
                    content_blocks.append(create_content_block(
                        block_id_counter, current_block_type, current_block_content, current_block_title
                    ))
                    block_id_counter += 1
                    current_block_content = []
                
                current_block_title = line.replace(":", "").strip()
            else:
                # Add to the current block content
                current_block_content.append(line)
    
    # Add the final block
    if current_block_content:
        content_blocks.append(create_content_block(
            block_id_counter, current_block_type, current_block_content, current_block_title
        ))
    
    # If no blocks were created, create a default text block with the entire response
    if not content_blocks:
        content_blocks.append({
            "block_id": 1,
            "type": "text",
            "content": response_text.strip()
        })
    
    return content_blocks

def create_content_block(block_id, block_type, content_lines, title=""):
    """
    Create a structured content block based on the type and content
    
    Args:
        block_id (int): Unique identifier for the block
        block_type (str): Type of content (text, table, chart, flowchart, image)
        content_lines (list): Lines of content for the block
        title (str): Title for the block if available
        
    Returns:
        dict: Structured content block
    """
    content_text = "\n".join(content_lines)
    
    if block_type == "text":
        return {
            "block_id": block_id,
            "type": "text",
            "content": content_text
        }
    elif block_type == "table":
        # Try to parse the table structure
        # This is a simplified implementation
        try:
            # Process table content to extract headers and rows
            headers = []
            rows = []
            
            # Look for header row indicators
            for i, line in enumerate(content_lines):
                if "|" in line and (i == 0 or (i == 1 and "---" in content_lines[i])):
                    # This looks like a header row in markdown table format
                    headers = [h.strip() for h in line.split("|") if h.strip()]
                    continue
                    
                if headers and "|" in line and "---" not in line:
                    # This looks like a data row
                    row_values = [cell.strip() for cell in line.split("|") if cell.strip()]
                    if len(row_values) == len(headers):
                        row_dict = {headers[i]: row_values[i] for i in range(len(headers))}
                        rows.append(row_dict)
            
            # If we couldn't parse as a structured table, use a basic approach
            if not headers or not rows:
                # Simplified approach: try to split by equal number of whitespace
                for i, line in enumerate(content_lines):
                    if i == 0 or i == 1:  # First two lines might be headers
                        headers = line.split()
                        continue
                    
                    values = line.split()
                    if len(values) == len(headers):
                        row_dict = {headers[i]: values[i] for i in range(len(headers))}
                        rows.append(row_dict)
            
            # If we still couldn't parse as a table, create a basic structure
            if not headers or not rows:
                return {
                    "block_id": block_id,
                    "type": "table",
                    "title": title,
                    "data": [{"value": content_text}],
                    "summary_table": f"Table containing data that could not be parsed structurally"
                }
            
            return {
                "block_id": block_id,
                "type": "table",
                "title": title,
                "data": rows,
                "summary_table": f"Table with {len(rows)} rows and {len(headers)} columns"
            }
        except Exception as e:
            # Fall back to raw text if table parsing fails
            return {
                "block_id": block_id,
                "type": "table",
                "title": title,
                "data": [{"raw_table_content": content_text}],
                "summary_table": f"Table data (parsing failed with error: {str(e)})"
            }
    elif block_type == "chart":
        # Simplified chart structure, in a real implementation you would need more robust parsing
        chart_type = "unknown"
        for line in content_lines:
            if "bar" in line.lower():
                chart_type = "bar"
                break
            elif "line" in line.lower():
                chart_type = "line"
                break
            elif "pie" in line.lower():
                chart_type = "pie"
                break
        
        # Create a placeholder chart structure
        return {
            "block_id": block_id,
            "type": "chart",
            "chart_type": chart_type,
            "title": title,
            "data": {
                "labels": ["Data extraction would require more sophisticated parsing"],
                "datasets": [
                    {
                        "label": "Chart Data",
                        "values": [0]  # Placeholder
                    }
                ]
            },
            "summary_chart": content_text
        }
    elif block_type == "flowchart":
        return {
            "block_id": block_id,
            "type": "flowchart",
            "title": title,
            "elements": [
                {"type": "node", "id": "1", "text": "Flowchart extraction would require more sophisticated parsing", "connects_to": []}
            ],
            "summary_flowchart": content_text
        }
    elif block_type == "image":
        return {
            "block_id": block_id,
            "type": "image",
            "description_image": content_text
        }
    else:
        # Default to text for unknown types
        return {
            "block_id": block_id,
            "type": "text",
            "content": content_text
        }

def process_pdf_pages(pdf_path, analysis_json_path, output_json_path, dpi=300):
    """
    Process all PDF pages that need multimodal LLM extraction based on analysis results
    
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
    
    # Process pages that need multimodal LLM extraction
    for page_num, page_data in analysis_data.items():
        # Check if this page needs multimodal LLM extraction (rules 1 and 3)
        # Rule 1: ocr_status=True, line_status=True, ai_status=True
        # Rule 3: ocr_status=False, line_status=True, ai_status=True
        if ((page_data.get("ocr_status", False) and 
             page_data.get("line_status", False) and 
             page_data.get("ai_status", False)) or
            (not page_data.get("ocr_status", True) and 
             page_data.get("line_status", False) and 
             page_data.get("ai_status", False))):
            
            # Check if this page has already been processed with multimodal LLM extraction
            if (page_num in output_data["pages"] and 
                "extraction" in output_data["pages"][page_num] and 
                output_data["pages"][page_num]["extraction"]["method"] == "multimodal_llm"):
                print(f"Page {page_num} already processed with multimodal LLM extraction. Skipping.")
                continue
            
            print(f"Processing page {page_num} with multimodal LLM extraction...")
            
            # Get existing result if available, otherwise create new
            existing_result = output_data["pages"].get(page_num, {"analysis": page_data})
            
            # Extract content
            result = extract_with_multimodal_llm(pdf_path, int(page_num), existing_result, dpi)
            
            # Update output data
            output_data["pages"][page_num] = result
            processed_count += 1
    
    # Update metadata
    total_processing_time = time.time() - start_time
    output_data["metadata"]["processing_time"] = f"{total_processing_time:.2f} seconds"
    
    # Save output data
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=4, ensure_ascii=False)
    
    print(f"Multimodal LLM extraction completed. Processed {processed_count} pages.")
    return output_data

if __name__ == "__main__":
    # Example usage
    pdf_path = "ABF Indonesia Bond Index Fund.pdf"  # Replace with your PDF path
    analysis_json_path = "sample.json"  # Path to analysis JSON
    output_json_path = "hasil_ekstraksi.json"  # Path to save extraction results
    
    process_pdf_pages(pdf_path, analysis_json_path, output_json_path)