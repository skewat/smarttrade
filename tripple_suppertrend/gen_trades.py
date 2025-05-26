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
                ohlc_df = core.till_date_ohlc_data.main(smart_api)
                if ohlc_df.empty:
                    sys.exit('OHLC data unavailable.')
                ohlc_df = core.convert_to_5min(ohlc_df)
                supertrend_file = core.supertrend.main(ohlc_df)
                core.process(connector, supertrend_file)
                trading_today = True
            else :
                start = "2025-05-02 09:15:00"
                end = "2025-05-02 15:30:00"
                minute_range = pd.date_range(start=start, end=end, freq='T')
                for timestamp in minute_range:
                    core.process(connector, config.CSV_FILE,timestamp)
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

