import asyncio
from playwright.async_api import async_playwright
import time
from datetime import datetime

async def scrape_period(page, period):
    start_time = time.time()
    try:
        button = await page.wait_for_selector(f'button[data-period="{period}"]')
        await button.click()
        
        await page.wait_for_selector('svg')
        graph = await page.query_selector('svg')
        box = await graph.bounding_box()
        graph_width = int(box['width'])
        start_offset = -graph_width // 2
        
        for offset in range(start_offset, start_offset + graph_width, 5):
            await graph.hover(position={'x': offset + graph_width/2, 'y': box['height']/2})
            value = await page.locator('.reksa-value-head-nav').text_content()
            date = await page.locator('.navDate').text_content()
            print(f"Period {period} - Offset {offset}: {date} = {value}")
            await asyncio.sleep(0.1)
            
    except Exception as e:
        print(f"Error in period {period}: {e}")
    finally:
        duration = time.time() - start_time
        print(f"Period {period} completed in {duration:.2f} seconds")
        return period, duration

async def main():
    total_start = time.time()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()
        
        pages = []
        for _ in range(7):
            page = await context.new_page()
            await page.goto('https://bibit.id/reksadana/RD66/avrist-ada-kas-mutiara')
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
    for period, duration in results:
        print(f"{period}: {duration:.2f} seconds")

if __name__ == "__main__":
    asyncio.run(main())