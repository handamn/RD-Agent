from Comparison_Data_Scrapper import Comparison_Data_Scrapper
from Mutual_Fund_Data_Scraper import Mutual_Fund_Data_Scraper
from Prospektus_Data_Scrapper import Prospektus_Data_Scrapper

from datetime import date, timedelta
import pandas as pd


today = date.today()

def Agent_CDS():
    urls = [
        ['IHSG', 'https://finance.yahoo.com/quote/%5EJKSE/history/?p=%5EJKSE'],
        ['LQ45', 'https://finance.yahoo.com/quote/%5EJKLQ45/history/']
    ]
    
    scraper = Comparison_Data_Scrapper(urls, 'w')
    
    for kode, _ in urls:
        try:
            df = pd.read_csv(f"database/comparison/{kode}.csv")
            latest_date = pd.to_datetime(df.iloc[-1]['Date']).date()
            
            period = scraper.determine_scraping_period(latest_date)
            if period:
                scraper.scrape_data(period)
        except Exception as e:
            scraper.logger.log_info(f"Error processing {kode}: {str(e)}", "ERROR")


def Agent_MFDS():
    urls = [
        ['Batavia Technology Sharia Equity USD','https://bibit.id/reksadana/RD4183'],
    ]
    
    scraper = Mutual_Fund_Data_Scraper(urls, pixel=20, debug_mode=True)
    
    for kode, _ in urls:
        try:
            df = pd.read_csv(f"database/mutual_fund/{kode}.csv")
            latest_date = pd.to_datetime(df.iloc[-1]['tanggal']).date()
            
            periods = scraper.determine_scraping_period(latest_date)
            if periods:
                scraper.run(periods)
        except Exception as e:
            scraper.logger.log_info(f"Error processing {kode}: {str(e)}", "ERROR")

def Agent_PDS():
    urls = [
    ['ABF Indonesia Bond Index Fund', 'https://bibit.id/reksadana/RD13'],
    # ['Mandiri Investa Cerdas', 'https://bibit.id/reksadana/RD14']  # Bisa ditambahkan jika perlu
    ]

    downloader = Prospektus_Data_Scrapper()
    downloader.download(urls)


Agent_CDS()
Agent_MFDS()
Agent_PDS()