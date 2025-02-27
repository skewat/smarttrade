#! /c/Users/SURYAKANT/AppData/Local/Microsoft/WindowsApps/python

import pandas as pd
import numpy as np
from SmartApi import SmartConnect
import matplotlib.pyplot as plt
from logzero import logger 
import pyotp
import sys
import signal
import os
import json
from datetime import datetime, timedelta
import pprint 

import symbol_token
import payout
from login_details import *

# Set print display preferance
pd.set_option('display.max_rows',None)
pd.set_option('display.width', None)

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

class OptionPosition:
    def __init__(self, data):
        """
        Initialize the OptionPosition object with the given dictionary.
        """
        self.data = data

    def get(self, key):
        """
        Get the value of a given attribute.
        """
        return self.data.get(key)

    def set(self, key, value):
        """
        Set the value of a given attribute.
        """
        if key in self.data:
            self.data[key] = value
        else:
            raise KeyError(f"Invalid key: {key}")

    def __repr__(self):
        """
        String representation of the OptionPosition object.
        """
        return str(self.data)


# Example Usage
data = {
     'expiry': '',
     'lotsize': '75',
     'order_type': '', # BUY / SELL
     'opt_type': '',  # PE/CE
     'quantity': '0',
     'strike': '',
     'symbolname': 'NIFTY',
     'symbol_token': '',
     'symbol': ''
}


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

#def active_trade():
#    # Check if There is alredy any active trade
#    active_orders = read_active_orders()
#    if active_orders:
#        return active_orders
#    else :
#        return None

def active_trade():
    """Reads the active orders file and returns a set of processed dates."""
    if not os.path.exists(ORDER_FILE):
        return None
    
    with open(ORDER_FILE, "r") as file:
        loaded_data = json.load(file)
        return loaded_data

def write_active_order(data):
    """Writes a new order date to the active orders file."""
    new_order = json.dumps(data)
    # Check if file exists
    if os.path.exists(ORDER_FILE):
        # Read existing orders
        with open(ORDER_FILE, "r") as file:
            try:
                orders = json.load(file)
            except json.JSONDecodeError:
                orders = []  # If file is empty, initialize an empty list
    else:
        orders = []

    # Append the new order
    orders.append(new_order)

    # Write updated orders back to file
    with open(ORDER_FILE, "w") as file:
        json.dump(orders, file, indent=4)

    print(f"New order added to {ORDER_FILE}")

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
        print("\n\n\n")
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
        print("\n\n\n")
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

def take_entry_positions(smartApi,positions):
    # Its expected that in the positions list , BUY orders are added before sell 
    # so that margin issues do not occur
    for position in positions :
        place_order(smartApi,position)



def place_order(smartApi, position):
    order = {
            "variety": "NORMAL", # ROBO NORMAL STOPLOSS AMO
            "tradingsymbol": position.get('symbol'),
            "symboltoken": position.get('symbol_token'),
            "transactiontype": position.get("order_type"),
            "exchange": "NFO",
            "ordertype": "MARKET",
            "producttype": "CARRYFORWARD",
            "duration": "DAY",
            "quantity":  position.get("quantity"),
            'ordertag': 'STRATEGY'
        }
    
    # Place Orders
    order_status = {}
    order_id = []
    response = smartApi.placeOrderFullResponse(order)
    oid = response['data']['orderid']
    try: 
        status = get_order_status(smartApi, oid) 
        assert( status != 'Order not found')
        assert( status != 'cancelled')
        #assert( status != 'rejected')
        #TBD  write only order which are with status as complete
    except AssertionError as e:
        print(f"Order {str(order_status[oid])} is not complete ")
        print(f"AssertionError: {e}")
        return None
    #For debugging only
    print(response)
    write_active_order(order)

# Function to get order status
def get_order_status(smart_api, order_id):
    order_book = smart_api.orderBook()
    if order_book["status"] :
        for order in order_book["data"]:
            if order["orderid"] == order_id:
                return order["status"]  # Possible statuses: "COMPLETE", "PENDING", "CANCELLED", etc.
    return "Order not found"

def get_pnl_state(positions,active_trades):
    pnl_total = 0
    for j_data in active_trades:
        #trade_data = active_trades[order]
        trade_data = json.loads(j_data)

        tradingsymbol = trade_data['tradingsymbol']
        for position in positions['data'] :
            if position['tradingsymbol'] == tradingsymbol :
                pnl_total = pnl_total + float(position['unrealised'])
    print(f"Current PNL : {pnl_total}")
    return pnl_total

def spread_payoff(positions,active_trades):
    active_positions = []
    max_profit = 0
    max_loss = 0
    for j_order in active_trades:
        trade_data = json.loads(j_order)
        tradingsymbol = trade_data['tradingsymbol']
        for position in positions['data'] :
            if position['tradingsymbol'] == tradingsymbol :

                trade = {}
                if int(position['cfbuyqty']) :
                    trade['strike'] = float(position['strikeprice'])
                    p_range = (trade['strike']*0.9,trade['strike']*1.1)
                    trade['premium'] = float(position['cfbuyavgprice'])
                    trade['quantity'] = float(position['cfbuyqty'])
                    trade['type'] = tradingsymbol[-2:].strip()
                else:
                    trade['strike'] = float(position['strikeprice'])
                    p_range = (trade['strike']*0.9,trade['strike']*1.1)
                    trade['premium'] = float(position['cfsellavgprice'])
                    trade['quantity'] = float(position['cfsellqty'])*-1
                    trade['type'] = tradingsymbol[-2:].strip()
                active_positions.append(trade)
    if active_positions:
        max_profit,max_loss = payout.calculate_max_min_payout(active_positions,p_range)
    else:
        print("Anomoally: There are no trading symbols common between active trades(local) and real positions with broker")
        print("Fix the active trade list if trades are exited manually")
    return max_profit, max_loss

def do_adjustment():
    pass

def exit_trades():
    pass

def get_open_positions(smart_api):    
    positions = smart_api.position()
    active_trades = active_trade()
    pnl = get_pnl_state(positions,active_trades)
    max_profit,max_loss = spread_payoff(positions,active_trades)
    print(f"Max profit:{max_profit}, Max loss :{max_loss}")
    
def create_call_spread_position(smartApi, lots):
    position1 = OptionPosition(data.copy())  # Use .copy() to avoid shared state
    position2 = OptionPosition(data.copy())

    ltp = int(get_ltp(smartApi))

    # get expiry which is 7 days away. Its just next thurshday which is not a holiday and alyeast 7 days away.
    next_expiry = get_next_expiry()
    position1.set('expiry', next_expiry)
    position2.set('expiry', next_expiry)
    
    # get strike price near LTP
    strike_atm = round(ltp / 50) * 50
    position1.set('strike', strike_atm)

    # get strike price 200 point OTM
    strike_otm = strike_atm + 200
    position2.set('strike', strike_otm)

    position1.set('opt_type', "CE")
    position2.set('opt_type', "CE")

    # get trading symbol token for this expiry and strike price
    atm_token, otm_token, atm_symbol, otm_symbol = get_symbol_token('NIFTY',next_expiry,strike_atm,strike_otm,"CE")
    position1.set('symbol_token', atm_token)
    position2.set('symbol_token', otm_token)
    position1.set('symbol', atm_symbol)
    position2.set('symbol', otm_symbol)
    position1.set('order_type', "BUY")
    position2.set('order_type', "SELL")

    position1.set('quantity', 75*lots)
    position2.set('quantity', 75*lots)
    return position1,position2


def create_put_spread_position(smartApi,lots):
    position1 = OptionPosition(data.copy())  # Use .copy() to avoid shared state
    position2 = OptionPosition(data.copy())

    ltp = int(get_ltp(smartApi))

    # get expiry which is 7 days away. Its just next thurshday which is not a holiday and alyeast 7 days away.
    next_expiry = get_next_expiry()
    position1.set('expiry', next_expiry)
    position2.set('expiry', next_expiry)
    
    # get strike price near LTP
    strike_atm = round(ltp / 50) * 50
    position1.set('strike', strike_atm)

    # get strike price 200 point OTM
    strike_otm = strike_atm - 200
    position2.set('strike', strike_otm)

    position1.set('opt_type', "PE")
    position2.set('opt_type', "PE")

    # get trading symbol token for this expiry and strike price
    atm_token, otm_token, atm_symbol, otm_symbol = get_symbol_token('NIFTY',next_expiry,strike_atm,strike_otm,'PE')

    position1.set('symbol_token', atm_token)
    position2.set('symbol_token', otm_token)
    position1.set('symbol', atm_symbol)
    position2.set('symbol', otm_symbol)

    position1.set('order_type', "BUY")
    position2.set('order_type', "SELL")
    position1.set('quantity', 75*lots)
    position2.set('quantity', 75*lots)
    return position1,position2

def create_spread_position(smartApi,trend, lots):
    if trend == "UP":
        p1,p2 = create_call_spread_position(smartApi,lots)
    else :
        p1,p2 = create_put_spread_position(smartApi,lots)
    return [p1,p2]

# Main highlevel logic
def main(martApi):
    LOTS = 1
    if active_trade():
        #Exit workflow (exit on target , expiry , SL or do adjustments in this workflow)
        print("There is active trade...")
        get_open_positions(smartApi)    
    else :
        # Entry workflow 
        df = fetch_ohlc(smartApi)
    
        # Identify trends
        trend = get_sma_trend(df)
     
        # based on trend create Call/Put spread positions
        positions = create_spread_position(smartApi,trend, LOTS)


        # Generate trade
        #place_order(smartApi,atm_token,otm_token,atm_symbol,otm_symbol)

        take_entry_positions(smartApi,positions)

if __name__ == "__main__":
    smartApi = connect_angeloone()
    if not smartApi :
        sys.exit("Failied while connecting to server")
    fetch_data(smartApi)
    main(smartApi)
    logout(smartApi)

