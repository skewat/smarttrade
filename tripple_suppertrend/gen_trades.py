#! /usr/bin/python3
import pandas as pd
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
import gen_trades_core as core
import pnl_calculator
NIFTY_TOKEN = "99926000" 

def main():
    connector = angelone.AngelOneConnector()
    connector.connect()
    smart_api = connector.smart_api
    trading_today = False
    if not config.SIMULATE :
        signal.signal(signal.SIGINT, core.signal_handler)
        if not smart_api:
            sys.exit("Failed to connect with broker API.")
        else:
            logger.info('Connected to broker ...')

    while True:
        now = datetime.now()
        if core.is_within_time_range() or config.TESTING:
            if not config.SIMULATE:
                ohlc_df = core.till_date_ohlc_data.main(smart_api,NIFTY_TOKEN,'NSE')
                if ohlc_df.empty:
                    sys.exit('OHLC data unavailable.')
                ohlc_df = core.convert_to_5min(ohlc_df)
                supertrend_file = core.supertrend.main(ohlc_df)
                try:
                    df = pd.read_csv(supertrend_file)
                except Exception as e:
                    logger.error(f"Error reading file: {e}")
                    continue
                core.process(connector, df)
                trading_today = True
            else :
                print("**** SIMULATION MODE ***")
                start = "2025-05-02 10:50:00"
                end = "2025-05-30 15:30:00"
                minute_range = pd.date_range(start=start, end=end, freq='5T')
                filtered_range = minute_range[(minute_range.time >= pd.to_datetime("09:00").time()) & 
                              (minute_range.time <= pd.to_datetime("15:30").time())]

                try:
                    df = pd.read_csv(config.CSV_FILE)
                except Exception as e:
                    logger.error(f"Error reading file: {e}")
                    continue





                df['datetime'] = pd.to_datetime(df['datetime'])  # Ensure datetime is parsed
            
                for i in range(1, len(df) + 1):
                    simulated_df = df.iloc[:i]  # Get first i rows
                    core.process(connector, simulated_df)

                return 
        else:
            if trading_today :
                # Exit all position if moving from office hour to non office hour
                core.force_exit_positions(connector)
                logger.info(f"Outside trading hours: {datetime.now().strftime('%H:%M:%S')}")
                return
            logger.info(f"Outside trading hours: {datetime.now().strftime('%H:%M:%S')}")

        next_minute = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
        try : 
            sleep_time = (next_minute - datetime.now()).total_seconds()
            if sleep_time > 0 :
                time.sleep(sleep_time)
        except Exception as e:
            logger.exception(f"{e}")
            connector.logout()

    connector.logout()

if __name__ == '__main__':
    main()

