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

def scrape_data(url, period, result_list, pixel):
    options = webdriver.ChromeOptions()
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--no-sandbox')
    options.add_argument('--headless')  # Run in background
    service = webdriver.chrome.service.Service()
    driver = webdriver.Chrome(service=service, options=options)

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

        for offset in range(start_offset, start_offset + graph_width, pixel):
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
            
            # Simpan data ke dalam list period_data (hanya Tanggal dan Data)
            period_data.append({
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

    # List URL yang akan di-scrap
    urls = [
        'https://bibit.id/reksadana/RD13/',
        'https://bibit.id/reksadana/RD66/',
        # Tambahkan URL lain di sini
    ]

    pixel = 2
    data_periods = ['ALL', '1M', '3M', 'YTD', '3Y', '5Y']

    for url in urls:
        print(f"\nMemulai scraping untuk URL: {url}")

        processes = []
        manager = Manager()
        result_list = manager.list()  # List shared antar proses

        for period in data_periods:
            p = Process(target=scrape_data, args=(url, period, result_list, pixel))
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
            formatted_data.append({
                'tanggal': tanggal_str,
                'data': data_str
            })

        # Cetak hasil akhir
        print("\nHasil akhir (Tanpa Duplikat, Diurutkan dari Tanggal Terlama):")
        for entry in formatted_data:
            print(f"Tanggal: {entry['tanggal']}, Data: {entry['data']}")

        # Simpan ke CSV
        # Buat nama file berdasarkan URL
        csv_file = os.path.basename(url) + '.csv'
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