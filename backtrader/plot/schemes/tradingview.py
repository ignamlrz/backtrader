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
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from ..plot import PlotScheme

class TradingViewPlotScheme(PlotScheme):
    def __init__(self):
        import matplotlib.pyplot as plt
        # Configuración global de matplotlib
        # plt.yscale("log")
        plt.style.use("dark_background")
        plt.rcParams.update(
            {   
                "axes.facecolor": "#131722",  # Fondo general oscuro
                "axes.edgecolor": "#333333",  # Bordes de los gráficos
                "grid.color": "#444444",  # Color del grid (gris oscuro)
                "grid.linestyle": "--",  # Líneas del grid punteadas
                "grid.linewidth": 0.2,  # Grosor del grid
                "xtick.color": "#888888",  # Color de los ejes X
                "ytick.color": "#888888",  # Color de los ejes Y
                "text.color": "#444444",  # Color del texto
                "axes.labelcolor": "#222222",  # Color para etiquetas (gris oscuro)
                "axes.titlecolor": "#222222",  # Color para títulos (gris oscuro)
            }
        )
        super().__init__()

        # General appearance
        self.grid = True

        # Dark mode colors
        self.style = "candle"  # Use candlestick style
        self.loc = "white"  # Line on close
        self.barup = "#26a69a"  # Bullish candle color (greenish)
        self.bardown = "#ef5350"  # Bearish candle color (red)
        self.barupfill = True
        self.bardownfill = True
        self.fillalpha = 0.3  # Strong fill transparency

        # Volume overlay
        self.volume = True
        self.voloverlay = True
        self.volup = "#9ccc65"  # Bullish volume color
        self.voldown = "#ff7043"  # Bearish volume color
        self.voltrans = 0.7  # Transparency for volume

        # Default colors for lines
        self.lcolors = ["#f44336", "#2196f3", "#ffeb3b", "#9c27b0", "#4caf50"]

        self.fmt_x_data = "%a, %Y-%m-%d %H:%M:%S"  # Format: yyyy-mm-dd hh:mm:ss

    def color(self, idx):
        """Override to customize line colors."""
        custom_colors = ["#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0", "#9966FF"]
        return custom_colors[idx % len(custom_colors)]
