from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from multiprocessing import Process, Manager
import csv
import os
from datetime import datetime
# from selenium.webdriver.support.expected_conditions import staleness_of

def print_header(text, char="="):
    """Print a header with consistent formatting"""
    line = char * 80
    print(f"\n{line}")
    print(f"{text.center(80)}")
    print(f"{line}\n")

def print_subheader(text, char="-"):
    """Print a subheader with consistent formatting"""
    print(f"\n{char * 40} {text} {char * 40}\n")

def print_progress(period, iteration, date, value):
    """Print progress with consistent formatting"""
    print(f"Period: {period:<4} | Iteration: {iteration:<4} | Date: {date:<10} | Value: {value}")

def convert_to_number(value):
    # Existing convert_to_number function remains the same
    if 'K' in value:
        return float(value.replace('K', '')) * 1000
    elif 'M' in value:
        return float(value.replace('M', '')) * 1000000
    else:
        return float(value.replace(',', ''))

def parse_tanggal(tanggal_str):
    # Existing parse_tanggal function remains the same
    bulan_map_id = {
        'Jan': 'Januari',
        'Feb': 'Februari',
        'Mar': 'Maret',
        'Apr': 'April',
        'Mei': 'Mei',
        'Jun': 'Juni',
        'Jul': 'Juli',
        'Agt': 'Agustus',
        'Sep': 'September',
        'Okt': 'Oktober',
        'Nov': 'November',
        'Des': 'Desember'
    }

    bulan_map_en = {
        'Januari': 'January',
        'Februari': 'February',
        'Maret': 'March',
        'April': 'April',
        'Mei': 'May',
        'Juni': 'June',
        'Juli': 'July',
        'Agustus': 'August',
        'September': 'September',
        'Oktober': 'October',
        'November': 'November',
        'Desember': 'December'
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


def scrape_data(url, period, result_list, pixel, max_retries=3):
    """
    Fungsi untuk melakukan scraping data berdasarkan periode tertentu.
    - Menangani 'stale element reference' dengan cara yang lebih adaptif.
    - Mencoba kembali (retry) hingga data berhasil diambil.
    - Menunggu elemen benar-benar siap sebelum berinteraksi.
    """

    retry_count = 0
    success = False

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

            # Tunggu tombol periode muncul dan bisa diklik
            button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, f'button[data-period="{period}"]')))

            print(f"[INFO] Memulai scraping untuk periode: {period}")

            # Klik tombol periode
            button.click()
            time.sleep(2)  # Tunggu perubahan halaman

            # Tunggu elemen grafik muncul sebelum mulai scraping
            graph_element = wait.until(EC.presence_of_element_located((By.TAG_NAME, 'svg')))
            graph_width = int(graph_element.size['width'])
            start_offset = -graph_width // 2

            actions = ActionChains(driver)
            period_data = []

            print_subheader(f"Mengambil data periode {period}")

            for offset in range(start_offset, start_offset + graph_width, pixel):
                actions.move_to_element_with_offset(graph_element, offset, 0).perform()
                time.sleep(0.1)

                # Ambil data harga reksa dana
                updated_data = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '.reksa-value-head-nav.ChartHead_reksa-value-head-nav__LCCdL'))
                ).text

                # Ambil tanggal
                tanggal_navdate = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '.navDate'))
                ).text

                print_progress(period, offset // pixel + 1, tanggal_navdate, updated_data)

                period_data.append({
                    'tanggal': tanggal_navdate,
                    'data': updated_data
                })

            # Jika ada data, simpan ke result_list
            if period_data:
                result_list.append(period_data)
                success = True
            else:
                raise Exception(f"Tidak ada data yang ditemukan untuk periode {period}")

        except Exception as e:
            retry_count += 1
            print(f"[WARNING] Gagal mengambil data untuk periode {period}. Percobaan {retry_count}/{max_retries}. Error: {e}")

            # Jika gagal, coba refresh halaman sebelum mencoba ulang
            if retry_count < max_retries:
                time.sleep(3)  # Tunggu sebelum mencoba lagi
                try:
                    driver.refresh()
                    time.sleep(2)  # Tunggu halaman reload
                except:
                    pass

        finally:
            try:
                driver.quit()
            except:
                pass  # Abaikan error jika driver sudah tertutup

    if not success:
        print(f"[ERROR] Gagal mengambil data untuk periode {period} setelah {max_retries} percobaan.")
