import time 
import os
import sys

# Project Imports
current_dir = os.path.dirname(os.path.abspath(__file__))
base_path = os.path.abspath(os.path.join(current_dir, ".."))
sys.path.append(base_path)

from common_utils import angelone

connector = angelone.AngelOneConnector()
connector.connect()

while True:

    if connector.is_token_valid():
        print(f"Token is valid. ")
    else:
        print("Token expired. Please reconnect.")
    time.sleep(1)

connector.logout()
