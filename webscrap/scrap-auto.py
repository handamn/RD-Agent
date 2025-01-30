from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from concurrent.futures import ThreadPoolExecutor
import time
import asyncio
import aiohttp

class BibitScraper:
    def __init__(self):
        self.options = webdriver.ChromeOptions()
        self.options.add_argument('--disable-gpu')
        self.options.add_argument('--disable-dev-shm-usage')
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--headless')
        self.options.add_argument('--disable-images')  # Disable image loading
        self.options.add_argument('--disable-javascript-harmony-shipping')
        self.options.add_experimental_option('excludeSwitches', ['enable-logging'])
        
        # Add performance preferences
        self.options.add_experimental_option('prefs', {
            'profile.default_content_setting_values': {
                'cookies': 2,
                'images': 2,
                'javascript': 1,
                'plugins': 2,
                'popups': 2,
                'geolocation': 2,
                'notifications': 2,
                'auto_select_certificate': 2,
                'fullscreen': 2,
                'mouselock': 2,
                'mixed_script': 2,
                'media_stream': 2,
                'media_stream_mic': 2,
                'media_stream_camera': 2,
                'protocol_handlers': 2,
                'ppapi_broker': 2,
                'automatic_downloads': 2,
                'midi_sysex': 2,
                'push_messaging': 2,
                'ssl_cert_decisions': 2,
                'metro_switch_to_desktop': 2,
                'protected_media_identifier': 2,
                'app_banner': 2,
                'site_engagement': 2,
                'durable_storage': 2
            }
        })
        
        self.service = webdriver.chrome.service.Service()
        self.driver = None
        
    async def setup(self):
        self.driver = webdriver.Chrome(service=self.service, options=self.options)
        self.driver.set_page_load_timeout(10)
        self.wait = WebDriverWait(self.driver, 5)
        
    def get_graph_data(self, period, offset, graph_element):
        try:
            actions = ActionChains(self.driver)
            actions.move_to_element_with_offset(graph_element, offset, 0).perform()
            
            updated_data = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.reksa-value-head-nav.ChartHead_reksa-value-head-nav__LCCdL'))
            ).text

            tanggal_navdate = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.navDate'))
            ).text

            return {
                'period': period,
                'offset': offset,
                'date': tanggal_navdate,
                'value': updated_data
            }
        except Exception as e:
            return None

    async def scrape_period(self, period):
        try:
            button = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, f'button[data-period="{period}"]'))
            )
            button.click()
            
            # Reduced sleep time
            time.sleep(0.5)
            
            graph_element = self.driver.find_element(By.TAG_NAME, 'svg')
            graph_width = int(graph_element.size['width'])
            start_offset = -graph_width // 2
            
            # Use ThreadPoolExecutor for parallel processing of graph points
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = []
                for offset in range(start_offset, start_offset + graph_width, 10):  # Increased step size
                    futures.append(
                        executor.submit(self.get_graph_data, period, offset, graph_element)
                    )
                
                results = [future.result() for future in futures if future.result() is not None]
                return results
                
        except Exception as e:
            print(f"Error scraping period {period}: {e}")
            return []

    async def scrape_all(self, url):
        await self.setup()
        self.driver.get(url)
        
        data_periods = ['ALL', '1M', '3M', 'YTD', '3Y', '5Y']
        all_results = []
        
        for period in data_periods:
            results = await self.scrape_period(period)
            all_results.extend(results)
        
        self.driver.quit()
        return all_results

async def main():
    start_time = time.time()
    
    scraper = BibitScraper()
    results = await scraper.scrape_all('https://bibit.id/reksadana/RD66/avrist-ada-kas-mutiara')
    
    end_time = time.time()
    duration = end_time - start_time
    
    print(f"Scraped {len(results)} data points")
    print(f"Duration: {duration:.2f} seconds")
    return results

if __name__ == "__main__":
    asyncio.run(main())