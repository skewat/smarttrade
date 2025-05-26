#!/usr/bin/python3

import pandas as pd
from logzero import logger
from SmartApi import SmartConnect
from datetime import datetime
from collections import defaultdict
import pprint 
import time
import sys

from common_utils import smartapi_wrapper
# Set pandas display preferences
pd.set_option('display.max_rows', None)
pd.set_option('display.width', None)


class StrategyManager:
    def __init__(self, smart_api):
        self.smart_api = smart_api
        self.wrapper_api = smartapi_wrapper.SmartAPIWrapper(smart_api)

    def take_entry_positions(self, positions,position_type=None):
        logger.info("Event: Taking Entry")

        # Sort positions so that BUY orders come before SELL
        positions = sorted(positions, key=lambda x: x.data["order_type"] != "BUY")

        for position in positions:
            order = self._place_order(position,position_type)

    # input is one position at a time 
    def target_order(self,position, target_point, stop_loss = False):
        open_positions = self.smart_api.position()
        order_book = self.smart_api.orderBook()
        target_tradingsymbol = position[0].get('symbol')
        order_type = position[0].get("order_type")
        data = self.get_latest_completed_order(order_book, target_tradingsymbol, order_type)
        # if order rejected or failed 
        if not data : 
            logger.warning("Looks like primary order failed..")
            return

        price = data['averageprice']
        #percent = 1*float(target_percent)/100
        for data in open_positions['data'] :
            if position[0].get('symbol') == data['tradingsymbol'] and int(data['netqty']) >= int(position[0].get('quantity')):
            #if 1:
                if stop_loss :
                    logger.info('There is valid open position to set STOPLOSS')
                else:
                    logger.info('There is valid position to set TARGET')
                if order_type == 'SELL':
                    position[0].set("order_type","BUY")
                    #t_price =  round(float(price)*(1 - percent),2)
                    #t_price = round(round(t_price/ 0.05) * 0.05, 2) # round to 0.05
                    if stop_loss :
                        t_price = price + target_point
                    else:
                        t_price = price - target_point

                elif order_type == 'BUY':
                    position[0].set("order_type","SELL")
                    #t_price =  round(float(price)*(1 + percent),2)
                    #t_price = round(round(t_price/ 0.05) * 0.05, 2) # round to 0.05
                    if stop_loss :
                        t_price = price - target_point
                    else:
                        t_price = price + target_point
                position[0].set("price", t_price)
                return position

    def clear_existing_positions(self,connector, tag):
        ''' AT this point clear any pending order or open position with given tag '''
        all_orders = self.get_order_book()

        for position in all_orders['data'] :
            if position['ordertag'] == 'SUPER_TREND' and position['status'] == 'open':
                orderid = position["orderid"]
                variety = position["variety"]
                if variety == 'AMO':
                    variety = 'NORMAL'
                cancel_response = connector.smart_api.cancelOrder(position["orderid"], variety)
        return 


    def get_latest_completed_order(self,orderbook, target_tradingsymbol, order_type):
        """
        Returns the latest completed order for the given tradingsymbol.
        Assumes orderbook is a list of dicts.
        """
        
        # Filter for matching tradingsymbol and complete status
        matching_orders = [
            order for order in orderbook['data']
            if order.get('tradingsymbol') == target_tradingsymbol and  order.get('transactiontype') == order_type and order.get('status', '').lower() == 'complete'
        ]
    
        if not matching_orders:
            return None  # No match found
    
        # Sort by orderid 
        sorted_orders = sorted(
            matching_orders,
            key=lambda x: x.get('orderid'),
            reverse=True
        )
        return sorted_orders[0]

    def _open_position(self, position):
        ''' This is to check if target exit order is still open '''
        open_positions = self.smart_api.position()
        if not open_positions or not open_positions['data']:
            return False
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

    def _place_order(self, position, position_type):
        timeout = 5
        poll_interval = 1
        if position_type == "TARGET":
            logger.info("Placing limit target order")
            order = {
                "variety": "NORMAL",
                "tradingsymbol": position.get("symbol"),
                "symboltoken": position.get("symbol_token"),
                "transactiontype": position.get("order_type"),
                "exchange": "NFO",
                "ordertype": "LIMIT",
                "price": position.get("price"),
                "producttype": "CARRYFORWARD",
                "duration": "DAY",
                "quantity": position.get("quantity"),
                "ordertag":  position.get("strategy_tag")
            }
        if position_type == "STOPLOSS":
            logger.info("Placing STOPLOSS order")
            order = {
                "variety": "STOPLOSS",
                "tradingsymbol": position.get("symbol"),
                "symboltoken": position.get("symbol_token"),
                "transactiontype": position.get("order_type"),
                "exchange": "NFO",
                "ordertype": "STOPLOSS_MARKET",
                "price": 0,
                "producttype": "CARRYFORWARD",
                "duration": "DAY",
                "triggerprice": position.get("price"),
                "quantity": position.get("quantity"),
                "ordertag":  position.get("strategy_tag")
            }
        else :
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
                "ordertag": position.get("strategy_tag")
            }

        try:
            logger.info('Placing order...')
            response = self.wrapper_api.place_order(order)
            order_id = response["data"]["orderid"]
            if response['message'] != 'SUCCESS' :
                raise Exception(f"Order status not valid: {response['message']}")
            logger.info("Waiting for order to be placed ..")
            return order

            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    order_status = self._get_order_status(order_id)
                    if order_status.lower() in ['cancelled','complete','rejected']:
                        return order  # Order has reached final state
                    else:
                        logger.debug(f"Waiting... current status: {order_status}")
                except Exception as e:
                    logger.error(f"Error while fetching order status: {e}")
                time.sleep(poll_interval)
            raise TimeoutError(f"Order {order_id} did not complete within {timeout} seconds.")
        except Exception as e:
            logger.error(f"Order placement failed: {e}")
            return None

    def get_order_book(self):
        order_book = self.smart_api.orderBook()
        return order_book

    def _get_order_status(self, order_id):
        order_book = self.smart_api.orderBook()
        if order_book.get("status"):
            for order in order_book.get("data", []):
                if order["orderid"] == order_id:
                    return order["status"]
        return "Order not found"

def main(connector, positions = None,position_type=None ,target=0):

    connector.connect()
    smart_api = connector.smart_api

    manager = StrategyManager(smart_api)
    if position_type == 'ENTRY' :
        manager.take_entry_positions(positions)
    elif position_type == 'EXIT' :
        manager.exit_positions(positions)
    elif position_type == 'TARGET' :
        positions = manager.target_order(positions,target)
        if positions :
            manager.take_entry_positions(positions,'TARGET')
    elif position_type == 'STOPLOSS' :
        sl = True
        positions = manager.target_order(positions,target,sl)
        if positions :
            manager.take_entry_positions(positions,'STOPLOSS')
    else:
        return manager



if __name__ == "__main__":
    smartApi = None
    positions = []
    main(smartApi, positions)
