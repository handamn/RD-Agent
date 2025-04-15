import os
import json
import time
import google.generativeai as genai
from PIL import Image
from pdf2image import convert_from_path
from dotenv import load_dotenv
from typing import Dict, List, Any

load_dotenv()

class MultimodalPDFExtractor:
    def __init__(self):
        self.api_key = os.getenv('GOOGLE_API_KEY')
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.temp_dir = "temporary_dir"
        os.makedirs(self.temp_dir, exist_ok=True)
        
    def process_pdf(self, pdf_path: str, page_analysis: Dict) -> Dict:
        """Proses seluruh PDF berdasarkan analisis halaman"""
        start_time = time.time()
        results = {}
        total_pages = len(page_analysis)
        
        for page_num, analysis in page_analysis.items():
            if self._requires_multimodal(analysis):
                print(f"Processing page {page_num} with multimodal...")
                page_result = self._extract_page(pdf_path, int(page_num), analysis)
                results[page_num] = {
                    "analysis": analysis,
                    "extraction": page_result
                }
            else:
                print(f"Skipping page {page_num} - not requiring multimodal processing")
        
        return {
            "metadata": self._generate_metadata(pdf_path, total_pages, time.time() - start_time),
            "pages": results
        }
    
    def _generate_metadata(self, pdf_path: str, total_pages: int, processing_time: float) -> Dict:
        return {
            "filename": os.path.basename(pdf_path),
            "total_pages": total_pages,
            "extraction_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "processing_time": round(processing_time, 2)
        }
    
    def _requires_multimodal(self, analysis: Dict) -> bool:
        """Determines if page requires multimodal processing"""
        return ((analysis['ocr_status'] and analysis['line_status'] and analysis['ai_status']) or 
                (not analysis['ocr_status'] and analysis['line_status'] and analysis['ai_status']))
    
    def _extract_page(self, pdf_path: str, page_num: int, analysis_data: Dict) -> Dict:
        """Extracts content from a single page"""
        start_time = time.time()
        
        # Step 1: Convert PDF page to image
        temp_image_path = os.path.join(self.temp_dir, f"page_{page_num}.png")
        if not self._save_page_as_image(pdf_path, page_num, temp_image_path):
            return {
                "method": "multimodal_llm",
                "status": "error",
                "error": "Failed to convert page to image",
                "processing_time": 0.0
            }
        
        # Step 2: Extract content
        try:
            pil_image = Image.open(temp_image_path)
            prompt = self._create_enhanced_prompt(analysis_data)
            response = self._call_gemini_api(pil_image, prompt)
            content_blocks = self._parse_response(response, page_num)
            
            return {
                "method": "multimodal_llm",
                "status": "success",
                "processing_time": round(time.time() - start_time, 2),
                "content_blocks": content_blocks
            }
        except Exception as e:
            return {
                "method": "multimodal_llm",
                "status": "error",
                "error": str(e),
                "processing_time": round(time.time() - start_time, 2)
            }
        finally:
            # Clean up temporary image
            if os.path.exists(temp_image_path):
                os.remove(temp_image_path)
    
    def _save_page_as_image(self, pdf_path: str, page_num: int, output_path: str) -> bool:
        """Converts PDF page to image"""
        try:
            images = convert_from_path(
                pdf_path,
                first_page=page_num,
                last_page=page_num,
                dpi=200,
                fmt='png',
                poppler_path=self._get_poppler_path()
            )
            images[0].save(output_path, 'PNG')
            return True
        except Exception as e:
            print(f"Error converting page {page_num}: {e}")
            return False
    
    def _get_poppler_path(self) -> str:
        """Helper to get poppler path for different OS"""
        # Implement your OS-specific path here if needed
        return None
    
    def _create_enhanced_prompt(self, analysis: Dict) -> str:
        """Creates optimized prompt based on page analysis"""
        prompt = """**TASK**: Extract all content from this financial document EXACTLY in this JSON format:

{
    "content_blocks": [
        {
            "block_id": 1,
            "type": "text",
            "content": "Full paragraph text..."
        },
        {
            "block_id": 2,
            "type": "table",
            "title": "Table title if exists",
            "data": [
                {"Header1": "Value1", "Header2": "Value2"},
                {"Header1": "Value3", "Header2": "Value4"}
            ],
            "summary_table": "Concise summary in Indonesian/English"
        },
        {
            "block_id": 3,
            "type": "chart",
            "chart_type": "line/bar/pie/etc",
            "title": "Chart title",
            "data": {
                "labels": ["Q1", "Q2"],
                "datasets": [
                    {"label": "Series1", "values": [10, 20]},
                    {"label": "Series2", "values": [15, 25]}
                ]
            },
            "summary_chart": "Key insights from chart"
        },
        {
            "block_id": 4,
            "type": "flowchart",
            "title": "Flowchart title",
            "elements": [
                {"type": "node", "id": "1", "text": "Start", "connects_to": ["2"]}
            ],
            "summary_flowchart": "Process description"
        },
        {
            "block_id": 5,
            "type": "image",
            "description_image": "Detailed description"
        }
    ]
}

**RULES**:
1. PRESERVE all numerical data exactly
2. For financial tables: Keep precise percentages (e.g., 45.23%)
3. For charts: Extract ALL data points accurately
4. For flowcharts: Capture ALL decision points and connections
5. For images: Provide DETAILED descriptions including:
   - Figures/numbers visible
   - Any annotations
   - Overall purpose in document

**DOCUMENT TYPE**: Financial Report"""
        
        if analysis['line_status']:
            prompt += "\n\n**NOTE**: This page contains structured elements (tables/charts). Pay SPECIAL ATTENTION to:"
            prompt += "\n- Table borders and alignment"
            prompt += "\n- Chart data points and axis labels"
            prompt += "\n- Flowchart decision points"
        
        return prompt
    
    def _call_gemini_api(self, image: Image, prompt: str) -> str:
        """Calls Gemini API with enhanced configuration"""
        try:
            response = self.model.generate_content(
                contents=[prompt, image],
                generation_config={
                    "temperature": 0.2,  # More deterministic output
                    "max_output_tokens": 4000,
                    "top_p": 0.8
                },
                safety_settings={
                    "HARASSMENT": "block_none",
                    "HATE_SPEECH": "block_none",
                    "SEXUAL": "block_none",
                    "DANGEROUS": "block_none"
                }
            )
            return response.text
        except Exception as e:
            raise Exception(f"API Error: {str(e)}")
    
    def _parse_response(self, response_text: str, page_num: int) -> List[Dict]:
        """Enhanced response parsing with validation"""
        try:
            # Clean response text
            cleaned = response_text.strip()
            if cleaned.startswith('```json'):
                cleaned = cleaned[7:-3].strip()
            
            # Parse and validate
            data = json.loads(cleaned)
            blocks = data.get('content_blocks', [])
            
            # Add block IDs if missing
            for i, block in enumerate(blocks, 1):
                if 'block_id' not in block:
                    block['block_id'] = i
            
            return blocks
        except json.JSONDecodeError as je:
            print(f"JSON Parse Error on page {page_num}: {je}")
            return [{
                "block_id": 1,
                "type": "text",
                "content": f"Error parsing response: {str(je)}"
            }]
        except Exception as e:
            print(f"Unexpected Error on page {page_num}: {e}")
            return [{
                "block_id": 1,
                "type": "text",
                "content": f"Extraction error: {str(e)}"
            }]

# Example usage
if __name__ == "__main__":
    # Load page analysis
    with open('sample.json') as f:
        analysis_data = json.load(f)
    
    # Initialize extractor
    extractor = MultimodalPDFExtractor()
    
    # Process PDF
    pdf_file = "ABF Indonesia Bond Index Fund.pdf"
    result = extractor.process_pdf(pdf_file, analysis_data)
    
    # Save results
    with open('hasil_ekstraksi.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print("Extraction complete. Results saved to hasil_ekstraksi.json")