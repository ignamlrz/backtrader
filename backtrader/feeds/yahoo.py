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

import collections
from datetime import datetime, timedelta
import io
import itertools

from ..utils.py3 import urlopen, urlquote, ProxyHandler, build_opener, install_opener

import backtrader as bt
from .. import feed
from ..utils import date2num


class YahooFinanceCSVData(feed.CSVDataBase):
    """
    Parses pre-downloaded Yahoo CSV Data Feeds (or locally generated if they
    comply to the Yahoo format)

    Specific parameters:

      - ``dataname``: The filename to parse or a file-like object

      - ``reverse`` (default: ``False``)

        It is assumed that locally stored files have already been reversed
        during the download process

      - ``adjclose`` (default: ``True``)

        Whether to use the dividend/split adjusted close and adjust all
        values according to it.

      - ``adjvolume`` (default: ``True``)

        Do also adjust ``volume`` if ``adjclose`` is also ``True``

      - ``round`` (default: ``True``)

        Whether to round the values to a specific number of decimals after
        having adjusted the close

      - ``roundvolume`` (default: ``0``)

        Round the resulting volume to the given number of decimals after having
        adjusted it

      - ``decimals`` (default: ``2``)

        Number of decimals to round to

      - ``swapcloses`` (default: ``False``)

        [2018-11-16] It would seem that the order of *close* and *adjusted
        close* is now fixed. The parameter is retained, in case the need to
        swap the columns again arose.

    """

    lines = ("adjclose",)

    params = (
        ("reverse", False),
        ("adjclose", True),
        ("adjvolume", True),
        ("round", True),
        ("decimals", 2),
        ("roundvolume", False),
        ("swapcloses", False),
    )

    def start(self):
        super(YahooFinanceCSVData, self).start()

        if not self.params.reverse:
            return

        # Yahoo sends data in reverse order and the file is still unreversed
        dq = collections.deque()
        for line in self.f:
            dq.appendleft(line)

        f = io.StringIO(newline=None)
        f.writelines(dq)
        f.seek(0)
        self.f.close()
        self.f = f

    def _loadline(self, linetokens):
        while True:
            nullseen = False
            for tok in linetokens[1:]:
                if tok == "null":
                    nullseen = True
                    linetokens = self._getnextline()  # refetch tokens
                    if not linetokens:
                        return False  # cannot fetch, go away

                    # out of for to carry on wiwth while True logic
                    break

            if not nullseen:
                break  # can proceed

        i = itertools.count(0)

        dttxt = linetokens[next(i)]
        dt = datetime.fromisoformat(dttxt)
        dtnum = date2num(dt)

        self.lines.datetime[0] = dtnum
        self.lines.open[0] = float(linetokens[next(i)])
        self.lines.high[0] = float(linetokens[next(i)])
        self.lines.low[0] = float(linetokens[next(i)])
        self.lines.close[0] = float(linetokens[next(i)])

        try:
            self.lines.volume[0] = float(linetokens[next(i)])
        except:  # cover the case in which volume is "null"
            self.lines.volume[0] = 0.0

        # Open Interest index
        oi_index = next(i)
        if oi_index < len(linetokens):
            self.lines.openinterest[0] = float(linetokens[oi_index]) if linetokens[oi_index] else 0
        else:
            self.lines.openinterest[0] = 0

        return True


class YahooLegacyCSV(YahooFinanceCSVData):
    """
    This is intended to load files which were downloaded before Yahoo
    discontinued the original service in May-2017

    """

    params = (("version", ""),)


class YahooFinanceCSV(feed.CSVFeedBase):
    DataCls = YahooFinanceCSVData


class YahooFinanceData(YahooFinanceCSVData):
    """
    Executes a direct download of data from Yahoo servers for the given time
    range.

    Specific parameters (or specific meaning):

    - ``dataname``

        The ticker to download ('YHOO' for Yahoo own stock quotes)

    - ``fromdate``

        Starting date for the download

    - ``todate``

        Ending date for the download

    - ``timeframe``

        Timeframe to download

    - ``compression``

        Compression to download
    """

    # Allowed granularities by Yahoo Finance: 1m,2m,5m,15m,30m,60m,90m,1h,1d,5d,1wk,1mo,3mo
    GRANULARITIES = {
        (bt.TimeFrame.Minutes, 1): "1m",
        (bt.TimeFrame.Minutes, 2): "2m",
        (bt.TimeFrame.Minutes, 5): "5m",
        (bt.TimeFrame.Minutes, 15): "15m",
        (bt.TimeFrame.Minutes, 30): "30m",
        (bt.TimeFrame.Minutes, 60): "1h",
        (bt.TimeFrame.Minutes, 90): "90m",
        (bt.TimeFrame.Days, 1): "1d",
        (bt.TimeFrame.Days, 5): "5d",
        (bt.TimeFrame.Weeks, 1): "1wk",
        (bt.TimeFrame.Months, 1): "1mo",
        (bt.TimeFrame.Months, 3): "3mo",
        (bt.TimeFrame.Months, 6): "6mo",
        (bt.TimeFrame.Years, 1): "1y",
        (bt.TimeFrame.Years, 2): "2y",
        (bt.TimeFrame.Years, 5): "5y",
        (bt.TimeFrame.Years, 10): "10y",
        (bt.TimeFrame.Years, None): "ytd",
    }

    def start_yfinance(self):
        try:
            import yfinance as yf
            import pandas as pd
        except ImportError as exc:
            msg = (
                "The new Yahoo data feed requires to have the yfinance "
                "module installed. Please use pip install yfinance or "
                "the method of your choice"
            )
            raise ImportError(msg) from exc

        ticker = yf.Ticker(self.p.dataname)
        interval = self.GRANULARITIES.get((self.p.timeframe, self.p.compression))
        # Check if the interval is supported by Yahoo Finance
        if interval not in ticker.history_metadata["validRanges"]:
            self.error = "Unsupported timeframe/compression combination"
            raise ValueError("Unsupported timeframe/compression combination")
        else:
            self.error = None
        # Download the data
        history = ticker.history(start=self.p.fromdate, end=self.p.todate, interval=interval)
        tk = ticker if ticker.history_metadata.get("instrumentType", None) != "CRYPTOCURRENCY" else yf.Ticker(ticker.ticker.split("-")[0])
        # Create Open Interest column right to volume
        history.insert(loc=history.columns.get_loc("Volume") + 1, column="OI", value=None)
        if tk.options and (
            not self.p.todate or self.p.todate > (datetime.today() - bt.TimeFrame.timedelta(self.p.timeframe, self.p.compression))
        ):
            # Get options for each expiration
            options = pd.DataFrame()
            for e in tk.options:
                opt = tk.option_chain(e)
                calls = opt.calls
                calls["CALL"] = True
                puts = opt.puts
                puts["CALL"] = False
                opt = pd.concat([calls, puts], ignore_index=True)
                opt["expirationDate"] = e
                options = pd.concat([options, opt], ignore_index=True)

            # Bizarre error in yfinance that gives the wrong expiration date
            # Add 1 day to get the correct expiration date
            options["expirationDate"] = pd.to_datetime(options["expirationDate"]) + timedelta(days=1)
            options["dte"] = (options["expirationDate"] - datetime.today()).dt.days / 365

            options[["bid", "ask", "strike"]] = options[["bid", "ask", "strike"]].apply(pd.to_numeric)
            options["mark"] = (options["bid"] + options["ask"]) / 2  # Calculate the midpoint of the bid-ask

            # Drop unnecessary and meaningless columns
            options = options.drop(columns=["contractSize", "currency", "change", "percentChange", "lastTradeDate", "lastPrice"])
            # Calculate the total open interest
            oi = options["openInterest"].fillna(0).sum().item()
            history.loc[history.index[-1], "OI"] = oi  # Set OI value only in the last row
        # Drop rows with missing values
        self.f = io.StringIO(history.to_csv())

    def start(self):
        self.start_yfinance()

        # Prepared a "path" file -  CSV Parser can take over
        super(YahooFinanceData, self).start()


class YahooFinance(feed.CSVFeedBase):
    DataCls = YahooFinanceData

    params = DataCls.params._gettuple()


class YahooLiveData(feed.GenericOhlcviLiveData):
    def get_store(self):
        """Returns this data as a store"""
        return self
    
    def notify_live_data(self, data):
        """Notify the live data"""

    def start_data(self, data):
        """Starts the data feed"""

    def get_currency(self, data):
        """Returns the currency of the data feed"""
        try:
            import yfinance as yf
        except ImportError as exc:
            msg = (
                "The new Yahoo data feed requires to have the yfinance "
                "module installed. Please use pip install yfinance or "
                "the method of your choice"
            )
            raise ImportError(msg) from exc
        if self.contractdetails is None:
            self.contractdetails = yf.Ticker(data.p.dataname)
        return self.contractdetails

    def get_granularity(self, data):
        """Returns the granularity of the data feed"""
        interval = YahooFinanceData.GRANULARITIES.get((data.p.timeframe, data.p.compression))
        # Check if the interval is supported by Yahoo Finance
        if interval not in self.get_currency(data).history_metadata["validRanges"]:
            return None
        else:
            return interval

    def fetch_ohlcvi(self, data, since, until, interval):
        """Fetches the OHLCVI data from Yahoo Finance"""
        return self.get_currency(data).history(start=since, end=until, interval=interval)
