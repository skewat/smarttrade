#! /usr/bin/python3
import pandas as pd
import logzero
from logzero import logger
import os
import signal
import sys
import time
from datetime import datetime, timedelta

# Project Imports
current_dir = os.path.dirname(os.path.abspath(__file__))
base_path = os.path.abspath(os.path.join(current_dir, ".."))
sys.path.append(base_path)

import config
from common_utils import angelone
import core
import strategy

logzero.logfile("atr_strategy_logfile.log", maxBytes=1e6, backupCount=2)
logzero.loglevel(config.LOG_LEVEL if hasattr(config, "LOG_LEVEL") else logzero.INFO)

def wait_for_trading_hrs():
    now = datetime.now()
    today_target = now.replace(hour=9, minute=16, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)

    if now >= market_close:
        # Market is closed, sleep until next day's 9:16 AM
        next_day_target = today_target + timedelta(days=1)
        delta = (next_day_target - now).total_seconds()
        logger.info(f"Market closed. Sleeping until next day 9:16 AM ({delta} seconds).")
        time.sleep(delta)

    elif now < today_target:
        # Before today's 9:16 AM, sleep until today 9:16 AM
        delta = (today_target - now).total_seconds()
        logger.info(f"Sleeping until today 9:16 AM ({delta} seconds).")
        time.sleep(delta)
        logger.info(f"... Current time {datetime.now()}")

    else:
        # Between 9:16 AM and 3:30 PM — no sleep
        print("Within trading hours, no sleep.")

def main(token, exchange):
    connector = angelone.AngelOneConnector()
    connector.connect()
    smart_api = connector.smart_api

    if not config.SIMULATE:
        signal.signal(signal.SIGINT, core.signal_handler)
        if not smart_api:
            sys.exit("Failed to connect with broker API.")
        else:
            logger.info('Connected to broker ...')
    trading_today = False

    try:
        while True:
            now = datetime.now()
            if core.is_within_time_range() or config.TESTING:
                ohlc_df = core.till_date_ohlc_data.main(smart_api, token, exchange)
                if ohlc_df.empty:
                    sys.exit('OHLC data unavailable.')
                trading_today = True
                df_5min = core.convert_to_5min(ohlc_df)
                strategy.run_strategy(connector, df_5min)
            else:
                if trading_today:
                    logger.info("Exiting positions and shutting down for the day.")
                    connector.logout()
                    sys.exit(0)
                logger.info(f"Outside trading hours: {datetime.now().strftime('%H:%M:%S')}")
                wait_for_trading_hrs()
                continue
            next_minute = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
            try:
                sleep_time = (next_minute - datetime.now()).total_seconds()
                if sleep_time > 0:
                    time.sleep(sleep_time)
            except Exception as e:
                logger.exception(f"{e}")
                connector.logout()
                sys.exit(1)
    finally:
        connector.logout()

if __name__ == '__main__':
    main("99926000", 'NSE')
