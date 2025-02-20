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
import re

def extract_pdf_with_content_distinction(pdf_path, output_folder="extracted_results"):
    # Create output folder if it doesn't exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    # Store results in dictionary
    results = {}
    
    # Get page dimensions for setting absolute coordinates
    with pdfplumber.open(pdf_path) as pdf:
        page_width = float(pdf.pages[0].width)
        page_height = float(pdf.pages[0].height)
        
        # 1. First extract all text using pdfplumber for better text handling
        print("\n=== EXTRACTING TEXT WITH PDFPLUMBER ===")
        for page_num, page in enumerate(pdf.pages, 1):
            page_key = f"page_{page_num}"
            
            # Initialize page in results if not exists
            if page_key not in results:
                results[page_key] = {"text": [], "tables": []}
            
            # Extract all text from the page
            text = page.extract_text()
            if text:
                results[page_key]["text"].append(text)
                
                # Save raw text to file
                with open(f"{output_folder}/{page_key}_text.txt", "w", encoding="utf-8") as f:
                    f.write(text)
                
                print(f"Extracted text from page {page_num} ({len(text)} characters)")
    
    # 2. Extract tables with camelot (stream mode) using absolute coordinates
    print("\n=== EXTRACTING TABLES WITH CAMELOT (STREAM) ===")
    try:
        # Use absolute coordinates for table area - entire page
        table_area = [0, 0, page_width, page_height]
        tables_stream = camelot.read_pdf(pdf_path, pages='all', flavor='stream', 
                                         table_areas=[','.join(map(str, table_area))])
        
        if len(tables_stream) > 0:
            for idx, table in enumerate(tables_stream, 1):
                page_num = table.page
                print(f"Table Stream {idx} detected on page {page_num} with accuracy {table.accuracy}")
                
                # Filter tables with low accuracy or too few columns
                if table.accuracy < 50 or table.df.shape[1] < 2:
                    print(f"  - Table has low accuracy or too few columns, might not be a real table")
                    continue
                
                # Check if this might be regular text formatted as a table
                if is_likely_paragraph(table.df):
                    print(f"  - This appears to be regular text, not adding as table")
                    continue
                
                # Save table as CSV
                table.to_csv(f"{output_folder}/page_{page_num}_table_stream_{idx}.csv")
                
                # Add to results if not already there
                page_key = f"page_{page_num}"
                if page_key not in results:
                    results[page_key] = {"text": [], "tables": []}
                results[page_key]["tables"].append(table.df)
                
                # Remove table text from the regular text content
                remove_table_from_text(results, page_key, table.df)
    except Exception as e:
        print(f"Error in camelot stream extraction: {e}")
    
    # 3. Try extracting with camelot stream without specific area for complex cases
    print("\n=== EXTRACTING WITH CAMELOT (STREAM) WITHOUT AREA ===")
    try:
        tables_stream_auto = camelot.read_pdf(pdf_path, pages='all', flavor='stream')
        if len(tables_stream_auto) > 0:
            for idx, table in enumerate(tables_stream_auto, 1):
                page_num = table.page
                print(f"Auto Stream Table {idx} detected on page {page_num} with accuracy {table.accuracy}")
                
                # Filter tables with low accuracy
                if table.accuracy < 50:
                    print(f"  - Table has low accuracy, might not be a real table")
                    continue
                
                # Check if already processed this table (to avoid duplicates)
                if is_duplicate_table(results, f"page_{page_num}", table.df):
                    print(f"  - Duplicate table, skipping")
                    continue
                
                # Check if this might be regular text formatted as a table
                if is_likely_paragraph(table.df):
                    print(f"  - This appears to be regular text, not adding as table")
                    continue
                
                # Save table as CSV
                table.to_csv(f"{output_folder}/page_{page_num}_table_stream_auto_{idx}.csv")
                
                # Add to results if not already there
                page_key = f"page_{page_num}"
                if page_key not in results:
                    results[page_key] = {"text": [], "tables": []}
                results[page_key]["tables"].append(table.df)
                
                # Remove table text from the regular text content
                remove_table_from_text(results, page_key, table.df)
    except Exception as e:
        print(f"Error in camelot auto stream extraction: {e}")
    
    # 4. Apply image preprocessing for problem pages
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
                        tmp_img_path = tmp.name
                        images[0].save(tmp_img_path)
                        
                        # Preprocess image
                        processed_img_path = f"{output_folder}/page_{problem_page}_processed.png"
                        preprocess_image_for_ocr(tmp_img_path, processed_img_path)
                        print(f"Preprocessing successfully applied for page {problem_page}")
            except Exception as e:
                print(f"Error preprocessing page {problem_page}: {e}")
    
    # 5. Output final results with clear distinction between text and tables
    print("\n=== FINAL RESULTS ===")
    for page_key, content in results.items():
        print(f"\n{page_key.upper().replace('_', ' ')}:")
        
        # Print regular text
        if content["text"]:
            print("\nREGULAR TEXT:")
            # Combine multiple text blocks and clean up
            combined_text = "\n".join(content["text"])
            cleaned_text = clean_text(combined_text)
            print(cleaned_text[:300] + "..." if len(cleaned_text) > 300 else cleaned_text)
            
        # Print tables
        if content["tables"]:
            print(f"\nTABLES ({len(content['tables'])} found):")
            for i, table_df in enumerate(content["tables"], 1):
                print(f"\nTable {i}:")
                print(tabulate(table_df.head(5), headers='keys', tablefmt='grid'))
                if len(table_df) > 5:
                    print(f"... {len(table_df) - 5} more rows ...")
        
        if not content["text"] and not content["tables"]:
            print("No content extracted from this page.")
    
    return results

def clean_text(text):
    """Clean up extracted text to remove artifacts and unnecessary whitespace"""
    # Remove excess whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove isolated characters that might be table artifacts
    text = re.sub(r'\s[A-Za-z0-9]\s', ' ', text)
    return text.strip()

def is_likely_paragraph(df):
    """Determine if a dataframe appears to be regular text rather than a table"""
    # Check if most cells only contain a single word or very few words
    word_counts = df.applymap(lambda x: len(str(x).split()) if pd.notnull(x) else 0)
    avg_words = word_counts.mean().mean()
    
    # Check if too many cells are empty
    empty_cells = df.isna().sum().sum() / (df.shape[0] * df.shape[1])
    
    # If there's only one column, likely not a table but a list or paragraph
    if df.shape[1] == 1:
        return True
    
    # If there are very long text cells, likely paragraphs not tables
    max_text_len = df.applymap(lambda x: len(str(x)) if pd.notnull(x) else 0).max().max()
    
    # Heuristics to identify paragraphs:
    # 1. Many words per cell on average (paragraphs vs table cells)
    # 2. Too many empty cells (sparse tables might be text with spacing)
    # 3. Very long text in cells
    return (avg_words > 15) or (empty_cells > 0.6) or (max_text_len > 200)

def is_duplicate_table(results, page_key, new_df):
    """Check if this table is already included in the results"""
    if page_key not in results or not results[page_key].get("tables"):
        return False
    
    for existing_df in results[page_key]["tables"]:
        # Simple check: same shape and some matching values
        if existing_df.shape == new_df.shape:
            # Check first few cells to see if they match
            matching_cells = 0
            sample_size = min(5, existing_df.size)
            for i in range(min(existing_df.shape[0], 3)):
                for j in range(min(existing_df.shape[1], 3)):
                    if str(existing_df.iloc[i, j]).strip() == str(new_df.iloc[i, j]).strip():
                        matching_cells += 1
            
            # If most sampled cells match, consider it a duplicate
            if matching_cells > sample_size * 0.7:
                return True
    
    return False

def remove_table_from_text(results, page_key, table_df):
    """Remove table content from the regular text to avoid duplication"""
    if page_key not in results or not results[page_key].get("text"):
        return
    
    # Convert table to string to look for in the text
    table_text = []
    for _, row in table_df.iterrows():
        # Join non-empty values from this row
        row_text = ' '.join([str(val) for val in row if pd.notnull(val) and str(val).strip()])
        if row_text:
            table_text.append(row_text)
    
    # If we have any table text
    if table_text:
        updated_texts = []
        for text_block in results[page_key]["text"]:
            current_text = text_block
            # Try to remove each table row from the text
            for row_text in table_text:
                if len(row_text) > 10:  # Only try to remove substantial rows
                    current_text = current_text.replace(row_text, '')
            
            # Add the modified text block
            updated_texts.append(current_text)
        
        # Update the text blocks
        results[page_key]["text"] = updated_texts

def identify_problem_pages(results):
    """Identify problematic pages (tables not detected properly)"""
    problem_pages = []
    
    for page_key, page_data in results.items():
        # Extract page number from key
        page_num = int(page_key.split('_')[1])
        
        # If no tables detected but text has table-like patterns
        if not page_data.get("tables") and page_data.get("text"):
            for text in page_data["text"]:
                # Simple heuristics: if many tabs or lines with consistent spacing patterns
                if text.count('\t') > 5 or len([line for line in text.split('\n') if line.count('  ') > 3]) > 3:
                    problem_pages.append(page_num)
                    break
    
    return problem_pages

def preprocess_image_for_ocr(image_path, output_path):
    """Preprocess image to clarify table structure"""
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
    print(f"Preprocessed image saved at: {output_path}")
    
    return output_path

# Example usage
if __name__ == "__main__":
    pdf_path = "studi_kasus/4_Tabel_Satu_Halaman_Normal_V2.pdf"
    results = extract_pdf_with_content_distinction(pdf_path)