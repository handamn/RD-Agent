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
    # Menghilangkan koma agar bisa dikonversi ke float
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


# def scrape_data(url, period, result_list, pixel, max_retries=3):
#     """
#     Fungsi untuk melakukan scraping data berdasarkan periode tertentu.
#     - Menangani 'stale element reference' dengan cara yang lebih adaptif.
#     - Mencoba kembali (retry) hingga data berhasil diambil.
#     - Menunggu elemen benar-benar siap sebelum berinteraksi.
#     """

#     retry_count = 0
#     success = False

#     while retry_count < max_retries and not success:
#         try:
#             options = webdriver.ChromeOptions()
#             options.add_argument('--disable-gpu')
#             options.add_argument('--disable-dev-shm-usage')
#             options.add_argument('--no-sandbox')
#             options.add_argument('--headless')
#             service = webdriver.chrome.service.Service()
#             driver = webdriver.Chrome(service=service, options=options)

#             #########
#             driver.get(url)
#             wait = WebDriverWait(driver, 10)

#             # Tunggu tombol periode muncul dan bisa diklik
#             button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, f'button[data-period="{period}"]')))

#             print(f"[INFO] Memulai scraping untuk periode: {period}")

#             # Klik tombol periode
#             button.click()
#             time.sleep(2)  # Tunggu perubahan halaman

#             # Tunggu elemen grafik muncul sebelum mulai scraping
#             graph_element = wait.until(EC.presence_of_element_located((By.TAG_NAME, 'svg')))
#             graph_width = int(graph_element.size['width'])
#             start_offset = -graph_width // 2

#             actions = ActionChains(driver)
#             period_data = []

#             print_subheader(f"Mengambil data periode {period}")

#             for offset in range(start_offset, start_offset + graph_width, pixel):
#                 actions.move_to_element_with_offset(graph_element, offset, 0).perform()
#                 time.sleep(0.1)

#                 # Ambil data harga reksa dana
#                 updated_data = wait.until(
#                     EC.presence_of_element_located((By.CSS_SELECTOR, '.reksa-value-head-nav.ChartHead_reksa-value-head-nav__LCCdL'))
#                 ).text

#                 # Ambil tanggal
#                 tanggal_navdate = wait.until(
#                     EC.presence_of_element_located((By.CSS_SELECTOR, '.navDate'))
#                 ).text

#                 print_progress(period, offset // pixel + 1, tanggal_navdate, updated_data)

#                 period_data.append({
#                     'tanggal': tanggal_navdate,
#                     'data': updated_data
#                 })

#             # Jika ada data, simpan ke result_list
#             if period_data:
#                 result_list.append(period_data)
#                 success = True
#             else:
#                 raise Exception(f"Tidak ada data yang ditemukan untuk periode {period}")

#         except Exception as e:
#             retry_count += 1
#             print(f"[WARNING] Gagal mengambil data untuk periode {period}. Percobaan {retry_count}/{max_retries}. Error: {e}")

#             # Jika gagal, coba refresh halaman sebelum mencoba ulang
#             if retry_count < max_retries:
#                 time.sleep(3)  # Tunggu sebelum mencoba lagi
#                 try:
#                     driver.refresh()
#                     time.sleep(2)  # Tunggu halaman reload
#                 except:
#                     pass

#         finally:
#             try:
#                 driver.quit()
#             except:
#                 pass  # Abaikan error jika driver sudah tertutup

#     if not success:
#         print(f"[ERROR] Gagal mengambil data untuk periode {period} setelah {max_retries} percobaan.")



def scrape_data(url, period, result_list, pixel, max_retries=3):
    """
    Fungsi scraping yang ditingkatkan:
    - Klik tombol "AUM" sebelum mulai scraping.
    - Menangani error 'stale element reference'.
    - Retry mechanism untuk memastikan data berhasil diambil.
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

            # 🔹 Coba Klik Tombol "AUM" Sebelum Scraping
            try:
                aum_button = wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'menu') and contains(text(), 'AUM')]"))
                )
                print("[INFO] Tombol 'AUM' ditemukan, mencoba klik...")

                try:
                    aum_button.click()
                    print("[INFO] Klik 'AUM' berhasil dengan metode .click()")
                except Exception as e:
                    print(f"[WARNING] Klik 'AUM' gagal dengan .click(), mencoba metode JavaScript: {e}")
                    driver.execute_script("arguments[0].click();", aum_button)

                time.sleep(5)  # 🔹 Tunggu halaman merespons setelah klik "AUM"
            except Exception as e:
                print(f"[WARNING] Tombol 'AUM' tidak ditemukan atau tidak bisa diklik: {e}")

            # 🔹 Klik Tombol Periode (ALL, 1M, 3M, YTD, 3Y, 5Y)
            button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, f'button[data-period="{period}"]')))
            print(f"[INFO] Memulai scraping untuk periode: {period}")

            button.click()
            time.sleep(2)  # Tunggu perubahan halaman

            # 🔹 Tunggu elemen grafik muncul sebelum mulai scraping
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

            # 🔹 Jika data berhasil diambil, simpan ke result_list
            if period_data:
                result_list.append(period_data)
                success = True
            else:
                raise Exception(f"Tidak ada data yang ditemukan untuk periode {period}")

        except Exception as e:
            retry_count += 1
            print(f"[WARNING] Gagal mengambil data untuk periode {period}. Percobaan {retry_count}/{max_retries}. Error: {e}")

            # 🔹 Jika gagal, coba refresh halaman sebelum mencoba ulang
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




if __name__ == "__main__":
    start_time = time.time()

    # List URL yang akan di-scrap
    urls = [
        ['ABF Indonesia Bond Index Fund', 'https://bibit.id/reksadana/RD13'],
        # ['Avrist Ada Kas Mutiara', 'https://bibit.id/reksadana/RD66'],
        # ['Avrist Ada Saham Blue Safir Kelas A','https://bibit.id/reksadana/RD68'],
        # ['Avrist IDX30','https://bibit.id/reksadana/RD82'],
        # ['Avrist Prime Bond Fund','https://bibit.id/reksadana/RD83'],
        # ['Bahana Dana Likuid Kelas G','https://bibit.id/reksadana/RD124'],
        # ['Bahana Likuid Plus','https://bibit.id/reksadana/RD140'],
        # ['Bahana Likuid Syariah Kelas G','https://bibit.id/reksadana/RD3595'],
        # ['Bahana MES Syariah Fund Kelas G','https://bibit.id/reksadana/RD1721'],
        # ['Bahana Pendapatan Tetap Makara Prima kelas G','https://bibit.id/reksadana/RD841'],
        # ['Bahana Primavera 99 Kelas G','https://bibit.id/reksadana/RD3672'],
        # ['Batavia Dana Kas Maxima','https://bibit.id/reksadana/RD205'],
        # ['Batavia Dana Likuid','https://bibit.id/reksadana/RD206'],
        # ['Batavia Dana Obligasi Ultima','https://bibit.id/reksadana/RD214'],
        # ['Batavia Dana Saham','https://bibit.id/reksadana/RD216'],
        # ['Batavia Dana Saham Syariah','https://bibit.id/reksadana/RD218'],
        # ['Batavia Index PEFINDO I-Grade','https://bibit.id/reksadana/RD6323'],
        # ['Batavia Obligasi Platinum Plus','https://bibit.id/reksadana/RD223'],
        # ['Batavia Technology Sharia Equity USD','https://bibit.id/reksadana/RD4183'],
        # ['BNI-AM Dana Lancar Syariah','https://bibit.id/reksadana/RD322'],
        # ['BNI-AM Dana Likuid Kelas A','https://bibit.id/reksadana/RD323'],
        # ['BNI-AM Dana Pendapatan Tetap Makara Investasi','https://bibit.id/reksadana/RD1409'],
        # ['BNI-AM Dana Pendapatan Tetap Syariah Ardhani','https://bibit.id/reksadana/RD332'],
        # ['BNI-AM Dana Saham Inspiring Equity Fund','https://bibit.id/reksadana/RD334'],
        # ['BNI-AM IDX PEFINDO Prime Bank Kelas R1','https://bibit.id/reksadana/RD6522'],
        # ['BNI-AM Indeks IDX30','https://bibit.id/reksadana/RD337'],
        # ['BNI-AM ITB Harmoni','https://bibit.id/reksadana/RD781'],
        # ['BNI-AM PEFINDO I-Grade Kelas R1','https://bibit.id/reksadana/RD6520'],
        # ['BNI-AM Short Duration Bonds Index Kelas R1','https://bibit.id/reksadana/RD5638'],
        # ['BNI-AM SRI KEHATI Kelas R1','https://bibit.id/reksadana/RD6502'],
        # ['BNP Paribas Cakra Syariah USD Kelas RK1','https://bibit.id/reksadana/RD1725'],
        # ['BNP Paribas Ekuitas','https://bibit.id/reksadana/RD409'],
        # ['BNP Paribas Greater China Equity Syariah USD','https://bibit.id/reksadana/RD3531'],
        # ['BNP Paribas Infrastruktur Plus','https://bibit.id/reksadana/RD412'],
        # ['BNP Paribas Pesona','https://bibit.id/reksadana/RD423'],
        # ['BNP Paribas Pesona Syariah','https://bibit.id/reksadana/RD424'],
        # ['BNP Paribas Prima II Kelas RK1','https://bibit.id/reksadana/RD3542'],
        # ['BNP Paribas Prima USD Kelas RK1','https://bibit.id/reksadana/RD426'],
        # ['BNP Paribas Rupiah Plus','https://bibit.id/reksadana/RD429'],
        # ['BNP Paribas Solaris','https://bibit.id/reksadana/RD431'],
        # ['BNP Paribas SRI KEHATI','https://bibit.id/reksadana/RD1911'],
        # ['BNP Paribas Sukuk Negara Kelas RK1','https://bibit.id/reksadana/RD6524'],
        # ['BRI Indeks Syariah','https://bibit.id/reksadana/RD562'],
        # ['BRI Mawar Konsumer 10 Kelas A','https://bibit.id/reksadana/RD569'],
        # ['BRI Melati Pendapatan Utama','https://bibit.id/reksadana/RD578'],
        # ['BRI MSCI Indonesia ESG Screened Kelas A','https://bibit.id/reksadana/RD5643'],
        # ['BRI Seruni Pasar Uang II Kelas A','https://bibit.id/reksadana/RD618'],
        # ['BRI Seruni Pasar Uang III','https://bibit.id/reksadana/RD619'],
        # ['BRI Seruni Pasar Uang Syariah','https://bibit.id/reksadana/RD620'],
        # ['Danamas Pasti','https://bibit.id/reksadana/RD553'],
        # ['Danamas Rupiah Plus','https://bibit.id/reksadana/RD555'],
        # ['Danamas Stabil','https://bibit.id/reksadana/RD556'],
        # ['Eastspring IDR Fixed Income Fund Kelas A','https://bibit.id/reksadana/RD3447'],
        # ['Eastspring IDX ESG Leaders Plus Kelas A','https://bibit.id/reksadana/RD4256'],
        # ['Eastspring Investments Cash Reserve Kelas A','https://bibit.id/reksadana/RD3448'],
        # ['Eastspring Investments Value Discovery Kelas A','https://bibit.id/reksadana/RD3509'],
        # ['Eastspring Investments Yield Discovery Kelas A','https://bibit.id/reksadana/RD3510'],
        # ['Eastspring Syariah Fixed Income Amanah Kelas A','https://bibit.id/reksadana/RD3487'],
        # ['Eastspring Syariah Greater China Equity USD Kelas A','https://bibit.id/reksadana/RD3702'],
        # ['Eastspring Syariah Money Market Khazanah Kelas A','https://bibit.id/reksadana/RD3449'],
        # ['Grow Dana Optima Kas Utama','https://bibit.id/reksadana/RD8808'],
        # ['Grow Obligasi Optima Dinamis Kelas O','https://bibit.id/reksadana/RD8807'],
        # ['Grow Saham Indonesia Plus Kelas O','https://bibit.id/reksadana/RD6651'],
        # ['Grow SRI KEHATI Kelas O','https://bibit.id/reksadana/RD6649'],
        # ['Jarvis Balanced Fund','https://bibit.id/reksadana/RD3191'],
        # ['Jarvis Money Market Fund','https://bibit.id/reksadana/RD2046'],
        # ['Majoris Pasar Uang Indonesia','https://bibit.id/reksadana/RD831'],
        # ['Majoris Pasar Uang Syariah Indonesia','https://bibit.id/reksadana/RD832'],
        # ['Majoris Saham Alokasi Dinamik Indonesia','https://bibit.id/reksadana/RD833'],
        # ['Majoris Sukuk Negara Indonesia','https://bibit.id/reksadana/RD838'],
        # ['Mandiri Indeks FTSE Indonesia ESG Kelas A','https://bibit.id/reksadana/RD4221'],
        # ['Mandiri Investa Atraktif-Syariah','https://bibit.id/reksadana/RD853'],
        # ['Mandiri Investa Dana Syariah Kelas A','https://bibit.id/reksadana/RD860'],
        # ['Mandiri Investa Dana Utama Kelas D','https://bibit.id/reksadana/RD6639'],
        # ['Mandiri Investa Pasar Uang Kelas A','https://bibit.id/reksadana/RD870'],
        # ['Mandiri Investa Syariah Berimbang','https://bibit.id/reksadana/RD872'],
        # ['Mandiri Pasar Uang Syariah Ekstra','https://bibit.id/reksadana/RD3173'],
        # ['Manulife Dana Kas II Kelas A','https://bibit.id/reksadana/RD983'],
        # ['Manulife Dana Kas Syariah','https://bibit.id/reksadana/RD984'],
        # ['Manulife Dana Saham Kelas A','https://bibit.id/reksadana/RD985'],
        # ['Manulife Obligasi Negara Indonesia II Kelas A','https://bibit.id/reksadana/RD994'],
        # ['Manulife Obligasi Unggulan Kelas A','https://bibit.id/reksadana/RD3206'],
        # ['Manulife Saham Andalan','https://bibit.id/reksadana/RD998'],
        # ['Manulife Syariah Sektoral Amanah Kelas A','https://bibit.id/reksadana/RD1001'],
        # ['Manulife USD Fixed Income Kelas A','https://bibit.id/reksadana/RD1003'],
        # ['Principal Cash Fund','https://bibit.id/reksadana/RD479'],
        # ['Principal Index IDX30 Kelas O','https://bibit.id/reksadana/RD707'],
        # ['Principal Islamic Equity Growth Syariah','https://bibit.id/reksadana/RD487'],
        # ['Schroder 90 Plus Equity Fund','https://bibit.id/reksadana/RD1538'],
        # ['Schroder Dana Andalan II','https://bibit.id/reksadana/RD1539'],
        # ['Schroder Dana Istimewa','https://bibit.id/reksadana/RD1541'],
        # ['Schroder Dana Likuid','https://bibit.id/reksadana/RD1543'],
        # ['Schroder Dana Likuid Syariah','https://bibit.id/reksadana/RD3454'],
        # ['Schroder Dana Mantap Plus II','https://bibit.id/reksadana/RD1544'],
        # ['Schroder Dana Prestasi','https://bibit.id/reksadana/RD1547'],
        # ['Schroder Dana Prestasi Plus','https://bibit.id/reksadana/RD1548'],
        # ['Schroder Dynamic Balanced Fund','https://bibit.id/reksadana/RD1551'],
        # ['Schroder Global Sharia Equity Fund USD','https://bibit.id/reksadana/RD1743'],
        # ['Schroder Syariah Balanced Fund','https://bibit.id/reksadana/RD1564'],
        # ['Schroder USD Bond Fund Kelas A','https://bibit.id/reksadana/RD1565'],
        # ['Simas Saham Unggulan','https://bibit.id/reksadana/RD1628'],
        # ['Simas Satu','https://bibit.id/reksadana/RD1629'],
        # ['Simas Syariah Unggulan','https://bibit.id/reksadana/RD1634'],
        # ['Sucorinvest Bond Fund','https://bibit.id/reksadana/RD1436'],
        # ['Sucorinvest Citra Dana Berimbang','https://bibit.id/reksadana/RD523'],
        # ['Sucorinvest Equity Fund','https://bibit.id/reksadana/RD1653'],
        # ['Sucorinvest Flexi Fund','https://bibit.id/reksadana/RD1655'],
        # ['Sucorinvest IDX30','https://bibit.id/reksadana/RD5741'],
        # ['Sucorinvest Maxi Fund','https://bibit.id/reksadana/RD1656'],
        # ['Sucorinvest Money Market Fund','https://bibit.id/reksadana/RD1657'],
        # ['Sucorinvest Premium Fund','https://bibit.id/reksadana/RD1658'],
        # ['Sucorinvest Sharia Balanced Fund','https://bibit.id/reksadana/RD3194'],
        # ['Sucorinvest Sharia Equity Fund','https://bibit.id/reksadana/RD1668'],
        # ['Sucorinvest Sharia Money Market Fund','https://bibit.id/reksadana/RD1669'],
        # ['Sucorinvest Sharia Sukuk Fund','https://bibit.id/reksadana/RD4046'],
        # ['Sucorinvest Stable Fund','https://bibit.id/reksadana/RD3561'],
        # ['TRAM Consumption Plus Kelas A','https://bibit.id/reksadana/RD1755'],
        # ['TRAM Strategic Plus Kelas A','https://bibit.id/reksadana/RD1761'],
        # ['TRIM Dana Tetap 2 Kelas A','https://bibit.id/reksadana/RD1763'],
        # ['TRIM Kapital','https://bibit.id/reksadana/RD1764'],
        # ['TRIM Kapital Plus','https://bibit.id/reksadana/RD1765'],
        # ['TRIM Kas 2 Kelas A','https://bibit.id/reksadana/RD1766'],
        # ['TRIM Syariah Saham','https://bibit.id/reksadana/RD1366'],
        # ['Trimegah Dana Tetap Syariah Kelas A','https://bibit.id/reksadana/RD3480'],
        # ['Trimegah FTSE Indonesia Low Volatility Factor Index','https://bibit.id/reksadana/RD3901'],
        # ['Trimegah Kas Syariah','https://bibit.id/reksadana/RD1775'],
    ]

    pixel = 2
    data_periods = ['ALL', '1M', '3M', 'YTD', '3Y', '5Y']

    for url_data in urls:
        kode = url_data[0]
        url = url_data[1]
        
        print_header(f"Memulai Scraping Data: {kode}")
        print(f"URL: {url}")

        processes = []
        manager = Manager()
        result_list = manager.list()

        for period in data_periods:
            p = Process(target=scrape_data, args=(url, period, result_list, pixel))
            processes.append(p)
            p.start()

        for p in processes:
            p.join()

        print_subheader("Memproses hasil scraping")
        
        combined_data = []
        for period_data in result_list:
            combined_data.extend(period_data)

        unique_data = []
        seen = set()
        for entry in combined_data:
            key = (entry['tanggal'], entry['data'])
            if key not in seen:
                seen.add(key)
                unique_data.append(entry)

        sorted_data = sorted(unique_data, key=lambda x: parse_tanggal(x['tanggal']))

        formatted_data = []
        for entry in sorted_data:
            tanggal_obj = parse_tanggal(entry['tanggal'])
            tanggal_str = tanggal_obj.strftime("%Y-%m-%d")
            data_str = entry['data'].replace('Rp', '').strip()
            
            try:
                data_number = convert_to_number(data_str)
                formatted_data.append({
                    'tanggal': tanggal_str,
                    'data': data_number
                })
            except ValueError as e:
                print(f"[ERROR] Gagal mengonversi data: {data_str}")

        print("\nHasil akhir (Tanpa Duplikat, Diurutkan dari Tanggal Terlama):")
        for entry in formatted_data[:5]:  # Hanya tampilkan 5 data pertama
            print(f"Tanggal: {entry['tanggal']}, Data: {entry['data']}")
        print("...")  # Menandakan masih ada data lainnya

        csv_file = f"database/{kode}.csv"
        file_exists = os.path.exists(csv_file)
        
        # Jika file belum ada, buat baru dengan header dan semua data
        if not file_exists:
            with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=['tanggal', 'data'])
                writer.writeheader()
                for entry in formatted_data:
                    writer.writerow(entry)
            print(f"\n[INFO] File baru dibuat: {csv_file}")
            print(f"[INFO] {len(formatted_data)} data berhasil disimpan")
        else:
            # Baca data existing dari CSV
            existing_data = []
            with open(csv_file, mode='r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    existing_data.append({
                        'tanggal': row['tanggal'],
                        'data': float(row['data'])  # Konversi ke float untuk konsistensi
                    })

            # Identifikasi data baru yang unik
            new_unique_data = []
            duplicate_count = 0
            
            for new_entry in formatted_data:
                is_duplicate = False
                for existing_entry in existing_data:
                    if (new_entry['tanggal'] == existing_entry['tanggal'] and 
                        float(new_entry['data']) == float(existing_entry['data'])):
                        duplicate_count += 1
                        is_duplicate = True
                        break
                if not is_duplicate:
                    new_unique_data.append(new_entry)

            # Append data unik ke CSV
            if new_unique_data:
                with open(csv_file, mode='a', newline='', encoding='utf-8') as file:
                    writer = csv.DictWriter(file, fieldnames=['tanggal', 'data'])
                    for entry in new_unique_data:
                        writer.writerow(entry)
                print(f"\n[INFO] {len(new_unique_data)} data baru ditambahkan ke {csv_file}")

                print(f"\n[INFO] Data telah disimpan ke {csv_file}")
                

    end_time = time.time()
    durasi = end_time - start_time
    
    print_header("Ringkasan Eksekusi")
    print(f"Total waktu eksekusi: {durasi:.2f} detik")