import threading
from SmartApi import SmartConnect
import time
import signal
import sys
import pandas as pd
from datetime import datetime
import os
import csv
import platform
import pyotp,time
from smartWebSocketV2 import SmartWebSocketV2  # Correct import
from config import  *


# === SmartAPI Login ===
obj=SmartConnect(api_key=apikey)
data = obj.generateSession(username,pwd,pyotp.TOTP(token).now())
AUTH_TOKEN = data['data']['jwtToken']
refreshToken= data['data']['refreshToken']
FEED_TOKEN=obj.getfeedToken()
res = obj.getProfile(refreshToken)

should_subscribe = True


# === iWebsocket and OHLC Configuration ===
correlation_id = "dft_test1"
action = 1
mode = 1
running = True

# Tokens to subscribe to
token_list = [{"exchangeType": 1, "tokens": ["99926000"]}]

# === Auth credentials (replace with your actual values) ===
sws = SmartWebSocketV2(AUTH_TOKEN, apikey, username, FEED_TOKEN)

# OHLC tracker
ohlc_data = {}  # Format: {token: {'minute': datetime, 'open': x, 'high': x, 'low': x, 'close': x}}


def write_ohlc_to_csv(ohlc_data, folder=os.getcwd()):
    """
    Writes OHLC data to a CSV file named by the date (e.g., 2025-04-11.csv).
    Creates the file if it doesn't exist. Appends data if it does.

    :param ohlc_data: dict with keys - 'minute', 'open', 'high', 'low', 'close'
    :param folder: Directory to store CSV files
    """
    # Ensure folder exists
    os.makedirs(folder, exist_ok=True)

    # Extract date from the 'minute' field
    date = ohlc_data['minute'].date()
    file_path = os.path.join(folder, f"{date}.csv")

    # Define CSV headers
    headers = ['minute', 'open', 'high', 'low', 'close']

    # Convert datetime to string format
    row = {
        'minute': ohlc_data['minute'].strftime("%Y-%m-%d %H:%M"),
        'open': ohlc_data['open'],
        'high': ohlc_data['high'],
        'low': ohlc_data['low'],
        'close': ohlc_data['close']
    }

    # Write or append
    write_headers = not os.path.exists(file_path)
    with open(file_path, 'a', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        if write_headers:
            writer.writeheader()
            print(f"OHLC is written in file {file_path}")
        writer.writerow(row)

def process_tick(token, price, timestamp):
    minute = timestamp.replace(second=0, microsecond=0)
    if token not in ohlc_data or ohlc_data[token]['minute'] != minute:
        # Flush and reset for new minute
        if token in ohlc_data:
            #print(f"OHLC for token {token} at {ohlc_data[token]['minute']} => {ohlc_data[token]}")
            write_ohlc_to_csv(ohlc_data[token], folder=os.getcwd())

        ohlc_data[token] = {
            'minute': minute,
            'open': price,
            'high': price,
            'low': price,
            'close': price
        }
    else:
        ohlc_data[token]['high'] = max(ohlc_data[token]['high'], price)
        ohlc_data[token]['low'] = min(ohlc_data[token]['low'], price)
        ohlc_data[token]['close'] = price


def on_data(wsapp, message):
    try:
        data = eval(message) if isinstance(message, str) else message
        #for tick in data.get('data', []):
        token = str(data['token'])
        ltp = float(data['last_traded_price'])  # Assuming price is in paise
        ts = data['exchange_timestamp']
        if ts:
            ts_dt = datetime.fromtimestamp(ts / 1000)
        price = ltp/100
        process_tick(token, price, ts_dt)
    except Exception as e:
        print("Error processing tick:", e)


def on_open(wsapp):
    if should_subscribe:
        sws.subscribe(correlation_id, mode, token_list)
    else :
        sys.exit('Exiting Thread ..')


def on_error(wsapp, error):
    print("Error:", error)


def on_close(wsapp):
    print("WebSocket closed")


# === Callback assignments ===
sws.on_open = on_open
sws.on_data = on_data
sws.on_error = on_error
sws.on_close = on_close


def signal_handler(signum, frame):
    global running
    global should_subscribe
    print(f"\nSignal {signum} received. Cleaning up...")

    try:
        should_subscribe = False
        sws.unsubscribe(correlation_id, mode, token_list)
        #print(f"\n --------- unsubscribed {token_list} --------- \n")
    except Exception as e:
        print("Unsubscribe error:", e)

    try:
        sws.close_connection()
        #print("Connection closed.")
    except Exception as e:
        print("Close connection error:", e)

    running = False
    sys.exit("Exiting ..............")
    os._exit(0)


import smartWebSocketV2

print(str(smartWebSocketV2))

# Register signal handlers for CTRL+C and CTRL+Z (Linux/Unix)
signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C (works on all OS)
if platform.system() != "Windows":
    signal.signal(signal.SIGTSTP, signal_handler)  # Ctrl+Z (Unix only)

# Start WebSocket in a separate thread
#threading.Thread(target=sws.connect).start()
#print('Control Released')

time.sleep(10)

try:
    sws.subscribe(correlation_id, mode, token_list)
    #print(f'\n ------ subscribed {token_list} ------- \n')
except Exception as e:
    print("Subscription error:", e)

# Keep running to collect ticks
try:
    while running:
        time.sleep(1)
except KeyboardInterrupt:
    signal_handler(signal.SIGINT, None)
    sys.exit("Exiting main ..............")
    os._exit(0)

