import requests
def get_symbol_token(trading_symbol, exchange="NFO"):
    headers = ''
    url = "https://apiconnect.angelbroking.com/rest/secure/angelbroking/order/v1/searchScrip"
    payload = {"exchange": exchange, "searchscrip": trading_symbol}
    response = requests.post(url, json=payload, headers=headers)
    print(response.text)
    data = response.json()
    
    if data.get("status") and "data" in data and len(data["data"]) > 0:
        return data["data"][0]["symboltoken"]
    print(f"Error !! Symbol token not found for {trading_symbol}")
    return None

get_symbol_token('RELIANCE')
