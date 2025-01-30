from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from multiprocessing import Process, Queue
import csv

def scrape_data(period, queue):
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
        data = []

        for offset in range(start_offset, start_offset + graph_width, 5):
            actions.move_to_element_with_offset(graph_element, offset, 0).perform()
            time.sleep(0.1)

            updated_data = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.reksa-value-head-nav.ChartHead_reksa-value-head-nav__LCCdL'))
            ).text

            tanggal_navdate = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.navDate'))
            ).text

            print(f"Period {period} - Data setelah pergeseran {offset} piksel -- tanggal {tanggal_navdate} : {updated_data}")
            data.append(updated_data)

    except Exception as e:
        print(f"Gagal mengklik tombol dengan data-period={period}: {e}")
    finally:
        driver.quit()
        queue.put((period, data))  # Kirim data ke proses utama

if __name__ == "__main__":
    start_time = time.time()

    data_periods = ['ALL', '1M', '3M', 'YTD', '3Y', '5Y']
    processes = []
    queue = Queue()  # Untuk mengumpulkan data dari proses

    for period in data_periods:
        p = Process(target=scrape_data, args=(period, queue))
        processes.append(p)
        p.start()

    for p in processes:
        p.join()

    # Kumpulkan semua data dari queue
    results = {}
    while not queue.empty():
        period, data = queue.get()
        results[period] = data

    # Simpan data ke CSV
    with open('output.csv', 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        
        # Header CSV
        header = ['Pergeseran ke'] + data_periods
        writer.writerow(header)
        
        # Data CSV
        max_length = max(len(results[period]) for period in data_periods)
        for i in range(max_length):
            row = [i + 1]  # Nomor pergeseran
            for period in data_periods:
                if i < len(results[period]):
                    row.append(results[period][i])
                else:
                    row.append('')  # Kosongkan jika data tidak ada
            writer.writerow(row)

    end_time = time.time()
    durasi = end_time - start_time
    print()
    print("====")
    print(f"Total waktu eksekusi: {durasi} detik")
    print("Data telah disimpan ke output.csv")
    print("====")
    print()