from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# Setup Selenium WebDriver dengan opsi optimasi
options = webdriver.ChromeOptions()
options.add_argument('--disable-gpu')  # Nonaktifkan GPU
options.add_argument('--disable-images')  # Nonaktifkan gambar
options.add_argument('--headless')  # Jalankan browser tanpa antarmuka grafis
service = webdriver.chrome.service.Service()  # Ganti dengan path ke ChromeDriver Anda
driver = webdriver.Chrome(service=service, options=options)

# Buka halaman web
url = 'https://bibit.id/reksadana/RD66/avrist-ada-kas-mutiara'  # Ganti dengan URL yang sesuai
driver.get(url)

# Tunggu hingga tombol muncul dan bisa diklik
try:
    # Menunggu tombol dengan data-period="3Y" muncul
    button_3Y = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-period="3Y"]'))
    )
    
    # Klik tombol
    button_3Y.click()
    print("Tombol 3Y berhasil diklik!")
    
    # Tunggu sebentar untuk memastikan data diperbarui
    time.sleep(2)
    
    # Ambil data yang muncul setelah tombol diklik
    try:
        data_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '.reksa-value-head-nav.ChartHead_reksa-value-head-nav__LCCdL'))
        )
        print("Data setelah klik tombol 3Y:", data_element.text)
    except Exception as e:
        print(f"Gagal mengambil data setelah klik tombol: {e}")
    
except Exception as e:
    print(f"Gagal mengklik tombol 3Y: {e}")

# Tutup browser
driver.quit()