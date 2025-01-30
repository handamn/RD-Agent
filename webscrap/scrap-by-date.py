from datetime import date
 
today = date.today()
 
print(today)

mydate = date(1996, 12, 11)

print(mydate)

if today >= mydate :
    print("ya")

else :
    print("no")