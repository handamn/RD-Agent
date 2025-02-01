from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
import glob

def setup_chrome_driver():
    chrome_options = webdriver.ChromeOptions()
    
    # Tambahkan opsi headless
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    
    # Tentukan direktori download
    download_dir = os.path.join(os.getcwd(), "downloads")
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
    
    # Atur preferensi download
    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    return webdriver.Chrome(options=chrome_options), download_dir

def wait_for_download(download_dir, timeout=60):
    """Menunggu sampai file selesai didownload"""
    seconds = 0
    dl_wait = True
    while dl_wait and seconds < timeout:
        time.sleep(1)
        dl_wait = False
        files = os.listdir(download_dir)
        for fname in files:
            if fname.endswith('.crdownload'):
                dl_wait = True
        seconds += 1
    return seconds < timeout

def rename_latest_pdf(download_dir, new_name):
    """Rename file PDF terakhir yang didownload"""
    # Cari file PDF terbaru di folder download
    list_of_files = glob.glob(os.path.join(download_dir, '*.pdf'))
    if not list_of_files:
        print("Tidak ada file PDF ditemukan")
        return False
        
    latest_file = max(list_of_files, key=os.path.getctime)
    
    # Buat path untuk nama file baru
    new_path = os.path.join(download_dir, f"{new_name}.pdf")
    
    # Rename file
    try:
        os.rename(latest_file, new_path)
        print(f"File berhasil direname menjadi: {new_name}.pdf")
        return True
    except Exception as e:
        print(f"Error saat rename file: {str(e)}")
        return False

def download_pdf(new_filename="Prospektus_Bahana_Likuid_Syariah"):
    driver, download_dir = setup_chrome_driver()
    try:
        print("Membuka halaman web...")
        driver.get("https://bibit.id/reksadana/RD83/avrist-prime-bond-fund")
        
        print("Menunggu button muncul...")
        button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CLASS_NAME, "DetailProductStyle_detail-produk-button__zk419"))
        )
        
        print("Mengklik button download...")
        button.click()
        
        # Tunggu sampai file selesai didownload
        print("Menunggu download selesai...")
        if wait_for_download(download_dir):
            print("Download selesai")
            # Tunggu sebentar untuk memastikan file sudah benar-benar tersimpan
            time.sleep(2)
            # Rename file
            rename_latest_pdf(download_dir, new_filename)
        else:
            print("Download timeout atau gagal")
        
    except Exception as e:
        print(f"Terjadi error: {str(e)}")
    finally:
        driver.quit()

if __name__ == "__main__":
    # Anda bisa mengubah nama file sesuai keinginan
    download_pdf("ganteng")