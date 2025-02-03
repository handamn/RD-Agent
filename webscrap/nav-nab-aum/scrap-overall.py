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
        log_filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_scrapping.log"
        self.LOG_FILE = os.path.join(log_dir, log_filename)

    def log_info(self, message, status="INFO"):
        """Menyimpan log ke file dengan format timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [{status}] {message}\n"

        with open(self.LOG_FILE, "a", encoding="utf-8") as log_file:
            log_file.write(log_message)

class Scraper:
    def __init__(self, urls, data_periods, pixel, logger, debug_mode=False):
        """Inisialisasi scraper dengan daftar URL, periode, pixel, dan logger eksternal."""
        self.urls = urls
        self.data_periods = data_periods
        self.pixel = pixel
        self.logger = logger  # Gunakan logger eksternal
        self.debug_mode = debug_mode
        self.database_dir = "database"  # Folder penyimpanan CSV
        os.makedirs(self.database_dir, exist_ok=True)  # Buat folder jika belum ada

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

            # Klik tombol periode
            button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, f'button[data-period="{period}"]')))
            button.click()
            self.logger.log_info(f"Berhasil memilih periode {period}")
            time.sleep(2)

            # Ambil elemen grafik
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
                    self.logger.log_info(f"Kursor pada offset {offset} | Tanggal: {tanggal_navdate} | Data: {updated_data}", "DEBUG")

            self.logger.log_info(f"Scraping {period} ({mode}) selesai, total data: {len(period_data)}")

        except Exception as e:
            self.logger.log_info(f"Scraping gagal untuk {period} ({mode}): {e}", "ERROR")

        finally:
            driver.quit()

        duration = time.time() - start_time
        self.logger.log_info(f"Scraping {period} ({mode}) selesai dalam {duration:.2f} detik.")
        return period_data

    def scrape_all_periods(self, url, mode):
        """Menjalankan scraping secara paralel untuk semua periode dalam satu mode."""
        max_workers = min(len(self.data_periods), 4)
        self.logger.log_info(f"Scraping {mode} dimulai dengan {max_workers} thread...")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.scrape_mode_data, url, period, mode): period for period in self.data_periods}
            results = []

            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.extend(result)
                except Exception as e:
                    self.logger.log_info(f"Scraping error: {e}", "ERROR")

            return results

    def save_to_csv(self, kode, mode1_data, mode2_data):
        """Menyimpan data hasil scraping ke dalam file CSV."""
        csv_file = os.path.join(self.database_dir, f"{kode}.csv")
        processed_data = {}

        # Proses data untuk mode1
        for entry in mode1_data:
            tanggal = entry['tanggal']
            if tanggal not in processed_data:
                processed_data[tanggal] = {'mode1': 'NA', 'mode2': 'NA'}
            processed_data[tanggal]['mode1'] = entry['data']

        # Proses data untuk mode2
        for entry in mode2_data:
            tanggal = entry['tanggal']
            if tanggal not in processed_data:
                processed_data[tanggal] = {'mode1': 'NA', 'mode2': 'NA'}
            processed_data[tanggal]['mode2'] = entry['data']

        # Urutkan berdasarkan tanggal
        sorted_dates = sorted(processed_data.keys())

        # Simpan ke CSV
        with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=['tanggal', 'mode1', 'mode2'])
            writer.writeheader()

            for date in sorted_dates:
                writer.writerow({
                    'tanggal': date,
                    'mode1': processed_data[date]['mode1'],
                    'mode2': processed_data[date]['mode2']
                })

        self.logger.log_info(f"Data {kode} berhasil disimpan ke {csv_file}")

    def run(self):
        """Menjalankan scraping untuk semua URL dan menyimpan hasil ke CSV."""
        total_start_time = time.time()
        self.logger.log_info("===== Mulai scraping seluruh data =====")

        for kode, url in self.urls:
            url_start_time = time.time()
            self.logger.log_info(f"Mulai scraping untuk {kode}")

            mode1_data = self.scrape_all_periods(url, "Default")
            mode2_data = self.scrape_all_periods(url, "AUM")

            # Simpan ke CSV
            self.save_to_csv(kode, mode1_data, mode2_data)

            url_duration = time.time() - url_start_time
            self.logger.log_info(f"Scraping {kode} selesai dalam {url_duration:.2f} detik.")

        total_duration = time.time() - total_start_time
        self.logger.log_info(f"===== Semua scraping selesai dalam {total_duration:.2f} detik =====")



logger = Logger()

### Menggunakan class
urls = [
    ['ABF Indonesia Bond Index Fund', 'https://bibit.id/reksadana/RD13'],
    # ['Mandiri Investa Cerdas', 'https://bibit.id/reksadana/RD14']  # Bisa ditambahkan jika perlu
]

data_periods = ['3Y', '5Y']
pixel = 200

# Membuat scraper instance dan menjalankan scraping
scraper = Scraper(urls, data_periods, pixel, logger, debug_mode=True)
scraper.run()