#! /c/Users/SURYAKANT/AppData/Local/Microsoft/WindowsApps/python
import numpy as np
import pprint 

def calculate_payout(option_positions, stock_prices):
    """
    Calculate the total payout for a given set of option positions.

    Parameters:
    option_positions (list of dict): Each dict contains 'type', 'strike', 'premium', and 'quantity'.
    stock_prices (np.array): Array of stock prices at expiration.

    Returns:
    np.array: Total payout for each stock price.
    """
    total_payout = np.zeros_like(stock_prices)
    #pprint.pprint(option_positions)

    for position in option_positions:
        option_type = position['type']  # 'call' or 'put'
        strike_price = position['strike']
        premium = position['premium']
        quantity = position['quantity']

        if option_type == 'call' or option_type == 'CE' :
            # Payout = max(0, stock price - strike price) - premium
            payouts = np.maximum(0, stock_prices - strike_price) - premium
        elif option_type == 'put' or  option_type == "PE" :
            # Payout = max(0, strike price - stock price) - premium
            payouts = np.maximum(0, strike_price - stock_prices) - premium
        else:
            raise ValueError("Option type must be 'call' or 'put'.")

        total_payout += payouts * quantity

    return total_payout

def calculate_max_min_payout(option_positions, stock_price_range):
    """
    Calculate the maximum and minimum payouts for multi-leg option positions.

    Parameters:
    option_positions (list): List of option position details.
    stock_price_range (tuple): Min and max stock price range for calculations.

    Returns:
    tuple: (max_payout, min_payout)
    """
    stock_prices = np.linspace(stock_price_range[0], stock_price_range[1], 100)
    
    payouts = calculate_payout(option_positions, stock_prices)
    
    max_payout = np.max(payouts)
    min_payout = np.min(payouts)
    
    return round(max_payout), round(min_payout)

'''
# Example usage
positions = [{'premium': 156.18, 'quantity': 75, 'strike': 22600, 'type': 'put'},
             {'premium': 86.66, 'quantity': -75, 'strike': 22400, 'type': 'put'}]


price_range = (20000, 30000)
max_payout, min_payout = calculate_max_min_payout(positions, price_range)

print(f"Maximum Payout: {max_payout}")
print(f"Minimum Payout: {min_payout}")

'''
