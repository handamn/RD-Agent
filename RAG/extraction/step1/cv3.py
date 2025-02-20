import pdfplumber
import pandas as pd
import camelot
import cv2
import numpy as np
from tabulate import tabulate
from PyPDF2 import PdfReader
import os
from pdf2image import convert_from_path
import tempfile

def extract_pdf_with_complex_structure(pdf_path, output_folder="extracted_results"):
    # Create output folder if it doesn't exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    # Store results in dictionary
    results = {}
    
    # Get page size to set table area in absolute coordinates
    with pdfplumber.open(pdf_path) as pdf:
        page_width = float(pdf.pages[0].width)
        page_height = float(pdf.pages[0].height)
    
    # First, identify potential multi-page tables by analyzing the structure
    potential_table_pages = identify_potential_table_pages(pdf_path)
    
    # 3. Extract with camelot (stream mode) - with table continuation handling
    print("\n=== EXTRACTING WITH CAMELOT (STREAM) ===")
    try:
        # Use absolute coordinates for table area - full page
        tables_stream = camelot.read_pdf(pdf_path, pages='all', flavor='stream')
        
        # Process extracted tables with potential continuation awareness
        processed_tables = process_multi_page_tables(tables_stream, potential_table_pages)
        
        # Save processed tables
        for idx, (table_df, pages_span) in enumerate(processed_tables, 1):
            table_name = f"table_{idx}_pages_{'-'.join(map(str, pages_span))}"
            table_df.to_csv(f"{output_folder}/{table_name}.csv", index=False)
            print(f"Saved merged table spanning pages {pages_span} as {table_name}.csv")
            
            # Add to results
            for page in pages_span:
                page_key = f"page_{page}"
                if page_key not in results:
                    results[page_key] = {"text": [], "tables": []}
                # Add the full context table to each page it spans
                results[page_key]["tables"].append(table_df)
            
    except Exception as e:
        print(f"Error in camelot stream extraction: {e}")
    
    # 5. For complex cases - Apply preprocessing for problem pages
    problem_pages = identify_problem_pages(results)
    if problem_pages:
        print(f"\nProblem pages found: {problem_pages}")
        for problem_page in problem_pages:
            print(f"\n=== APPLYING PREPROCESSING FOR PAGE {problem_page} ===")
            
            # Convert PDF page to image
            try:
                images = convert_from_path(pdf_path, first_page=problem_page, last_page=problem_page)
                
                if images:
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_img:
                        tmp_img_path = tmp_img.name
                        images[0].save(tmp_img_path)
                        
                        # Preprocess image
                        processed_img_path = f"{output_folder}/page_{problem_page}_processed.png"
                        preprocess_image_for_ocr(tmp_img_path, processed_img_path)
                        print(f"Preprocessing successfully applied for page {problem_page}")
                        
                        # Try extraction again with the processed image
                        try_extraction_from_processed_image(processed_img_path, results, problem_page)
            except Exception as e:
                print(f"Error in preprocessing page {problem_page}: {e}")
    
    return results

def identify_potential_table_pages(pdf_path):
    """Identify pages that potentially contain tables and their relationships"""
    potential_tables = {}
    table_continuations = {}
    
    with pdfplumber.open(pdf_path) as pdf:
        num_pages = len(pdf.pages)
        
        for page_num in range(num_pages):
            page = pdf.pages[page_num]
            text = page.extract_text() or ""
            
            # Check if page contains table indicators
            has_table = False
            if any(keyword in text.lower() for keyword in ["tabel", "table", "biaya", "jenis", "keterangan"]):
                has_table = True
            
            # Check if this appears to be a continuation from previous page
            is_continuation = False
            if page_num > 0:
                prev_text = pdf.pages[page_num-1].extract_text() or ""
                if prev_text.strip().endswith(":") or text.strip()[0].isalpha() and not text.strip()[0].isupper():
                    is_continuation = True
            
            if has_table:
                potential_tables[page_num + 1] = {
                    "has_table": True,
                    "is_continuation": is_continuation
                }
                
                # If this seems to be a continuation, link it to previous page
                if is_continuation and (page_num) in potential_tables:
                    table_continuations[page_num] = page_num + 1
    
    return {"potential_tables": potential_tables, "continuations": table_continuations}

def process_multi_page_tables(tables, potential_table_info):
    """Process and merge tables that span multiple pages"""
    processed_tables = []
    tables_by_page = {}
    
    # Group tables by page
    for idx, table in enumerate(tables):
        page_num = int(table.page)
        if page_num not in tables_by_page:
            tables_by_page[page_num] = []
        tables_by_page[page_num].append((idx, table))
    
    # Process tables
    processed_indices = set()
    for page_num, page_tables in sorted(tables_by_page.items()):
        for idx, table in page_tables:
            if idx in processed_indices:
                continue
                
            # Check if this table continues to next page
            table_df = table.df.copy()
            pages_span = [page_num]
            
            # Look for continuation tables
            continuations = potential_table_info["continuations"]
            current_page = page_num
            while current_page in continuations:
                next_page = continuations[current_page]
                if next_page in tables_by_page:
                    # Get the first table from next page
                    next_idx, next_table = tables_by_page[next_page][0]
                    
                    # If the next table seems to be a continuation (no header or appears to continue structure)
                    next_df = next_table.df.copy()
                    
                    # If next table has fewer columns, align it with the header
                    if next_df.shape[1] < table_df.shape[1]:
                        # Pad with empty columns to match
                        for i in range(next_df.shape[1], table_df.shape[1]):
                            next_df[i] = ""
                    elif next_df.shape[1] > table_df.shape[1]:
                        # Pad original with empty columns to match
                        for i in range(table_df.shape[1], next_df.shape[1]):
                            table_df[i] = ""
                    
                    # Merge the tables
                    table_df = pd.concat([table_df, next_df], ignore_index=True)
                    pages_span.append(next_page)
                    processed_indices.add(next_idx)
                    
                current_page = next_page
            
            # Clean up the merged table
            if len(pages_span) > 1:
                # If we merged tables, rename columns using the first table's header
                if table_df.shape[0] > 0 and not table_df.iloc[0, 0].strip().isdigit():
                    header = table_df.iloc[0].tolist()
                    table_df = table_df[1:]
                    table_df.columns = header
            
            processed_tables.append((table_df, pages_span))
            processed_indices.add(idx)
    
    return processed_tables

def identify_problem_pages(results):
    """Identify pages with potential table extraction issues"""
    problem_pages = []
    
    for page_key, page_data in results.items():
        # Extract page number from key
        page_num = int(page_key.split('_')[1])
        
        # If no tables detected but there's text that might be a table
        if not page_data.get("tables") and page_data.get("text"):
            for text in page_data["text"]:
                # Simple heuristic: if many tab characters or lines with a pattern, might be a table
                if text.count('\t') > 5 or len([line for line in text.split('\n') if line.count('  ') > 3]) > 3:
                    problem_pages.append(page_num)
                    break
    
    return problem_pages

def try_extraction_from_processed_image(image_path, results, page_num):
    """Try to extract table from preprocessed image using OCR-based approach"""
    try:
        # Use pytesseract or other OCR-based approach here
        # For demonstration, we'll just use camelot's lattice mode which works well with preprocessed images
        tables = camelot.read_pdf(image_path, flavor='lattice')
        
        if len(tables) > 0:
            page_key = f"page_{page_num}"
            if page_key not in results:
                results[page_key] = {"text": [], "tables": []}
            
            for table in tables:
                results[page_key]["tables"].append(table.df)
                print(f"Successfully extracted table from preprocessed image for page {page_num}")
    except Exception as e:
        print(f"Failed to extract from processed image: {e}")

def preprocess_image_for_ocr(image_path, output_path):
    """Preprocess image to enhance table structure for OCR"""
    # Read image
    img = cv2.imread(image_path)
    
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Adaptive thresholding to handle lighting variations
    binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                  cv2.THRESH_BINARY_INV, 11, 2)
    
    # Detect and enhance horizontal and vertical lines
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (50, 1))
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 50))
    
    horizontal_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)
    vertical_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel, iterations=2)
    
    # Combine horizontal and vertical lines
    table_structure = cv2.addWeighted(horizontal_lines, 0.5, vertical_lines, 0.5, 0.0)
    
    # Dilate to thicken lines
    kernel = np.ones((3,3), np.uint8)
    table_structure = cv2.dilate(table_structure, kernel, iterations=1)
    
    # Invert image to get black lines on white background
    table_structure = cv2.bitwise_not(table_structure)
    
    # Overlay table structure on original image
    result = cv2.addWeighted(gray, 0.7, table_structure, 0.3, 0)
    
    # Final thresholding for clarity
    _, result = cv2.threshold(result, 150, 255, cv2.THRESH_BINARY)
    
    # Save processed image
    cv2.imwrite(output_path, result)
    print(f"Preprocessed image saved to: {output_path}")
    
    return output_path

def postprocess_table(table_df):
    """Clean and format extracted table data"""
    # Remove empty rows and columns
    table_df = table_df.dropna(how='all').reset_index(drop=True)
    table_df = table_df.dropna(axis=1, how='all')
    
    # Try to identify header row
    header_row = 0
    for i, row in table_df.iterrows():
        if row.astype(str).str.contains('JENIS|BIAYA|KETERANGAN').any():
            header_row = i
            break
    
    # If header found, set it as column names
    if header_row > 0:
        table_df.columns = table_df.iloc[header_row]
        table_df = table_df.iloc[header_row+1:].reset_index(drop=True)
    
    return table_df

# Example usage
def main():
    pdf_path = "studi_kasus/7_Tabel_N_Halaman_Normal_V1.pdf"
    results = extract_pdf_with_complex_structure(pdf_path)
    
    # Post-process and merge all tables with context
    all_tables = []
    for page_key, page_data in sorted(results.items()):
        if "tables" in page_data and page_data["tables"]:
            for table in page_data["tables"]:
                processed_table = postprocess_table(table)
                if not processed_table.empty:
                    all_tables.append(processed_table)
    
    # If tables were found, merge them if they appear to be continuations
    if all_tables:
        # Identify tables that appear to be continuations
        merged_tables = []
        current_table = all_tables[0]
        
        for i in range(1, len(all_tables)):
            next_table = all_tables[i]
            
            # If column count is similar and this appears to be a continuation
            if abs(len(current_table.columns) - len(next_table.columns)) <= 1:
                # Check if the next table has headers
                has_headers = any(col.upper() == col for col in next_table.columns)
                
                if not has_headers:
                    # Likely a continuation, align columns and merge
                    if len(next_table.columns) < len(current_table.columns):
                        next_table.columns = current_table.columns[:len(next_table.columns)]
                    current_table = pd.concat([current_table, next_table], ignore_index=True)
                else:
                    # Not a continuation, save current and start new
                    merged_tables.append(current_table)
                    current_table = next_table
            else:
                # Different structure, likely not a continuation
                merged_tables.append(current_table)
                current_table = next_table
        
        # Add the last table
        merged_tables.append(current_table)
        
        # Save merged tables
        for i, table in enumerate(merged_tables):
            table.to_csv(f"extracted_results/merged_table_{i+1}.csv", index=False)
            print(f"Saved merged table {i+1}")

if __name__ == "__main__":
    main()