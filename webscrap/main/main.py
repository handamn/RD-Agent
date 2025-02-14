from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from datetime import datetime, date, timedelta
import pandas as pd
import numpy as np
import os
import json
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed


class UnifiedLogger:
    """Unified logger untuk mencatat aktivitas dari multiple classes ke satu file log."""
    _instance = None
    
    def __new__(cls, log_dir="logs"):
        # Singleton pattern - memastikan hanya ada satu instance logger
        if cls._instance is None:
            cls._instance = super(UnifiedLogger, cls).__new__(cls)
            cls._instance.setup(log_dir)
        return cls._instance
    
    def setup(self, log_dir):
        """Setup awal logger."""
        os.makedirs(log_dir, exist_ok=True)
        log_filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_unified_scraping.log"
        self.LOG_FILE = os.path.join(log_dir, log_filename)
        self.log_info("=== Unified Logger Initialized ===")
    
    def log_info(self, message, status="INFO", source=None):
        """Menyimpan log ke file dengan format timestamp dan source."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        source_info = f"[{source}]" if source else ""
        log_message = f"[{timestamp}] [{status}] {source_info} {message}\n"

        with open(self.LOG_FILE, "a", encoding="utf-8") as log_file:
            log_file.write(log_message)


class Comparison_Data_Scrapper:
    def __init__(self, urls, pilih_tahun, mode_csv):
        self.urls = urls
        self.pilih_tahun = pilih_tahun
        self.mode_csv = mode_csv
        
        # Gunakan unified logger
        self.logger = UnifiedLogger()
        self.logger.log_info("Initializing Comparison_Data_Scrapper", source="Comparison_Data_Scrapper")
        
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        try:
            self.driver = webdriver.Chrome(options=options)
            self.log("Browser Chrome berhasil diinisialisasi")
        except Exception as e:
            self.log(f"Gagal menginisialisasi Chrome browser: {str(e)}", "ERROR")
            raise
            
    def log(self, message, status="INFO"):
        """Helper method untuk logging dengan source=Comparison_Data_Scrapper"""
        self.logger.log_info(message, status, source="Comparison_Data_Scrapper")

    def scrape_CDS_data(self):
        start_time = time.time()
        self.logger.log_info("===== Memulai proses scraping =====")
        
        try:
            for name, url in self.urls:
                self.logger.log_info(f"Memulai scraping untuk {name} dari {url}")
                self._scrape_CDS_single_url(name, url)
                
        except Exception as e:
            self.logger.log_info(f"Error dalam proses scraping utama: {str(e)}", "ERROR")
        finally:
            self.driver.quit()
            duration = time.time() - start_time
            self.logger.log_info(f"===== Proses scraping selesai dalam {duration:.2f} detik =====")

    def _scrape_CDS_single_url(self, name, url):
        try:
            self.logger.log_info(f"Mengakses URL: {url}")
            self.driver.get(url)
            time.sleep(5)

            self.logger.log_info("Mencari dan mengklik tombol menu")
            button = self.driver.find_element(By.CSS_SELECTOR, ".tertiary-btn.fin-size-small.menuBtn.rounded.yf-15mk0m")
            button.click()
            time.sleep(2)

            self.logger.log_info("Menunggu dialog menu muncul")
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".dialog-container.menu-surface-dialog.modal.yf-9a5vow"))
            )

            buttons = self.driver.find_elements(By.CSS_SELECTOR, ".quickpicks.yf-1th5n0r .tertiary-btn.fin-size-small.tw-w-full.tw-justify-center.rounded.yf-15mk0m")
            values = [button.text for button in buttons]
            self.logger.log_info(f"Opsi tahun yang tersedia: {values}")

            if self.pilih_tahun in values:
                index = values.index(self.pilih_tahun)
                self.logger.log_info(f"Memilih tahun {self.pilih_tahun}")
                buttons[index].click()
                time.sleep(2)

                self.logger.log_info("Mengekstrak data tabel")
                headers = [header.text.strip() for header in self.driver.find_elements(By.CSS_SELECTOR, ".table.yf-1jecxey.noDl th")]
                table = self.driver.find_element(By.CSS_SELECTOR, ".table.yf-1jecxey.noDl")
                rows = table.find_elements(By.TAG_NAME, "tr")
                data = []
                for row in rows:
                    cols = row.find_elements(By.TAG_NAME, "td")
                    cols = [col.text.strip() for col in cols]
                    data.append(cols)

                df = pd.DataFrame(data, columns=headers)
                df.replace("-", np.nan, inplace=True)
                df = df.drop(0).reset_index(drop=True)
                df['Date'] = pd.to_datetime(df['Date'], format='%b %d, %Y', errors='coerce')
                df['Date'] = df['Date'].dt.date
                df = df[::-1]
                
                # Handle CSV file
                csv_filename = f"database/comparison/{name}.csv"
                if os.path.exists(csv_filename):
                    self.logger.log_info(f"Memperbarui file CSV yang ada: {csv_filename}")
                    existing_df = pd.read_csv(csv_filename)
                    existing_df['Date'] = pd.to_datetime(existing_df['Date']).dt.date
                    combined_df = pd.concat([existing_df, df])
                    combined_df = combined_df.drop_duplicates(subset=['Date'], keep='last')
                    combined_df = combined_df.sort_values('Date')
                    combined_df.to_csv(csv_filename, index=False)
                    self.logger.log_info(f"Data CSV diperbarui. {len(combined_df) - len(existing_df)} baris baru ditambahkan")
                else:
                    self.logger.log_info(f"Membuat file CSV baru: {csv_filename}")
                    df.to_csv(csv_filename, index=False)
                    self.logger.log_info(f"File CSV dibuat dengan {len(df)} baris data")

                # Handle JSON file
                json_filename = f"database/comparison/{name}.json"
                self.logger.log_info(f"Memproses data untuk format JSON: {json_filename}")
                new_json_data = {
                    "benchmark_name": name,
                    "historical_data": []
                }
                
                def safe_float_convert(value):
                    if pd.isna(value):
                        return None
                    try:
                        return float(str(value).replace(',', ''))
                    except (ValueError, TypeError):
                        try:
                            return float(str(value).replace(',', ''))
                        except (ValueError, TypeError):
                            return None
                
                for _, row in df.iterrows():
                    json_row = {
                        "date": str(row['Date']),
                        "open": safe_float_convert(row['Open']),
                        "high": safe_float_convert(row['High']),
                        "low": safe_float_convert(row['Low']),
                        "close": safe_float_convert(row['Close']),
                        "adj_close": safe_float_convert(row['Adj Close']),
                        "volume": safe_float_convert(row['Volume'])
                    }
                    new_json_data["historical_data"].append(json_row)

                if os.path.exists(json_filename):
                    self.logger.log_info("Memperbarui file JSON yang ada")
                    with open(json_filename, 'r') as f:
                        existing_json = json.load(f)
                    
                    existing_data_dict = {item['date']: item for item in existing_json['historical_data']}
                    
                    for new_item in new_json_data['historical_data']:
                        existing_data_dict[new_item['date']] = new_item
                    
                    combined_data = list(existing_data_dict.values())
                    combined_data.sort(key=lambda x: x['date'])
                    
                    existing_json['historical_data'] = combined_data
                    
                    with open(json_filename, 'w') as f:
                        json.dump(existing_json, f, indent=2)
                    
                    self.logger.log_info(f"Data JSON diperbarui dengan total {len(combined_data)} records")
                else:
                    self.logger.log_info("Membuat file JSON baru")
                    with open(json_filename, 'w') as f:
                        json.dump(new_json_data, f, indent=2)
                    self.logger.log_info(f"File JSON dibuat dengan {len(new_json_data['historical_data'])} records")

                self.logger.log_info(f"Scraping selesai untuk {name}")
            else:
                self.logger.log_info(f"Tahun {self.pilih_tahun} tidak ditemukan untuk {name}", "WARNING")
        except Exception as e:
            self.logger.log_info(f"Error saat scraping {name}: {str(e)}", "ERROR")
            raise


class Mutual_Fund_Data_Scraper:
    def __init__(self, urls, data_periods, pixel, logger, debug_mode=False):
        """Inisialisasi scraper dengan daftar URL, periode, pixel, dan logger eksternal."""
        self.urls = urls
        self.data_periods = data_periods
        self.pixel = pixel
        self.logger = UnifiedLogger()
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
            self.logger.log_info("Beralih ke mode AUM...")
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
                        f"{mode} | Periode {period} | Kursor {offset} | Tanggal: {tanggal_navdate} | Data: {updated_data}", 
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
        """Memproses dan menyimpan data hasil scraping ke dalam CSV dan JSON, termasuk informasi mata uang.
        Memastikan tidak ada duplikasi sebelum menyimpan data baru."""
        
        processed_data = {}

        # Proses data baru dari mode1_data (NAV)
        for entry in mode1_data:
            try:
                tanggal_obj = self.parse_tanggal(entry['tanggal'])
                tanggal_str = tanggal_obj.strftime("%Y-%m-%d")
                data_number, currency = self.convert_to_number(entry['data'])

                if tanggal_str not in processed_data:
                    processed_data[tanggal_str] = {'NAV': 'NA', 'AUM': 'NA', 'currency': currency}
                processed_data[tanggal_str]['NAV'] = data_number
            except ValueError:
                self.logger.log_info(f"Gagal mengonversi data NAV: {entry['data']}", "ERROR")

        # Proses data baru dari mode2_data (AUM)
        for entry in mode2_data:
            try:
                tanggal_obj = self.parse_tanggal(entry['tanggal'])
                tanggal_str = tanggal_obj.strftime("%Y-%m-%d")
                data_number, currency = self.convert_to_number(entry['data'])

                if tanggal_str not in processed_data:
                    processed_data[tanggal_str] = {'NAV': 'NA', 'AUM': 'NA', 'currency': currency}
                processed_data[tanggal_str]['AUM'] = data_number
            except ValueError:
                self.logger.log_info(f"[ERROR] Gagal mengonversi data AUM: {entry['data']}", "ERROR")

        # Handle CSV file
        csv_file = os.path.join(self.database_dir, f"{kode}.csv")
        
        if os.path.exists(csv_file):
            existing_data = {}

            with open(csv_file, mode='r', newline='', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    tanggal = row['tanggal']
                    existing_data[tanggal] = {
                        'NAV': row['NAV'],
                        'AUM': row['AUM'],
                        'currency': row['currency']
                    }

            # Gabungkan data lama dengan data baru tanpa duplikasi
            for tanggal, values in processed_data.items():
                if tanggal in existing_data:
                    if values['NAV'] != 'NA':
                        existing_data[tanggal]['NAV'] = values['NAV']
                    if values['AUM'] != 'NA':
                        existing_data[tanggal]['AUM'] = values['AUM']
                    if existing_data[tanggal]['currency'] == 'NA':
                        existing_data[tanggal]['currency'] = values['currency']
                else:
                    existing_data[tanggal] = values
        else:
            existing_data = processed_data

        # Urutkan data berdasarkan tanggal
        sorted_dates = sorted(existing_data.keys())

        # Simpan data ke dalam CSV
        with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=['tanggal', 'NAV', 'AUM', 'currency'])
            writer.writeheader()

            for date in sorted_dates:
                writer.writerow({
                    'tanggal': date,
                    'NAV': existing_data[date]['NAV'],
                    'AUM': existing_data[date]['AUM'],
                    'currency': existing_data[date]['currency']
                })

        # Handle JSON file
        json_file = os.path.join(self.database_dir, f"{kode}.json")
        
        def convert_value(value):
            """Konversi nilai untuk format JSON dengan mempertahankan konsistensi None"""
            if value == 'NA' or value is None:
                return None
            try:
                return float(value) if isinstance(value, (str, int, float)) else None
            except (ValueError, TypeError):
                return None

        # Prepare new JSON data
        new_json_data = {
            "benchmark_name": kode,
            "historical_data": []
        }

        # Convert existing data to JSON format
        for date in sorted_dates:
            json_entry = {
                "date": date,
                "nav": convert_value(existing_data[date]['NAV']),
                "aum": convert_value(existing_data[date]['AUM']),
                "currency": existing_data[date]['currency'] if existing_data[date]['currency'] != 'NA' else None
            }
            new_json_data["historical_data"].append(json_entry)

        if os.path.exists(json_file):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    existing_json = json.load(f)
                    
                # Create dictionary for quick lookup of existing data
                existing_data_dict = {
                    item['date']: item 
                    for item in existing_json['historical_data']
                }
                
                # Update with new data
                for new_item in new_json_data['historical_data']:
                    existing_data_dict[new_item['date']] = new_item
                
                # Convert back to list and sort by date
                combined_data = list(existing_data_dict.values())
                combined_data.sort(key=lambda x: x['date'])
                
                # Update the JSON structure
                existing_json['historical_data'] = combined_data
                
                # Save updated JSON
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(existing_json, f, indent=2, ensure_ascii=False)
            except Exception as e:
                self.logger.log_info(f"[ERROR] Gagal memperbarui file JSON: {str(e)}", "ERROR")
        else:
            # Create new JSON file
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(new_json_data, f, indent=2, ensure_ascii=False)

        self.logger.log_info(f"Data {kode} berhasil diperbarui dan disimpan ke {csv_file} dan {json_file}")


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
            with ThreadPoolExecutor(max_workers=3) as executor:  # 3 worker threads, bisa disesuaikan
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



today = date.today()
# today = date(2025, 2, 10)

urls = [
    ['IHSG', 'https://finance.yahoo.com/quote/%5EJKSE/history/?p=%5EJKSE'],
    ['LQ45', 'https://finance.yahoo.com/quote/%5EJKLQ45/history/']
]

for kode, url in urls:
    csv_file_recent = f"database/comparison/{kode}.csv"
    df = pd.read_csv(csv_file_recent)
    latest_data = df.iloc[-1].tolist()

    latest_data_date = latest_data[0]
    latest_data_value = latest_data[-1]


    LD_years, LD_months, LD_dates = latest_data_date.split("-")
    date_database = date(int(LD_years), int(LD_months), int(LD_dates))

    delta_date = today - date_database

    if delta_date < timedelta(0):
            print("tidak proses")
    else:
        # Daftar periode berdasarkan hari
        period_map = [
            (1, '1D'),
            (5, '5D'),
            (90, '3M'),
            (180, '6M'),
            (360, '1Y'),
            (1800, '5Y')
        ]

        # Default jika lebih dari 5 tahun
        data_periods = 'Max'
        
        # Loop untuk mencari rentang yang sesuai
        for days, periods in period_map:
            if delta_date <= timedelta(days=days):
                data_periods = periods
                break  # Stop loop setelah menemukan rentang yang sesuai


adam = Comparison_Data_Scrapper(urls, data_periods, 'w')
adam.scrape_CDS_data()