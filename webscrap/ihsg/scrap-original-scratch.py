from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# Ganti dengan path ke WebDriver Anda
# driver_path = 'path/to/chromedriver'

# Ganti dengan URL target
url = 'https://id.investing.com/indices/idx-composite'

# Inisialisasi WebDriver
driver = webdriver.Chrome()
driver.get(url)

# Tunggu hingga halaman selesai memuat
time.sleep(10)  # Sesuaikan waktu tunggu jika diperlukan

# Temukan elemen grafik (ganti dengan selector yang sesuai)
chart_element = driver.find_element(By.CSS_SELECTOR, 'selector_grafik')

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
time.sleep(2)  # Sesuaikan waktu tunggu jika diperlukan

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