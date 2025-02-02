#!/usr/bin/env python
# -*- coding: utf-8; py-indent-offset:4 -*-
###############################################################################
#
# Copyright (C) 2015-2023 Daniel Rodriguez
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
from __future__ import absolute_import, division, print_function, unicode_literals

import argparse
import datetime
import math

import backtrader as bt
import backtrader.plot.schemes as btschemes
import backtrader.indicators as btind
import backtrader.feeds as btfeeds
import backtrader.filters as btfilters

class Strategy(bt.Strategy):
    def __init__(self):
        self.rsi = btind.RelativeStrengthIndex()
        self.clength = 0
        self.tcounter = 0
        self.order = None

    def notify_order(self, order):
        if order.status in [bt.Order.Completed] and order.parent:
            self.order = None

    def next(self):
        prev_rsi = round(self.rsi[-1], 2)
        rsi = round(self.rsi[0], 2)
        if self.clength == len(self):
            return
        self.clength = len(self)
        if not self.order:
            if prev_rsi < 30:
                self.tcounter += 1
                price = self.data.close[-1]
                diff = self.data.high[-1] - self.data.low[-1]
                print(
                    "[{}] Buy called: Open {}, Close {}, RSI {}_{}".format(
                        self.data.datetime.datetime(), self.data.open[-1], self.data.close[-1], prev_rsi, rsi
                    )
                )
                self.order = self.buy_bracket(
                    data=self.data, price=price, stopprice=price - diff, limitprice=price + diff, tradeid=self.tcounter
                )
            elif prev_rsi > 70:
                self.tcounter += 1
                price = self.data.close[-1]
                diff = self.data.high[-1] - self.data.low[-1]
                print(
                    "[{}] Sell called: Open {}, Close: {}, RSI: {}".format(
                        self.data.datetime.datetime(), self.data.open[-1], self.data.close[-1], prev_rsi
                    )
                )
                self.order = self.sell_bracket(
                    data=self.data, price=price, stopprice=price + diff, limitprice=price - diff, tradeid=self.tcounter
                )


def runstrat():
    args = parse_args()

    # Create a cerebro entity
    cerebro = bt.Cerebro(stdstats=False)

    # Add a strategy
    cerebro.addstrategy(bt.Strategy)
    cerebro.addsizer(bt.sizers.PercentSizer, percents=20)
    cerebro.addobserver(bt.observers.Orders)
    cerebro.addobserver(bt.observers.BuySell)
    cerebro.addobserver(bt.observers.Broker)
    cerebro.getbroker().setcash(100)
    cerebro.getbroker().setcommission(0.025, 1, 50)

    # Get the dates from the args
    fromdate = datetime.datetime.strptime(args.fromdate, "%Y-%m-%d")
    todate = datetime.datetime.strptime(args.todate, "%Y-%m-%d") if args.todate else None

    bitget = btfeeds.BitgetLive()
    futures_config = {
        "options": {
            "defaultType": "swap",
            "marginMode": "isolated",
        },
        "enableRateLimit": True,
    }
    for a in ["DOGEUSDT", "LINKUSDT"]:
        data = bitget.getdata(
            dataname=a,
            compression=1,
            historical=True,
            csv=True,
            timeframe=bt.TimeFrame.Minutes,
            qcheck=5,
            fromdate=fromdate,
            todate=todate,
            config=futures_config if args.futures else {}
        )

        cerebro.adddata(data)
    # data = bitget.getdata(
    #     dataname=args.data,
    #     compression=1,
    #     historical=True,
    #     csv=True,
    #     timeframe=bt.TimeFrame.Minutes,
    #     qcheck=5,
    #     fromdate=fromdate,
    #     todate=todate,
    #     config=futures_config if args.futures else {}
    # )

    # # Add the resample data instead of the original
    # cerebro.replaydata(dataname=data, timeframe=bt.TimeFrame.Minutes, compression=15, boundoff=1, rightedge=False)

    # Add a simple moving average if requested
    # cerebro.addindicator(btind.SMA, period=args.period)

    # Add a writer with CSV
    if args.writer:
        cerebro.addwriter(bt.WriterFile, csv=args.wrcsv)

    # Run over everything
    cerebro.run()

    # Plot if requested
    if args.plot:
        cerebro.plot(scheme=btschemes.TradingViewPlotScheme(), style="candle", numfigs=args.numfigs, volume=False)


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter, description="Calendar Days Filter Sample")

    parser.add_argument("--data", "-d", default="BTCUSDT", help="Ticker to download from Bitget")

    parser.add_argument(
        "--fromdate",
        "-f",
        default=(datetime.datetime.now() - datetime.timedelta(days=10)).strftime("%Y-%m-%d"),
        help="Starting date in YYYY-MM-DD format",
    )

    parser.add_argument("--todate", "-t", default=None, help="Starting date in YYYY-MM-DD format")

    parser.add_argument("--period", default=15, type=int, help="Period to apply to the Simple Moving Average")

    parser.add_argument("--writer", "-w", action="store_true", help="Add a writer to cerebro")

    parser.add_argument("--wrcsv", "-wc", action="store_true", help="Enable CSV Output in the writer")

    parser.add_argument("--csv", action="store_true", help="Specify if store the fetched data into CSV")

    parser.add_argument("--futures", action="store_true", help="Specify if use futures chart")

    parser.add_argument("--plot", "-p", action="store_true", help="Plot the read data")

    parser.add_argument("--numfigs", "-n", default=1, type=int, help="Plot using numfigs figures")

    return parser.parse_args()


if __name__ == "__main__":
    runstrat()
