from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
import time

# Ganti dengan path ke chromedriver Anda
# chrome_driver_path = '/path/to/chromedriver'

# Inisialisasi WebDriver
service = Service()
driver = webdriver.Chrome(service=service)

# Buka website yang dituju
driver.get('https://bibit.id/reksadana/RD1721/bahana-mes-syariah-fund-kelas-g')  # Ganti dengan URL website Anda

# Tunggu beberapa detik untuk memastikan halaman sudah sepenuhnya dimuat
time.sleep(5)

# Temukan elemen dengan class 'selected-menu' dan klik
try:
    aum_button = driver.find_element(By.CLASS_NAME, 'selected-menu')
    aum_button.click()
    print("Berhasil mengklik AUM")
except Exception as e:
    print(f"Gagal menemukan atau mengklik AUM: {e}")

# Tunggu beberapa detik untuk melihat hasilnya
time.sleep(5)

# Tutup browser
driver.quit()