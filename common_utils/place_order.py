#!/usr/bin/python3

import pandas as pd
from logzero import logger
from SmartApi import SmartConnect
from datetime import datetime
import pprint 
import time

from common_utils import smartapi_wrapper
# Set pandas display preferences
pd.set_option('display.max_rows', None)
pd.set_option('display.width', None)


class StrategyManager:
    def __init__(self, smart_api):
        self.smart_api = smart_api
        self.wrapper_api = smartapi_wrapper.SmartAPIWrapper(smart_api)

    def take_entry_positions(self, positions):
        logger.info("Event: Taking Entry")

        #print(positions)
        # Sort positions so that BUY orders come before SELL
        positions = sorted(positions, key=lambda x: x.data["order_type"] != "BUY")

        for position in positions:
            order = self._place_order(position)

    def _open_position(self, position):
        open_positions = self.smart_api.position()
        for data in open_positions['data'] :
            if position.data['symbol'] == data['tradingsymbol'] and data['netqty'] >= position.data['quantity']:
                logger.info('There is valid position to exit')
                return True
        return False

    def exit_positions(self, positions):
        logger.info("Event: Exiting Positions")

        # Sort positions so that BUY orders come before SELL
        positions = sorted(positions, key=lambda x: x.data["order_type"] != "BUY")

        for position in positions:
            if self._open_position(position):
                order = self._place_order(position)
            else:
                logger.info('There is no valid position to exit')

    def _place_order(self, position):
        order = {
            "variety": "NORMAL",
            "tradingsymbol": position.get("symbol"),
            "symboltoken": position.get("symbol_token"),
            "transactiontype": position.get("order_type"),
            "exchange": "NFO",
            "ordertype": "MARKET",
            "producttype": "CARRYFORWARD",
            "duration": "DAY",
            "quantity": position.get("quantity"),
            "ordertag": "STRATEGY"
        }

        try:
            logger.info('Placing order...')
            #pprint.pprint(self.smart_api)
            #pprint.pprint(order)
            #response = self.smart_api.placeOrderFullResponse(order)
            response = self.wrapper_api.place_order(order)
            order_id = response["data"]["orderid"]
            #pprint.pprint(response)
            if response['message'] != 'SUCCESS' :
                raise Exception(f"Order status not valid: {response['message']}")
            return order
        except Exception as e:
            logger.error(f"Order placement failed: {e}")
            return None

    def _get_order_status(self, order_id):
        order_book = self.smart_api.orderBook()
        if order_book.get("status"):
            for order in order_book.get("data", []):
                if order["orderid"] == order_id:
                    return order["status"]
        return "Order not found"

def main(connector, positions,position_type='ENTRY'):

    connector.connect()
    smart_api = connector.smart_api

    manager = StrategyManager(smart_api)
    if position_type == 'ENTRY' :
        manager.take_entry_positions(positions)
    if position_type == 'EXIT' :
        manager.exit_positions(positions)
    # Avoid API call with a second 
    time.sleep(2)



if __name__ == "__main__":
    smartApi = None
    positions = []
    main(smartApi, positions)
