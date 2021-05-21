#!/usr/bin/python3

# DOC: https://binance-docs.github.io/apidocs/futures/en/#continuous-contract-kline-candlestick-data
# Usage: python3 liquidity.py --pair XMR --quantity 10 --interval HOUR --leverage 2 
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

MAX_ORDER_RETRIES = 3

SLEEP_TIMEOUT = 15
START_INTERVAL = 0
END_INTERVAL = 8
FIRST_TRY = True

MAX_STOP_LOSS_RISK = 3

# Futures environment variables
BINANCE_FUTURES_BASE_URL = "https://fapi.binance.com"
BINANCE_FUTURES_KLINES_ENDPOINT = "/fapi/v1/continuousKlines"
BINANCE_FUTURES_EXCHANGE_INFO_ENDPOINT = "/fapi/v1/exchangeInfo"

# Spot environment variables
BINANCE_SPOT_BASE_URL = "https://api.binance.com"
BINANCE_SPOT_CREATE_ORDER_ENDPOINT = "/api/v3/order/test"
BINANCE_SPOT_KLINES_ENDPOINT = "/api/v3/klines"
BINANCE_SPOT_EXCHANGE_INFO_ENDPOINT = "/api/v3/exchangeInfo"

RETRIES = 0

LAST_CANDLE_RED = True
LAST_CANDLE_GREEN = True

LAST_LOW_PRICE = 999999
LAST_HIGH_PRICE = 0

STOP_LOSS_REACHED = False
STOP_LOSS = 0

CAN_CLEAR_STALE_ORDERS = False

TARGET_REACHED = False
TARGET = 99999
TARGETS = []

STOP_LOSS_ORDER = None
TAKE_PROFIT_ORDERS = []
NEXT_STOP_LOSS = 0

POSITION_ORDER_ID = None
PRECISION = 0

class Intervals(Enum):
    FIVETEEN_MINUTES = "15m"
    THIRTY_MINUTES = "30m"
    HOUR = "1h"
    FOUR_HOURS = "4h"
    TWELVE_HOURS = "12h"
    DAY = "1d"
    THREE_DAYS = "3d"
    WEEK = "1w"
    TWO_WEEKS = "2w"
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

class MarketSide(Enum):
    LONG = 'long'
    SHORT = 'short'

    def __str__(self):
        return self.name.lower()

    @staticmethod
    def from_string(s):
        try:
            return MarketSide[s.upper()]
        except KeyError:
            raise ValueError()

def check_best_trade(interval=Intervals.DAY):
    request_client = RequestClient(api_key=API_KEY, secret_key=SECRET_KEY)

    # Request info of all symbols to retrieve precision
    response = requests.get(BINANCE_FUTURES_BASE_URL + BINANCE_FUTURES_EXCHANGE_INFO_ENDPOINT)

    exchange_info = response.json()

    price_precision = 0
    best_bullish_wicks = []
    best_bearish_wicks = []
    print('Number of pairs to check approximately: ', len(exchange_info['symbols']))
    for item in exchange_info['symbols']:
        if (not item['contractType'] == 'PERPETUAL'):
            continue
        print('\t * Checking: {}'.format(item['symbol']))
        candles = get_last_binance_candles(item['symbol'], interval, Markets.FUTURES)
        if (not len(candles) > 1):
            continue
        current_candle = candles[1]
        cc_open = float(current_candle[1])
        cc_high = float(current_candle[2])
        cc_low = float(current_candle[3])
        cc_close = float(current_candle[4])

        if (cc_open < cc_close):
            # Candle is green
            diff = cc_high - cc_close
            cc_wick = round((diff / cc_close) * 100, 2)
            best_bullish_wicks.append({ 'wick': cc_wick, 'symbol': item['symbol'] })
        else:
            # Candle is red
            diff = cc_close - cc_low
            cc_wick = -round((diff / cc_low) * 100, 2)
            best_bearish_wicks.append({ 'wick': cc_wick, 'symbol': item['symbol'] })

    candles = get_last_binance_candles('BTCUSDT', interval, Markets.FUTURES)
    current_candle = candles[1]
    cc_open = float(current_candle[1])
    cc_high = float(current_candle[2])
    cc_low = float(current_candle[3])
    cc_close = float(current_candle[4])
    btc_green = None
    btc_wick = None
    if (cc_open < cc_close):
        # Candle is green
        diff = cc_high - cc_close
        btc_wick = round((diff / cc_close) * 100, 2)
        btc_green = True
    else:
        # Candle is red
        diff = cc_close - cc_low
        btc_wick = -round((diff / cc_low) * 100, 2)
        btc_green = False

    bullish_result = sorted(best_bullish_wicks, key=lambda k: k['wick'], reverse=True)
    bearish_result = sorted(best_bearish_wicks, key=lambda k: k['wick'], reverse=False)
    
    print(white.bold(f'Best options to trade the daily of {interval}'))
    if btc_green:
        print(green.bold(f'\tBTC bullish wick: {btc_wick}%'))
    else:
        print(red.bold(f'\tBTC bearish wick: {btc_wick}%'))

    print(white.bold('Best bullish wicks to trade found are:'))
    for item in bullish_result[0:10]:
        print(green.bold('\t{} -> {} % wick.'.format(item['symbol'], item['wick'])))

    print(white.bold('Best bearish wicks to trade found are:'))
    for item in bearish_result[0:10]:
        print(red.bold('\t{} -> {} % wick.'.format(item['symbol'], item['wick'])))

def move_stop_loss(pair, quantity_to_extract, new_stop):
    global STOP_LOSS_ORDER
    global PRECISION
    request_client = RequestClient(api_key=API_KEY, secret_key=SECRET_KEY)
    quantity = STOP_LOSS_ORDER["quantity"]
    side = STOP_LOSS_ORDER["side"]
    order_id = STOP_LOSS_ORDER["orderId"]
    print(white.bold(f'\tCancelling previous stop loss with order id: {order_id}'))
    if (order_id):
        try:
            result = request_client.cancel_order(symbol=pair, orderId=order_id)
            print(green.bold('\t✓ Previous stop loss cancelled.'))
        except Exception as e:
            print(red.bold(f'\tx Previous stop loss could not be cancelled ({e})'))

    remaining_quantity = float(quantity) - float(quantity_to_extract)
    remaining_quantity_with_precision = "{:0.0{}f}".format(float(remaining_quantity), PRECISION)
    new_stop_with_precision = "{:0.0{}f}".format(float(new_stop), PRECISION)

    print(white.bold(f'Moving stop loss with order id: {order_id} and quantity {remaining_quantity_with_precision} to {new_stop_with_precision}'))
    try:
        result = request_client.post_order(symbol=pair, side=side, stopPrice=new_stop_with_precision, closePosition=True, ordertype=OrderType.STOP_MARKET, positionSide="BOTH", timeInForce="GTC")
        STOP_LOSS_ORDER = {"orderId": result.orderId, "quantity": remaining_quantity_with_precision, "stop_loss": new_stop_with_precision, "side": side}
        print(f'\t ✓ Stop loss succesfully moved.')
    except Exception as e:
        print(red.bold(f'\tStop loss could not be moved ({e})'))


def check_take_profits_reached(pair, cc_open):
    global TAKE_PROFIT_ORDERS
    global NEXT_STOP_LOSS
    global TARGET_REACHED
    request_client = RequestClient(api_key=API_KEY, secret_key=SECRET_KEY)
    new_take_profits = []
    for index in range(len(TAKE_PROFIT_ORDERS)):
        quantity = TAKE_PROFIT_ORDERS[index]["quantity"]
        try:
            result = request_client.get_order(symbol=pair, orderId=TAKE_PROFIT_ORDERS[index]["orderId"])
            if (result.status == 'FILLED' or result.status == 'CANCELED' or result.status == 'REJECTED' or result.status == 'EXPIRED'):
                print(green.bold(f'\t✓ Take profit {TAKE_PROFIT_ORDERS["index"]}'))
                move_stop_loss(pair, quantity, TARGETS[NEXT_STOP_LOSS])
                NEXT_STOP_LOSS += 1
            else:
                new_take_profits = TAKE_PROFIT_ORDERS[index::]
                break
        except Exception as e:
            print(red.bold(f'\t x Something failed checking take profits ({e})'))
            move_stop_loss(pair, quantity, TARGETS[NEXT_STOP_LOSS])
            NEXT_STOP_LOSS += 1
    TAKE_PROFIT_ORDERS = new_take_profits
    if (not len(TAKE_PROFIT_ORDERS)):
        TARGET_REACHED = True


def check_stop_loss_reached(pair, side, cc_low, cc_high):
    global STOP_LOSS_REACHED
    global STOP_LOSS
    global STOP_LOSS_ORDER
    global CAN_CLEAR_STALE_ORDERS
    if (side == MarketSide.LONG):
        # Check if previous SL has been reached
        if (cc_low < float(STOP_LOSS)):
            if (not STOP_LOSS_REACHED):
                request_client = RequestClient(api_key=API_KEY, secret_key=SECRET_KEY)
                try:
                    result = request_client.get_order(symbol=pair, orderId=STOP_LOSS_ORDER["order_id"])
                    if (result.status == 'FILLED' or result.status == 'CANCELED' or result.status == 'REJECTED' or result.status == 'EXPIRED'):
                        print(yellow.bold(f'x Stop loss reached ({result.status}): {STOP_LOSS}'))
                        STOP_LOSS_REACHED = True
                        STOP_LOSS_ORDER = None
                        STOP_LOSS = 0
                        if (CAN_CLEAR_STALE_ORDERS):
                            clear_take_profit_orders(pair)
                            CAN_CLEAR_STALE_ORDERS = False
                except Exception as e:
                    print(yellow.bold(f'x Something failed while checking stop loss ({e}) -> {STOP_LOSS}'))
                    STOP_LOSS_REACHED = True
                    STOP_LOSS_ORDER = None
                    STOP_LOSS = 0

                    if (CAN_CLEAR_STALE_ORDERS):
                        clear_take_profit_orders(pair)
                        CAN_CLEAR_STALE_ORDERS = False
    else:
        if (cc_high > float(STOP_LOSS)):
            if (not STOP_LOSS_REACHED):
                request_client = RequestClient(api_key=API_KEY, secret_key=SECRET_KEY)
                try:
                    result = request_client.get_order(symbol=pair, orderId=STOP_LOSS_ORDER["order_id"])
                    if (result.status == 'FILLED' or result.status == 'CANCELED' or result.status == 'REJECTED' or result.status == 'EXPIRED'):
                        print(yellow.bold(f'x Stop loss reached ({result.status}): {STOP_LOSS}'))
                        STOP_LOSS_REACHED = True
                        STOP_LOSS_ORDER = None
                        STOP_LOSS = 0
                        if (CAN_CLEAR_STALE_ORDERS):
                            clear_take_profit_orders(pair)
                            CAN_CLEAR_STALE_ORDERS = False
                except Exception as e:
                    print(yellow.bold(f'x Something failed while checking stop loss ({e})'))
                    STOP_LOSS_REACHED = True
                    STOP_LOSS_ORDER = None
                    STOP_LOSS = 0
                    if (CAN_CLEAR_STALE_ORDERS):
                        clear_take_profit_orders(pair)
                        CAN_CLEAR_STALE_ORDERS = False

def check_open_trade_ready():
    now = datetime.utcnow()
    hour_check = now.hour >= START_INTERVAL and now.hour <= END_INTERVAL
    if (hour_check):
        print(yellow("\nChecking candle open: {} -> {}.".format(now.strftime('%B %d %Y - %H:%M:%S'), hour_check)))
        time.sleep(SLEEP_TIMEOUT)
    else:
        print(yellow("\nChecking candle open: {} -> {}. Checking again in {} seconds.".format(now.strftime('%B %d %Y - %H:%M:%S'), hour_check, SLEEP_TIMEOUT)))
        time.sleep(SLEEP_TIMEOUT)
    return hour_check

def clear_stale_orders(pair):
    global TAKE_PROFIT_ORDERS
    global STOP_LOSS
    global FIRST_TRY
    if (FIRST_TRY):
        FIRST_TRY = False
        return
    request_client = RequestClient(api_key=API_KEY, secret_key=SECRET_KEY)
    result = request_client.cancel_all_orders(symbol=pair)
    TAKE_PROFIT_ORDERS = []
    print(yellow.bold('\n\t ✓ All the previous stale {} orders have been cleared.'.format(pair)))

def clear_take_profit_orders(pair):
    global TAKE_PROFIT_ORDERS
    global NEXT_STOP_LOSS
    request_client = RequestClient(api_key=API_KEY, secret_key=SECRET_KEY)
    for index in range(len(TAKE_PROFIT_ORDERS)):
        id = TAKE_PROFIT_ORDERS[index]["orderId"]
        try:
            result = request_client.cancel_order(symbol=pair, orderId=id)
            print(yellow.bold('Take profit order id removed: {}'.format(result.orderId)))
        except Exception as e:
            print(white.bold(f' x Something failed while cleaning take profit order ({e}) -> {TAKE_PROFIT_ORDERS["index"]}'))
    TAKE_PROFIT_ORDERS = []
    NEXT_STOP_LOSS = 0
    print(yellow.bold(f'\n\t All {pair} take profit order ids have been cancelled.'))

def open_position_binance_futures(pair, targets, target, stop_loss, pair_change, quantity, leverage, side):
    global STOP_LOSS_ORDER
    global TARGET
    global STOP_LOSS_REACHED
    global STOP_LOSS
    global TAKE_PROFIT_ORDERS
    global CAN_CLEAR_STALE_ORDERS
    global POSITION_ORDER_ID
    global PRECISION
    global TARGETS

    request_client = RequestClient(api_key=API_KEY, secret_key=SECRET_KEY)
    # Cancel previous take profit and stop loss orders
    clear_stale_orders(pair)

    # Change leverage
    try:
        request_client.change_initial_leverage(pair, leverage)
    except:
        pass
    try:
        margin_type = request_client.change_margin_type(symbol=pair, marginType=FuturesMarginType.ISOLATED)
    except:
        pass
    # Request info of all symbols to retrieve precision
    exchange_info = request_client.get_exchange_information()
    price_precision = 0
    tick_size = 0
    for item in exchange_info.symbols:
        if (item.symbol == pair):
            precision = item.quantityPrecision
            price_precision = item.pricePrecision
            tick_size = item.filters[0]["tickSize"]
            tick_size = str(tick_size).split('.')[1].find("1") + 1
            PRECISION = price_precision
            if (tick_size < price_precision):
                print(white.bold(f'Tick size ({tick_size}) lower than price precision ({price_precision}), new precision is {price_precision}.'))
                price_precision = tick_size
                PRECISION = price_precision

    # Create order
    quantity_rounded = float(quantity * leverage) / float(pair_change)
    quantity_with_precision = "{:0.0{}f}".format(quantity_rounded, precision)

    stop_loss = "{:0.0{}f}".format(stop_loss, price_precision)
    take_profit = "{:0.0{}f}".format(targets[target], price_precision)

    STOP_LOSS = stop_loss
    STOP_LOSS_REACHED = False

    TARGET = targets[target]

    print(white.bold('\n\tOpening future position {} at market ({}) with quantity: {} {} with take profit on: {} and stop loss: {}'.format(side, pair_change, quantity_with_precision, pair, take_profit, stop_loss)))
    order_side = OrderSide.BUY
    if (side == MarketSide.SHORT):
        order_side = OrderSide.SELL

    result = request_client.post_order(symbol=pair, side=order_side, quantity=quantity_with_precision, ordertype=OrderType.MARKET, positionSide="BOTH")
    POSITION_ORDER_ID = result.orderId
    print(green.bold('\n\t\t✓ Market order created.'))

    # Set take profit and stop loss orders
    weighted_targets = {
        1: [{ 1: 1}],
        2: [{ 1: 0.25 }, { 2: 0.75 }],
        3: [{1: 0.25}, {2: 0.25}, {3: 0.50}],
        4: [{1: 0.20},{2: 0.20},{3: 0.20},{4: 0.40},
        ]
    }

    order_side = OrderSide.SELL
    if (side == MarketSide.SHORT):
        order_side = OrderSide.BUY
    CAN_CLEAR_STALE_ORDERS = True
    remaining_quantity = float(quantity_with_precision)
    try:
        take_profits_set = 0
        for index in range(len(weighted_targets[target])):
            for key, weight in weighted_targets[target][index].items():
                weighted_quantity = quantity_rounded * weight
                if (index == len(weighted_targets[target]) - 1):
                    weighted_quantity += remaining_quantity
                weighted_quantity_with_precision = "{:0.0{}f}".format(weighted_quantity, precision)
                remaining_quantity -= float(weighted_quantity_with_precision)

                take_profit = "{:0.0{}f}".format(targets[key], price_precision)
                try:
                    print(white.bold(f'\n\t\t Creating take profit order weight: {weight * 100} at {take_profit} with weighted quantity: {weighted_quantity_with_precision}, current price: {pair_change}'))
                    result = request_client.post_order(symbol=pair, side=order_side, quantity=weighted_quantity_with_precision, price=take_profit, stopPrice=take_profit, ordertype=OrderType.TAKE_PROFIT, positionSide="BOTH", timeInForce="GTC")
                    print(green.bold('\n\t\t✓ Take profit successfully created.'))
                    TAKE_PROFIT_ORDERS.append({ "take_profit": take_profit, "quantity": weighted_quantity_with_precision, "orderId": result.orderId})
                    TARGETS.append(take_profit)
                    take_profits_set += 1
                except Exception as e:
                    weighted_quantity_with_precision = "{:0.0{}f}".format(weighted_quantity, precision)
                    print(yellow.bold('\n\t\tx Take profit with {} weight created at: {} failed ({}). Weighted quantity: {}. Selling at market price'.format(weight * 100, take_profit, e, weighted_quantity_with_precision)))
                    request_client.post_order(symbol=pair, side=order_side, ordertype=OrderType.MARKET, quantity=weighted_quantity_with_precision, positionSide="BOTH")
                    
        if (take_profits_set == 0):
            raise Exception('Take profit orders were all market selled. Close position and stop loss')

        if (remaining_quantity > 0):
            remaining_quantity_with_precision = "{:0.0{}f}".format(remaining_quantity, precision)
            result = request_client.post_order(symbol=pair, side=order_side, stopPrice=stop_loss, closePosition=True, ordertype=OrderType.STOP_MARKET, positionSide="BOTH", timeInForce="GTC")

            STOP_LOSS_ORDER = {"orderId": result.orderId, "quantity": remaining_quantity_with_precision, "stop_loss": stop_loss, "side": order_side}
            print(green.bold('\n\t\t✓ Stop order at: {} created with {} as quantity.'.format(stop_loss, remaining_quantity_with_precision)))
        return True
    except Exception as e:
        # Cancel order if something did not work as expected
        remaining_quantity_with_precision = "{:0.0{}f}".format(remaining_quantity, precision)
        print(red.bold('\n\t\t x Stop loss failed ({}). Cancelling order at market price : {}.'.format(e, remaining_quantity_with_precision)))
        STOP_LOSS_ORDER = {"orderId": None, "quantity": remaining_quantity_with_precision, "stop_loss": stop_loss, "side": order_side}
        
        clear_stale_orders(pair)
        # Change this check for the minimun notional quantity
        if (remaining_quantity > 5):
            result = request_client.post_order(symbol=pair, side=order_side, quantity=remaining_quantity_with_precision, ordertype=OrderType.MARKET, positionSide="BOTH")
        return False

def open_position_binance_spot(pair, limit, pair_change, quantity, side = SpotSides.BUY):
    url = BINANCE_SPOT_BASE_URL + BINANCE_SPOT_CREATE_ORDER_ENDPOINT
    
    response = requests.get(BINANCE_SPOT_BASE_URL + BINANCE_SPOT_EXCHANGE_INFO_ENDPOINT)
    exchange_info = response.json()
    price_precision = 0
    for item in exchange_info["symbols"]:
        if (item["symbol"] == pair):
            price_precision = item["baseAssetPrecision"]

    quantity_rounded = float(quantity) / float(pair_change)
    quantity_with_precision = "{:0.0{}f}".format(quantity_rounded, price_precision)
    
    parameters = {}
    if (side == SpotSides.BUY):
        parameters = { "symbol": pair, "side": SpotSides.BUY, "type": "LIMIT", "price": limit, "quantity": quantity_with_precision }
    else:
        parameters = { "symbol": pair, "side": SpotSides.SELL, "type": "STOP_LOSS", "quantity": quantity_with_precision, "stopPrice": quantity_with_precision }
    
    response = requests.post(url, data = parameters)
    print(response)
    print('***********')
    print(response.json())

    print(white.bold('\n\tOpening spot position type LIMIT for {} pair limit {} with quantity: {}.'.format(pair, limit, quantity)))
    print(green.bold('\n\t\t✓ Limit order created at price: {}.'.format(limit)))


def fib_retracement(min, max):
    diff = max - min
    return { 1: min + 0.236 * diff, 2: min + 0.382 * diff, 3: min + 0.5 * diff, 4: min + 0.618 * diff}


def get_last_binance_candles(pair, interval, market=Markets.FUTURES):
    response = None
    limit = 2
    if (interval == Intervals.TWO_WEEKS.value):
        two_week_reference = datetime.utcfromtimestamp(1618185600)
        now = datetime.utcfromtimestamp(1619433046)
        now = datetime.utcnow()
        diff = now - two_week_reference
        diff_in_minutes = (diff.total_seconds() % (14 * 24 * 60 * 60)) / 60
        diff_in_hours = diff_in_minutes / 60

        next_two_week_candle = (14 * 24) - diff_in_hours
        interval = Intervals.WEEK.value
        limit = 3
        if (next_two_week_candle < 24):
            limit = 4

    if (market == Markets.SPOT):
        url = '{}{}?symbol={}&interval={}&limit={}'.format(BINANCE_SPOT_BASE_URL, BINANCE_SPOT_KLINES_ENDPOINT, pair, interval, limit)
        response = requests.get(url)
    else:
        url = '{}{}?pair={}&interval={}&limit={}&contractType=PERPETUAL'.format(BINANCE_FUTURES_BASE_URL, BINANCE_FUTURES_KLINES_ENDPOINT, pair, interval, limit)
        response = requests.get(url)
    data = response.json()

    result = data
    # Parse intervals non accepted by binance API (2w)
    if (len(result) > 2):
        first_week = result[0]
        second_week = result[1]
        third_week = result[2]
        lc_low = min(float(first_week[3]), float(second_week[3]))
        lc_open = float(first_week[1])
        lc_close = float(second_week[4])
        lc_high = max(float(first_week[2]), float(second_week[2]))

        cc_low = float(third_week[3])
        cc_open = float(third_week[1])
        cc_close = float(third_week[4])
        cc_high = float(third_week[2])

        if (next_two_week_candle < 24):
            fourth_week = result[3]
            cc_low = min(float(third_week[3]), float(fourth_week[3]))
            cc_open = float(third_week[1])
            cc_close = float(fourth_week[4])
            cc_high = max(float(third_week[2]), float(fourth_week[2]))
        result = [[first_week[0], lc_open, lc_high, lc_low, lc_close], [third_week[0], cc_open, cc_high, cc_low, cc_close]]  

    return result

def check_safe_stop_loss(low, open):
    diff = open - low
    trade_risk = (diff / low) * 100
    is_safe = MAX_STOP_LOSS_RISK > trade_risk
    print(yellow.bold('\n\t⚠ Position risk is: {}%'.format(round(trade_risk, 2))))
    if not is_safe:
        print(red.bold('\n\tTrade is too risky ({}), aborting!.'.format(trade_risk)))
        exit(1)
    return is_safe

def set_sleep_timeout(interval):
    global SLEEP_TIMEOUT
    sleep = 15
    lowest_tf_sleep = 1
    low_tf_sleep = 3
    if (interval == Intervals.FIVETEEN_MINUTES.value):
        sleep = lowest_tf_sleep
    elif (interval == Intervals.THIRTY_MINUTES.value):
        sleep = lowest_tf_sleep
    if (interval == Intervals.HOUR.value):
        sleep = lowest_tf_sleep
    elif (interval == Intervals.FOUR_HOURS.value):
        sleep = low_tf_sleep
    elif (interval == Intervals.TWELVE_HOURS.value):
        sleep = low_tf_sleep
    SLEEP_TIMEOUT = sleep

def init(interval):
    global START_INTERVAL
    global END_INTERVAL
    set_sleep_timeout(interval)
    now = datetime.utcnow()
    if interval == Intervals.HOUR.value:
        START_INTERVAL = now.hour + 1
        END_INTERVAL = now.hour + 2
    elif interval == Intervals.FOUR_HOURS.value:
        START_INTERVAL = now.hour + 1
        END_INTERVAL = START_INTERVAL + 4
    elif interval == Intervals.TWELVE_HOURS.value:
        START_INTERVAL = now.hour + 1
        END_INTERVAL = START_INTERVAL + 12
    else:
        START_INTERVAL = 0
        END_INTERVAL = 16


def trade_the_open(pair, interval, quantity, leverage, market, side, limit, target):
    global LAST_CANDLE_RED
    global LAST_CANDLE_GREEN
    global LAST_LOW_PRICE
    global LAST_HIGH_PRICE
    global TARGET
    global TARGETS
    global TARGET_REACHED
    global STOP_LOSS_REACHED
    global STOP_LOSS
    global STOP_LOSS
    global CAN_CLEAR_STALE_ORDERS
    global RETRIES
    try:
        candles = get_last_binance_candles(pair, interval, market)
    except:
        return False
            
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
    
    if (not len(TARGETS)):
        TARGETS = [cc_open]

    if (len(TAKE_PROFIT_ORDERS)):
        check_take_profits_reached(pair, cc_open)
        check_stop_loss_reached(pair, side, cc_low, cc_high)

    if (RETRIES > 1 and not STOP_LOSS_REACHED):
        print(white.bold(f'\tCurrent order is still in play. Checking again in {SLEEP_TIMEOUT} seconds'))
        return False

    # LONG trades
    if (side == MarketSide.LONG):
        if (cc_open < cc_close and cc_open >= cc_low):
            if (LAST_CANDLE_RED and cc_low < LAST_LOW_PRICE):
                print(white.bold('\t * Attempt number: {}'.format(RETRIES)))
                RETRIES += 1
                LAST_CANDLE_RED = False
                LAST_LOW_PRICE = cc_low
            else:
                print(yellow.bold('\tCandle is still GREEN as to try again.'))
                return False
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
                result = False
                if (market == Markets.FUTURES):
                    result = open_position_binance_futures(pair, targets, target, cc_low, cc_close, quantity, leverage, side)
                else:
                    result = open_position_binance_spot(pair, cc_close, cc_close, quantity, SpotSides.BUY)
                return result
        else:
            if not LAST_CANDLE_RED:
                LAST_CANDLE_RED = True
            print(yellow.bold('\t Candle is still RED after the open. Checking again in {} seconds'.format(SLEEP_TIMEOUT)))    
            return False
    
    else:
        if (cc_open > cc_close and cc_open <= cc_high):
            if (LAST_CANDLE_GREEN and cc_high > LAST_HIGH_PRICE):
                print(white.bold('\t* Attempt number: {}'.format(RETRIES)))
                RETRIES += 1
                LAST_CANDLE_GREEN = False
                LAST_HIGH_PRICE = cc_high
            else:
                print(yellow.bold('\tCandle is still RED as to try again.'))
                return False
            print(green.bold('\n\tCandle turned red.'))
            # Check if previous candle is red to apply fib retracement
            if (lc_open < lc_close):
                # Previous candle is green
                targets = fib_retracement(lc_open, lc_low)
            else:
                # Previous candle is red
                targets = fib_retracement(lc_close, lc_low)
            print(white.bold('\n\tTargets based on fib retracement: {}'.format(targets)))

            if (check_safe_stop_loss(cc_open, cc_high)):
                if (market == Markets.FUTURES):
                    open_position_binance_futures(pair, targets, target, cc_high, cc_close, quantity, leverage, side)
                else:
                    open_position_binance_spot(pair, cc_close, cc_close, quantity, SpotSides.BUY)
                return True
        else:
            if not LAST_CANDLE_GREEN:
                LAST_CANDLE_GREEN = True
            print(yellow.bold('\t Candle is still GREEN after the open. Checking again in {} seconds'.format(SLEEP_TIMEOUT)))    
            return False

def check_trade_finished(pair, side, interval, market):
    current_hour = datetime.utcnow().hour
    global TARGET_REACHED
    global STOP_LOSS_REACHED
    global RETRIES
    global MAX_ORDER_RETRIES
    print('TARGET REACHED: {} - {} < {}'.format(TARGET_REACHED, current_hour, END_INTERVAL))
    while not TARGET_REACHED and not STOP_LOSS_REACHED and current_hour < END_INTERVAL:
        time.sleep(SLEEP_TIMEOUT)
        try:
            candles = get_last_binance_candles(pair, interval, market)
        except:
            time.sleep(SLEEP_TIMEOUT)
            candles = get_last_binance_candles(pair, interval, market)
        current_candle = candles[1]
        cc_high = float(current_candle[2])
        cc_low = float(current_candle[3])
        check_stop_loss_reached(pair, side, cc_low, cc_high)
        
    print(f'Number of retires: {RETRIES} and maximum value: {MAX_ORDER_RETRIES}')
    if TARGET_REACHED:
        print(green.bold('\n\t\tTarget has been reached!'))
    elif RETRIES < MAX_ORDER_RETRIES:
        print(red.bold(f'\n\t\tMax number of retries reached: {RETRIES} === {MAX_ORDER_RETRIES}.'))
    else:
        print(red.bold('\n\t\tInterval has finished, target has NOT been reached. Exiting.'))

    time.sleep(60)
    clear_stale_orders(pair)

def main(pair, quantity, interval=Intervals.DAY, leverage=2, market=Markets.FUTURES, side=MarketSide.LONG, limit=0, target=1):
    global TARGET 
    global TARGET_REACHED
    global MAX_ORDER_RETRIES
    global RETRIES
    init(interval)

    if (market == Markets.FUTURES):
        pair = pair + 'USDT'
   

    if (side == MarketSide.SHORT):
        TARGET = 0

    print(white.bold('* Liquidity trading of: {} with {} as amount at {} candle with x{} leverage and at {} market starting at {} and finishing at {}.'.format(pair, quantity, interval, leverage, market, START_INTERVAL, END_INTERVAL)))
    while not TARGET_REACHED and (RETRIES < MAX_ORDER_RETRIES):
        if (check_open_trade_ready()):
            trade_the_open(pair, interval, quantity, leverage, market, side, limit, target)
    # Close stale orders when target has been reached
    check_trade_finished(pair, side, interval, market)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Trade the open of candles in different timeframes.')
    parser.add_argument('--pair', type=str, help='Cryptocurrency pair to trade.')
    parser.add_argument('--quantity', type=float, help='Quantity in USD to trade.')
    parser.add_argument('--interval', type=Intervals.from_string, choices=list(Intervals), help='Candle timeframe to trade.')
    parser.add_argument('--leverage', type=int, help='Leverage to apply on the trade.')
    parser.add_argument('--market', type=Markets.from_string, help='Market where the will be executed.', default=Markets.FUTURES)
    parser.add_argument('--side', type=MarketSide.from_string, help='Type of order to be executed.', default=MarketSide.LONG)
    parser.add_argument('--limit', type=float, help='Limit for spot orders.')
    parser.add_argument('--start', type=int, help='Candle UTC start.', default=0)
    parser.add_argument('--end', type=int, help='Candle UTC end.', default=8)
    parser.add_argument('--risk', type=int, help='Risk to take with the trade.', default=4)
    parser.add_argument('--target', type=int, help='Fibonnacci target to reach.', default=4)
    parser.add_argument('--check', action='store_true', help='Check best pair to trade.')

    args = parser.parse_args()

    if (args.check):
        check_best_trade(args.interval.value)
        sys.exit()

    MAX_STOP_LOSS_RISK = args.risk
    main(args.pair, args.quantity, args.interval.value, args.leverage, args.market, args.side, args.limit, args.target)

    print(green.bold('\nOrders successfully set.'))
