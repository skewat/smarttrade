def test_bullish_crossover_entry():
    row = {
        "time": pd.to_datetime("10:00:00").time(),
        "ema_fast": 102,
        "ema_slow": 100,
        "ema_crossover": "bullish",
        "close": 25500,
        "atr_upper": 25800,
        "atr_lower": 25200
    }
    signals = strategy_decision(row, None, None, [], [], 0.03)
    assert any(s["action"] == "ENTER" and s["position"] == "BULL_PUT" for s in signals)

