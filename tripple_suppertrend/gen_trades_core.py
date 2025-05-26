#! /usr/bin/python3

import os
import sys
import csv
import copy
from datetime import datetime, timedelta, time
import time
import pandas as pd
from logzero import logger
import signal
import supertrend
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
    sma,
    angelone,
    smartapi_wrapper,
)

STRATEGY_TAG = "SUPER_TREND"

# ========================================
# UTILITY FUNCTIONS
# ========================================

simulate_timestamp = None

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

def get_ltp(connector, token='99926000', symbol='NIFTY', exchange='NSE', timestamp = None):
    """Fetch latest traded price (LTP) from API."""
    global simulate_timestamp
    if config.SIMULATE :
        return get_ltp_from_file(config.CSV_FILE, simulate_timestamp)
    else:
        smart_api = connector.smart_api
        wrapper_api = smartapi_wrapper.SmartAPIWrapper(smart_api)
        data = wrapper_api.get_ltp(exchange,symbol,token)
        return data['data']['ltp']

# ========================================
# ENTRY & EXIT PROCESSORS
# ========================================

def process_option_buy_entry(connector, trade_info, lots=1):
    """Process entry for single option buying."""
    position = opt_position.OptionPosition({
        'expiry': trade_info['expiry'],
        'opt_type': trade_info['type'],
        'quantity': lots * config.LOTSIZE,
        'position_type': 'ENTRY',
    })

    position.set('strike', trade_info['strike_price_atm'])
    position.set('symbol_token', trade_info['atm_token'])
    position.set('symbol', trade_info['atm_symbol'])
    position.set('order_type', 'BUY')
    position.set('price', get_ltp(connector, trade_info['atm_token'], trade_info['atm_symbol'], 'NFO'))
    position.set('time_stamp', datetime.now().strftime("%d-%m-%Y:%H:%M:%S"))
    position.set('strategy_tag',STRATEGY_TAG)

    write_positions_to_csv([position], config.ACTIVE_TRADES_CSV, 'w')
    write_positions_to_csv([position], config.ARCHIVE_TRADES_CSV, 'a')
    return [position]

def process_option_buy_exit(connector, positions):
    """Exit active positions."""
    exit_positions = []
    for pos in positions:
        position = opt_position.OptionPosition(pos)
        position.set('order_type', 'BUY' if position.get('order_type') == 'SELL' else 'SELL')
        position.set('price', get_ltp(connector, position.get('symbol_token'), position.get('symbol'), 'NFO'))
        position.set('position_type', 'EXIT')
        position.set('time_stamp', datetime.now())
        position.set('strategy_tag',STRATEGY_TAG)
        exit_positions.append(position)

    write_positions_to_csv(exit_positions, config.ARCHIVE_TRADES_CSV, 'a')
    if os.path.exists(config.ACTIVE_TRADES_CSV):
        os.remove(config.ACTIVE_TRADES_CSV)
    return exit_positions

# ========================================
# STRATEGY FUNCTIONS
# ========================================

def option_buy_strategy(option_expiries, spot_ltp, option_type):
    """Decide an option buying strategy based on trend."""
    expiry = find_valid_expiry(option_expiries)
    if not expiry:
        return None
    return {
        'strike_price_atm': int(spot_ltp // 50) * 50,
        'expiry': expiry,
        'type': option_type
    }

def find_valid_expiry(expiries):
    """Pick the first expiry > 6 days from today."""
    dt = datetime.today()
    expiry = next((datetime.strptime(e, "%d%b%y") for e in expiries if datetime.strptime(e, "%d%b%y") > dt + timedelta(days=2)), None)
    return expiry.strftime('%d%b%y').upper() if expiry else None

def get_trend(file_path, timestamp = None) -> int:
    """
    Check for a signal change in the indicator file.

    If timestamp is provided, compares signal at that time and the previous one.
    If not, compares the last two signals in the file.

    Args:
        file_path (str): Path to the CSV file with 'timestamp' and 'signals' columns.
        timestamp (str, optional): Timestamp to check (must match the format in CSV exactly).

    Returns:
        int: Latest signal (1 or -1) if there's a trend change, else 0.
    """
    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        return 0

    return df.iloc[-1]['entry_flag'],df.iloc[-1]['exit_flag']

    if 'signals' not in df.columns:
        logger.warning(f"signal not in column")
        return 0

    if timestamp is not None:
        if 'datetime' not in df.columns:
            logger.warning(f"datetime not in column, check if it is Datetime ?")
            return 0

        df['datetime'] = pd.to_datetime(df['datetime'])
        try:
            target_time = pd.to_datetime(timestamp)
        except Exception as e:
            logger.warning(f"Invalid timestamp: {e}")
            return 0

        row_index = df.index[df['datetime'] == target_time].tolist()
        if not row_index:
            logger.warning(f"Row index empty")
            return 0
        idx = row_index[0]

        if idx == 0:
            logger.warning(f"No previous row to compare")
            return 0  # No previous row to compare

        prev_signal = df.iloc[idx - 1]['signals']
        latest_signal = df.iloc[idx]['signals']
    else:
        if len(df) < 2:
            logger.warning(f"Data Frame too small")
            return 0
        prev_signal = df.iloc[-2]['signals']
        latest_signal = df.iloc[-1]['signals']
    return df.iloc[-1]['entry_flag'],df.iloc[-1]['exit_flag']



#    # Validate and compare
#    if pd.isna(prev_signal) or pd.isna(latest_signal):
#        logger.warning(f"Both signals are needed to compare")
#        return 0
#
#    try:
#        prev_signal = int(prev_signal)
#        latest_signal = int(latest_signal)
#    except ValueError:
#        logger.warning(f"Value error: {e}")
#        return 0
#
#    if prev_signal != latest_signal and latest_signal in [1, -1] and prev_signal in [1, -1]:
#        logger.info(f"{timestamp}  Trend {latest_signal} prev {prev_signal} latest {latest_signal}")
#        return latest_signal
#    else:
#        return 0

# ========================================
# TRADE MANAGEMENT
# ========================================

def convert_to_5min(df):

    # Assuming you've already loaded the DataFrame (df)
    # Example: df = pd.read_csv("your_file.csv")
    
    # Step 1: Convert 'datetime' column to datetime type
    df['datetime'] = pd.to_datetime(df['datetime'])
    
    # Step 2: Set 'datetime' as index
    df.set_index('datetime', inplace=True)
    
    # Step 3: Resample to 5-minute OHLC
    df_5min = df.resample('5T').agg({
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

def modify_limit_orders_to_market(connector, tag_to_match = STRATEGY_TAG):
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

def is_there_existing_trade():
    """Check if there is an active open trade."""
    return os.path.exists(config.ACTIVE_TRADES_CSV) and not pd.read_csv(config.ACTIVE_TRADES_CSV).empty

def get_active_positions():
    """Read active trades."""
    with open(config.ACTIVE_TRADES_CSV, mode='r', newline='') as file:
        return list(csv.DictReader(file))

def new_trade(file_path, spot_ltp,timestamp=None):
    """Create a new trade idea based on indicator trend."""
    entry_trend,exit_trend  = get_trend(file_path,timestamp)
    trade = None
    trend = entry_trend 
    if trend not in ['ENTRY_BULLISH','ENTRY_BEARISH']:
        logger.info(f"No decisive trend.... ")
        return None

    option_type = "CE" if trend == 'ENTRY_BULLISH' else "PE"
    year = datetime.now().year
    option_expiries = expiries_of_year.main(year)

    trade = option_buy_strategy(option_expiries, spot_ltp, option_type)

    if trade:
        atm_t, otm_t, atm_s, otm_s = symboltoken.get_symbol_token(
            'NIFTY', trade['expiry'],
            trade['strike_price_atm'],
            trade.get('strike_price_otm', trade['strike_price_atm']),
            trade['type']
        )
        trade.update({
            'atm_token': atm_t,
            'atm_symbol': atm_s,
            'otm_token': otm_t,
            'otm_symbol': otm_s
        })
    return trade

def get_ltp_from_file(file_path,timestamp):
    """
    Return the 'close' price from the row with the timestamp closest to the given one.

    Args:
        file_path (str): Path to the CSV file with 'timestamp' and 'close' columns.
        timestamp (str): Target timestamp string to match.

    Returns:
        float: The close price (LTP) closest to the given timestamp. Returns None if not found.
    """
    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        return None

    if 'datetime' not in df.columns or 'close' not in df.columns:
        logger.error("Missing required columns 'timestamp' or 'close'")
        return None

    # Convert to datetime
    try:
        df['timestamp'] = pd.to_datetime(df['datetime'])
        target_time = pd.to_datetime(timestamp)
    except Exception as e:
        logger.error(f"Timestamp parsing error: {e}")
        return None

    if df.empty:
        return None

    # Find row with closest timestamp
    df['time_diff'] = (df['timestamp'] - target_time).abs()
    closest_row = df.loc[df['time_diff'].idxmin()]

    return closest_row['close']


def process(connector, file_path, tick_time = None):
    """Main decision logic: Entry or Exit based on trend."""
    global simulate_timestamp
    simulate_timestamp = tick_time
    place_order_obj = place_order.main(connector)
    if config.SIMULATE :
        spot_ltp = get_ltp_from_file(file_path,tick_time)
    else :
        spot_ltp = get_ltp(connector, '99926000', 'NIFTY', 'NSE', tick_time)
    if is_there_existing_trade():
        active_positions = get_active_positions()
        entry_trend,exit_trend = get_trend(file_path, tick_time)
        trend_now = exit_trend
        df = pd.read_csv(config.ACTIVE_TRADES_CSV)
        opt_type = df['opt_type'].iloc[0]
        expiry = datetime.strptime(df['expiry'].iloc[0], "%d%b%y").date()
        today = datetime.today().date()
        current_time = datetime.now().time()

        if expiry == today and current_time >= time(14, 50):
            exit_positions = process_option_buy_exit(connector, active_positions)
            if config.LIVE:
                place_order.main(connector, exit_positions, 'EXIT')
            logger.info('Exited on expiry.')
            return
        if not trend_now == 'EXIT' :
            logger.info(f"{tick_time} Trend unchanged, Trend {trend_now}.")
            return

        #if (opt_type == 'CE' and trend_now == 1) or (opt_type == 'PE' and trend_now == -1):
        #    logger.info(f"{tick_time} Trend unchanged. Option_type {opt_type}, Trend {trend_now}")
        #    return

        exit_positions = process_option_buy_exit(connector, active_positions)
        if config.LIVE:
            place_order.main(connector, exit_positions, 'EXIT')
        logger.info('Exited on trend reversal.')

    if not is_there_existing_trade():
        trade = new_trade(file_path, spot_ltp,tick_time)
        if not trade:
            return
        positions = process_option_buy_entry(connector, trade)

        if config.LIVE:
            # If there is pending target order , make sure to make it market so it gets closed 
            #modify_limit_orders_to_market(connector, STRATEGY_TAG)

            # Clear open position and pending order  with TAG used in this stragety
            place_order_obj.clear_existing_positions(connector, STRATEGY_TAG)

            # Take Entry order  - MARKET order type
            place_order.main(connector, positions, 'ENTRY')
            time.sleep(2) # give for prder to reflect

            # Place target order
            #positions = place_order.main(connector, positions, 'TARGET', 30)

            # Place SL order
            positions = place_order.main(connector, positions, 'STOPLOSS', 20)


        logger.info('Entered new position.')

def is_within_time_range():
    """Check if current time is within trading hours."""
    now = datetime.now()
    return now.replace(hour=9, minute=16) <= now <= now.replace(hour=15, minute=25)

