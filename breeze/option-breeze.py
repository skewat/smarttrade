from breeze_connect import BreezeConnect
from datetime import datetime
import pprint

api_key='2T30qVi00490_03C4z1F4jH743QO5517'
secret_key='99663!A45356C31l64T2k29826I995^9'
api_session = '51201148'

# Initialize SDK
breeze = BreezeConnect(api_key=api_key)

# Obtain your session key from https://api.icicidirect.com/apiuser/login?api_key=2T30qVi00490_03C4z1F4jH743QO5517

# Incase your api-key has special characters(like +,=,!) then encode the api key before using in the url as shown below.
import urllib
#print("https://api.icicidirect.com/apiuser/login?api_key="+urllib.parse.quote_plus("api_key"))

# Generate Session
breeze.generate_session(api_secret=secret_key, session_token=api_session)

#print(breeze.get_funds())
'''
future_historical_data = breeze.get_historical_data(interval="1minute",
                  from_date= "2025-02-03T09:15:00.000Z",
                  to_date= "2025-02-20T15:30:00.000Z",
                  stock_code="NIFTY",
                  exchange_code="NFO",
                  product_type="futures",
                  expiry_date="2025-02-20T07:00:00.000Z",
                  right="others",  # or "put"
                  strike_price="0")    

option_historical_data = breeze.get_historical_data(interval="1minute",
                  from_date= "2025-02-03T09:15:00.000Z",
                  to_date= "2025-02-20T15:30:00.000Z",
                  stock_code="NIFTY",
                  exchange_code="NFO",
                  product_type="options",
                  expiry_date="2025-02-20T07:00:00.000Z",
                  right="call", # or 'put'
                  strike_price="23300")    
'''

index_historical_data = breeze.get_historical_data(interval="1minute",
                  from_date= "2025-04-11T09:15:00.000Z",
                  to_date= "2025-04-15T15:30:00.000Z",
                  stock_code="NIFTY",
                  exchange_code="NSE",
                  product_type="CASH",
                  strike_price="0")    

pprint.pprint(index_historical_data)
