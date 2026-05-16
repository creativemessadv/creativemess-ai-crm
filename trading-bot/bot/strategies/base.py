from dataclasses import dataclass
from enum import Enum
from typing import Optional

import pandas as pd


class Side(str, Enum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


@dataclass
class Signal:
    side: Side
    take_profit_pct: float
    stop_loss_pct: float
    reason: str = ""


class Strategy:
    """Base interface. A strategy looks at a window of bars ending at `t`
    and decides whether to open a new position. Exits are managed by the
    backtester via TP/SL embedded in the signal.
    """

    name: str = "base"

    def warmup(self) -> int:
        return 0

    def on_bar(self, window: pd.DataFrame) -> Optional[Signal]:
        raise NotImplementedError
