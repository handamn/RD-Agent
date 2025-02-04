import time
import pandas as pd
import numpy as np
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class WebScraper:
    def __init__(self, url, pilih_tahun):
        self.url = url
        self.pilih_tahun = pilih_tahun
        self.driver = webdriver.Chrome()  # Inisialisasi WebDriver

    def scrape_data(self):
        try:
            # 1. Load web
            self.driver.get(self.url)
            time.sleep(5)  # Tunggu beberapa detik untuk memastikan halaman terload sepenuhnya

            # 2. Klik button dengan class tertentu
            button = self.driver.find_element(By.CSS_SELECTOR, ".tertiary-btn.fin-size-small.menuBtn.rounded.yf-15mk0m")
            button.click()
            time.sleep(2)  # Tunggu dialog box terbuka

            # 3. Tunggu dialog box terbuka
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".dialog-container.menu-surface-dialog.modal.yf-9a5vow"))
            )

            # 4. Ambil value dari button yang ada di dalam dialog box
            buttons = self.driver.find_elements(By.CSS_SELECTOR, ".quickpicks.yf-1th5n0r .tertiary-btn.fin-size-small.tw-w-full.tw-justify-center.rounded.yf-15mk0m")
            values = [button.text for button in buttons]

            # 5. Cocokkan value dengan input variable pilih_tahun
            if self.pilih_tahun in values:
                # 6. Klik button yang sesuai
                index = values.index(self.pilih_tahun)
                buttons[index].click()
                time.sleep(2)  # Tunggu proses selesai

                # 7. Ambil header dari tabel
                headers = self.driver.find_elements(By.CSS_SELECTOR, ".table.yf-1jecxey.noDl th")
                header_list = [header.text.strip() for header in headers]

                # 8. Ambil data dari tabel
                table = self.driver.find_element(By.CSS_SELECTOR, ".table.yf-1jecxey.noDl")
                rows = table.find_elements(By.TAG_NAME, "tr")
                data = []
                for row in rows:
                    cols = row.find_elements(By.TAG_NAME, "td")
                    cols = [col.text.strip() for col in cols]
                    data.append(cols)

                # 9. Buat DataFrame
                df = pd.DataFrame(data, columns=header_list)

                # 10. Ganti "-" dengan NaN
                df.replace("-", np.nan, inplace=True)

                df = df.drop(0).reset_index(drop=True)

                # 11. Simpan ke CSV
                df.to_csv("output_with_header.csv", index=False)
                print("Data telah disimpan ke output_with_header.csv")

                # 12. Print DataFrame
                print(df)

            else:
                print(f"Tahun {self.pilih_tahun} tidak ditemukan.")

        finally:
            # Tutup browser
            self.driver.quit()

# Contoh penggunaan
url = "https://finance.yahoo.com/quote/%5EJKSE/history/?p=%5EJKSE"  # Ganti dengan URL yang sesuai
# https://finance.yahoo.com/quote/%5EJKLQ45/history/
pilih_tahun = "5D"  # Ganti dengan tahun yang ingin dipilih

scraper = WebScraper(url, pilih_tahun)
scraper.scrape_data()