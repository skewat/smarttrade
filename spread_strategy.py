#! /c/Users/SURYAKANT/AppData/Local/Microsoft/WindowsApps/python


"""
Assumptions and rules .. 
1. Order is placed every Thurshday at 10:15


"""


import pandas as pd
import numpy as np
from SmartApi import SmartConnect
import matplotlib.pyplot as plt
from logzero import logger 
import pyotp
import sys
import signal
import os
import symbol_token
from datetime import datetime, timedelta
import pprint 

# List of holidays (YYYY-MM-DD format)
HOLIDAYS = {"2025-01-01",
    "2025-01-26",
    "2025-02-26",
    "2025-03-14",
    "2025-03-31",
    "2025-04-06",
    "2025-04-10",
    "2025-04-14",
    "2025-04-18",
    "2025-05-01",
    "2025-06-07",
    "2025-07-06",
    "2025-08-15",
    "2025-08-27",
    "2025-10-02",
    "2025-10-21",
    "2025-10-22",
    "2025-11-05",
    "2025-12-25"}

# Set print display preferance
pd.set_option('display.max_rows',None)
pd.set_option('display.width', None)

#File where previous oreders are stored
ORDER_FILE = "active_orders.txt"

# Set testing to read data for back testing instead of from API
TESTING = True


# Determine trend based on SMA_5 and SMA_21
def get_trend(row):
    if pd.isna(row["SMA_5"]) or pd.isna(row["SMA_21"]):
        return None  # Avoid trends for NaN values
    if row["SMA_5"] > row["SMA_21"]:
        return "UP"
    elif row["SMA_5"] < row["SMA_21"]:
        return "DOWN"
    else:
        return "NEUTRAL"

def next_candle_limit(df, window=5):
    ''' TBD .. COnsider latest price and check if 5/7 SMA crosses 20 SMA.
        This is to account for large gapup or gapdown
        So , iput here will be 
        (1) DF of 5 for 5 SMA, 20 for 20 SMA
        (2)  LTP price
        (3) recalculate SMA cross over 
    '''
    """Calculate the price limit for the next candle that can change the trend."""
    if len(df) < window:
        return "Not enough data for SMA calculation."

    # Get the last SMA and trend
    last_sma = df.iloc[-1]['SMA']
    last_trend = df.iloc[-1]['Trend']

    # Compute new SMA threshold where the trend flips
    prev_closes = df['Close'].iloc[-(window-1):].tolist()  # Last (window-1) closes
    sma_sum = sum(prev_closes)  # Sum of last (window-1) close prices

    # New close price needed to flip the trend
    if last_trend == 'UP':
        new_close = (window * last_sma) - sma_sum - 0.01  # Slightly below SMA
        return f"Trend will change to DOWN if next candle closes below {new_close:.2f}"
    else:
        new_close = (window * last_sma) - sma_sum + 0.01  # Slightly above SMA
        return f"Trend will change to UP if next candle closes above {new_close:.2f}"


def get_sma_trend(data):
    ''' Get SMA and add it as column in Data Frame  and return last trend'''
    
    df = pd.DataFrame(data)
    
    # Calculate moving averages
    df["SMA_5"] = df["Close"].rolling(window=5).mean()
    df["SMA_7"] = df["Close"].rolling(window=7).mean()
    df["SMA_21"] = df["Close"].rolling(window=21).mean()
    df["Trend"] = df.apply(get_trend, axis=1)
    
    return df['Trend'].iloc[-1]

def active_trade():
    # Check if There is alredy any active trade
    active_orders = read_active_orders()
    if active_orders:
        return True
    else :
        return False

def read_active_orders():
    """Reads the active orders file and returns a set of processed dates."""
    if not os.path.exists(ORDER_FILE):
        return set()
    
    with open(ORDER_FILE, "r") as file:
        return set(line.strip() for line in file)

def write_active_order(data):
    """Writes a new order date to the active orders file."""
    with open(ORDER_FILE, "a") as file:
        file.write(str(data))

def generate_order(df,ltp):
    """
    Checks if the current timestamp is Thursday at 10:15 and generates an order.
    
    """

    if df.empty:
        return "No Data in DataFrame"

    # Get the latest row
    latest_row = df.iloc[-1]
    latest_timestamp = latest_row.name  # Since index is DateTime
    trend = latest_row['Trend'].upper()

    # Check if it's Thursday and time is 10:15 AM or later
    if TESTING or ( latest_timestamp.weekday() == 3 and latest_timestamp.strftime('%H:%M') >= '10:15'):
        order_type = 'CE' if trend == 'UP' else 'PE'

        # Store today's order
        write_active_order(latest_row)

        return f"Placing {order_type} order at {latest_timestamp}"

    return "No Order"


def connect_angeloone():
    ''' Connect to AngelOne using API '''

    api_key = 'TPQapFn5'
    username = 'AAAE362329'
    pwd = '1697'
    smartApi = SmartConnect(api_key)
    
    try:
        token = "YDGLN23VQ7KBI4QEY6PR2OA7TE"
        totp = pyotp.TOTP(token).now()
    except Exception as e:
        logger.error("Invalid Token: The provided token is not valid.")
        raise e
    
    correlation_id = "abcde"
    data = smartApi.generateSession(username, pwd, totp)
    
    if data['status'] == False:
        logger.error(data)
    
    else:
        # login api call
        # logger.info(f"You Credentials: {data}")
        authToken = data['data']['jwtToken']
        refreshToken = data['data']['refreshToken']
        # fetch the feedtoken
        feedToken = smartApi.getfeedToken()
        # fetch User Profile
        res = smartApi.getProfile(refreshToken)
        smartApi.generateToken(refreshToken)
        res = res['data']['exchanges']
        return smartApi


def get_previous_working_day(ref_date):
    """Finds the most recent working day (excluding weekends and holidays)."""
    while True:
        ref_date -= timedelta(days=1)
        if ref_date.weekday() in {5, 6} or ref_date.strftime('%Y-%m-%d') in HOLIDAYS:
            continue
        return ref_date

def get_two_dates():
    ''' Get two dates of last 1 week to get historical data to determine trend '''
    today = datetime.today()

    # Get the latest working day (yesterday or last business day)
    latest_working_day = get_previous_working_day(today)

    # Get the second date (at least 5 working days before)
    second_working_day = latest_working_day
    for _ in range(5):  # Move back 5 working days
        second_working_day = get_previous_working_day(second_working_day)

    return latest_working_day.strftime('%Y-%m-%d'), second_working_day.strftime('%Y-%m-%d')

def get_next_expiry():
    ''' Next expiry to use for taking trade '''
    ''' Get next thurshday which is 7 days away from today and is not in HOLIDAY list '''
    today = datetime.today()
    next_thursday = today + timedelta(days=(3 - today.weekday() + 7) % 7)  # Get next Thursday

    # Ensure it's at least 7 days from today
    if (next_thursday - today).days < 7:
        next_thursday += timedelta(days=7)

    # Check if the date is in holidays, if so, find the next available Thursday
    while next_thursday.strftime("%Y-%m-%d") in HOLIDAYS:
        next_thursday += timedelta(days=7)

    return next_thursday.strftime("%d%b%y").upper()


def get_date_range():
    ''' Date yesterday and previous 5 working days '''
    # Example Usage
    date1, date2 = get_two_dates()
    d1 = f"{date1} 15:20"
    d2 = f"{date2} 09:15"
    return d1,d2

def fetch_data(smartApi):
    ''' Fetch historical data to get SMA based trend '''
    TODATE,FROMDATE = get_date_range()
    try:
        historicParam = {
            "exchange": "NSE",
            #"symboltoken": "99926009",
            "symboltoken": "99926000",
            "interval": "ONE_HOUR",
            #"fromdate": "2025-01-12 09:20",
            "fromdate": FROMDATE,
            "todate": TODATE
            #"todate": "2025-02-19 10:20"
        }
        data = smartApi.getCandleData(historicParam)
        return data

    except Exception as e:
        logger.exception(f"Historic Api failed: {e}")

def logout(smartAPi):
    # logout from AngenOne API
    try:
        logout = smartApi.terminateSession('AAAE362329')
        logger.info("Logout Successfull")
    except Exception as e:
        logger.exception(f"Logout failed: {e}")


def signal_handler(sig, frame):
    ''' This is system signal handelr not related to stock/trend signal '''
    print("\nExiting gracefully...")
    disconnect(SmartApi)
    sys.exit(0)


def get_ltp(smartApi):
    ''' Get LTP for Nifty50 Index '''
    signal.signal(signal.SIGINT, signal_handler)
    stock_symbol_token_NIFTY = '99926000' # NIFTY token for NSE
    exchange_NIFTY = 'NSE'
    trading_symbol_NIFTY = 'NIFTY'
    stock_data_NIFTY = smartApi.ltpData(exchange_NIFTY, trading_symbol_NIFTY, stock_symbol_token_NIFTY)

    return (stock_data_NIFTY['data']['ltp'])



# Authenticate and fetch historical data
def fetch_ohlc(smartApi):
    data = fetch_data(smartApi)
    df = pd.DataFrame(data["data"], columns=["Datetime", "Open", "High", "Low", "Close", "Volume"])
    df["Datetime"] = pd.to_datetime(df["Datetime"])
    df.set_index("Datetime", inplace=True)
    return df


def get_symbol_token(name, expiry, strike_atm, strike_otm,opt_type):
    '''Symbol token is needed for placing order and historical data , this token is not generic and
       it's provided by angelone @ 
       curl -k https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json
       We store it in symbol_token.py and import it as this gives next few years data.
    '''
    for i in symbol_token.data:
        if i['exch_seg'] == 'NFO' and  i['name'] == name :
            atm_symbol = f"{name}{expiry}{strike_atm}{opt_type}"
            otm_symbol = f"{name}{expiry}{strike_otm}{opt_type}"
            if i['symbol'] == atm_symbol:
                atm_token = i['token']
            elif i['symbol'] == otm_symbol:
                otm_token = i['token']
    if not atm_token or not otm_token :
        print("Error !! trading token not found",name, expiry, strike_atm, strike_otm,opt_type)
    else:
        return atm_token, otm_token, atm_symbol, otm_symbol


def place_order(smartApi,atm_token,otm_token,atm_symbol,otm_symbol):

    # Angel One Symbol Tokens (Fetch using API)
    symbol_tokens = {
        atm_symbol: atm_token,  
        otm_symbol: otm_token  
    }
    
    # Define ROBO Order Legs
    order_legs = [
        {
            "variety": "NORMAL", # ROBO NORMAL STOPLOSS AMO
            "tradingsymbol": atm_symbol,
            "symboltoken": symbol_tokens[atm_symbol],
            "transactiontype": "BUY",
            "exchange": "NFO",
            "ordertype": "MARKET",
            #"ordertype": "LIMIT",
            "producttype": "CARRYFORWARD",
            "duration": "DAY",
            #"price": 5.0,  # Replace with PRICE in case of LIMIT order
            "quantity": 75,
            'ordertag': 'STRATEGY'
        },
        {
            "variety": "NORMAL",
            "tradingsymbol": otm_symbol,
            "symboltoken": symbol_tokens[otm_symbol],
            "transactiontype": "SELL",
            "exchange": "NFO",
            "ordertype": "MARKET",
            #"ordertype": "LIMIT",
            "producttype": "CARRYFORWARD",
            "duration": "DAY",
            #"price": 150.0,  # Replace with PRICE in case of LIMIT order type
            "quantity": 75,
            'ordertag': 'STRATEGY'
        }
    ]
    
    # Place Orders
    order_status = {}
    order_id = []
    for order in order_legs:
        response = smartApi.placeOrderFullResponse(order)
        #print(order)
        if response['status'] == True:
            oid = response['data']['orderid']
            order_id.append(oid)
        #print(f"Order Response for {order['tradingsymbol']}: {response}")
        #print(order_id)
        order_status[oid] = order
    for oid in order_id : 
        try: 
            status = get_order_status(smartApi, oid) 
            assert( status != 'Order not found')
            assert( status != 'cancelled')
            #assert( status != 'rejected')
            #TBD  write only order which are with status as complete
            order_status[oid]['status'] = status 
        except AssertionError as e:
            print(f"Order {str(order_status[oid])} is not complete ")
            print(f"AssertionError: {e}")
            return None

    write_active_order(order_status)

# Function to get order status
def get_order_status(smart_api, order_id):
    order_book = smart_api.orderBook()
    if order_book["status"] :
        for order in order_book["data"]:
            if order["orderid"] == order_id:
                return order["status"]  # Possible statuses: "COMPLETE", "PENDING", "CANCELLED", etc.
    return "Order not found"

    
    
# Main highlevel logic
def main(martApi):

    ltp = int(get_ltp(smartApi))

    #Remove 'not' after test
    if active_trade():
        print("There is active trade...")
        pass
        #Exit workflow (exit on target , expiry , SL or do adjustments in this workflow)
    else :
        # Entry workflow 
        df = fetch_ohlc(smartApi)
    
        # Identify trends
        trend = get_sma_trend(df)

        # get expiry which is 7 days away.
        next_expiry = get_next_expiry()

        # get strike price neart LTP
        strike_atm = round(ltp / 50) * 50

        # get strike price 200 point OTM
        if trend == 'UP' :
            strike_otm = strike_atm + 200
            opt_type = "CE"
        else:
            strike_otm = strike_atm - 200
            opt_type = "PE"

        # get trading symbol token for this expiry and strike price
        atm_token, otm_token, atm_symbol, otm_symbol = get_symbol_token('NIFTY',next_expiry,strike_atm,strike_otm,opt_type)

        # Generate trade
        place_order(smartApi,atm_token,otm_token,atm_symbol,otm_symbol)
        #print(generate_order(sma,ltp))

if __name__ == "__main__":
    smartApi = connect_angeloone()
    if not smartApi :
        sys.exit("Failied while connecting to server")
    fetch_data(smartApi)
    main(smartApi)
    logout(smartApi)

