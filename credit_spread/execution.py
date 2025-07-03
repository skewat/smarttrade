import pandas as pd
import indicators
from strategy_engine import strategy_decision
from logzero import logger
import core
import credit_spread as spread

# global state
SEEN_CANDLES_ENTRY = []
SEEN_CANDLES_EXIT = []
SPREAD_NAME = None

def run_live(connector, df):
    global SEEN_CANDLES_ENTRY, SEEN_CANDLES_EXIT, SPREAD_NAME

    df = df.copy()
    df['ema_fast'] = indicators.calculate_ema(df['close'], 3)
    df['ema_slow'] = indicators.calculate_ema(df['close'], 20)

    daily = df.resample('1D', on='datetime').agg({
        'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'
    }).dropna()
    daily['ATR'] = indicators.calculate_atr(daily)
    daily.index = daily.index.date

    df['date'] = df['datetime'].dt.date
    df['time'] = df['datetime'].dt.time

    df = df.merge(
        daily[['ATR', 'close']],
        left_on='date', right_index=True,
        suffixes=('', '_daily')
    )

    df['atr_upper'] = df['close_daily'] + df['ATR']
    df['atr_lower'] = df['close_daily'] - df['ATR']

    df = indicators.add_ema_crossover(df, 'ema_fast', 'ema_slow')

    current_position = None
    previous_day_trend = None

    for idx, row in df.iterrows():
        row_dict = row.to_dict()

        # optionally inject PnL for profit exit
        if SPREAD_NAME:
            pnl_pct = spread.monitor_pnl(connector, SPREAD_NAME, target_pnl_pct=0.03)
            row_dict['pnl_pct'] = pnl_pct

        signals = strategy_decision(
            row_dict,
            current_position,
            previous_day_trend,
            SEEN_CANDLES_ENTRY,
            SEEN_CANDLES_EXIT,
            profit_threshold=0.03,
        )

        for signal in signals:
            if signal["action"] == "ENTER":
                pos = signal["position"]
                logger.info(f"ENTRY: {pos}")
                on_entry(connector, pos, row['datetime'], row['close'])
                current_position = pos
                previous_day_trend = "bullish" if pos == "BULL_PUT" else "bearish"
                SEEN_CANDLES_ENTRY.append(row['time'])
            elif signal["action"] == "EXIT":
                pos = signal["position"]
                reason = signal["reason"]
                logger.info(f"EXIT: {pos} ({reason})")
                on_exit(connector, pos, row['datetime'], reason, row['close'])
                current_position = None
                previous_day_trend = None
                SEEN_CANDLES_EXIT.append(row['time'])

def on_entry(connector, position_type, dt, price):
    global SPREAD_NAME
    spot_ltp = core.get_ltp(connector, '99926000', 'NIFTY', 'NSE')
    strike = int(spot_ltp / 50) * 50
    expiries = core.find_valid_expiry(expiries_of_year.main(None))
    direction = "bullish" if position_type == 'BULL_PUT' else "bearish"
    spread_name, buy_symbol, sell_symbol = spread.generate_credit_spread(
        connector, strike, expiry, direction
    )
    SPREAD_NAME = spread_name
    spread.take_spread_position(connector, spread_name, buy_symbol, sell_symbol, dt)

def on_exit(connector, position_type, dt, reason, price):
    global SPREAD_NAME
    spread.exit_position(connector, SPREAD_NAME, dt, reason=reason)
    SPREAD_NAME = None

