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
    # Menunggu tombol dengan class tertentu muncul
    button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, '.reksa-border-button-period-box'))
    )
    
    # Ambil nilai (teks) dari tombol sebelum diklik
    button_value = button.text
    print(f"Nilai tombol sebelum diklik: {button_value}")
    
    # Klik tombol
    button.click()
    print("Tombol berhasil diklik!")
    
    # Tunggu sebentar untuk melihat efek klik (opsional)
    time.sleep(2)
    
    # Ambil nilai (teks) dari tombol setelah diklik (jika berubah)
    button_value_after_click = button.text
    print(f"Nilai tombol setelah diklik: {button_value_after_click}")
    
except Exception as e:
    print(f"Gagal mengklik tombol atau mengambil nilai: {e}")

# Tutup browser
driver.quit()