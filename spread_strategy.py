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
import re
import logging
from datetime import datetime, timedelta
import pprint 

import symbol_token
import payout

'''Create login_details.py file with your credentials, below are example content
api_key = 'TgDJkhyT'
username = 'ABCD123456'
wd = '5379'
'''
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

t_events = logging.getLogger("Logger1")
t_events.setLevel(logging.DEBUG)
handler1 = logging.FileHandler("trading-events.txt")
formatter1 = logging.Formatter('%(asctime)s - %(message)s')
handler1.setFormatter(formatter1)
t_events.addHandler(handler1)



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
ADJUSTMENT_FILE = "adjustment_tages.txt"

# Set testing to read data for back testing instead of from API
PAPER_TRADING = True
BACK_TESTING = True

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
    """Reads the active orders file and returns a set of processed dates."""
    if not os.path.exists(ORDER_FILE):
        return None
    
    with open(ORDER_FILE, "r") as file:
        loaded_data = json.load(file)
        return loaded_data

def remove_active_order(data):
    """Writes a new order date to the active orders file."""
    new_order = json.dumps(data)
    symbol = data['tradingsymbol']
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

    # remove the order
    new_orders = []
    for j_order in orders :
        order = json.loads(j_order)

        if order['tradingsymbol'] == symbol :
            continue
        new_orders.append(j_order)
    # Write updated orders back to file
    with open(ORDER_FILE, "w") as file:
        json.dump(new_orders, file, indent=4)
    message = f"Exit: {data['tradingsymbol']}  {data['transactiontype']}  {data['quantity']} {data['netprice']}"
    t_events.info(message)

def write_adjustment(adjustment_date, adjustment_exited, adjustment_entered):
    ''' Adjustments are stored in a file '''
    data = {
            'date': adjustment_date,
            'exited': adjustment_exited, # Symbol exited 
            'entered': adjustment_entered # symbol entered
        }
    new_adjustement = json.dumps(data)
    # Check if file exists
    if os.path.exists(ADJUSTMENT_FILE):
        # Read existing adjustements
        with open(ADJUSTMENT_FILE, "r") as file:
            try:
                adjustements = json.load(file)
            except json.JSONDecodeError:
                adjustements = []  # If file is empty, initialize an empty list
    else:
        adjustements = []

    # Append the new adjustement
    adjustements.append(new_adjustement)

    # Write updated adjustements back to file
    with open(ADJUSTMENT_FILE, "w") as file:
        json.dump(adjustements, file, indent=4)



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
    message = f"Entry: {data['tradingsymbol']}  {data['transactiontype']}  {data['quantity']} {data['netprice']}"
    t_events.info(message)
    print(f"New order added to {ORDER_FILE}")


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
            "symboltoken": "99926000",
            "interval": "ONE_HOUR",
            "fromdate": FROMDATE,
            "todate": TODATE
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


def get_ltp(smartApi,token='99926000',symbol='NIFTY',exchange='NSE'):
    ''' Get LTP for Nifty50 Index '''
    signal.signal(signal.SIGINT, signal_handler)
    #stock_symbol_token_NIFTY = '99926000' # NIFTY token for NSE
    stock_symbol_token_NIFTY = token
    exchange_NIFTY = exchange
    trading_symbol_NIFTY = symbol
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

def exit_positions(smartApi,positions):
    # Its expected that in the positions list , SELL orders are added before BUY 
    # so that margin issues do not occur
    for position in positions :
        order = place_order(smartApi,position)
        remove_active_order(order)


def take_entry_positions(smartApi,positions):
    # Its expected that in the positions list , BUY orders are added before RSELL
    # so that margin issues do not occur
    message = f"Event: Taking Entry"
    t_events.info(message)
    for position in positions :
        order = place_order(smartApi,position)
        write_active_order(order)


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
    if PAPER_TRADING:
        # IN Paper trading since positins will not be with broker , so insert a netprice .
        order['netprice'] = get_ltp(smartApi,token= order['symboltoken'],symbol=order['tradingsymbol'],exchange=order["exchange"])
        print("Not adding real order .. its mock/paper trading")
        #print(order)
        return order
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
    #print(response)
    return order

# Function to get order status
def get_order_status(smart_api, order_id):
    order_book = smart_api.orderBook()
    if order_book["status"] :
        for order in order_book["data"]:
            if order["orderid"] == order_id:
                return order["status"]  # Possible statuses: "COMPLETE", "PENDING", "CANCELLED", etc.
    return "Order not found"

def get_pnl_state(positions,active_trades):
    pnl_total = 4799
    if PAPER_TRADING:
        for j_data in active_trades:
            trade_data = json.loads(j_data)
            tradingsymbol = trade_data['tradingsymbol']
            for position in positions['data'] :
                if position['tradingsymbol'] == tradingsymbol :
                    # Calculate PNL
                    if trade_data['transactiontype'] == 'BUY':
                        trade_qty = trade_data['quantity']
                    else:
                        trade_qty = -trade_data['quantity']


                    pnl = -((float(trade_qty) * float(trade_data['netprice'])) + (float(position['netqty']) * float(position['netprice'])))
                    pnl_total = pnl_total + pnl
        print(f"Paper trading - Current PNL : {pnl_total}")
    else:        
        for j_data in active_trades:
            trade_data = json.loads(j_data)
            tradingsymbol = trade_data['tradingsymbol']
            for position in positions['data'] :
                if position['tradingsymbol'] == tradingsymbol :
                    pnl_total = pnl_total + float(position['unrealised'])
        print(f"Current PNL : {pnl_total}")
    return pnl_total

def position_papertrading(smartApi,all_active_trades):
    expiry = ''
    strike_price = 0
    option_type = ''
    positions = {'data':[]}

    position_template = {'avgnetprice': '0',
                'buyavgprice': '7.7',
                'buyqty': '75',
                'cfbuyamount': '0.0',
                'cfbuyavgprice': '0.0',
                'cfbuyqty': '0',
                'cfsellamount': '7383.37',
                'cfsellavgprice': '98.44',
                'cfsellqty': '75',
                'expirydate': '13MAR2025',
                'instrumenttype': 'OPTIDX',
                'lotsize': '75',
                'ltp': '18.75',
                'netprice': '0.0',
                'netqty': '0',
                'netvalue': '6805.87',
                'optiontype': 'PE',
                'pnl': '6805.50',
                'precision': '2',
                'priceden': '1.00',
                'pricenum': '1.00',
                'sellamount': '0.0',
                'sellavgprice': '0.0',
                'sellqty': '0',
                'strikeprice': '22050.0',
                'symbolgroup': 'XX',
                'symbolname': 'NIFTY',
                'symboltoken': '45443',
                'totalbuyvalue': '577.5',
                'totalsellavgprice': '98.44',
                'totalsellvalue': '7383.37',
                'tradingsymbol': 'NIFTY13MAR2522050PE',
                'unrealised': '0.00'}
    for order in all_active_trades :

        position = position_template.copy()
        active_trades = json.loads(order)
        netqty = int(active_trades['quantity'])
        if active_trades['transactiontype'] == 'BUY':
            # In position trade type is reverse of original trade
            position['netqty'] = -netqty
        else:
            position['netqty'] = netqty
    
        # Regex pattern
        pattern = r'(\d{2}[A-Z]{3}\d{2})(\d+)(CE|PE)'
        
        # Extract details
        match = re.search(pattern, active_trades['tradingsymbol'])
        if match:
            expiry = match.group(1)  # Expiry: 20MAR25
            strike_price = match.group(2)  # Strike Price: 22550
            option_type = match.group(3)  # Option Type: CE
        
        position['expirydate'] = expiry
        position['strikeprice'] = strike_price
        position['optiontype'] = option_type
    
        position['tradingsymbol'] = active_trades['tradingsymbol']
        position['symboltoken'] = active_trades['symboltoken']
        position['exchange'] = active_trades['exchange']
        # IN Paper trading since positins will not be with broker , so insert a netprice when it was purchased and get LTP at time of PNL.
        position['netprice'] = get_ltp(smartApi,token= active_trades['symboltoken'],symbol=active_trades['tradingsymbol'],exchange=active_trades['exchange'])
        positions['data'].append(position)

    return positions


def spread_payoff(smartApi, positions,active_trades):
    active_positions = []
    max_profit = 0
    max_loss = 0
    for j_order in active_trades:
        trade_data = json.loads(j_order)
        tradingsymbol = trade_data['tradingsymbol']
        for position in positions['data'] :
            if position['tradingsymbol'] == tradingsymbol :
                trade = {}
                trade['strike'] = float(position['strikeprice'])
                p_range = (trade['strike']*0.9,trade['strike']*1.1)
                trade['premium'] = float(position['netprice'])
                trade['quantity'] = float(position['netqty'])
                trade['type'] = tradingsymbol[-2:].strip()
                active_positions.append(trade)
    if active_positions:
        max_profit,max_loss = payout.calculate_max_min_payout(active_positions, p_range)
    else:
        print("Anomoally: There are no trading symbols common between active trades(local) and real positions with broker")
        print("Fix the active trade list if trades are exited manually")
    return max_profit, max_loss

def process_exit_trades(smart_api,active_trades, positions, lots = 1):
    position1 = OptionPosition(data.copy())  # Use .copy() to avoid shared state
    position2 = OptionPosition(data.copy())
    trades = []
    for j_data in active_trades:
        trade_data = json.loads(j_data)
        trades.append(trade_data)

    # both legs have same Expiry
    tradingsymbol = trades[0]['tradingsymbol']
    match = re.search(r'[A-Z]+(\d{2}[A-Z]{3}\d{2})\d{5}(PE|CE)', tradingsymbol)
    expiry1 = match.group(1)  # Extract expiry part

    tradingsymbol = trades[1]['tradingsymbol']
    match = re.search(r'[A-Z]+(\d{2}[A-Z]{3}\d{2})\d{5}(PE|CE)', tradingsymbol)
    expiry2 = match.group(1)  # Extract expiry part

    position1.set('expiry', expiry1)
    position2.set('expiry', expiry2)
    
    # get strike price
    match = re.search(r'(\d+)(PE|CE)', trades[0]['tradingsymbol'])
    strike1 = int(match.group(1)[2:]) 
    position1.set('strike', strike1)

    match = re.search(r'(\d+)(PE|CE)', trades[1]['tradingsymbol'])
    strike2 = int(match.group(1)[2:]) 
    position2.set('strike', strike2)

    # get option type 
    position1.set('opt_type', trades[0]['tradingsymbol'][-2:])
    position2.set('opt_type', trades[1]['tradingsymbol'][-2:])

    # get trading symbol token 
    position1.set('symbol_token', trades[0]['symboltoken'])
    position2.set('symbol_token', trades[1]['symboltoken'])

    # get trading symbol
    position1.set('symbol', trades[0]['tradingsymbol'])
    position2.set('symbol', trades[1]['tradingsymbol'])

    # swam tranction type
    if trades[0]['transactiontype'] == "BUY":
        position1.set('order_type', 'SELL')
    else:
        position1.set('order_type', 'BUY')

    if trades[1]['transactiontype'] == "BUY":
        position2.set('order_type', 'SELL')
    else:
        position2.set('order_type', 'BUY')

    # get tranction quantity
    position1.set('quantity', trades[0]['quantity'])
    position2.set('quantity', trades[1]['quantity'])
    
    exit_positions(smartApi,[position1,position2])
    if os.path.exists(ADJUSTMENT_FILE):
        os.remove(ADJUSTMENT_FILE)
    return True 

def spread_adjustment(lots = 1):
    # Move SELL leg closer to BUY leg by 50 points
    position1 = OptionPosition(data.copy())  # Use .copy() to avoid shared state
    position2 = OptionPosition(data.copy())


    active_trades = active_trade()
    for j_data in active_trades:
        trade_data = json.loads(j_data)
        if trade_data['transactiontype'] == 'SELL' :
            existing_leg = trade_data

    # Expiry should be same 
    tradingsymbol = trade_data['tradingsymbol']
    match = re.search(r'[A-Z]+(\d{2}[A-Z]{3}\d{2})\d{5}(PE|CE)', tradingsymbol)
    expiry = match.group(1)  # Extract expiry part
    position1.set('expiry', expiry)
    position2.set('expiry', expiry)
    
    # get strike price near LTP
    match = re.search(r'(\d+)(PE|CE)', trade_data['tradingsymbol'])
    strike = int(match.group(1)[2:]) 
    position1.set('strike', strike)

    # get strike price 200 point OTM
    opt_type =  trade_data['tradingsymbol'][-2:]
    if  opt_type == "CE":
        strike_2 = strike - 50
    else:
        strike_2 = strike + 50
    position2.set('strike', strike_2)

    position1.set('opt_type', opt_type)
    position2.set('opt_type', opt_type)

    # get trading symbol token for this expiry and strike price
    existing_token, new_token, existing_symbol, new_symbol = get_symbol_token('NIFTY',expiry,strike,strike_2, opt_type)

    position1.set('symbol_token', existing_token)
    position2.set('symbol_token', new_token)
    position1.set('symbol', existing_symbol)
    position2.set('symbol', new_symbol)

    position1.set('order_type', "BUY")
    position2.set('order_type', "SELL")
    position1.set('quantity', 75*lots)
    position2.set('quantity', 75*lots)
    
    order = place_order(smartApi, position1)
    remove_active_order(order)
    order = place_order(smartApi, position2)
    write_active_order(order)

    #save adjustment history
    today = datetime.today().strftime("%d%b%y").upper()
    write_adjustment(today, existing_symbol,new_symbol)
    return True 

def room_for_adjustment():
    # Read the strike price difference between BUY and SELL leg, it should be atleast 50 points
    strike_prices = []
    active_trades = active_trade()
    for j_data in active_trades:
        trade_data = json.loads(j_data)

        match = re.search(r'(\d+)(PE|CE)', trade_data['tradingsymbol'])
        if match:
            strike = match.group(1)[2:]  # Convert to integer
            strike_prices.append(int(strike))
    if len(strike_prices) == 2:
        if abs(strike_prices[0] - strike_prices[1]) > 50:
            print("We have room for adjustment !!")
            return True
        else :
            return False
    else :
        #There is something wrong , as comparison ca happen on two numbers only
        raise("Insufficient strike prices to compare")


def adjustment_done_today():
    ''' One one adjustment a day '''
    if not os.path.exists(ADJUSTMENT_FILE):
        print("No adjustments done yet !!")
        return False
    with open(ADJUSTMENT_FILE, "r") as file:
        try:
            adjustments = json.load(file)
        except json.JSONDecodeError:
            return False 
        today = datetime.today().strftime("%d%b%y").upper()
        for rec in adjustments : 
            record = json.loads(rec)
            if record["date"] == today :
                return True
        return False

def process_adjustments(max_loss, pnl):
    # If we are in 25% of max loss , do adjustments 
    # Only one adjustments a day , max till 50 point away from ATM strike
    print("Processing adjustments ")
    if pnl > 0 :
        print("No adjustments needed , PNL is +ve")
        return False
    if max_loss*0.25 < pnl and not adjustment_done_today() and room_for_adjustment():
        print("Performing adjustments..")
        message = f"Event: Making adjustment to reduce loss"
        t_events.info(message)
        return spread_adjustment()
    else:
        print("No Padjustments needed..")
        return False


def exit_trades(max_profit, max_loss, pnl):
    # Exit all positions if we are at more than 50% of max loss 
    if max_profit*0.5 < pnl :
        print("Exit order as target acheived ..")
        message = f"Event: Target acheived"
        t_events.info(message)
        return True
    elif max_loss*0.5 > pnl :
        print("Exit order as Stop Loss hit ..",max_loss*0.5,pnl)
        message = f"Event: SL hit"
        t_events.info(message)
        return True
    return False

def process_open_positions(smart_api):    
    active_trades = active_trade()
    positions = smart_api.position()
    if active_trades and PAPER_TRADING :
        # Its paper trading , so there will not be positions in broker's DB
        # Create a virtual position based on LTP and active trades.
        positions = position_papertrading(smartApi, active_trades)
        #print('Positions',positions)

    pnl = get_pnl_state(positions,active_trades)
    max_profit,max_loss = spread_payoff(smartApi, positions, active_trades)

    if not process_adjustments(max_loss, pnl):
        # if adjustment done ignore exit evaluation that time
        if exit_trades(max_profit,max_loss,pnl):
            process_exit_trades(smart_api,active_trades, positions)
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
        process_open_positions(smartApi)    
    else :
        # Entry workflow 
        df = fetch_ohlc(smartApi)
    
        # Identify trends
        trend = get_sma_trend(df)
     
        # based on trend create Call/Put spread positions
        positions = create_spread_position(smartApi,trend, LOTS)


        # Generate trade
        take_entry_positions(smartApi,positions)

if __name__ == "__main__":
    smartApi = connect_angeloone()
    if not smartApi :
        sys.exit("Failied while connecting to server")
    fetch_data(smartApi)
    main(smartApi)
    logout(smartApi)

