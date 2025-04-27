# ohlc_recorder.py

import threading
import time
import signal
import sys
import os
import csv
import platform
from datetime import datetime
import pyotp
from SmartApi import SmartConnect
from smartWebSocketV2 import SmartWebSocketV2
from config import apikey, username, pwd, token


class SmartAPIClient:
    """Handles SmartAPI login and WebSocket connection."""

    def __init__(self):
        self.api = SmartConnect(api_key=apikey)
        session = self.api.generateSession(username, pwd, pyotp.TOTP(token).now())
        self.auth_token = session['data']['jwtToken']
        self.feed_token = self.api.getfeedToken()
        self.refresh_token = session['data']['refreshToken']
        self.profile = self.api.getProfile(self.refresh_token)

        self.websocket = SmartWebSocketV2(self.auth_token, apikey, username, self.feed_token)
        print("WebSocket object created:", self.websocket)

    def connect_websocket(self):
        """Starts the WebSocket connection in a separate thread."""
        ws_thread = threading.Thread(target=self.websocket.connect)
        ws_thread.daemon = True
        ws_thread.start()
        print("WebSocket connection thread started.")


class OHLCManager:
    """Manages OHLC data creation from live ticks."""

    def __init__(self, folder=None):
        self.ohlc_data = {}
        self.folder = folder or os.getcwd()
        os.makedirs(self.folder, exist_ok=True)

    def write_ohlc_to_csv(self, token_data):
        """Writes OHLC data to a CSV file."""
        date = token_data['minute'].date()
        file_path = os.path.join(self.folder, f"nifty50_ohlc_{date}.csv")
        headers = ['minute', 'open', 'high', 'low', 'close']

        row = {
            'minute': token_data['minute'].strftime("%Y-%m-%d %H:%M"),
            'open': token_data['open'],
            'high': token_data['high'],
            'low': token_data['low'],
            'close': token_data['close']
        }

        write_headers = not os.path.exists(file_path)
        with open(file_path, 'a', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            if write_headers:
                writer.writeheader()
            writer.writerow(row)
            print(f"OHLC written to {file_path}")

    def process_tick(self, token, price, timestamp):
        """Updates OHLC data based on incoming tick."""
        minute = timestamp.replace(second=0, microsecond=0)
        if token not in self.ohlc_data or self.ohlc_data[token]['minute'] != minute:
            if token in self.ohlc_data:
                self.write_ohlc_to_csv(self.ohlc_data[token])
            self.ohlc_data[token] = {
                'minute': minute,
                'open': price,
                'high': price,
                'low': price,
                'close': price
            }
        else:
            self.ohlc_data[token]['high'] = max(self.ohlc_data[token]['high'], price)
            self.ohlc_data[token]['low'] = min(self.ohlc_data[token]['low'], price)
            self.ohlc_data[token]['close'] = price


def setup_signal_handlers(sws, correlation_id, mode, token_list):
    """Sets up signal handlers for clean shutdown."""

    def signal_handler(signum, frame):
        print(f"\nSignal {signum} received. Cleaning up...")
        try:
            sws.unsubscribe(correlation_id, mode, token_list)
            print("Unsubscribed from tokens.")
        except Exception as e:
            print(f"Unsubscribe error: {e}")

        try:
            sws.close_connection()
            print("WebSocket closed.")
        except Exception as e:
            print(f"WebSocket close error: {e}")

        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    if platform.system() != "Windows":
        signal.signal(signal.SIGTSTP, signal_handler)


