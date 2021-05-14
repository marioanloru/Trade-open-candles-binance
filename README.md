#Trade the open candles
## Installation and Dependencies
This code uses Binance Python SDK, which needs to be installed following https://github.com/Binance-docs/Binance_Futures_python#Installation

After installing Binance SDK install modules requirements with `pip3 install -r requirements.txt`
## Futures

It uses the statregy teached at https://www.thecryptocheck.com/ by MartyBoots to take liquidity from wicks.

### Check biggest wicks
First command to be used, checks the biggest wicks for that interval of time (doesn't mean those are the best ones).

`python3 liquidity.py --interval <interval> --check`

It will prompt as shown here:

![photo_2021-05-14_17-55-55](https://user-images.githubusercontent.com/7242825/118296791-a5f4fb80-b4dd-11eb-8c98-60237a86a6c8.jpg)

### Trade order
Once you've checked the biggest wicks, you choose the pair in which you want to trade with the script, the quantity (USDTs), interval (FIVETEEN_MINUTES, THIRTHY_MINUTES, HOUR, FOUR_HOURS, TWELVE_HOURS, DAY, THREE_DAYS, WEEK, TWO_WEEKS or MONTH), leverage, target (this will be explained later) and risk (also explained later).

`python3 liquidity.py --pair <PAIR> --quantity <QUANTITY> --interval <INTERVAL> --leverage <LEVERAGE> --start <CANDLE-START-UTC> --end <END-TIME-UTC> --risk <%-OF-RISK-TO-TAKE> --leverage <LEVERAGE> --target <FIBONACCI-TARGET>`

A valid example would be:
`python3 liquidity.py --pair XMR --quantity 10 --interval DAY --leverage 5 --start 0 --end 8 --risk 4 --target 2` 

#### Target

Target variable, is used inside the script to determine to which FIBO line you want to go with the trade.
If the wick doesn't get to target, and becomes red, it will try it up to 3 times before giving up. (multiplying risk by 3)

Example with ICP/USDT:

As you can see in the image below we'll use as example the wick with the blue arrow (don't pay attention to the next one).
We saw this ICP/USDT wick when using the `--check` command.

![photo_2021-05-14_18-14-20](https://user-images.githubusercontent.com/7242825/118298806-3df3e480-b4e0-11eb-873a-ca42d77ea9f8.jpg)

The script will "draw" a FIBO retracement as we can see in the next image; those lines, going from bottom to top will determine our target variable beeing 1->0.236, 2->0.382, 3->0.5 and 4->0.61 (It's recommended to use 1 or 2 as targets (less risk) but if we think that wick will be strong, we can use 4 as target).

![photo_2021-05-14_18-14-22](https://user-images.githubusercontent.com/7242825/118299119-a3e06c00-b4e0-11eb-80dc-c00075022112.jpg)

The wick starts (take into account, that when we say that the wick starts, the interval wick depends on which interval you've chosen on the script variable):

![photo_2021-05-14_18-14-25](https://user-images.githubusercontent.com/7242825/118299542-2c5f0c80-b4e1-11eb-88dc-e14f6af21d6d.jpg)

The dotted line of the left is the start of thw wick, the green rectangle is where it opens position with the risk that shows the blue arrow (that we've previously determine on the variable `--risk` on the script.

The trade will go up to the target, unless it becomes red for three times (as we explained before).



## Spot [IN PROGRESS]
Opens an order for the new candle at interval introduced when conditions are given.

## Summary

1. Install
   - Clone the respository
   - Install dependencies
     - Binance SDK
     - requirements.txt
   - Create API KEY on Binance, and write API_SECRET and SECRET_KEY on .env file. (**REMEMBER** to set the API KEY on Binance only for your public IP.)
2. Commands: 
   - Check best "play"(changing parameters):
     - `python3 liquidity.py --interval DAY --check`
   - Launch trade (changing parameters):
     - `python3 liquidity.py --pair ICP --market futures --quantity 20 --interval DAY --start 0 --end 8 --leverage 4 --target 2 --risk 4`
  
