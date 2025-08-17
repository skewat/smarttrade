# Updated: Persistent ACTIVE_ORDERS using CSV file
import pandas as pd
from datetime import datetime
from logzero import logger
import os
import sys
import pprint
import core
from functools import wraps
from log_utils import log_function_entry_exit
import config


today = datetime.today().date()
# Load active orders from file if present
if os.path.exists(config.ORDERS_FILE):
    try:
        df = pd.read_csv(config.ORDERS_FILE, index_col=0)
        if df.empty or df.columns.empty:
            logger.warning(f"Empty or invalid CSV file: {config.ORDERS_FILE}")
            ACTIVE_ORDERS = {}
        else:
            # Filter out old orders from previous days
            today_str = datetime.today().strftime("%Y-%m-%d")
            df = df[df['timestamp'].str.startswith(today_str, na=False)]
            ACTIVE_ORDERS = df.to_dict(orient='index')
            logger.info(f"ACTIVE_ORDERS loaded from file '{config.ORDERS_FILE}'. Found {len(ACTIVE_ORDERS)} active orders for today.")
    except pd.errors.EmptyDataError:
        logger.warning(f"Empty CSV file: {config.ORDERS_FILE}")
        ACTIVE_ORDERS = {}
else:
    ACTIVE_ORDERS = {}


@log_function_entry_exit
def save_active_orders():
    pd.DataFrame.from_dict(ACTIVE_ORDERS, orient='index').to_csv(config.ORDERS_FILE)


@log_function_entry_exit
def process_order(connector, order):
    core.process_order(connector, order, lots=1)

@log_function_entry_exit
def place_order(connector, order_id, symbol, action, quantity, price):
    today_str = datetime.today().strftime("%Y%m%d")
    key = f"{symbol}_{today_str}"
    if key in ACTIVE_ORDERS and order_id.startswith('ENTRY_'):
        logger.warning(f"{action} Order {order_id} already active. Skipping duplicate.")
        return False
    if order_id.startswith('ENTRY_'):
        #Add the order to CSV
        ACTIVE_ORDERS[key] = {
            "symbol": symbol,
            "action": action,
            "quantity": quantity,
            "price": price,
            "status": "FILLED",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "position": "ENTRY",
        }
        process_order(connector, ACTIVE_ORDERS[key])
        save_active_orders()
        logger.info(f"Placed ENTRY {action} order for {symbol} @ {price}")
    if order_id.startswith('EXIT_'):
        #Remove the order from CSV
        if ACTIVE_ORDERS[key]["action"] == 'BUY' :
            ACTIVE_ORDERS[key]["action"] = 'SELL'

        elif ACTIVE_ORDERS[key]["action"] == 'SELL' :
            ACTIVE_ORDERS[key]["action"] = 'BUY'

        ACTIVE_ORDERS[key]["position"] = 'EXIT'
        process_order(connector, ACTIVE_ORDERS[key])
        ACTIVE_ORDERS.pop(key, None)
        save_active_orders()
        logger.info(f"Placed EXIT {action} order for {symbol} @ {price}")
    return True

@log_function_entry_exit
def fetch_ltp(connector,symbol):
    token = core.get_token(symbol)
    ltp = core.get_ltp(connector, token, symbol, 'NFO')
    return ltp

@log_function_entry_exit
def load_positions():
    if os.path.exists(config.POSITIONS_FILE):
        return pd.read_csv(config.POSITIONS_FILE)
    return pd.DataFrame(columns=["spread", "buy_symbol", "buy_price", "buy_qty", "sell_symbol", "sell_price", "sell_qty", "entry_time"])

@log_function_entry_exit
def save_positions(df, dt):
    """
    Save the active positions to positions.csv
    """
    if not df.empty :
        archive_positions(df, dt, reason="CLOSED")
    print('Save DF .. position;',df)
    df.to_csv(config.POSITIONS_FILE, index=False)

@log_function_entry_exit
def archive_positions(positions_to_archive, dt , reason="CLOSED"):
    """
    Archive exited positions with timestamp and reason
    """
    # Load previous archive
    if os.path.exists(config.ARCHIVE_FILE):
        archive_df = pd.read_csv(config.ARCHIVE_FILE)
    else:
        archive_df = pd.DataFrame(columns=[
            "spread", "buy_symbol", "buy_price", "buy_qty",
            "sell_symbol", "sell_price", "sell_qty",
            "entry_time", "exit_time", "exit_reason"
        ])

    positions_to_archive = positions_to_archive.copy()
    positions_to_archive["exit_time"] = dt
    positions_to_archive["exit_reason"] = reason

    #archive_df = pd.concat([archive_df, positions_to_archive], ignore_index=True)
    if not positions_to_archive.empty:
        if archive_df.empty:
            archive_df = positions_to_archive
        else:
            archive_df = pd.concat([archive_df, positions_to_archive], ignore_index=True)

    archive_df.to_csv(config.ARCHIVE_FILE, index=False)
    logger.debug(f"✅ Archived {len(positions_to_archive)} positions to positions_archive.csv")


@log_function_entry_exit
def record_position(spread_name, buy_symbol, buy_price, sell_symbol, sell_price, quantity, dt):
    df = load_positions()
    new_entry = {
        "spread": spread_name,
        "buy_symbol": buy_symbol,
        "buy_price": buy_price,
        "buy_qty": quantity,
        "sell_symbol": sell_symbol,
        "sell_price": sell_price,
        "sell_qty": quantity,
        "entry_time": dt,
    }
    new_entry_df = pd.DataFrame([new_entry])
    #if not new_entry_df.empty:
    #    if df.empty:
    #        df = new_entry_df
    #    else:
    #        df = pd.concat([df, new_entry_df], ignore_index=True)
    logger.info(f"Entry: new Position {new_entry_df}, entry taken" )
    save_positions(new_entry_df, dt)

@log_function_entry_exit
def generate_credit_spread(connector, strike_price, expiry_str, direction, spread_width=200):
    if direction.lower() == "bullish":
        sell = f"NIFTY{expiry_str}{strike_price}PE"
        buy = f"NIFTY{expiry_str}{strike_price - spread_width}PE"
        spread_type = "Bull Put Spread"
    elif direction.lower() == "bearish":
        sell = f"NIFTY{expiry_str}{strike_price}CE"
        buy = f"NIFTY{expiry_str}{strike_price + spread_width}CE"
        spread_type = "Bear Call Spread"
    else:
        raise ValueError("Direction must be 'bullish' or 'bearish'")
    return spread_type, buy, sell

@log_function_entry_exit
def take_spread_position(connector, spread_name, buy_symbol, sell_symbol, dt, quantity=75):
    df = load_positions()
    if spread_name in df['spread'].values:
        logger.warning(f"Position '{spread_name}' already exists.")
        return

    buy_price = fetch_ltp(connector, buy_symbol)
    if not place_order(connector, f"ENTRY_{buy_symbol}", buy_symbol, "BUY", quantity, buy_price):
        return

    sell_price = fetch_ltp(connector, sell_symbol)
    if not place_order(connector, f"ENTRY_{sell_symbol}", sell_symbol, "SELL", quantity, sell_price):
        return

    record_position(spread_name, buy_symbol, buy_price, sell_symbol, sell_price, quantity, dt)
    logger.info(f"Position '{spread_name}' recorded.")

@log_function_entry_exit
def exit_position(connector, spread_name, dt, reason="Signal"):
    df = load_positions()
    row = df[df['spread'] == spread_name]
    if row.empty:
        logger.warning(f"No active position for '{spread_name}'")
        return
    row = row.iloc[0]
    buy_symbol, buy_qty = row['buy_symbol'], row['buy_qty']
    sell_symbol, sell_qty = row['sell_symbol'], row['sell_qty']
    buy_price = fetch_ltp(connector, buy_symbol)
    sell_price = fetch_ltp(connector, sell_symbol)

    place_order(connector,f"EXIT_BUY_{sell_symbol}", sell_symbol, "BUY", sell_qty, sell_price)
    place_order(connector,f"EXIT_SELL_{buy_symbol}", buy_symbol, "SELL", buy_qty, buy_price)

    df = df[df['spread'] != spread_name]
    save_positions(df, dt)
    logger.info(f"EXIT:Position '{spread_name}' {df} exited due to {reason}.")

@log_function_entry_exit
def monitor_pnl(connector, spread_name, target_pnl_pct=0.03):
    position_book = load_positions()
    pnl_pct = 0

    if spread_name not in position_book['spread'].values:
        logger.warning(f"No active position for '{spread_name}'")
        return 0

    # get the matching row
    row = position_book[position_book['spread'] == spread_name]
    if row.empty:
        logger.warning(f"No active position for {spread_name}")
        return 0

    pos = row.iloc[0]

    # correct column keys from the CSV
    buy_symbol = pos["buy_symbol"]
    sell_symbol = pos["sell_symbol"]
    buy_price = pos["buy_price"]
    sell_price = pos["sell_price"]
    qty = pos["buy_qty"]

    buy_ltp = fetch_ltp(connector, buy_symbol)

    sell_ltp = fetch_ltp(connector, sell_symbol)

    entry_credit = sell_price - buy_price
    current_credit = sell_ltp - buy_ltp

    pnl = (entry_credit - current_credit) * qty

    if entry_credit * qty == 0:
        logger.debug("Entry_credit is zero, cannot calculate PnL percentage safely.")
        pnl_pct = 0
    else:
        pnl_pct = pnl / (entry_credit * qty)

    logger.info(f"Spread '{spread_name}' PnL: {pnl:.2f} ({pnl_pct*100:.2f}%)")
    #return pnl_pct
    #keeping simple for now , cap the profit 
    return round(pnl)

