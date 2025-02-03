from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
import glob

class ProspektusDownloader:
    def __init__(self, download_folder="downloads"):
        """
        Inisialisasi downloader dengan lokasi folder yang dapat dikustomisasi
        
        Parameters:
        download_folder (str): Nama folder untuk menyimpan file yang diunduh
        """
        self.download_dir = os.path.join(os.getcwd(), download_folder)
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)
    
    def _setup_driver(self):
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
        seconds = 0
        while seconds < timeout:
            time.sleep(1)
            files = os.listdir(self.download_dir)
            if not any(fname.endswith('.crdownload') for fname in files):
                return True
            seconds += 1
        return False
    
    def _rename_latest_pdf(self, new_name):
        list_of_files = glob.glob(os.path.join(self.download_dir, '*.pdf'))
        if not list_of_files:
            raise Exception("Tidak ada file PDF ditemukan")
        latest_file = max(list_of_files, key=os.path.getctime)
        new_path = os.path.join(self.download_dir, f"{new_name}.pdf")
        os.rename(latest_file, new_path)
    
    def download(self, urls, button_class="DetailProductStyle_detail-produk-button__zk419"):
        """
        Fungsi utama untuk mengunduh dan rename file
        
        Parameters:
        urls (list): Judul dan URL halaman web yang berisi button download
        button_class (str): Class name dari button yang akan diklik
        
        Returns:
        tuple: (bool, str) - (Success status, Message)
        """
        driver = self._setup_driver()

        for kode, url in urls:
            try:
                driver.get(url)
                button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CLASS_NAME, button_class))
                )
                button.click()
                
                if not self._wait_for_download():
                    raise Exception("Download timeout")
                    
                time.sleep(2)
                self._rename_latest_pdf(kode)
                
                return True, f"File berhasil didownload dan direname menjadi {kode}.pdf"
                
            except Exception as e:
                return False, f"Error: {str(e)}"
                
            finally:
                driver.quit()




# Buat instance dengan folder kustom
downloader = ProspektusDownloader(download_folder="my_downloads")

# Download file
# success, message = downloader.download(
#     urls="https://bibit.id/reksadana/RD3595/bahana-likuid-syariah-kelas-g",
#     new_filename="Prospektus_Baru"
# )

urls = [
    ['ABF Indonesia Bond Index Fund', 'https://bibit.id/reksadana/RD13'],
    # ['Mandiri Investa Cerdas', 'https://bibit.id/reksadana/RD14']  # Bisa ditambahkan jika perlu
]

success, message = downloader.download(urls)

# Cek hasil
if success:
    print(message)
else:
    print(f"Gagal: {message}")