#!/usr/bin/python3

# DOC: https://binance-docs.github.io/apidocs/futures/en/#continuous-contract-kline-candlestick-data
# Usage: python3 liquidity.py --pair XMR --quantity 10 --interval HOUR --leverage 2 --precision 2
import sys
import requests
import time
import argparse
import os

from datetime import datetime
from binance_f import RequestClient
from binance_f.constant.test import *
from binance_f.base.printobject import *
from binance_f.model.constant import *
from decimal import Decimal
from dotenv import load_dotenv
from enum import Enum
from simple_chalk import yellow, red, green, white


load_dotenv()

API_KEY = os.environ.get('API_KEY')
SECRET_KEY = os.environ.get('SECRET_KEY')

SLEEP_TIMEOUT = 30
START_INTERVAL = 0
END_INTERVAL = 8

MAX_STOP_LOSS_RISK=4

candle_status_green = False

# Futures environment variables
BINANCE_FUTURES_BASE_URL = "https://fapi.binance.com"
BINANCE_FUTURES_KLINES_ENDPOINT = "/fapi/v1/continuousKlines"

# Spot environment variables
BINANCE_SPOT_BASE_URL = "https://api.binance.com"
BINANCE_SPOT_CREATE_ORDER_ENDPOINT = "/api/v3/order"
BINANCE_SPOT_KLINES_ENDPOINT = "/api/v3/klines"
class Intervals(Enum):
    TEN_MINUTES = "15m"
    THIRTY_MINUTES = "30m"
    HOUR = "1h"
    FOUR_HOURS = "4h"
    TWELVE_HOURS = "12h"
    DAY = "1d"
    THREE_DAYS = "3d"
    WEEK = "1w"
    MONTH = "1M"

    def __str__(self):
        return self.name.lower()

    @staticmethod
    def from_string(s):
        try:
            return Intervals[s.upper()]
        except KeyError:
            raise ValueError()

class SpotSides(Enum):
    BUY = 'buy'
    SELL = 'sell'

    def __str__(self):
        return self.name.lower()

    @staticmethod
    def from_string(s):
        try:
            return SpotSides[s.upper()]
        except KeyError:
            raise ValueError()

class Markets(Enum):
    FUTURES = 'futures'
    SPOT = 'spot'

    def __str__(self):
        return self.name.lower()

    @staticmethod
    def from_string(s):
        try:
            return Markets[s.upper()]
        except KeyError:
            raise ValueError()


def check_open_trade_ready():
    now = datetime.utcnow()
    hour_check = now.hour >= START_INTERVAL and now.hour <= END_INTERVAL
    if (hour_check):
        print(yellow("\nChecking candle open: {} -> {}.".format(now.strftime('%B %d %Y - %H:%M:%S'), hour_check)))
    else:
        print(yellow("\nChecking candle open: {} -> {}. Checking again in {} seconds.".format(now.strftime('%B %d %Y - %H:%M:%S'), hour_check, SLEEP_TIMEOUT)))
    return hour_check

def open_long_position_binance_futures(pair, take_profit, stop_loss, pair_change, quantity, leverage, precision):
    request_client = RequestClient(api_key=API_KEY, secret_key=SECRET_KEY)
    # Change leverage
    #request_client.change_initial_leverage(pair, leverage)
    #try:
        #margin_type = request_client.change_margin_type(symbol=pair, marginType=FuturesMarginType.ISOLATED)
    #except:
        #print('error')
    # Create order
    quantity_rounded = float(quantity * leverage) / float(pair_change)
    quantity_with_precision = "{:0.0{}f}".format(quantity_rounded, precision)
    
    stop_loss = "{:0.0{}f}".format(stop_loss, precision)
    take_profit = "{:0.0{}f}".format(take_profit, precision)

    print(white.bold('\n\tOpening future position LONG at market ({}) with quantity: {} {} with take profit on: {} and stop loss: {}'.format(pair_change, quantity_with_precision, pair, take_profit, stop_loss)))
    #result = request_client.post_order(symbol=pair, side=OrderSide.BUY, quantity=quantity_with_precision, ordertype=OrderType.MARKET, positionSide="BOTH")
    print(green.bold('\n\t\t✓ Market order created.'))

    # Set take profit and stop loss orders

    #result = request_client.post_order(symbol=pair, side=OrderSide.SELL, stopPrice=stop_loss, closePosition=True, ordertype=OrderType.STOP_MARKET, positionSide="BOTH", timeInForce="GTC")
    print(green.bold('\n\t\t✓ Stop market order at: {} created.'.format(stop_loss)))
    #result = request_client.post_order(symbol=pair, side=OrderSide.SELL, stopPrice=take_profit, closePosition=True, ordertype=OrderType.TAKE_PROFIT_MARKET, positionSide="BOTH", timeInForce="GTC")
    print(green.bold('\n\t\t✓ Take profit market at: {} creted.'.format(take_profit)))

def open_position_binance_spot(pair, side, limit, pair_change, quantity, precision):
    url = BINANCE_SPOT_BASE_URL + BINANCE_SPOT_CREATE_ORDER_ENDPOINT
    
    quantity_rounded = float(quantity) / float(pair_change)
    quantity_with_precision = "{:0.0{}f}".format(quantity_rounded, precision)
    
    parameters = {}
    if (side == SpotSides.BUY):
        parameters = { "symbol": pair, "side": SpotSides.BUY, "type": "LIMIT", "quantity": quantity_with_precision }
    else:
        parameters = { "symbol": pair, "side": SpotSides.SELL, "type": "STOP_LOSS", "quantity": quantity_with_precision, "stopPrice": quantity_with_precision }
    
    response = requests.post(url, data = parameters)

    print(white.bold('\n\tOpening spot position type {} for {} pair limit/stop order at ({}) with quantity: {}.'.format(side, pair, limit)))
    print(green.bold('\n\t\t✓ Limit order created at price: {}.'.format(limit)))


def fib_retracement(min, max):
    diff = max - min
    return { "tp1": min + 0.236 * diff, "tp2": min + 0.382 * diff, "tp3": min + 0.5 * diff, "tp4": min + 0.618 * diff}


def get_last_binance_candles(pair, interval, market):

    response = None
    if (market == Markets.SPOT):
        response = requests.get('{}{}?symbol={}&interval={}&limit=2'.format(BINANCE_SPOT_BASE_URL, BINANCE_SPOT_KLINES_ENDPOINT, pair, interval))
    else:
        response = requests.get('{}{}?pair={}&interval={}&limit=2&contractType=PERPETUAL'.format(BINANCE_FUTURES_BASE_URL, BINANCE_FUTURES_KLINES_ENDPOINT, pair, interval))
    data = response.json()
    return data

def check_safe_stop_loss(low, open):
    diff = open - low
    trade_risk = (diff / low) * 100
    is_safe = MAX_STOP_LOSS_RISK > trade_risk
    print(yellow.bold('\n\t⚠ Position risk is: {}%'.format(round(trade_risk, 2))))
    if not is_safe:
        print(red.bold('\n\tTrade is too risky ({}), aborting!.'.format(trade_risk)))
        exit(1)
    return is_safe

def trade_the_open(pair, interval, quantity, leverage, precision, market, limit):
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
        print(green.bold('\n\tCandle turned green.'))
        # Check if previous candle is green or red to apply fib retracement
        if (lc_open < lc_close):
            # Previous candle is green
            targets = fib_retracement(lc_close, lc_high)
        else:
            # Previous candle is red
            targets = fib_retracement(lc_open, lc_high)
        print(white.bold('\n\tTargets based on fib retracement: {}'.format(targets)))
        if (check_safe_stop_loss(cc_low, cc_open)):
            if (market == Markets.FUTURES):
                open_long_position_binance_futures(pair, targets["tp2"], cc_low, cc_close, quantity, leverage, precision)
            else:
                open_position_binance_spot(pair, side=SpotSides.BUY, limit, pair_change, quantity, precision
            return True
    else:
        print(yellow.bold('\t Candle is still RED after the open. Checking again in {} seconds'.format(SLEEP_TIMEOUT)))    
        return False




def main(pair, quantity, interval=Intervals.DAY, leverage=2, precision=0, market=Markets.FUTURES, limit=0):
    order_filled = False
    while not order_filled:
        if (check_open_trade_ready()):
            order_filled = trade_the_open(pair, interval, quantity, leverage, precision, market, limit)
        if (not order_filled):
            time.sleep(SLEEP_TIMEOUT)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Trade the open of candles in different timeframes.')
    parser.add_argument('--pair', type=str, help='Cryptocurrency pair to trade.')
    parser.add_argument('--quantity', type=float, help='Quantity in USD to trade.')
    parser.add_argument('--interval', type=Intervals.from_string, choices=list(Intervals), help='Candle timeframe to trade.')
    parser.add_argument('--leverage', type=int, help='Leverage to apply on the trade.')
    parser.add_argument('--precision', type=int, help='Number of decimals (precision) for the selected pair.')
    parser.add_argument('--market', type=Markets.from_string, help='Market where the will be executed.')
    parser.add_argument('--limit', type=float, help='Limit for spot orders.')


    args = parser.parse_args()
    args.pair = args.pair + 'USDT'
    print(white.bold('* Liquidity trading of: {} with {} as amount at {} candle with x{} leverage and precision of {} at {} market.'.format(args.pair, args.quantity, args.interval.value, args.leverage, args.precision, args.market)))
    main(args.pair, args.quantity, args.interval.value, args.leverage, args.precision, args.market, args.limit)
    
    print(green.bold('\nOrders successfully set.'))
