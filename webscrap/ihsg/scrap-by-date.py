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

class WebScraper:
    def __init__(self, urls, pilih_tahun, mode_csv):
        self.urls = urls
        self.pilih_tahun = pilih_tahun
        self.mode_csv = mode_csv
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        self.driver = webdriver.Chrome(options=options)

    def scrape_data(self):
        try:
            for name, url in self.urls:
                self._scrape_single_url(name, url)
        finally:
            self.driver.quit()

    def _scrape_single_url(self, name, url):
        try:
            self.driver.get(url)
            time.sleep(5)

            button = self.driver.find_element(By.CSS_SELECTOR, ".tertiary-btn.fin-size-small.menuBtn.rounded.yf-15mk0m")
            button.click()
            time.sleep(2)

            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".dialog-container.menu-surface-dialog.modal.yf-9a5vow"))
            )

            buttons = self.driver.find_elements(By.CSS_SELECTOR, ".quickpicks.yf-1th5n0r .tertiary-btn.fin-size-small.tw-w-full.tw-justify-center.rounded.yf-15mk0m")
            values = [button.text for button in buttons]

            if self.pilih_tahun in values:
                index = values.index(self.pilih_tahun)
                buttons[index].click()
                time.sleep(2)

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
                csv_filename = f"database/{name}.csv"
                if os.path.exists(csv_filename):
                    existing_df = pd.read_csv(csv_filename)
                    existing_df['Date'] = pd.to_datetime(existing_df['Date']).dt.date
                    combined_df = pd.concat([existing_df, df])
                    combined_df = combined_df.drop_duplicates(subset=['Date'], keep='last')
                    combined_df = combined_df.sort_values('Date')
                    combined_df.to_csv(csv_filename, index=False)
                    print(f"Data CSV telah diperbarui di {csv_filename}")
                    print(f"Jumlah data CSV baru yang ditambahkan atau diperbarui: {len(combined_df) - len(existing_df)}")
                else:
                    df.to_csv(csv_filename, index=False)
                    print(f"File CSV baru dibuat: {csv_filename}")
                    print(f"Jumlah data yang disimpan: {len(df)}")

                # Handle JSON file
                json_filename = f"database/{name}.json"
                new_json_data = {
                    "benchmark_name": name,
                    "historical_data": []
                }
                
                def safe_float_convert(value):
                    if pd.isna(value):
                        return None
                    try:
                        # Menghapus koma ribuan dan mengonversi ke float
                        return float(str(value).replace(',', ''))
                    except (ValueError, TypeError):
                        try:
                            # Jika masih error, coba dengan menghapus semua koma
                            return float(str(value).replace(',', ''))
                        except (ValueError, TypeError):
                            return None
                
                # Convert DataFrame to JSON structure
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
                    with open(json_filename, 'r') as f:
                        existing_json = json.load(f)
                    
                    # Create a dictionary for quick lookup of existing data
                    existing_data_dict = {item['date']: item for item in existing_json['historical_data']}
                    
                    # Update with new data
                    for new_item in new_json_data['historical_data']:
                        existing_data_dict[new_item['date']] = new_item
                    
                    # Convert back to list and sort by date
                    combined_data = list(existing_data_dict.values())
                    combined_data.sort(key=lambda x: x['date'])
                    
                    # Update the JSON structure
                    existing_json['historical_data'] = combined_data
                    
                    with open(json_filename, 'w') as f:
                        json.dump(existing_json, f, indent=2)
                    
                    print(f"Data JSON telah diperbarui di {json_filename}")
                    print(f"Jumlah data JSON yang diproses: {len(combined_data)}")
                else:
                    with open(json_filename, 'w') as f:
                        json.dump(new_json_data, f, indent=2)
                    print(f"File JSON baru dibuat: {json_filename}")
                    print(f"Jumlah data yang disimpan: {len(new_json_data['historical_data'])}")

                print(df)
            else:
                print(f"Tahun {self.pilih_tahun} tidak ditemukan untuk {name}.")
        except Exception as e:
            print(f"Error saat scraping {name}: {e}")


today = date.today()
# today = date(2025, 2, 10)

urls = [
    ['IHSG', 'https://finance.yahoo.com/quote/%5EJKSE/history/?p=%5EJKSE'],
    ['LQ45', 'https://finance.yahoo.com/quote/%5EJKLQ45/history/']
]

for kode, url in urls:
    csv_file_recent = f"database/{kode}.csv"
    df = pd.read_csv(csv_file_recent)
    latest_data = df.iloc[-1].tolist()

    latest_data_date = latest_data[0]
    latest_data_value = latest_data[-1]


    LD_years, LD_months, LD_dates = latest_data_date.split("-")
    date_database = date(int(LD_years), int(LD_months), int(LD_dates))

    delta_date = today - date_database

    if delta_date < timedelta(0):
            print("tidak proses")
    else:
        # Daftar periode berdasarkan hari
        period_map = [
            (1, '1D'),
            (5, '5D'),
            (90, '3M'),
            (180, '6M'),
            (360, '1Y'),
            (1800, '5Y')
        ]

        # Default jika lebih dari 5 tahun
        data_periods = 'Max'
        
        # Loop untuk mencari rentang yang sesuai
        for days, periods in period_map:
            if delta_date <= timedelta(days=days):
                data_periods = periods
                break  # Stop loop setelah menemukan rentang yang sesuai

scraper = WebScraper(urls, data_periods, 'w')
scraper.scrape_data()