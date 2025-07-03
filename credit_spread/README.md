📄 File Descriptions
✅ indicators.py

Holds calculate_ema, calculate_atr, add_ema_crossover

pure data functions

unit-testable

✅ strategy_engine.py

Contains strategy_decision()

takes a row + context, returns signals

no side effects

test with simple mocks

✅ execution.py

wires live data + actual broker calls

controls main loop

depends on strategy_engine and indicators

holds on_entry / on_exit

includes run_live()

✅ core.py

your existing common functions (get_ltp, find_valid_expiry)

unchanged, reused

✅ credit_spread.py

your existing spread generation and placing logic

✅ common_utils/expiries_of_year.py

holds expiry helpers

✅ tests/

separate test files for each module

test_indicators.py: pure math

test_strategy_engine.py: strategy decision making

test_execution.py: you can mock core/spread and check call sequence

✅ data/sample_ohlc.csv

store test OHLC 5m or 1m bars

use for replay simulation
