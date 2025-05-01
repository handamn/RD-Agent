import json

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def extract_blocks(data):
    results = []
    for page_num, page_data in data.get("pages", {}).items():
        content_blocks = page_data.get("extraction", {}).get("content_blocks", [])
        for block in content_blocks:
            entry = {
                "page": int(page_num),
                "block_id": block.get("block_id"),
                "type": block.get("type"),
            }

            if block["type"] == "text":
                entry["text"] = block.get("content", "")
            elif block["type"] == "image":
                entry["description"] = block.get("description_image", "")
            elif block["type"] == "table":
                entry["title"] = block.get("title", "")
                entry["summary"] = block.get("summary_table", "")
                entry["data"] = block.get("data", [])
            elif block["type"] == "flowchart":
                entry["title"] = block.get("title", "")
                entry["summary"] = block.get("summary_flowchart", "")
                entry["elements"] = block.get("elements", [])
            else:
                entry["raw"] = block

            results.append(entry)
    return results

if __name__ == "__main__":
    data = load_json("misterius.json")
    extracted_blocks = extract_blocks(data)

    # Contoh preview
    for item in extracted_blocks[:5]:
        print(json.dumps(item, indent=2, ensure_ascii=False))
