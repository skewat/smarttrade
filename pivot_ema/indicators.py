def calculate_ema(series, period):
    """
    Calculate EMA of a pandas Series
    """
    return series.ewm(span=period, adjust=False).mean()

