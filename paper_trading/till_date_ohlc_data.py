#! /usr/bin/python3

import pandas as pd
from SmartApi import SmartConnect
from logzero import logger
import pyotp
import sys
import logging
from datetime import datetime, time, timedelta
from login_details import *

# Configure Pandas display settings
pd.set_option('display.max_rows', None)
pd.set_option('display.width', None)

# List of trading holidays (YYYY-MM-DD format)
HOLIDAYS = {
    "2025-01-01", "2025-01-26", "2025-02-26", "2025-03-14", "2025-03-31", "2025-04-06",
    "2025-04-10", "2025-04-14", "2025-04-18", "2025-05-01", "2025-06-07", "2025-07-06",
    "2025-08-15", "2025-08-27", "2025-10-02", "2025-10-21", "2025-10-22", "2025-11-05",
    "2025-12-25"
}

def combine_todays_ohlc(existing_df, minute_csv='t_nifty50_ohlc_2025-04-16.csv'):
    """
    Combine today's 1-minute OHLC data with existing hourly OHLC data.

    Args:
        existing_df (pd.DataFrame): Existing historical hourly OHLC data.
        minute_csv (str): Path to the 1-minute OHLC CSV file.

    Returns:
        pd.DataFrame: Combined DataFrame with updated OHLC data.
    """
    today = datetime.today().strftime('%Y-%m-%d')
    if not minute_csv:
        minute_csv = f"t_nifty50_ohlc_{today}.csv"

    minute_df = pd.read_csv(minute_csv, parse_dates=['datetime'])
    minute_df = minute_df[['datetime', 'open', 'high', 'low', 'close']]
    minute_df = minute_df[
        (minute_df['datetime'].dt.time >= time(9, 15)) &
        (minute_df['datetime'].dt.time <= time(15, 30))
    ]

    minute_df.set_index('datetime', inplace=True)
    hourly_df = minute_df.resample('1H', label='right', closed='right').agg({
        'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'
    }).dropna().reset_index()

    hourly_df['datetime'] = hourly_df['datetime'] - pd.Timedelta(minutes=45)
    hourly_df = hourly_df[
        (hourly_df['datetime'].dt.time >= time(9, 15)) &
        (hourly_df['datetime'].dt.time <= time(15, 15))
    ]

    existing_df = existing_df[['datetime', 'open', 'high', 'low', 'close']]
    combined_df = pd.concat([existing_df, hourly_df])
    combined_df['datetime'] = pd.to_datetime(combined_df['datetime']).dt.tz_localize(None)
    combined_df = combined_df.drop_duplicates(subset='datetime').sort_values('datetime').reset_index(drop=True)

    print(combined_df)
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
        if ref_date.weekday() in {5, 6} or ref_date.strftime('%Y-%m-%d') in HOLIDAYS:
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
    for _ in range(25):
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

def fetch_data(smartApi):
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
            "exchange": "NSE",
            "symboltoken": "99926000",
            "interval": "ONE_HOUR",
            "fromdate": from_date,
            "todate": to_date
        }
        return smartApi.getCandleData(historicParam)
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

def fetch_ohlc(smartApi):
    """
    Fetch and prepare historical OHLC data as DataFrame.

    Args:
        smartApi (SmartConnect): Authenticated SmartAPI object.

    Returns:
        pd.DataFrame: DataFrame with OHLC data.
    """
    data = fetch_data(smartApi)
    df = pd.DataFrame(data["data"], columns=["Datetime", "Open", "High", "Low", "Close", "Volume"])
    df["Datetime"] = pd.to_datetime(df["Datetime"])
    df.set_index("Datetime", inplace=True)
    return df

def main():
    smartApi = connect_angeloone()
    if not smartApi:
        sys.exit("Failed while connecting to server.")

    df = fetch_ohlc(smartApi).reset_index()
    df.columns = df.columns.str.lower()
    df['datetime'] = pd.to_datetime(df['datetime']).dt.tz_localize(None)

    combine_todays_ohlc(df)
    logout(smartApi)

if __name__ == "__main__":
    main()
