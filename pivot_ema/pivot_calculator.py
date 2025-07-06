import pandas as pd

class PivotCalculator:
    def __init__(self, df):
        self.df = df
    def calculate_standard_pivots(self):
        self.df['datetime'] = pd.to_datetime(self.df['datetime'])  # adjust the column name if needed
        self.df = self.df.set_index('datetime')
        prev_day = self.df.resample('1D').agg({
            'high': 'max',
            'low': 'min',
            'close': 'last'
        }).shift(1)
        pp = (prev_day['high'] + prev_day['low'] + prev_day['close']) / 3
        r1 = 2 * pp - prev_day['low']
        s1 = 2 * pp - prev_day['high']
        r2 = pp + (prev_day['high'] - prev_day['low'])
        s2 = pp - (prev_day['high'] - prev_day['low'])
        pivots = pd.DataFrame({'PP': pp, 'R1': r1, 'S1': s1, 'R2': r2, 'S2': s2})
        return pivots

    def calculate_fibonacci_pivots(self):
        prev_day = self.df.resample('1D').agg({
            'high': 'max',
            'low': 'min',
            'close': 'last'
        }).shift(1)
        pp = (prev_day['high'] + prev_day['low'] + prev_day['close']) / 3
        rng = prev_day['high'] - prev_day['low']
        r1 = pp + 0.382 * rng
        s1 = pp - 0.382 * rng
        r2 = pp + 0.618 * rng
        s2 = pp - 0.618 * rng
        pivots = pd.DataFrame({'PP': pp, 'R1': r1, 'S1': s1, 'R2': r2, 'S2': s2})
        return pivots

