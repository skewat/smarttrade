
#! /c/Users/SURYAKANT/AppData/Local/Microsoft/WindowsApps/python
from maticalgos.historical import historical
import datetime
import pandas as pd
import sys


def login_maticalgos(username='skewat@gmail.com',password='807860'):
    ''' Login to Matic Algos '''
    ma = historical(username)
    ma.login(password)
    return ma 

def get_days_option_chain(ma, date, symbol):
    ''' get dailing option chanin of a symbol with spot proce '''
    data = ma.get_data(symbol, date)
    # Combile date and time as that's two different in original data frame
    data['datetime'] = data['date'] + " " + data['time']
    data['datetime'] = pd.to_datetime(data['datetime']).dt.strftime('%m/%d/%Y %H:%M:%S')
    data['datetime'] = pd.to_datetime(data['datetime'], format='%m/%d/%Y %H:%M:%S')
    
    #data[['open', 'high', 'low', 'close', 'volume', 'oi']] = data[['open', 'high', 'low', 'close', 'volume', 'oi']].astype(float)
    data = data[['datetime', 'symbol', 'open', 'high', 'low', 'close', 'volume', 'oi']]
    data = data.set_index('datetime')
    #data_grouped = data.groupby('symbol')
    return data

def is_nse_working_day(date):
    """
    Function to check if a given date is an NSE working day.
    
    Parameters:
        date (str or datetime): Date in 'YYYY-MM-DD' format or as a datetime object.
    
    Returns:
        bool: True if it's an NSE working day, False otherwise.
    """
    # Convert input to datetime if it's a string
    date = pd.to_datetime(date)
    
    # List of NSE holidays (Update with actual holidays for the year)
    nse_holidays = [
        "2024-01-26", "2024-03-08", "2024-03-29", "2024-04-11", "2024-04-17", "2024-05-01", "2024-06-17", "2024-08-15", "2024-10-02", "2024-11-01",
        "2024-11-15", "2024-12-25", "2023-01-26", "2023-03-07", "2023-03-22", "2023-03-30", "2023-04-04", "2023-04-07", "2023-04-14", "2023-05-01",
        "2023-05-05", "2023-06-29", "2023-08-15", "2023-08-16", "2023-09-19", "2023-10-02", "2023-10-24", "2023-11-14", "2023-11-27", "2023-12-25",
        "2022-01-26", "2022-03-01", "2022-03-18", "2022-04-14", "2022-04-15", "2022-05-03", "2022-08-09",  "2022-08-15", "2022-08-31", "2022-10-05", 
        "2022-10-24", "2022-10-26", "2022-11-08", "2021-01-26", "2021-03-11", "2021-03-29", "2021-04-02", "2021-04-14", "2021-04-21", "2021-05-13", 
        "2021-07-21", "2021-08-19", "2021-09-10", "2021-10-15", "2021-11-04", "2021-11-05", "2021-11-19", "2020-01-26", "2020-02-21", "2020-03-10", 
        "2020-04-02", "2020-04-06", "2020-04-10", "2020-04-14", "2020-05-01", "2020-05-25", "2020-10-02", "2020-11-16", "2020-11-30",
    ]
    nse_holidays = pd.to_datetime(nse_holidays)
    
    # Check if the date is a weekday (Monday to Friday) and not a holiday
    return (date.weekday() < 5) and (date not in nse_holidays)

def get_calendar_dates(year):
    return pd.date_range(start=f"{year}-01-01", end=f"{year}-12-31").strftime("%Y-%m-%d").tolist()



def main():
    symbol = 'banknifty'
    ma = login_maticalgos()
    
    if 0:
        date = datetime.date(2020,1,15)
        data = get_days_option_chain(ma, date, symbol)
        data.to_csv(f"{symbol}_{date}_option_chain.csv", index=True)

    else:
       i = 0
       for year in range(2020,2025):
           calendar_dates = get_calendar_dates(year)
           for date in calendar_dates:
               if is_nse_working_day(date):
                   i = i + 1
                   print(i)
                   date_obj = datetime.datetime.strptime(date, "%Y-%m-%d").date()
                   data = get_days_option_chain(ma,date_obj,symbol)
                   data.to_csv(f"{symbol}_{date}_option_chain.csv", index=True)
                   if i == 30 : # Only 30 for testing
                       sys.exit(0)

if __name__ == "__main__":
    main()



