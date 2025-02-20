import os
import re
from typing import List, Dict, Any, Tuple, Optional
import pandas as pd
import numpy as np
import cv2
import pytesseract
from pdf2image import convert_from_path
import pdfplumber
from PIL import Image

class PDFExtractor:
    def __init__(self, pdf_path: str, output_dir: str = "output", dpi: int = 300):
        """Initialize the PDF extractor.
        
        Args:
            pdf_path: Path to the PDF file
            output_dir: Directory to save extracted content
            dpi: DPI for PDF conversion to images
        """
        self.pdf_path = pdf_path
        self.output_dir = output_dir
        self.dpi = dpi
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        # File name without extension
        self.base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        
        # Load PDF with pdfplumber
        self.pdf = pdfplumber.open(pdf_path)
        
        # Convert PDF to images for image processing approach
        self.images = convert_from_path(pdf_path, dpi=dpi)
        
        # Verify OpenCV installation by checking available functions
        self._check_opencv()

        # Add to PDFExtractor.__init__ to adjust table detection parameters
        self.table_detection_settings = {
            "vertical_strategy": "text",  # Try "text" instead of "lines" for tables without vertical lines
            "horizontal_strategy": "text",  # Try "text" instead of "lines" for tables without horizontal lines
            "snap_tolerance": 6,  # Increase for better alignment of cells
            "join_tolerance": 3,  # Increase to join nearby cells
            "edge_min_length": 3,  # Reduce to detect shorter lines
            "min_words_vertical": 2,  # Minimum words to consider for vertical alignment
            "min_words_horizontal": 2  # Minimum words to consider for horizontal alignment
        }

    def _check_opencv(self):
        """Check if OpenCV is properly installed with required functions."""
        required_functions = ['imread', 'cvtColor', 'getStructuringElement', 'morphologyEx', 'threshold', 'findContours']
        missing_functions = [func for func in required_functions if not hasattr(cv2, func)]
        
        if missing_functions:
            print(f"WARNING: The following OpenCV functions are missing: {missing_functions}")
            # print("Your OpenCV installation may be incomplete. Current version:", cv2.__version__)
            print("Trying alternative approach for image processing...")

    def extract_all(self) -> Dict[str, Any]:
        """Extract all content from the PDF including text and tables."""
        result = {
            "pages": [],
            "regular_tables": [],
            "financial_tables": []
        }
        
        for page_num, (page, img) in enumerate(zip(self.pdf.pages, self.images)):
            page_data = {"page_number": page_num + 1}
            
            # Extract text outside tables
            page_text = self._extract_text_outside_tables(page)
            page_data["text"] = page_text
            
            # Extract regular tables using pdfplumber
            regular_tables = self._extract_regular_tables(page)
            
            # If no regular tables found, try text alignment approach
            if not regular_tables:
                text_alignment_tables = self._extract_text_alignment_tables(page)
                if text_alignment_tables:
                    regular_tables = text_alignment_tables
            
            try:
                # Extract financial tables using image processing or fallback method
                financial_tables = self._extract_financial_tables_safe(img, page_num)
                if financial_tables:
                    for i, table in enumerate(financial_tables):
                        result["financial_tables"].append({
                            "page": page_num + 1,
                            "table_index": i,
                            "data": table
                        })
            except Exception as e:
                print(f"Error extracting financial tables from page {page_num+1}: {str(e)}")
                # Try fallback method
                financial_tables = self._extract_financial_tables_fallback(page)
                if financial_tables:
                    for i, table in enumerate(financial_tables):
                        result["financial_tables"].append({
                            "page": page_num + 1,
                            "table_index": i,
                            "data": table
                        })
            
            result["pages"].append(page_data)
            
        return result
    
    def _extract_text_alignment_tables(self, page) -> List[pd.DataFrame]:
        """Detect tables based on text alignment patterns when no lines are present."""
        words = page.extract_words(x_tolerance=3, y_tolerance=3)
        if not words:
            return []
            
        # Group words by y-coordinate to find rows
        y_coords = {}
        for word in words:
            y = round(word['top'])
            if y not in y_coords:
                y_coords[y] = []
            y_coords[y].append(word)
        
        # Sort rows by y-coordinate
        sorted_rows = [y_coords[y] for y in sorted(y_coords.keys())]
        
        # Identify potential tables where multiple rows have similar word patterns
        # (Multiple rows with similar number of aligned words might indicate a table)
        potential_tables = []
        current_table_rows = []
        
        for i, row in enumerate(sorted_rows):
            if i == 0:
                current_table_rows.append(row)
                continue
            
            prev_row = sorted_rows[i-1]
            
            # Simple heuristic: if rows have similar number of words and similar width span,
            # they might be part of the same table
            if (abs(len(row) - len(prev_row)) <= 2 and 
                abs(max(w['x1'] for w in row) - max(w['x1'] for w in prev_row)) < 50):
                current_table_rows.append(row)
            else:
                if len(current_table_rows) >= 3:  # At least 3 rows to be considered a table
                    potential_tables.append(current_table_rows)
                current_table_rows = [row]
        
        # Don't forget the last group
        if len(current_table_rows) >= 3:
            potential_tables.append(current_table_rows)
        
        # Convert potential tables to DataFrames
        result_tables = []
        for table_rows in potential_tables:
            # Find column boundaries by detecting consistent x-positions
            x_positions = []
            for row in table_rows:
                for word in row:
                    x_positions.append(word['x0'])
                    x_positions.append(word['x1'])
            
            # Group close x-positions
            x_groups = []
            sorted_x = sorted(x_positions)
            current_group = [sorted_x[0]]
            
            for x in sorted_x[1:]:
                if x - current_group[-1] < 10:  # Tolerance for column alignment
                    current_group.append(x)
                else:
                    x_groups.append(sum(current_group) / len(current_group))
                    current_group = [x]
                    
            if current_group:
                x_groups.append(sum(current_group) / len(current_group))
            
            # Use these x-positions to create a grid and place words in cells
            table_data = []
            for row in table_rows:
                row_data = [''] * (len(x_groups) - 1)
                for word in row:
                    # Find which column this word belongs to
                    for i in range(len(x_groups) - 1):
                        if x_groups[i] <= word['x0'] < x_groups[i+1]:
                            if row_data[i]:
                                row_data[i] += ' ' + word['text']
                            else:
                                row_data[i] = word['text']
                            break
                table_data.append(row_data)
            
            # Convert to DataFrame
            df = pd.DataFrame(table_data)
            
            # Clean up
            df = df.replace('', np.nan)
            df = df.dropna(axis=1, how='all')
            df = df.dropna(axis=0, how='all')
            
            if not df.empty and len(df) > 1:
                result_tables.append(df)
        
        return result_tables
    
    def _extract_text_outside_tables(self, page) -> str:
        """Extract text outside of table areas."""
        # Get table bounding boxes
        table_bounds = []
        
        # Regular tables detected by pdfplumber
        for table in page.find_tables():
            table_bounds.append(table.bbox)
        
        # Add financial tables boundaries by detecting horizontal lines
        horizontal_lines = page.horizontal_edges
        if len(horizontal_lines) > 1:
            # Group lines that might belong to same table
            potential_tables = self._group_horizontal_lines(horizontal_lines)
            for lines in potential_tables:
                if len(lines) >= 2:  # At least 2 horizontal lines to form a table
                    min_y = min([line['y0'] for line in lines]) - 5
                    max_y = max([line['y0'] for line in lines]) + 5
                    left_x = page.width
                    right_x = 0
                    
                    for line in lines:
                        left_x = min(left_x, line['x0'])
                        right_x = max(right_x, line['x1'])
                    
                    table_bounds.append((left_x, min_y, right_x, max_y))
        
        # Extract text with bounding boxes exclusion
        text = ""
        if table_bounds:
            # Extract text excluding table areas
            text = page.filter(lambda obj: not self._in_any_bbox(obj, table_bounds)).extract_text() or ""
        else:
            # If no tables detected, extract all text
            text = page.extract_text() or ""
            
        return text
    
    def _group_horizontal_lines(self, lines, y_tolerance=20, min_width=100):
        """Group horizontal lines that might belong to the same table."""
        # Filter out short lines that might not be table boundaries
        lines = [line for line in lines if line['x1'] - line['x0'] > min_width]
        
        if not lines:
            return []
            
        # Sort lines by y position
        sorted_lines = sorted(lines, key=lambda line: line['y0'])
        
        groups = []
        current_group = [sorted_lines[0]]
        
        for i in range(1, len(sorted_lines)):
            current_line = sorted_lines[i]
            previous_line = sorted_lines[i-1]
            
            # If the current line is close to the previous line, add to the current group
            if current_line['y0'] - previous_line['y0'] < y_tolerance:
                current_group.append(current_line)
            else:
                # Start a new group if there's a significant gap
                if len(current_group) >= 2:
                    groups.append(current_group)
                current_group = [current_line]
        
        # Don't forget the last group
        if len(current_group) >= 2:
            groups.append(current_group)
            
        return groups
    
    def _in_any_bbox(self, obj, bboxes):
        """Check if an object is within any of the bounding boxes."""
        if 'x0' not in obj or 'y0' not in obj or 'x1' not in obj or 'y1' not in obj:
            return False
            
        obj_bbox = (obj['x0'], obj['y0'], obj['x1'], obj['y1'])
        for bbox in bboxes:
            overlap = self._get_bbox_overlap(obj_bbox, bbox)
            if overlap > 0.5:  # If more than 50% of the object is inside a table
                return True
        return False
    
    def _get_bbox_overlap(self, bbox1, bbox2):
        """Calculate the overlap ratio between two bounding boxes."""
        x0 = max(bbox1[0], bbox2[0])
        y0 = max(bbox1[1], bbox2[1])
        x1 = min(bbox1[2], bbox2[2])
        y1 = min(bbox1[3], bbox2[3])
        
        if x0 >= x1 or y0 >= y1:
            return 0
            
        intersection = (x1 - x0) * (y1 - y0)
        bbox1_area = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
        
        if bbox1_area == 0:
            return 0
            
        return intersection / bbox1_area
    
    def _extract_regular_tables(self, page) -> List[pd.DataFrame]:
        """Extract regular tables with both explicit and implicit table structures."""
        tables = []

        # First try with standard line detection
        plumber_tables = page.find_tables(
            table_settings={
                "vertical_strategy": "lines", 
                "horizontal_strategy": "lines",
                "intersection_y_tolerance": 10,
                "intersection_x_tolerance": 10
            }
        )

        # If no tables found, try text-based alignment detection
        if not plumber_tables:
            plumber_tables = page.find_tables(
                table_settings=self.table_detection_settings
            )

        # If still no tables, try hybrid approach
        if not plumber_tables:
            plumber_tables = page.find_tables(
                table_settings={
                    "vertical_strategy": "text",
                    "horizontal_strategy": "lines",
                    "intersection_y_tolerance": 12,
                    "intersection_x_tolerance": 12
                }
            )
        
        for table in plumber_tables:
            if table is not None:
                # Convert to pandas DataFrame
                df = pd.DataFrame(table.extract())
                if not df.empty and len(df) > 1:  # Ensure it's not an empty table
                    # If the first row contains mostly None/empty values, use the second row as header
                    if df.iloc[0].isna().mean() > 0.5:
                        df = df.iloc[1:].reset_index(drop=True)
                    
                    # Clean up the DataFrame
                    df = df.replace('', np.nan)
                    
                    # Remove columns that are completely empty
                    df = df.dropna(axis=1, how='all')
                    
                    # Remove rows that are completely empty
                    df = df.dropna(axis=0, how='all')
                    
                    if not df.empty:
                        tables.append(df)
        
        return tables
    
    def _extract_financial_tables_safe(self, image, page_num) -> List[pd.DataFrame]:
        """Safely extract financial tables using image processing with fallbacks."""
        try:
            # Check if OpenCV has the required functions
            if not hasattr(cv2, 'cvtColor'):
                return self._extract_financial_tables_fallback(self.pdf.pages[page_num])
            
            return self._extract_financial_tables(image, page_num)
        except Exception as e:
            print(f"Error in image-based table extraction: {str(e)}")
            return self._extract_financial_tables_fallback(self.pdf.pages[page_num])
    
    def _extract_financial_tables(self, image, page_num) -> List[pd.DataFrame]:
        """Extract financial tables that only have horizontal lines using OpenCV."""
        # Convert PIL Image to OpenCV format
        img_cv = np.array(image)
        img_cv = cv2.cvtColor(img_cv, cv2.COLOR_RGB2BGR)
        
        # Create a grayscale version for processing
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        # Detect horizontal lines
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
        horizontal_lines = cv2.morphologyEx(gray, cv2.MORPH_OPEN, horizontal_kernel)
        
        # Threshold to get binary image
        _, thresh = cv2.threshold(horizontal_lines, 40, 255, cv2.THRESH_BINARY)
        
        # Find contours of horizontal lines
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filter contours to find potential tables
        horizontal_lines = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w > 100 and h < 10:  # Likely a horizontal line
                horizontal_lines.append((y, x, x + w))
        
        # Sort by y-coordinate
        horizontal_lines.sort()
        
        # Group lines into potential tables
        tables = []
        current_table = []
        
        for i, line in enumerate(horizontal_lines):
            if i == 0:
                current_table.append(line)
                continue
                
            prev_line = horizontal_lines[i-1]
            vertical_distance = line[0] - prev_line[0]
            
            # If the vertical distance between lines is small, consider them part of the same table
            if vertical_distance < 100:
                current_table.append(line)
            else:
                if len(current_table) >= 3:  # A table should have at least 3 horizontal lines
                    tables.append(current_table)
                current_table = [line]
        
        # Don't forget the last table
        if len(current_table) >= 3:
            tables.append(current_table)
        
        # Process each detected table
        result_tables = []
        for table_idx, table_lines in enumerate(tables):
            # Determine table boundaries
            min_y = table_lines[0][0] - 10
            max_y = table_lines[-1][0] + 10
            min_x = min([line[1] for line in table_lines])
            max_x = max([line[2] for line in table_lines])
            
            # Extract the table region
            table_img = img_cv[min_y:max_y, min_x:max_x]
            
            # Save the detected table for debugging
            debug_path = os.path.join(self.output_dir, f"{self.base_name}_page{page_num+1}_financial_table{table_idx}.png")
            cv2.imwrite(debug_path, table_img)
            
            # Extract text from the table image using OCR
            table_data = self._extract_financial_table_content(table_img, table_lines)
            if table_data is not None and not table_data.empty:
                result_tables.append(table_data)
        
        return result_tables
    
    def _extract_financial_table_content(self, table_img, table_lines) -> Optional[pd.DataFrame]:
        """Extract content from financial table images using OCR and row structure."""
        # Convert to grayscale for OCR
        gray = cv2.cvtColor(table_img, cv2.COLOR_BGR2GRAY)
        
        # Apply thresholding to improve OCR accuracy
        _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
        
        # Save processed image for OCR
        temp_img_path = os.path.join(self.output_dir, "temp_ocr_image.png")
        cv2.imwrite(temp_img_path, 255 - binary)  # Invert back for OCR
        
        # Use pytesseract to extract text with bounding boxes
        custom_config = r'--oem 3 --psm 6'
        ocr_data = pytesseract.image_to_data(Image.open(temp_img_path), config=custom_config, output_type=pytesseract.Output.DICT)
        
        # Normalize table lines to image coordinates
        table_height = table_img.shape[0]
        base_y = 0
        normalized_lines = [(y - table_lines[0][0] + 10, x1, x2) for y, x1, x2 in table_lines]
        
        # Group text by rows based on horizontal lines
        rows = []
        current_row = []
        
        # Filter valid text
        valid_indices = [i for i, conf in enumerate(ocr_data['conf']) 
                        if conf > 0 and ocr_data['text'][i].strip()]
        
        # Extract all text with positions
        text_items = []
        for i in valid_indices:
            x = ocr_data['left'][i]
            y = ocr_data['top'][i]
            w = ocr_data['width'][i]
            h = ocr_data['height'][i]
            text = ocr_data['text'][i]
            
            # Skip empty text
            if not text.strip():
                continue
                
            text_items.append({
                'text': text,
                'x': x,
                'y': y,
                'center_y': y + h/2,
                'right': x + w
            })
        
        # Sort text items by y position
        text_items.sort(key=lambda item: item['y'])
        
        # Find rows based on horizontal lines
        rows = []
        for i in range(len(normalized_lines) - 1):
            top_line = normalized_lines[i][0]
            bottom_line = normalized_lines[i+1][0]
            
            # Get all text between these lines
            row_items = [item for item in text_items 
                        if top_line <= item['center_y'] < bottom_line]
            
            if row_items:
                # Sort items in the row by x position
                row_items.sort(key=lambda item: item['x'])
                row_text = [item['text'] for item in row_items]
                rows.append(row_text)
        
        # If we have rows, create a DataFrame
        if rows:
            # Determine max columns
            max_cols = max(len(row) for row in rows)
            
            # Normalize row lengths
            normalized_rows = [row + [''] * (max_cols - len(row)) for row in rows]
            
            # Create DataFrame
            df = pd.DataFrame(normalized_rows)
            
            # Clean up: Remove completely empty rows and columns
            df = df.replace('', np.nan)
            df = df.dropna(how='all')
            df = df.dropna(axis=1, how='all')
            
            # First row is header if it doesn't contain numeric values
            first_row_is_header = True
            for cell in df.iloc[0]:
                if isinstance(cell, str) and cell.strip() and re.search(r'\d', cell):
                    first_row_is_header = False
                    break
            
            if first_row_is_header and len(df) > 1:
                df.columns = df.iloc[0]
                df = df.iloc[1:].reset_index(drop=True)
            
            return df
        
        return None
    
    def _extract_financial_tables_fallback(self, page) -> List[pd.DataFrame]:
        """Fallback method to extract financial tables using pdfplumber's horizontal lines."""
        tables = []
        
        # Get horizontal lines
        horizontal_lines = page.horizontal_edges
        if len(horizontal_lines) < 3:
            return []
            
        # Group horizontal lines that might belong to the same table
        potential_tables = self._group_horizontal_lines(horizontal_lines)
        
        for table_lines in potential_tables:
            if len(table_lines) < 3:  # Need at least 3 lines to form a meaningful table
                continue
                
            # Sort lines by y-position
            table_lines = sorted(table_lines, key=lambda line: line['y0'])
            
            # Get table boundaries
            min_y = table_lines[0]['y0'] - 5
            max_y = table_lines[-1]['y0'] + 5
            min_x = min([line['x0'] for line in table_lines])
            max_x = max([line['x1'] for line in table_lines])
            
            # Crop page to table area
            table_crop = page.crop((min_x, min_y, max_x, max_y))
            
            # Try to extract table using only horizontal lines
            plumber_table = table_crop.extract_table(
                table_settings={
                    "vertical_strategy": "text",
                    "horizontal_strategy": "lines",
                    "intersection_y_tolerance": 10,
                    "intersection_x_tolerance": 10
                }
            )
            
            if plumber_table:
                # Convert to pandas DataFrame
                df = pd.DataFrame(plumber_table)
                
                # Clean up the DataFrame
                df = df.replace('', np.nan)
                df = df.dropna(axis=1, how='all')
                df = df.dropna(axis=0, how='all')
                
                if not df.empty and len(df) > 1:
                    # Check if first row could be a header
                    first_row_is_header = True
                    for cell in df.iloc[0]:
                        if isinstance(cell, str) and cell and re.search(r'\d', str(cell)):
                            first_row_is_header = False
                            break
                    
                    if first_row_is_header:
                        df.columns = df.iloc[0]
                        df = df.iloc[1:].reset_index(drop=True)
                    
                    tables.append(df)
            else:
                # If table extraction failed, try to detect cells based on text positions
                words = table_crop.extract_words()
                if words:
                    # Group words by lines based on y-position
                    y_positions = [word['top'] for word in words]
                    unique_y = sorted(list(set([round(y/5)*5 for y in y_positions])))
                    
                    # Group words into rows
                    rows = []
                    for y in unique_y:
                        row_words = [word for word in words if abs(word['top'] - y) < 5]
                        row_words.sort(key=lambda w: w['x0'])
                        if row_words:
                            row_text = [word['text'] for word in row_words]
                            rows.append(row_text)
                    
                    if rows:
                        # Determine max columns
                        max_cols = max(len(row) for row in rows)
                        
                        # Normalize row lengths
                        normalized_rows = [row + [''] * (max_cols - len(row)) for row in rows]
                        
                        # Create DataFrame
                        df = pd.DataFrame(normalized_rows)
                        
                        # Clean up
                        df = df.replace('', np.nan)
                        df = df.dropna(how='all')
                        df = df.dropna(axis=1, how='all')
                        
                        if not df.empty and len(df) > 1:
                            tables.append(df)
        
        return tables
    
    def save_results(self, results: Dict[str, Any]) -> None:
        """Save extraction results to files."""
        # Save text content
        text_path = os.path.join(self.output_dir, f"{self.base_name}_text.txt")
        with open(text_path, 'w', encoding='utf-8') as f:
            for page in results['pages']:
                f.write(f"--- Page {page['page_number']} ---\n\n")
                f.write(page['text'])
                f.write("\n\n")
        
        # Save regular tables
        for i, table_info in enumerate(results['regular_tables']):
            table_path = os.path.join(self.output_dir, 
                                     f"{self.base_name}_page{table_info['page']}_regular_table{table_info['table_index']}.csv")
            table_info['data'].to_csv(table_path, index=False)
        
        # Save financial tables
        for i, table_info in enumerate(results['financial_tables']):
            table_path = os.path.join(self.output_dir, 
                                     f"{self.base_name}_page{table_info['page']}_financial_table{table_info['table_index']}.csv")
            table_info['data'].to_csv(table_path, index=False)
        
        # Save a summary file
        summary_path = os.path.join(self.output_dir, f"{self.base_name}_summary.txt")
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(f"Extraction Summary for {self.pdf_path}\n")
            f.write(f"Total Pages: {len(results['pages'])}\n")
            f.write(f"Regular Tables: {len(results['regular_tables'])}\n")
            f.write(f"Financial Tables: {len(results['financial_tables'])}\n\n")
            
            f.write("Regular Tables:\n")
            for i, table in enumerate(results['regular_tables']):
                f.write(f"  - Page {table['page']}, Table {table['table_index']+1}: "
                       f"{table['data'].shape[0]} rows × {table['data'].shape[1]} columns\n")
            
            f.write("\nFinancial Tables:\n")
            for i, table in enumerate(results['financial_tables']):
                f.write(f"  - Page {table['page']}, Table {table['table_index']+1}: "
                       f"{table['data'].shape[0]} rows × {table['data'].shape[1]} columns\n")

    def close(self):
        """Close the PDF file."""
        self.pdf.close()


# Example usage
if __name__ == "__main__":
    # Replace with your PDF path
    pdf_path = "studi_kasus/4_Tabel_Satu_Halaman_Normal_V1.pdf"
    output_dir = "extracted_content"
    
    extractor = PDFExtractor(pdf_path, output_dir)
    results = extractor.extract_all()
    extractor.save_results(results)
    extractor.close()
    
    print(f"Extraction complete. Results saved to {output_dir}")
