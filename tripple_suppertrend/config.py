from datetime import datetime

#Add your login details 
#https://smartapi.angelbroking.com/apps  URL to get API key
API_KEY = 'b3Jt20md'
USERNAME = 'AAAE362329'
PWD = '1697'
TOKEN = "YDGLN23VQ7KBI4QEY6PR2OA7TE"

# Sellect as apropriate 
SIMULATE = False
LOTSIZE = 75

LIVE = True     # Only during office hours of market
TESTING = False# It allows LIVE beyond office hours - test end to end flow ( order placements )
PAPER_TRADING = False # everything except real order is not placed 

CSV_FILE = 'sma_supertrend_hourly_candle.csv'

today = datetime.today().date()
ACTIVE_TRADES_CSV = f"active_buying_trades_{today}.csv"
ARCHIVE_TRADES_CSV = "archive_buying_trades.csv"

