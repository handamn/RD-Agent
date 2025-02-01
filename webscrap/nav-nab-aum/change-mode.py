from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# Inisialisasi WebDriver
driver = webdriver.Chrome()

# Buka Halaman Web
driver.get("https://bibit.id/reksadana/RD1721/bahana-mes-syariah-fund-kelas-g")

# Tunggu hingga halaman termuat
time.sleep(3)

# Pastikan Elemen "AUM" Muncul Sebelum Diklik
try:
    wait = WebDriverWait(driver, 10)  # Tunggu maksimal 10 detik
    aum_button = wait.until(
        EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'menu') and contains(text(), 'AUM')]"))
    )
    print("Elemen AUM ditemukan dan bisa diklik.")

    # Klik dengan metode normal
    try:
        aum_button.click()
        print("Klik berhasil dengan metode .click()")
    except Exception as e:
        print(f"Gagal dengan .click(): {e}")

    # Tunggu beberapa detik agar halaman berubah setelah klik
    time.sleep(10)
finally:
    # Tutup Browser
    driver.quit()
