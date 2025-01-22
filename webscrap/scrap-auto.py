import asyncio
from playwright.async_api import async_playwright
import time
from datetime import datetime
import csv

async def wait_for_chart_load(page):
    await page.wait_for_selector('svg', state='visible')
    await page.wait_for_selector('.reksa-value-head-nav', state='visible')
    await page.wait_for_selector('.navDate', state='visible')
    # Wait for animation to complete
    await asyncio.sleep(1)

async def scrape_period(page, period):
    start_time = time.time()
    data_points = []
    
    try:
        # Wait for period button and click
        button = await page.wait_for_selector(f'button[data-period="{period}"]', state='visible')
        await button.click()
        
        # Wait for all elements to load
        await wait_for_chart_load(page)
        
        graph = await page.query_selector('svg')
        box = await graph.bounding_box()
        graph_width = int(box['width'])
        start_offset = -graph_width // 2
        
        # Additional wait after graph size calculation
        await asyncio.sleep(0.5)
        
        for offset in range(start_offset, start_offset + graph_width, 15):
            await graph.hover(position={'x': offset + graph_width/2, 'y': box['height']/2})
            
            # Wait for data update after hover
            await page.wait_for_function("""
                () => {
                    const nav = document.querySelector('.reksa-value-head-nav');
                    const date = document.querySelector('.navDate');
                    return nav && date && nav.textContent && date.textContent;
                }
            """)
            
            value = await page.locator('.reksa-value-head-nav').text_content()
            date = await page.locator('.navDate').text_content()
            
            data_points.append({
                'period': period,
                'date': date,
                'value': value,
                'offset': offset
            })
            
            print(f"Period {period} - Offset {offset}: {date} = {value}")
            await asyncio.sleep(0.2)
            
    except Exception as e:
        print(f"Error in period {period}: {e}")
    finally:
        duration = time.time() - start_time
        save_to_csv(data_points, period)
        return period, duration, len(data_points)

def save_to_csv(data_points, period):
    filename = f'data_{period}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    with open(filename, 'w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=['period', 'date', 'value', 'offset'])
        writer.writeheader()
        writer.writerows(data_points)

async def main():
    total_start = time.time()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()
        
        pages = []
        for _ in range(7):
            page = await context.new_page()
            await page.goto('https://bibit.id/reksadana/RD66/avrist-ada-kas-mutiara')
            # Wait for initial page load
            await wait_for_chart_load(page)
            pages.append(page)
        
        periods = ['1M', '3M', 'YTD', '1Y', '3Y', '5Y', 'ALL']
        tasks = [scrape_period(pages[i], period) for i, period in enumerate(periods)]
        results = await asyncio.gather(*tasks)
        
        for page in pages:
            await page.close()
        await browser.close()

    total_duration = time.time() - total_start
    
    print("\nPerformance Summary:")
    print(f"Total execution time: {total_duration:.2f} seconds")
    for period, duration, count in results:
        print(f"{period}: {duration:.2f} seconds, {count} data points collected")

if __name__ == "__main__":
    asyncio.run(main())