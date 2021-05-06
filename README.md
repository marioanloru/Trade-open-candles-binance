#Trade the open candles
## Installation and Dependencies
This code uses Binance Python SDK, which needs to be installed following https://github.com/Binance-docs/Binance_Futures_python#Installation

After installing Binance SDK install modules requirements with `pip3 install -r requirements.txt`
## Futures

It uses the statregy teached at https://www.thecryptocheck.com/ by MartyBoots to take liquidity from wicks.

### Check biggest wicks
`python3 liquidity.py --interval <interval> --check`

### Trade order
`python3 liquidity.py --pair <PAIR> --quantity <QUANTITY> --interval <INTERVAL> --leverage <LEVERAGE> --start <CANDLE-START-UTC> --end <END-TIME-UTC> --risk <%-OF-RISK-TO-TAKE> --leverage <LEVERAGE> --target <FIBONACCI-TARGET>`

A valid example would be:
`python3 liquidity.py --pair XMR --quantity 10 --interval DAY --leverage 5 --start 0 --end 8 --risk 4 --target 2` 

## Spot [IN PROGRESS]
Opens an order for the new candle at interval introduced when conditions are given.

