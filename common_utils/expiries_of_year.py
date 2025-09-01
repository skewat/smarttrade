import datetime
from datetime import timedelta
import pandas as pd
from common_utils import holidays

def get_next_expiry(reference_date=None):
    """
    Returns the next available Nifty expiry date from the reference date.
    - Until Aug 2025: expiry is on Thursday
    - From Sept 2025 onward: expiry is on Tuesday
    If expiry day is a holiday, it returns the previous working day.

    Parameters:
        reference_date (datetime.datetime): Reference date. Defaults to today.

    Returns:
        str: Expiry date in 'DDMMMYY' format (e.g., '30SEP25')
    """
    if reference_date is None:
        reference_date = datetime.datetime.today()

    # Decide expiry weekday based on NSE rule change
    cutoff_date = datetime.datetime(2025, 9, 1)
    if reference_date >= cutoff_date:
        expiry_weekday = 1   # Tuesday
    else:
        expiry_weekday = 3   # Thursday

    # Get next expiry weekday
    days_until_expiry = (expiry_weekday - reference_date.weekday() + 7) % 7
    if days_until_expiry == 0:  # if today is expiry day, keep today
        days_until_expiry = 0
    next_expiry = reference_date + timedelta(days=days_until_expiry)

    # Adjust for holidays (move backward if expiry falls on a holiday)
    while holidays.is_holiday(next_expiry.strftime("%Y-%m-%d")):
        next_expiry -= timedelta(days=1)

    return next_expiry.strftime("%d%b%y").upper()

def get_calendar_dates(year):
    """
    Returns all Mondays of the given year.

    Parameters:
        year (int): The year for which calendar dates are generated.

    Returns:
        list of str: List of Mondays in 'YYYY-MM-DD' format.
    """
    all_dates = pd.date_range(start=f"{year}-01-01", end=f"{year}-12-31")
    mondays = all_dates[all_dates.weekday == 0]  # 0 = Monday
    return mondays.strftime("%Y-%m-%d").tolist()

def get_all_expiry_dates(year=None, backtest=False):
    """
    Returns all expiry dates for a given year. If backtesting is enabled,
    it only includes dates at least 7 days old.

    Parameters:
        year (int): The year to compute expiry dates for.
        backtest (bool): If True, skips dates within the last 7 days.

    Returns:
        list of str: List of expiry dates in 'DDMMMYY' format.
    """
    year = datetime.datetime.now().year

    all_exp_dates = []
    calendar_dates = get_calendar_dates(year)
    today = datetime.datetime.now()
    seven_days_ago = today - timedelta(days=7)

    for input_date_str in calendar_dates:
        input_date = datetime.datetime.strptime(input_date_str, '%Y-%m-%d')

        if input_date < seven_days_ago or not backtest:
            exp_date = get_next_expiry(input_date)
            all_exp_dates.append(exp_date)
        else:
            print(f"Date is too close {input_date}")

    return all_exp_dates

def main(year, backtest=False):
    """
    Main function to print all expiry dates for a year.

    Parameters:
        year (int): Year to generate expiry dates for.
        backtest (bool): Whether to exclude recent dates for backtesting.
    """
    exp_dates = get_all_expiry_dates(year, backtest)
    #print(exp_dates)
    return exp_dates

