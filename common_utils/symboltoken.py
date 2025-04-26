import os
import requests
import json
from datetime import datetime
data = []
def download_symbol_token_file():
    today = datetime.now().strftime("%Y%m%d")
    filename = f"symbol_token_{today}.json"

    if os.path.exists(filename):
        #print(f"{filename} already exists. Skipping download.")
        print(' ')
    else:
        url = "https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json"
        try:
            response = requests.get(url)
            response.raise_for_status()
            with open(filename, "wb") as f:
                f.write(response.content)
            #print(f"Downloaded and saved as {filename}")
        except requests.exceptions.RequestException as e:
            print(f"Error downloading the file: {e}")
            return None

    return filename

def load_json_data(filename):
    try:
        with open(filename, "r") as f:
            data = json.load(f)  # This will give you a list of dictionaries
        return data
    except Exception as e:
        print(f"Error loading JSON: {e}")
        return None

def main():
    global data
    filename = download_symbol_token_file()
    if filename:
        data = load_json_data(filename)
        #print(f"Loaded {len(data)} records.")
    else :
        data = []
    return data

if __name__ == '__main__':
    main()
