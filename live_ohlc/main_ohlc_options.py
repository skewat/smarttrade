#! /usr/bin/python3
import os,sys
import time
from datetime import datetime 
from logzero import logger



current_dir = os.path.dirname(os.path.abspath(__file__))
base_path = os.path.abspath(os.path.join(current_dir, ".."))
sys.path.append(base_path)

from common_utils.ohlc_recorder import SmartAPIClient, OHLCManager, setup_signal_handlers
from common_utils import symboltoken
from common_utils import expiries_of_year
from common_utils import angelone
from common_utils import smartapi_wrapper


def get_nifty_options_token():
    symbol_token = []
    symbols = get_nifty_option_symbols()
    for symbol in symbols :
        token = symboltoken.get_single_symbol_token(symbol, 'OPTION')
        symbol_token.append(token)
    print(symbol_token)
    return symbol_token

def get_nifty_option_symbols():
    spot = get_spot_ltp()
    base = int(spot / 50) * 50
    strikes = [base + 50 * i for i in range(-10, 11)]
    expiry = expiries_of_year.get_next_expiry()  # should return '19JUN25' format
    option_symbols = []
    for strike in strikes:
        for opt_type in ['CE', 'PE']:
            symbol = f"NIFTY{expiry}{strike}{opt_type}"
            option_symbols.append(symbol)
    return option_symbols

def initialize_clients_with_retry(retry_interval=5):
    """Keep retrying to initialize SmartAPIClient and OHLCManager until success."""
    path = os.path.abspath(os.path.join(os.path.expanduser("~"),'options_strategy/smarttrade//data/ohlc_data'))
    while True:
        try:
            client = SmartAPIClient()
            ohlc_manager = OHLCManager(path)
            print("SmartAPIClient and OHLCManager initialized successfully!")
            return client, ohlc_manager
        except Exception as e:
            print(f"Initialization failed: {e}")
            print(f"Retrying in {retry_interval} seconds...")
            time.sleep(retry_interval)


def get_spot_ltp(symbol='NIFTY', token='99926000'):
    connector = angelone.AngelOneConnector()
    connector.connect()
    smart_api = connector.smart_api
    if not smart_api:
        sys.exit("Failed to connect with broker API.")
    else:
        logger.info('Connected to broker ...')
    wrapper_api = smartapi_wrapper.SmartAPIWrapper(smart_api)

    data = wrapper_api.get_ltp('NSE',symbol,token)
    return data['data']['ltp']

def main(token = ["99926000"]):
    client, ohlc_manager = initialize_clients_with_retry()
    correlation_id = "dft_test1"
    mode = 1  # LTP
    #token_list = [{"exchangeType": 1, "tokens": ["99926000"]}]
    #token_list = [{"exchangeType": 1, "tokens": tokens}]
    token_list = [{"exchangeType": 1, "tokens": ["99926000"]},  # NSE Index
            {"exchangeType": 4, "tokens": ["27554"]},
              {"exchangeType": 2, "tokens": tokens}]  # NFO Options
    running = True

    def on_data(wsapp, message):
        try:
            data = eval(message) if isinstance(message, str) else message
            token = str(data['token'])
            ltp = float(data['last_traded_price'])
            ts = data['exchange_timestamp']
            if ts:
                ts_dt = datetime.fromtimestamp(ts / 1000)
                price = ltp / 100
                ohlc_manager.process_tick(token, price, ts_dt)
                print(token)
        except Exception as e:
            print("Error processing tick:", e)

    def on_open(wsapp):
        try:
            client.websocket.subscribe(correlation_id, mode, token_list)
        except Exception as e:
            print("Error during subscription:", e)

    client.websocket.on_open = on_open
    client.websocket.on_data = on_data
    client.websocket.on_error = lambda wsapp, error: print("WebSocket Error:", error)
    client.websocket.on_close = lambda wsapp: print("WebSocket Closed.")

    setup_signal_handlers(client.websocket, correlation_id, mode, token_list)
    client.connect_websocket()

    try:
        while running:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    tokens = get_nifty_options_token()
    #tokens.append("99926000")
    main(tokens)
