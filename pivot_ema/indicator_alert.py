import pandas as pd
from pivot_calculator import PivotCalculator
from indicators import calculate_ema
from alert_engines import generate_pivot_alerts

def run_alerts_pipeline(df):
    # Add EMA columns
    df['ema_89_high'] = calculate_ema(df['high'], 89)
    df['ema_89_low'] = calculate_ema(df['low'], 89)

    pivot_calc = PivotCalculator(df)
    std_pivots = pivot_calc.calculate_standard_pivots()
    fib_pivots = pivot_calc.calculate_fibonacci_pivots()

    alerts = generate_pivot_alerts(df, std_pivots, fib_pivots)
    return alerts

def get_alert(connector, df):
    # sample 5-min dataframe
    #df = pd.read_csv("your_5min_data.csv", parse_dates=["Datetime"], index_col="Datetime")
    alerts = run_alerts_pipeline(df)
    for a in alerts:
        print(a)

