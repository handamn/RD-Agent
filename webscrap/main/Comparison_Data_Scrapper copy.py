import time
import pandas as pd
import numpy as np
import csv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
from selenium.webdriver.chrome.options import Options
import time
from datetime import date, timedelta
import os
import json

class Logger:
    """Logger untuk mencatat aktivitas scraping ke file log."""
    def __init__(self, log_dir="logs"):
        os.makedirs(log_dir, exist_ok=True)
        log_filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_Comparison_Data_Scrapper.log"
        self.LOG_FILE = os.path.join(log_dir, log_filename)

    def log_info(self, message, status="INFO"):
        """Menyimpan log ke file dengan format timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [{status}] {message}\n"

        with open(self.LOG_FILE, "a", encoding="utf-8") as log_file:
            log_file.write(log_message)

class Comparison_Data_Scrapper:
    def __init__(self, urls, mode_csv):
        self.urls = urls
        self.mode_csv = mode_csv
        self.logger = Logger()
        self.data_periods = self.determine_period()
        
        # Log konfigurasi awal
        self.logger.log_info(f"Inisialisasi Comparison_Data_Scrapper dengan {len(urls)} URL dan tahun {self.data_periods}")
        
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        try:
            self.driver = webdriver.Chrome(options=options)
            self.logger.log_info("Browser Chrome berhasil diinisialisasi")
        except Exception as e:
            self.logger.log_info(f"Gagal menginisialisasi Chrome browser: {str(e)}", "ERROR")
            raise

    def determine_period(self):
        today = date.today()
        csv_file_recent = f"database/comparison/{self.urls[0][0]}.csv"
        df = pd.read_csv(csv_file_recent)
        latest_data = df.iloc[-1].tolist()
        latest_data_date = latest_data[0]
        LD_years, LD_months, LD_dates = latest_data_date.split("-")
        date_database = date(int(LD_years), int(LD_months), int(LD_dates))
        delta_date = today - date_database

        period_map = [
            (1, '1D'),
            (5, '5D'),
            (90, '3M'),
            (180, '6M'),
            (360, '1Y'),
            (1800, '5Y')
        ]

        data_periods = 'Max'
        for days, periods in period_map:
            if delta_date <= timedelta(days=days):
                data_periods = periods
                break

        return data_periods
    
    def scrape_data(self):
        start_time = time.time()
        self.logger.log_info("===== Memulai proses scraping =====")
        
        try:
            for name, url in self.urls:
                self.logger.log_info(f"Memulai scraping untuk {name} dari {url}")
                self._scrape_single_url(name, url)
                
        except Exception as e:
            self.logger.log_info(f"Error dalam proses scraping utama: {str(e)}", "ERROR")
        finally:
            self.driver.quit()
            duration = time.time() - start_time
            self.logger.log_info(f"===== Proses scraping selesai dalam {duration:.2f} detik =====")

    def _scrape_single_url(self, name, url):
        try:
            self.logger.log_info(f"Mengakses URL: {url}")
            self.driver.get(url)
            time.sleep(5)

            self.logger.log_info("Mencari dan mengklik tombol menu")
            button = self.driver.find_element(By.CSS_SELECTOR, ".tertiary-btn.fin-size-small.menuBtn.rounded.yf-15mk0m")
            button.click()
            time.sleep(2)

            self.logger.log_info("Menunggu dialog menu muncul")
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".dialog-container.menu-surface-dialog.modal.yf-9a5vow"))
            )

            buttons = self.driver.find_elements(By.CSS_SELECTOR, ".quickpicks.yf-1th5n0r .tertiary-btn.fin-size-small.tw-w-full.tw-justify-center.rounded.yf-15mk0m")
            values = [button.text for button in buttons]
            self.logger.log_info(f"Opsi tahun yang tersedia: {values}")

            if self.data_periods in values:
                index = values.index(self.data_periods)
                self.logger.log_info(f"Memilih tahun {self.data_periods}")
                buttons[index].click()
                time.sleep(2)

                self.logger.log_info("Mengekstrak data tabel")
                headers = [header.text.strip() for header in self.driver.find_elements(By.CSS_SELECTOR, ".table.yf-1jecxey.noDl th")]
                table = self.driver.find_element(By.CSS_SELECTOR, ".table.yf-1jecxey.noDl")
                rows = table.find_elements(By.TAG_NAME, "tr")
                data = []
                for row in rows:
                    cols = row.find_elements(By.TAG_NAME, "td")
                    cols = [col.text.strip() for col in cols]
                    data.append(cols)

                df = pd.DataFrame(data, columns=headers)
                df.replace("-", np.nan, inplace=True)
                df = df.drop(0).reset_index(drop=True)
                df['Date'] = pd.to_datetime(df['Date'], format='%b %d, %Y', errors='coerce')
                df['Date'] = df['Date'].dt.date
                df = df[::-1]
                
                # Handle CSV file
                csv_filename = f"database/comparison/{name}.csv"
                if os.path.exists(csv_filename):
                    self.logger.log_info(f"Memperbarui file CSV yang ada: {csv_filename}")
                    existing_df = pd.read_csv(csv_filename)
                    existing_df['Date'] = pd.to_datetime(existing_df['Date']).dt.date
                    combined_df = pd.concat([existing_df, df])
                    combined_df = combined_df.drop_duplicates(subset=['Date'], keep='last')
                    combined_df = combined_df.sort_values('Date')
                    combined_df.to_csv(csv_filename, index=False)
                    self.logger.log_info(f"Data CSV diperbarui. {len(combined_df) - len(existing_df)} baris baru ditambahkan")
                else:
                    self.logger.log_info(f"Membuat file CSV baru: {csv_filename}")
                    df.to_csv(csv_filename, index=False)
                    self.logger.log_info(f"File CSV dibuat dengan {len(df)} baris data")

                # Handle JSON file
                json_filename = f"database/comparison/{name}.json"
                self.logger.log_info(f"Memproses data untuk format JSON: {json_filename}")
                new_json_data = {
                    "benchmark_name": name,
                    "historical_data": []
                }
                
                def safe_float_convert(value):
                    if pd.isna(value):
                        return None
                    try:
                        return float(str(value).replace(',', ''))
                    except (ValueError, TypeError):
                        try:
                            return float(str(value).replace(',', ''))
                        except (ValueError, TypeError):
                            return None
                
                for _, row in df.iterrows():
                    json_row = {
                        "date": str(row['Date']),
                        "open": safe_float_convert(row['Open']),
                        "high": safe_float_convert(row['High']),
                        "low": safe_float_convert(row['Low']),
                        "close": safe_float_convert(row['Close']),
                        "adj_close": safe_float_convert(row['Adj Close']),
                        "volume": safe_float_convert(row['Volume'])
                    }
                    new_json_data["historical_data"].append(json_row)

                if os.path.exists(json_filename):
                    self.logger.log_info("Memperbarui file JSON yang ada")
                    with open(json_filename, 'r') as f:
                        existing_json = json.load(f)
                    
                    existing_data_dict = {item['date']: item for item in existing_json['historical_data']}
                    
                    for new_item in new_json_data['historical_data']:
                        existing_data_dict[new_item['date']] = new_item
                    
                    combined_data = list(existing_data_dict.values())
                    combined_data.sort(key=lambda x: x['date'])
                    
                    existing_json['historical_data'] = combined_data
                    
                    with open(json_filename, 'w') as f:
                        json.dump(existing_json, f, indent=2)
                    
                    self.logger.log_info(f"Data JSON diperbarui dengan total {len(combined_data)} records")
                else:
                    self.logger.log_info("Membuat file JSON baru")
                    with open(json_filename, 'w') as f:
                        json.dump(new_json_data, f, indent=2)
                    self.logger.log_info(f"File JSON dibuat dengan {len(new_json_data['historical_data'])} records")

                self.logger.log_info(f"Scraping selesai untuk {name}")
            else:
                self.logger.log_info(f"Tahun {self.data_periods} tidak ditemukan untuk {name}", "WARNING")
        except Exception as e:
            self.logger.log_info(f"Error saat scraping {name}: {str(e)}", "ERROR")
            raise


# today = date.today()
# # today = date(2025, 2, 10)

# urls = [
#     ['IHSG', 'https://finance.yahoo.com/quote/%5EJKSE/history/?p=%5EJKSE'],
#     ['LQ45', 'https://finance.yahoo.com/quote/%5EJKLQ45/history/']
# ]

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
#             (1, '1D'),
#             (5, '5D'),
#             (90, '3M'),
#             (180, '6M'),
#             (360, '1Y'),
#             (1800, '5Y')
#         ]

#         # Default jika lebih dari 5 tahun
#         data_periods = 'Max'
        
#         # Loop untuk mencari rentang yang sesuai
#         for days, periods in period_map:
#             if delta_date <= timedelta(days=days):
#                 data_periods = periods
#                 break  # Stop loop setelah menemukan rentang yang sesuai

# scraper = Comparison_Data_Scrapper(urls, data_periods, 'w')
# scraper.scrape_data()