import time
import pandas as pd
import numpy as np
import csv
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
from selenium.webdriver.chrome.options import Options
from datetime import date, timedelta
import os

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

    def _convert_to_float(self, value):
        """Convert string number to float, handling commas and invalid values."""
        try:
            if pd.isna(value) or value == "-":
                return None
            # Remove commas and convert to float
            return float(value.replace(',', ''))
        except (ValueError, AttributeError):
            return None

    def _create_json_data(self, df, name):
        json_data = {
            "benchmark_name": name,
            "historical_data": []
        }
        
        for _, row in df.iterrows():
            data_point = {
                "date": str(row['Date']),
                "open": self._convert_to_float(row['Open']),
                "high": self._convert_to_float(row['High']),
                "low": self._convert_to_float(row['Low']),
                "close": self._convert_to_float(row['Close']),
                "adj_close": self._convert_to_float(row['Adj Close']),
                "volume": self._convert_to_float(row['Volume'])
            }
            json_data["historical_data"].append(data_point)
        
        return json_data

    def _save_data(self, df, name):
        # Convert numeric columns before saving
        numeric_columns = ['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']
        for col in numeric_columns:
            df[col] = df[col].apply(self._convert_to_float)

        # Prepare filenames
        csv_filename = f"database/{name}.csv"
        json_filename = f"database/{name}.json"
        
        # Handle CSV file
        if os.path.exists(csv_filename):
            # Read existing CSV
            existing_df = pd.read_csv(csv_filename)
            existing_df['Date'] = pd.to_datetime(existing_df['Date']).dt.date
            
            # Combine data
            combined_df = pd.concat([existing_df, df])
            combined_df = combined_df.drop_duplicates(subset=['Date'], keep='last')
            combined_df = combined_df.sort_values('Date')
            
            # Save CSV
            combined_df.to_csv(csv_filename, index=False)
            print(f"Data telah diperbarui di {csv_filename}")
            print(f"Jumlah data baru yang ditambahkan atau diperbarui: {len(combined_df) - len(existing_df)}")
            
            # Create JSON data from combined DataFrame
            json_data = self._create_json_data(combined_df, name)
        else:
            # Create new CSV
            df.to_csv(csv_filename, index=False)
            print(f"File CSV baru dibuat: {csv_filename}")
            print(f"Jumlah data yang disimpan: {len(df)}")
            
            # Create JSON data from new DataFrame
            json_data = self._create_json_data(df, name)
        
        # Save JSON file
        with open(json_filename, 'w') as f:
            json.dump(json_data, f, indent=2)
        print(f"Data JSON telah disimpan di {json_filename}")

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
                
                # Save both CSV and JSON
                self._save_data(df, name)
                
                print(df)
            else:
                print(f"Tahun {self.pilih_tahun} tidak ditemukan untuk {name}.")
        except Exception as e:
            print(f"Error saat scraping {name}: {e}")


today = date.today()
urls = [
    ['IHSG', 'https://finance.yahoo.com/quote/%5EJKSE/history/?p=%5EJKSE'],
    ['LQ45', 'https://finance.yahoo.com/quote/%5EJKLQ45/history/']
]

for kode, url in urls:
    csv_file_recent = f"database/{kode}.csv"
    
    if os.path.exists(csv_file_recent):
        df = pd.read_csv(csv_file_recent)
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df = df.dropna(subset=['Date'])
        latest_data = df.iloc[-1]
        latest_data_date = latest_data['Date'].date()

        delta_date = today - latest_data_date

        if delta_date < timedelta(0):
            print("Tidak ada proses pembaruan")
            continue
        
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
    else:
        data_periods = 'Max'

scraper = WebScraper(urls, data_periods, 'w')
scraper.scrape_data()
