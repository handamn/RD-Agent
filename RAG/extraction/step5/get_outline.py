import fitz  # PyMuPDF
import numpy as np
import cv2
from PIL import Image
import io
import os

class PDFProcessor:
    def __init__(self):
        self.pdf_path = "studi_kasus/7_Tabel_N_Halaman_Normal_V3.pdf"
        self.output_dir = "result"
        self.doc = fitz.open(self.pdf_path)
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        
        self.table_counter = 0
        self.min_table_area = 10000  # Minimum area to consider as table
        self.line_thickness_threshold = 2  # Minimum thickness for table lines

    def detect_table_boundaries(self, page_image):
        """Enhanced table detection with better filtering"""
        # Convert to grayscale
        gray = cv2.cvtColor(page_image, cv2.COLOR_BGR2GRAY)
        
        # Apply adaptive thresholding for better line detection
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, 
            cv2.THRESH_BINARY_INV, 15, 2
        )

        # Detect horizontal and vertical lines with more precise kernels
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (50, 1))
        vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 50))

        # Detect lines
        horizontal_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel)
        vertical_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel)

        # Combine lines
        table_mask = cv2.addWeighted(horizontal_lines, 1, vertical_lines, 1, 0)
        
        # Clean up noise
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        table_mask = cv2.morphologyEx(table_mask, cv2.MORPH_CLOSE, kernel)

        # Find contours
        contours, _ = cv2.findContours(table_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        table_boundaries = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h
            
            # Filter based on area and aspect ratio
            if area > self.min_table_area and 0.1 < h/w < 10:
                # Check if the region contains enough horizontal and vertical lines
                roi_h = horizontal_lines[y:y+h, x:x+w]
                roi_v = vertical_lines[y:y+h, x:x+w]
                
                if (cv2.countNonZero(roi_h) > w * 0.3 and 
                    cv2.countNonZero(roi_v) > h * 0.3):
                    # Expand boundaries slightly to ensure we capture the full table
                    x = max(0, x - 5)
                    y = max(0, y - 5)
                    w = min(page_image.shape[1] - x, w + 10)
                    h = min(page_image.shape[0] - y, h + 10)
                    table_boundaries.append((x, y, w, h))

        # Merge overlapping or very close boundaries
        return self.merge_close_boundaries(table_boundaries)

    def merge_close_boundaries(self, boundaries, distance_threshold=20):
        """Merge table boundaries that are close to each other"""
        if not boundaries:
            return []

        def overlaps_or_close(b1, b2, threshold):
            x1, y1, w1, h1 = b1
            x2, y2, w2, h2 = b2
            return not (x1 + w1 + threshold < x2 or 
                       x2 + w2 + threshold < x1 or 
                       y1 + h1 + threshold < y2 or 
                       y2 + h2 + threshold < y1)

        merged = []
        current_group = list(boundaries[0])

        for boundary in boundaries[1:]:
            if overlaps_or_close(current_group, boundary, distance_threshold):
                # Merge boundaries
                x = min(current_group[0], boundary[0])
                y = min(current_group[1], boundary[1])
                w = max(current_group[0] + current_group[2], 
                       boundary[0] + boundary[2]) - x
                h = max(current_group[1] + current_group[3], 
                       boundary[1] + boundary[3]) - y
                current_group = [x, y, w, h]
            else:
                merged.append(tuple(current_group))
                current_group = list(boundary)
        
        merged.append(tuple(current_group))
        return merged

    def extract_text_blocks(self, page, table_boundaries):
        """Extract text from non-table areas"""
        text_blocks = []
        blocks = page.get_text("blocks")
        
        table_rects = [(b[0], b[1], b[0] + b[2], b[1] + b[3]) for b in table_boundaries]
        
        for block in blocks:
            block_rect = block[:4]
            is_in_table = False
            
            for table_rect in table_rects:
                if (block_rect[0] < table_rect[2] and block_rect[2] > table_rect[0] and
                    block_rect[1] < table_rect[3] and block_rect[3] > table_rect[1]):
                    is_in_table = True
                    break
            
            if not is_in_table:
                text_blocks.append(block[4])
        
        return text_blocks

    def capture_table(self, page, boundary):
        """Capture table with improved quality"""
        x, y, w, h = boundary
        # Use higher resolution for better quality
        zoom = 2.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        # Adjust coordinates for zoom
        x, y, w, h = [int(val * zoom) for val in (x, y, w, h)]
        table_img = img.crop((x, y, x+w, y+h))
        return table_img

    def process_pdf(self):
        """Main processing function"""
        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            print(f"\n{'='*50}")
            print(f"Processing page {page_num + 1}")
            print(f"{'='*50}")
            
            # Convert page to image
            pix = page.get_pixmap()
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            img_np = np.array(img)
            
            # Detect tables
            table_boundaries = self.detect_table_boundaries(img_np)
            
            # Extract non-table text
            text_blocks = self.extract_text_blocks(page, table_boundaries)
            
            # Print extracted text
            if text_blocks:
                print("\nExtracted text:")
                print("-" * 50)
                for block in text_blocks:
                    clean_text = ' '.join(block.split())
                    if clean_text:
                        print(clean_text)
                        print("-" * 50)
            
            # Process detected tables
            for boundary in table_boundaries:
                self.table_counter += 1
                table_img = self.capture_table(page, boundary)
                output_path = os.path.join(self.output_dir, f"table_{self.table_counter}.png")
                table_img.save(output_path)
                print(f"Saved table: {output_path}")

    def close(self):
        """Close the PDF document"""
        self.doc.close()

def main():
    processor = PDFProcessor()
    processor.process_pdf()
    processor.close()

if __name__ == "__main__":
    main()