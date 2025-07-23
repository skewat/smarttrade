from datetime import time
from logzero import logger
from functools import wraps
from log_utils import log_function_entry_exit


@log_function_entry_exit
def strategy_decision(
    row,
    current_position,
    previous_day_trend,
    seen_candles_entry,
    seen_candles_exit,
    profit_threshold,
):
    signals = []

    row_time = row['time']
    # 3:15 PM exit
    if row_time >= time(15, 15):
        if current_position and row_time not in seen_candles_exit:
            signals.append({
                "action": "EXIT",
                "position": current_position,
                "reason": "315PM"
            })

    # Crossover exit
    if current_position and row_time not in seen_candles_exit:
        if current_position == 'BULL_PUT' and row['ema_crossover'] == 'bearish':
            signals.append({
                "action": "EXIT",
                "position": "BULL_PUT",
                "reason": "XOVER"
            })
        elif current_position == 'BEAR_CALL' and row['ema_crossover'] == 'bullish' :
            signals.append({
                "action": "EXIT",
                "position": "BEAR_CALL",
                "reason": "XOVER"
            })

    # Profit exit
    if current_position and row_time not in seen_candles_exit:
        logger.info(f"Profit {row.get('pnl_pct', 0)}, Threshold {profit_threshold}")
        #if row.get('pnl_pct', 0) >= profit_threshold:
        if row.get('pnl_pct', 0) >= 1200 :
            signals.append({
                "action": "EXIT",
                "position": current_position,
                "reason": "PROFIT"
            })

    # Entry logic
    if row_time not in seen_candles_entry and row_time < time(14, 45):
        if row_time == time(9, 20):
            if row['close'] > row['atr_upper'] or row['close'] < row['atr_lower']:
                pass
            else:
                if row['ema_fast'] > row['ema_slow']:
                    signals.append({
                        "action": "ENTER",
                        "position": "BULL_PUT"
                    })
                elif row['ema_fast'] < row['ema_slow']:
                    signals.append({
                        "action": "ENTER",
                        "position": "BEAR_CALL"
                    })
        else:
            if row['ema_crossover'] == 'bullish':
                signals.append({
                    "action": "ENTER",
                    "position": "BULL_PUT"
                })
            elif row['ema_crossover'] == 'bearish':
                signals.append({
                    "action": "ENTER",
                    "position": "BEAR_CALL"
                })
            elif row['close'] >= row['atr_upper']:
                signals.append({
                    "action": "ENTER",
                    "position": "BEAR_CALL"
                })
            elif row['close'] <= row['atr_lower']:
                signals.append({
                    "action": "ENTER",
                    "position": "BULL_PUT"
                })
    return signals

