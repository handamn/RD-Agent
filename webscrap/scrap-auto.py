from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import *
import time
import logging
import traceback
from datetime import datetime

class BibitScraper:
    def __init__(self):
        self.options = webdriver.ChromeOptions()
        # Basic options
        self.options.add_argument('--headless=new')
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--disable-dev-shm-usage')
        
        # Performance options
        self.options.add_argument('--disable-gpu')
        self.options.add_argument('--disable-software-rasterizer')
        self.options.add_argument('--disable-extensions')
        
        # Memory options
        self.options.add_argument('--disable-application-cache')
        self.options.add_argument('--disable-features=NetworkService')
        
        # Window options
        self.options.add_argument('--window-size=1920,1080')
        self.options.add_argument("--hide-scrollbars")
        
        # Additional stability options
        self.options.add_argument('--ignore-certificate-errors')
        self.options.add_argument('--disable-popup-blocking')
        self.options.add_argument('--disable-notifications')
        
        self.driver = None
        self.wait = None

    def safe_click(self, element, max_attempts=3):
        for attempt in range(max_attempts):
            try:
                if attempt == 0:
                    element.click()
                elif attempt == 1:
                    ActionChains(self.driver).move_to_element(element).click().perform()
                else:
                    self.driver.execute_script("arguments[0].click();", element)
                return True
            except Exception as e:
                if attempt == max_attempts - 1:
                    logging.error(f"Failed to click element after {max_attempts} attempts: {str(e)}")
                    return False
                time.sleep(1)
        return False

    def initialize_driver(self):
        try:
            if self.driver:
                self.driver.quit()
            
            self.driver = webdriver.Chrome(options=self.options)
            self.driver.set_page_load_timeout(30)
            self.wait = WebDriverWait(self.driver, 15)
            return True
        except Exception as e:
            logging.error(f"Failed to initialize driver: {str(e)}")
            return False

    def get_element_safely(self, by, selector, timeout=10, retries=3):
        for attempt in range(retries):
            try:
                element = WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((by, selector))
                )
                return element
            except Exception as e:
                if attempt == retries - 1:
                    logging.error(f"Failed to find element {selector} after {retries} attempts: {str(e)}")
                    return None
                time.sleep(1)
        return None

    def get_graph_data_point(self, graph_element, offset):
        try:
            actions = ActionChains(self.driver)
            actions.move_to_element_with_offset(graph_element, offset, 0)
            actions.perform()
            
            time.sleep(0.2)
            
            value = self.get_element_safely(
                By.CSS_SELECTOR, 
                '.reksa-value-head-nav.ChartHead_reksa-value-head-nav__LCCdL'
            )
            date = self.get_element_safely(By.CSS_SELECTOR, '.navDate')
            
            if value and date:
                return {
                    'value': value.text.replace('Rp', '').strip(),
                    'date': date.text
                }
            return None
            
        except Exception as e:
            logging.debug(f"Failed to get data point at offset {offset}: {str(e)}")
            return None

    def print_period_summary(self, results, period):
        if not results:
            print(f"\nNo data found for period {period}")
            return
            
        print(f"\nPeriod: {period}")
        print("-" * 50)
        print(f"{'Date':<20} {'Value':>15}")
        print("-" * 50)
        
        for result in results:
            print(f"{result['date']:<20} {result['value']:>15}")
        
        print("-" * 50)
        print(f"Total data points for {period}: {len(results)}")

    def scrape_period(self, period):
        try:
            logging.info(f"Starting to scrape period: {period}")
            
            button = self.get_element_safely(
                By.CSS_SELECTOR,
                f'button[data-period="{period}"]',
                timeout=15
            )
            
            if not button:
                logging.error(f"Could not find button for period {period}")
                return []
                
            self.driver.execute_script("arguments[0].scrollIntoView(true);", button)
            time.sleep(1)
            
            if not self.safe_click(button):
                logging.error(f"Failed to click button for period {period}")
                return []
            
            time.sleep(2)
            
            graph = self.get_element_safely(By.TAG_NAME, 'svg', timeout=15)
            if not graph:
                logging.error("Could not find graph element")
                return []
            
            width = int(graph.size['width'])
            start_offset = -width // 2
            step = 5
            
            results = []
            for offset in range(start_offset, start_offset + width, step):
                data = self.get_graph_data_point(graph, offset)
                if data:
                    data['period'] = period
                    data['offset'] = offset
                    results.append(data)
            
            # Print results for this period
            self.print_period_summary(results, period)
            
            logging.info(f"Successfully collected {len(results)} points for period {period}")
            return results
            
        except Exception as e:
            logging.error(f"Error in scrape_period for {period}: {str(e)}\n{traceback.format_exc()}")
            return []

    def scrape(self, url):
        if not self.initialize_driver():
            return []
            
        try:
            print(f"\nStarting scraping at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"URL: {url}")
            print("=" * 50)
            
            logging.info(f"Navigating to {url}")
            self.driver.get(url)
            time.sleep(3)
            
            data_periods = ['ALL', '1M', '3M', 'YTD', '3Y', '5Y']
            all_results = []
            
            for period in data_periods:
                results = self.scrape_period(period)
                all_results.extend(results)
                time.sleep(1)
                
            return all_results
            
        except Exception as e:
            logging.error(f"Scraping failed: {str(e)}\n{traceback.format_exc()}")
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
    
    scraper = BibitScraper()
    results = scraper.scrape('https://bibit.id/reksadana/RD66/avrist-ada-kas-mutiara')
    
    end_time = time.time()
    duration = end_time - start_time
    
    print("\nScraping Summary:")
    print("=" * 50)
    print(f"Total data points: {len(results)}")
    print(f"Duration: {duration:.2f} seconds")
    print(f"Average time per data point: {(duration/len(results) if results else 0):.2f} seconds")
    print("=" * 50)
    
    return results

if __name__ == "__main__":
    results = main()