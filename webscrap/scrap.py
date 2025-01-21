from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# Setup Selenium WebDriver dengan opsi nonaktifkan GPU
options = webdriver.ChromeOptions()
options.add_argument('--disable-gpu')  # Nonaktifkan GPU
service = webdriver.chrome.service.Service()  # Ganti dengan path ke ChromeDriver Anda
driver = webdriver.Chrome(service=service, options=options)

# Buka halaman web
url = 'https://bibit.id/reksadana/RD66/avrist-ada-kas-mutiara'  # Ganti dengan URL yang sesuai
driver.get(url)


# Tunggu hingga halaman sepenuhnya dimuat
time.sleep(5)  # Sesuaikan waktu tunggu sesuai kebutuhan

data_periods = ['1D', '1M', '3M', 'YTD', '1Y', '3Y', '5Y', 'ALL']


# Temukan elemen grafik (contoh: elemen dengan tag <svg> atau <canvas>)
graph_element = driver.find_element(By.TAG_NAME, 'svg')  # Gunakan By.TAG_NAME untuk mencari elemen

# Dapatkan lebar grafik
graph_width = graph_element.size['width']

# Konversi lebar grafik ke integer
graph_width = int(graph_width)

# Hitung titik awal (paling kiri)
start_offset = -graph_width // 2  # Titik paling kiri relatif terhadap titik tengah

# Buat objek ActionChains untuk mensimulasikan interaksi
actions = ActionChains(driver)

# Loop untuk menggeser kursor dari kiri ke kanan dengan langkah 5 piksel
for offset in range(start_offset, start_offset + graph_width, 5):
    # Geser kursor ke posisi tertentu
    actions.move_to_element_with_offset(graph_element, offset, 0).perform()
    time.sleep(1)  # Tunggu sebentar setelah pergeseran

    # Ambil data yang diperbarui (elemen pertama)
    updated_data = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, '.reksa-value-head-nav.ChartHead_reksa-value-head-nav__LCCdL'))
    ).text

    # Ambil tanggal dari elemen dengan class 'navDate' (elemen kedua)
    tanggal_navdate = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, '.navDate'))
    ).text

    # Cetak hasilnya
    print(f"Data setelah pergeseran {offset} piksel -- tanggal {tanggal_navdate} : {updated_data}")
    
# Tutup browser
driver.quit()