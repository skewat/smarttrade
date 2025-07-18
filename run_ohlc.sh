#!/bin/bash

# Path to your Python scripts
CHECK_HOLIDAY_SCRIPT="/home/ckewat/options_strategy/smarttrade/check_holiday.py"
#OHLC_SCRIPT="/home/ckewat/options_strategy/smarttrade/live_ohlc_v02.py"
OHLC_SCRIPT="/home/ckewat/options_strategy/smarttrade/live_ohlc/main_ohlc.py"
# Step 1: Run holiday checker
python3 "$CHECK_HOLIDAY_SCRIPT"
HOLIDAY_STATUS=$?

if [ $HOLIDAY_STATUS -ne 0 ]; then
    echo "Today is a holiday. Exiting script."
    exit 0
fi

# Step 2: Start the main script in the background
echo "No holiday. Start the main script in the background."
python3 "$OHLC_SCRIPT" &
PID=$!

echo "Started ohlc_live.py with PID $PID"

# Helper function to convert HH:MM to seconds since midnight
time_to_seconds() {
    IFS=: read hour minute <<< "$1"
    echo $((10#$hour * 3600 + 10#$minute * 60))
}

# Step 3: Compute sleep time until 15:33
CURRENT_TIME=$(date +%H:%M)
CURRENT_SEC=$(time_to_seconds "$CURRENT_TIME")
TARGET_SEC=$(time_to_seconds "15:33")
SLEEP_DURATION=$((TARGET_SEC - CURRENT_SEC))

if [ $SLEEP_DURATION -gt 0 ]; then
    echo "Sleeping for $SLEEP_DURATION seconds until 15:33"
    sleep $SLEEP_DURATION
    echo "Killing process $PID"
    kill $PID
else
    echo "It's past 15:33. Not killing the process."
fi
