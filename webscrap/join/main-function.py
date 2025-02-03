import os
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import glob


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

    def run(self):
        """Menjalankan scraping untuk semua URL."""
        total_start_time = time.time()
        self.logger.log_info("===== Mulai scraping seluruh data =====")

        for kode, url in self.urls:
            url_start_time = time.time()
            self.logger.log_info(f"Mulai scraping untuk {kode}")

            mode1_data = self.scrape_all_periods(url, "Default")
            mode2_data = self.scrape_all_periods(url, "AUM")

            url_duration = time.time() - url_start_time
            self.logger.log_info(f"Scraping {kode} selesai dalam {url_duration:.2f} detik.")

        total_duration = time.time() - total_start_time
        self.logger.log_info(f"===== Semua scraping selesai dalam {total_duration:.2f} detik =====")


class ProspektusDownloader:
    def __init__(self, logger, download_folder="downloads"):
        """Inisialisasi downloader dengan lokasi folder dan logger eksternal."""
        self.logger = logger
        self.download_dir = os.path.join(os.getcwd(), download_folder)
        os.makedirs(self.download_dir, exist_ok=True)

    def _setup_driver(self):
        """Menyiapkan instance WebDriver dengan konfigurasi download otomatis."""
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-gpu')

        prefs = {
            "download.default_directory": self.download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True
        }
        chrome_options.add_experimental_option("prefs", prefs)
        return webdriver.Chrome(options=chrome_options)

    def _wait_for_download(self, timeout=60):
        """Menunggu hingga file selesai diunduh."""
        self.logger.log_info(f"Menunggu proses download selesai di {self.download_dir}...")
        seconds = 0
        while seconds < timeout:
            time.sleep(1)
            files = os.listdir(self.download_dir)
            if not any(fname.endswith('.crdownload') for fname in files):
                self.logger.log_info("Download selesai.")
                return True
            seconds += 1
        self.logger.log_info("Download timeout!", "ERROR")
        return False

    def _rename_latest_pdf(self, new_name):
        """Mengganti nama file PDF terbaru dengan nama yang ditentukan."""
        list_of_files = glob.glob(os.path.join(self.download_dir, '*.pdf'))
        if not list_of_files:
            raise Exception("Tidak ada file PDF ditemukan")

        latest_file = max(list_of_files, key=os.path.getctime)
        new_path = os.path.join(self.download_dir, f"{new_name}.pdf")

        os.rename(latest_file, new_path)
        self.logger.log_info(f"File {latest_file} berhasil diubah menjadi {new_path}")

    def download(self, urls, button_class="DetailProductStyle_detail-produk-button__zk419"):
        """
        Fungsi utama untuk mengunduh dan rename file.

        Parameters:
        urls (list): List berisi judul dan URL halaman web yang berisi button download.
        button_class (str): Class name dari button yang akan diklik.
        """
        driver = self._setup_driver()

        for kode, url in urls:
            try:
                self.logger.log_info(f"Memulai download prospektus untuk {kode} dari {url}")
                driver.get(url)

                button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CLASS_NAME, button_class))
                )
                button.click()

                if not self._wait_for_download():
                    raise Exception("Download timeout")

                time.sleep(2)
                self._rename_latest_pdf(kode)

                self.logger.log_info(f"Download prospektus {kode} berhasil.")

            except Exception as e:
                self.logger.log_info(f"Error saat download {kode}: {str(e)}", "ERROR")

            finally:
                driver.quit()


logger = Logger()


urls = [
    ['ABF Indonesia Bond Index Fund', 'https://bibit.id/reksadana/RD13'],
]


data_periods = ['3Y', '5Y']
pixel = 200

# Membuat scraper instance dan menjalankan scraping
scraper = Scraper(urls, data_periods, pixel, logger, debug_mode=True)
scraper.run()

downloader = ProspektusDownloader(logger)
downloader.download(urls)