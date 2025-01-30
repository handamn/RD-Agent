from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from multiprocessing import Process, Manager

def scrape_data(period, result_list):
    options = webdriver.ChromeOptions()
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--no-sandbox')
    options.add_argument('--headless')  # Run in background
    service = webdriver.chrome.service.Service()
    driver = webdriver.Chrome(service=service, options=options)

    url = 'https://bibit.id/reksadana/RD66/avrist-ada-kas-mutiara'
    driver.get(url)

    try:
        button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, f'button[data-period="{period}"]'))
        )

        button_text = button.find_element(By.CSS_SELECTOR, '.reksa-border-button-period-box').text
        print(f"Tombol yang diklik memiliki teks: {button_text}")
        
        button.click()
        print(f"Tombol {button_text} berhasil diklik!")

        time.sleep(2)

        graph_element = driver.find_element(By.TAG_NAME, 'svg')
        graph_width = graph_element.size['width']
        graph_width = int(graph_width)
        start_offset = -graph_width // 2

        actions = ActionChains(driver)
        hitung = 1

        period_data = []  # List untuk menyimpan data per periode

        for offset in range(start_offset, start_offset + graph_width, 5):
            print(f"Period {period} - Iterasi {hitung}")
            
            actions.move_to_element_with_offset(graph_element, offset, 0).perform()
            time.sleep(0.1)

            updated_data = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.reksa-value-head-nav.ChartHead_reksa-value-head-nav__LCCdL'))
            ).text

            tanggal_navdate = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.navDate'))
            ).text

            print(f"Period {period} - Data setelah pergeseran {offset} piksel -- tanggal {tanggal_navdate} : {updated_data}")
            
            # Simpan data ke dalam list period_data
            period_data.append({
                'period': period,
                'offset': offset,
                'tanggal': tanggal_navdate,
                'data': updated_data
            })
            
            hitung += 1

        # Simpan hasil periode ke dalam result_list
        result_list.append(period_data)

    except Exception as e:
        print(f"Gagal mengklik tombol dengan data-period={period}: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    start_time = time.time()

    data_periods = ['ALL', '1M', '3M', 'YTD', '3Y', '5Y']
    processes = []
    manager = Manager()
    result_list = manager.list()  # List shared antar proses

    for period in data_periods:
        p = Process(target=scrape_data, args=(period, result_list))
        processes.append(p)
        p.start()

    for p in processes:
        p.join()

    # Cetak hasil di akhir
    # print("\nHasil akhir:")
    # for period_data in result_list:
    #     print(f"\nData untuk periode {period_data[0]['period']}:")
    #     for data in period_data:
    #         print(f"Offset: {data['offset']}, Tanggal: {data['tanggal']}, Data: {data['data']}")

    print()
    print(type(result_list))
    print()

    end_time = time.time()
    durasi = end_time - start_time
    print()
    print("====")
    print(f"Total waktu eksekusi: {durasi} detik")
    print("====")
    print()