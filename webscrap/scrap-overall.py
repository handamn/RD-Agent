from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import csv
import os
import logging
from multiprocessing import Process, Manager
from tqdm import tqdm
from itertools import cycle

# Konfigurasi logging
log_file = "scraping.log"
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# Simbol animasi untuk progress bar
symbols = cycle(['⣾', '⣷', '⣯', '⣟', '⡿', '⢿', '⣻', '⣽'])

# Fungsi untuk mengubah format tanggal dari "ddmmmyy" ke objek datetime
def parse_tanggal(tanggal_str):
    # Kamus untuk memetakan singkatan bulan ke nama bulan dalam bahasa Indonesia
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

    # Kamus untuk memetakan nama bulan dalam bahasa Indonesia ke bahasa Inggris
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

    # Pisahkan tanggal, bulan, dan tahun
    parts = tanggal_str.split()
    if len(parts) != 3:
        raise ValueError(f"Format tanggal tidak valid: {tanggal_str}")

    hari = parts[0]
    bulan_singkat = parts[1]
    tahun = parts[2]

    # Ubah singkatan bulan ke nama bulan dalam bahasa Indonesia
    if bulan_singkat not in bulan_map_id:
        raise ValueError(f"Bulan tidak valid: {bulan_singkat}")
    bulan_id = bulan_map_id[bulan_singkat]

    # Ubah nama bulan dalam bahasa Indonesia ke bahasa Inggris
    if bulan_id not in bulan_map_en:
        raise ValueError(f"Bulan tidak valid: {bulan_id}")
    bulan_en = bulan_map_en[bulan_id]

    # Gabungkan menjadi format yang bisa dipahami oleh datetime
    # Misalnya: "1 Agt 24" -> "1 August 2024"
    tanggal_full = f"{hari} {bulan_en} 20{tahun}"
    return datetime.strptime(tanggal_full, "%d %B %Y")


def convert_to_number(value):
    # Jika nilai mengandung 'K' (ribuan)
    if 'K' in value:
        return float(value.replace('K', '')) * 1000
    # Jika nilai mengandung 'M' (jutaan)
    elif 'M' in value:
        return float(value.replace('M', '')) * 1000000
    # Jika tidak ada huruf, langsung konversi ke float
    else:
        return float(value.replace(',', ''))  # Hapus koma jika ada


def scrape_data(url, period, result_list, pixel, progress_bar):
    options = webdriver.ChromeOptions()
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--no-sandbox')
    options.add_argument('--headless')
    service = webdriver.chrome.service.Service()
    driver = webdriver.Chrome(service=service, options=options)
    driver.get(url)

    try:
        button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, f'button[data-period="{period}"]'))
        )
        button_text = button.find_element(By.CSS_SELECTOR, '.reksa-border-button-period-box').text
        logging.info(f"Klik tombol: {button_text} di {url} (Periode: {period})")
        button.click()
        time.sleep(2)

        graph_element = driver.find_element(By.TAG_NAME, 'svg')
        graph_width = int(graph_element.size['width'])
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

            logging.info(f"{url} [{period}] - {tanggal_navdate}: {updated_data}")
            period_data.append({'tanggal': tanggal_navdate, 'data': updated_data})

            progress_bar.update(1)

        result_list.append(period_data)
    except Exception as e:
        logging.error(f"Error scraping {url} [{period}]: {e}")
    finally:
        driver.quit()
        progress_bar.update(1)

if __name__ == "__main__":
    start_time = time.time()

    # List URL yang akan di-scrap
    urls = [
        ['ABF Indonesia Bond Index Fund', 'https://bibit.id/reksadana/RD13'],
        ['Avrist Ada Kas Mutiara', 'https://bibit.id/reksadana/RD66'],
        ['Avrist Ada Saham Blue Safir Kelas A','https://bibit.id/reksadana/RD68'],
        ['Avrist IDX30','https://bibit.id/reksadana/RD82'],
        ['Avrist Prime Bond Fund','https://bibit.id/reksadana/RD83'],
        ['Bahana Dana Likuid Kelas G','https://bibit.id/reksadana/RD124'],
        ['Bahana Likuid Plus','https://bibit.id/reksadana/RD140'],
        ['Bahana Likuid Syariah Kelas G','https://bibit.id/reksadana/RD3595'],
        ['Bahana MES Syariah Fund Kelas G','https://bibit.id/reksadana/RD1721'],
        ['Bahana Pendapatan Tetap Makara Prima kelas G','https://bibit.id/reksadana/RD841'],
        ['Bahana Primavera 99 Kelas G','https://bibit.id/reksadana/RD3672'],
        ['Batavia Dana Kas Maxima','https://bibit.id/reksadana/RD205'],
        ['Batavia Dana Likuid','https://bibit.id/reksadana/RD206'],
        ['Batavia Dana Obligasi Ultima','https://bibit.id/reksadana/RD214'],
        ['Batavia Dana Saham','https://bibit.id/reksadana/RD216'],
        ['Batavia Dana Saham Syariah','https://bibit.id/reksadana/RD218'],
        ['Batavia Index PEFINDO I-Grade','https://bibit.id/reksadana/RD6323'],
        ['Batavia Obligasi Platinum Plus','https://bibit.id/reksadana/RD223'],
        ['Batavia Technology Sharia Equity USD','https://bibit.id/reksadana/RD4183'],
        ['BNI-AM Dana Lancar Syariah','https://bibit.id/reksadana/RD322'],
        ['BNI-AM Dana Likuid Kelas A','https://bibit.id/reksadana/RD323'],
        ['BNI-AM Dana Pendapatan Tetap Makara Investasi','https://bibit.id/reksadana/RD1409'],


    ]

    pixel = 5
    data_periods = ['ALL', '1M', '3M', 'YTD', '3Y', '5Y']
    total_tasks = len(urls) * len(data_periods)
    
    with tqdm(total=total_tasks, bar_format="{l_bar}{bar} {n_fmt}/{total_fmt} [{elapsed}] {postfix}") as progress_bar:
        manager = Manager()
        result_list = manager.list()
        processes = []
        for url_data in urls:
            kode, url = url_data
            logging.info(f"Memulai scraping: {url} ({kode})")
            for period in data_periods:
                p = Process(target=scrape_data, args=(url, period, result_list, pixel, progress_bar))
                processes.append(p)
                p.start()
        for p in processes:
            p.join()
    

        # Gabungkan semua data dari result_list menjadi satu list
        combined_data = []
        for period_data in result_list:
            combined_data.extend(period_data)

        # Hapus duplikat berdasarkan Tanggal dan Data
        unique_data = []
        seen = set()  # Untuk melacak data yang sudah diproses
        for entry in combined_data:
            key = (entry['tanggal'], entry['data'])  # Gunakan tuple (Tanggal, Data) sebagai kunci
            if key not in seen:
                seen.add(key)
                unique_data.append(entry)

        # Ubah format tanggal dan urutkan data berdasarkan Tanggal (dari terlama ke terbaru)
        sorted_data = sorted(unique_data, key=lambda x: parse_tanggal(x['tanggal']))

        # Format ulang tanggal dan data
        formatted_data = []
        for entry in sorted_data:
            tanggal_obj = parse_tanggal(entry['tanggal'])
            tanggal_str = tanggal_obj.strftime("%Y-%m-%d")  # Format tanggal ke YYYY-MM-DD
            data_str = entry['data'].replace('Rp', '').strip()  # Hapus "Rp" dan spasi
            
            # Konversi data ke angka biasa
            try:
                data_number = convert_to_number(data_str)
            except ValueError:
                print(f"Gagal mengonversi data: {data_str}")
                continue  # Lewati data yang tidak valid

            formatted_data.append({
                'tanggal': tanggal_str,
                'data': data_number
            })

        # Cetak hasil akhir
        print("\nHasil akhir (Tanpa Duplikat, Diurutkan dari Tanggal Terlama):")
        for entry in formatted_data:
            print(f"Tanggal: {entry['tanggal']}, Data: {entry['data']}")

        # Simpan ke CSV
        # Gunakan kode sebagai nama file CSV
        csv_file = f"database/{kode}.csv"
        with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=['tanggal', 'data'])
            writer.writeheader()
            for entry in formatted_data:
                writer.writerow(entry)

        print(f"\nData telah disimpan ke {csv_file}")

    end_time = time.time()
    durasi = end_time - start_time
    print()
    print("====")
    print(f"Total waktu eksekusi: {durasi} detik")
    print("====")
    print()


    # print hasil raw
    # print("\nHasil akhir:")
    # for period_data in result_list:
    #     print(f"\nData untuk periode {period_data[0]['period']}:")
    #     for data in period_data:
    #         print(f"Offset: {data['offset']}, Tanggal: {data['tanggal']}, Data: {data['data']}")