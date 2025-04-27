#! /usr/bin/python3

import os
import shutil
from common_utils.ohlc_recorder import OHLCManager
from datetime import datetime

def test_ohlc_creation_and_write():
    """Test OHLC data creation and CSV writing."""

    # Setup test folder
    test_folder = "test_output"
    if os.path.exists(test_folder):
        shutil.rmtree(test_folder)
    os.makedirs(test_folder)

    manager = OHLCManager(folder=test_folder)
    token = "99926000"
    timestamp = datetime(2025, 4, 27, 10, 15)
    price = 225.5

    manager.process_tick(token, price, timestamp)
    manager.process_tick(token, price + 5, timestamp)  # High
    manager.process_tick(token, price - 3, timestamp)  # Low
    manager.process_tick(token, price + 1, timestamp)  # Close

    # Force write to file
    manager.write_ohlc_to_csv(manager.ohlc_data[token])

    # Verify file exists
    files = os.listdir(test_folder)
    assert len(files) == 1, "CSV file not created"

    csv_file_path = os.path.join(test_folder, files[0])
    with open(csv_file_path, "r") as f:
        content = f.read()
        assert "minute,open,high,low,close" in content, "Headers missing"
        assert "2025-04-27 10:15" in content, "Timestamp missing"

    print("Test Passed!")

if __name__ == "__main__":
    test_ohlc_creation_and_write()

