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

from datetime import datetime
from abc import abstractmethod
from typing import Final, List, Union, final

from .. import MetaParams, Position, Order
from ..feed import DataBase
from ..utils.py3 import queue, with_metaclass


class StoreBase(with_metaclass(MetaParams, object)):
    """
    Abstract base class for creating Backtrader stores.
    Specific implementations should extend this class and define the abstract methods.
    """

    def __init__(self):
        self._notifs: Final[queue.Queue] = queue.Queue()  # store notifications for cerebro

    @abstractmethod
    def start(self):
        """notify that the store will start"""

    @abstractmethod
    def stop(self):
        """notify to stop the store"""

    @abstractmethod
    def start_data(self, data: DataBase) -> str:
        """notify that the store will start with this data"""

    @abstractmethod
    def get_granularity(self, data: DataBase) -> str:
        """get granularity"""
        raise NotImplementedError

    @abstractmethod
    def get_currency(self, data: DataBase) -> str:
        """get base currency"""
        raise NotImplementedError

    @abstractmethod
    def fetch_server_time(self) -> datetime:
        """Server time"""
        raise NotImplementedError

    @abstractmethod
    def fetch_acc_value(self) -> float:
        """Returns the net liquidation value
        """
        raise NotImplementedError

    @abstractmethod
    def fetch_acc_cash(self) -> float:
        """
        Returns the total cash value
        """
        raise NotImplementedError

    @abstractmethod
    def fetch_positions(self) -> list[Position]:
        """Return all open positions
        """
        raise NotImplementedError

    @abstractmethod
    def fetch_open_orders(self) -> list[Order]:
        """Return a list of open orders
        """
        raise NotImplementedError

    @abstractmethod
    def fetch_closed_orders(self, fromdate) -> list[Order]:
        """Return a list of closed orders
        """
        raise NotImplementedError

    @abstractmethod
    def fetch_order(self, identifier: Union[str, int]) -> Order:
        """Retrun the order specified"""
        raise NotImplementedError

    @abstractmethod
    def create_order(self, order: Order) -> Order:
        """Create a new order"""
        raise NotImplementedError

    @abstractmethod
    def update_order(self, order: Order) -> Order:
        """Update the order"""
        raise NotImplementedError

    @abstractmethod
    def cancel_order(self, order: Order) -> Order:
        """Cancel the order"""
        raise NotImplementedError

    @abstractmethod
    def fetch_ohlcvi(self, data: DataBase, since: datetime, until: datetime, limit: int) -> list:
        """Fetch ohlcv data

        Should return a list of data, where data is an array with properties sorted in with
        this ordenation:
        - ``timestamp``
        - ``open``
        - ``high``
        - ``low``
        - ``close``
        - ``volume``
        - ``openinterest``
        """
        raise NotImplementedError

    @final
    def put_notification(self, notification):
        """Add a "store" notification"""
        self._notifs.put(notification)

    @final
    def get_notifications(self) -> List[tuple[any, any]]:
        """Return the pending "store" notifications"""
        # The background thread could keep on adding notifications. The None
        # mark allows to identify which is the last notification to deliver
        self._notifs.put(None)  # put a mark
        notifs = list()
        while True:
            notif = self._notifs.get()
            if notif is None:  # mark is reached
                break
            notifs.append(notif)

        return notifs
