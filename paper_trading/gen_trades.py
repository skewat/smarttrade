#! /usr/bin/python3
import pandas as pd
from SmartApi import SmartConnect
from datetime import datetime, timedelta
import pprint 
import sys
from logzero import logger 
import expiries_of_year
import supertrend
import sma
import os
from login_details import *
from logzero import logger 
import symboltoken
import pyotp
import sys
import signal
import os
import opt_position 
import copy 
import csv
import till_date_ohlc_data


LOTSIZE = 75
ACTIVE_TRADES_CSV = "active_spread_trades.csv"
ARCHIVE_TRADES_CSV = "archive_spread_trades.csv"

#def write_positions_to_csv(position1, position2, filename, append):
#    # Create a list of dictionaries
#    positions = [position1.data, position2.data]
#
#    # Get all field names from the first position
#    fieldnames = positions[0].keys()
#
#    # Write to CSV
#
#    with open(filename, mode=append, newline='') as file:
#        writer = csv.DictWriter(file, fieldnames=fieldnames)
#        writer.writeheader()
#        for position in positions:
#            writer.writerow(position)
#    print(f"Wrote to {filename}")

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
    #with open(trades_csv, mode='r') as file:
    #    reader = csv.DictReader(file)
    #    trades = [row for row in reader][0]
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
    write_positions_to_csv(position1, position2, ARCHIVE_TRADES_CSV,'a')
    if os.path.exists(ACTIVE_TRADES_CSV):
       os.remove(ACTIVE_TRADES_CSV)


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

def process_exit():
    filename = ACTIVE_TRADES_CSV
    with open(filename, mode='r', newline='') as file:
        reader = csv.DictReader(file)
        positions = [row for row in reader]
    return positions




# Check If there is already a trade
def is_there_existing_trade():
    if os.path.exists(ACTIVE_TRADES_CSV):
        return True
    else:
        return False

def trend_reversed():
    return True

# If there is already a trade
def process_existing_trade(smart_api):
    if trend_reversed() or is_expiryday():
        positions = process_exit()
        process_spread_positions_exit(smart_api, positions)
        return

def get_trend(spot_indicators_df):

    # Sample: loading your CSV
    df = pd.read_csv(spot_indicators_df)
    
    # Get the last row
    last_row = df.iloc[-1]

    # Check the BULLISH condition
    if last_row['signals'] == 1 and last_row['close'] > last_row['SMA_21']:
        return 1
    elif last_row['signals'] == -1 and last_row['close'] < last_row['SMA_21']:
        return -1
    else :
        return 0


def new_trade(file_name, spot_ltp):
    ''' Process a new trade if applicable '''
    trend = get_trend(file_name) 
    
    if trend == 1 :
        print("Trend is Bulish..")
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
        process_existing_trade(smart_api)
    else:
        # Take a new trade
        trades = new_trade(file_name, spot_ltp)
        if not trades :
            print('No trades taken .. ')
            return
        position1,position2 = process_spread_positions_entry(smart_api, trades, lots = 1)
        print(position1.data)
        print(position2.data)
if __name__ == '__main__':
    smartApi = connect_angeloone()
    if not smartApi :
        sys.exit("Failied while connecting to server")

    ohlc_df = till_date_ohlc_data.main(smartApi)

    #today = datetime.today().date()
    #today = datetime.today().date() - timedelta(days=1)
    #data_file = f"../data/ohlc_data/t_nifty50_ohlc_{today}.csv"
    super_file = supertrend.main(ohlc_df)
    sma_file = sma.main(super_file)
    main(smartApi, sma_file)
    logout(smartApi)

