from datetime import date, timedelta
import pandas as pd

from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from multiprocessing import Process, Manager
import csv
import os
from datetime import datetime


#################################################################################

today = date.today()
today_request = date(2025, 4, 10)

urls = [
    ['Batavia Technology Sharia Equity USD','https://bibit.id/reksadana/RD4183'],
]


pixel = 20

# Read csv

for kode, url in urls:
    csv_file_recent = f"database/{kode}.csv"
    df = pd.read_csv(csv_file_recent)
    latest_data = df.iloc[-1].tolist()

    latest_data_date = latest_data[0]
    latest_data_value = latest_data[-1]

    LD_years, LD_months, LD_dates = latest_data_date.split("-")
    date_database = date(int(LD_years), int(LD_months), int(LD_dates))

    delta_date = today_request - date_database

    if delta_date < timedelta(0):
            print("tidak proses")
    else:
        # Daftar periode berdasarkan hari
        period_map = [
            (30, ['1M']),
            (90, ['1M', '3M']),
            (365, ['1M', '3M', 'YTD']),
            (1095, ['1M', '3M', 'YTD', '3Y']),
            (1825, ['1M', '3M', 'YTD', '3Y', '5Y']),
        ]

        # Default jika lebih dari 5 tahun
        data_periods = ['ALL', '1M', '3M', 'YTD', '3Y', '5Y']

        # Loop untuk mencari rentang yang sesuai
        for days, periods in period_map:
            if delta_date <= timedelta(days=days):
                data_periods = periods
                break  # Stop loop setelah menemukan rentang yang sesuai

print(data_periods)




# #################################################################################
# from scrap_function import print_header, scrape_data, print_subheader, parse_tanggal, convert_to_number

# if __name__ == "__main__":
#     start_time = time.time()

#     ######### PERBEDAAN #########
#     # Package tanggal setting
#     today = date.today()
#     today_a = date(2025, 2, 15) 
#     #############################

#     # List URL yang akan di-scrap
#     urls = [
#         ['ABF Indonesia Bond Index Fund', 'https://bibit.id/reksadana/RD13'],
#     ]


#     pixel = 2
#     # data_periods = ['ALL', '1M', '3M', 'YTD', '3Y', '5Y']

#     for url_data in urls:
#         kode = url_data[0]
#         url = url_data[1]


#         #############################
#         ######### PERBEDAAN #########
#         # csv name
#         csv_file = f"database/{kode}.csv"

#         # csv process
#         df = pd.read_csv(csv_file)
#         latest_data = df.iloc[-1].tolist()

#         latest_data_date = latest_data[0]
#         latest_data_value = latest_data[-1]


#         LD_years, LD_months, LD_dates = latest_data_date.split("-")
#         date_database = date(int(LD_years), int(LD_months), int(LD_dates))

#         # operasi penentuan periode
#         pengurangan = today_a - date_database

#         # Jika pengurangan negatif, langsung cetak dan hentikan proses
#         if pengurangan < timedelta(0):
#             print("tidak proses")
#         else:
#             # Daftar periode berdasarkan hari
#             period_map = [
#                 (30, ['1M']),
#                 (90, ['1M', '3M']),
#                 (365, ['1M', '3M', 'YTD']),
#                 (1095, ['1M', '3M', 'YTD', '3Y']),
#                 (1825, ['1M', '3M', 'YTD', '3Y', '5Y']),
#             ]

#             # Default jika lebih dari 5 tahun
#             data_periods = ['ALL', '1M', '3M', 'YTD', '3Y', '5Y']

#             # Loop untuk mencari rentang yang sesuai
#             for days, periods in period_map:
#                 if pengurangan <= timedelta(days=days):
#                     data_periods = periods
#                     break  # Stop loop setelah menemukan rentang yang sesuai
#         #############################
#         #############################
        

#         print_header(f"Memulai Scraping Data: {kode}")
#         print(f"URL: {url}")

#         processes = []
#         manager = Manager()
#         result_list = manager.list()

#         for period in data_periods:
#             p = Process(target=scrape_data, args=(url, period, result_list, pixel))
#             processes.append(p)
#             p.start()

#         for p in processes:
#             p.join()

#         print_subheader("Memproses hasil scraping")
        
#         combined_data = []
#         for period_data in result_list:
#             combined_data.extend(period_data)

#         unique_data = []
#         seen = set()
#         for entry in combined_data:
#             key = (entry['tanggal'], entry['data'])
#             if key not in seen:
#                 seen.add(key)
#                 unique_data.append(entry)

#         sorted_data = sorted(unique_data, key=lambda x: parse_tanggal(x['tanggal']))

#         formatted_data = []
#         for entry in sorted_data:
#             tanggal_obj = parse_tanggal(entry['tanggal'])
#             tanggal_str = tanggal_obj.strftime("%Y-%m-%d")
#             data_str = entry['data'].replace('Rp', '').strip()
            
#             try:
#                 data_number = convert_to_number(data_str)
#                 formatted_data.append({
#                     'tanggal': tanggal_str,
#                     'data': data_number
#                 })
#             except ValueError as e:
#                 print(f"[ERROR] Gagal mengonversi data: {data_str}")

#         print("\nHasil akhir (Tanpa Duplikat, Diurutkan dari Tanggal Terlama):")
#         for entry in formatted_data[:5]:  # Hanya tampilkan 5 data pertama
#             print(f"Tanggal: {entry['tanggal']}, Data: {entry['data']}")
#         print("...")  # Menandakan masih ada data lainnya

        
#         file_exists = os.path.exists(csv_file)

#         # Jika file belum ada, buat baru dengan header dan semua data
#         if not file_exists:
#             with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
#                 writer = csv.DictWriter(file, fieldnames=['tanggal', 'data'])
#                 writer.writeheader()
#                 for entry in formatted_data:
#                     writer.writerow(entry)
#             print(f"\n[INFO] File baru dibuat: {csv_file}")
#             print(f"[INFO] {len(formatted_data)} data berhasil disimpan")
#         else:
#             # Baca data existing dari CSV
#             existing_data = []
#             with open(csv_file, mode='r', encoding='utf-8') as file:
#                 reader = csv.DictReader(file)
#                 for row in reader:
#                     existing_data.append({
#                         'tanggal': row['tanggal'],
#                         'data': float(row['data'])  # Konversi ke float untuk konsistensi
#                     })

#             # Identifikasi data baru yang unik
#             new_unique_data = []
#             duplicate_count = 0
            
#             for new_entry in formatted_data:
#                 is_duplicate = False
#                 for existing_entry in existing_data:
#                     if (new_entry['tanggal'] == existing_entry['tanggal'] and 
#                         float(new_entry['data']) == float(existing_entry['data'])):
#                         duplicate_count += 1
#                         is_duplicate = True
#                         break
#                 if not is_duplicate:
#                     new_unique_data.append(new_entry)

#             # Append data unik ke CSV
#             if new_unique_data:
#                 with open(csv_file, mode='a', newline='', encoding='utf-8') as file:
#                     writer = csv.DictWriter(file, fieldnames=['tanggal', 'data'])
#                     for entry in new_unique_data:
#                         writer.writerow(entry)
#                 print(f"\n[INFO] {len(new_unique_data)} data baru ditambahkan ke {csv_file}")

#                 print(f"\n[INFO] Data telah disimpan ke {csv_file}")

#     end_time = time.time()
#     durasi = end_time - start_time
    
#     print_header("Ringkasan Eksekusi")
#     print(f"Total waktu eksekusi: {durasi:.2f} detik")
