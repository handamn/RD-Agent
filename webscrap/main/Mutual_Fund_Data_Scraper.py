from datetime import date, timedelta
import pandas as pd
import json
import os
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import csv


class Logger:
    """Logger untuk mencatat aktivitas scraping dan downloading ke file log yang sama."""
    def __init__(self, log_dir="logs"):
        os.makedirs(log_dir, exist_ok=True)
        log_filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_Mutual_Fund_Data_Scraper.log"
        self.LOG_FILE = os.path.join(log_dir, log_filename)

    def log_info(self, message, status="INFO"):
        """Menyimpan log ke file dengan format timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [{status}] {message}\n"

        with open(self.LOG_FILE, "a", encoding="utf-8") as log_file:
            log_file.write(log_message)

class Mutual_Fund_Data_Scraper:
    def __init__(self, urls, pixel, debug_mode=False):
        """Inisialisasi scraper dengan daftar URL, periode, pixel, dan logger eksternal."""
        self.urls = urls
        self.pixel = pixel
        self.logger = Logger()
        self.debug_mode = debug_mode
        self.database_dir = "database/mutual_fund"
        self.data_periods = self.determine_period()
        os.makedirs(self.database_dir, exist_ok=True)

    def determine_period(self):
        today = date.today()
        csv_file_recent = f"database/mutual_fund/{self.urls[0][0]}.csv"
        df = pd.read_csv(csv_file_recent)
        latest_data = df.iloc[-1].tolist()
        latest_data_date = latest_data[0]
        LD_years, LD_months, LD_dates = latest_data_date.split("-")
        date_database = date(int(LD_years), int(LD_months), int(LD_dates))
        delta_date = today - date_database

        period_map = [
            (30, ['1M']),
            (90, ['1M', '3M']),
            (365, ['1M', '3M', 'YTD']),
            (1095, ['1M', '3M', 'YTD', '3Y']),
            (1825, ['1M', '3M', 'YTD', '3Y', '5Y']),
            (3650, ['1M', '3M', 'YTD', '3Y', '5Y', '10Y'])
        ]

        data_periods = ['ALL', '1M', '3M', 'YTD', '3Y', '5Y', '10Y']
        for days, periods in period_map:
            if delta_date <= timedelta(days=days):
                data_periods = periods
                break

        return data_periods
    
    def convert_to_number(self, value):
        """Mengonversi string nilai dengan format K, M, B, T menjadi angka float dan mengembalikan jenis mata uang."""
        value = value.replace(',', '').strip()

        if value.startswith('Rp'):
            currency = 'IDR'
            value = value.replace('Rp', '').strip()
        elif value.startswith('$'):
            currency = 'USD'
            value = value.replace('$', '').strip()
        else:
            currency = 'UNKNOWN'  # Jika format tidak dikenali

        multiplier = 1
        if 'K' in value:
            value = value.replace('K', '')
            multiplier = 1_000
        elif 'M' in value:
            value = value.replace('M', '')
            multiplier = 1_000_000
        elif 'B' in value:
            value = value.replace('B', '')
            multiplier = 1_000_000_000
        elif 'T' in value:
            value = value.replace('T', '')
            multiplier = 1_000_000_000_000

        try:
            return float(value) * multiplier, currency
        except ValueError:
            raise ValueError(f"Format angka tidak valid: {value}")



    def parse_tanggal(self, tanggal_str):
        """Mengonversi tanggal dalam format Indonesia ke format datetime Python."""
        bulan_map = {
            'Jan': 'January', 'Feb': 'February', 'Mar': 'March',
            'Apr': 'April', 'Mei': 'May', 'Jun': 'June',
            'Jul': 'July', 'Agt': 'August', 'Sep': 'September',
            'Okt': 'October', 'Nov': 'November', 'Des': 'December'
        }

        parts = tanggal_str.split()
        if len(parts) != 3:
            raise ValueError(f"Format tanggal tidak valid: {tanggal_str}")

        hari, bulan_singkat, tahun = parts
        bulan_en = bulan_map.get(bulan_singkat, None)
        if not bulan_en:
            raise ValueError(f"Bulan tidak valid: {bulan_singkat}")

        return datetime.strptime(f"{hari} {bulan_en} 20{tahun}", "%d %B %Y")

    def switch_to_aum_mode(self, driver, wait):
        """Mengaktifkan mode AUM di situs sebelum scraping data."""
        try:
            aum_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'menu') and contains(text(), 'AUM')]"))
            )
            self.logger.log_info("Beralih ke mode AUM...")
            aum_button.click()
            time.sleep(3)  # Menunggu perubahan tampilan
            return True
        except Exception as e:
            self.logger.log_info(f"Gagal beralih ke mode AUM: {e}", "ERROR")
            return False

    def scrape_mode_data(self, url, period, mode):
        """Scrape data untuk mode dan periode tertentu."""
        start_time = time.time()
        period_data = []

        try:
            self.logger.log_info(f"Memulai scraping {period} ({mode}) untuk {url}...")

            options = webdriver.ChromeOptions()
            options.add_argument('--headless')
            driver = webdriver.Chrome(options=options)
            wait = WebDriverWait(driver, 10)

            driver.get(url)
            self.logger.log_info(f"Berhasil membuka URL {url}")

            # Beralih ke mode AUM jika mode yang dipilih adalah AUM
            if mode == "AUM":
                if not self.switch_to_aum_mode(driver, wait):
                    raise Exception("Gagal mengaktifkan mode AUM")

            # Ambil semua tombol periode yang tersedia di halaman
            available_buttons = driver.find_elements(By.CSS_SELECTOR, 'button[data-period]')
            available_periods = [btn.get_attribute("data-period") for btn in available_buttons]

            # Filter periode yang benar-benar tersedia
            valid_periods = [p for p in self.data_periods if p in available_periods]

            # Log jika ada periode yang tidak tersedia
            missing_periods = [p for p in self.data_periods if p not in available_periods]
            if missing_periods:
                self.logger.log_info(f"Periode berikut tidak ditemukan di halaman ini: {missing_periods}", "WARNING")

            # Jalankan scraping hanya jika periode yang diminta tersedia
            if period not in valid_periods:
                self.logger.log_info(f"Periode {period} tidak tersedia, skipping...", "WARNING")
                return period_data  # Return kosong karena tidak bisa lanjut

            # Klik tombol periode jika tersedia
            button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, f'button[data-period="{period}"]')))
            button.click()
            self.logger.log_info(f"Berhasil memilih periode {period}.")
            time.sleep(2)

            # Mulai scraping grafik
            graph_element = wait.until(EC.presence_of_element_located((By.TAG_NAME, 'svg')))
            graph_width = int(graph_element.size['width'])
            start_offset = -graph_width // 2

            actions = ActionChains(driver)

            for offset in range(start_offset, start_offset + graph_width, self.pixel):
                actions.move_to_element_with_offset(graph_element, offset, 0).perform()
                time.sleep(0.1)

                updated_data = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.reksa-value-head-nav'))).text
                tanggal_navdate = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.navDate'))).text

                period_data.append({'tanggal': tanggal_navdate, 'data': updated_data})

                if self.debug_mode:
                    self.logger.log_info(
                        f"{mode} | Periode {period} | Kursor {offset} | Tanggal: {tanggal_navdate} | Data: {updated_data}", 
                        "DEBUG"
                    )

            self.logger.log_info(f"Scraping {period} ({mode}) selesai, total data: {len(period_data)}")

        except Exception as e:
            self.logger.log_info(f"Scraping gagal untuk {period} ({mode}): {e}", "ERROR")

        finally:
            driver.quit()

        duration = time.time() - start_time
        self.logger.log_info(f"Scraping {period} ({mode}) selesai dalam {duration:.2f} detik.")
        return period_data


    def process_and_save_data(self, kode, mode1_data, mode2_data):
        """Memproses dan menyimpan data hasil scraping ke dalam CSV dan JSON, termasuk informasi mata uang.
        Memastikan tidak ada duplikasi sebelum menyimpan data baru."""
        
        processed_data = {}

        # Proses data baru dari mode1_data (NAV)
        for entry in mode1_data:
            try:
                tanggal_obj = self.parse_tanggal(entry['tanggal'])
                tanggal_str = tanggal_obj.strftime("%Y-%m-%d")
                data_number, currency = self.convert_to_number(entry['data'])

                if tanggal_str not in processed_data:
                    processed_data[tanggal_str] = {'NAV': 'NA', 'AUM': 'NA', 'currency': currency}
                processed_data[tanggal_str]['NAV'] = data_number
            except ValueError:
                self.logger.log_info(f"Gagal mengonversi data NAV: {entry['data']}", "ERROR")

        # Proses data baru dari mode2_data (AUM)
        for entry in mode2_data:
            try:
                tanggal_obj = self.parse_tanggal(entry['tanggal'])
                tanggal_str = tanggal_obj.strftime("%Y-%m-%d")
                data_number, currency = self.convert_to_number(entry['data'])

                if tanggal_str not in processed_data:
                    processed_data[tanggal_str] = {'NAV': 'NA', 'AUM': 'NA', 'currency': currency}
                processed_data[tanggal_str]['AUM'] = data_number
            except ValueError:
                self.logger.log_info(f"[ERROR] Gagal mengonversi data AUM: {entry['data']}", "ERROR")

        # Handle CSV file
        csv_file = os.path.join(self.database_dir, f"{kode}.csv")
        
        if os.path.exists(csv_file):
            existing_data = {}

            with open(csv_file, mode='r', newline='', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    tanggal = row['tanggal']
                    existing_data[tanggal] = {
                        'NAV': row['NAV'],
                        'AUM': row['AUM'],
                        'currency': row['currency']
                    }

            # Gabungkan data lama dengan data baru tanpa duplikasi
            for tanggal, values in processed_data.items():
                if tanggal in existing_data:
                    if values['NAV'] != 'NA':
                        existing_data[tanggal]['NAV'] = values['NAV']
                    if values['AUM'] != 'NA':
                        existing_data[tanggal]['AUM'] = values['AUM']
                    if existing_data[tanggal]['currency'] == 'NA':
                        existing_data[tanggal]['currency'] = values['currency']
                else:
                    existing_data[tanggal] = values
        else:
            existing_data = processed_data

        # Urutkan data berdasarkan tanggal
        sorted_dates = sorted(existing_data.keys())

        # Simpan data ke dalam CSV
        with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=['tanggal', 'NAV', 'AUM', 'currency'])
            writer.writeheader()

            for date in sorted_dates:
                writer.writerow({
                    'tanggal': date,
                    'NAV': existing_data[date]['NAV'],
                    'AUM': existing_data[date]['AUM'],
                    'currency': existing_data[date]['currency']
                })

        # Handle JSON file
        json_file = os.path.join(self.database_dir, f"{kode}.json")
        
        def convert_value(value):
            """Konversi nilai untuk format JSON dengan mempertahankan konsistensi None"""
            if value == 'NA' or value is None:
                return None
            try:
                return float(value) if isinstance(value, (str, int, float)) else None
            except (ValueError, TypeError):
                return None

        # Prepare new JSON data
        new_json_data = {
            "benchmark_name": kode,
            "historical_data": []
        }

        # Convert existing data to JSON format
        for date in sorted_dates:
            json_entry = {
                "date": date,
                "nav": convert_value(existing_data[date]['NAV']),
                "aum": convert_value(existing_data[date]['AUM']),
                "currency": existing_data[date]['currency'] if existing_data[date]['currency'] != 'NA' else None
            }
            new_json_data["historical_data"].append(json_entry)

        if os.path.exists(json_file):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    existing_json = json.load(f)
                    
                # Create dictionary for quick lookup of existing data
                existing_data_dict = {
                    item['date']: item 
                    for item in existing_json['historical_data']
                }
                
                # Update with new data
                for new_item in new_json_data['historical_data']:
                    existing_data_dict[new_item['date']] = new_item
                
                # Convert back to list and sort by date
                combined_data = list(existing_data_dict.values())
                combined_data.sort(key=lambda x: x['date'])
                
                # Update the JSON structure
                existing_json['historical_data'] = combined_data
                
                # Save updated JSON
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(existing_json, f, indent=2, ensure_ascii=False)
            except Exception as e:
                self.logger.log_info(f"[ERROR] Gagal memperbarui file JSON: {str(e)}", "ERROR")
        else:
            # Create new JSON file
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(new_json_data, f, indent=2, ensure_ascii=False)

        self.logger.log_info(f"Data {kode} berhasil diperbarui dan disimpan ke {csv_file} dan {json_file}")


    def run(self):
        """Menjalankan scraping untuk semua URL dan menyimpan hasil ke CSV dengan multithreading pada periode."""
        total_start_time = time.time()
        self.logger.log_info("===== Mulai scraping seluruh data =====")

        for kode, url in self.urls:
            url_start_time = time.time()
            self.logger.log_info(f"Mulai scraping untuk {kode} (Total {len(self.data_periods)} periode)")

            all_mode1_data = []
            all_mode2_data = []

            # Menjalankan scraping setiap periode secara paralel
            with ThreadPoolExecutor(max_workers=3) as executor:  # 3 worker threads, bisa disesuaikan
                futures = {executor.submit(self.scrape_mode_data, url, period, mode): (period, mode)
                        for period in self.data_periods for mode in ["Default", "AUM"]}

                for future in as_completed(futures):
                    period, mode = futures[future]
                    try:
                        data = future.result()
                        if mode == "Default":
                            all_mode1_data.extend(data)
                        else:
                            all_mode2_data.extend(data)
                        
                        self.logger.log_info(f"Scraping {kode} untuk {period} ({mode}) selesai.")
                    
                    except Exception as e:
                        self.logger.log_info(f"[ERROR] Scraping gagal untuk {kode} ({period}, {mode}): {e}", "ERROR")

            # Proses & simpan setelah semua periode selesai
            self.process_and_save_data(kode, all_mode1_data, all_mode2_data)

            url_duration = time.time() - url_start_time
            self.logger.log_info(f"Scraping {kode} selesai dalam {url_duration:.2f} detik.")

        total_duration = time.time() - total_start_time
        self.logger.log_info(f"===== Semua scraping selesai dalam {total_duration:.2f} detik =====")



# logger = Logger()


# #################################################################################

# today = date.today()
# # today_request = date(2025, 2, 10)

# urls = [
#     ['Batavia Technology Sharia Equity USD','https://bibit.id/reksadana/RD4183'],
# ]

# pixel = 20

# # Read csv

# for kode, url in urls:
#     csv_file_recent = f"database/{kode}.csv"
#     df = pd.read_csv(csv_file_recent)
#     latest_data = df.iloc[-1].tolist()

#     latest_data_date = latest_data[0]
#     latest_data_value = latest_data[-1]

#     LD_years, LD_months, LD_dates = latest_data_date.split("-")
#     date_database = date(int(LD_years), int(LD_months), int(LD_dates))

#     delta_date = today - date_database

#     if delta_date < timedelta(0):
#             print("tidak proses")
#     else:
#         # Daftar periode berdasarkan hari
#         period_map = [
#             (30, ['1M']),
#             (90, ['1M', '3M']),
#             (365, ['1M', '3M', 'YTD']),
#             (1095, ['1M', '3M', 'YTD', '3Y']),
#             (1825, ['1M', '3M', 'YTD', '3Y', '5Y']),
#             (3650, ['1M', '3M', 'YTD', '3Y', '5Y', '10Y'])
#         ]

#         # Default jika lebih dari 5 tahun
#         data_periods = ['ALL', '1M', '3M', 'YTD', '3Y', '5Y', '10Y']

#         # Loop untuk mencari rentang yang sesuai
#         for days, periods in period_map:
#             if delta_date <= timedelta(days=days):
#                 data_periods = periods
#                 break  # Stop loop setelah menemukan rentang yang sesuai

# print(data_periods)




# scraper = Mutual_Fund_Data_Scraper(urls, data_periods, pixel, logger, debug_mode=True)
# scraper.run()