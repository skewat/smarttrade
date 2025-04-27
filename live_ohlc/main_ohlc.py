#! /usr/bin/python3
import os,sys
import time
from datetime import datetime 

current_dir = os.path.dirname(os.path.abspath(__file__))
base_path = os.path.abspath(os.path.join(current_dir, ".."))
sys.path.append(base_path)

from common_utils.ohlc_recorder import SmartAPIClient, OHLCManager, setup_signal_handlers

def initialize_clients_with_retry(retry_interval=5):
    """Keep retrying to initialize SmartAPIClient and OHLCManager until success."""
    while True:
        try:
            client = SmartAPIClient()
            ohlc_manager = OHLCManager()
            print("SmartAPIClient and OHLCManager initialized successfully!")
            return client, ohlc_manager
        except Exception as e:
            print(f"Initialization failed: {e}")
            print(f"Retrying in {retry_interval} seconds...")
            time.sleep(retry_interval)

def main():

    client, ohlc_manager = initialize_clients_with_retry()
    correlation_id = "dft_test1"
    mode = 1  # LTP
    token_list = [{"exchangeType": 1, "tokens": ["99926000"]}]
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
    main()
