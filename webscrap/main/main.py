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

    for kode, url in urls:
        csv_file_recent = f"database/comparison/{kode}.csv"
        df = pd.read_csv(csv_file_recent)
        latest_data = df.iloc[-1].tolist()

        latest_data_date = latest_data[0]
        latest_data_value = latest_data[-1]


        LD_years, LD_months, LD_dates = latest_data_date.split("-")
        date_database = date(int(LD_years), int(LD_months), int(LD_dates))

        delta_date = today - date_database

        if delta_date < timedelta(0):
                print("tidak proses")
        else:
            # Daftar periode berdasarkan hari
            period_map = [
                (1, '1D'),
                (5, '5D'),
                (90, '3M'),
                (180, '6M'),
                (360, '1Y'),
                (1800, '5Y')
            ]

            # Default jika lebih dari 5 tahun
            data_periods = 'Max'
            
            # Loop untuk mencari rentang yang sesuai
            for days, periods in period_map:
                if delta_date <= timedelta(days=days):
                    data_periods = periods
                    break  # Stop loop setelah menemukan rentang yang sesuai

    scraper = Comparison_Data_Scrapper(urls, data_periods, 'w')
    scraper.scrape_data()


def Agent_MFDS():
    urls = [
        ['Batavia Technology Sharia Equity USD','https://bibit.id/reksadana/RD4183'],
    ]

    pixel = 20

    # Read csv

    for kode, url in urls:
        csv_file_recent = f"database/mutual_fund/{kode}.csv"
        df = pd.read_csv(csv_file_recent)
        latest_data = df.iloc[-1].tolist()

        latest_data_date = latest_data[0]
        latest_data_value = latest_data[-1]

        LD_years, LD_months, LD_dates = latest_data_date.split("-")
        date_database = date(int(LD_years), int(LD_months), int(LD_dates))

        delta_date = today - date_database

        if delta_date < timedelta(0):
                print("tidak proses")
        else:
            # Daftar periode berdasarkan hari
            period_map = [
                (30, ['1M']),
                (90, ['1M', '3M']),
                (365, ['1M', '3M', 'YTD']),
                (1095, ['1M', '3M', 'YTD', '3Y']),
                (1825, ['1M', '3M', 'YTD', '3Y', '5Y']),
                (3650, ['1M', '3M', 'YTD', '3Y', '5Y', '10Y'])
            ]

            # Default jika lebih dari 5 tahun
            data_periods = ['ALL', '1M', '3M', 'YTD', '3Y', '5Y', '10Y']

            # Loop untuk mencari rentang yang sesuai
            for days, periods in period_map:
                if delta_date <= timedelta(days=days):
                    data_periods = periods
                    break  # Stop loop setelah menemukan rentang yang sesuai
    
    scraper = Mutual_Fund_Data_Scraper(urls, data_periods, pixel, debug_mode=True)
    scraper.run()

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