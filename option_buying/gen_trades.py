#! /usr/bin/python3
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
    signal.signal(signal.SIGINT, core.signal_handler)
    smart_api = angelone.connect()
    if not smart_api:
        sys.exit("Failed to connect to broker API.")

    while True:
        if core.is_within_time_range() or config.TESTING:
            ohlc_df = core.till_date_ohlc_data.main(smart_api)
            if ohlc_df.empty:
                sys.exit('OHLC data unavailable.')
            supertrend_file = core.supertrend.main(ohlc_df)
            sma_file = core.sma.main(supertrend_file)
            core.process(smart_api, sma_file)
        else:
            print("Outside trading hours:", datetime.now().strftime("%H:%M:%S"))

        now = datetime.now()
        next_minute = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
        time.sleep((next_minute - datetime.now()).total_seconds())

    angelone.logout(smart_api)

if __name__ == '__main__':
    main()

