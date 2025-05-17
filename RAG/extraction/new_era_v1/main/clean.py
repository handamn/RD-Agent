import os

# Ganti dengan path ke folder kamu
folder_path = 'database/classified_result'

# Loop melalui semua file dalam folder
for filename in os.listdir(folder_path):
    if filename.endswith('_analyzed.json'):
        # Buat nama file baru
        new_filename = filename.replace('_analyzed.json', '_classified.json')

        # Path lengkap ke file lama dan baru
        old_file = os.path.join(folder_path, filename)
        new_file = os.path.join(folder_path, new_filename)

        # Rename file
        os.rename(old_file, new_file)
        print(f'Renamed: {filename} → {new_filename}')
