import pandas as pd
import indicators
from strategy_engine import strategy_decision
from logzero import logger
import core
import sys
import credit_spread as spread

# global state
SEEN_CANDLES_ENTRY = []
SEEN_CANDLES_EXIT = []
SPREAD_NAME = None

def run_live(connector, df, c_pos=None, prev_day_trend=None):
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
    df.to_csv('atr_ema_indicator.csv', index=False)

    current_position = c_pos
    previous_day_trend = prev_day_trend

    # Filter to today's data only
    today = pd.Timestamp.now().date()
    df = df[df['datetime'].dt.date == today]

    if df.empty:
        logger.info("No data for today. Skipping run_live execution.")
        return
    df = df.tail(1)

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
        if signals :
            # Make sure EXIT signals are processed before Entry
            signals = sorted(signals, key=lambda x: 0 if x["action"] == "EXIT" else 1)
        else :
            continue
        
        for signal in signals:
            logger.info(f"Candletime: {row['datetime']}")
            if signal["action"] == "ENTER":

                # before taking a new entry
                if current_position:
                    logger.info(f"{row['datetime']}: Exiting current position {current_position} before taking new entry.")
                    on_exit(connector, current_position, row['datetime'], "!! NewEntry", row['close'])
                    current_position = None
                    previous_day_trend = None

                pos = signal["position"]
                logger.info(f"ENTRY: {pos} {row['datetime']}")
                on_entry(connector, pos, row['datetime'], row['close'])
                current_position = pos
                previous_day_trend = "bullish" if pos == "BULL_PUT" else "bearish"
                SEEN_CANDLES_ENTRY.append(row['time'])
            elif signal["action"] == "EXIT" or pnl_pct > 700 :
                pos = signal["position"]
                reason = signal["reason"]
                logger.info(f"EXIT: {pos} ({reason}) {row['datetime']}")
                on_exit(connector, pos, row['datetime'], reason, row['close'])
                current_position = None
                previous_day_trend = None
                SEEN_CANDLES_EXIT.append(row['time'])

    return current_position, previous_day_trend

def on_entry(connector, position_type, dt, price):
    global SPREAD_NAME
    spot_ltp = core.get_ltp(connector, '99926000', 'NIFTY', 'NSE')
    strike = int(spot_ltp / 50) * 50
    expiry = core.find_valid_expiry()
    direction = "bullish" if position_type == 'BULL_PUT' else "bearish"
    spread_name, buy_symbol, sell_symbol = spread.generate_credit_spread(
        connector, strike, expiry, direction
    )
    SPREAD_NAME = spread_name
    spread.take_spread_position(connector, spread_name, buy_symbol, sell_symbol, dt)
    logger.info(f"Entry: {spread_name} {buy_symbol} {buy_symbol} {dt}")


def on_exit(connector, position_type, dt, reason, price):
    global SPREAD_NAME
    spread.exit_position(connector, SPREAD_NAME, dt, reason=reason)
    logger.info(f"Exit: {SPREAD_NAME} {reason} {dt}")
    SPREAD_NAME = None

