import time
from logzero import logger as logging
import pandas as pd
import requests

class SmartAPIWrapper:
    """A safe wrapper around SmartAPI with retries for network and rate-limit errors."""

    def __init__(self, smart_api, max_retries=2, sleep_seconds=1):
        self.smart_api = smart_api
        self.max_retries = max_retries
        self.sleep_seconds = sleep_seconds

    def _is_retryable_exception(self, exception):
        """Check if the exception is retryable based on type or message."""
        return True
        if isinstance(exception, (requests.exceptions.RequestException, )):
            return True

        error_message = str(exception).lower()
        retryable_keywords = [
            "rate limit", 
            "too many requests", 
            "access denied because of exceeding access rate"
        ]
        return any(keyword in error_message for keyword in retryable_keywords)

    def _retry_api_call(self, func, *args, **kwargs):
        """Execute an API call with retry on network and rate-limit errors."""
        func_name = func.__name__

        for attempt in range(1, self.max_retries + 1):
            try:
                logging.info(f"Calling API: {func_name} (Attempt {attempt})")
                # Optional: log args safely if needed
                logging.info(f"Args: {args}, Kwargs: {kwargs}")

                response = func(*args, **kwargs)

                # Handle API-level error responses
                if isinstance(response, dict) and response.get('status') == 'error':
                    error_message = str(response.get('message', '')).lower()
                    raise Exception(error_message)

                logging.info(f"Success: {func_name}")
                return response

            except Exception as e:
                if attempt < self.max_retries:
                    time.sleep(self.sleep_seconds)
                else:
                    logging.error(f"{func_name} failed after {self.max_retries} attempts.")
                    raise

    # -------------------------------
    # API Wrapper Methods
    # -------------------------------

    def get_ltp(self, exchange, symbol, token):
        """Get Last Traded Price (LTP)"""
        return self._retry_api_call(self.smart_api.ltpData, exchange, symbol, token)

    def get_open_positions(self):
        """Get current open positions"""
        return self._retry_api_call(self.smart_api.position)

    def place_order(self, order_params):
        """Place an order and get full response"""
        print(order_params)
        return self._retry_api_call(self.smart_api.placeOrderFullResponse, order_params)

    def get_order_book(self):
        """Get current order book"""
        return self._retry_api_call(self.smart_api.orderBook)

    def get_candle_data(self, historic_params):
        """Get candle data"""
        return self._retry_api_call(self.smart_api.getCandleData, historic_params)

