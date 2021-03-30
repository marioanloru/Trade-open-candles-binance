#!/usr/bin/python3

# DOC: https://binance-docs.github.io/apidocs/futures/en/#continuous-contract-kline-candlestick-data
# CALL EXAMPLE: python3 liquidity.py TRB 15m 2
import sys
import requests
import time
from datetime import datetime
from binance_f import RequestClient
from binance_f.constant.test import *
from binance_f.base.printobject import *
from binance_f.model.constant import *
from decimal import Decimal

SLEEP_TIMEOUT = 60
START_INTERVAL = 14
END_INTERVAL = 17

MAX_STOP_LOSS_RISK=5

candle_status_green = False

API_KEY=""
SECRET_KEY=""

BINANCE_FUTURES_BASE_URL="https://fapi.binance.com"

def check_open_trade_ready():
    now = datetime.utcnow()
    hour_check = now.hour >= START_INTERVAL and now.hour <= END_INTERVAL
    print("\nChecking candle open: {} -> {}".format(now.strftime('%B %d %Y - %H:%M:%S'), hour_check))
    return hour_check

def open_long_position_binance(pair, take_profit, stop_loss, pair_change, quantity, leverage):
    print('\n\tOpening future position LONG with TP: {} and SL: {}'.format(take_profit, stop_loss))
    request_client = RequestClient(api_key=API_KEY, secret_key=SECRET_KEY)
    # Change leverage
    #leverage = request_client.change_initial_leverage(pair, leverage)

    # Create order
    #result = request_client.post_order(symbol=pair, side=OrderSide.BUY, quantity=quantity, ordertype=OrderType.MARKET, positionSide="BOTH")
    print('\n\t\tMarket order created.')
    
    precision = 3
    stop_loss = "{:0.0{}f}".format(stop_loss, precision)
    take_profit = "{:0.0{}f}".format(take_profit, precision)

    # Set take profit and stop loss orders
    print('\n\t\tSetting stop market at: {}.'.format(stop_loss))
    print('\n\t\tSetting take profit market at: {}.'.format(take_profit))

    #result = request_client.post_order(symbol=pair, side=OrderSide.SELL, stopPrice=stop_loss, closePosition=True, ordertype=OrderType.STOP_MARKET, positionSide="BOTH", timeInForce="GTC")
    #result = request_client.post_order(symbol=pair, side=OrderSide.SELL, stopPrice=take_profit, closePosition=True, ordertype=OrderType.TAKE_PROFIT_MARKET, positionSide="BOTH", timeInForce="GTC")


def fib_retracement(min, max):
    diff = max - min
    return { "tp1": min + 0.236 * diff, "tp2": min + 0.382 * diff, "tp3": min + 0.5 * diff, "tp4": min + 0.618 * diff}


def get_last_binance_candles(pair, interval):
    url = requests.get('{}/fapi/v1/continuousKlines?pair={}&interval={}&limit=2&contractType=PERPETUAL'.format(BINANCE_FUTURES_BASE_URL, pair, interval))
    print()
    data = url.json()
    return data

def check_safe_stop_loss(low, open):
    diff = open - low
    trade_risk = (diff / low) * 100
    is_safe = MAX_STOP_LOSS_RISK > trade_risk
    print('\n\t Position risk is: {}'.format(trade_risk))
    if not is_safe:
        print('\n\tTrade is too risky ({}), aborting!.'.format(trade_risk))
        exit(1)
    return is_safe

def trade_the_open(pair, interval, quantity, leverage):
    print('Getting binance candles: ', pair, interval)
    candles = get_last_binance_candles(pair, interval)
    """ Binance API response format
    [
        [
            1499040000000,      // Open time
            "0.01634790",       // Open
            "0.80000000",       // High
            "0.01575800",       // Low
            "0.01577100",       // Close
            "148976.11427815",  // Volume
            1499644799999,      // Close time
            "2434.19055334",    // Quote asset volume
            308,                // Number of trades
            "1756.87402397",    // Taker buy base asset volume
            "28.46694368",      // Taker buy quote asset volume
            "17928899.62484339" // Ignore.
        ]
    ]"""
    last_candle = candles[0]
    lc_open = float(last_candle[1])
    lc_high = float(last_candle[2])
    lc_low = float(last_candle[3])
    lc_close = float(last_candle[4])

    current_candle = candles[1]
    cc_open = float(current_candle[1])
    cc_high = float(current_candle[2])
    cc_low = float(current_candle[3])
    cc_close = float(current_candle[4])
    # Check if candlestick turned green
    if (cc_open < cc_close and cc_open > cc_low):
        print('=== Candle turned green. ===')
        # Check if previous candle is green or red to apply fib retracement
        if (lc_open < lc_close):
            # Previous candle is green
            targets = fib_retracement(lc_close, lc_high)
        else:
            # Previous candle is red
            targets = fib_retracement(lc_open, lc_high)
        print('\tTargets based on fib retracement: ', targets)
        if (check_safe_stop_loss(cc_low, cc_open)):
            open_long_position_binance(pair, targets["tp1"], cc_low, cc_close, quantity, leverage)
            return True
    else:
        print('\t Candle is still RED after the open.')
        return False




def main(pair, quantity, interval='1d', leverage=3):
    order_filled = False
    while not order_filled:
        if (check_open_trade_ready()):
            order_filled = trade_the_open(pair, interval, quantity, leverage)
            break
        time.sleep(SLEEP_TIMEOUT)

if __name__ == "__main__":
    pair = sys.argv[1].upper() + 'USDT'
    quantity = sys.argv[2]
    interval = sys.argv[3]
    leverage = sys.argv[4]
    print('Liquidity trading of: {} with {} as amount at {} candle with {} leverage.'.format(pair, quantity, interval, leverage))
    main(pair, quantity, interval, leverage)
    
    print('Orders successfully set.')
