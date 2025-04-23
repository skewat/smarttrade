#!/usr/bin/python3

import pandas as pd
from SmartApi import SmartConnect
from datetime import datetime

# Set pandas display preferences
pd.set_option('display.max_rows', None)
pd.set_option('display.width', None)


class StrategyManager:
    def __init__(self, smart_api):
        self.smart_api = smart_api

    def take_entry_positions(self, positions):
        print("Event: Taking Entry")
        for position in positions:
            order = self._place_order(position)
            if order:
                self._write_active_order(order)

    def exit_positions(self, positions):
        print("Event: Exiting Positions")
        for position in positions:
            order = self._place_order(position)
            if order:
                self._remove_active_order(order)

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
            response = self.smart_api.placeOrderFullResponse(order)
            order_id = response["data"]["orderid"]
            status = self._get_order_status(order_id)
            if status not in ("COMPLETE",):
                raise Exception(f"Order status not valid: {status}")
            print(response)
            return order
        except Exception as e:
            print(f"Order placement failed: {e}")
            return None

    def _get_order_status(self, order_id):
        order_book = self.smart_api.orderBook()
        if order_book.get("status"):
            for order in order_book.get("data", []):
                if order["orderid"] == order_id:
                    return order["status"]
        return "Order not found"

def main(smart_api):

    manager = StrategyManager(smart_api)

    # Example usage
    sample_positions = [
        {"symbol": "NIFTY24APR17600CE", "symbol_token": "12345", "order_type": "BUY", "quantity": 75},
        {"symbol": "NIFTY24APR17600PE", "symbol_token": "12346", "order_type": "SELL", "quantity": 75},
    ]

    manager.take_entry_positions(sample_positions)
    # manager.exit_positions(sample_positions)



if __name__ == "__main__":
    smartApi = None
    main(smartApi)
