from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os

def setup_chrome_driver():
    # Konfigurasi Chrome options untuk mengatur lokasi download
    chrome_options = webdriver.ChromeOptions()
    
    # Tentukan direktori download (ganti dengan path yang Anda inginkan)
    download_dir = os.path.join(os.getcwd(), "downloads")
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
    
    # Atur preferensi download
    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True  # PDF akan langsung diunduh, bukan dibuka di browser
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    return webdriver.Chrome(options=chrome_options)

def download_pdf():
    driver = setup_chrome_driver()
    try:
        # Buka halaman web
        driver.get("https://bibit.id/reksadana/RD3595/bahana-likuid-syariah-kelas-g")
        
        # Tunggu sampai button muncul dan bisa diklik
        button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CLASS_NAME, "DetailProductStyle_detail-produk-button__zk419"))
        )
        
        # Klik button
        button.click()
        
        # Tunggu beberapa saat untuk memastikan proses download dimulai
        time.sleep(5)  # Waktu bisa disesuaikan
        
    except Exception as e:
        print(f"Terjadi error: {str(e)}")
    finally:
        # Tutup browser
        driver.quit()

if __name__ == "__main__":
    download_pdf()