import numpy as np
import pandas as pd
from functools import wraps
from log_utils import log_function_entry_exit

@log_function_entry_exit
def calculate_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

@log_function_entry_exit
def calculate_atr(df, period=18):
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()

    return atr.round(0)

@log_function_entry_exit
def __add_ema_crossover(df, fast_col, slow_col):
    df = df.copy()
    df['ema_crossover'] = None
    prev_fast = df[fast_col].shift(1)
    prev_slow = df[slow_col].shift(1)
    bullish = (prev_fast < prev_slow) & (df[fast_col] > df[slow_col])
    bearish = (prev_fast > prev_slow) & (df[fast_col] < df[slow_col])
    df.loc[bullish, 'ema_crossover'] = 'bullish'
    df.loc[bearish, 'ema_crossover'] = 'bearish'
    return df

@log_function_entry_exit
def add_ema_crossover(df, fast_col, slow_col, threshold=5):
    df = df.copy()
    df['ema_crossover'] = None

    # Previous values
    prev_fast = df[fast_col].shift(1)
    prev_slow = df[slow_col].shift(1)

    # Crossover conditions
    bullish_cross = (
        (prev_fast < prev_slow) &
        (df[fast_col] > df[slow_col]) &
        ((df[fast_col] - df[slow_col]).abs() > threshold)
    )

    bearish_cross = (
        (prev_fast > prev_slow) &
        (df[fast_col] < df[slow_col]) &
        ((df[fast_col] - df[slow_col]).abs() > threshold)
    )

    df.loc[bullish_cross, 'ema_crossover'] = 'bullish'
    df.loc[bearish_cross, 'ema_crossover'] = 'bearish'
    return df

