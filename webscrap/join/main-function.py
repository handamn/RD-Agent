import os
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import glob
import csv

class Logger:
    """Logger untuk mencatat aktivitas scraping dan downloading ke file log yang sama."""
    def __init__(self, log_dir="logs"):
        os.makedirs(log_dir, exist_ok=True)
        log_filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_scrapping.log"
        self.LOG_FILE = os.path.join(log_dir, log_filename)

    def log_info(self, message, status="INFO"):
        """Menyimpan log ke file dengan format timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [{status}] {message}\n"

        with open(self.LOG_FILE, "a", encoding="utf-8") as log_file:
            log_file.write(log_message)


class Scraper:
    def __init__(self, urls, data_periods, pixel, logger, debug_mode=False):
        """Inisialisasi scraper dengan daftar URL, periode, pixel, dan logger eksternal."""
        self.urls = urls
        self.data_periods = data_periods
        self.pixel = pixel
        self.logger = logger
        self.debug_mode = debug_mode
        self.database_dir = "database"
        os.makedirs(self.database_dir, exist_ok=True)

    def convert_to_number(self, value):
        """Mengonversi string nilai dengan format K, M, B, T menjadi angka float dan mengembalikan jenis mata uang."""
        value = value.replace(',', '').strip()

        if value.startswith('Rp'):
            currency = 'IDR'
            value = value.replace('Rp', '').strip()
        elif value.startswith('$'):
            currency = 'USD'
            value = value.replace('$', '').strip()
        else:
            currency = 'UNKNOWN'  # Jika format tidak dikenali

        multiplier = 1
        if 'K' in value:
            value = value.replace('K', '')
            multiplier = 1_000
        elif 'M' in value:
            value = value.replace('M', '')
            multiplier = 1_000_000
        elif 'B' in value:
            value = value.replace('B', '')
            multiplier = 1_000_000_000
        elif 'T' in value:
            value = value.replace('T', '')
            multiplier = 1_000_000_000_000

        try:
            return float(value) * multiplier, currency
        except ValueError:
            raise ValueError(f"Format angka tidak valid: {value}")



    def parse_tanggal(self, tanggal_str):
        """Mengonversi tanggal dalam format Indonesia ke format datetime Python."""
        bulan_map = {
            'Jan': 'January', 'Feb': 'February', 'Mar': 'March',
            'Apr': 'April', 'Mei': 'May', 'Jun': 'June',
            'Jul': 'July', 'Agt': 'August', 'Sep': 'September',
            'Okt': 'October', 'Nov': 'November', 'Des': 'December'
        }

        parts = tanggal_str.split()
        if len(parts) != 3:
            raise ValueError(f"Format tanggal tidak valid: {tanggal_str}")

        hari, bulan_singkat, tahun = parts
        bulan_en = bulan_map.get(bulan_singkat, None)
        if not bulan_en:
            raise ValueError(f"Bulan tidak valid: {bulan_singkat}")

        return datetime.strptime(f"{hari} {bulan_en} 20{tahun}", "%d %B %Y")

    def switch_to_aum_mode(self, driver, wait):
        """Mengaktifkan mode AUM di situs sebelum scraping data."""
        try:
            aum_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'menu') and contains(text(), 'AUM')]"))
            )
            self.logger.log_info("[INFO] Beralih ke mode AUM...")
            aum_button.click()
            time.sleep(3)  # Menunggu perubahan tampilan
            return True
        except Exception as e:
            self.logger.log_info(f"Gagal beralih ke mode AUM: {e}", "ERROR")
            return False

    def scrape_mode_data(self, url, period, mode):
        """Scrape data untuk mode dan periode tertentu."""
        start_time = time.time()
        period_data = []

        try:
            self.logger.log_info(f"Memulai scraping {period} ({mode}) untuk {url}...")

            options = webdriver.ChromeOptions()
            options.add_argument('--headless')
            driver = webdriver.Chrome(options=options)
            wait = WebDriverWait(driver, 10)

            driver.get(url)
            self.logger.log_info(f"Berhasil membuka URL {url}")

            # Beralih ke mode AUM jika mode yang dipilih adalah AUM
            if mode == "AUM":
                if not self.switch_to_aum_mode(driver, wait):
                    raise Exception("Gagal mengaktifkan mode AUM")

            # Ambil semua tombol periode yang tersedia di halaman
            available_buttons = driver.find_elements(By.CSS_SELECTOR, 'button[data-period]')
            available_periods = [btn.get_attribute("data-period") for btn in available_buttons]

            # Filter periode yang benar-benar tersedia
            valid_periods = [p for p in self.data_periods if p in available_periods]

            # Log jika ada periode yang tidak tersedia
            missing_periods = [p for p in self.data_periods if p not in available_periods]
            if missing_periods:
                self.logger.log_info(f"Periode berikut tidak ditemukan di halaman ini: {missing_periods}", "WARNING")

            # Jalankan scraping hanya jika periode yang diminta tersedia
            if period not in valid_periods:
                self.logger.log_info(f"Periode {period} tidak tersedia, skipping...", "WARNING")
                return period_data  # Return kosong karena tidak bisa lanjut

            # Klik tombol periode jika tersedia
            button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, f'button[data-period="{period}"]')))
            button.click()
            self.logger.log_info(f"Berhasil memilih periode {period}.")
            time.sleep(2)

            # Mulai scraping grafik
            graph_element = wait.until(EC.presence_of_element_located((By.TAG_NAME, 'svg')))
            graph_width = int(graph_element.size['width'])
            start_offset = -graph_width // 2

            actions = ActionChains(driver)

            for offset in range(start_offset, start_offset + graph_width, self.pixel):
                actions.move_to_element_with_offset(graph_element, offset, 0).perform()
                time.sleep(0.1)

                updated_data = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.reksa-value-head-nav'))).text
                tanggal_navdate = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.navDate'))).text

                period_data.append({'tanggal': tanggal_navdate, 'data': updated_data})

                if self.debug_mode:
                    self.logger.log_info(
                        f"[DEBUG] Mode {mode} | Periode {period} | Kursor {offset} | Tanggal: {tanggal_navdate} | Data: {updated_data}", 
                        "DEBUG"
                    )

            self.logger.log_info(f"Scraping {period} ({mode}) selesai, total data: {len(period_data)}")

        except Exception as e:
            self.logger.log_info(f"Scraping gagal untuk {period} ({mode}): {e}", "ERROR")

        finally:
            driver.quit()

        duration = time.time() - start_time
        self.logger.log_info(f"Scraping {period} ({mode}) selesai dalam {duration:.2f} detik.")
        return period_data


    def process_and_save_data(self, kode, mode1_data, mode2_data):
        """Memproses dan menyimpan data hasil scraping ke dalam CSV, termasuk informasi mata uang."""
        processed_data = {}

        for entry in mode1_data:
            try:
                tanggal_obj = self.parse_tanggal(entry['tanggal'])
                tanggal_str = tanggal_obj.strftime("%Y-%m-%d")
                data_number, currency = self.convert_to_number(entry['data'])  # Dapatkan nilai + mata uang

                if tanggal_str not in processed_data:
                    processed_data[tanggal_str] = {'NAV': 'NA', 'AUM': 'NA', 'currency': currency}
                processed_data[tanggal_str]['NAV'] = data_number
            except ValueError:
                self.logger.log_info(f"[ERROR] Gagal mengonversi data NAV: {entry['data']}", "ERROR")

        for entry in mode2_data:
            try:
                tanggal_obj = self.parse_tanggal(entry['tanggal'])
                tanggal_str = tanggal_obj.strftime("%Y-%m-%d")
                data_number, currency = self.convert_to_number(entry['data'])  # Dapatkan nilai + mata uang

                if tanggal_str not in processed_data:
                    processed_data[tanggal_str] = {'NAV': 'NA', 'AUM': 'NA', 'currency': currency}
                processed_data[tanggal_str]['AUM'] = data_number
            except ValueError:
                self.logger.log_info(f"[ERROR] Gagal mengonversi data AUM: {entry['data']}", "ERROR")

        sorted_dates = sorted(processed_data.keys())

        csv_file = os.path.join(self.database_dir, f"{kode}.csv")
        with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=['tanggal', 'NAV', 'AUM', 'currency'])
            writer.writeheader()

            for date in sorted_dates:
                writer.writerow({
                    'tanggal': date,
                    'NAV': processed_data[date]['NAV'],
                    'AUM': processed_data[date]['AUM'],
                    'currency': processed_data[date]['currency']
                })

        self.logger.log_info(f"Data {kode} berhasil disimpan ke {csv_file}")



    def run(self):
        """Menjalankan scraping untuk semua URL dan menyimpan hasil ke CSV dengan multithreading pada periode."""
        total_start_time = time.time()
        self.logger.log_info("===== Mulai scraping seluruh data =====")

        for kode, url in self.urls:
            url_start_time = time.time()
            self.logger.log_info(f"Mulai scraping untuk {kode} (Total {len(self.data_periods)} periode)")

            all_mode1_data = []
            all_mode2_data = []

            # Menjalankan scraping setiap periode secara paralel
            with ThreadPoolExecutor(max_workers=10) as executor:  # 3 worker threads, bisa disesuaikan
                futures = {executor.submit(self.scrape_mode_data, url, period, mode): (period, mode)
                        for period in self.data_periods for mode in ["Default", "AUM"]}

                for future in as_completed(futures):
                    period, mode = futures[future]
                    try:
                        data = future.result()
                        if mode == "Default":
                            all_mode1_data.extend(data)
                        else:
                            all_mode2_data.extend(data)
                        
                        self.logger.log_info(f"Scraping {kode} untuk {period} ({mode}) selesai.")
                    
                    except Exception as e:
                        self.logger.log_info(f"[ERROR] Scraping gagal untuk {kode} ({period}, {mode}): {e}", "ERROR")

            # Proses & simpan setelah semua periode selesai
            self.process_and_save_data(kode, all_mode1_data, all_mode2_data)

            url_duration = time.time() - url_start_time
            self.logger.log_info(f"Scraping {kode} selesai dalam {url_duration:.2f} detik.")

        total_duration = time.time() - total_start_time
        self.logger.log_info(f"===== Semua scraping selesai dalam {total_duration:.2f} detik =====")



class ProspektusDownloader:
    def __init__(self, logger, download_folder="downloads"):
        """Inisialisasi downloader dengan lokasi folder dan logger eksternal."""
        self.logger = logger
        self.download_dir = os.path.join(os.getcwd(), download_folder)
        os.makedirs(self.download_dir, exist_ok=True)

    def _setup_driver(self):
        """Menyiapkan instance WebDriver dengan konfigurasi download otomatis."""
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--disable-gpu')

        prefs = {
            "download.default_directory": self.download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True
        }
        chrome_options.add_experimental_option("prefs", prefs)
        return webdriver.Chrome(options=chrome_options)

    def _wait_for_download(self, timeout=60):
        """Menunggu hingga file selesai diunduh."""
        self.logger.log_info(f"Menunggu proses download selesai di {self.download_dir}...")
        seconds = 0
        while seconds < timeout:
            time.sleep(1)
            files = os.listdir(self.download_dir)
            if not any(fname.endswith('.crdownload') for fname in files):
                self.logger.log_info("Download selesai.")
                return True
            seconds += 1
        self.logger.log_info("Download timeout!", "ERROR")
        return False

    def _rename_latest_pdf(self, new_name):
        """Mengganti nama file PDF terbaru dengan nama yang ditentukan."""
        list_of_files = glob.glob(os.path.join(self.download_dir, '*.pdf'))
        if not list_of_files:
            raise Exception("Tidak ada file PDF ditemukan")

        latest_file = max(list_of_files, key=os.path.getctime)
        new_path = os.path.join(self.download_dir, f"{new_name}.pdf")

        os.rename(latest_file, new_path)
        self.logger.log_info(f"File {latest_file} berhasil diubah menjadi {new_path}")

    def download(self, urls, button_class="DetailProductStyle_detail-produk-button__zk419"):
        """
        Fungsi utama untuk mengunduh dan rename file.

        Parameters:
        urls (list): List berisi judul dan URL halaman web yang berisi button download.
        button_class (str): Class name dari button yang akan diklik.
        """
        driver = self._setup_driver()

        for kode, url in urls:
            try:
                self.logger.log_info(f"Memulai download prospektus untuk {kode} dari {url}")
                driver.get(url)

                button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CLASS_NAME, button_class))
                )
                button.click()

                if not self._wait_for_download():
                    raise Exception("Download timeout")

                time.sleep(2)
                self._rename_latest_pdf(kode)

                self.logger.log_info(f"Download prospektus {kode} berhasil.")

            except Exception as e:
                self.logger.log_info(f"Error saat download {kode}: {str(e)}", "ERROR")

            finally:
                driver.quit()


logger = Logger()


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
        ['BNI-AM Dana Pendapatan Tetap Syariah Ardhani','https://bibit.id/reksadana/RD332'],
        ['BNI-AM Dana Saham Inspiring Equity Fund','https://bibit.id/reksadana/RD334'],
        ['BNI-AM IDX PEFINDO Prime Bank Kelas R1','https://bibit.id/reksadana/RD6522'],
        ['BNI-AM Indeks IDX30','https://bibit.id/reksadana/RD337'],
        ['BNI-AM ITB Harmoni','https://bibit.id/reksadana/RD781'],
        ['BNI-AM PEFINDO I-Grade Kelas R1','https://bibit.id/reksadana/RD6520'],
        ['BNI-AM Short Duration Bonds Index Kelas R1','https://bibit.id/reksadana/RD5638'],
        ['BNI-AM SRI KEHATI Kelas R1','https://bibit.id/reksadana/RD6502'],
        ['BNP Paribas Cakra Syariah USD Kelas RK1','https://bibit.id/reksadana/RD1725'],
        ['BNP Paribas Ekuitas','https://bibit.id/reksadana/RD409'],
        ['BNP Paribas Greater China Equity Syariah USD','https://bibit.id/reksadana/RD3531'],
        ['BNP Paribas Infrastruktur Plus','https://bibit.id/reksadana/RD412'],
        ['BNP Paribas Pesona','https://bibit.id/reksadana/RD423'],
        ['BNP Paribas Pesona Syariah','https://bibit.id/reksadana/RD424'],
        ['BNP Paribas Prima II Kelas RK1','https://bibit.id/reksadana/RD3542'],
        ['BNP Paribas Prima USD Kelas RK1','https://bibit.id/reksadana/RD426'],
        ['BNP Paribas Rupiah Plus','https://bibit.id/reksadana/RD429'],
        ['BNP Paribas Solaris','https://bibit.id/reksadana/RD431'],
        ['BNP Paribas SRI KEHATI','https://bibit.id/reksadana/RD1911'],
        ['BNP Paribas Sukuk Negara Kelas RK1','https://bibit.id/reksadana/RD6524'],
        ['BRI Indeks Syariah','https://bibit.id/reksadana/RD562'],
        ['BRI Mawar Konsumer 10 Kelas A','https://bibit.id/reksadana/RD569'],
        ['BRI Melati Pendapatan Utama','https://bibit.id/reksadana/RD578'],
        ['BRI MSCI Indonesia ESG Screened Kelas A','https://bibit.id/reksadana/RD5643'],
        ['BRI Seruni Pasar Uang II Kelas A','https://bibit.id/reksadana/RD618'],
        ['BRI Seruni Pasar Uang III','https://bibit.id/reksadana/RD619'],
        ['BRI Seruni Pasar Uang Syariah','https://bibit.id/reksadana/RD620'],
        ['Danamas Pasti','https://bibit.id/reksadana/RD553'],
        ['Danamas Rupiah Plus','https://bibit.id/reksadana/RD555'],
        ['Danamas Stabil','https://bibit.id/reksadana/RD556'],
        ['Eastspring IDR Fixed Income Fund Kelas A','https://bibit.id/reksadana/RD3447'],
        ['Eastspring IDX ESG Leaders Plus Kelas A','https://bibit.id/reksadana/RD4256'],
        ['Eastspring Investments Cash Reserve Kelas A','https://bibit.id/reksadana/RD3448'],
        ['Eastspring Investments Value Discovery Kelas A','https://bibit.id/reksadana/RD3509'],
        ['Eastspring Investments Yield Discovery Kelas A','https://bibit.id/reksadana/RD3510'],
        ['Eastspring Syariah Fixed Income Amanah Kelas A','https://bibit.id/reksadana/RD3487'],
        ['Eastspring Syariah Greater China Equity USD Kelas A','https://bibit.id/reksadana/RD3702'],
        ['Eastspring Syariah Money Market Khazanah Kelas A','https://bibit.id/reksadana/RD3449'],
        ['Grow Dana Optima Kas Utama','https://bibit.id/reksadana/RD8808'],
        ['Grow Obligasi Optima Dinamis Kelas O','https://bibit.id/reksadana/RD8807'],
        ['Grow Saham Indonesia Plus Kelas O','https://bibit.id/reksadana/RD6651'],
        ['Grow SRI KEHATI Kelas O','https://bibit.id/reksadana/RD6649'],
        ['Jarvis Balanced Fund','https://bibit.id/reksadana/RD3191'],
        ['Jarvis Money Market Fund','https://bibit.id/reksadana/RD2046'],
        ['Majoris Pasar Uang Indonesia','https://bibit.id/reksadana/RD831'],
        ['Majoris Pasar Uang Syariah Indonesia','https://bibit.id/reksadana/RD832'],
        ['Majoris Saham Alokasi Dinamik Indonesia','https://bibit.id/reksadana/RD833'],
        ['Majoris Sukuk Negara Indonesia','https://bibit.id/reksadana/RD838'],
        ['Mandiri Indeks FTSE Indonesia ESG Kelas A','https://bibit.id/reksadana/RD4221'],
        ['Mandiri Investa Atraktif-Syariah','https://bibit.id/reksadana/RD853'],
        ['Mandiri Investa Dana Syariah Kelas A','https://bibit.id/reksadana/RD860'],
        ['Mandiri Investa Dana Utama Kelas D','https://bibit.id/reksadana/RD6639'],
        ['Mandiri Investa Pasar Uang Kelas A','https://bibit.id/reksadana/RD870'],
        ['Mandiri Investa Syariah Berimbang','https://bibit.id/reksadana/RD872'],
        ['Mandiri Pasar Uang Syariah Ekstra','https://bibit.id/reksadana/RD3173'],
        ['Manulife Dana Kas II Kelas A','https://bibit.id/reksadana/RD983'],
        ['Manulife Dana Kas Syariah','https://bibit.id/reksadana/RD984'],
        ['Manulife Dana Saham Kelas A','https://bibit.id/reksadana/RD985'],
        ['Manulife Obligasi Negara Indonesia II Kelas A','https://bibit.id/reksadana/RD994'],
        ['Manulife Obligasi Unggulan Kelas A','https://bibit.id/reksadana/RD3206'],
        ['Manulife Saham Andalan','https://bibit.id/reksadana/RD998'],
        ['Manulife Syariah Sektoral Amanah Kelas A','https://bibit.id/reksadana/RD1001'],
        ['Manulife USD Fixed Income Kelas A','https://bibit.id/reksadana/RD1003'],
        ['Principal Cash Fund','https://bibit.id/reksadana/RD479'],
        ['Principal Index IDX30 Kelas O','https://bibit.id/reksadana/RD707'],
        ['Principal Islamic Equity Growth Syariah','https://bibit.id/reksadana/RD487'],
        ['Schroder 90 Plus Equity Fund','https://bibit.id/reksadana/RD1538'],
        ['Schroder Dana Andalan II','https://bibit.id/reksadana/RD1539'],
        ['Schroder Dana Istimewa','https://bibit.id/reksadana/RD1541'],
        ['Schroder Dana Likuid','https://bibit.id/reksadana/RD1543'],
        ['Schroder Dana Likuid Syariah','https://bibit.id/reksadana/RD3454'],
        ['Schroder Dana Mantap Plus II','https://bibit.id/reksadana/RD1544'],
        ['Schroder Dana Prestasi','https://bibit.id/reksadana/RD1547'],
        ['Schroder Dana Prestasi Plus','https://bibit.id/reksadana/RD1548'],
        ['Schroder Dynamic Balanced Fund','https://bibit.id/reksadana/RD1551'],
        ['Schroder Global Sharia Equity Fund USD','https://bibit.id/reksadana/RD1743'],
        ['Schroder Syariah Balanced Fund','https://bibit.id/reksadana/RD1564'],
        ['Schroder USD Bond Fund Kelas A','https://bibit.id/reksadana/RD1565'],
        ['Simas Saham Unggulan','https://bibit.id/reksadana/RD1628'],
        ['Simas Satu','https://bibit.id/reksadana/RD1629'],
        ['Simas Syariah Unggulan','https://bibit.id/reksadana/RD1634'],
        ['Sucorinvest Bond Fund','https://bibit.id/reksadana/RD1436'],
        ['Sucorinvest Citra Dana Berimbang','https://bibit.id/reksadana/RD523'],
        ['Sucorinvest Equity Fund','https://bibit.id/reksadana/RD1653'],
        ['Sucorinvest Flexi Fund','https://bibit.id/reksadana/RD1655'],
        ['Sucorinvest IDX30','https://bibit.id/reksadana/RD5741'],
        ['Sucorinvest Maxi Fund','https://bibit.id/reksadana/RD1656'],
        ['Sucorinvest Money Market Fund','https://bibit.id/reksadana/RD1657'],
        ['Sucorinvest Premium Fund','https://bibit.id/reksadana/RD1658'],
        ['Sucorinvest Sharia Balanced Fund','https://bibit.id/reksadana/RD3194'],
        ['Sucorinvest Sharia Equity Fund','https://bibit.id/reksadana/RD1668'],
        ['Sucorinvest Sharia Money Market Fund','https://bibit.id/reksadana/RD1669'],
        ['Sucorinvest Sharia Sukuk Fund','https://bibit.id/reksadana/RD4046'],
        ['Sucorinvest Stable Fund','https://bibit.id/reksadana/RD3561'],
        ['TRAM Consumption Plus Kelas A','https://bibit.id/reksadana/RD1755'],
        ['TRAM Strategic Plus Kelas A','https://bibit.id/reksadana/RD1761'],
        ['TRIM Dana Tetap 2 Kelas A','https://bibit.id/reksadana/RD1763'],
        ['TRIM Kapital','https://bibit.id/reksadana/RD1764'],
        ['TRIM Kapital Plus','https://bibit.id/reksadana/RD1765'],
        ['TRIM Kas 2 Kelas A','https://bibit.id/reksadana/RD1766'],
        ['TRIM Syariah Saham','https://bibit.id/reksadana/RD1366'],
        ['Trimegah Dana Tetap Syariah Kelas A','https://bibit.id/reksadana/RD3480'],
        ['Trimegah FTSE Indonesia Low Volatility Factor Index','https://bibit.id/reksadana/RD3901'],
        ['Trimegah Kas Syariah','https://bibit.id/reksadana/RD1775'],
    ]


data_periods = ['1M', '3M', 'YTD', '1Y', '3Y', '5Y', '10Y', 'ALL']
pixel = 2

# Membuat scraper instance dan menjalankan scraping
scraper = Scraper(urls, data_periods, pixel, logger, debug_mode=False)
scraper.run()

downloader = ProspektusDownloader(logger)
downloader.download(urls)