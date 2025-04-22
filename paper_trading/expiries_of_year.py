
#! /c/Users/SURYAKANT/AppData/Local/Microsoft/WindowsApps/python
from datetime import datetime, timedelta

import datetime
import pandas as pd
import sys,os
import traceback
from holidays import *

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
    nse_holidays = HOLIDAYS 
    nse_holidays = pd.to_datetime(nse_holidays)
    
    # Check if the date is a weekday (Monday to Friday) and not a holiday
    return (date.weekday() < 5) and (date not in nse_holidays)

def get_next_expiry(today=datetime.datetime.today):
    ''' Next expiry to use for taking trade '''
    ''' Get next thurshday which is 7 days away from today and is not in HOLIDAY list '''
    next_thursday = today + timedelta(days=(3 - today.weekday() + 7) % 7)  # Get next Thursday

    # Check if the date is in holidays, if so, expiry is previous day
    while next_thursday.strftime("%Y-%m-%d") in HOLIDAYS:
        next_thursday += timedelta(days=-1)

    return next_thursday.strftime("%d%b%y").upper()

def get_calendar_dates(year):
    all_dates = pd.date_range(start=f"{year}-01-01", end=f"{year}-12-31")
    mondays = all_dates[all_dates.weekday == 0]  # 0 = Monday
    return mondays.strftime("%Y-%m-%d").tolist()

    #return pd.date_range(start=f"{year}-01-01", end=f"{year}-12-31").strftime("%Y-%m-%d").tolist()

def get_all_expiry_dates(year,backtest):
    ''' Get all expiry dates of a given year '''
    all_exp_dates = []
    calendar_dates = get_calendar_dates(year)

    for input_date_str in calendar_dates :
        input_date = datetime.datetime.strptime(input_date_str, '%Y-%m-%d')
    
        # Get today's date and 7 days ago
        today = datetime.datetime.now()
        seven_days_ago = today - timedelta(days=7)
        
        # Check if the input date is older than 7 days
        if input_date < seven_days_ago or not backtest:
            exp_date = get_next_expiry(input_date)
            all_exp_dates.append(exp_date)
        else:
            print(f"Date is too close {input_date}")

    return all_exp_dates

def main(year,backtest=False):
    i = 0
    exp_dates = get_all_expiry_dates(year,backtest)
    return exp_dates

if __name__ == "__main__":
    main(2022)
