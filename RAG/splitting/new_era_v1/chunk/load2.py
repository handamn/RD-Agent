import json
import os
import tiktoken  # For accurate token counting
import uuid

# Initialize tokenizer
tokenizer = tiktoken.get_encoding("cl100k_base")  # Using OpenAI's tokenizer as example

def count_tokens(text):
    """Count the number of tokens in a string."""
    return len(tokenizer.encode(text))

def create_chunks(json_data, max_tokens=1000, overlap_tokens=100):
    """
    Create optimized chunks from the extracted PDF JSON data.
    
    Args:
        json_data: The JSON data from the PDF extraction
        max_tokens: Maximum tokens per chunk
        overlap_tokens: Number of tokens to overlap between chunks
    
    Returns:
        List of chunks with content and metadata
    """
    chunks = []
    document_metadata = {
        "filename": json_data.get("metadata", {}).get("filename", "unknown"),
        "total_pages": json_data.get("metadata", {}).get("total_pages", 0),
    }
    
    # Process each page
    for page_num_str, page_data in sorted(json_data.get("pages", {}).items(), key=lambda x: int(x[0])):
        page_num = int(page_num_str)
        
        # Skip if no content blocks
        if "extraction" not in page_data or "content_blocks" not in page_data["extraction"]:
            continue
            
        content_blocks = page_data["extraction"]["content_blocks"]
        
        i = 0
        while i < len(content_blocks):
            block = content_blocks[i]
            
            # Handle non-text elements (images, tables, flowcharts) as individual chunks
            if block["type"] in ["image", "table", "flowchart"]:
                # Get text context before the element (up to 200 tokens)
                context_before = ""
                if i > 0 and content_blocks[i-1]["type"] == "text":
                    context_text = content_blocks[i-1]["content"]
                    context_tokens = count_tokens(context_text)
                    if context_tokens > 200:
                        # Get approximately last 200 tokens
                        words = context_text.split()
                        estimated_word_count = int(200 / (context_tokens / len(words)))
                        context_before = " ".join(words[-estimated_word_count:])
                    else:
                        context_before = context_text
                
                # Get text context after the element (up to 200 tokens)
                context_after = ""
                if i < len(content_blocks)-1 and content_blocks[i+1]["type"] == "text":
                    context_text = content_blocks[i+1]["content"]
                    context_tokens = count_tokens(context_text)
                    if context_tokens > 200:
                        # Get approximately first 200 tokens
                        words = context_text.split()
                        estimated_word_count = int(200 / (context_tokens / len(words)))
                        context_after = " ".join(words[:estimated_word_count])
                    else:
                        context_after = context_text
                
                # Prepare content for the chunk
                chunk_content = ""
                
                # Add context before if available
                if context_before:
                    chunk_content += context_before + "\n\n"
                
                # Add title/description
                if block.get("title"):
                    chunk_content += f"Title: {block['title']}\n\n"
                elif block.get("description_image"):
                    chunk_content += f"Description: {block['description_image']}\n\n"
                
                # Add the main content based on type
                if block["type"] == "table":
                    if "data" in block:
                        # Format table data as text
                        chunk_content += "Table Content:\n"
                        # Handle table with column names
                        if isinstance(block["data"], list) and len(block["data"]) > 0 and isinstance(block["data"][0], dict):
                            # Get all column names
                            columns = set()
                            for row in block["data"]:
                                columns.update(row.keys())
                            columns = sorted(list(columns))
                            
                            # Add column header
                            chunk_content += " | ".join(columns) + "\n"
                            chunk_content += "-" * (sum(len(col) for col in columns) + 3 * (len(columns) - 1)) + "\n"
                            
                            # Add rows
                            for row in block["data"]:
                                row_data = []
                                for col in columns:
                                    row_data.append(str(row.get(col, "")))
                                chunk_content += " | ".join(row_data) + "\n"
                    
                    # Add table summary if available
                    if block.get("summary_table"):
                        chunk_content += f"\nTable Summary: {block['summary_table']}\n"
                
                elif block["type"] == "flowchart":
                    chunk_content += "Flowchart Elements:\n"
                    
                    if "elements" in block:
                        for element in block["elements"]:
                            chunk_content += f"- {element.get('type', 'Element')}: {element.get('text', '')}\n"
                            
                            # Add connection information
                            if "connects_to" in element:
                                if isinstance(element["connects_to"], list):
                                    if all(isinstance(item, str) for item in element["connects_to"]):
                                        chunk_content += f"  Connects to: {', '.join(element['connects_to'])}\n"
                                    else:
                                        for conn in element["connects_to"]:
                                            if isinstance(conn, dict):
                                                chunk_content += f"  Connects to: {conn.get('target', '')} ({conn.get('label', '')})\n"
                    
                    # Add flowchart summary if available
                    if block.get("summary_flowchart"):
                        chunk_content += f"\nFlowchart Summary: {block['summary_flowchart']}\n"
                
                # Add context after if available
                if context_after:
                    chunk_content += f"\n\n{context_after}"
                
                # Create chunk with metadata
                chunk_id = f"chunk_{uuid.uuid4().hex[:8]}"
                chunks.append({
                    "chunk_id": chunk_id,
                    "content": chunk_content,
                    "metadata": {
                        "document": document_metadata["filename"],
                        "page": page_num,
                        "type": block["type"],
                        "block_id": block.get("block_id"),
                        "page_location": f"Page {page_num}"
                    }
                })
                
                i += 1  # Move to next block
            
            # Handle text blocks with chunking
            elif block["type"] == "text":                
                # Start a new text chunk
                current_chunk_text = block["content"]
                current_chunk_blocks = [i]
                current_token_count = count_tokens(current_chunk_text)
                
                # Try to add more text blocks to reach max_tokens
                j = i + 1
                while j < len(content_blocks):
                    next_block = content_blocks[j]
                    
                    # Only combine with subsequent text blocks
                    if next_block["type"] != "text":
                        break
                    
                    next_text = next_block["content"]
                    next_token_count = count_tokens(next_text)
                    
                    # Check if adding would exceed the limit
                    if current_token_count + next_token_count > max_tokens:
                        break
                    
                    # Add to current chunk
                    current_chunk_text += "\n" + next_text
                    current_chunk_blocks.append(j)
                    current_token_count += next_token_count
                    j += 1
                
                # Create chunk with the text content
                chunk_id = f"chunk_{uuid.uuid4().hex[:8]}"
                chunks.append({
                    "chunk_id": chunk_id,
                    "content": current_chunk_text,
                    "metadata": {
                        "document": document_metadata["filename"],
                        "page": page_num,
                        "type": "text",
                        "block_ids": [content_blocks[idx].get("block_id") for idx in current_chunk_blocks],
                        "page_location": f"Page {page_num}"
                    }
                })
                
                # Create overlap chunk if needed
                if j < len(content_blocks) and content_blocks[j]["type"] == "text":
                    # Calculate the text to use for overlap
                    words = current_chunk_text.split()
                    overlap_word_count = min(
                        len(words),
                        int(overlap_tokens / (current_token_count / len(words)))
                    )
                    
                    # Only create overlap if we have enough words
                    if overlap_word_count > 0:
                        overlap_text = " ".join(words[-overlap_word_count:])
                        
                        # The next chunk will start with the overlap text
                        # We don't need to explicitly create it here
                        # It will be handled in the next iteration
                        
                        # Move to the position after the last fully processed block
                        i = current_chunk_blocks[-1] + 1
                    else:
                        # No overlap needed, move to the next unprocessed block
                        i = j
                else:
                    # No overlap needed, move to the next unprocessed block
                    i = j
            
            else:
                # Skip unrecognized block types
                i += 1
    
    return chunks

def process_pdf_json(input_path, output_path, max_tokens=1000, overlap_tokens=100):
    """
    Process PDF JSON file and create chunked JSON output
    
    Args:
        input_path: Path to input JSON file
        output_path: Path to output chunked JSON file
        max_tokens: Maximum tokens per chunk
        overlap_tokens: Number of tokens for overlap
    """
    # Load JSON data
    with open(input_path, 'r', encoding='utf-8') as f:
        pdf_data = json.load(f)
    
    # Create chunks
    chunks = create_chunks(pdf_data, max_tokens, overlap_tokens)
    
    # Create output structure
    output_data = {
        "document_metadata": {
            "filename": pdf_data.get("metadata", {}).get("filename", "unknown"),
            "total_pages": pdf_data.get("metadata", {}).get("total_pages", 0),
            "extraction_date": pdf_data.get("metadata", {}).get("extraction_date", ""),
            "chunk_count": len(chunks)
        },
        "chunks": chunks
    }
    
    # Save output
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"Processed {len(chunks)} chunks from {input_path}")
    print(f"Output saved to {output_path}")

def process_directory(input_dir, output_dir, max_tokens=1000, overlap_tokens=100):
    """
    Process all JSON files in a directory
    
    Args:
        input_dir: Directory containing extracted PDF JSON files
        output_dir: Directory to save chunked output
        max_tokens: Maximum tokens per chunk
        overlap_tokens: Number of tokens for overlap
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Process each JSON file
    for filename in os.listdir(input_dir):
        if filename.endswith('.json'):
            input_path = os.path.join(input_dir, filename)
            output_filename = f"chunked_{filename}"
            output_path = os.path.join(output_dir, output_filename)
            
            process_pdf_json(input_path, output_path, max_tokens, overlap_tokens)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Process PDF extraction JSON into optimal chunks for RAG")
    parser.add_argument("--input", required=True, help="Input JSON file or directory")
    parser.add_argument("--output", required=True, help="Output JSON file or directory")
    parser.add_argument("--max-tokens", type=int, default=1000, help="Maximum tokens per chunk")
    parser.add_argument("--overlap", type=int, default=100, help="Token overlap between chunks")
    
    args = parser.parse_args()
    
    if os.path.isdir(args.input):
        process_directory(args.input, args.output, args.max_tokens, args.overlap)
    else:
        process_pdf_json(args.input, args.output, args.max_tokens, args.overlap)