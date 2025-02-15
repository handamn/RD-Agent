from Comparison_Data_Scrapper import Comparison_Data_Scrapper
from Mutual_Fund_Data_Scraper import Mutual_Fund_Data_Scraper
from Prospektus_Data_Scrapper import Prospektus_Data_Scrapper

def Agent_CDS():
    # Daftar URL untuk Comparison Data Scrapper
    urls = [
        ['IHSG', 'https://finance.yahoo.com/quote/%5EJKSE/history/?p=%5EJKSE'],
        ['LQ45', 'https://finance.yahoo.com/quote/%5EJKLQ45/history/']
    ]

    # Inisialisasi dan jalankan Comparison_Data_Scrapper
    scraper = Comparison_Data_Scrapper(urls, mode_csv='w')
    scraper.scrape_data()


def Agent_MFDS():
    # Daftar URL untuk Mutual Fund Data Scraper
    urls = [
        ['Batavia Technology Sharia Equity USD', 'https://bibit.id/reksadana/RD4183'],
    ]

    # Inisialisasi dan jalankan Mutual_Fund_Data_Scraper
    pixel = 20  # Jumlah pixel untuk scraping grafik
    scraper = Mutual_Fund_Data_Scraper(urls, pixel, debug_mode=True)
    scraper.run()


def Agent_PDS():
    # Daftar URL untuk Prospektus Data Scrapper
    urls = [
        ['ABF Indonesia Bond Index Fund', 'https://bibit.id/reksadana/RD13'],
        # ['Mandiri Investa Cerdas', 'https://bibit.id/reksadana/RD14']  # Bisa ditambahkan jika perlu
    ]

    # Inisialisasi dan jalankan Prospektus_Data_Scrapper
    downloader = Prospektus_Data_Scrapper()
    downloader.download(urls)


# Jalankan semua agent
Agent_CDS()
Agent_MFDS()
Agent_PDS()