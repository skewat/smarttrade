
#! /c/Users/SURYAKANT/AppData/Local/Microsoft/WindowsApps/python
from datetime import datetime, timedelta

import datetime
import pandas as pd
import sys,os
import traceback
import calendar


from breeze_connect import BreezeConnect

# breeze Config parameters

api_key='2T30qVi00490_03C4z1F4jH743QO5517'
secret_key='99663!A45356C31l64T2k29826I995^9'
api_session = '51443881'


# List of NSE holidays (Update with actual holidays for the year)
HOLIDAYS = [
    "2024-01-22", "2024-01-26", "2024-03-08", "2024-03-25", "2024-03-29", "2024-04-11", "2024-04-17", 
    "2024-05-01", "2024-05-20", "2024-06-17", "2024-07-17", "2024-08-15", "2024-10-02", "2024-11-01",
    "2024-11-20", "2024-11-15", "2024-12-25", "2023-01-26", "2023-03-07", "2023-03-22", "2023-03-30", 
    "2023-04-04", "2023-04-07", "2023-04-14", "2023-05-01", "2023-05-05", "2023-06-29", "2023-08-15", 
    "2023-08-16", "2023-09-19", "2023-10-02", "2023-10-24", "2023-11-14", "2023-11-27", "2023-12-25",
    "2022-01-26", "2022-03-01", "2022-03-18", "2022-04-14", "2022-04-15", "2022-05-03", "2022-08-09", 
    "2022-08-15", "2022-08-31", "2022-10-05", "2022-10-24", "2022-10-26", "2022-11-08", "2021-01-26", 
    "2021-03-11", "2021-03-29", "2021-04-02", "2021-04-14", "2021-04-21", "2021-05-13", "2021-07-21", 
    "2021-08-19", "2021-09-10", "2021-10-15", "2021-11-04", "2021-11-05", "2021-11-19", "2020-01-26", 
    "2020-02-21", "2020-03-10", "2020-04-02", "2020-04-06", "2020-04-10", "2020-04-14", "2020-05-01",
    "2020-05-25", "2020-10-02", "2020-11-16", "2020-11-30", "2020-12-25",
]



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

def last_thursdays_of_months(year):
    last_thursdays = []
    for month in range(1, 13):
        # Get the last day of the month
        last_day = calendar.monthrange(year, month)[1]
        date = datetime.datetime(year, month, last_day)
        # Move back to the last Thursday
        while date.weekday() != calendar.THURSDAY:
            date -= timedelta(days=1)
        last_thursdays.append(date.date())
    last_thursdays = pd.to_datetime(last_thursdays)
    return last_thursdays.strftime("%Y-%m-%d").tolist()
#    return last_thursdays


def get_spot_price(breeze,date,symbol):
    spot = get_breeze_hist_data(breeze,date,date,symbol,'CASH')
    #print(spot)
    return int(float(spot['Success'][-1]['close']))

def get_strike_price_range(spot_price):
    step = 50
    lower_limit = ((spot_price - 1500) // step) * step
    upper_limit = ((spot_price + 1400) // step) * step

    return list(range(int(lower_limit), int(upper_limit + step), step))

def get_all_expiry_dates(year):
    ''' Get all expiry dates of a given year '''
    all_exp_dates = []
    # Weekly expiry 
    #calendar_dates = get_calendar_dates(year)

    #Monthly expiry
    calendar_dates = last_thursdays_of_months(year)

    for input_date_str in calendar_dates :
        print(input_date_str)
        input_date = datetime.datetime.strptime(input_date_str, '%Y-%m-%d')
    
        # Get today's date and 7 days ago
        today = datetime.datetime.now()
        seven_days_ago = today - timedelta(days=7)
        
        # Check if the input date is older than 7 days
        if input_date < seven_days_ago:
            exp_date = get_next_expiry(input_date)
            all_exp_dates.append(exp_date)
        else:
            print(f"Date is too close {input_date}")

    return all_exp_dates


def connect_breeze():
    
    # Initialize SDK
    breeze = BreezeConnect(api_key=api_key)
    
    # Obtain your session key from https://api.icicidirect.com/apiuser/login?api_key=2T30qVi00490_03C4z1F4jH743QO5517
    # Incase your api-key has special characters(like +,=,!) then encode the api key before using in the url as shown below.
    # import urllib
    # print("https://api.icicidirect.com/apiuser/login?api_key="+urllib.parse.quote_plus("api_key"))
    
    # Generate Session
    breeze.generate_session(api_secret=secret_key, session_token=api_session)

    #print(breeze.get_funds())

    return breeze     

def get_start_end_date(start_date,expiry = 'WEEKLY'):
    # Go back 14 days
    #check_date = start_date - timedelta(days=15)
    start_date = datetime.datetime.strptime(start_date, "%d%b%y")
    if expiry == 'MONTHLY':
        #print(start_date,type(start_date))
        check_date = start_date - timedelta(days=27)
        # Adjust if date is Saturday, Sunday, or a holiday
        while not (check_date.weekday() == 4) or check_date in HOLIDAYS:
            check_date -= timedelta(days=1)
        return check_date,start_date


    # Adjust if date is Saturday, Sunday, or a holiday
    while check_date.weekday() >= 5 or check_date in HOLIDAYS:
        check_date -= timedelta(days=1)
    return check_date,start_date

def get_breeze_hist_data(breeze, start_date,end_date,symbol,product_type,expiry=0,strike=0,opt_type='call'):

    #traceback.print_stack()
    from_d = f"{start_date}T09:15:00.000Z"
    to_d = f"{start_date}T15:30:00.000Z"
    if product_type.lower() == 'futures':
        #start_d,end_d = get_start_end_date(expiry,'MONTHLY')
        #start_date = f"{start_d}T09:15:00.000Z"
        #end_date = f"{expiry}T15:30:00.000Z"
        #expiry_d = f"{expiry}T15:30:00.000Z"
        historical_data = breeze.get_historical_data(interval="1day",
                      from_date= start_date,
                      to_date= end_date,
                      stock_code="NIFTY",
                      exchange_code="NFO",
                      product_type="futures",
                      expiry_date=expiry,
                      right="others",
                      strike_price="0")
    
    elif product_type.lower() == 'options':
        if (start_date == 0 or end_date == 0) and not expiry == 0 :
            # Set start date 15 days prior to expiry
            start_d,end_d = get_start_end_date(expiry)
            start_date = f"{start_d}T09:15:00.000Z"
            end_date = f"{end_d}T15:30:00.000Z"
            expiry_d = f"{expiry}T07:00:00.000Z"

        historical_data = breeze.get_historical_data(interval="1minute",
                      from_date= start_date,
                      to_date= end_date,
                      stock_code="NIFTY",
                      exchange_code="NFO",
                      product_type="options",
                      expiry_date=expiry_d,
                      right=opt_type, # or 'put'
                      strike_price=strike)
    
    
    elif product_type.lower() == 'cash':
        historical_data = breeze.get_historical_data(interval="1day",
                      from_date= start_date,
                      to_date= end_date,
                      stock_code=symbol,
                      exchange_code="NSE",
                      product_type="CASH",
                      strike_price="0")
    else:
        sys.exit("Invalid product_type")
    
    return(historical_data)
    

def get_option_data_given_expiry_strike(breeze,expiry, strike, symbol):
    ''' get option historical data of a symbol with spot proce +/- 1000'''
    data = get_breeze_hist_data(breeze,date,date,symbol,'CASH',strike)
    return data

def to_csv(file_name,data):
    import csv

    with open(file_name, 'w', newline='') as file:
        try :
            writer = csv.DictWriter(file, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        except:
            print(f"Failed to write {file_name} , issue with data")


def main():
    i = 0
    symbol = 'NIFTY'
    opt_types = ['call','put']
    FUTURE = True

    try :
        print("Connecting ...",flush=True)
        breeze = connect_breeze()
        print("Connected ...",flush=True)
    except Exception as e:
        error_message = str(e)
        full_traceback = traceback.format_exc()

        print("Error message:", error_message)
        print("Traceback:\n", full_traceback)
        sys.exit(f"\n\n Failed to connect to icicidirect using breeze API")
    

    for year in range(2024,2025):
        exp_dates = get_all_expiry_dates(year)
        exps = []
        for i in range(len(exp_dates) - 1):
            expiry_near = exp_dates[i]
            expiry_next = exp_dates[i + 1]
            exp = [expiry_near,expiry_next]
            exps.append(exp)
        #for exp_date in exp_dates:
        for exp_dates in exps:
            #print('+'*80)
            for exp_date in exp_dates : 
                date_obj = datetime.datetime.strptime(exp_date, "%d%b%y")
                date= date_obj.date()
                expiry_date = date
                start_d,end_d = get_start_end_date(exp_dates[0],'MONTHLY')
                start_d = start_d.strftime("%Y-%m-%d")
                start_date = f"{start_d}T09:15:00.000Z"
                end_d = end_d.strftime("%Y-%m-%d")
                end_date = f"{end_d}T15:30:00.000Z"

                ex_d = date_obj.strftime("%Y-%m-%d")
                expiry_d = f"{ex_d}T15:30:00.000Z"
                #print(start_date,end_date,expiry_d)
                data = get_breeze_hist_data(breeze,start_date,end_date,symbol,'futures',expiry_d,'',0)
                #print(data)
                print(data['Success'][0]['datetime'],',',data['Success'][0]['close'],',',data['Success'][-1]['datetime'],',',data['Success'][-1]['close'],',',ex_d)
                continue
            data = get_breeze_hist_data(breeze,start_date,end_date,symbol,'cash',expiry_d,'',0)
            to_csv('test_data.csv',data['Success'])
            print(data['Success'][0]['datetime'],',',data['Success'][0]['close'],',',data['Success'][-1]['datetime'],',',data['Success'][-1]['close'],',','NA')
            print('-',',','-',',','-',',','-',',','_')
            continue
        continue
    return 

'''
            spot = get_spot_price(breeze,date,symbol)
            strike_prices = get_strike_price_range(spot) 
            #print(exp_date, flush=True)
            #if not exp_date == '13JUN24' :
            #    continue
            for strike_price in strike_prices :
                #print(strike_price)
                for opt in opt_types :
                    #print(opt)
                    i = i + 1
                    file_name = f"{symbol}_{exp_date}_{strike_price}_{opt}_option_data.csv"
                    file_name = file_name.lower()
                    print(i, flush=True)
                    if not os.path.exists(file_name):
                        data = get_breeze_hist_data(breeze,0,0,symbol,'options',expiry_date,strike_price,opt)
                        #print(data)
                        to_csv(file_name,data['Success'])
'''

if __name__ == "__main__":
    main()
