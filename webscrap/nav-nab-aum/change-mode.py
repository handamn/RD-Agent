from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
import time

# Inisialisasi WebDriver (misalnya, Chrome)
driver = webdriver.Chrome()
# Buka halaman web
driver.get('https://bibit.id/reksadana/RD1721/bahana-mes-syariah-fund-kelas-g')

# Tunggu hingga halaman selesai dimuat
time.sleep(5)  # Anda bisa mengganti ini dengan WebDriverWait untuk lebih presisi

# Temukan elemen "AUM" menggunakan selector CSS atau XPath
aum_element = driver.find_element(By.CSS_SELECTOR, '.navigator .selected-menu')

# Klik elemen "AUM"
aum_element.click()

# Tunggu beberapa detik untuk memastikan tindakan selesai
time.sleep(3)

# Lakukan scraping setelah mengklik
# Contoh: Ambil konten dari halaman
# content = driver.page_source
# print(content)

# Tutup browser
driver.quit()