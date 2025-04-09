# import json

# # Ganti dengan path ke file JSON kamu
# file_path = 'ABF Indonesia Bond Index Fund.json'

# # Membaca file JSON dan ambil hanya "filename"
# with open(file_path, 'r', encoding='utf-8') as f:
#     data = json.load(f)
#     filename = data.get("metadata", {}).get("filename")

# print("Filename:", filename)


import json

# Ganti dengan path file JSON kamu
file_path = 'ABF Indonesia Bond Index Fund.json'

# Membaca file JSON
with open(file_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Ambil nilai y_position dari valid_lines pada page_num 1
y_positions = []
for page in data.get("pages", []):
    if page.get("page_num") == 1:
        for line in page.get("valid_lines", []):
            y_positions.append(line.get("y_position"))

print("Semua y_position dari page_num 1:")
print(y_positions)
