"""Live Data Feed"""

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

from collections import deque
from datetime import datetime, timedelta
from abc import abstractmethod

from .. import TimeFrame
from .. import feed
from ..utils import date2num, num2date, timestamp2date


class State(object):
    """State enumeration for the live data feed"""

    (Init, Start, Live, Historback, Over, Conencted, Disconnected) = range(1, 6)

    Names = ["", "Init", "Start", "Live", "Historback", "Over", "Connected", "Disconnected"]

    names = Names  # support old naming convention


class GenericOhlcviLiveData(feed.DataBase):
    """Abstract class OHLCVI Live Data Feed.
    The data feed will fetch the historical data and then switch to live data
    if the ``historical`` parameter is set to ``False``.

        Methods to implement:

        - ``get_store()``: Return the store to be used

        - ``notify_live_data(data)``: Called when new live data is received


        Params:
            Default params of DataBase plus:
            
            - ``limit`` (default: ``50``)

            The maximum number of data points to fetch in a single request.

            - ``historical`` (default: ``False``)

            If set to ``True`` the data feed will stop after doing the first
            download of data.

            The standard data feed parameters ``fromdate`` and ``todate`` will be
            used as reference.

            The data feed will make multiple requests if the requested duration is
            larger than the one allowed by the store given the timeframe/compression
            chosen for the data.

            - ``backfill_start`` (default: ``True``)

            Perform backfilling at the start. The maximum possible historical data
            will be fetched in a single request.

        Store: 
            The store to be used to fetch the data. The store must implement the
            following methods:

            - ``start_data(data)``: Start the data feed and get the queue to wait on

            - ``get_granularity(data)``: Get the granularity of the data

            - ``get_currency(data)``: Get the currency of the data

            - ``fetch_ohlcvi(data, since, until, limit)``: Fetch the OHLCVI data
    """

    params = (
        ("limit", 50),  # limit of data to fetch
        ("historical", False),  # do backfilling at the start
        ("backfill_start", True),  # do backfilling at the start
    )

    state = State.Init
    store = None

    def islive(self):
        """If returns ``True``, it notify ``Cerebro`` that preloading and runonce
        should be deactivated"""
        return not self.p.historical

    def setenvironment(self, env):
        """Receives an environment (cerebro) and passes it over to the store it
        belongs to"""
        super(GenericOhlcviLiveData, self).setenvironment(env)
        env.addstore(self.get_store())

    def __init__(self, **kwargs):
        super(GenericOhlcviLiveData, self).__init__(**kwargs)

        # Create attributes as soon as possible
        self._data = deque()
        self.granularity = None
        self.contractdetails = None

    def start(self):
        """Starts the OHLCVI connecction and gets the real contract and
        contractdetails if it exists"""
        super(GenericOhlcviLiveData, self).start()

        self.state = State.Over
        self.store = self.get_store()

        # Kickstart store and get queue to wait on
        self.store.start_data(data=self)

        # check if the granularity is supported
        if self.p.timeframe == TimeFrame.Ticks or self.p.timeframe == TimeFrame.NoTimeFrame:
            self.put_notification(self.NOTSUPPORTED_TF)
            self.state = State.Over
            return
        self.granularity = granularity = self.store.get_granularity(data=self)
        if granularity is None:
            self.put_notification(self.NOTSUPPORTED_TF)
            self.state = State.Over
            return

        self.contractdetails = cd = self.store.get_currency(data=self)
        if cd is None:
            self.put_notification(self.NOTSUBSCRIBED)
            self.state = State.Over
            return

        self._start_finish()

    def _start_finish(self):
        super(GenericOhlcviLiveData, self)._start_finish()
        self.state = State.Start
        if self.p.historical:
            self.state = State.Historback
        self.put_notification(self.DELAYED)
        self._fetch_history()
        return True

    def _fetch_history(self):
        dtend = datetime.now()
        if not self.p.backfill_start and self.todate < float("inf"):
            dtend = num2date(self.todate)

        dtbegin = None
        if self.fromdate > float("-inf"):
            dtbegin = num2date(self.fromdate)

        _last_dt0 = dtbegin
        while True:
            _request = dict(data=self, since=_last_dt0, until=dtend, limit=self.p.limit)
            _data0 = self.store.fetch_ohlcvi(**_request)
            if len(_data0) == 0:
                break
            if _last_dt0 is None:
                _last_dt0 = timestamp2date(_data0[0][0])
            _last_dt1 = timestamp2date(_data0[-1][0])
            if _last_dt0 >= dtend or _last_dt0 == _last_dt1:
                break
            else:
                self._data.extend(_data0)
                _last_dt0 = _last_dt1 + timedelta(milliseconds=1)

    def _load(self):
        if self.state == State.Over:
            return False

        while True:
            if self.state == State.Live:
                self._fetch_history()
                exists = self._load_history()
                if exists:
                    self.notify_live_data(self.lines[0])
                return exists

            elif self.state == State.Historback:
                exists = self._load_history()
                if exists:
                    return exists
                else:
                    # End of historical data
                    if self.p.historical:  # only historical
                        self.state = State.Over
                        self.put_notification(self.DISCONNECTED)
                        return False  # end of historical
                    else:
                        self.state = State.Live
                        self.put_notification(self.LIVE)
                        continue

    def _load_history(self):
        try:
            ohlcvi = self._data.popleft()
        except IndexError:
            return None  # no data in the queue
        tstamp, open_, high, low, close, volume, open_interest = ohlcvi
        tstamp = timestamp2date(tstamp)
        dt = date2num(tstamp)
        if dt <= self.lines.datetime[-1]:
            return False  # time already seen

        self.lines.datetime[0] = dt
        self.lines.open[0] = open_
        self.lines.high[0] = high
        self.lines.low[0] = low
        self.lines.close[0] = close
        self.lines.volume[0] = volume
        self.lines.openinterest[0] = open_interest

        return True

    def haslivedata(self):
        return bool(self.state == State.Live and self._data)

    @abstractmethod
    def get_store(self):
        """Return the store to be used"""
        raise NotImplementedError

    @abstractmethod
    def notify_live_data(self, data):
        """Called when live data is received"""
