from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import csv
import os
from multiprocessing import Process, Manager
from tqdm import tqdm
from itertools import cycle

# Simbol animasi untuk menunjukkan progres setiap proses
symbols = cycle(['⣾', '⣷', '⣯', '⣟', '⡿', '⢿', '⣻', '⣽'])

# Direktori untuk menyimpan log
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)

def write_log(log_file, message):
    with open(log_file, 'a', encoding='utf-8') as log:
        log.write(f"{message}\n")

def parse_tanggal(tanggal_str):
    bulan_map = {'Jan': 'January', 'Feb': 'February', 'Mar': 'March', 'Apr': 'April',
                 'Mei': 'May', 'Jun': 'June', 'Jul': 'July', 'Agt': 'August',
                 'Sep': 'September', 'Okt': 'October', 'Nov': 'November', 'Des': 'December'}
    
    parts = tanggal_str.split()
    hari, bulan_singkat, tahun = parts[0], parts[1], parts[2]
    bulan_en = bulan_map.get(bulan_singkat, None)
    if not bulan_en:
        raise ValueError(f"Bulan tidak valid: {bulan_singkat}")
    tanggal_full = f"{hari} {bulan_en} 20{tahun}"
    return datetime.strptime(tanggal_full, "%d %B %Y")

def convert_to_number(value):
    if 'K' in value:
        return float(value.replace('K', '')) * 1_000
    elif 'M' in value:
        return float(value.replace('M', '')) * 1_000_000
    return float(value.replace(',', ''))

def scrape_data(url, period, result_list, pixel, log_file, progress_bar):
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    service = webdriver.chrome.service.Service()
    driver = webdriver.Chrome(service=service, options=options)
    driver.get(url)
    try:
        button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, f'button[data-period="{period}"]'))
        )
        button.click()
        time.sleep(2)
        graph_element = driver.find_element(By.TAG_NAME, 'svg')
        graph_width = graph_element.size['width']
        start_offset = -graph_width // 2
        actions = ActionChains(driver)
        period_data = []
        for offset in range(start_offset, start_offset + graph_width, pixel):
            actions.move_to_element_with_offset(graph_element, offset, 0).perform()
            time.sleep(0.1)
            updated_data = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.reksa-value-head-nav'))
            ).text
            tanggal_navdate = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.navDate'))
            ).text
            period_data.append({'tanggal': tanggal_navdate, 'data': updated_data})
            progress_bar.set_description(f"Scraping {period} {next(symbols)}")
            progress_bar.update(1)
        result_list.append(period_data)
    except Exception as e:
        write_log(log_file, f"[ERROR] Gagal scraping {period}: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    start_time = time.time()
    urls = [['ABF Indonesia Bond Index Fund', 'https://bibit.id/reksadana/RD13'],
            ['Avrist Ada Kas Mutiara', 'https://bibit.id/reksadana/RD66']]
    pixel = 5
    data_periods = ['ALL', '1M', '3M', 'YTD', '3Y', '5Y']
    for url_data in tqdm(urls, desc="Scraping Progress", unit="URL"):
        kode, url = url_data
        log_file = os.path.join(log_dir, f"{kode}.log")
        processes = []
        manager = Manager()
        result_list = manager.list()
        progress_bar = tqdm(total=len(data_periods), desc=f"{kode}", position=1, leave=False)
        for period in data_periods:
            p = Process(target=scrape_data, args=(url, period, result_list, pixel, log_file, progress_bar))
            processes.append(p)
            p.start()
        for p in processes:
            p.join()
        combined_data = sorted(set((parse_tanggal(d['tanggal']), convert_to_number(d['data']))
                                   for period_data in result_list for d in period_data))
        csv_file = f"database/{kode}.csv"
        os.makedirs(os.path.dirname(csv_file), exist_ok=True)
        with open(csv_file, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['tanggal', 'data'])
            writer.writerows([(d.strftime('%Y-%m-%d'), data) for d, data in combined_data])
        write_log(log_file, f"[INFO] Data tersimpan di {csv_file}")
        progress_bar.close()
    print(f"Total waktu eksekusi: {time.time() - start_time:.2f} detik")
