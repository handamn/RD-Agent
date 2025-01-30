from datetime import date
import pandas as pd


today = date.today()
 

mydate = date(1996, 12, 11)



csv_file ="database\ABF Indonesia Bond Index Fund.csv"

df = pd.read_csv(csv_file)
latest_data = df.iloc[-1].tolist()

latest_data_date = latest_data[0]
latest_data_value = latest_data[-1]

LD_years, LD_months, LD_dates = latest_data_date.split("-")

date_database = date(int(LD_years), int(LD_months), int(LD_dates))



if date_database >= mydate :
    value = True

else :
    value = False


print(value)