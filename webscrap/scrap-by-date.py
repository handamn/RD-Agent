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




# def print_header(text, char="="):
#     """Print a header with consistent formatting"""
#     line = char * 80
#     print(f"\n{line}")
#     print(f"{text.center(80)}")
#     print(f"{line}\n")

# def print_subheader(text, char="-"):
#     """Print a subheader with consistent formatting"""
#     print(f"\n{char * 40} {text} {char * 40}\n")

# def print_progress(period, iteration, date, value):
#     """Print progress with consistent formatting"""
#     print(f"Period: {period:<4} | Iteration: {iteration:<4} | Date: {date:<10} | Value: {value}")

# def convert_to_number(value):
#     # Existing convert_to_number function remains the same
#     if 'K' in value:
#         return float(value.replace('K', '')) * 1000
#     elif 'M' in value:
#         return float(value.replace('M', '')) * 1000000
#     else:
#         return float(value.replace(',', ''))

# def parse_tanggal(tanggal_str):
#     # Existing parse_tanggal function remains the same
#     bulan_map_id = {
#         'Jan': 'Januari',
#         'Feb': 'Februari',
#         'Mar': 'Maret',
#         'Apr': 'April',
#         'Mei': 'Mei',
#         'Jun': 'Juni',
#         'Jul': 'Juli',
#         'Agt': 'Agustus',
#         'Sep': 'September',
#         'Okt': 'Oktober',
#         'Nov': 'November',
#         'Des': 'Desember'
#     }

#     bulan_map_en = {
#         'Januari': 'January',
#         'Februari': 'February',
#         'Maret': 'March',
#         'April': 'April',
#         'Mei': 'May',
#         'Juni': 'June',
#         'Juli': 'July',
#         'Agustus': 'August',
#         'September': 'September',
#         'Oktober': 'October',
#         'November': 'November',
#         'Desember': 'December'
#     }

#     parts = tanggal_str.split()
#     if len(parts) != 3:
#         raise ValueError(f"Format tanggal tidak valid: {tanggal_str}")

#     hari = parts[0]
#     bulan_singkat = parts[1]
#     tahun = parts[2]

#     if bulan_singkat not in bulan_map_id:
#         raise ValueError(f"Bulan tidak valid: {bulan_singkat}")
#     bulan_id = bulan_map_id[bulan_singkat]

#     if bulan_id not in bulan_map_en:
#         raise ValueError(f"Bulan tidak valid: {bulan_id}")
#     bulan_en = bulan_map_en[bulan_id]

#     tanggal_full = f"{hari} {bulan_en} 20{tahun}"
#     return datetime.strptime(tanggal_full, "%d %B %Y")

# def scrape_data(url, period, result_list, pixel):
#     options = webdriver.ChromeOptions()
#     options.add_argument('--disable-gpu')
#     options.add_argument('--disable-dev-shm-usage')
#     options.add_argument('--no-sandbox')
#     options.add_argument('--headless')
#     service = webdriver.chrome.service.Service()
#     driver = webdriver.Chrome(service=service, options=options)

#     driver.get(url)

#     try:
#         button = WebDriverWait(driver, 10).until(
#             EC.element_to_be_clickable((By.CSS_SELECTOR, f'button[data-period="{period}"]'))
#         )

#         button_text = button.find_element(By.CSS_SELECTOR, '.reksa-border-button-period-box').text
#         print(f"[INFO] Memulai scraping untuk periode: {button_text}")
        
#         button.click()
#         time.sleep(2)

#         graph_element = driver.find_element(By.TAG_NAME, 'svg')
#         graph_width = int(graph_element.size['width'])
#         start_offset = -graph_width // 2

#         actions = ActionChains(driver)
#         period_data = []

#         print_subheader(f"Mengambil data periode {period}")

#         for offset in range(start_offset, start_offset + graph_width, pixel):
#             current_iteration = (offset - start_offset) // pixel + 1
            
#             actions.move_to_element_with_offset(graph_element, offset, 0).perform()
#             time.sleep(0.1)

#             updated_data = WebDriverWait(driver, 10).until(
#                 EC.presence_of_element_located((By.CSS_SELECTOR, '.reksa-value-head-nav.ChartHead_reksa-value-head-nav__LCCdL'))
#             ).text

#             tanggal_navdate = WebDriverWait(driver, 10).until(
#                 EC.presence_of_element_located((By.CSS_SELECTOR, '.navDate'))
#             ).text

#             print_progress(period, current_iteration, tanggal_navdate, updated_data)
            
#             period_data.append({
#                 'tanggal': tanggal_navdate,
#                 'data': updated_data
#             })

#         result_list.append(period_data)

#     except Exception as e:
#         print(f"[ERROR] Gagal mengambil data untuk periode {period}: {str(e)}")
#     finally:
#         driver.quit()

from scrap_function import print_header, scrape_data, print_subheader, parse_tanggal, convert_to_number

if __name__ == "__main__":
    start_time = time.time()

    ######### PERBEDAAN #########
    # Package tanggal setting
    today = date.today()
    today_a = date(2025, 2, 15) 
    #############################

    # List URL yang akan di-scrap
    urls = [
        ['ABF Indonesia Bond Index Fund', 'https://bibit.id/reksadana/RD13'],
    ]


    pixel = 2
    # data_periods = ['ALL', '1M', '3M', 'YTD', '3Y', '5Y']

    for url_data in urls:
        kode = url_data[0]
        url = url_data[1]


        #############################
        ######### PERBEDAAN #########
        # csv name
        csv_file = f"database/{kode}.csv"

        # csv process
        df = pd.read_csv(csv_file)
        latest_data = df.iloc[-1].tolist()

        latest_data_date = latest_data[0]
        latest_data_value = latest_data[-1]


        LD_years, LD_months, LD_dates = latest_data_date.split("-")
        date_database = date(int(LD_years), int(LD_months), int(LD_dates))

        # operasi penentuan periode
        pengurangan = today_a - date_database

        # Jika pengurangan negatif, langsung cetak dan hentikan proses
        if pengurangan < timedelta(0):
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
                if pengurangan <= timedelta(days=days):
                    data_periods = periods
                    break  # Stop loop setelah menemukan rentang yang sesuai
        #############################
        #############################
        

        print_header(f"Memulai Scraping Data: {kode}")
        print(f"URL: {url}")

        processes = []
        manager = Manager()
        result_list = manager.list()

        for period in data_periods:
            p = Process(target=scrape_data, args=(url, period, result_list, pixel))
            processes.append(p)
            p.start()

        for p in processes:
            p.join()

        print_subheader("Memproses hasil scraping")
        
        combined_data = []
        for period_data in result_list:
            combined_data.extend(period_data)

        unique_data = []
        seen = set()
        for entry in combined_data:
            key = (entry['tanggal'], entry['data'])
            if key not in seen:
                seen.add(key)
                unique_data.append(entry)

        sorted_data = sorted(unique_data, key=lambda x: parse_tanggal(x['tanggal']))

        formatted_data = []
        for entry in sorted_data:
            tanggal_obj = parse_tanggal(entry['tanggal'])
            tanggal_str = tanggal_obj.strftime("%Y-%m-%d")
            data_str = entry['data'].replace('Rp', '').strip()
            
            try:
                data_number = convert_to_number(data_str)
                formatted_data.append({
                    'tanggal': tanggal_str,
                    'data': data_number
                })
            except ValueError as e:
                print(f"[ERROR] Gagal mengonversi data: {data_str}")

        print("\nHasil akhir (Tanpa Duplikat, Diurutkan dari Tanggal Terlama):")
        for entry in formatted_data[:5]:  # Hanya tampilkan 5 data pertama
            print(f"Tanggal: {entry['tanggal']}, Data: {entry['data']}")
        print("...")  # Menandakan masih ada data lainnya

        
        file_exists = os.path.exists(csv_file)

        # Jika file belum ada, buat baru dengan header dan semua data
        if not file_exists:
            with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=['tanggal', 'data'])
                writer.writeheader()
                for entry in formatted_data:
                    writer.writerow(entry)
            print(f"\n[INFO] File baru dibuat: {csv_file}")
            print(f"[INFO] {len(formatted_data)} data berhasil disimpan")
        else:
            # Baca data existing dari CSV
            existing_data = []
            with open(csv_file, mode='r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    existing_data.append({
                        'tanggal': row['tanggal'],
                        'data': float(row['data'])  # Konversi ke float untuk konsistensi
                    })

            # Identifikasi data baru yang unik
            new_unique_data = []
            duplicate_count = 0
            
            for new_entry in formatted_data:
                is_duplicate = False
                for existing_entry in existing_data:
                    if (new_entry['tanggal'] == existing_entry['tanggal'] and 
                        float(new_entry['data']) == float(existing_entry['data'])):
                        duplicate_count += 1
                        is_duplicate = True
                        break
                if not is_duplicate:
                    new_unique_data.append(new_entry)

            # Append data unik ke CSV
            if new_unique_data:
                with open(csv_file, mode='a', newline='', encoding='utf-8') as file:
                    writer = csv.DictWriter(file, fieldnames=['tanggal', 'data'])
                    for entry in new_unique_data:
                        writer.writerow(entry)
                print(f"\n[INFO] {len(new_unique_data)} data baru ditambahkan ke {csv_file}")

                print(f"\n[INFO] Data telah disimpan ke {csv_file}")

    end_time = time.time()
    durasi = end_time - start_time
    
    print_header("Ringkasan Eksekusi")
    print(f"Total waktu eksekusi: {durasi:.2f} detik")
