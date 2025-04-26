#! /usr/bin/python3

import os
import sys
import csv
import copy
from datetime import datetime, timedelta, time
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
    supertrend,
    sma,
    angelone,
)

# ========================================
# UTILITY FUNCTIONS
# ========================================

def signal_handler(sig, frame):
    """Handle SIGINT (Ctrl+C) to exit gracefully."""
    print("\nExiting gracefully...")
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

def get_ltp(smart_api, token='99926000', symbol='NIFTY', exchange='NSE'):
    """Fetch latest traded price (LTP) from API."""
    data = smart_api.ltpData(exchange, symbol, token)
    return data['data']['ltp']

# ========================================
# ENTRY & EXIT PROCESSORS
# ========================================

def process_option_buy_entry(smart_api, trade_info, lots=1):
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
    position.set('price', get_ltp(smart_api, trade_info['atm_token'], trade_info['atm_symbol'], 'NFO'))
    position.set('time_stamp', datetime.now().strftime("%d-%m-%Y:%H:%M:%S"))

    write_positions_to_csv([position], config.ACTIVE_TRADES_CSV, 'w')
    write_positions_to_csv([position], config.ARCHIVE_TRADES_CSV, 'a')
    return [position]

def process_spread_positions_entry(smart_api, trade_info, lots=1):
    """Process entry for debit spreads (bullish/bearish spreads)."""
    pos1 = opt_position.OptionPosition({
        'expiry': trade_info['expiry'],
        'opt_type': trade_info['type'],
        'quantity': lots * config.LOTSIZE,
        'position_type': 'ENTRY',
        'strike': trade_info['strike_price_otm'],
        'symbol_token': trade_info['otm_token'],
        'symbol': trade_info['otm_symbol'],
        'order_type': 'SELL',
        'price': get_ltp(smart_api, trade_info['otm_token'], trade_info['otm_symbol'], 'NFO'),
        'time_stamp': datetime.now(),
    })

    pos2 = opt_position.OptionPosition(copy.deepcopy(pos1.data))
    pos2.set('strike', trade_info['strike_price_atm'])
    pos2.set('symbol_token', trade_info['atm_token'])
    pos2.set('symbol', trade_info['atm_symbol'])
    pos2.set('order_type', 'BUY')
    pos2.set('price', get_ltp(smart_api, trade_info['atm_token'], trade_info['atm_symbol'], 'NFO'))

    write_positions_to_csv([pos1, pos2], config.ACTIVE_TRADES_CSV, 'w')
    write_positions_to_csv([pos1, pos2], config.ARCHIVE_TRADES_CSV, 'a')
    return [pos1, pos2]

def process_spread_positions_exit(smart_api, positions):
    """Exit active positions."""
    exit_positions = []
    for pos in positions:
        position = opt_position.OptionPosition(pos)
        position.set('order_type', 'BUY' if position.get('order_type') == 'SELL' else 'SELL')
        position.set('price', get_ltp(smart_api, position.get('symbol_token'), position.get('symbol'), 'NFO'))
        position.set('position_type', 'EXIT')
        position.set('time_stamp', datetime.now())
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

def debit_spread_strategy(option_expiries, spot_ltp, option_type):
    """Setup debit spread strategy."""
    expiry = find_valid_expiry(option_expiries)
    if not expiry:
        return None
    strike_price_atm = int(spot_ltp // 50) * 50
    strike_price_otm = strike_price_atm + 200 if option_type == 'CE' else strike_price_atm - 200
    return {
        'strike_price_atm': strike_price_atm,
        'strike_price_otm': strike_price_otm,
        'expiry': expiry,
        'type': option_type
    }

def find_valid_expiry(expiries):
    """Pick the first expiry > 6 days from today."""
    dt = datetime.today()
    expiry = next((datetime.strptime(e, "%d%b%y") for e in expiries if datetime.strptime(e, "%d%b%y") > dt + timedelta(days=6)), None)
    return expiry.strftime('%d%b%y').upper() if expiry else None

def get_trend(file_path):
    """Read latest trend signal from indicator file."""
    df = pd.read_csv(file_path)
    return df.iloc[-1]['signals']

# ========================================
# TRADE MANAGEMENT
# ========================================

def is_there_existing_trade():
    """Check if there is an active open trade."""
    return os.path.exists(config.ACTIVE_TRADES_CSV) and not pd.read_csv(config.ACTIVE_TRADES_CSV).empty

def get_active_positions():
    """Read active trades."""
    with open(config.ACTIVE_TRADES_CSV, mode='r', newline='') as file:
        return list(csv.DictReader(file))

def new_trade(smart_api, file_path, spot_ltp):
    """Create a new trade idea based on indicator trend."""
    trend = get_trend(file_path)
    if trend not in [1, -1]:
        logger.info('No decisive trend.')
        return None

    option_type = "CE" if trend == 1 else "PE"
    year = datetime.now().year
    option_expiries = expiries_of_year.main(year)

    if config.OPTION_BUYING:
        trade = option_buy_strategy(option_expiries, spot_ltp, option_type)
    else:
        trade = debit_spread_strategy(option_expiries, spot_ltp, option_type)

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

def process(smart_api, file_path):
    """Main decision logic: Entry or Exit based on trend."""
    spot_ltp = get_ltp(smart_api)
    if is_there_existing_trade():
        active_positions = get_active_positions()
        trend_now = get_trend(file_path)
        df = pd.read_csv(config.ACTIVE_TRADES_CSV)
        opt_type = df['opt_type'].iloc[0]
        expiry = datetime.strptime(df['expiry'].iloc[0], "%d%b%y").date()
        today = datetime.today().date()
        current_time = datetime.now().time()

        if expiry == today and current_time >= time(14, 30):
            exit_positions = process_spread_positions_exit(smart_api, active_positions)
            if config.LIVE:
                place_order.main(smart_api, exit_positions, 'EXIT')
            logger.info('Exited on expiry.')
            return

        if (opt_type == 'CE' and trend_now == 1) or (opt_type == 'PE' and trend_now == -1):
            logger.info('Trend unchanged.')
            return

        exit_positions = process_spread_positions_exit(smart_api, active_positions)
        if config.LIVE:
            place_order.main(smart_api, exit_positions, 'EXIT')
        logger.info('Exited on trend reversal.')

    if not is_there_existing_trade():
        trade = new_trade(smart_api, file_path, spot_ltp)
        if not trade:
            return
        if config.OPTION_BUYING:
            positions = process_option_buy_entry(smart_api, trade)
        else:
            positions = process_spread_positions_entry(smart_api, trade)

        if config.LIVE:
            place_order.main(smart_api, positions, 'ENTRY')
        logger.info('Entered new position.')

def is_within_time_range():
    """Check if current time is within trading hours."""
    now = datetime.now()
    return now.replace(hour=9, minute=16) <= now <= now.replace(hour=15, minute=25)

