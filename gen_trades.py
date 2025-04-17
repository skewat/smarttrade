import pandas as pd
from datetime import datetime, timedelta
import pprint 
import sys
import expiries_of_year
import supertrend
import sma
import os

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
                'entry_strike_price_atm': int(spot_ltp // 50) * 50 ,
                'entry_strike_price_otm': int(spot_ltp // 50) * 50 + 200,
                'expiry': expiry,
                'type': option_type
            }

    elif option_type == "PE" :
        # Bear spread
        o_expiries = [ datetime.strptime(e, "%d%b%y") for e in option_expiries ]
        expiry = next((e for e in o_expiries if e > dt + timedelta(days=6)), None)
        if expiry:
            position = {
                'entry_strike_price_atm': int(spot_ltp // 50) * 50 ,
                'entry_strike_price_otm': int(spot_ltp // 50) * 50 - 200 ,
                'expiry': expiry,
                'type': option_type
            }
    return position

def process_exit():

    file_path = "active_spread_trades.csv"
    os.remove(file_path)
    return 


# Check If there is already a trade
def is_there_existing_trade():
    if os.path.exists('active_spread_trades.csv'):
        return True
    else:
        return False

def trend_reversed():
    return True

# If there is already a trade
def process_existing_trade():
    if trend_reversed() or is_expiryday():
        process_exit()
        return

def get_trend(spot_indicators_df):
    return 1


def new_trade(file_name,ltp):
    ''' Process a new trade if applicable '''
    trend = get_trend(file_name) 
    if trend == 1 :
        trade_type = "CE"
    elif trend == -1 :
        trade_type = 'PE'
    else :
        return

    year = datetime.now().year
    option_expiries = expiries_of_year.main(year)
    print('---->',option_expiries)
    trades = debit_spread_strategy(option_expiries,ltp,trade_type)

    # Convert to DataFrame
    print(trades)

    # Convert to DataFrame
    df = pd.DataFrame([trades])  # Wrap in a list for one row

    # Save to CSV
    s_file = "active_spread_trades.csv"
    df.to_csv(s_file, index=False)

    return s_file

def main(file_name = None,ltp = 23800):
    ''' Input is DF with inicators, here we take call if we hit trigger to take trade or exit a trade '''

    if is_there_existing_trade():
        process_existing_trade()
    else:
        # Take a new trade
        new_trade(file_name,ltp)

if __name__ == '__main__':
    today = datetime.today().date()

    print('t_nifty50_ohlc_2025-04-16.csv')
    data_file = f"t_nifty50_ohlc_{today}.csv"
    print(data_file)
    super_file = supertrend.main(data_file)
    print('+'*80,super_file)
    sma_file = sma.main(super_file)
    print('!'*80,sma_file)

    main(sma_file)


