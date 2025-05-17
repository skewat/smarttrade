from datetime import datetime

#Add your login details 
API_KEY = 'WfhXGr5z'
USERNAME = 'AAAE362329'
PWD = '1697'
TOKEN = "YDGLN23VQ7KBI4QEY6PR2OA7TE"

# Sellect as apropriate 
PAPER_TRADING = False
SIMULATE = False
OPTION_BUYING = True
LOTSIZE = 75
LIVE = True
TESTING = True
CSV_FILE = 'sma_supertrend_hourly_candle.csv'

today = datetime.today().date()
ACTIVE_TRADES_CSV = f"active_buying_trades_{today}.csv"
ARCHIVE_TRADES_CSV = "archive_buying_trades.csv"

