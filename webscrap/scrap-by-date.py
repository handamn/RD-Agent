from datetime import date
import pandas as pd


today = date.today()
 
print(today)

mydate = date(1996, 12, 11)

print(mydate)

if today >= mydate :
    print("ya")

else :
    print("no")

csv_file ="database\ABF Indonesia Bond Index Fund.csv"

df = pd.read_csv(csv_file)
adam = df.iloc[-1].tolist()
adam_a = adam[0]
adam_b = adam_a.replace("-", ", ")
print(adam_b)

date_from = date(adam_b)

print(date_from)
print(type(date_from))