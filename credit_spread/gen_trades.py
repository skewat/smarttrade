#! /usr/bin/python3
import os
import sys
import time
import signal
from datetime import datetime, timedelta
import logzero
from logzero import logger

# Project Imports
current_dir = os.path.dirname(os.path.abspath(__file__))
base_path = os.path.abspath(os.path.join(current_dir, ".."))
sys.path.append(base_path)

import config
import core
from common_utils import angelone
from execution import run_live

# Setup logger
logzero.logfile("atr_strategy_logfile.log", maxBytes=1e6, backupCount=2)
logzero.loglevel(config.LOG_LEVEL if hasattr(config, "LOG_LEVEL") else logzero.INFO)


def wait_for_trading_hours():
    """
    Sleep outside trading hours:
      - before 9:16 AM => sleep till 9:16 AM
      - after 3:30 PM => sleep till next day 9:16 AM
    """
    now = datetime.now()
    market_open = now.replace(hour=9, minute=16, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)

    if now >= market_close:
        next_day_open = market_open + timedelta(days=1)
        sleep_seconds = (next_day_open - now).total_seconds()
        logger.info(f"Market closed. Sleeping till next day 9:16 AM ({sleep_seconds} seconds).")
        time.sleep(sleep_seconds)

    elif now < market_open:
        sleep_seconds = (market_open - now).total_seconds()
        logger.info(f"Sleeping till today 9:16 AM ({sleep_seconds} seconds).")
        time.sleep(sleep_seconds)
        logger.info(f"Awake now at {datetime.now()}")

    else:
        logger.info("Within trading hours. Proceeding...")


def main(token, exchange):
    current_position = None
    previous_day_trend = None
    connector = angelone.AngelOneConnector()
    connector.connect()
    smart_api = connector.smart_api

    if not config.SIMULATE:
        signal.signal(signal.SIGINT, core.signal_handler)
        if not smart_api:
            logger.error("Could not connect to broker API. Exiting.")
            sys.exit(1)
        logger.info("Connected to broker API.")

    trading_today = False

    try:
        while True:
            now = datetime.now()

            if core.is_within_time_range() or config.TESTING:
                # pull latest OHLC from your data source
                ohlc_df = core.till_date_ohlc_data.main(smart_api, token, exchange)
                if ohlc_df.empty:
                    logger.warning("OHLC data unavailable. Skipping iteration.")
                    time.sleep(30)
                    continue

                trading_today = True

                # resample to 5-min
                df_5min = core.convert_to_5min(ohlc_df)

                # execute strategy
                current_position, previous_day_trend = run_live(connector, 
                                                                current_position,
                                                                previous_day_trend,
                                                                df_5min)

            else:
                if trading_today:
                    logger.info("Market closed, logging out and exiting cleanly.")
                    connector.logout()
                    sys.exit("Exiting ..")

                logger.info(f"Outside trading hours at {now.strftime('%H:%M:%S')}")
                wait_for_trading_hours()
                continue

            # synchronize to next minute
            next_min = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
            sleep_time = (next_min - datetime.now()).total_seconds()
            if sleep_time > 0:
                time.sleep(sleep_time)

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
    finally:
        connector.logout()
        logger.info("Graceful shutdown completed.")


if __name__ == "__main__":
    main("99926000", "NSE")
