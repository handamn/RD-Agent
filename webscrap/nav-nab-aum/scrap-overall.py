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

def print_header(text, char="="):
    """Print a header with consistent formatting"""
    line = char * 80
    print(f"\n{line}")
    print(f"{text.center(80)}")
    print(f"{line}\n")

def print_subheader(text, char="-"):
    """Print a subheader with consistent formatting"""
    print(f"\n{char * 40} {text} {char * 40}\n")

def print_progress(mode, period, iteration, date, value):
    """Print progress with consistent formatting"""
    print(f"Mode: {mode:<6} | Period: {period:<4} | Iteration: {iteration:<4} | Date: {date:<10} | Value: {value}")

def convert_to_number(value):
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
    bulan_map_id = {
        'Jan': 'Januari', 'Feb': 'Februari', 'Mar': 'Maret',
        'Apr': 'April', 'Mei': 'Mei', 'Jun': 'Juni',
        'Jul': 'Juli', 'Agt': 'Agustus', 'Sep': 'September',
        'Okt': 'Oktober', 'Nov': 'November', 'Des': 'Desember'
    }
    
    bulan_map_en = {
        'Januari': 'January', 'Februari': 'February', 'Maret': 'March',
        'April': 'April', 'Mei': 'May', 'Juni': 'June',
        'Juli': 'July', 'Agustus': 'August', 'September': 'September',
        'Oktober': 'October', 'November': 'November', 'Desember': 'December'
    }

    parts = tanggal_str.split()
    if len(parts) != 3:
        raise ValueError(f"Format tanggal tidak valid: {tanggal_str}")

    hari = parts[0]
    bulan_singkat = parts[1]
    tahun = parts[2]

    if bulan_singkat not in bulan_map_id:
        raise ValueError(f"Bulan tidak valid: {bulan_singkat}")
    bulan_id = bulan_map_id[bulan_singkat]

    if bulan_id not in bulan_map_en:
        raise ValueError(f"Bulan tidak valid: {bulan_id}")
    bulan_en = bulan_map_en[bulan_id]

    tanggal_full = f"{hari} {bulan_en} 20{tahun}"
    return datetime.strptime(tanggal_full, "%d %B %Y")

def switch_to_aum_mode(driver, wait):
    """Switch to AUM mode"""
    try:
        aum_button = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'menu') and contains(text(), 'AUM')]"))
        )
        print("[INFO] Switching to AUM mode...")
        aum_button.click()
        time.sleep(3)  # Wait for mode switch
        return True
    except Exception as e:
        print(f"[ERROR] Failed to switch to AUM mode: {e}")
        return False

def scrape_mode_data(url, period, mode, pixel, max_retries=3):
    """Scrape data for a specific mode and period"""
    retry_count = 0
    success = False
    period_data = []

    while retry_count < max_retries and not success:
        try:
            options = webdriver.ChromeOptions()
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--no-sandbox')
            options.add_argument('--headless')
            service = webdriver.chrome.service.Service()
            driver = webdriver.Chrome(service=service, options=options)

            driver.get(url)
            wait = WebDriverWait(driver, 10)

            # Switch to AUM mode if needed
            if mode == "AUM":
                if not switch_to_aum_mode(driver, wait):
                    raise Exception("Failed to switch to AUM mode")

            # Click period button
            button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, f'button[data-period="{period}"]')))
            print(f"[INFO] Starting scraping for period {period} in {mode} mode")
            button.click()
            time.sleep(2)

            # Get graph element
            graph_element = wait.until(EC.presence_of_element_located((By.TAG_NAME, 'svg')))
            graph_width = int(graph_element.size['width'])
            start_offset = -graph_width // 2

            actions = ActionChains(driver)

            print_subheader(f"Collecting data for {mode} mode, period {period}")

            for offset in range(start_offset, start_offset + graph_width, pixel):
                actions.move_to_element_with_offset(graph_element, offset, 0).perform()
                time.sleep(0.1)

                updated_data = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '.reksa-value-head-nav.ChartHead_reksa-value-head-nav__LCCdL'))
                ).text

                tanggal_navdate = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '.navDate'))
                ).text

                print_progress(mode, period, offset // pixel + 1, tanggal_navdate, updated_data)

                period_data.append({
                    'tanggal': tanggal_navdate,
                    'data': updated_data
                })

            if period_data:
                success = True
            else:
                raise Exception(f"No data found for period {period} in {mode} mode")

        except Exception as e:
            retry_count += 1
            print(f"[WARNING] Failed to get data for period {period} in {mode} mode. Attempt {retry_count}/{max_retries}. Error: {e}")

            if retry_count < max_retries:
                time.sleep(3)
                try:
                    driver.refresh()
                    time.sleep(2)
                except:
                    pass

        finally:
            try:
                driver.quit()
            except:
                pass

    if not success:
        print(f"[ERROR] Failed to get data for period {period} in {mode} mode after {max_retries} attempts.")

    return period_data

def process_and_save_data(kode, mode1_data, mode2_data):
    """Process and save data from both modes"""
    processed_data = {}
    
    # Process mode1 data
    for entry in mode1_data:
        try:
            tanggal_obj = parse_tanggal(entry['tanggal'])
            tanggal_str = tanggal_obj.strftime("%Y-%m-%d")
            data_str = entry['data'].replace('Rp', '').strip()
            data_number = convert_to_number(data_str)
            
            if tanggal_str not in processed_data:
                processed_data[tanggal_str] = {'mode1': 'NA', 'mode2': 'NA'}  # Default NA
            processed_data[tanggal_str]['mode1'] = data_number
        except ValueError as e:
            print(f"[ERROR] Failed to convert mode1 data: {data_str}")

    # Process mode2 data
    for entry in mode2_data:
        try:
            tanggal_obj = parse_tanggal(entry['tanggal'])
            tanggal_str = tanggal_obj.strftime("%Y-%m-%d")
            data_str = entry['data'].replace('Rp', '').strip()
            data_number = convert_to_number(data_str)
            
            if tanggal_str not in processed_data:
                processed_data[tanggal_str] = {'mode1': 'NA', 'mode2': 'NA'}  # Default NA
            processed_data[tanggal_str]['mode2'] = data_number
        except ValueError as e:
            print(f"[ERROR] Failed to convert mode2 data: {data_str}")

    # Sort data by date
    sorted_dates = sorted(processed_data.keys())
    
    # Prepare data for CSV
    csv_data = []
    for date in sorted_dates:
        entry = processed_data[date]
        csv_data.append({
            'tanggal': date,
            'mode1': entry['mode1'],
            'mode2': entry['mode2']
        })

    # Save to CSV
    csv_file = f"database/{kode}.csv"
    with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=['tanggal', 'mode1', 'mode2'])
        writer.writeheader()
        writer.writerows(csv_data)

def scrape_url(url_data, pixel, data_periods):
    """Function to scrape data for a single URL"""
    kode, url = url_data
    print_header(f"Starting Data Collection: {kode}")
    print(f"URL: {url}")

    # Collect data for both modes
    mode1_data = []
    mode2_data = []

    # Scrape Mode 1 (Default mode)
    print_header("Collecting Mode 1 (Default) Data")
    for period in data_periods:
        period_data = scrape_mode_data(url, period, "Default", pixel)
        mode1_data.extend(period_data)

    # Scrape Mode 2 (AUM mode)
    print_header("Collecting Mode 2 (AUM) Data")
    for period in data_periods:
        period_data = scrape_mode_data(url, period, "AUM", pixel)
        mode2_data.extend(period_data)

    # Process and save combined data
    process_and_save_data(kode, mode1_data, mode2_data)

def main():
    start_time = time.time()

    urls = [
        ['ABF Indonesia Bond Index Fund', 'https://bibit.id/reksadana/RD13'],
        # Tambahkan URL lainnya di sini
    ]

    pixel = 200
    data_periods = ['3Y', '5Y']

    # Create a list to hold process objects
    processes = []

    # Start a process for each URL
    for url_data in urls:
        process = Process(target=scrape_url, args=(url_data, pixel, data_periods))
        processes.append(process)
        process.start()

    # Wait for all processes to complete
    for process in processes:
        process.join()

    end_time = time.time()
    duration = end_time - start_time
    
    print_header("Execution Summary")
    print(f"Total execution time: {duration:.2f} seconds")

if __name__ == "__main__":
    main()