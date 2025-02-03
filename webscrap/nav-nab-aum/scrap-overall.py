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
        self.logger = logger
        self.debug_mode = debug_mode
        self.database_dir = "database"
        os.makedirs(self.database_dir, exist_ok=True)

    def convert_to_number(self, value):
        """Mengonversi string nilai dengan format K, M, B, T menjadi angka float."""
        value = value.replace(',', '')
        if 'K' in value:
            return float(value.replace('K', '')) * 1_000
        elif 'M' in value:
            return float(value.replace('M', '')) * 1_000_000
        elif 'B' in value:
            return float(value.replace('B', '')) * 1_000_000_000
        elif 'T' in value:
            return float(value.replace('T', '')) * 1_000_000_000_000
        else:
            return float(value)

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
            self.logger.log_info("[INFO] Beralih ke mode AUM...")
            aum_button.click()
            time.sleep(3)  # Menunggu perubahan tampilan
            return True
        except Exception as e:
            self.logger.log_info(f"[ERROR] Gagal beralih ke mode AUM: {e}", "ERROR")
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

            button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, f'button[data-period="{period}"]')))
            button.click()
            self.logger.log_info(f"Berhasil memilih periode {period}")
            time.sleep(2)

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
                    self.logger.log_info(f"Kursor {offset} | Tanggal: {tanggal_navdate} | Data: {updated_data}", "DEBUG")

            self.logger.log_info(f"Scraping {period} ({mode}) selesai, total data: {len(period_data)}")

        except Exception as e:
            self.logger.log_info(f"Scraping gagal untuk {period} ({mode}): {e}", "ERROR")

        finally:
            driver.quit()

        duration = time.time() - start_time
        self.logger.log_info(f"Scraping {period} ({mode}) selesai dalam {duration:.2f} detik.")
        return period_data

    def process_and_save_data(self, kode, mode1_data, mode2_data):
        """Memproses dan menyimpan data hasil scraping ke dalam CSV."""
        processed_data = {}

        for entry in mode1_data:
            try:
                tanggal_obj = self.parse_tanggal(entry['tanggal'])
                tanggal_str = tanggal_obj.strftime("%Y-%m-%d")
                data_number = self.convert_to_number(entry['data'].replace('Rp', '').strip())

                if tanggal_str not in processed_data:
                    processed_data[tanggal_str] = {'NAV': 'NA', 'AUM': 'NA'}
                processed_data[tanggal_str]['NAV'] = data_number
            except ValueError as e:
                self.logger.log_info(f"[ERROR] Gagal mengonversi data NAV: {entry['data']}", "ERROR")

        for entry in mode2_data:
            try:
                tanggal_obj = self.parse_tanggal(entry['tanggal'])
                tanggal_str = tanggal_obj.strftime("%Y-%m-%d")
                data_number = self.convert_to_number(entry['data'].replace('Rp', '').strip())

                if tanggal_str not in processed_data:
                    processed_data[tanggal_str] = {'NAV': 'NA', 'AUM': 'NA'}
                processed_data[tanggal_str]['AUM'] = data_number
            except ValueError as e:
                self.logger.log_info(f"[ERROR] Gagal mengonversi data AUM: {entry['data']}", "ERROR")

        sorted_dates = sorted(processed_data.keys())

        csv_file = os.path.join(self.database_dir, f"{kode}.csv")
        with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=['tanggal', 'NAV', 'AUM'])
            writer.writeheader()

            for date in sorted_dates:
                writer.writerow({
                    'tanggal': date,
                    'NAV': processed_data[date]['NAV'],
                    'AUM': processed_data[date]['AUM']
                })

        self.logger.log_info(f"Data {kode} berhasil disimpan ke {csv_file}")

    def run(self):
        """Menjalankan scraping untuk semua URL dan menyimpan hasil ke CSV."""
        total_start_time = time.time()
        self.logger.log_info("===== Mulai scraping seluruh data =====")

        for kode, url in self.urls:
            url_start_time = time.time()
            self.logger.log_info(f"Mulai scraping untuk {kode} (Total {len(self.data_periods)} periode)")

            all_mode1_data = []
            all_mode2_data = []

            for period in self.data_periods:
                self.logger.log_info(f"Scraping {kode} untuk periode {period}...")

                mode1_data = self.scrape_mode_data(url, period, "Default")
                mode2_data = self.scrape_mode_data(url, period, "AUM")

                all_mode1_data.extend(mode1_data)
                all_mode2_data.extend(mode2_data)

            # Proses & simpan setelah semua periode selesai
            self.process_and_save_data(kode, all_mode1_data, all_mode2_data)

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