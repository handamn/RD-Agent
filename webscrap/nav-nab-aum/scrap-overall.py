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

# =========================== Utility Functions ===========================

def print_header(text, char="="):
    """Print a header with consistent formatting"""
    line = char * 80
    print(f"\n{line}")
    print(f"{text.center(80)}")
    print(f"{line}\n")

def print_progress(mode, period, iteration, date, value):
    """Print progress with consistent formatting"""
    print(f"Mode: {mode:<6} | Period: {period:<4} | Iteration: {iteration:<4} | Date: {date:<10} | Value: {value}")

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

def switch_to_aum_mode(driver, wait):
    """Switch to AUM mode"""
    try:
        aum_button = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'menu') and contains(text(), 'AUM')]"))
        )
        aum_button.click()
        time.sleep(3)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to switch to AUM mode: {e}")
        return False

# =========================== Scraping Function ===========================

def scrape_mode_data(url, period, mode, pixel, max_retries=3):
    """Scrape data for a specific mode and period"""
    retry_count = 0
    success = False
    period_data = []

    while retry_count < max_retries and not success:
        try:
            options = webdriver.ChromeOptions()
            options.add_argument('--disable-gpu')
            options.add_argument('--no-sandbox')
            options.add_argument('--headless')
            driver = webdriver.Chrome(options=options)
            wait = WebDriverWait(driver, 10)

            driver.get(url)

            # Switch to AUM mode if needed
            if mode == "AUM":
                if not switch_to_aum_mode(driver, wait):
                    raise Exception("Failed to switch to AUM mode")

            # Click period button
            button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, f'button[data-period="{period}"]')))
            button.click()
            time.sleep(2)

            # Get graph element
            graph_element = wait.until(EC.presence_of_element_located((By.TAG_NAME, 'svg')))
            graph_width = int(graph_element.size['width'])
            start_offset = -graph_width // 2

            actions = ActionChains(driver)

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

        except Exception as e:
            retry_count += 1
            print(f"[WARNING] Failed to get data for {period} in {mode} mode. Attempt {retry_count}/{max_retries}. Error: {e}")
            if retry_count < max_retries:
                time.sleep(3)

        finally:
            try:
                driver.quit()
            except:
                pass

    return period_data

# =========================== Parallel Scraping with Threads ===========================

def scrape_all_periods(url, mode, pixel):
    """Run scraping in parallel for all periods using threads"""
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(scrape_mode_data, url, period, mode, pixel): period for period in ['3Y', '5Y']}
        results = []

        for future in as_completed(futures):
            period = futures[future]
            try:
                result = future.result()
                results.extend(result)
            except Exception as e:
                print(f"[ERROR] Scraping failed for {period}: {e}")

        return results

# =========================== Save Data Function ===========================

def process_and_save_data(kode, mode1_data, mode2_data):
    """Process and save data"""
    processed_data = {}

    # Merge mode1 & mode2 data
    for data_list, mode in [(mode1_data, 'mode1'), (mode2_data, 'mode2')]:
        for entry in data_list:
            try:
                tanggal_obj = datetime.strptime(entry['tanggal'], "%d %B %Y")
                tanggal_str = tanggal_obj.strftime("%Y-%m-%d")
                data_number = convert_to_number(entry['data'].replace('Rp', '').strip())

                if tanggal_str not in processed_data:
                    processed_data[tanggal_str] = {'mode1': 'NA', 'mode2': 'NA'}
                processed_data[tanggal_str][mode] = data_number
            except Exception as e:
                print(f"[ERROR] Data conversion failed: {e}")

    # Save to CSV
    os.makedirs("database", exist_ok=True)
    csv_file = f"database/{kode}.csv"
    with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=['tanggal', 'mode1', 'mode2'])
        writer.writeheader()
        writer.writerows([{'tanggal': date, 'mode1': data['mode1'], 'mode2': data['mode2']} for date, data in sorted(processed_data.items())])

# =========================== Main Function ===========================

def main():
    start_time = time.time()

    urls = [
        ['ABF Indonesia Bond Index Fund', 'https://bibit.id/reksadana/RD13'],
    ]

    pixel = 200

    for kode, url in urls:
        print_header(f"Starting Data Collection: {kode}")

        mode1_data = scrape_all_periods(url, "Default", pixel)
        mode2_data = scrape_all_periods(url, "AUM", pixel)

        process_and_save_data(kode, mode1_data, mode2_data)

    print_header("Execution Summary")
    print(f"Total execution time: {time.time() - start_time:.2f} seconds")

if __name__ == "__main__":
    main()
