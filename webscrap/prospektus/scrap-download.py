from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
import glob
import os
import time
import glob
from datetime import datetime

class Logger:
    """Logger untuk mencatat aktivitas scraping dan downloading ke file log yang sama."""
    def __init__(self, log_dir="logs"):
        os.makedirs(log_dir, exist_ok=True)
        log_filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_activity.log"
        self.LOG_FILE = os.path.join(log_dir, log_filename)

    def log_info(self, message, status="INFO"):
        """Menyimpan log ke file dengan format timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [{status}] {message}\n"

        with open(self.LOG_FILE, "a", encoding="utf-8") as log_file:
            log_file.write(log_message)

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
        driver = self._setup_driver()  # Inisialisasi driver sekali

        try:
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
                    continue  # Lanjutkan ke iterasi berikutnya jika terjadi error

        finally:
            driver.quit()



logger = Logger()  # Buat satu logger untuk semua proses

# Buat instance dengan folder kustom
# downloader = ProspektusDownloader(download_folder="my_downloads")


urls = [
    ['ABF Indonesia Bond Index Fund', 'https://bibit.id/reksadana/RD13'],
    # ['Mandiri Investa Cerdas', 'https://bibit.id/reksadana/RD14']  # Bisa ditambahkan jika perlu
]

downloader = ProspektusDownloader(logger)
downloader.download(urls)