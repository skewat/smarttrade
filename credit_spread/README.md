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


Below is a comprehensive README for the **skewat/smarttrade** repository, focusing on the **common_utils** and **credit_spread** folders.  
It includes:  
1. A full code flow starting from `credit_spread/gen_trades.py`
2. Summaries of key files/functions
3. Usage and environment details

---

# smarttrade: Automated Credit Spread Trading

## Overview

This repository implements automated options trading strategies, specifically credit spreads, using Angel One's SmartAPI.  
The core logic is split between two main folders:

- **common_utils/**: Reusable utilities for broker connection, symbol/token handling, OHLC data management, technical indicators, and more.
- **credit_spread/**: Implements the credit spread strategy, order management, execution logic, and trade orchestration.

The main entry point for live trading is `credit_spread/gen_trades.py`.

---

## Folder Structure

```
smarttrade/
│
├── common_utils/
│   ├── angelone.py         # Angel One API connector
│   ├── sma.py              # Simple Moving Average (SMA) utilities
│   ├── supertrend.py       # Supertrend indicator calculation
│   ├── holidays.py         # Trading holiday calendar
│   ├── ohlc_recorder.py    # Real-time OHLC data recorder
│   ├── symboltoken.py      # Symbol-token resolution utilities
│   ├── smartapi_wrapper.py # Robust SmartAPI wrapper
│   ├── till_date_ohlc_data.py # Historical OHLC data management
│   ├── expiries_of_year.py # Expiry calculation utilities
│   ├── opt_position.py     # Option position management
│
├── credit_spread/
│   ├── gen_trades.py       # Main execution script
│   ├── core.py             # Core business logic
│   ├── config.py           # Strategy and broker config
│   ├── execution.py        # Trading logic and live run manager
│   ├── credit_spread.py    # Persistent order and position management
│   ├── indicators.py       # EMA/ATR indicator utilities
│   ├── strategy_engine.py  # Signal generation and strategy rules
│   ├── log_utils.py        # Logging decorators/utilities
│
```

---

## Code Flow: Main Execution Starting from `gen_trades.py`

1. **Entrypoint: `credit_spread/gen_trades.py`**
   - Ensures single process using file lock (`prevent_multiple_instances`)
   - Waits for trading hours (`wait_for_trading_hours`)
   - Loads config, sets up logger
   - Connects to AngelOne via `common_utils/angelone.py`
   - Registers signal handler for graceful shutdown

2. **API Connection: `common_utils/angelone.py`**
   - `AngelOneConnector` class manages SmartAPI session, authentication tokens, feed tokens
   - Handles connection retry logic and token validation

3. **Configuration: `credit_spread/config.py`**
   - Loads API credentials, strategy parameters (e.g., lotsize, mode, log level)
   - Controls simulation vs. live mode

4. **Core Trading Logic:**
   - **`credit_spread/core.py`**:  
     - Imports all key modules from `common_utils`  
     - Provides utility functions for trading hours, OHLC resampling, LTP retrieval  
     - Handles signal processing and order writing to CSV

   - **`credit_spread/execution.py`**:  
     - The main trading loop (`run_live`)  
     - Loads latest market data, computes technical indicators (EMA, ATR) using `indicators.py`
     - Generates signals via `strategy_engine.py`
     - Calls order execution logic

   - **`credit_spread/strategy_engine.py`**:  
     - Implements decision rules for when to enter/exit credit spreads  
     - Signal logic based on EMA crossovers, ATR bands, profit thresholds, and time-based exits

   - **`credit_spread/credit_spread.py`**:  
     - Manages persistent active orders in CSV  
     - Order placement and exit functions  
     - Ensures duplicate entries are avoided

   - **`credit_spread/indicators.py`**:  
     - Implements EMA and ATR calculation  
     - Adds EMA crossover signals to data

5. **Utilities and Data Management (from `common_utils`):**
   - **`ohlc_recorder.py`**: Real-time tick data collection & OHLC aggregation
   - **`symboltoken.py`**: Resolves symbol-token mapping required for API orders
   - **`supertrend.py` / `sma.py`**: Computes technical indicators for strategy decisions
   - **`opt_position.py`**: Option position objects and order placement helpers
   - **`expiries_of_year.py` / `holidays.py`**: Expiry date calculation, holiday adjustments

6. **Logging & Error Handling:**
   - Logging is managed via `logzero` and custom decorators in `log_utils.py`
   - Key events, function entry/exit, and errors are logged for audit and debugging

---

## Example Usage

### 1. Setup

- Install dependencies (`requirements.txt` includes pandas, logzero, pyotp, SmartAPI, etc.)
- Update API credentials in `credit_spread/config.py`
- Ensure you have access to Angel One SmartAPI

### 2. Run the Main Script

```bash
cd credit_spread
python3 gen_trades.py
```

- The script will run only during market hours (9:16 AM - 3:30 PM IST)
- All logs are saved under `credit_spread/atr_strategy_logfile_<date>.log`
- Active trades and order states are persisted in CSV files for recovery

### 3. Strategy Details

- The strategy uses ATR and EMA crossover signals
- Trades are entered/exited based on strategy signals, profit thresholds, and time-of-day rules
- Orders are placed via Angel One's SmartAPI, with error handling and retry logic

---

## Environment Variables & Sensitive Info

- **API_KEY, USERNAME, PWD, TOKEN**: Must be set in `credit_spread/config.py`.  
  **Do NOT commit your secret credentials to public repositories.**
- **SIMULATE** mode: Useful for testing without placing real orders

---

## Extending or Debugging

- To add new strategies, modify or extend `strategy_engine.py`
- For custom indicators, use or add to `indicators.py`
- Order and position logic can be modified in `credit_spread.py` and `opt_position.py`
- For troubleshooting, check the log files and CSV outputs

---

## References

- [Browse code for common_utils](https://github.com/skewat/smarttrade/tree/main/common_utils)
- [Browse code for credit_spread](https://github.com/skewat/smarttrade/tree/main/credit_spread)
- [Main entry script: gen_trades.py](https://github.com/skewat/smarttrade/blob/main/credit_spread/gen_trades.py)

---

**Note:**  
This summary is based on a code search and may be incomplete.  
For all files and full details, [view the repository on GitHub](https://github.com/skewat/smarttrade).

---

If you need a detailed function-by-function mapping, or want to see full code for any specific file, let me know!
