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

from ..observer import Observer
from ..order import Order


class Orders(Observer):
    lines = ("created",)

    plotinfo = dict(plot=True, subplot=False, plotlinelabels=True)

    plotlines = dict(
        created=dict(marker="*", markersize=5, color="lime"),
    )

    plotboxes = (
        "profit",
        "loss",
    )

    packages = ("math",)

    params = (
        ("profit_color", "green"),
        ("profit_alpha", 0.2),
        ("loss_color", "red"),
        ("loss_alpha", 0.2),
    )

    def __init__(self):
        self.profit = []
        self.loss = []

    def notify_order(self, order):
        if order.status in [Order.Submitted]:
            order.info["dt"] = len(order.data)
            current_created = max(self.l.created[-1], self.l.created[0], 0)
            current_created = 0 if math.isnan(current_created) else current_created
            self.l.created[0] = current_created + 1
        if order.parent and order.status in [Order.Completed, Order.Canceled, Order.Rejected]:
            x0 = order.parent.info["dt"]
            x1 = len(order.data)
            y0 = order.parent.created.pricelimit or order.parent.created.price or order.parent.created.pclose
            y1 = order.created.pricelimit or order.created.price or order.created.pclose
            box = (x0, x1, y0, y1, order.status == Order.Completed)
            islong = order.parent.isbuy()
            if (islong and y0 < y1) or (not islong and y0 > y1):
                # Is profit
                self.profit.append(box)
            elif (islong and y0 > y1) or (not islong and y0 < y1):
                # Is loss
                self.loss.append(box)
        elif order.parent and order.status in [Order.Canceled, Order.Expired, Order.Margin]:
            print(Order.Status[order.status])

    def next(self):
        pass
