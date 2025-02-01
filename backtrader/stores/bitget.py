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

import ccxt
from datetime import datetime, timedelta

import backtrader as bt
from ..stores.live import StoreBase


class BitgetStore(StoreBase):
    """
    API provider for bitget CCXT feed and broker classes.

    Added a new get_wallet_balance method. This will allow manual checking of the balance.
        The method will allow setting parameters. Useful for getting margin balances

    Added new private_end_point method to allow using any private non-unified end point
    """

    _GRANULARITIES = {
        (bt.TimeFrame.Minutes, 1): "1m",
        (bt.TimeFrame.Minutes, 3): "3m",
        (bt.TimeFrame.Minutes, 5): "5m",
        (bt.TimeFrame.Minutes, 15): "15m",
        (bt.TimeFrame.Minutes, 30): "30m",
        (bt.TimeFrame.Minutes, 60): "1h",
        (bt.TimeFrame.Minutes, 90): "90m",
        (bt.TimeFrame.Minutes, 120): "2h",
        (bt.TimeFrame.Minutes, 180): "3h",
        (bt.TimeFrame.Minutes, 240): "4h",
        (bt.TimeFrame.Minutes, 360): "6h",
        (bt.TimeFrame.Minutes, 480): "8h",
        (bt.TimeFrame.Minutes, 720): "12h",
        (bt.TimeFrame.Days, 1): "1d",
        (bt.TimeFrame.Days, 3): "3d",
        (bt.TimeFrame.Weeks, 1): "1w",
        (bt.TimeFrame.Weeks, 2): "2w",
        (bt.TimeFrame.Months, 1): "1M",
        (bt.TimeFrame.Months, 3): "3M",
        (bt.TimeFrame.Months, 6): "6M",
        (bt.TimeFrame.Years, 1): "1y",
    }

    def __init__(self, config, *args, **kwargs) -> None:
        super(BitgetStore, self).__init__()
        self.exchange = ccxt.bitget(config=config)
        if "sandbox" in config and config["sandbox"]:
            self.exchange.set_sandbox_mode(True)
        self.exchange.load_markets()
        self.next_fetch = datetime.now() + timedelta(hours=1)

    def get_currency(self, data):
        """Returns the currency of the data feed"""
        if self.next_fetch < datetime.now():
            self.exchange.load_markets()
            self.next_fetch = datetime.now() + timedelta(hours=1)
        try:
            return self.exchange.market(data.p.dataname)
        except Exception as _:
            return None

    def get_granularity(self, data):
        """Returns the granularity of the data feed"""
        return self._GRANULARITIES[(data.p.timeframe, data.p.compression)]

    def fetch_ohlcvi(self, data, since, until, limit):
        """Fetches the OHLCVI data from Bitget exchange"""
        symbol = self.get_currency(data)["id"]
        timeframe = self.get_granularity(data)
        # request_params = dict(paginate=True, maxEntriesPerRequest=limit, paginationCalls=50, paginationDirection="forward")
        request_params = dict(until=self.exchange.parse8601(str(until)), useHistoryEndpoint=True)
        request = dict(since=self.exchange.parse8601(str(since)), params=request_params)
        result = self.exchange.fetch_ohlcv(symbol=symbol, timeframe=timeframe, limit=limit, **request)
        # currently openinterest is not calculated, so add new item with value 0
        result = [(timestamp, o, h, l, c, v, 0) for timestamp, o, h, l, c, v in result]
        return sorted(result, key=lambda x: x[0])
