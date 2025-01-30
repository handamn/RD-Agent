from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import *
from bs4 import BeautifulSoup
import time
import logging
import traceback
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures

class HybridScraper:
    def __init__(self):
        self.options = webdriver.ChromeOptions()
        # Basic options
        self.options.add_argument('--headless=new')
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--disable-dev-shm-usage')
        self.options.add_argument('--disable-gpu')
        self.options.add_argument('--window-size=1920,1080')
        
        # Performance optimizations
        self.options.add_argument('--disable-javascript-harmony-shipping')
        self.options.add_argument('--disable-features=NetworkService')
        self.options.add_argument('--disable-dev-tools')
        self.options.add_argument('--dns-prefetch-disable')
        self.options.add_argument('--disable-browser-side-navigation')
        
        # Memory optimizations
        self.options.add_argument('--disable-extensions')
        self.options.add_argument('--disable-application-cache')
        self.options.add_argument('--aggressive-cache-discard')
        self.options.add_argument('--disable-cache')
        
        self.driver = None
        self.wait = None
        self.current_period = None
        self.data_cache = {}

    def initialize_driver(self):
        if self.driver:
            self.driver.quit()
        self.driver = webdriver.Chrome(options=self.options)
        self.driver.set_page_load_timeout(30)
        self.wait = WebDriverWait(self.driver, 10)
        return True

    def parse_tooltip_data(self, html_content):
        """Parse tooltip data using BeautifulSoup"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            value_element = soup.select_one('.reksa-value-head-nav.ChartHead_reksa-value-head-nav__LCCdL')
            date_element = soup.select_one('.navDate')
            
            if value_element and date_element:
                return {
                    'value': value_element.text.replace('Rp', '').strip(),
                    'date': date_element.text.strip()
                }
            return None
        except Exception as e:
            logging.debug(f"Failed to parse tooltip: {str(e)}")
            return None

    def get_data_point(self, graph_element, offset):
        """Get single data point with optimized parsing"""
        try:
            actions = ActionChains(self.driver)
            actions.move_to_element_with_offset(graph_element, offset, 0)
            actions.perform()
            
            # Minimal wait
            time.sleep(0.1)
            
            # Get tooltip content directly from DOM
            tooltip_html = self.driver.find_element(By.CSS_SELECTOR, '.ChartHead_chart-head__RXkYG').get_attribute('innerHTML')
            
            data = self.parse_tooltip_data(tooltip_html)
            if data:
                data['offset'] = offset
                data['period'] = self.current_period
                return data
            return None
            
        except Exception as e:
            logging.debug(f"Failed to get data point at offset {offset}: {str(e)}")
            return None

    def process_data_chunk(self, graph_element, offsets):
        """Process a chunk of offsets in parallel"""
        results = []
        for offset in offsets:
            data = self.get_data_point(graph_element, offset)
            if data:
                results.append(data)
        return results

    def scrape_period(self, period):
        """Scrape data for a period using parallel processing"""
        try:
            self.current_period = period
            logging.info(f"Processing period: {period}")
            
            # Click period button
            button = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, f'button[data-period="{period}"]'))
            )
            self.driver.execute_script("arguments[0].click();", button)
            time.sleep(1)  # Wait for graph update
            
            # Get graph element
            graph = self.wait.until(
                EC.presence_of_element_located((By.TAG_NAME, 'svg'))
            )
            
            width = int(graph.size['width'])
            start_offset = -width // 2
            offsets = range(start_offset, start_offset + width, 5)  # 5 pixel steps as requested
            
            # Split offsets into chunks for parallel processing
            chunk_size = 20
            offset_chunks = [list(offsets[i:i + chunk_size]) for i in range(0, len(offsets), chunk_size)]
            
            results = []
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = []
                for chunk in offset_chunks:
                    future = executor.submit(self.process_data_chunk, graph, chunk)
                    futures.append(future)
                
                for future in concurrent.futures.as_completed(futures):
                    chunk_results = future.result()
                    results.extend(chunk_results)
            
            # Sort results by date
            results.sort(key=lambda x: datetime.strptime(x['date'], '%d %b %Y'))
            
            # Cache results
            self.data_cache[period] = results
            
            # Print results
            self.print_period_data(results, period)
            
            return results
            
        except Exception as e:
            logging.error(f"Error in period {period}: {str(e)}")
            return []

    def print_period_data(self, results, period):
        """Print formatted data for a period"""
        if not results:
            print(f"\nNo data for period: {period}")
            return
            
        print(f"\nPeriod: {period}")
        print("-" * 60)
        print(f"{'Date':<20} {'Value':>15} {'Offset':>10}")
        print("-" * 60)
        
        for result in sorted(results, key=lambda x: datetime.strptime(x['date'], '%d %b %Y')):
            print(f"{result['date']:<20} {result['value']:>15} {result['offset']:>10}")
        
        print("-" * 60)
        print(f"Total points: {len(results)}")

    def scrape(self, url):
        """Main scraping function with optimized workflow"""
        try:
            self.initialize_driver()
            print(f"\nStarting scrape at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"URL: {url}")
            print("=" * 60)
            
            self.driver.get(url)
            time.sleep(2)  # Initial load
            
            periods = ['ALL', '1M', '3M', 'YTD', '3Y', '5Y']
            all_results = []
            
            for period in periods:
                results = self.scrape_period(period)
                all_results.extend(results)
            
            return all_results
            
        except Exception as e:
            logging.error(f"Scraping failed: {str(e)}")
            return []
        finally:
            if self.driver:
                self.driver.quit()

def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    start_time = time.time()
    
    scraper = HybridScraper()
    results = scraper.scrape('https://bibit.id/reksadana/RD66/avrist-ada-kas-mutiara')
    
    end_time = time.time()
    duration = end_time - start_time
    
    print("\nScraping Summary")
    print("=" * 60)
    print(f"Total data points: {len(results)}")
    print(f"Duration: {duration:.2f} seconds")
    print(f"Speed: {len(results)/duration:.2f} points/second")
    print("=" * 60)
    
    return results

if __name__ == "__main__":
    results = main()