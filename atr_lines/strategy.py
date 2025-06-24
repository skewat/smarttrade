# Intraday Bull Put / Bear Call Spread Strategy Template

import pandas as pd
from datetime import datetime, time

# --- Constants ---
EMA_SHORT = 3
EMA_LONG = 22
TARGET_PROFIT_PCT = 3
EXIT_TIME = time(15, 15)
SIMULATION = True  # Enable backtest mode if True

# --- Data Input ---
def get_previous_day_data(df_daily):
    prev = df_daily.iloc[-1]
    return prev['close'], prev['ATR']

def compute_levels(prev_close, prev_atr):
    upper_limit = prev_close + prev_atr
    upper_limit_80 = prev_close + 0.8 * prev_atr
    lower_limit = prev_close - prev_atr
    lower_limit_80 = prev_close - 0.8 * prev_atr
    return upper_limit, upper_limit_80, lower_limit, lower_limit_80

def calculate_ema(df, period):
    return df['close'].ewm(span=period, adjust=False).mean()

# --- Signal Evaluators ---
def is_red_candle(candle):
    return candle['close'] < candle['open']

def is_green_candle(candle):
    return candle['close'] > candle['open']

def ema_cross_signal(ema_short, ema_long):
    if len(ema_short) < 2 or len(ema_long) < 2:
        return None
    if ema_short.iloc[-2] < ema_long.iloc[-2] and ema_short.iloc[-1] > ema_long.iloc[-1]:
        return 'bullish'
    elif ema_short.iloc[-2] > ema_long.iloc[-2] and ema_short.iloc[-1] < ema_long.iloc[-1]:
        return 'bearish'
    return None

def evaluate_first_trade(df_15min, levels):
    c915 = df_15min.iloc[0]  # 9:15 AM candle
    ul, ul80, ll, ll80 = levels
    result = None

    if c915['close'] > ul80:
        for candle in df_15min.iloc[1:]:
            if candle['high'] >= ul and is_red_candle(candle):
                result = 'bear_call'
                break

    elif c915['close'] < ll80:
        for candle in df_15min.iloc[1:]:
            if candle['low'] <= ll and is_green_candle(candle):
                result = 'bull_put'
                break

    else:
        ema_short = calculate_ema(df_15min, EMA_SHORT)
        ema_long = calculate_ema(df_15min, EMA_LONG)
        signal = ema_cross_signal(ema_short, ema_long)
        if signal == 'bullish':
            result = 'bull_put'
        elif signal == 'bearish':
            result = 'bear_call'

    return result

def evaluate_trade_switch(df_15min, current_trade, levels):
    ema_short = calculate_ema(df_15min, EMA_SHORT)
    ema_long = calculate_ema(df_15min, EMA_LONG)
    signal = ema_cross_signal(ema_short, ema_long)

    if signal == 'bullish' and current_trade != 'bull_put':
        return 'bull_put'
    elif signal == 'bearish' and current_trade != 'bear_call':
        return 'bear_call'

    last_candle = df_15min.iloc[-1]
    ul, _, ll, _ = levels

    if last_candle['high'] >= ul and current_trade != 'bear_call':
        return 'bear_call'
    elif last_candle['low'] <= ll and current_trade != 'bull_put':
        return 'bull_put'

    return None

# --- Trade Management ---
def execute_trade(trade_type, time_stamp, log):
    message = f"{time_stamp} - Entered {trade_type} spread"
    print(message)
    if SIMULATION:
        log.append(message)
    return trade_type

def close_trade(trade_type, time_stamp, log):
    message = f"{time_stamp} - Closed {trade_type} spread"
    print(message)
    if SIMULATION:
        log.append(message)
    return None

def check_exit_conditions(now, pnl_pct, ema_signal, current_trade):
    if now.time() >= EXIT_TIME:
        return True
    if pnl_pct >= TARGET_PROFIT_PCT:
        return True
    if (ema_signal == 'bullish' and current_trade == 'bear_call') or \
       (ema_signal == 'bearish' and current_trade == 'bull_put'):
        return True
    return False

# --- Main Strategy Runner ---
def run_strategy(df_15min, df_daily):
    prev_close, prev_atr = get_previous_day_data(df_daily)
    levels = compute_levels(prev_close, prev_atr)

    current_trade = None
    trade_open_time = None
    log = []

    for i in range(1, len(df_15min)):
        now = pd.to_datetime(df_15min.index[i])
        df_window = df_15min.iloc[:i+1].copy()

        if current_trade is None:
            if now.time() >= time(9, 30):
                entry_signal = evaluate_first_trade(df_window, levels)
                if entry_signal:
                    current_trade = execute_trade(entry_signal, now, log)
                    trade_open_time = now
        else:
            ema_short = calculate_ema(df_window, EMA_SHORT)
            ema_long = calculate_ema(df_window, EMA_LONG)
            signal = ema_cross_signal(ema_short, ema_long)

            pnl_pct = 0.5  # Placeholder
            if check_exit_conditions(now, pnl_pct, signal, current_trade):
                current_trade = close_trade(current_trade, now, log)
            else:
                new_signal = evaluate_trade_switch(df_window, current_trade, levels)
                if new_signal and new_signal != current_trade:
                    current_trade = close_trade(current_trade, now, log)
                    current_trade = execute_trade(new_signal, now, log)
                    trade_open_time = now

    if current_trade:
        current_trade = close_trade(current_trade, df_15min.index[-1], log)

    if SIMULATION:
        with open("back_test.txt", "w") as f:
            for entry in log:
                f.write(entry + "\n")
