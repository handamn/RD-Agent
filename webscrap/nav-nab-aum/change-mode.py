from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait  # ← Perbaikan di sini
from selenium.webdriver.support import expected_conditions as EC
import time


# Inisialisasi WebDriver (pastikan path chromedriver sudah benar)
driver = webdriver.Chrome()

# 1️⃣ **Buka Halaman Web**
driver.get("https://bibit.id/reksadana/RD1721/bahana-mes-syariah-fund-kelas-g")

# Tunggu hingga halaman termuat
time.sleep(3)

# 2️⃣ **Pastikan Elemen "AUM" Muncul Sebelum Diklik**
try:
    wait = WebDriverWait(driver, 10)  # Tunggu maksimal 10 detik
    aum_button = wait.until(
        EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'menu') and text()='AUM (Assets Under Management)']"))
    )
    print("Elemen AUM ditemukan dan bisa diklik.")

    # 3️⃣ **Gunakan Metode Klik Pertama (Normal .click())**
    try:
        aum_button.click()
        print("Klik berhasil dengan metode .click()")
    except Exception as e:
        print(f"Gagal dengan .click(): {e}")

    # Tunggu beberapa detik agar halaman berubah setelah klik
    time.sleep(10)
finally:
    # 7️⃣ **Tutup Browser**
    driver.quit()
