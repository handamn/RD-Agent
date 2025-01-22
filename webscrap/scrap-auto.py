import asyncio
from playwright.async_api import async_playwright
import time
from datetime import datetime
import csv

async def wait_for_chart_load(page):
    """
    Menunggu grafik dan elemen terkait sepenuhnya dimuat.
    """
    await page.wait_for_selector('svg', state='visible', timeout=10000)
    await page.wait_for_selector('.reksa-value-head-nav', state='visible', timeout=10000)
    await page.wait_for_selector('.navDate', state='visible', timeout=10000)
    await asyncio.sleep(1)  # Tunggu animasi selesai

async def scrape_period(page, period):
    """
    Scrape data untuk satu periode tertentu.
    """
    start_time = time.time()
    data_points = []
    max_retries = 3  # Jumlah maksimal retry jika terjadi error
    
    try:
        # Klik tombol periode
        button = await page.wait_for_selector(f'button[data-period="{period}"]', state='visible', timeout=10000)
        await button.click()
        
        # Tunggu grafik dimuat
        await wait_for_chart_load(page)
        
        # Dapatkan dimensi grafik
        graph = await page.query_selector('svg')
        box = await graph.bounding_box()
        graph_width = int(box['width'])
        
        # Sesuaikan rentang offset secara manual
        start_offset = -509  # Sesuaikan dengan script sequence
        end_offset = 506     # Sesuaikan dengan script sequence
        
        print(f"Graph width: {graph_width}, Start offset: {start_offset}, End offset: {end_offset}")
        
        # Loop melalui offset grafik
        for offset in range(start_offset, end_offset, 5):
            for retry in range(max_retries):
                try:
                    # Nonaktifkan pointer-events pada elemen yang menghalangi
                    await page.evaluate("""
                        () => {
                            const htmlElement = document.querySelector('html');
                            htmlElement.style.pointerEvents = 'none';
                        }
                    """)
                    
                    # Hover pada posisi tertentu
                    await graph.hover(position={'x': offset + graph_width/2, 'y': box['height']/2}, force=True)
                    
                    # Tunggu data diperbarui setelah hover
                    await page.wait_for_function("""
                        () => {
                            const nav = document.querySelector('.reksa-value-head-nav');
                            const date = document.querySelector('.navDate');
                            return nav && date && nav.textContent && date.textContent;
                        }
                    """, timeout=5000)
                    
                    # Ambil nilai dan tanggal
                    value = await page.locator('.reksa-value-head-nav').text_content()
                    date = await page.locator('.navDate').text_content()
                    
                    # Simpan data
                    data_points.append({
                        'period': period,
                        'date': date,
                        'value': value,
                        'offset': offset
                    })
                    
                    # Log hasil scraping
                    print(f"Period {period} - Offset {offset}: {date} = {value}")
                    break  # Keluar dari retry loop jika berhasil
                except Exception as e:
                    print(f"Retry {retry + 1} for offset {offset}: {e}")
                    await asyncio.sleep(1)  # Tunggu sebelum retry
                finally:
                    # Kembalikan pointer-events ke default
                    await page.evaluate("""
                        () => {
                            const htmlElement = document.querySelector('html');
                            htmlElement.style.pointerEvents = 'auto';
                        }
                    """)
            else:
                print(f"Gagal mengambil data untuk offset {offset} setelah {max_retries} retry.")
            
            # Tunggu sebentar sebelum melanjutkan ke offset berikutnya
            await asyncio.sleep(0.2)
            
    except Exception as e:
        print(f"Error in period {period}: {e}")
    finally:
        # Hitung durasi dan simpan data ke CSV
        duration = time.time() - start_time
        save_to_csv(data_points, period)
        return period, duration, len(data_points)

def save_to_csv(data_points, period):
    """
    Simpan data ke file CSV.
    """
    filename = f'data_{period}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    with open(filename, 'w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=['period', 'date', 'value', 'offset'])
        writer.writeheader()
        writer.writerows(data_points)

async def main():
    """
    Fungsi utama untuk menjalankan scraping secara parallel.
    """
    total_start = time.time()
    
    async with async_playwright() as p:
        # Buka browser dan context
        browser = await p.chromium.launch()
        context = await browser.new_context()
        
        # Daftar periode yang akan di-scrape
        periods = ['5Y']  # Anda bisa menambahkan periode lain seperti '3Y', '1Y', dll.
        
        # Buka halaman untuk setiap periode
        pages = [await context.new_page() for _ in range(len(periods))]
        for i, page in enumerate(pages):
            await page.goto('https://bibit.id/reksadana/RD66/avrist-ada-kas-mutiara')
            await wait_for_chart_load(page)
            print(f"Halaman untuk periode {periods[i]} siap.")
        
        # Scrape data untuk setiap periode secara parallel
        tasks = [scrape_period(pages[i], period) for i, period in enumerate(periods)]
        results = await asyncio.gather(*tasks)
        
        # Tutup halaman dan browser
        for page in pages:
            await page.close()
        await browser.close()

    # Hitung total durasi dan tampilkan ringkasan
    total_duration = time.time() - total_start
    print("\nPerformance Summary:")
    print(f"Total execution time: {total_duration:.2f} seconds")
    for period, duration, count in results:
        print(f"{period}: {duration:.2f} seconds, {count} data points collected")

if __name__ == "__main__":
    asyncio.run(main())