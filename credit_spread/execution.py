import pandas as pd
import indicators
from strategy_engine import strategy_decision
from logzero import logger
import core
import sys
import os
import credit_spread as spread

class SpreadTracker:
    def __init__(self):
        self.spread_name = None
        self.seen_candles_entry = []
        self.seen_candles_exit = []
        self.last_exit_time = None
        self.min_time_between_trades = pd.Timedelta(minutes=2)  # Minimum wait between trades
        
    def reset(self):
        self.spread_name = None
        self.seen_candles_entry = []
        self.seen_candles_exit = []
        self.last_exit_time = None
        
    def can_enter_new_trade(self, current_time):
        if self.last_exit_time is None:
            return True
        time_since_exit = current_time - self.last_exit_time
        return time_since_exit >= self.min_time_between_trades

# Initialize state manager
state = SpreadTracker()

def run_live(connector, df, c_pos=None, prev_day_trend=None):
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
    df.to_csv('/home/ckewat/options_strategy/smarttrade/credit_spread/atr_ema_indicator.csv', index=False)

    current_position = c_pos
    previous_day_trend = prev_day_trend

    # Filter to today's data only
    today = pd.Timestamp.now().date()
    df = df[df['datetime'].dt.date == today]

    if df.empty:
        logger.info("No data for today. Skipping run_live execution.")
        return current_position, previous_day_trend
        
    df = df.tail(1)
    
    try:
        for idx, row in df.iterrows():
            row_dict = row.to_dict()

            # Check PNL if we have an active position
            pnl_pct = None
            if state.spread_name:
                try:
                    # Verify if position still exists
                    position_exists = spread.verify_position_exists(connector, state.spread_name)
                    if not position_exists:
                        manual_exit_time = row['datetime']
                        logger.warning(f"MANUAL EXIT DETECTED at {manual_exit_time}")
                        logger.warning(f"Position {state.spread_name} was manually exited from broker UI")
                        logger.info(f"Previous state - Position: {current_position}, Trend: {previous_day_trend}")
                        current_position = None
                        previous_day_trend = None
                        state.last_exit_time = manual_exit_time  # Track manual exit time
                        state.reset()
                        continue
                        
                    pnl_pct = spread.monitor_pnl(connector, state.spread_name, target_pnl_pct=0.03)
                    row_dict['pnl_pct'] = pnl_pct
                    
                    # Early exit on PNL threshold
                    if pnl_pct and pnl_pct > 1200:
                        logger.info(f"PNL threshold reached: {pnl_pct}")
                        on_exit(connector, current_position, row['datetime'], "PNL_TARGET", row['close'])
                        current_position = None
                        previous_day_trend = None
                        continue
                        
                except Exception as e:
                    logger.error(f"Error monitoring PNL: {str(e)}")

        signals = strategy_decision(
            row_dict,
            current_position,
            previous_day_trend,
            SEEN_CANDLES_ENTRY,
            SEEN_CANDLES_EXIT,
            profit_threshold=0.03,
        )
        # Ensure signals is iterable
        if not isinstance(signals, (list, tuple)):
            logger.error(f"strategy_decision returned non-iterable: {type(signals)}. Skipping this row.")
            continue
        if signals :
            # Make sure EXIT signals are processed before Entry
            signals = sorted(signals, key=lambda x: 0 if x["action"] == "EXIT" else 1)
        else :
            continue
        
        # Check for 9:20 exit condition
        current_time = row['datetime']
        if current_time.time() >= pd.Timestamp('09:20').time() and current_position and not state.last_exit_time:
            logger.info(f"9:20 Exit condition met. Exiting position at {current_time}")
            on_exit(connector, current_position, current_time, "TIME_EXIT", row['close'])
            current_position = None
            previous_day_trend = None
            state.last_exit_time = current_time
            continue

        for signal in signals:
            logger.info(f"Candletime: {current_time}")
            
            if signal["action"] == "ENTER" and state.can_enter_new_trade(current_time):
                pos = signal["position"]
                logger.info(f"ENTRY: {pos} {current_time}")
                if on_entry(connector, pos, current_time, row['close']):
                    current_position = pos
                    previous_day_trend = "bullish" if pos == "BULL_PUT" else "bearish"
                    state.seen_candles_entry.append(row['time'])
                
            elif signal["action"] == "EXIT" or pnl_pct > 1200:
                pos = signal["position"]
                reason = signal["reason"] if signal["action"] == "EXIT" else "PNL_TARGET"
                logger.info(f"EXIT: {pos} ({reason}) {current_time}")
                if on_exit(connector, pos, current_time, reason, row['close']):
                    current_position = None
                    previous_day_trend = None
                    state.seen_candles_exit.append(row['time'])
                    state.last_exit_time = current_time
    logger.info(f"Current Position: {current_position}, Previous Day Trend: {previous_day_trend}")
    return current_position, previous_day_trend

def on_entry(connector, position_type, dt, price):
    try:
        spot_ltp = core.get_ltp(connector, '99926000', 'NIFTY', 'NSE')
        if not spot_ltp:
            logger.error("Could not get LTP for NIFTY")
            return False
            
        strike = int(spot_ltp / 50) * 50
        expiry = core.find_valid_expiry()
        if not expiry:
            logger.error("Could not find valid expiry")
            return False
            
        direction = "bullish" if position_type == 'BULL_PUT' else "bearish"
        spread_name, buy_symbol, sell_symbol = spread.generate_credit_spread(
            connector, strike, expiry, direction
        )
        
        if not all([spread_name, buy_symbol, sell_symbol]):
            logger.error("Invalid spread parameters generated")
            return False
            
        state.spread_name = spread_name
        result = spread.take_spread_position(connector, spread_name, buy_symbol, sell_symbol, dt)
        if not result:
            logger.error("Failed to take spread position")
            state.spread_name = None
            return False
            
        logger.info(f"Entry: {spread_name} buy:{buy_symbol} sell:{sell_symbol} {dt}")
        return True
        
    except Exception as e:
        logger.exception(f"Error in on_entry: {str(e)}")
        state.spread_name = None
        return False


def on_exit(connector, position_type, dt, reason, price):
    try:
        if not state.spread_name:
            logger.error("No active spread position to exit")
            return False
            
        # Verify position still exists before attempting exit
        position_exists = spread.verify_position_exists(connector, state.spread_name)
        if not position_exists:
            logger.warning("=" * 50)
            logger.warning(f"MANUAL EXIT DETECTED during exit attempt at {dt}")
            logger.warning(f"Position {state.spread_name} was already closed in broker UI")
            logger.warning(f"Requested exit reason was: {reason}")
            logger.warning("=" * 50)
            state.last_exit_time = dt  # Track when we detected the manual exit
            state.reset()
            return True  # Return True since position is already exited
            
        result = spread.exit_position(connector, state.spread_name, dt, reason=reason)
        if not result:
            logger.error("Failed to exit spread position")
            return False
            
        logger.info(f"Exit: {state.spread_name} {reason} {dt}")
        state.spread_name = None
        return True
        
    except Exception as e:
        logger.exception(f"Error in on_exit: {str(e)}")
        return False
