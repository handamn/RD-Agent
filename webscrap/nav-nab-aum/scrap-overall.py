from concurrent.futures import ThreadPoolExecutor, as_completed
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import csv
import os
from datetime import datetime

# =========================== CONFIGURATIONS ===========================
DEBUG_MODE = False  # Ubah ke True untuk melihat log setiap titik kursor
LOG_FILE = "scraping_log.log"  # File log untuk menyimpan hasil log

# =========================== Logging Function ===========================

def log_info(message, status="INFO"):
    """Write logs to a file with a consistent format"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] [{status}] {message}\n"
    
    # Simpan log ke file
    with open(LOG_FILE, "a", encoding="utf-8") as log_file:
        log_file.write(log_message)

# =========================== Utility Functions ===========================

def convert_to_number(value):
    """Convert formatted numbers to float"""
    value = value.replace(',', '')
    if 'K' in value:
        return float(value.replace('K', '')) * 1_000
    elif 'M' in value:
        return float(value.replace('M', '')) * 1_000_000
    elif 'B' in value:
        return float(value.replace('B', '')) * 1_000_000_000
    elif 'T' in value:
        return float(value.replace('T', '')) * 1_000_000_000_000
    else:
        return float(value)

def parse_tanggal(tanggal_str):
    """Convert Indonesian date format (e.g., '31 Jan 25') to datetime object"""
    bulan_map = {
        'Jan': 'January', 'Feb': 'February', 'Mar': 'March',
        'Apr': 'April', 'Mei': 'May', 'Jun': 'June',
        'Jul': 'July', 'Agt': 'August', 'Sep': 'September',
        'Okt': 'October', 'Nov': 'November', 'Des': 'December'
    }

    parts = tanggal_str.split()
    if len(parts) != 3:
        raise ValueError(f"Format tanggal tidak valid: {tanggal_str}")

    hari = parts[0]
    bulan_singkat = parts[1]
    tahun = "20" + parts[2]

    if bulan_singkat not in bulan_map:
        raise ValueError(f"Bulan tidak valid: {bulan_singkat}")

    bulan_en = bulan_map[bulan_singkat]
    tanggal_full = f"{hari} {bulan_en} {tahun}"

    return datetime.strptime(tanggal_full, "%d %B %Y")

# =========================== Scraping Function ===========================

def scrape_mode_data(url, period, mode, pixel):
    """Scrape data for a specific mode and period"""
    start_time = time.time()
    period_data = []

    try:
        log_info(f"Memulai scraping {period} ({mode}) untuk {url}...")

        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        driver = webdriver.Chrome(options=options)
        wait = WebDriverWait(driver, 10)

        driver.get(url)
        log_info(f"Berhasil membuka URL {url}")

        # Klik tombol periode
        button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, f'button[data-period="{period}"]')))
        button.click()
        log_info(f"Berhasil memilih periode {period}")
        time.sleep(2)

        # Ambil elemen grafik
        graph_element = wait.until(EC.presence_of_element_located((By.TAG_NAME, 'svg')))
        graph_width = int(graph_element.size['width'])
        start_offset = -graph_width // 2

        actions = ActionChains(driver)

        for offset in range(start_offset, start_offset + graph_width, pixel):
            actions.move_to_element_with_offset(graph_element, offset, 0).perform()
            time.sleep(0.1)

            updated_data = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.reksa-value-head-nav'))).text
            tanggal_navdate = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.navDate'))).text

            period_data.append({'tanggal': tanggal_navdate, 'data': updated_data})

            if DEBUG_MODE:
                log_info(f"Kursor pada offset {offset} | Tanggal: {tanggal_navdate} | Data: {updated_data}", "DEBUG")

        log_info(f"Scraping {period} ({mode}) selesai, total data: {len(period_data)}")

    except Exception as e:
        log_info(f"Scraping gagal untuk {period} ({mode}): {e}", "ERROR")

    finally:
        driver.quit()

    duration = time.time() - start_time
    log_info(f"Scraping {period} ({mode}) selesai dalam {duration:.2f} detik.")
    return period_data


# =========================== Parallel Scraping with Threads ===========================

def scrape_all_periods(url, mode, pixel, data_periods):
    """Run scraping in parallel for all periods using threads"""
    max_workers = min(len(data_periods), 4)  # Maksimal 4 thread agar tidak overload
    log_info(f"Scraping {mode} dimulai dengan {max_workers} thread...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(scrape_mode_data, url, period, mode, pixel): period for period in data_periods}
        results = []

        for future in as_completed(futures):
            try:
                result = future.result()
                results.extend(result)
            except Exception as e:
                log_info(f"Scraping error: {e}", "ERROR")

        return results

# =========================== Main Function ===========================

def main():
    urls = [
        ['ABF Indonesia Bond Index Fund', 'https://bibit.id/reksadana/RD13'],
        # ['Mandiri Investa Cerdas', 'https://bibit.id/reksadana/RD14']  # Contoh URL tambahan
    ]
    data_periods = ['3Y', '5Y']
    pixel = 200

    total_start_time = time.time()
    log_info("===== Mulai scraping seluruh data =====")

    for kode, url in urls:
        url_start_time = time.time()
        log_info(f"Mulai scraping untuk {kode}")

        mode1_data = scrape_all_periods(url, "Default", pixel, data_periods)
        mode2_data = scrape_all_periods(url, "AUM", pixel, data_periods)

        url_duration = time.time() - url_start_time
        log_info(f"Scraping {kode} selesai dalam {url_duration:.2f} detik.")

    total_duration = time.time() - total_start_time
    log_info(f"===== Semua scraping selesai dalam {total_duration:.2f} detik =====")

if __name__ == "__main__":
    main()