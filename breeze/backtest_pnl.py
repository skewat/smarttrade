import pandas as pd
import sys
from datetime import datetime
from datetime import timedelta


# Set print display preferance
pd.set_option('display.max_rows',None)
pd.set_option('display.width', None)


# Load the main spread strategy CSV
trades_df = pd.read_csv("2024_spread_strategy_trades.csv", parse_dates=["entry_time", "exit_time", "expiry"])

# Function to get close price from option CSV for a given timestamp
def get_close_price(filename, timestamp):
    df = pd.read_csv(filename, parse_dates=["datetime"])  # Make sure 'datetime' column exists
    row = df[df['datetime'] == timestamp]
    # If not found, try next minute up to +10 minutes
    if row.empty:
        for i in range(1, 11):
            new_time = timestamp + timedelta(minutes=i)
            row = df[df['datetime'] == new_time]
            if not row.empty:
                print(f"Found match at {new_time}")
                break

    if not row.empty:
        #print(float(row.iloc[0]['close']))
        return float(row.iloc[0]['close'])
    else:
        # You could log or raise a warning here
        #print(f"In {filename} Time dint match ... {timestamp} ")
        #sys.exit(0)
        return None

# Store PnL results
pnl_results = []
atm_entry_list = []
atm_exit_list = []
otm_entry_list = []
otm_exit_list = []


for idx, row in trades_df.iterrows():
    atm_file = row['atm_option_filename'] + ".csv"
    otm_file = row['otm_option_filename'] + ".csv"

    entry_time = row['entry_time'].tz_localize(None)
    exit_time = row['exit_time'].tz_localize(None)
    direction = row['direction']

    # Get option prices at entry and exit
    atm_entry = get_close_price(atm_file, entry_time)

    #print(f"ATM file = {atm_file}")
    atm_exit = get_close_price(atm_file, exit_time)
    otm_entry = get_close_price(otm_file, entry_time)
    otm_exit = get_close_price(otm_file, exit_time)

    if None in [atm_entry, atm_exit, otm_entry, otm_exit]:
        print(f" Entry = {entry_time} Exit = {exit_time} atm_file = {atm_file} otm_file = {otm_file}") 
        print(f" ATM Entry = {atm_entry} , ATM Exit {atm_exit}, OTM Entry {otm_entry}, OTM Exit {otm_exit}")
        print(f"Missing data for trade at index {idx}\n\n")
        pnl = None
    else:
        if direction == 1:  # Bull spread: Buy ATM, Sell OTM
            pnl = (atm_exit - atm_entry) - (otm_exit - otm_entry)
        else:  # Bear spread: Sell ATM, Buy OTM
            pnl = (otm_entry - otm_exit) - (atm_entry - atm_exit)

    pnl_results.append(pnl)
    atm_entry_list.append(atm_entry)
    atm_exit_list.append(atm_exit)
    otm_entry_list.append(otm_entry)
    otm_exit_list.append(otm_exit)

# Add PnL to DataFrame and save
print(pnl_results)
t = 0
for xt in pnl_results :
    if xt :
        t = t + int(float(xt))
print(t)

trades_df["spread_pnl"] = pnl_results
trades_df["atm_entry"] = atm_entry_list
trades_df["atm_exit"] = atm_exit_list
trades_df["otm_entry"] = otm_entry_list
trades_df["otm_exit"] = otm_exit_list

trades_df.to_csv("2024_spread_strategy_trades_with_pnl.csv", index=False)

print("Done! PnL added and saved to 2024_spread_strategy_trades_with_pnl.csv")

if __name__ == "__main__":
    main('sma_supertrend_nifty50_dec_2022_245_data.csv')
