from datetime import datetime
import logzero 
#Add your login details 
#https://smartapi.angelbroking.com/apps  URL to get API key
API_KEY = 'b3Jt20md'
USERNAME = 'AAAE362329'
PWD = '1697'
TOKEN = "YDGLN23VQ7KBI4QEY6PR2OA7TE"

# Sellect as apropriate 
SIMULATE = False
LOTSIZE = 75
STRATEGY = 'ATR_CR_SPREAD'

LIVE = True      # Only during office hours of market
TESTING = True # It allows LIVE beyond office hours - test end to end flow ( order placements )
LOG_LEVEL =  logzero.INFO

today = datetime.today().date()
ACTIVE_TRADES_CSV = f"active_trades_{today}.csv"
ARCHIVE_TRADES_CSV = "archive_trades.csv"

