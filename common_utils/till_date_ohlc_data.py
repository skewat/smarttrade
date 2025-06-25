#! /usr/bin/python3

import pandas as pd
from SmartApi import SmartConnect
from logzero import logger
import pyotp
import sys,os
import logging
from datetime import datetime, time, timedelta
from login_details import *

from common_utils import holidays

# Configure Pandas display settings
pd.set_option('display.max_rows', None)
pd.set_option('display.width', None)

def combine_todays_ohlc(existing_df, minute_csv):
    """
    Combine today's 1-minute OHLC data with existing hourly OHLC data.

    Args:
        existing_df (pd.DataFrame): Existing historical hourly OHLC data.
        minute_csv (str): Path to the 1-minute OHLC CSV file.

    Returns:
        pd.DataFrame: Combined DataFrame with updated OHLC data.
    """
    if not os.path.exists(minute_csv) or os.stat(minute_csv).st_size == 0:
        return existing_df
    minute_df = pd.read_csv(minute_csv, parse_dates=['datetime'])
    minute_df.columns = [col.lower() for col in minute_df.columns]
    #minute_df.rename(columns={'minute': 'datetime'}, inplace=True)

    #try :
    #    minute_df = minute_df[['datetime', 'open', 'high', 'low', 'close']]
    #except:
    #    minute_df = minute_df[['Datetime', 'Open', 'High', 'Low', 'Close']]

    # Assuming minute_df is already defined
    minute_df['datetime'] = pd.to_datetime(minute_df['datetime'])

    # Now this line is safe
    filtered_df = minute_df[
        (minute_df['datetime'].dt.time >= time(9, 15)) &
        (minute_df['datetime'].dt.time <= time(15, 30))
    ]

   # print(minute_df,existing_df,minute_csv)
   # minute_df = minute_df[
   #     (minute_df['datetime'].dt.time >= time(9, 15)) &
   #     (minute_df['datetime'].dt.time <= time(15, 30))
   # ]

    minute_df.set_index('datetime', inplace=True)
    resampled_df = minute_df.resample('1T', label='right', closed='right').agg({
        'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'
    }).dropna().reset_index()
    resampled_df = resampled_df[
        (resampled_df['datetime'].dt.time >= time(9, 15)) &
        (resampled_df['datetime'].dt.time <= time(15, 30))
    ]

    existing_df = existing_df[['datetime', 'open', 'high', 'low', 'close']]
    combined_df = pd.concat([existing_df, resampled_df])
    #combined_df['datetime'] = pd.to_datetime(combined_df['datetime']).dt.tz_localize(None)
    combined_df['datetime'] = pd.to_datetime(combined_df['datetime'], utc=True).dt.tz_convert(None)


    combined_df = combined_df.drop_duplicates(subset='datetime').sort_values('datetime').reset_index(drop=True)

    return combined_df

def connect_angeloone():
    """
    Establish connection with AngelOne SmartAPI.

    Returns:
        SmartConnect: Authenticated SmartConnect object.
    """
    smartApi = SmartConnect(api_key)
    try:
        token = "YDGLN23VQ7KBI4QEY6PR2OA7TE"
        totp = pyotp.TOTP(token).now()
    except Exception as e:
        logger.error("Invalid Token: The provided token is not valid.")
        raise e

    data = smartApi.generateSession(username, pwd, totp)

    if not data['status']:
        logger.error(data)
        return None

    smartApi.getfeedToken()
    smartApi.getProfile(data['data']['refreshToken'])
    smartApi.generateToken(data['data']['refreshToken'])
    return smartApi

def get_previous_working_day(ref_date):
    """
    Get the previous valid trading day.

    Args:
        ref_date (datetime): Reference date.

    Returns:
        datetime: Previous working day.
    """
    while True:
        ref_date -= timedelta(days=1)
        #if ref_date.weekday() in {5, 6} or ref_date.strftime('%Y-%m-%d') in HOLIDAYS:
        if holidays.is_holiday(ref_date):
            continue
        return ref_date

def get_two_dates():
    """
    Get two valid trading dates for historical data download.

    Returns:
        tuple: Latest working day and a second working day from the past.
    """
    today = datetime.today()
    latest_working_day = get_previous_working_day(today)

    second_working_day = latest_working_day
    for _ in range(30):
        second_working_day = get_previous_working_day(second_working_day)

    return latest_working_day.strftime('%Y-%m-%d'), second_working_day.strftime('%Y-%m-%d')

def get_date_range():
    """
    Get a date range string for historical data query.

    Returns:
        tuple: Start and end datetime strings.
    """
    date1, date2 = get_two_dates()
    return f"{date1} 15:30", f"{date2} 09:15"

def fetch_data(smartApi,symbol_token,exchange='NSE'):
    """
    Fetch historical Nifty50 hourly OHLC data from AngelOne.

    Args:
        smartApi (SmartConnect): Authenticated SmartAPI object.

    Returns:
        dict: Historical candle data.
    """
    to_date, from_date = get_date_range()
    try:
        historicParam = {
            "exchange": exchange,
            "symboltoken": symbol_token,
            "interval": "ONE_MINUTE",
            "fromdate": from_date,
            "todate": to_date
        }
        data = smartApi.getCandleData(historicParam)
        return data
    except Exception as e:
        logger.exception(f"Historic API failed: {e}")

def logout(smartApi):
    """
    Logout from AngelOne SmartAPI.

    Args:
        smartApi (SmartConnect): Authenticated SmartAPI object.
    """
    try:
        smartApi.terminateSession('AAAE362329')
        logger.info("Logout Successful")
    except Exception as e:
        logger.exception(f"Logout failed: {e}")

def get_daily_data(smartApi, symbol_token, exchange, data_file):
    """Fetch data once per day and cache it in a CSV file."""
    filename = data_file

    if os.path.exists(filename) and 0:
        # If file exists, load from CSV
        logger.info(f"Loading data from existing file: {filename}")
        df = pd.read_csv(filename)
    else:
        # If file does not exist, fetch and save
        #print(f"Fetching new data and saving to file: {filename}")
        data = fetch_data(smartApi,symbol_token, exchange)  # Your function
        df = pd.DataFrame(data["data"], columns=["datetime", "open", "high", "low", "close", "volume"])
        df.to_csv(filename, index=False)

    return df

def fetch_ohlc(smartApi,symbol_token, exchange, data_file):
    """
    Fetch and prepare historical OHLC data as DataFrame.

    Args:
        smartApi (SmartConnect): Authenticated SmartAPI object.

    Returns:
        pd.DataFrame: DataFrame with OHLC data.
    """
    df = get_daily_data(smartApi,symbol_token, exchange, data_file)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df.set_index("datetime", inplace=True)
    return df

def main(smartApi,symbol_token,exchange):
    today = datetime.today().date()
    data_file = f"/home/ckewat/options_strategy/smarttrade/data/ohlc_data/{symbol_token}_ohlc_{today}.csv"
    df = pd.DataFrame()
#    if not os.path.exists(data_file):
#        print(f"Todays OHLC data file {data_file} does not exist")
#        return df
    df = fetch_ohlc(smartApi, symbol_token, exchange, data_file).reset_index()
    df.columns = df.columns.str.lower()
    df['datetime'] = pd.to_datetime(df['datetime']).dt.tz_localize(None)
    return combine_todays_ohlc(df,data_file)

if __name__ == "__main__":
    main()
