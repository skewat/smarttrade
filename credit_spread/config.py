from datetime import datetime
import logzero 
import os
#Login details 
#https://smartapi.angelbroking.com/apps  URL to get API key
API_KEY = 'b3Jt20md'
USERNAME = 'AAAE362329'
PWD = '1697'
TOKEN = "YDGLN23VQ7KBI4QEY6PR2OA7TE"


STRATEGY = 'ATR_CR_SPREAD'
LOTSIZE = 75
today = datetime.today().date()
datapath = "/home/ckewat/options_strategy/smarttrade/credit_spread"

# Sellect as apropriate 
TESTING = True # It allows LIVE beyond office hours - test end to end flow ( including order placements )

LOG_LEVEL =  logzero.INFO
LOG_FILE = os.path.join(datapath,f"atr_strategy_logfile_{today}.log")

ATR_EMA_INDICATOR = os.path.join(datapath,"atr_ema_indicator.csv")
POSITIONS_FILE = os.path.join(datapath,f"positions_{today}.csv")
ARCHIVE_FILE = os.path.join(datapath,"archive_positions.csv")
ORDERS_FILE = os.path.join(datapath,"active_orders.csv")
