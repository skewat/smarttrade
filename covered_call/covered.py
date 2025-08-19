#! /usr/bin/python3
import numpy as np
import requests
import pandas as pd
import pprint
import pyotp
import socket, uuid, time


import os
import sys
import time
import signal
from datetime import datetime, timedelta
import logzero
from logzero import logger

# Project Imports
current_dir = os.path.dirname(os.path.abspath(__file__))
base_path = os.path.abspath(os.path.join(current_dir, ".."))
sys.path.append(base_path)

import config
from common_utils import angelone
from common_utils import till_date_ohlc_data
from common_utils import symboltoken
from common_utils import expiries_of_year

def historical_volatility(data, window=30):
    """Calculate annualized historical volatility from log returns."""
    log_returns = np.log(data / data.shift(1)).dropna()
    hv = log_returns.rolling(window).std().iloc[-1] * np.sqrt(252)
    return hv

def implied_volatility(api, symbol):
    """Fetch approximate IV and ATM option volume from option chain."""
    valid_rows = []
    data = option_greek(api, symbol)

    for r in data:
        try:
            iv = float(r.get("impliedVolatility", "0") or 0)
            delta = float(r.get("delta", "0") or 0)
            vol = float(r.get("tradeVolume", "0") or 0)
        except (TypeError, ValueError):
            continue

        if iv <= 0:
            continue

        # closeness to delta ~ 0.5 = ATM
        valid_rows.append((abs(abs(delta) - 0.5), iv, vol, r))

    if not valid_rows:
        raise ValueError("No valid rows found with IV > 0")

    valid_rows.sort(key=lambda x: x[0])  # nearest to delta=0.5
    best = valid_rows[0]

    iv = float(best[1])
    atm_volume = float(best[2])
    return iv, atm_volume

def _implied_volatility(api, symbol):
    """Fetch approximate IV from NSE option chain (ATM options)."""
    valid_rows = []
    data = option_greek(api, symbol)

    for r in data:
        try:
            iv = float(r.get("impliedVolatility", "0") or 0)
            delta = float(r.get("delta", "0") or 0)
            ety = r.get("expiry", "")
        except (TypeError, ValueError):
            continue

        if iv <= 0:
            continue

        valid_rows.append((abs(abs(delta) - 0.5), iv, r))

    if not valid_rows:
        raise ValueError("No valid rows found with IV > 0")

    # sort by closeness to |delta|=0.5
    valid_rows.sort(key=lambda x: x[0])
    best = valid_rows[0][2]
    print(float(best["impliedVolatility"]))
    return float(best["impliedVolatility"])

def _historical_data(smart_api, symbol):
    token = symboltoken.get_single_symbol_token(symbol, 'EQ')
    ohlc_df = till_date_ohlc_data.historical_data(smart_api, token, exchange,'ONE_DAY',180)
    if ohlc_df and "data" in ohlc_df and ohlc_df["data"]:
        df = pd.DataFrame(ohlc_df["data"], columns=["datetime", "open", "high", "low", "close", "volume"])
        return df.set_index("datetime")["close"].astype(float)
    return None

def scan_covered_calls(api, symbols):
    results = []

    for sym in symbols:
        print(f"Scanning {sym}...")
        try:
            data = _historical_data(smart_api, sym)
            hv = historical_volatility(data, window=30)
            iv, atm_volume = implied_volatility(api, sym)

            sma20 = data.rolling(20).mean().iloc[-1]
            sma60 = data.rolling(60).mean().iloc[-1]
            price = data.iloc[-1]
            underlying_vol = data.iloc[-1]  # last day's volume

            # Basic scoring logic with volume factor
            score = 0
            if iv and hv:
                if iv > hv:  # premium rich
                    score += (iv - hv) * 100
            if sma20 >= sma60:  # uptrend or sideways
                score += 5
            if hv < 0.30:  # avoid extremely volatile stocks
                score += 5

            # Add major weight for liquidity
            score += min(atm_volume / 1000, 20)  # normalize ATM volume
            score += min(underlying_vol / 1e6, 20)  # normalize stock volume

            results.append({
                "Symbol": sym,
                "Price": round(price, 2),
                "HV%": round(hv*100, 2),
                "IV%": round(iv, 2) if iv else None,
                "SMA20": round(sma20, 2),
                "SMA60": round(sma60, 2),
                "ATM_Volume": int(atm_volume),
                "Underlying_Volume": int(underlying_vol),
                "Score": round(score, 2)
            })
        except Exception as e:
            print(f"Error with {sym}: {e}")

    df = pd.DataFrame(results)
    print(df)
    df = df.sort_values("Score", ascending=False).head(5)
    return df

def _scan_covered_calls(api, symbols):
    results = []
    
    for sym in symbols:
        print(f"Scanning {sym}...")
        symbol = sym
        try:
            data = _historical_data(smart_api, symbol)
            hv = historical_volatility(data, window=30)
            iv = implied_volatility(api,sym)
            
            sma20 = data.rolling(20).mean().iloc[-1]
            sma60 = data.rolling(60).mean().iloc[-1]
            price = data.iloc[-1]
            
            # Basic scoring logic
            score = 0
            if iv and hv:
                if iv > hv:  # premium rich
                    score += (iv - hv) * 100
            if sma20 >= sma60:  # uptrend or sideways
                score += 5
            if hv < 0.30:  # avoid extremely volatile stocks
                score += 5
            
            results.append({
                "Symbol": sym,
                "Price": round(price, 2),
                "HV%": round(hv*100, 2),
                "IV%": round(iv, 2) if iv else None,
                "SMA20": round(sma20, 2),
                "SMA60": round(sma60, 2),
                "Score": score
            })
        except Exception as e:
            print(f"Error with {sym}: {e}")
    
    df = pd.DataFrame(results)
    df = df.sort_values("Score", ascending=False).head(5)
    return df

def find_valid_expiry(expiries=expiries_of_year.main(2025)):
    """Pick the first expiry > 2 days from today."""
    expiry_list = expiries

    min_days = 2
    today = datetime.today()

    # Convert expiry strings to datetime objects
    parsed_expiries = [datetime.strptime(e, "%d%b%y") for e in expiry_list]

    # Sort them
    parsed_expiries.sort()

    # Group by month-year to find last expiry of each month (monthly expiry)
    monthly_expiries = {}
    for d in parsed_expiries:
        key = (d.year, d.month)
        if key not in monthly_expiries or d > monthly_expiries[key]:
            monthly_expiries[key] = d

    # Filter monthly expiries at least min_days away
    valid_expiries = [d for d in monthly_expiries.values() if (d - today).days >= min_days]
    valid_expiries.sort()

    return valid_expiries[0].strftime("%d%b%Y") if valid_expiries else "None"



def option_greek(api, symbol):
    expirydate =  find_valid_expiry()
    expirydate = "30SEP2025"
    params = {
        "name":symbol,
        "expirydate": expirydate
    }
    optionGreek = smart_api.optionGreek(params)
    time.sleep(1)
    df = pd.DataFrame(optionGreek['data'])
    return optionGreek['data']


if __name__ == "__main__":

    token = "99926000"
    exchange = "NSE"
    symbols = [
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK",
    "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BEL", "BHARTIARTL",
    "CIPLA", "COALINDIA", "DRREDDY", "EICHERMOT", "ETERNAL",
    "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO",
    "HINDALCO", "HINDUNILVR", "ICICIBANK", "INDUSINDBK", "INFY",
    "ITC", "JIOFIN", "JSWSTEEL", "KOTAKBANK", "LT",
    "M&M", "MARUTI", "NESTLEIND", "NTPC", "ONGC", "POWERGRID", "RELIANCE", "SBILIFE", "SHRIRAMFIN", "SBIN",
    "SUNPHARMA", "TCS", "TATACONSUM", "TATAMOTORS", "TATASTEEL",
    "TECHM", "TITAN", "TRENT", "ULTRACEMCO", "WIPRO"
    ]
    connector = angelone.AngelOneConnector()
    connector.connect()
    smart_api = connector.smart_api

    if not smart_api:
        logger.error("Could not connect to broker API. Exiting.")
        sys.exit(1)
    logger.info("Connected to broker API.")

    top5 = scan_covered_calls(smart_api, symbols)
    print(top5)
