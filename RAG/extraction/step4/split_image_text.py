import fitz  # PyMuPDF
import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional
import tempfile
import os
from PIL import Image
import json
from datetime import datetime
import shutil

@dataclass
class TableBoundary:
    page: int
    x0: float
    y0: float
    x1: float
    y1: float
    confidence: float

@dataclass
class PDFElement:
    type: str  # 'text' or 'table'
    content: str
    page: int
    bbox: Optional[Tuple[float, float, float, float]] = None
    
class PDFProcessor:
    def __init__(self, filename: str, output_dir: str = None):
        self.doc = fitz.open(filename)
        
        # Gunakan nama file PDF (tanpa ekstensi) untuk subfolder
        base_filename = os.path.splitext(os.path.basename(filename))[0]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if output_dir:
            # Jika output_dir disediakan, buat subfolder dengan nama file dan timestamp
            self.output_dir = os.path.join(output_dir, f"{base_filename}_{timestamp}")
            os.makedirs(self.output_dir, exist_ok=True)
            self.temp_dir = self.output_dir
        else:
            # Jika tidak, gunakan direktori temporary
            self.temp_dir = tempfile.mkdtemp()
            self.output_dir = self.temp_dir
            
        print(f"Gambar tabel akan disimpan di: {self.output_dir}")
    
    def _is_likely_table_region(self, text_blocks: List[dict]) -> bool:
        """Analyze text blocks to determine if they likely form a table structure"""
        if len(text_blocks) < 2:
            return False
            
        # Check for consistent horizontal alignment
        x_positions = [block['bbox'][0] for block in text_blocks]
        x_variance = np.var(x_positions)
        
        # Check for consistent vertical spacing
        y_positions = sorted([block['bbox'][1] for block in text_blocks])
        y_diffs = np.diff(y_positions)
        y_spacing_variance = np.var(y_diffs) if len(y_diffs) > 0 else float('inf')
        
        # Analyze content characteristics
        numeric_blocks = sum(1 for block in text_blocks if any(c.isdigit() for c in block['text']))
        total_blocks = len(text_blocks)
        
        return (x_variance < 100 and  # Consistent horizontal alignment
                y_spacing_variance < 50 and  # Consistent vertical spacing
                numeric_blocks / total_blocks > 0.2)  # At least 20% contains numbers
    
    def _detect_table_boundaries(self, page_idx: int) -> List[TableBoundary]:
        """Detect potential table regions on a page"""
        page = self.doc[page_idx]
        blocks = page.get_text("dict")["blocks"]
        
        table_regions = []
        current_region = []
        
        for block in blocks:
            if "lines" not in block:
                continue
                
            # Group adjacent blocks that might form a table
            if current_region and self._is_likely_table_region(current_region):
                # Calculate region boundaries
                x0 = min(b['bbox'][0] for b in current_region)
                y0 = min(b['bbox'][1] for b in current_region)
                x1 = max(b['bbox'][2] for b in current_region)
                y1 = max(b['bbox'][3] for b in current_region)
                
                table_regions.append(TableBoundary(
                    page=page_idx,
                    x0=x0, y0=y0,
                    x1=x1, y1=y1,
                    confidence=0.8  # Can be adjusted based on more sophisticated metrics
                ))
                
            current_region = []
        
        return table_regions
    
    def _capture_table_image(self, boundary: TableBoundary, table_index: int) -> str:
        """Capture a table region as an image"""
        page = self.doc[boundary.page]
        
        # Convert PDF coordinates to pixels (assuming 300 DPI)
        dpi = 300
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        
        # Get the region as an image
        pix = page.get_pixmap(matrix=mat, clip=fitz.Rect(
            boundary.x0, boundary.y0,
            boundary.x1, boundary.y1
        ))
        
        # Save with more informative filename
        img_filename = f"table_{table_index + 1}_page_{boundary.page + 1}_y{int(boundary.y0)}.png"
        img_path = os.path.join(self.output_dir, img_filename)
        pix.save(img_path)
        
        return img_path
    
    def _analyze_page_continuity(self, prev_boundary: TableBoundary, next_boundary: TableBoundary) -> bool:
        """Check if two table regions are likely part of the same table"""
        # Check if regions are on consecutive pages
        if next_boundary.page != prev_boundary.page + 1:
            return False
            
        # Check for similar horizontal alignment
        x_overlap = min(prev_boundary.x1, next_boundary.x1) - max(prev_boundary.x0, next_boundary.x0)
        x_overlap_ratio = x_overlap / (prev_boundary.x1 - prev_boundary.x0)
        
        # Check if the table starts near the top of the next page
        page_height = self.doc[next_boundary.page].rect.height
        starts_near_top = next_boundary.y0 < page_height * 0.2
        
        return x_overlap_ratio > 0.7 and starts_near_top
    
    def process(self) -> List[PDFElement]:
        """Process the PDF and extract text and table regions"""
        elements = []
        current_table_boundaries = []
        table_count = 0
        
        for page_idx in range(len(self.doc)):
            page = self.doc[page_idx]
            
            # Detect table regions
            table_boundaries = self._detect_table_boundaries(page_idx)
            
            # Process text blocks
            blocks = page.get_text("dict")["blocks"]
            current_text = []
            
            for block in blocks:
                if "lines" not in block:
                    continue
                    
                bbox = block["bbox"]
                
                # Check if block overlaps with any table region
                is_in_table = any(
                    tb.x0 <= bbox[0] <= tb.x1 and tb.y0 <= bbox[1] <= tb.y1
                    for tb in table_boundaries
                )
                
                if not is_in_table:
                    text = " ".join(
                        span["text"] for line in block["lines"]
                        for span in line["spans"]
                    )
                    current_text.append(text)
            
            # Add text elements
            if current_text:
                elements.append(PDFElement(
                    type="text",
                    content="\n".join(current_text),
                    page=page_idx
                ))
            
            # Process table regions
            for boundary in table_boundaries:
                # Check for table continuity
                if current_table_boundaries and self._analyze_page_continuity(
                    current_table_boundaries[-1], boundary
                ):
                    # Extend existing table
                    current_table_boundaries.append(boundary)
                else:
                    # Process any existing table
                    if current_table_boundaries:
                        table_images = [
                            self._capture_table_image(tb, table_count)
                            for tb in current_table_boundaries
                        ]
                        elements.append(PDFElement(
                            type="table",
                            content=json.dumps({
                                "image_paths": table_images,
                                "boundaries": [vars(tb) for tb in current_table_boundaries]
                            }),
                            page=current_table_boundaries[0].page,
                            bbox=(
                                current_table_boundaries[0].x0,
                                current_table_boundaries[0].y0,
                                current_table_boundaries[-1].x1,
                                current_table_boundaries[-1].y1
                            )
                        ))
                        table_count += 1
                    # Start new table
                    current_table_boundaries = [boundary]
        
        # Process final table if any
        if current_table_boundaries:
            table_images = [
                self._capture_table_image(tb, table_count)
                for tb in current_table_boundaries
            ]
            elements.append(PDFElement(
                type="table",
                content=json.dumps({
                    "image_paths": table_images,
                    "boundaries": [vars(tb) for tb in current_table_boundaries]
                }),
                page=current_table_boundaries[0].page,
                bbox=(
                    current_table_boundaries[0].x0,
                    current_table_boundaries[0].y0,
                    current_table_boundaries[-1].x1,
                    current_table_boundaries[-1].y1
                )
            ))
        
        return elements
    
    def __del__(self):
        """Cleanup when object is destroyed"""
        self.doc.close()
        if not self.output_dir:  # Only cleanup if using temporary directory
            try:
                shutil.rmtree(self.temp_dir)
            except:
                pass

def process_pdf(filename: str, output_dir: str = None) -> Tuple[List[PDFElement], List[str]]:
    """
    Main function to process a PDF file
    
    Args:
        filename (str): Path to the PDF file
        output_dir (str, optional): Directory to save table images. If None, uses a temporary directory.
    """
    processor = PDFProcessor(filename, output_dir)
    elements = processor.process()
    
    # Separate results into text and table paths
    text_elements = []
    table_images = []
    
    for element in elements:
        if element.type == "text":
            text_elements.append(element.content)
        else:  # table
            table_data = json.loads(element.content)
            table_images.extend(table_data["image_paths"])
    
    return elements, table_images

if __name__ == "__main__":
    filename = "studi_kasus/4_Tabel_Satu_Halaman_Normal_V3.pdf"  # Replace with your PDF file
    output_dir = "result"     # Replace with your desired output directory
    
    elements, table_images = process_pdf(filename, output_dir)
    
    print("Found elements:")
    for element in elements:
        print(f"Type: {element.type}")
        if element.type == "text":
            print(f"Content: {element.content[:100]}...")
        else:
            print(f"Table images: {json.loads(element.content)['image_paths']}")
        print("---")
