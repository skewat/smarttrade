#! /usr/bin/python3
'''
This called with list input as OptionsPositions data input where data is as following.

data = {
     'expiry': '',
     'lotsize': '75',
     'order_type': '', # BUY / SELL
     'opt_type': '',  # PE/CE
     'quantity': '0',
     'strike': '',
     'symbolname': 'NIFTY',
     'symbol_token': '',
     'symbol': '',
     'price': 0,
     'strategy_name': "NONE',
}

'''

import pandas as pd
from SmartApi import SmartConnect
from logzero import logger 
import pyotp
import sys
import signal
import os
import json
import re
import logging
from datetime import datetime, timedelta
import pprint 

from login_details import *

# Set print display preferance
pd.set_option('display.max_rows',None)
pd.set_option('display.width', None)

t_events = logging.getLogger("Logger1")
t_events.setLevel(logging.DEBUG)
handler1 = logging.FileHandler("event_logs.txt")
formatter1 = logging.Formatter('%(asctime)s - %(message)s')
handler1.setFormatter(formatter1)
t_events.addHandler(handler1)



class OptionPosition:
    def __init__(self, data):
        """
        Initialize the OptionPosition object with the given dictionary.
        """
        self.data = data
        self.keys = ['expiry',
                     'lotsize',
                     'opt_type',
                     'quantity',
                     'symbolname',
                     'strike',
                     'order_type',
                     'symbol_token',
                     'symbol',
                     'price',
                     'position_type',
                     'time_stamp',
                     'strategy_name',
                    ]

    def get(self, key):
        """
        Get the value of a given attribute.
        """
        return self.data.get(key)

    def set(self, key, value):
        """
        Set the value of a given attribute.
        """
        if key in self.keys:
            self.data[key] = value
        else:
            raise KeyError(f"Invalid key: {key}")

    def __repr__(self):
        """
        String representation of the OptionPosition object.
        """
        return str(self.data)


def trade_positions(smartApi,positions):
    # Its expected that in the positions list , BUY orders are added before RSELL
    # so that margin issues do not occur
    message = f"Event: Taking Entry"
    t_events.info(message)
    for position in positions :
        order = place_order(smartApi,position)
        write_active_order(order)


def place_order(smartApi, position):
    order = {
            "variety": "NORMAL", # ROBO NORMAL STOPLOSS AMO
            "tradingsymbol": position.get('symbol'),
            "symboltoken": position.get('symbol_token'),
            "transactiontype": position.get("order_type"),
            "exchange": "NFO",
            "ordertype": "MARKET",
            "producttype": "CARRYFORWARD",
            "duration": "DAY",
            "quantity":  position.get("quantity"),
            'ordertag': 'STRATEGY'
        }
    
    # Place Orders
    order_status = {}
    order_id = []
    if PAPER_TRADING:
        # IN Paper trading since positins will not be with broker , so insert a netprice .
        order['netprice'] = get_ltp(smartApi,token= order['symboltoken'],symbol=order['tradingsymbol'],exchange=order["exchange"])
        print("Not adding real order .. its mock/paper trading")
        #print(order)
        return order
    response = smartApi.placeOrderFullResponse(order)
    oid = response['data']['orderid']
    try: 
        status = get_order_status(smartApi, oid) 
        assert( status != 'Order not found')
        assert( status != 'cancelled')
        #assert( status != 'rejected')
        #TBD  write only order which are with status as complete
    except AssertionError as e:
        print(f"Order {str(order_status[oid])} is not complete ")
        print(f"AssertionError: {e}")
        return None
    #For debugging only
    #print(response)
    return order


# Main highlevel logic
def main(martApi, positions):
    # Generate trade
    trade_positions(smartApi,positions)

if __name__ == "__main__":
    smartApi = connect_angeloone()
    if not smartApi :
        sys.exit("Failied while connecting to server")
    fetch_data(smartApi)
    main(smartApi)
    logout(smartApi)

