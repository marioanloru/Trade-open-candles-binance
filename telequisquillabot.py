#!/usr/bin/env python
# pylint: disable=C0116
# This program is dedicated to the public domain under the CC0 license.

"""
Simple Bot to reply to Telegram messages.

First, a few handler functions are defined. Then, those functions are passed to
the Dispatcher and registered at their respective places.
Then, the bot is started and runs until we press Ctrl-C on the command line.

Usage:
Basic Echobot example, repeats messages.
Press Ctrl-C on the command line or send a signal to the process to stop the
bot.
"""

import logging
import liquidity
import argparse
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext



# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)

parser = argparse.ArgumentParser(description='Trade the open of candles in different timeframes.')
parser.add_argument('--pair', type=str, help='Cryptocurrency pair to trade.')
parser.add_argument('--quantity', type=float, help='Quantity in USD to trade.')
parser.add_argument('--interval', type=liquidity.Intervals.from_string, choices=list(liquidity.Intervals), help='Candle timeframe to trade.')
parser.add_argument('--leverage', type=int, help='Leverage to apply on the trade.')
parser.add_argument('--market', type=liquidity.Markets.from_string, help='Market where the will be executed.', default=liquidity.Markets.FUTURES)
parser.add_argument('--side', type=liquidity.MarketSide.from_string, help='Type of order to be executed.', default=liquidity.MarketSide.LONG)
parser.add_argument('--limit', type=float, help='Limit for spot orders.')
parser.add_argument('--start', type=int, help='Candle UTC start.', default=0)
parser.add_argument('--end', type=int, help='Candle UTC end.', default=8)
parser.add_argument('--risk', type=int, help='Risk to take with the trade.', default=4)
parser.add_argument('--target', type=int, help='Fibonnacci target to reach.', default=4)
parser.add_argument('--check', action='store_true', help='Check best pair to trade.')

# Define a few command handlers. These usually take the two arguments update and
# context.user = liquidity.check_best_trade(liquidity.Intervals.DAY.value)
def check(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /check is issued."""
    if (len(context.args) == 1):
        list = liquidity.check_best_trade(context.args[0])
    else:
        list = liquidity.check_best_trade(liquidity.Intervals.DAY.value)
    update.message.reply_text(list, parse_mode='HTML')

def quisquilla(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /check is issued."""
    args = parser.parse_args(context.args)
    message = liquidity.main(args.pair, args.quantity, args.interval.value, args.leverage, args.market, args.side, args.limit, args.target)
    update.message.reply_text(message, parse_mode='HTML')

def help_command(update: Update, _: CallbackContext) -> None:
    """Send a message when the command /help is issued."""
    user ='Comandos G validos:\n' 
    user = user + '\n\t<code>/check: para ver las velitas donde poner manteca</code>\n'
    user = user + '<code>\t\t\t\tParametros aceptados: 1h 4h 12h 1d 3d 1w 2w 1M</code>\n'
    user = user + '<code>\t\t\t\tValor por defecto: 1d</code>\n'
    
    user = user + '\n\t<code>/quisquilla: Trade the open of candles in different timeframes.</code>\n'
    user = user + '<code>\t\t\t\t--pair: Cryptocurrency pair to trade.</code>\n'
    user = user + '<code>\t\t\t\t--quantity: Quantity in USD to trade.</code>\n'
    user = user + '<code>\t\t\t\t--interval: Candle timeframe to trade.</code>\n'
    user = user + '<code>\t\t\t\t--leverage: Leverage to apply on the trade.</code>\n'
    user = user + '<code>\t\t\t\t--market: Market where the will be executed.</code>\n'
    user = user + '<code>\t\t\t\t--side: Type of order to be executed.</code>\n'
    user = user + '<code>\t\t\t\t--limit: Limit for spot orders.</code>\n'
    user = user + '<code>\t\t\t\t--risk: Risk to take with the trade.</code>\n'
    user = user + '<code>\t\t\t\t--target: Fibonnacci target to reach.</code>\n'
    user = user + '<code>\t\t\t\t--check: Check best pair to trade.</code>\n'

    user = user + '\n\t<code>/help: para ver los comandos G aceptados</code>\n'
    user = user + '<code>\t\t\t\tParametros aceptados: niguno joder, por eso pides ayuda</code>\n'
    user = user + '<code>\t\t\t\tValor por defecto: fuck you</code>\n'
    update.message.reply_text(user, parse_mode='HTML')


def echo(update: Update, _: CallbackContext) -> None:
    """Echo the user message."""
    update.message.reply_text(update.message.text)


def main() -> None:
    """Start the bot."""
    # Create the Updater and pass it your bot's token.
    updater = Updater("TOKEN")

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # on different commands - answer in Telegram
    dispatcher.add_handler(CommandHandler("check", check))
    dispatcher.add_handler(CommandHandler("quisquilla", quisquilla))
    dispatcher.add_handler(CommandHandler("help", help_command))

    # on non command i.e message - echo the message on Telegram
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, echo))

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
