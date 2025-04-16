from pdf_only import process_pdf_pages
from ocr_only import process_pdf_pages
from multimodal_only import process_pdf_pages

pdf_path = "ABF Indonesia Bond Index Fund.pdf"  # Replace with your PDF path
analysis_json_path = "sample.json"  # Path to analysis JSON
output_json_path = "hasil_ekstraksi.json"  # Path to save extraction results
temp_dir = "temporary_dir"  # Directory for temporary images