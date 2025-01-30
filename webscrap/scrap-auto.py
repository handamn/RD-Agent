from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import *
import time
import logging
import traceback

class BibitScraper:
    def __init__(self):
        self.options = webdriver.ChromeOptions()
        # Basic options
        self.options.add_argument('--headless=new')  # Using new headless mode
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
        """Safely click an element with multiple attempts and methods."""
        for attempt in range(max_attempts):
            try:
                # Try different click methods
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
        """Initialize the webdriver with proper error handling."""
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
        """Safely get an element with retries."""
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
        """Get a single data point from the graph."""
        try:
            # Move to element
            actions = ActionChains(self.driver)
            actions.move_to_element_with_offset(graph_element, offset, 0)
            actions.perform()
            
            # Small wait for tooltip to update
            time.sleep(0.2)
            
            # Get data
            value = self.get_element_safely(
                By.CSS_SELECTOR, 
                '.reksa-value-head-nav.ChartHead_reksa-value-head-nav__LCCdL'
            )
            date = self.get_element_safely(By.CSS_SELECTOR, '.navDate')
            
            if value and date:
                return {
                    'value': value.text,
                    'date': date.text
                }
            return None
            
        except Exception as e:
            logging.debug(f"Failed to get data point at offset {offset}: {str(e)}")
            return None

    def scrape_period(self, period):
        """Scrape data for a specific period."""
        try:
            logging.info(f"Starting to scrape period: {period}")
            
            # Find and click period button
            button = self.get_element_safely(
                By.CSS_SELECTOR,
                f'button[data-period="{period}"]',
                timeout=15
            )
            
            if not button:
                logging.error(f"Could not find button for period {period}")
                return []
                
            # Scroll into view and click
            self.driver.execute_script("arguments[0].scrollIntoView(true);", button)
            time.sleep(1)
            
            if not self.safe_click(button):
                logging.error(f"Failed to click button for period {period}")
                return []
            
            # Wait for graph to update
            time.sleep(2)
            
            # Get graph element
            graph = self.get_element_safely(By.TAG_NAME, 'svg', timeout=15)
            if not graph:
                logging.error("Could not find graph element")
                return []
            
            # Calculate points to sample
            width = int(graph.size['width'])
            start_offset = -width // 2
            step = 20  # Increased step size for stability
            
            results = []
            for offset in range(start_offset, start_offset + width, step):
                data = self.get_graph_data_point(graph, offset)
                if data:
                    data['period'] = period
                    data['offset'] = offset
                    results.append(data)
            
            logging.info(f"Successfully collected {len(results)} points for period {period}")
            return results
            
        except Exception as e:
            logging.error(f"Error in scrape_period for {period}: {str(e)}\n{traceback.format_exc()}")
            return []

    def scrape(self, url):
        """Main scraping function."""
        if not self.initialize_driver():
            return []
            
        try:
            logging.info(f"Navigating to {url}")
            self.driver.get(url)
            time.sleep(3)  # Wait for initial page load
            
            data_periods = ['ALL', '1M', '3M', 'YTD', '3Y', '5Y']
            all_results = []
            
            for period in data_periods:
                results = self.scrape_period(period)
                all_results.extend(results)
                time.sleep(1)  # Break between periods
                
            return all_results
            
        except Exception as e:
            logging.error(f"Scraping failed: {str(e)}\n{traceback.format_exc()}")
            return []
        finally:
            if self.driver:
                self.driver.quit()

def main():
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    start_time = time.time()
    
    scraper = BibitScraper()
    results = scraper.scrape('https://bibit.id/reksadana/RD66/avrist-ada-kas-mutiara')
    
    end_time = time.time()
    duration = end_time - start_time
    
    print(f"\nResults:")
    print(f"Total data points: {len(results)}")
    print(f"Duration: {duration:.2f} seconds")
    
    return results

if __name__ == "__main__":
    results = main()