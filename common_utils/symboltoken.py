import os
import requests
import json
from datetime import datetime
import config 

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

def get_symbol_token(name, expiry, strike_atm, strike_otm,opt_type):
    '''Symbol token is needed for placing order and historical data , this token is not generic and
       it's provided by angelone @
       curl -k https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json
       We store it in symbol_token.py and import it as this gives next few years data.
    '''
    atm_token = None
    otm_token = None
    data = main()
    for i in data:
        if i['exch_seg'] == 'NFO' and  i['name'] == name :
            atm_symbol = f"{name}{expiry}{strike_atm}{opt_type}"
            otm_symbol = f"{name}{expiry}{strike_otm}{opt_type}"
            if i['symbol'] == atm_symbol:
                atm_token = i['token']

            elif i['symbol'] == otm_symbol:
                otm_token = i['token']
                
    if not ( atm_token or not otm_token ) and not config.OPTION_BUYING :
        print("Error !! trading token not found",atm_symbol,otm_symbol)
    return atm_token, otm_token, atm_symbol, otm_symbol

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
