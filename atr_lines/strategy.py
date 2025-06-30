# Updated Python script with SIMULATE flag to toggle between simulation and execution
# Includes hooks for actual trade execution (entry/exit) when SIMULATE=False

import pandas as pd
import numpy as np
import credit_spread as spread
from logzero import logger
import time 
import core
import os
import sys

# Project Imports
current_dir = os.path.dirname(os.path.abspath(__file__))
base_path = os.path.abspath(os.path.join(current_dir, ".."))
sys.path.append(base_path)

import config
from common_utils import (
    expiries_of_year,
)


# ---------------- Configuration -------------------
SIMULATE = False # Set to False to run in execution mode (with hooks)
PROFIT_THRESHOLD = 0.03
ATR_PERIOD = 20
ATR_MULT = 1.0
EMA_FAST = 3
EMA_SLOW = 20
SPREAD_NAME = None
CONNECTOR = None
SEEN_CANDLES = []
# --------------------------------------------------

def calculate_ema(df, period):
    return df['close'].ewm(span=period, adjust=False).mean()

def calculate_atr(df, period=ATR_PERIOD):
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr

def on_entry(connector, position_type, dt, price):
    global SPREAD_NAME
    spot_ltp = core.get_ltp(connector, '99926000', 'NIFTY', 'NSE')
    strike = int(spot_ltp/50)*50
    expiries = expiries_of_year.main(None)
    expiry = core.find_valid_expiry(expiries)

    logger.info(f"ENTRY: {dt} - {position_type} at {price}")
    if position_type == 'BULL_PUT':
        direction = "bullish"
    if position_type == 'BEAR_CALL':
        direction = "bearish"
    spread_name, buy_symbol, sell_symbol = spread.generate_credit_spread(connector, strike, expiry, direction)
    SPREAD_NAME = spread_name
    spread.take_spread_position(connector, spread_name, buy_symbol, sell_symbol,dt)
    logger.debug(f"Entry... {position_type}")

def on_monitor(connector, dt):
    global SPREAD_NAME
    spread_name = SPREAD_NAME
    pnl_pct = spread.monitor_pnl(connector, spread_name, target_pnl_pct=0.03)
    return pnl_pct

def on_exit(connector, position_type, dt, reason, price):
    global SPREAD_NAME
    spread_name = SPREAD_NAME
    logger.info(f"EXIT: {dt} - {position_type} ({reason}) at {price}")
    spread.exit_position(connector, spread_name, dt, reason="Signal")
    SPREAD_NAME = None
    logger.debug(f"Exit ... {position_type}")


def add_ema_crossover_signal(df):
    """
    Adds a 'ema_crossover' column indicating bullish or bearish EMA crossover.

    Bullish: ema_fast crosses above ema_slow
    Bearish: ema_fast crosses below ema_slow
    """
    df = df.copy()  # avoid modifying original
    df['ema_crossover'] = None

    # Shift EMAs to detect crossovers
    prev_fast = df['ema_fast'].shift(1)
    prev_slow = df['ema_slow'].shift(1)

    # Bullish crossover condition
    bullish = (prev_fast < prev_slow) & (df['ema_fast'] > df['ema_slow'])

    # Bearish crossover condition
    bearish = (prev_fast > prev_slow) & (df['ema_fast'] < df['ema_slow'])

    # Assign crossover signals
    df.loc[bullish, 'ema_crossover'] = 'bullish'
    df.loc[bearish, 'ema_crossover'] = 'bearish'

    return df


def run_strategy(connector, df):
    ''' Data Frame is 5 min OHLC '''
    global SEEN_CANDLES

    df = df.copy()
    df['date'] = df['datetime'].dt.date
    df['time'] = df['datetime'].dt.time
    # Calculate daily ATR
    daily = df.resample('1D', on='datetime').agg({
        'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'
    }).dropna()
    daily['ATR'] = calculate_atr(daily)
    daily.index = daily.index.date  # <- Add this line
    df = df.merge(daily[['ATR', 'close']], left_on='date', right_index=True, suffixes=('', '_daily'))
    df['atr_upper'] = df['close_daily'] + df['ATR'] * ATR_MULT
    df['atr_lower'] = df['close_daily'] - df['ATR'] * ATR_MULT
    df['atr_upper_80'] = df['close_daily'] + df['ATR'] * ATR_MULT * 0.8
    df['atr_lower_80'] = df['close_daily'] - df['ATR'] * ATR_MULT * 0.8

    df['ema_fast'] = calculate_ema(df, EMA_FAST)
    df['ema_slow'] = calculate_ema(df, EMA_SLOW)

    signal_log = []
    current_position = None
    entry_price = 0.0
    df = add_ema_crossover_signal(df)
    if not SIMULATE:
        df = df.tail(1).reset_index(drop=True)

    for i in range(len(df)):
        row = df.iloc[i]

        # 3:15 PM Exit
        if row['time'] >= pd.to_datetime('15:15:00').time():
            if current_position:
                msg = f"{row['datetime']} - EXIT_{current_position}_315PM"
                if SIMULATE:
                    signal_log.append(msg)
                else:
                    on_exit(connector, current_position, row['datetime'], "315PM", row['close'])
                current_position = None
                # No more trades now .. 
                return

        # Crossover Exit
        if  str(row['time']) not in SEEN_CANDLES and current_position == 'BULL_PUT' and row['ema_crossover'] == 'bearish':
            msg = f"{row['datetime']} - EXIT_BULL_PUT_XOVER"
            if SIMULATE:
                signal_log.append(msg)
            else:
                on_exit(connector, "BULL_PUT", row['datetime'], "XOVER", row['close'])
            current_position = None

        elif current_position == 'BEAR_CALL' and row['ema_crossover'] == 'bullish':
            msg = f"{row['datetime']} - EXIT_BEAR_CALL_XOVER"
            if SIMULATE:
                signal_log.append(msg)
            else:
                on_exit(connector, "BEAR_CALL", row['datetime'], "XOVER", row['close'])
            current_position = None

        # Profit Exit
        if current_position :
            change = on_monitor(connector, row['datetime'])
            if change and ( change >= PROFIT_THRESHOLD ):
                msg = f"{row['datetime']} - EXIT_{current_position}_PROFIT"
                if SIMULATE:
                    signal_log.append(msg)
                else:
                    on_exit(connector, current_position, row['datetime'], "PROFIT", row['close'])
                current_position = None

        # Entry Logic
        if not current_position and str(row['time']) not in SEEN_CANDLES :
            if row['time'] >= pd.to_datetime('14:45:00').time():
                # No new entry after 2:45 PM
                continue
            if row['time'] == pd.to_datetime('09:20:00').time():
                logger.info('===================== Start of the Day ===================')
                # Do not jump to trade if opened too high or low ( Above or below TAR )
                if row['close'] > row['atr_upper']:
                    pass
                elif row['close'] < row['atr_lower']:
                    pass
                else:
                    # If yesterdays Bulish continued, with a gap up follow it 
                    if row['ema_fast'] > row['ema_slow']:
                        msg = f"{row['datetime']} - ENTER_BULL_PUT"
                        if SIMULATE:
                            signal_log.append(msg)
                        else:
                            on_entry(connector, "BULL_PUT", row['datetime'], row['close'])
                        current_position = 'BULL_PUT'
                        entry_price = row['close']
                    # If yesterdays Bearish continued, with a gap down follow it 
                    elif row['ema_fast'] < row['ema_slow']:
                        msg = f"{row['datetime']} - ENTER_BEAR_CALL"
                        if SIMULATE:
                            signal_log.append(msg)
                        else:
                            on_entry(connector, "BEAR_CALL", row['datetime'], row['close'])
                        current_position = 'BEAR_CALL'
                        entry_price = row['close']
            else:
                if row['ema_crossover'] == 'bullish':
                    logger.info(f"{row['time']}, {row['ema_crossover']}")
                    msg = f"{row['datetime']} - ENTER_BULL_PUT"
                    if SIMULATE:
                        signal_log.append(msg)
                    else:
                        on_entry(connector, "BULL_PUT", row['datetime'], row['close'])
                    current_position = 'BULL_PUT'
                    entry_price = row['close']
                if row['ema_crossover'] == 'bearish':
                    logger.info(f"{row['time']}, {row['ema_crossover']}")
                    msg = f"{row['datetime']} - ENTER_BEAR_CALL"
                    if SIMULATE:
                        signal_log.append(msg)
                    else:
                        on_entry(connector,"BEAR_CALL", row['datetime'], row['close'])
                    current_position = 'BEAR_CALL'
                    entry_price = row['close']
                elif row['close'] >= row['atr_upper']:
                    logger.info(f"{row['time']}, crossed ATR {'ATR Upper'}")
                    if current_position != 'BEAR_CALL':
                        msg = f"{row['datetime']} - ENTER_BEAR_CALL_TOUCH"
                        if SIMULATE:
                            signal_log.append(msg)
                        else:
                            on_entry(connector, "BEAR_CALL", row['datetime'], row['close'])
                        current_position = 'BEAR_CALL'
                        entry_price = row['close']
                elif row['close'] <= row['atr_lower']:
                    logger.info(f"{row['time']}, crossed lower ATR {'ATR Lower'}")
                    if current_position != 'BULL_PUT':
                        msg = f"{row['datetime']} - ENTER_BULL_PUT_TOUCH"
                        if SIMULATE:
                            signal_log.append(msg)
                        else:
                            on_entry(connector, "BULL_PUT", row['datetime'], row['close'])
                        current_position = 'BULL_PUT'
                        entry_price = row['close']
        if row['time'] not in SEEN_CANDLES:
            SEEN_CANDLES.append(str(row['time']))
    return signal_log

# --------- Main Execution ----------
if __name__ == "__main__":
    df = pd.read_csv("/mnt/data/your_intraday_data.csv", parse_dates=['datetime'])
    logs = run_strategy(df)

    if SIMULATE:
        with open("/mnt/data/back_test.txt", "w") as f:
            for line in logs:
                f.write(line + "\n")
        print("Simulation complete. Output written to back_test.txt")
    else:
        print("Execution mode complete. Entry/Exit hooks triggered.")


