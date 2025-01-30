from datetime import date, timedelta
import pandas as pd


today = date.today()

today_a = date(2029, 6, 30) 
 

mydate = date(1996, 12, 11)



csv_file ="database\ABF Indonesia Bond Index Fund.csv"

df = pd.read_csv(csv_file)
latest_data = df.iloc[-1].tolist()

latest_data_date = latest_data[0]
latest_data_value = latest_data[-1]

LD_years, LD_months, LD_dates = latest_data_date.split("-")

date_database = date(int(LD_years), int(LD_months), int(LD_dates))



if date_database <= mydate :
    value = True

else :
    value = False


print(value)

from datetime import timedelta

pengurangan = today_a - date_database

# Jika pengurangan negatif, langsung cetak dan hentikan proses
if pengurangan < timedelta(0):
    print("tidak proses")
else:
    # Daftar periode berdasarkan hari
    period_map = [
        (30, ['1M']),
        (90, ['1M', '3M']),
        (365, ['1M', '3M', 'YTD']),
        (1095, ['1M', '3M', 'YTD', '3Y']),
        (1825, ['1M', '3M', 'YTD', '3Y', '5Y']),
    ]

    # Default jika lebih dari 5 tahun
    data_periods = ['ALL', '1M', '3M', 'YTD', '3Y', '5Y']

    # Loop untuk mencari rentang yang sesuai
    for days, periods in period_map:
        if pengurangan <= timedelta(days=days):
            data_periods = periods
            break  # Stop loop setelah menemukan rentang yang sesuai

    # Cetak hasil
    print(pengurangan)
    print(data_periods)


