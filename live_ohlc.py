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
import pyotp
from smartWebSocketV2 import SmartWebSocketV2  # Correct import
from config import *

# === SmartAPI Login ===
obj = SmartConnect(api_key=apikey)
data = obj.generateSession(username, pwd, pyotp.TOTP(token).now())
AUTH_TOKEN = data['data']['jwtToken']
refreshToken = data['data']['refreshToken']
FEED_TOKEN = obj.getfeedToken()
res = obj.getProfile(refreshToken)

# === Subscription Settings ===
correlation_id = "dft_test1"
mode = 1  # LTP mode or as per your need
running = True

# Tokens to subscribe to
token_list = [{"exchangeType": 1, "tokens": ["99926000"]}]
#token_list = [{"exchangeType": 5, "tokens": ["244999","246083"]}]

# === Initialize WebSocket ===
sws = SmartWebSocketV2(AUTH_TOKEN, apikey, username, FEED_TOKEN)
print("WebSocket object created:", sws)

ohlc_data = {}


def write_ohlc_to_csv(ohlc_data, folder=os.getcwd()):
    os.makedirs(folder, exist_ok=True)
    date = ohlc_data['minute'].date()
    file_path = os.path.join(folder, f"{date}.csv")
    headers = ['minute', 'open', 'high', 'low', 'close']
    row = {
        'minute': ohlc_data['minute'].strftime("%Y-%m-%d %H:%M"),
        'open': ohlc_data['open'],
        'high': ohlc_data['high'],
        'low': ohlc_data['low'],
        'close': ohlc_data['close']
    }
    write_headers = not os.path.exists(file_path)
    with open(file_path, 'a', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        if write_headers:
            writer.writeheader()
        writer.writerow(row)
        print(f"OHLC is written in file {file_path}")


def process_tick(token, price, timestamp):
    minute = timestamp.replace(second=0, microsecond=0)
    if token not in ohlc_data or ohlc_data[token]['minute'] != minute:
        if token in ohlc_data:
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
        token = str(data['token'])
        ltp = float(data['last_traded_price'])
        ts = data['exchange_timestamp']
        if ts:
            #print("Tick:",data)
            ts_dt = datetime.fromtimestamp(ts / 1000)
            price = ltp / 100
            process_tick(token, price, ts_dt)
    except Exception as e:
        print("Error processing tick:", e)


def on_open(wsapp):
    try:
        #print(f"WebSocket connected! Subscribing: {correlation_id}, Mode: {mode}, Tokens: {token_list}")
        sws.subscribe(correlation_id, mode, token_list)
        #print(f"Subscription successful for {token_list}")
    except Exception as e:
        print("Error during subscription on open:", e)


def on_error(wsapp, error):
    print("WebSocket Error:", error)


def on_close(wsapp):
    print("WebSocket closed.")


sws.on_open = on_open
sws.on_data = on_data
sws.on_error = on_error
sws.on_close = on_close


def signal_handler(signum, frame):
    global running
    print(f"\nSignal {signum} received. Cleaning up...")

    running = False  # Stop main loop
    try:
        sws.unsubscribe(correlation_id, mode, token_list)
        print(f"Unsubscribed from {token_list}")
    except Exception as e:
        print("Unsubscribe error:", e)

    try:
        sws.close_connection()
        print("WebSocket connection closed.")
    except Exception as e:
        print("Error closing WebSocket:", e)

    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
if platform.system() != "Windows":
    signal.signal(signal.SIGTSTP, signal_handler)

# Start WebSocket Thread (Daemon=True for clean exit)
ws_thread = threading.Thread(target=sws.connect)
ws_thread.daemon = True
ws_thread.start()

print("WebSocket connection thread started. Waiting for data...")

try:
    while running:
        time.sleep(1)
except KeyboardInterrupt:
    signal_handler(signal.SIGINT, None)

