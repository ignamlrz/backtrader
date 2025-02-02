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
from datetime import timezone, datetime, timedelta
from abc import abstractmethod
import time
import os
import pandas as pd
import numpy as np

from .. import TimeFrame
from .. import feed
from ..utils import date2num, num2date, timestamp2date

import platform

# Define la ruta basada en la plataforma
if platform.system().lower() == "windows":
    DEFAULT_CSV_PATH = "C:/opt/backtrader"
elif platform.system().lower() in ["linux", "darwin"]:  # Darwin es para macOS
    DEFAULT_CSV_PATH = "/opt/backtrader"
else:
    raise EnvironmentError(f"Unsupported platform: {platform.system().lower()}")


class State(object):
    """State enumeration for the live data feed"""

    (Init, Start, Live, Historback, Over, Conencted, Disconnected) = range(1, 8)

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

            - ``qcheck`` (default: ``0.5``)

            Delay between queries in seconds

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

            - ``csv`` (default: ``False``)

            Specify if save/load into/from a CSV the fetched data, stored by months. Only apply if historical
            data is enabled too

            - ``csv_basepath`` (default: None)

            Specify where to save/load the csv data. If not is specified a folder name data will be on
            C:/opt/backtrader or /opt/backtrader, depending on the platform

        Store:
            The store to be used to fetch the data. The store must implement the
            following methods:

            - ``start_data(data)``: Start the data feed and get the queue to wait on

            - ``get_granularity(data)``: Get the granularity of the data

            - ``get_currency(data)``: Get the currency of the data

            - ``fetch_ohlcvi(data, since, until, limit)``: Fetch the OHLCVI data
    """

    params = (
        ("qcheck", 0.5),  # timeout in seconds (float) to check for events
        ("limit", 50),  # limit of data to fetch
        ("historical", False),  # do backfilling at the start
        ("backfill_start", True),  # do backfilling at the start
        ("csv", False),  # Specify if save into a CSV the fetched data. Store by months
        ("csv_basepath", None),
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
        # Ensure default qcheck is 0.5
        self.p.qcheck = 0.5 if not self.p.qcheck else self.p.qcheck
        self.granularity = None
        self.contractdetails = None
        self._csv_filepath = None

    def start(self):
        """Starts the OHLCVI connecction and gets the real contract and
        contractdetails if it exists"""
        if self.state != State.Init:
            return
        super(GenericOhlcviLiveData, self).start()

        self.store = self.get_store()

        # Kickstart store and get queue to wait on
        self.store.start_data(data=self)

        # get the contract details
        self.contractdetails = cd = self.store.get_currency(data=self)
        if cd is None:
            self.put_notification(self.NOTSUBSCRIBED)
            self.state = State.Over
            return

        # check if the granularity is supported
        if self.p.timeframe == TimeFrame.Ticks or self.p.timeframe == TimeFrame.NoTimeFrame:
            print("Timeframe not supported")
            self.state = State.Over
            self.put_notification(self.NOTSUPPORTED_TF)
            return
        self.granularity = granularity = self.store.get_granularity(data=self)
        if granularity is None:
            print("Granularity not supported")
            self.state = State.Over
            self.put_notification(self.NOTSUPPORTED_TF)
            return

        if self.p.historical and self.p.csv:
            root_filepath = self.p.csv_basepath if self.p.csv_basepath else DEFAULT_CSV_PATH
            class_name = type(self).__name__
            symbol_name = self.p.dataname.replace(":", "_").replace("/", "-") # Sanitize
            self._csv_filepath = os.path.join(root_filepath, class_name, symbol_name, granularity)

        self._start_finish()

    def _start_finish(self):
        if self.state != State.Init:
            return
        super(GenericOhlcviLiveData, self)._start_finish()
        self.state = State.Start
        if self.p.historical:
            self.state = State.Historback
        self.put_notification(self.DELAYED)
        self._fetch_history()
        return True

    def _fetch_history(self):
        dtend = current_dt = self.store.fetch_server_time()
        if self.p.backfill_start and self.todate < float("inf"):
            dtend = num2date(self.todate)

        dtbegin = num2date(self.lines.datetime[-1]) if len(self.lines) > 1 else None
        if not dtbegin and self.fromdate > float("-inf"):
            dtbegin = num2date(self.fromdate)

        dtbegin = dtbegin.astimezone(tz=timezone.utc)
        dtend = dtend.astimezone(tz=timezone.utc)
        _last_dt0 = dtbegin - timedelta(milliseconds=1)
        while True:
            _last_dt1 = _last_dt0 + (TimeFrame.timedelta(self.p.timeframe, self.p.compression) * (self.p.limit - 2))
            _last_dt0 = _last_dt0 + timedelta(milliseconds=1) # avoid repeat previous _last_dt1 data
            _data_csv0, _path0 = self._exists_data_csv(fromdate=_last_dt0, endate=dtend)
            if _data_csv0:
                # Read data from csv
                _datares = _data_csv0
            elif _path0:
                # Not exists, but allowed to download all month data to csv
                self._download_into_csv(_last_dt0, _path0)
                _datares = self._read_from_csv(fromdate=_last_dt0, endate=dtend, path=_path0)
            else:
                _request = dict(data=self, since=_last_dt0, until=_last_dt1, limit=self.p.limit)
                _datares = self.store.fetch_ohlcvi(**_request)
            if len(_datares) == 0:
                break
            _last_dt0 = timestamp2date(_datares[0][0]).astimezone(tz=timezone.utc)
            _last_dt1 = timestamp2date(_datares[-1][0]).astimezone(tz=timezone.utc)
            if _last_dt0 >= dtend or _last_dt0 == _last_dt1:
                break
            else:
                self._data.extend(_datares)
                _last_dt0 = _last_dt1

        # Remove data that is not open yet
        if len(self._data) > 0:
            next_dt = timestamp2date(self._data[-1][0]) + TimeFrame.timedelta(self.p.timeframe, self.p.compression)
            if current_dt < next_dt:
                self._data.pop()

    def _load(self):
        if self.state == State.Live and self._qcheck:
            time.sleep(self._qcheck)
        if self.state == State.Over:
            return False

        while True:
            if self.state == State.Live:
                self._fetch_history()
                exists = self._load_history()
                if exists:
                    self.notify_live_data(self.lines[0])
                return exists

            else:
                exists = self._load_history()
                if len(self._data) == 0:
                    # End of historical data
                    if self.p.historical:  # only historical
                        self.state = State.Over
                        self.put_notification(self.DISCONNECTED)
                    else:
                        self.state = State.Live
                        self.put_notification(self.LIVE)
                if exists:
                    return exists

    def _load_history(self):
        try:
            ohlcvi = self._data.popleft()
        except IndexError:
            return None  # no data in the queue
        tstamp, open_, high, low, close, volume, open_interest = ohlcvi
        tstamp = timestamp2date(tstamp)
        dt = date2num(tstamp)
        if dt <= self.lines.datetime[-1]:
            return None  # time already seen

        self.lines.datetime[0] = dt
        self.lines.open[0] = float(open_)
        self.lines.high[0] = float(high)
        self.lines.low[0] = float(low)
        self.lines.close[0] = float(close)
        self.lines.volume[0] = float(volume)
        self.lines.openinterest[0] = float(open_interest)

        return True

    def _exists_data_csv(self, fromdate, endate):
        if not self._csv_filepath:
            return False, None
        target_date = str(fromdate.date())[:-3]
        current_date = str(datetime.today().date())[:-3]
        if target_date == current_date:
            return False, None
        path = os.path.join(self._csv_filepath, target_date + ".csv")
        if not os.path.exists(path=path):
            return False, path # Specify that should be loaded
        result = self._read_from_csv(fromdate=fromdate, endate=endate, path=path)
        if not result:
            return False, None
        return result, path

    def _download_into_csv(self, fromdate, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        dtbegin = datetime.combine(fromdate.date().replace(day=1), datetime.min.time())
        dtbegin = dtbegin.replace(tzinfo=timezone.utc)
        dtend = datetime.combine((dtbegin + timedelta(days=datetime.max.day + 1)).replace(day=1), datetime.min.time())
        dtend = dtend.replace(tzinfo=timezone.utc)
        result = deque()
        _last_dt0 = dtbegin - timedelta(milliseconds=1)
        _timedelta = TimeFrame.timedelta(self.p.timeframe, self.p.compression)
        while True:
            _next_timedelta = _timedelta * (self.p.limit - 2)
            _last_dt1 = min(_last_dt0 + _next_timedelta, dtend)
            _request = dict(data=self, since=_last_dt0 + timedelta(milliseconds=1), until=_last_dt1, limit=self.p.limit)
            _datares = self.store.fetch_ohlcvi(**_request)
            if len(_datares) == 0:
                break
            _last_dt0 = timestamp2date(_datares[0][0]).astimezone(tz=timezone.utc)
            _last_dt1 = timestamp2date(_datares[-1][0]).astimezone(tz=timezone.utc)
            if _last_dt0 >= dtend or _last_dt0 == _last_dt1:
                break
            else:
                result.extend(_datares)
                _last_dt0 = _last_dt1
        # Convert deque to DataFrame and save
        columns = ["datetime", "open", "high", "low", "close", "volume", "openinterest"]
        df = pd.DataFrame(list(result), columns=columns)
        df["datetime"] = pd.to_datetime(df["datetime"], unit="ms")
        df.to_csv(path, index=False)

    def _read_from_csv(self, fromdate, endate, path):
        df = pd.read_csv(path, parse_dates=["datetime"])
        if not fromdate:
            fromdate = np.datetime64(df.iloc[0]["datetime"])
        if not endate:
            endate = np.datetime64(df.iloc[-1]["datetime"])
        fromdate = pd.to_datetime(fromdate).tz_convert(timezone.utc)
        endate = pd.to_datetime(endate).tz_convert(timezone.utc)
        df["datetime"] = pd.to_datetime(df["datetime"]).dt.tz_localize(timezone.utc)
        filtered_df = df[(df["datetime"] >= fromdate) & (df["datetime"] <= endate)]
        filtered_df.set_index("datetime", inplace=True)
        result = filtered_df.to_records(index=True)
        # Convert the records timestamp to milliseconds
        for r in result:
            r[0] = r[0].value
        return [(r[0], float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5]), float(r[6])) for r in result]

    def haslivedata(self):
        return bool(self.state == State.Live and self._data)

    @abstractmethod
    def get_store(self):
        """Return the store to be used"""
        raise NotImplementedError

    @abstractmethod
    def notify_live_data(self, data):
        """Called when live data is received"""
