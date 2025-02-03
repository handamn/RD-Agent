from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time

def scrape_chart_data(url):
    # Konfigurasi Chrome Options
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Inisialisasi WebDriver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        # Buka halaman web
        driver.get(url)
        time.sleep(50)  # Tunggu halaman dimuat
        
        # Temukan elemen grafik (sesuaikan dengan selector yang tepat)
        chart = driver.find_element(By.CSS_SELECTOR, "selector-grafik-anda")
        
        # Gerakkan kursor ke tengah grafik
        actions = ActionChains(driver)
        actions.move_to_element(chart).perform()
        time.sleep(2)  # Tunggu tooltip muncul
        
        # Ambil data tooltip
        tooltip = driver.find_element(By.CLASS_NAME, "hu-tooltip")
        
        # Ekstrak nilai-nilai spesifik
        values = tooltip.find_elements(By.CLASS_NAME, "hu-tooltip-value")
        
        # Simpan data dalam dictionary
        chart_data = {
            "datetime": values[0].text,
            "close": values[1].text,
            "open": values[2].text,
            "high": values[3].text,
            "low": values[4].text,
            "volume": values[5].text
        }
        
        return chart_data
    
    except Exception as e:
        print(f"Terjadi kesalahan: {e}")
        return None
    
    finally:
        driver.quit()

# Contoh penggunaan
url = "https://id.investing.com/indices/idx-composite"
data = scrape_chart_data(url)
if data:
    print(data)