import fitz
import numpy as np
import cv2
from PIL import Image
import io
from pathlib import Path
from typing import List, Tuple, Dict, Optional, Union
import os
import json
import concurrent.futures
from tqdm import tqdm

class PDFProcessor:
    def __init__(
        self,
        min_line_length: int = 200,
        line_thickness: int = 2,
        header_threshold: float = 50,
        footer_threshold: float = 50,
        scan_header_threshold: float = 100,
        scan_footer_threshold: float = 100,
        min_lines_per_page: int = 2,
        output_dir: str = "output"
    ):
        self.min_line_length = min_line_length
        self.line_thickness = line_thickness
        self.header_threshold = header_threshold
        self.footer_threshold = footer_threshold
        self.scan_header_threshold = scan_header_threshold
        self.scan_footer_threshold = scan_footer_threshold
        self.min_lines_per_page = min_lines_per_page
        self.output_dir = output_dir
        
        # Create output directories
        self.base_output_dir = Path(output_dir)
        self.base_output_dir.mkdir(parents=True, exist_ok=True)
        
        self.img_output_dir = self.base_output_dir / "images"
        self.img_output_dir.mkdir(parents=True, exist_ok=True)
        
        # State tracking
        self.current_line_group = []
        self.all_line_groups = []
        self.page_images = {}
        self.page_info = {}

    def process_pdf(self, pdf_path: str) -> Dict:
        """
        Main processing function that handles the entire PDF
        """
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        
        print(f"Processing {total_pages} pages from {pdf_path}")
        
        # Process each page
        for page_num in tqdm(range(total_pages), desc="Processing pages"):
            self._process_page(doc, page_num)
            
        # Close any open group
        if self.current_line_group:
            self.all_line_groups.append(self.current_line_group)
            self.current_line_group = []
        
        # Process groups for extraction
        extraction_results = self._process_all_groups(doc)
        
        # Save final results
        result_path = self._save_results(extraction_results)
        
        doc.close()
        
        return {
            "result_path": result_path,
            "line_groups": self.all_line_groups,
            "extraction_results": extraction_results
        }
    
    def _process_page(self, doc: fitz.Document, page_num: int) -> Dict:
        """
        Process a single page to detect content type and handle accordingly
        """
        page = doc[page_num]
        page_width, page_height = page.rect.width, page.rect.height
        
        # Check if scanned or native PDF
        text = page.get_text()
        is_scanned = len(text.strip()) < 50  # Threshold for considering as scanned
        
        # Check page rotation
        rotation = page.rotation
        
        # Set thresholds based on document type
        current_header = self.scan_header_threshold if is_scanned else self.header_threshold
        current_footer = self.scan_footer_threshold if is_scanned else self.footer_threshold
        
        # Store page info
        self.page_info[page_num] = {
            "page_num": page_num + 1,  # 1-based page number
            "is_scanned": is_scanned,
            "rotation": rotation,
            "width": page_width,
            "height": page_height,
            "has_lines": False,
            "lines": []
        }
        
        # Detect lines
        page_img, lines = self._detect_lines(
            page, 
            header_threshold=current_header,
            footer_threshold=current_footer
        )
        
        # Store image for later use
        if page_img is not None:
            self.page_images[page_num] = page_img
        
        # Handle based on line detection result
        if lines and len(lines) >= self.min_lines_per_page:
            self.page_info[page_num]["has_lines"] = True
            self.page_info[page_num]["lines"] = lines
            
            # Add to current group
            self.current_line_group.append(page_num)
        else:
            # No lines detected, process current group if it exists
            if self.current_line_group:
                self.all_line_groups.append(self.current_line_group)
                self.current_line_group = []
                
            # For non-line pages, extract text based on document type
            if is_scanned:
                extracted_text = self._extract_via_ocr(page_img)
            else:
                extracted_text = self._extract_native_pdf_text(page)
                
            self.page_info[page_num]["extracted_text"] = extracted_text
        
        return self.page_info[page_num]
    
    def _detect_lines(
        self, 
        page: fitz.Page,
        header_threshold: float,
        footer_threshold: float
    ) -> Tuple[Optional[np.ndarray], List[Dict]]:
        """
        Detect horizontal lines in a page
        """
        # Render page to image
        zoom = 2
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        
        # Save original image for later use
        original_img = img.copy()
        
        # Convert to grayscale for processing
        if img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2GRAY)
            original_img = cv2.cvtColor(original_img, cv2.COLOR_RGBA2BGR)
        elif img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            original_img = cv2.cvtColor(original_img, cv2.COLOR_RGB2BGR)
            
        page_height = page.rect.height
        
        # Apply rotation handling
        rotation = page.rotation
        if rotation == 180:
            img = cv2.rotate(img, cv2.ROTATE_180)
            original_img = cv2.rotate(original_img, cv2.ROTATE_180)
        
        # Detect horizontal lines
        _, binary = cv2.threshold(img, 200, 255, cv2.THRESH_BINARY_INV)
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (self.min_line_length, self.line_thickness))
        detect_horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)
        
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, self.line_thickness))
        detect_horizontal = cv2.dilate(detect_horizontal, horizontal_kernel, iterations=1)
        
        contours, _ = cv2.findContours(detect_horizontal, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filter lines
        valid_lines = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            y_pdf = y / zoom
            
            # Check minimum length
            if w < self.min_line_length:
                continue
                
            # Check header/footer position
            if (y_pdf < header_threshold) or (y_pdf > page_height - footer_threshold):
                continue
            
            # Apply rotation corrections for coordinates
            x1 = x / zoom
            y1 = y / zoom - 0.5
            x2 = (x + w) / zoom
            y2 = y / zoom + 0.5
            
            if rotation == 90:
                x1, y1, x2, y2 = y1, page.rect.width - x2, y2, page.rect.width - x1
            elif rotation == 180:
                x1, y1, x2, y2 = page.rect.width - x2, page_height - y2, page.rect.width - x1, page_height - y1
            elif rotation == 270:
                x1, y1, x2, y2 = page_height - y2, x1, page_height - y1, x2
            
            valid_lines.append({
                'y_position': y / zoom,
                'x_min': x1,
                'x_max': x2,
                'width': w / zoom
            })
        
        return original_img, valid_lines
    
    def _extract_via_ocr(self, img: np.ndarray) -> str:
        """
        Extract text via OCR using pytesseract
        """
        try:
            import pytesseract
            
            # Make sure image is in correct format for tesseract (RGB)
            if len(img.shape) == 2:
                # Convert grayscale to RGB
                img_rgb = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
            elif img.shape[2] == 3:
                # Already RGB or BGR, make sure it's RGB
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            elif img.shape[2] == 4:
                # RGBA or BGRA, convert to RGB
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
            else:
                img_rgb = img
            
            # Use pytesseract to extract text
            custom_config = r'--oem 3 --psm 6'  # OCR Engine Mode = 3 (default), Page Segmentation Mode = 6 (assume single uniform block of text)
            text = pytesseract.image_to_string(img_rgb, config=custom_config)
            
            # Additional post-processing if needed
            text = text.strip()
            
            return text
        except ImportError:
            # Inform user that pytesseract is not installed
            print("Warning: pytesseract not found. OCR extraction will not work properly.")
            return "OCR extraction failed: pytesseract not installed"
        except Exception as e:
            print(f"Error during OCR extraction: {e}")
            return f"OCR extraction failed: {str(e)}"
        
    
    def _extract_native_pdf_text(self, page: fitz.Page) -> str:
        """
        Extract text from native PDF using unstructured library
        """
        try:
            from unstructured.partition.pdf import partition_pdf_page
            
            # Get page number for extraction
            page_num = page.number
            page_path = self._temp_save_page(page)
            
            # Use unstructured to extract text from the page
            elements = partition_pdf_page(filename=page_path, page_number=page_num)
            
            # Clean up temporary file
            if os.path.exists(page_path):
                os.remove(page_path)
            
            # Combine all text elements
            text = "\n".join([str(element) for element in elements])
            
            return text
        except ImportError:
            # Fallback to PyMuPDF extraction if unstructured is not available
            print("Warning: unstructured library not found. Using fallback extraction method.")
            return page.get_text()
        except Exception as e:
            print(f"Error extracting text with unstructured: {e}")
            # Fallback to PyMuPDF extraction
            return page.get_text()

    def _temp_save_page(self, page: fitz.Page) -> str:
        """
        Temporarily save a page to disk for processing by external libraries
        """
        temp_doc = fitz.open()
        temp_doc.insert_pdf(page.parent, from_page=page.number, to_page=page.number)
        temp_path = f"{self.output_dir}/temp_page_{page.number}.pdf"
        temp_doc.save(temp_path)
        temp_doc.close()
        return temp_path
        
    
    def _process_all_groups(self, doc: fitz.Document) -> Dict:
        """
        Process all line groups with appropriate methods
        """
        results = {}
        
        # Process each group of pages with lines
        for group_idx, group in enumerate(self.all_line_groups):
            group_results = self._process_line_group(doc, group, group_idx)
            
            # Add to overall results
            start_page = group[0] + 1  # 1-based page numbers
            end_page = group[-1] + 1
            group_key = f"group_{start_page}" + (f"-{end_page}" if start_page != end_page else "")
            
            results[group_key] = group_results
        
        # Add results from pages with no lines
        for page_num, page_data in self.page_info.items():
            if not page_data["has_lines"] and "extracted_text" in page_data:
                results[f"page_{page_num+1}"] = {
                    "extraction_method": "native" if not page_data["is_scanned"] else "ocr",
                    "text": page_data["extracted_text"]
                }
        
        return results
    
    def _process_line_group(self, doc: fitz.Document, group: List[int], group_idx: int) -> Dict:
        """
        Process a group of pages with lines using multimodal LLM
        """
        # Create PDF for the group
        group_pdf_path = self._create_group_pdf(doc, group)
        
        # Prepare images for multimodal LLM
        image_paths = self._prepare_group_images(group, group_idx)
        
        # TODO: Actual LLM processing would happen here
        # For now, return placeholder results
        return {
            "extraction_method": "multimodal_llm",
            "pdf_path": group_pdf_path,
            "image_paths": image_paths,
            "detected_tables": len(group),
            "extracted_data": "LLM extraction would be implemented here"
        }
    
    def _create_group_pdf(self, doc: fitz.Document, group: List[int]) -> str:
        """
        Create a PDF containing only the pages in the group
        """
        dest_doc = fitz.open()
        
        for page_num in group:
            dest_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
        
        # Save PDF group
        group_start = group[0] + 1  # +1 for 1-based page numbering
        group_end = group[-1] + 1
        
        if len(group) == 1:
            filename = f"{self.output_dir}/pages_with_lines_page_{group_start}.pdf"
        else:
            filename = f"{self.output_dir}/pages_with_lines_pages_{group_start}-{group_end}.pdf"
        
        dest_doc.save(filename)
        dest_doc.close()
        
        return filename
    
    def _prepare_group_images(self, group: List[int], group_idx: int) -> List[str]:
        """
        Prepare and save images for the group for multimodal LLM processing
        """
        image_paths = []
        
        # Create group identifier
        group_start = group[0] + 1  # 1-based page numbers
        group_end = group[-1] + 1
        group_id = f"{group_start}" + (f"-{group_end}" if group_start != group_end else "")
        
        # Save each image in the group
        for i, page_num in enumerate(group):
            if page_num in self.page_images:
                img_path = f"{self.img_output_dir}/table_pages_{group_id}_part{i+1}.png"
                cv2.imwrite(img_path, self.page_images[page_num])
                
                # Convert to PIL image for potential LLM API use
                pil_img = Image.fromarray(cv2.cvtColor(self.page_images[page_num], cv2.COLOR_BGR2RGB))
                
                # Store path for later use
                image_paths.append(img_path)
        
        return image_paths
    
    def _save_results(self, extraction_results: Dict) -> str:
        """
        Save final results as JSON
        """
        output_path = f"{self.output_dir}/extraction_results.json"
        
        # Create final results structure
        final_results = {
            "document_info": {
                "total_pages": len(self.page_info),
                "pages_with_lines": sum(1 for info in self.page_info.values() if info["has_lines"]),
                "line_groups": len(self.all_line_groups)
            },
            "extraction_results": extraction_results
        }
        
        # Write to JSON file
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(final_results, f, indent=2, ensure_ascii=False)
            
        return output_path

# Placeholder for multimodal LLM API integration (to be implemented)
class MultimodalLLMProcessor:
    def __init__(self, api_key=None):
        self.api_key = api_key
    
    def process_images(self, image_paths: List[str], prompt: str) -> Dict:
        """
        Process images with a multimodal LLM API
        This is a placeholder - implement with actual API calls
        """
        # TODO: Implement actual API call
        return {
            "status": "success",
            "message": f"Would process {len(image_paths)} images with prompt: {prompt}",
            "extracted_data": {
                "tables": [{"placeholder": "table data would be here"}]
            }
        }

# Example usage
def process_document(
    pdf_path: str,
    output_dir: str = "output",
    min_line_length: int = 30,
    line_thickness: int = 1,
    header_threshold: float = 120,
    footer_threshold: float = 100,
    scan_header_threshold: float = 120,
    scan_footer_threshold: float = 100,
    min_lines_per_page: int = 2,
    parallel: bool = False
):
    """
    Main function to process a document
    """
    processor = PDFProcessor(
        min_line_length=min_line_length,
        line_thickness=line_thickness,
        header_threshold=header_threshold,
        footer_threshold=footer_threshold,
        scan_header_threshold=scan_header_threshold,
        scan_footer_threshold=scan_footer_threshold,
        min_lines_per_page=min_lines_per_page,
        output_dir=output_dir
    )
    
    results = processor.process_pdf(pdf_path)
    
    print(f"Processing complete. Results saved to: {results['result_path']}")
    return results

def check_dependencies():
    """
    Check if required dependencies are installed
    """
    missing_deps = []
    
    try:
        import pytesseract
    except ImportError:
        missing_deps.append("pytesseract")
    
    try:
        from unstructured.partition.pdf import partition_pdf_page
    except ImportError:
        missing_deps.append("unstructured")
    
    if missing_deps:
        print(f"Warning: Missing dependencies: {', '.join(missing_deps)}")
        print("Install with: pip install " + " ".join(missing_deps))
        
    return len(missing_deps) == 0

if __name__ == "__main__":
    results = process_document(
        pdf_path="studi_kasus/Batavia Dana Likuid.pdf",
        output_dir="output_enhanced",
        min_line_length=30,
        line_thickness=1,
        header_threshold=120,
        footer_threshold=100,
        scan_header_threshold=120,
        scan_footer_threshold=100,
        min_lines_per_page=2
    )
    # check_dependencies()