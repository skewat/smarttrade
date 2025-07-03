import os
import sys
import csv
import copy
import re
from datetime import datetime, timedelta, time
import time
import pandas as pd
from logzero import logger
import signal

# Project Imports
current_dir = os.path.dirname(os.path.abspath(__file__))
base_path = os.path.abspath(os.path.join(current_dir, ".."))
sys.path.append(base_path)

import config
from common_utils import (
    till_date_ohlc_data,
    expiries_of_year,
    place_order,
    symboltoken,
    opt_position,
    angelone,
    smartapi_wrapper,
)
# ========================================
# UTILITY FUNCTIONS
# ========================================

def is_within_time_range():
    """Check if current time is within trading hours."""
    now = datetime.now()
    return now.replace(hour=9, minute=18) <= now <= now.replace(hour=15, minute=15)

def signal_handler(sig, frame):
    """Handle SIGINT (Ctrl+C) to exit gracefully."""
    logger.info("\nExiting gracefully...")
    sys.exit(0)

def write_positions_to_csv(positions, filename, append):
    """Write positions to CSV."""
    if not positions:
        return

    fieldnames = positions[0].data.keys()
    mode = 'a' if append else 'w'
    write_header = not append or not os.path.exists(filename)

    with open(filename, mode=mode, newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        for position in positions:
            writer.writerow(position.data)


def convert_to_5min(df):

    # Assuming you've already loaded the DataFrame (df)
    # Example: df = pd.read_csv("your_file.csv")

    # Step 1: Convert 'datetime' column to datetime type
    df['datetime'] = pd.to_datetime(df['datetime'])

    # Step 2: Set 'datetime' as index
    df.set_index('datetime', inplace=True)

    # Step 3: Resample to 5-minute OHLC
    df_5min = df.resample('5min').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last'
    })

    # Step 4: Drop incomplete candles if any
    df_5min.dropna(inplace=True)

    # Step 5: Reset index (optional)
    df_5min.reset_index(inplace=True)

    return  df_5min

def get_ltp(connector, token='99926000', symbol='NIFTY', exchange='NSE'):
    """Fetch latest traded price (LTP) from API."""
    smart_api = connector.smart_api
    wrapper_api = smartapi_wrapper.SmartAPIWrapper(smart_api)
    data = wrapper_api.get_ltp(exchange,symbol,token)

    return data['data']['ltp']

def get_token(name):
    token = symboltoken.get_single_symbol_token(name, 'OPTION')
    return token 


def find_valid_expiry(expiries):
    """Pick the first expiry > 2 days from today."""
    dt = datetime.today()
    expiry = next((datetime.strptime(e, "%d%b%y") for e in expiries if datetime.strptime(e, "%d%b%y") > dt + timedelta(days=2)), None)
    return expiry.strftime('%d%b%y').upper() if expiry else None


def modify_limit_orders_to_market(connector, tag_to_match = None):
    try:
        # 1. Get all open orders
        order_api = place_order.main(connector)
        orders = order_api.get_order_book()

        for order in orders:
            # 2. Check for tag and order type
            if (order.get("order_tag") == tag_to_match and
                order.get("orderstatus") == "open" and
                order.get("ordertype") == "LIMIT"):

                # 3. Modify order to market
                modified_order = smart_api.modifyOrder(
                    orderid=order["orderid"],
                    variety=order["variety"],           # e.g. 'NORMAL'
                    tradingsymbol=order["tradingsymbol"],
                    symboltoken=order["symboltoken"],
                    transactiontype=order["transactiontype"],  # 'BUY' or 'SELL'
                    exchange=order["exchange"],         # e.g. 'NSE'
                    ordertype="MARKET",
                    producttype=order["producttype"],   # e.g. 'INTRADAY'
                    duration=order["duration"],         # e.g. 'DAY'
                    quantity=order["quantity"]
                )
                logger.info(f"Modified Order ID {order['orderid']} to MARKET")

    except Exception as e:
        print(f"Error: {e}")

def force_exit_positions(connector):
    if is_there_existing_trade():
        active_positions = get_active_positions()
        exit_positions = process_option_buy_exit(connector, active_positions)
        place_order.main(connector, exit_positions, 'EXIT')
        logger.info('Exited by force.....')

def decode_option_symbol(symbol):
    """
    Decodes an option symbol like NIFTY03JUL2525800CE
    and returns its components in a dictionary.
    """
    pattern = r"([A-Z]+)(\d{2}[A-Z]{3}\d{2})(\d+)(CE|PE)"
    match = re.match(pattern, symbol)

    if not match:
        raise ValueError(f"Invalid option symbol format: {symbol}")

    underlying = match.group(1)
    expiry_str = match.group(2)
    strike = int(match.group(3))
    option_type = match.group(4)

    # convert expiry to YYYY-MM-DD
    try:
        expiry_date = datetime.strptime(expiry_str, "%d%b%y").strftime("%Y-%m-%d")
    except Exception:
        expiry_date = None

    return {
        "underlying": underlying, # NIFTY
        "expiry_str": expiry_str, # 05JUL25
        "expiry": expiry_date, #2025-07-05
        "option_type": option_type, # PE/CE
        "strike": strike , #24500
    }

# ========================================
# Place Order
# ========================================
def process_order(connector, trade_info, lots=1):
    """Process entry for single option buying."""
    STRATEGY_TAG = config.STRATEGY
    opt_data = decode_option_symbol(trade_info['symbol'])
    position = opt_position.OptionPosition({
        'expiry': opt_data['expiry'],
        'opt_type': opt_data['option_type'],
        'quantity': lots * config.LOTSIZE,
        'position_type': 'ENTRY',
        })

    token = get_token( trade_info['symbol'])
    position.set('strike', opt_data['strike'])
    position.set('symbol_token', token) # TBD
    position.set('symbol', trade_info['symbol'])
    position.set('order_type', trade_info['action'])
    position.set('price', get_ltp(connector, token, trade_info['symbol'], 'NFO'))
    position.set('time_stamp', trade_info["timestamp"])
    position.set('strategy_tag',STRATEGY_TAG)

    place_order.main(connector, position, trade_info['position'])
    write_positions_to_csv([position], config.ACTIVE_TRADES_CSV, 'w')
    write_positions_to_csv([position], config.ARCHIVE_TRADES_CSV, 'a')
    return True
