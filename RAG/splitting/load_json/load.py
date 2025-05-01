import json
import os
import uuid
from typing import Dict, List, Any, Optional, Union, Tuple

class PDFJsonProcessor:
    def __init__(self, json_file_path: str):
        """
        Initialize the processor with path to the JSON file
        
        Args:
            json_file_path: Path to the JSON file containing PDF extraction data
        """
        self.json_file_path = json_file_path
        self.data = None
        self.processed_chunks = []
        self.metadata = {}
    
    def load_data(self) -> None:
        """Load the JSON data from file"""
        try:
            with open(self.json_file_path, 'r', encoding='utf-8') as file:
                self.data = json.load(file)
                
            # Extract document metadata
            if 'metadata' in self.data:
                self.metadata = self.data['metadata']
                print(f"Loaded document with {self.metadata.get('total_pages', 'unknown')} pages")
        except Exception as e:
            print(f"Error loading JSON file: {e}")
            raise
    
    def _create_unique_id(self, page_num: str, block_id: int) -> str:
        """Create a unique ID for each content block"""
        return f"page_{page_num}_block_{block_id}"
    
    def _extract_text_from_block(self, block: Dict[str, Any]) -> str:
        """Extract text content from a block based on its type"""
        if not isinstance(block, dict):
            return ""
            
        block_type = block.get('type')
        
        if block_type == 'text':
            content = block.get('content')
            return content if content is not None else ""
        elif block_type == 'image':
            description = block.get('description_image')
            return description if description is not None else ""
        elif block_type == 'table':
            # Convert table data to text representation
            text = block.get('title', '') or ''
            if text:
                text += "\n"
            
            table_data = block.get('data', [])
            
            if table_data and isinstance(table_data, list):
                # Get column names from the first row
                if table_data:
                    columns = list(table_data[0].keys())
                    
                    # Add each row as text
                    for row in table_data:
                        row_text = " | ".join([f"{col}: {row.get(col, '')}" for col in columns])
                        text += row_text + "\n"
            
            # Add table summary if available
            if 'summary_table' in block:
                summary = block.get('summary_table')
                if summary is not None:
                    text += f"Summary: {summary}"
                
            return text
        elif block_type == 'flowchart':
            # Convert flowchart to text representation
            text = block.get('title', '') or ''
            if text:
                text += "\n"
                
            elements = block.get('elements', [])
            
            # Process each flowchart element
            for element in elements:
                if not isinstance(element, dict):
                    continue
                    
                element_type = element.get('type', 'node')
                element_id = element.get('id', '')
                element_content = element.get('text', '')
                
                element_text = f"{element_type} - {element_id}: {element_content}"
                
                # Add connection information
                connects_to = element.get('connects_to', [])
                if isinstance(connects_to, list):
                    if all(isinstance(c, str) for c in connects_to if c is not None):
                        if connects_to:
                            element_text += f" → Connects to: {', '.join([c for c in connects_to if c is not None])}"
                    else:
                        # Handle complex connections with labels
                        connections = []
                        for conn in connects_to:
                            if isinstance(conn, dict):
                                target = conn.get('target', '')
                                label = conn.get('label', '')
                                if target:
                                    connections.append(f"{target} ({label})" if label else target)
                        if connections:
                            element_text += f" → Connects to: {', '.join(connections)}"
                
                text += element_text + "\n"
                
            # Add flowchart summary if available
            if 'summary_flowchart' in block:
                summary = block.get('summary_flowchart')
                if summary is not None:
                    text += f"Summary: {summary}"
                
            return text
        else:
            return ""
    
    def process_content(self, chunk_size: int = 1000, chunk_overlap: int = 100) -> None:
        """
        Process the PDF JSON content into chunks suitable for vector database
        
        Args:
            chunk_size: Target size of text chunks in characters
            chunk_overlap: Overlap between consecutive chunks in characters
        """
        if not self.data or 'pages' not in self.data:
            raise ValueError("JSON data not loaded or invalid format")
        
        self.processed_chunks = []
        
        # Process each page
        for page_num, page_data in self.data['pages'].items():
            if not isinstance(page_data, dict):
                print(f"Warning: Page {page_num} data is not a dictionary. Skipping.")
                continue
                
            extraction_data = page_data.get('extraction', {})
            if not isinstance(extraction_data, dict):
                print(f"Warning: Page {page_num} extraction data is not a dictionary. Skipping.")
                continue
                
            content_blocks = extraction_data.get('content_blocks', [])
            if not isinstance(content_blocks, list):
                print(f"Warning: Page {page_num} content_blocks is not a list. Skipping.")
                continue
            
            # Process each content block on the page
            for block in content_blocks:
                if not isinstance(block, dict):
                    print(f"Warning: Found a content block that is not a dictionary on page {page_num}. Skipping.")
                    continue
                    
                block_id = block.get('block_id')
                block_type = block.get('type')
                
                # Create a unique ID for this block
                unique_id = self._create_unique_id(page_num, block_id)
                
                try:
                    # Extract text based on block type
                    text_content = self._extract_text_from_block(block)
                    
                    # Skip empty content
                    if not text_content or not text_content.strip():
                        continue
                    
                    # Create block metadata
                    block_metadata = {
                        'id': unique_id,
                        'page': page_num,
                        'block_id': block_id,
                        'block_type': block_type,
                        'extraction_method': extraction_data.get('method'),
                        'document_filename': self.metadata.get('filename'),
                        'document_total_pages': self.metadata.get('total_pages')
                    }
                except Exception as e:
                    print(f"Error processing block {block_id} on page {page_num}: {e}")
                    continue
                
                # For longer text blocks, create chunks with overlap
                if len(text_content) > chunk_size and block_type == 'text':
                    chunks = self._create_overlapping_chunks(text_content, chunk_size, chunk_overlap)
                    
                    # Create a chunk object for each text chunk
                    for i, chunk in enumerate(chunks):
                        chunk_metadata = block_metadata.copy()
                        chunk_metadata['chunk_index'] = i
                        chunk_metadata['id'] = f"{unique_id}_chunk_{i}"
                        
                        self.processed_chunks.append({
                            'id': chunk_metadata['id'],
                            'text': chunk,
                            'metadata': chunk_metadata
                        })
                else:
                    # Store the content as a single chunk
                    self.processed_chunks.append({
                        'id': unique_id,
                        'text': text_content,
                        'metadata': block_metadata
                    })
        
        print(f"Processed {len(self.processed_chunks)} chunks from {len(self.data['pages'])} pages")
    
    def _create_overlapping_chunks(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """Create overlapping chunks from a long text"""
        chunks = []
        start = 0
        
        while start < len(text):
            # Get chunk of desired size
            end = start + chunk_size
            
            # If this is not the last chunk, try to break at a sentence or word boundary
            if end < len(text):
                # Try to find a sentence break
                sentence_break = text.rfind('. ', start, end) + 1
                if sentence_break > start + chunk_size // 2:
                    end = sentence_break
                else:
                    # Try to find a word break
                    word_break = text.rfind(' ', start, end) + 1
                    if word_break > start:
                        end = word_break
            
            # Add the chunk
            chunks.append(text[start:end].strip())
            
            # Move the window, accounting for overlap
            start = end - overlap
            
            # Avoid getting stuck in an infinite loop if overlap >= chunk_size
            if start <= 0 or overlap >= chunk_size:
                start = end
        
        return chunks
    
    def get_processed_data(self) -> List[Dict[str, Any]]:
        """Return the processed data ready for vector database"""
        return self.processed_chunks
    
    def save_processed_data(self, output_path: str) -> None:
        """Save the processed data to a JSON file"""
        try:
            with open(output_path, 'w', encoding='utf-8') as file:
                json.dump(self.processed_chunks, file, ensure_ascii=False, indent=2)
            print(f"Saved processed data to {output_path}")
        except Exception as e:
            print(f"Error saving processed data: {e}")
            raise


# Example usage
if __name__ == "__main__":
    # File paths
    input_json = "real.json"  # Path to your JSON file
    output_json = "processed_for_qdrant.json"  # Output file path
    
    # Initialize and run the processor
    processor = PDFJsonProcessor(input_json)
    processor.load_data()
    
    # Process with custom chunk parameters
    processor.process_content(chunk_size=800, chunk_overlap=100)
    
    # Save the processed data
    processor.save_processed_data(output_json)
    
    # Print some stats
    processed_data = processor.get_processed_data()
    print(f"Total chunks generated: {len(processed_data)}")
    
    # Preview some chunks
    if processed_data:
        print("\nPreview of first chunk:")
        first_chunk = processed_data[0]
        print(f"ID: {first_chunk['id']}")
        print(f"Metadata: {first_chunk['metadata']}")
        print(f"Text (first 100 chars): {first_chunk['text'][:100]}...")