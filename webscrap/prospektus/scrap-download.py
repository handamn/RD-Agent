from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time

# Konfigurasi ChromeOptions
options = Options()
options.add_argument("--headless")  # Jika Anda ingin menjalankan browser dalam mode headless
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

# Atur preferensi untuk mengunduh file PDF secara otomatis
prefs = {
    "download.default_directory": "webscrap/prospektus/database",  # Ganti dengan direktori tujuan unduhan
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
    "plugins.always_open_pdf_externally": True
}
options.add_experimental_option("prefs", prefs)

# Inisialisasi WebDriver
service = webdriver.chrome.service.Service()
driver = webdriver.Chrome(service=service, options=options)

# Buka link web
driver.get("https://bibit.id/reksadana/RD3595/bahana-likuid-syariah-kelas-g")

# Cari tombol unduh berdasarkan class dan klik
try:
    download_button = driver.find_element(By.CLASS_NAME, "DetailProductStyle_detail-produk-button__zk419")
    download_button.click()
    print("Tombol berhasil diklik!")
except Exception as e:
    print(f"Gagal menemukan tombol: {e}")

# Tunggu tab baru terbuka
time.sleep(5)  # Beri waktu untuk tab baru terbuka

# Beralih ke tab baru
driver.switch_to.window(driver.window_handles[1])

# Dapatkan URL file PDF
pdf_url = driver.current_url
print(f"URL PDF: {pdf_url}")

# Tutup tab PDF
driver.close()

# Beralih kembali ke tab utama
driver.switch_to.window(driver.window_handles[0])

# Tutup browser
driver.quit()

# Unduh file PDF menggunakan requests
import requests
response = requests.get(pdf_url)
with open("webscrap/prospektus/database/file.pdf", "wb") as f:
    f.write(response.content)
print("File PDF berhasil diunduh!")