from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import pandas as pd
import time
import csv

def scrape_web_data(url, pilih_tahun):
    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--headless")
    
    try:
        # Initialize webdriver
        driver = webdriver.Chrome(service=Service(), options=chrome_options)
        print(f"Membuka URL: {url}")
        driver.get(url)
        
        # Wait and click menu button
        menu_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CLASS_NAME, "yf-15mk0m"))
        )
        menu_button.click()
        print("Menu button diklik")
        
        # Wait for dialog box
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "yf-9a5vow"))
        )
        print("Dialog box terbuka")
        
        # Get all buttons in quickpicks
        quickpicks_buttons = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, ".yf-1th5n0r button.yf-15mk0m")
            )
        )
        
        # Get values from buttons
        button_values = []
        target_button = None
        
        for button in quickpicks_buttons:
            value = button.get_attribute("value")
            button_values.append(value)
            if value == pilih_tahun:
                target_button = button
        
        print(f"Nilai button yang tersedia: {button_values}")
        
        if target_button:
            print(f"Button dengan nilai {pilih_tahun} ditemukan")
            target_button.click()
            print("Button diklik")
            
            # Wait for table to load
            table = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "yf-1jecxey"))
            )
            
            # Get headers
            headers = []
            header_elements = table.find_elements(By.TAG_NAME, "th")
            for header in header_elements:
                headers.append(header.text)
            
            # Get table data
            rows = table.find_elements(By.TAG_NAME, "tr")
            data = []
            
            for row in rows[1:]:  # Skip header row
                cols = row.find_elements(By.TAG_NAME, "td")
                row_data = []
                for col in cols:
                    value = col.text
                    # Replace "-" with NaN
                    row_data.append(None if value == "-" else value)
                data.append(row_data)
            
            # Create DataFrame
            df = pd.DataFrame(data, columns=headers)
            
            # Save to CSV
            csv_filename = f"data_scraping_{pilih_tahun}.csv"
            df.to_csv(csv_filename, index=False)
            print(f"\nData berhasil disimpan ke {csv_filename}")
            
            # Print the data
            print("\nData yang diperoleh:")
            print(df)
            
        else:
            print(f"Tidak ditemukan button dengan nilai {pilih_tahun}")
            
    except TimeoutException:
        print("Timeout: Elemen tidak ditemukan dalam waktu yang ditentukan")
    except Exception as e:
        print(f"Terjadi kesalahan: {str(e)}")
    finally:
        driver.quit()

url = "https://finance.yahoo.com/quote/%5EJKSE/history/?p=%5EJKSE"
pilih_tahun = "5D"
scrape_web_data(url, pilih_tahun)

