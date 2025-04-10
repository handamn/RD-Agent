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
# for page in data.get("pages", []):
#     if page.get("page_num") == 1:
#         for line in page.get("valid_lines", []):
#             y_positions.append(line.get("y_position"))

# print("Semua y_position dari page_num 1:")
# print(y_positions)


text = []
# a = 1
# for page in data.get("pages", []):
#     if page.get("page_num") == 40 :
        # index = 1
        # for split in page.get("table_data"):
            # key_split = "split_" + str(split)
            # print(split)
            # index +=1
        # bacot = "split_"+str(1)
        # print((page.get("table_data"))[bacot])
        # # print(a)
        # a+=1


text = []
table = []
a = 1
for page in data.get("pages", []):
    # if page.get("text") != None :
    #     text.append(page.get("text"))
    
    if page.get("table_data") != None:
        # a = 0
        for split in page.get("table_data",[]):
            for type
            # print(split)
            # print(a)
            # print()

            # a+=1
            # if split.get("type") != None:
            #     print(split.get("type"))

    #     print(page.get("table_data"))

    #     print(a)
    # a+=1


# for a in text :
#     print(type(a))
#     print()
# # print(len(text))