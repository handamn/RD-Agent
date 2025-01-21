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
    
    # Ambil nilai dari elemen <div> di dalam tombol
    button_text = button_3Y.find_element(By.CSS_SELECTOR, '.reksa-border-button-period-box').text
    print(f"Tombol yang diklik memiliki teks: {button_text}")
    
    # Klik tombol
    button_3Y.click()
    print(f"Tombol {button_text} berhasil diklik!")
    
    # Tunggu sebentar untuk memastikan data diperbarui
    time.sleep(2)
    
except Exception as e:
    print(f"Gagal mengklik tombol: {e}")

# Tutup browser
driver.quit()