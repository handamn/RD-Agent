from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
import random

# Konfigurasi Chrome Options
chrome_options = Options()
chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_experimental_option("useAutomationExtension", False)

# Inisialisasi WebDriver
driver = webdriver.Chrome(options=chrome_options)
driver.get('https://id.investing.com/indices/idx-composite')

# Tunggu hingga halaman selesai memuat
time.sleep(10)  # Sesuaikan waktu tunggu jika diperlukan

# Temukan elemen grafik (ganti dengan selector yang sesuai)
chart_element = driver.find_element(By.CSS_SELECTOR, 'div.chart-container')  # Ganti dengan selector yang benar

# Dapatkan ukuran dan posisi grafik
chart_location = chart_element.location
chart_size = chart_element.size

# Hitung posisi tengah grafik
center_x = chart_location['x'] + chart_size['width'] / 2
center_y = chart_location['y'] + chart_size['height'] / 2

# Arahkan kursor ke tengah grafik
actions = ActionChains(driver)
actions.move_to_element_with_offset(chart_element, chart_size['width'] / 2, chart_size['height'] / 2).perform()

# Tunggu hingga tabel muncul
WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'table.hu-tooltip')))

# Ambil data dari tabel
tooltip_table = driver.find_element(By.CSS_SELECTOR, 'table.hu-tooltip')
rows = tooltip_table.find_elements(By.TAG_NAME, 'tr')

data = {}
for row in rows:
    cells = row.find_elements(By.TAG_NAME, 'td')
    if len(cells) == 2:
        key = cells[0].text
        value = cells[1].text
        data[key] = value

# Cetak data yang diambil
print(data)

# Tutup browser
driver.quit()