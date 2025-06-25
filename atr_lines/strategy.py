# Updated Python script with SIMULATE flag to toggle between simulation and execution
# Includes hooks for actual trade execution (entry/exit) when SIMULATE=False

import pandas as pd
import numpy as np

# ---------------- Configuration -------------------
SIMULATE = False # Set to False to run in execution mode (with hooks)
PROFIT_THRESHOLD = 0.03
ATR_PERIOD = 20
ATR_MULT = 1.0
EMA_FAST = 3
EMA_SLOW = 20
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

def on_entry(position_type, dt, price):
    print(f"ENTRY: {dt} - {position_type} at {price}")

def on_exit(position_type, dt, reason, price):
    print(f"EXIT: {dt} - {position_type} ({reason}) at {price}")

def run_strategy(df,daily_df='unused'):
    print(df)
    sys.exit(0)
    df = df.copy()
    df['date'] = df['datetime'].dt.date
    df['time'] = df['datetime'].dt.time

    # Calculate daily ATR
    daily = df.resample('1D', on='datetime').agg({
        'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'
    }).dropna()
    daily['ATR'] = calculate_atr(daily)
    print(daily)
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

    for i in range(1, len(df)):
        row = df.iloc[i]
        prev = df.iloc[i - 1]
     
        print(row['time'])
        # 3:15 PM Exit
        if row['time'] >= pd.to_datetime('15:15:00').time():
            if current_position:
                msg = f"{row['datetime']} - EXIT_{current_position}_315PM"
                if SIMULATE:
                    signal_log.append(msg)
                else:
                    on_exit(current_position, row['datetime'], "315PM", row['close'])
                current_position = None
                continue

        # Crossover Exit
        if current_position == 'BULL_PUT' and row['ema_fast'] < row['ema_slow'] and prev['ema_fast'] >= prev['ema_slow']:
            msg = f"{row['datetime']} - EXIT_BULL_PUT_XOVER"
            if SIMULATE:
                signal_log.append(msg)
            else:
                on_exit("BULL_PUT", row['datetime'], "XOVER", row['close'])
            current_position = None

        elif current_position == 'BEAR_CALL' and row['ema_fast'] > row['ema_slow'] and prev['ema_fast'] <= prev['ema_slow']:
            msg = f"{row['datetime']} - EXIT_BEAR_CALL_XOVER"
            if SIMULATE:
                signal_log.append(msg)
            else:
                on_exit("BEAR_CALL", row['datetime'], "XOVER", row['close'])
            current_position = None

        # Profit Exit
        if current_position and entry_price > 0:
            change = (row['close'] - entry_price) / entry_price if current_position == 'BULL_PUT' else (entry_price - row['close']) / entry_price
            if change >= PROFIT_THRESHOLD:
                msg = f"{row['datetime']} - EXIT_{current_position}_PROFIT"
                if SIMULATE:
                    signal_log.append(msg)
                else:
                    on_exit(current_position, row['datetime'], "PROFIT", row['close'])
                current_position = None

        # Entry Logic
        if not current_position:
            if row['time'] == pd.to_datetime('09:30:00').time():
                if row['close'] > row['atr_upper_80']:
                    pass
                elif row['close'] < row['atr_lower_80']:
                    pass
                else:
                    if row['ema_fast'] > row['ema_slow'] and prev['ema_fast'] <= prev['ema_slow']:
                        msg = f"{row['datetime']} - ENTER_BULL_PUT"
                        if SIMULATE:
                            signal_log.append(msg)
                        else:
                            on_entry("BULL_PUT", row['datetime'], row['close'])
                        current_position = 'BULL_PUT'
                        entry_price = row['close']
                    elif row['ema_fast'] < row['ema_slow'] and prev['ema_fast'] >= prev['ema_slow']:
                        msg = f"{row['datetime']} - ENTER_BEAR_CALL"
                        if SIMULATE:
                            signal_log.append(msg)
                        else:
                            on_entry("BEAR_CALL", row['datetime'], row['close'])
                        current_position = 'BEAR_CALL'
                        entry_price = row['close']
            else:
                if row['ema_fast'] > row['ema_slow'] and prev['ema_fast'] <= prev['ema_slow']:
                    msg = f"{row['datetime']} - ENTER_BULL_PUT"
                    if SIMULATE:
                        signal_log.append(msg)
                    else:
                        on_entry("BULL_PUT", row['datetime'], row['close'])
                    current_position = 'BULL_PUT'
                    entry_price = row['close']
                elif row['ema_fast'] < row['ema_slow'] and prev['ema_fast'] >= prev['ema_slow']:
                    msg = f"{row['datetime']} - ENTER_BEAR_CALL"
                    if SIMULATE:
                        signal_log.append(msg)
                    else:
                        on_entry("BEAR_CALL", row['datetime'], row['close'])
                    current_position = 'BEAR_CALL'
                    entry_price = row['close']
                elif row['close'] >= row['atr_upper']:
                    if current_position != 'BEAR_CALL':
                        msg = f"{row['datetime']} - ENTER_BEAR_CALL_TOUCH"
                        if SIMULATE:
                            signal_log.append(msg)
                        else:
                            on_entry("BEAR_CALL", row['datetime'], row['close'])
                        current_position = 'BEAR_CALL'
                        entry_price = row['close']
                elif row['close'] <= row['atr_lower']:
                    if current_position != 'BULL_PUT':
                        msg = f"{row['datetime']} - ENTER_BULL_PUT_TOUCH"
                        if SIMULATE:
                            signal_log.append(msg)
                        else:
                            on_entry("BULL_PUT", row['datetime'], row['close'])
                        current_position = 'BULL_PUT'
                        entry_price = row['close']

    return signal_log

# --------- Main Execution ----------
if __name__ == "__main__":
    df = pd.read_csv("/mnt/data/your_intraday_data.csv", parse_dates=['datetime'])
    logs = run_strategy(df)

    if SIMULATE:
        with open("/mnt/data/back_test.txt", "w") as f:
            for line in logs:
                f.write(line + "\n")
        print("✅ Simulation complete. Output written to back_test.txt")
    else:
        print("✅ Execution mode complete. Entry/Exit hooks triggered.")


