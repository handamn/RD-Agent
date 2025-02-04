import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

# Variable
url = "https://finance.yahoo.com/quote/%5EJKSE/history/"  # Ganti dengan URL yang sesuai
pilih_tahun = "5D"  # Ganti dengan tahun yang ingin dipilih

# Inisialisasi WebDriver (Pastikan Anda sudah menginstall driver yang sesuai, misalnya ChromeDriver)

chrome_options = Options()
chrome_options.add_argument("--log-level=3")  # Nonaktifkan logging
chrome_options.add_argument("--ignore-certificate-errors")  # Abaikan error SSL
chrome_options.add_argument("--disable-extensions")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--headless")  # Jika Anda tidak perlu melihat browser
driver = webdriver.Chrome(service=Service(), options=chrome_options)

try:
    # 1. Load web
    driver.get(url)
    time.sleep(5)  # Tunggu beberapa detik untuk memastikan halaman terload sepenuhnya

    # 2. Klik button dengan class tertentu
    button = driver.find_element(By.CSS_SELECTOR, ".tertiary-btn.fin-size-small.menuBtn.rounded.yf-15mk0m")
    button.click()
    time.sleep(2)  # Tunggu dialog box terbuka

    # 3. Tunggu dialog box terbuka
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".dialog-container.menu-surface-dialog.modal.yf-9a5vow"))
    )

    # 4. Ambil value dari button yang ada di dalam dialog box
    buttons = driver.find_elements(By.CSS_SELECTOR, ".quickpicks.yf-1th5n0r .tertiary-btn.fin-size-small.tw-w-full.tw-justify-center.rounded.yf-15mk0m")
    values = [button.text for button in buttons]

    # 5. Cocokkan value dengan input variable pilih_tahun
    if pilih_tahun in values:
        # 6. Klik button yang sesuai
        index = values.index(pilih_tahun)
        buttons[index].click()
        time.sleep(2)  # Tunggu proses selesai

        # 7. Ambil data dari table
        table = driver.find_element(By.CSS_SELECTOR, ".table.yf-1jecxey.noDl")
        rows = table.find_elements(By.TAG_NAME, "tr")
        data = []
        for row in rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            cols = [col.text for col in cols]
            data.append(cols)

        # 8. Simpan data ke CSV
        df = pd.DataFrame(data)
        df.to_csv("output.csv", index=False)
        print("Data telah disimpan ke output.csv")

        # Print data
        print(df)

    else:
        print(f"Tahun {pilih_tahun} tidak ditemukan.")

finally:
    # Tutup browser
    driver.quit()