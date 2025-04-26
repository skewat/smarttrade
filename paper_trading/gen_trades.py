#! /usr/bin/python3
import pandas as pd
from SmartApi import SmartConnect
from datetime import datetime,time, timedelta
from logzero import logger 
import sys
import os
from login_details import *
from logzero import logger 
import pyotp
import sys
import signal
import os
import copy 
import csv
import symboltoken
import opt_position 
import till_date_ohlc_data
import expiries_of_year
import supertrend
import sma
import place_order


LOTSIZE = 75
ACTIVE_TRADES_CSV = "active_spread_trades.csv"
ARCHIVE_TRADES_CSV = "archive_spread_trades.csv"
LIVE = False

def write_positions_to_csv(position1, position2, filename, append):
    # Create a list of dictionaries
    positions = [position1.data, position2.data]

    # Get all field names from the first position
    fieldnames = positions[0].keys()

    # Determine write mode and whether to write the header
    mode = 'a' if append else 'w'
    write_header = not append or not os.path.exists(filename)

    with open(filename, mode=mode, newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)

        if write_header:
            writer.writeheader()

        for position in positions:
            writer.writerow(position)


def process_spread_positions_exit(smart_api, trades ):
    position1 = opt_position.OptionPosition(trades[0])
    position2 = opt_position.OptionPosition(trades[1])

    if position1.get('order_type') == 'SELL':
        position1.set('order_type', 'BUY')
        position2.set('order_type', 'SELL')
    elif position1.get('order_type') == 'BUY':
        position1.set('order_type', 'SELL')
        position2.set('order_type', 'BUY')

    price1 = get_ltp(smart_api,position1.get('symbol_token'),position1.get('symbol'),'NFO')
    price2 = get_ltp(smart_api,position2.get('symbol_token'),position2.get('symbol'),'NFO')
    position1.set('price',price1)
    position2.set('price', price2)
    position1.set('position_type','EXIT')
    position2.set('position_type', 'EXIT')
    now = datetime.now()
    position1.set('time_stamp',now)
    position2.set('time_stamp',now)
    write_positions_to_csv(position1, position2, ARCHIVE_TRADES_CSV,'a')
    if os.path.exists(ACTIVE_TRADES_CSV):
       os.remove(ACTIVE_TRADES_CSV)
    return [position1,position2]


def process_spread_positions_entry(smart_api, trades, lots = 1 ):

    original = opt_position.OptionPosition({'expiry':trades['expiry'],
                                            'opt_type':trades['type'],
                                            'quantity':lots*LOTSIZE,
                                            'position_type':'ENTRY',
                                          })

    position1 = opt_position.OptionPosition(copy.deepcopy(original.data))
    position2 = opt_position.OptionPosition(copy.deepcopy(original.data))
    
    # both legs have same Expiry
    position1.set('expiry', trades['expiry'])
    position2.set('expiry', trades['expiry'])
    
    # get strike price
    position1.set('strike', trades['strike_price_otm'])

    position2.set('strike',  trades['strike_price_atm'])

    # get option type 
    position1.set('opt_type', trades['type'])
    position2.set('opt_type', trades['type'])

    # get trading symbol token 
    position1.set('symbol_token', trades['otm_token'])
    position2.set('symbol_token', trades['atm_token'])

    # get trading symbol
    position1.set('symbol', trades['otm_symbol'])
    position2.set('symbol', trades['atm_symbol'])

    position1.set('order_type', 'SELL')
    position2.set('order_type', 'BUY')

    # get tranction quantity
    position1.set('quantity', lots*LOTSIZE)
    position2.set('quantity', lots*LOTSIZE)

    atm_price = get_ltp(smart_api,trades['atm_token'],trades['atm_symbol'],'NFO')
    otm_price = get_ltp(smart_api,trades['otm_token'],trades['otm_symbol'],'NFO')
    position1.set('price', otm_price)
    position2.set('price', atm_price)

    now = datetime.now()
    position1.set('time_stamp',now)
    position2.set('time_stamp',now)

    write_positions_to_csv(position1, position2, ACTIVE_TRADES_CSV,'w')
    write_positions_to_csv(position1, position2, ARCHIVE_TRADES_CSV,'a')
    return position1,position2

def get_ltp(smartApi,token='99926000',symbol='NIFTY',exchange='NSE'):
    ''' Get LTP for Nifty50 Index '''
    signal.signal(signal.SIGINT, signal_handler)
    stock_symbol_token = token
    exchange = exchange
    trading_symbol = symbol
    
    data = smartApi.ltpData(exchange, trading_symbol, stock_symbol_token)
    return (data['data']['ltp'])


def debit_spread_strategy(option_expiries, spot_ltp,option_type):
    """
    Args:
        csv_path: Path to the CSV file with Supertrend and SMA data.
        option_expiries: List of expiry dates (datetime objects) for available options.
    """
    position = None
    dt = datetime.today()
     
    # Entry logic
    if option_type == 'CE' :
        # Bull spread
        o_expiries = [ datetime.strptime(e, "%d%b%y") for e in option_expiries ]
        expiry = next((e for e in o_expiries if e > dt + timedelta(days=6)), None)
        expiry = expiry.strftime('%d%b%y').upper()
        if expiry:
            position = {
                'strike_price_atm': int(spot_ltp // 50) * 50 ,
                'strike_price_otm': int(spot_ltp // 50) * 50 + 200,
                'expiry': expiry,
                'type': option_type
            }

    elif option_type == "PE" :
        # Bear spread
        o_expiries = [ datetime.strptime(e, "%d%b%y") for e in option_expiries ]
        expiry = next((e for e in o_expiries if e > dt + timedelta(days=6)), None)
        expiry = expiry.strftime('%d%b%y').upper()
        if expiry:
            position = {
                'strike_price_atm': int(spot_ltp // 50) * 50 ,
                'strike_price_otm': int(spot_ltp // 50) * 50 - 200 ,
                'expiry': expiry,
                'type': option_type
            }
    return position

def get_active_positions():
    filename = ACTIVE_TRADES_CSV
    with open(filename, mode='r', newline='') as file:
        reader = csv.DictReader(file)
        positions = [row for row in reader]
    return positions

# Check If there is already a trade
def is_there_existing_trade():
    if os.path.exists(ACTIVE_TRADES_CSV):
        df = pd.read_csv(ACTIVE_TRADES_CSV)
        try :
            first_opt_type = df['opt_type'].iloc[0]
            return True
        except :
            sys.exit("Corrupted active trade DB file ")
    else:
        return False


# If there is already a trade
def process_existing_trade(smart_api):
    positions = get_active_positions()
    exit_positions = process_spread_positions_exit(smart_api, positions)
    if LIVE :
        place_order.main(smart_api,exit_positions,'EXIT')
   
def get_trend(spot_indicators_df, type="ENTRY"):

    # Sample: loading your CSV
    df = pd.read_csv(spot_indicators_df)
    
    # Get the last row
    last_row = df.iloc[-1]
    if type == 'ENTRY':
        # Check the BULLISH condition
        if last_row['signals'] == 1 and last_row['close'] > last_row['SMA_21']:
            return 1
        elif last_row['signals'] == -1 and last_row['close'] < last_row['SMA_21']:
            return -1
        else :
            return 0
    elif type == 'EXIT' :
        if last_row['signals'] == 1 :
            return 1
        elif last_row['signals'] == -1 :
            return -1


def new_trade(file_name, spot_ltp):
    ''' Process a new trade if applicable '''
    trend = get_trend(file_name, 'ENTRY') 
    
    if trend == 1 :
        print("Trend is bullish..")
        trade_type = "CE"
    elif trend == -1 :
        print("Trend is bearish..")
        trade_type = 'PE'
    else :
        print("Trend is non decisive ..")
        return

    year = datetime.now().year
    option_expiries = expiries_of_year.main(year)
    trades = debit_spread_strategy(option_expiries, spot_ltp,trade_type)
    atm_t, otm_t, atm_s, otm_s = get_symbol_token('NIFTY',
                                                  trades['expiry'],
                                                  trades['strike_price_atm'], 
                                                  trades['strike_price_otm'],
                                                  trades['type'])
    trades['atm_token'] = atm_t
    trades['otm_token'] = otm_t
    trades['otm_symbol'] = otm_s
    trades['atm_symbol'] = atm_s

    return trades

def connect_angelone():
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

def logout(smartAPi):
    # logout from AngenOne API
    try:
        logout = smartApi.terminateSession('AAAE362329')
        print("\n\n\n")
        logger.info("Logout Successfull")
    except Exception as e:
        logger.exception(f"Logout failed: {e}")

def get_symbol_token(name, expiry, strike_atm, strike_otm,opt_type):
    '''Symbol token is needed for placing order and historical data , this token is not generic and
       it's provided by angelone @
       curl -k https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json
       We store it in symbol_token.py and import it as this gives next few years data.
    '''
    atm_token = None
    otm_token = None
    data = symboltoken.main()
    for i in data:
        if i['exch_seg'] == 'NFO' and  i['name'] == name :
            atm_symbol = f"{name}{expiry}{strike_atm}{opt_type}"
            otm_symbol = f"{name}{expiry}{strike_otm}{opt_type}"
            if i['symbol'] == atm_symbol:
                atm_token = i['token']

            elif i['symbol'] == otm_symbol:
                otm_token = i['token']
                
    if not atm_token or not otm_token :
        print("Error !! trading token not found",atm_symbol,otm_token)
    else:
        return atm_token, otm_token, atm_symbol, otm_symbol

def signal_handler(sig, frame):
    ''' This is system signal handelr not related to stock/trend signal '''
    print("\nExiting gracefully...")
    disconnect(SmartApi)
    sys.exit(0)

def main(smart_api, file_name = None, spot_ltp = 23800):
    ''' Input is DF with inicators, here we take call if we hit trigger to take trade or exit a trade '''
    spot_ltp = get_ltp(smart_api,'99926000','NIFTY','NSE')
    if is_there_existing_trade():
        df = pd.read_csv(ACTIVE_TRADES_CSV)
        opt_type = df['opt_type'].iloc[0]
        trend = get_trend(file_name, 'EXIT') 

        # Get expiry from first row
        expiry_str = df['expiry'].iloc[0]
        # Convert expiry string to date
        expiry_date = datetime.strptime(expiry_str, "%d%b%y").date()
        # Get today's date
        today = datetime.today().date()
        # Check current time
        current_time = datetime.now().time()

        # Logic to check expiry date and time
        if expiry_date == today and current_time >= time(14, 30):
            process_existing_trade(smart_api)
            print("Exited the trade on expiry ..")

        if opt_type == 'CE' and trend == 1 :
            return
        if opt_type == 'PE' and trend == -1 :
            return
        # Trend have changed so exit the trade
        process_existing_trade(smart_api)
        print("Exited the trade ..  change in trend")

    if not is_there_existing_trade():
        # Take a new trade
        trades = new_trade(file_name, spot_ltp)
        if not trades :
            print('No new trades taken .. ')
            return
        position1,position2 = process_spread_positions_entry(smart_api, trades, lots = 1)
        if LIVE and trades:
            place_order.main(smart_api,[position1,position2],'ENTRY')
        print('Taking entry position',position1.data,position2.data)

def ohlc_with_retry(delay_seconds=5):
    ohlc_df = pd.DataFrame()  # Initialize as an empty DataFrame
    while True:
        ohlc_df = till_date_ohlc_data.main(smartApi)
        if ohlc_df.empty:
            time.sleep(delay_seconds)
        else:
            return ohlc_df

def connect_with_retry(delay_seconds=5):
    while True:
        smartApi = connect_angelone()
        if smartApi:
            print("Connected successfully to AngelOne!")
            return smartApi
        else:
            print(f"Failed to connect. Retrying in {delay_seconds} seconds...")
            time.sleep(delay_seconds)

if __name__ == '__main__':
    smartApi = connect_with_retry()
    ohlc_df = till_date_ohlc_data.main(smartApi)

    super_file = supertrend.main(ohlc_df)
    sma_file = sma.main(super_file)
    main(smartApi, sma_file)
    logout(smartApi)
