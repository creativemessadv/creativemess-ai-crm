from typing import Optional

import numpy as np
import pandas as pd

from .base import Signal, Side, Strategy


def rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


class MeanReversionRSI(Strategy):
    name = "mean_reversion_rsi"

    def __init__(
        self,
        rsi_period: int = 14,
        rsi_oversold: float = 30.0,
        rsi_overbought: float = 70.0,
        take_profit_pct: float = 0.0015,
        stop_loss_pct: float = 0.0010,
    ):
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct

    def warmup(self) -> int:
        return self.rsi_period + 2

    def on_bar(self, window: pd.DataFrame) -> Optional[Signal]:
        if len(window) < self.warmup():
            return None
        r = rsi(window["close"], self.rsi_period).iloc[-1]
        if np.isnan(r):
            return None
        if r < self.rsi_oversold:
            return Signal(
                side=Side.LONG,
                take_profit_pct=self.take_profit_pct,
                stop_loss_pct=self.stop_loss_pct,
                reason=f"RSI={r:.1f} < {self.rsi_oversold}",
            )
        if r > self.rsi_overbought:
            return Signal(
                side=Side.SHORT,
                take_profit_pct=self.take_profit_pct,
                stop_loss_pct=self.stop_loss_pct,
                reason=f"RSI={r:.1f} > {self.rsi_overbought}",
            )
        return None
