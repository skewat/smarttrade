#! /c/Users/SURYAKANT/AppData/Local/Microsoft/WindowsApps/python

import schedule
import time
import subprocess
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler

logger1 = logging.getLogger("Logger1")
logger1 .setLevel(logging.DEBUG)
handler1 = RotatingFileHandler("scheduler-logs.log", maxBytes=1_048_576, backupCount=1)

formatter1 = logging.Formatter('%(asctime)s - %(message)s')
handler1.setFormatter(formatter1)
logger1.addHandler(handler1)

# List of holidays (format: 'YYYY-MM-DD')

HOLIDAYS = {"2025-01-01",
    "2025-01-26",
    "2025-02-26",
    "2025-03-14",
    "2025-03-31",
    "2025-04-06",
    "2025-04-10",
    "2025-04-14",
    "2025-04-18",
    "2025-05-01",
    "2025-06-07",
    "2025-07-06",
    "2025-08-15",
    "2025-08-27",
    "2025-10-02",
    "2025-10-21",
    "2025-10-22",
    "2025-11-05",
    "2025-12-25"}

print('Hello')
# Function to check if today is a holiday
def is_holiday():
    today = datetime.now().strftime('%Y-%m-%d')
    return today in HOLIDAYS

# Function to run the strategy script
def run_spread_strategy():
    logger1.info("Executer called..")
    if is_holiday():
        logger1.info(f"{datetime.now()} - Skipping execution due to holiday.")
        return
    try:
        logger1.info(f"{datetime.now()} - Strategy executed successfully.")
        subprocess.run(["python","spread_strategy.py"], check=True)
    except subprocess.CalledProcessError as e:
        logger1.error(f"Error executing strategy: {e}")

# Schedule the strategy to run every 5 minutes between 9:20 AM and 3:25 PM
def schedule_strategy():
    if datetime.now().weekday() < 5:  # 0=Monday, 4=Friday
        logger1.info("Initialising Scheduler..")
        schedule.every(5).minutes.do(run_spread_strategy)
        #schedule.every(5).seconds.do(run_spread_strategy)

# Main loop to keep the scheduler running
if __name__ == "__main__":
    logger1.info("Starting")
    schedule_strategy()
    while True:
        now = datetime.now().strftime("%H:%M")
        if "09:20" <= now <= "15:25":
        #if "09:20" <= now <= "22:25":
            schedule.run_pending()
            logger1.info("Run scheduled job..")
        else:
            print("Out of time window")
        time.sleep(60)

