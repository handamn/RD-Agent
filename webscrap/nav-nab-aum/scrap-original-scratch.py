from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

start_time = time.time()

options = webdriver.ChromeOptions()
options.add_argument('--disable-gpu')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--no-sandbox')
options.add_argument('--headless')  # Run in background
options.add_argument('--disable-extensions')
options.add_argument('--disable-software-rasterizer')
service = webdriver.chrome.service.Service()
driver = webdriver.Chrome(service=service, options=options)

url = 'https://bibit.id/reksadana/RD66/avrist-ada-kas-mutiara'
driver.get(url)

data_periods = ['1M']

for period in data_periods:
    try:
        button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, f'button[data-period="{period}"]'))
        )

        button_text = button.find_element(By.CSS_SELECTOR, '.reksa-border-button-period-box').text
        print(f"Tombol yang diklik memiliki teks: {button_text}")
        
        button.click()
        print(f"Tombol {button_text} berhasil diklik!")

        time.sleep(1)  # Kurangi waktu tunggu

        graph_element = driver.find_element(By.TAG_NAME, 'svg')
        graph_width = graph_element.size['width']
        graph_width = int(graph_width)
        start_offset = -graph_width // 2

        actions = ActionChains(driver)
        hitung = 1

        for offset in range(start_offset, start_offset + graph_width, 5):
            print(hitung)
            
            actions.move_to_element_with_offset(graph_element, offset, 0).perform()
            time.sleep(0.1)  # Kurangi waktu tunggu

            updated_data = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.reksa-value-head-nav.ChartHead_reksa-value-head-nav__LCCdL'))
            ).text

            tanggal_navdate = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.navDate'))
            ).text

            print(f"Data setelah pergeseran {offset} piksel -- tanggal {tanggal_navdate} : {updated_data}")
            
            hitung += 1

    except Exception as e:
        print(f"Gagal mengklik tombol dengan data-period={period}: {e}")

driver.quit()

end_time = time.time()

durasi = end_time - start_time
print()
print("====")
print(durasi)
print("====")
print()