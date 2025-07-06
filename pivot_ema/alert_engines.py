def generate_pivot_alerts(df, std_pivots, fib_pivots):
    """
    Generates alerts based on pivot and EMA conditions.
    """
    alerts = []

    df = df.set_index('datetime')
    for idx, row in df.iterrows():
        day = row.name.floor('1D')
        std_piv = std_pivots.loc[day] if day in std_pivots.index else None
        fib_piv = fib_pivots.loc[day] if day in fib_pivots.index else None
        
        #for name, pivs in [('Standard', std_piv), ('Fibonacci', fib_piv)]:
        for name, pivs in [('Fibonacci', fib_piv)]:
            if pivs is None:
                continue
            r1, r2, s1, s2 = pivs['R1'], pivs['R2'], pivs['S1'], pivs['S2']
            
            # Resistance
            if row['high'] >= r1 and row['close'] > row['ema_89_high']:
                alerts.append({
                    'time': idx,
                    'type': f"R1 Touch {r1}",
                    'pivot': name,
                    'price': row['close']
                })
            if row['high'] >= r2 and row['close'] > row['ema_89_high']:
                alerts.append({
                    'time': idx,
                    'type': f"R2 Touch {r2}",
                    'pivot': name,
                    'price': row['close']
                })
            # Support
            if row['low'] <= s1 and row['close'] < row['ema_89_low']:
                alerts.append({
                    'time': idx,
                    'type': f"S1 Touch {s1}",
                    'pivot': name,
                    'price': row['close']
                })
            if row['low'] <= s2 and row['close'] < row['ema_89_low']:
                alerts.append({
                    'time': idx,
                    'type': f"S2 Touch {s2}",
                    'pivot': name,
                    'price': row['close']
                })
    return alerts

