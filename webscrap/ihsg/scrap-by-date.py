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
                
                filename = f"database/{name}.csv"
                with open(filename, mode=self.mode_csv, newline='', encoding='utf-8') as file:
                    writer = csv.DictWriter(file, fieldnames=df.columns)
                    writer.writeheader()
                    for _, row in df.iterrows():
                        writer.writerow(row.to_dict())
                
                print(f"Data telah disimpan ke {filename}")
                print(df)
            else:
                print(f"Tahun {self.pilih_tahun} tidak ditemukan untuk {name}.")
        except Exception as e:
            print(f"Error saat scraping {name}: {e}")

# urls = [
#     ['IHSG', 'https://finance.yahoo.com/quote/%5EJKSE/history/?p=%5EJKSE'],
#     ['LQ45', 'https://finance.yahoo.com/quote/%5EJKLQ45/history/']
# ]

# pilih_tahun = "Max"

# scraper = WebScraper(urls, pilih_tahun, 'w')
# scraper.scrape_data()

today = date.today()
today_request = date(2025, 2, 10)

urls = [
    ['Batavia Technology Sharia Equity USD','https://bibit.id/reksadana/RD4183'],
]