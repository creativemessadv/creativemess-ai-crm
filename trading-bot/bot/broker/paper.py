from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd

from ..strategies.base import Side


@dataclass
class Position:
    side: Side
    qty: float
    entry_price: float
    take_profit: float
    stop_loss: float
    opened_at: pd.Timestamp
    reason: str = ""


@dataclass
class ClosedTrade:
    side: Side
    qty: float
    entry_price: float
    exit_price: float
    opened_at: pd.Timestamp
    closed_at: pd.Timestamp
    pnl: float
    fees: float
    exit_reason: str


@dataclass
class PaperBroker:
    """Minimal paper-trading broker for backtests. Fills market orders at
    the bar's open price plus configurable slippage. TP/SL checked
    intra-bar against bar high/low. If both hit in the same bar we
    pessimistically assume the stop fires first.
    """

    fee_pct: float = 0.00075
    slippage_pct: float = 0.0002
    positions: List[Position] = field(default_factory=list)
    trades: List[ClosedTrade] = field(default_factory=list)

    def open(
        self,
        side: Side,
        qty: float,
        bar_open: float,
        take_profit_pct: float,
        stop_loss_pct: float,
        bar_time: pd.Timestamp,
        reason: str = "",
    ) -> Optional[Position]:
        if qty <= 0 or side == Side.FLAT:
            return None
        slip = 1 + self.slippage_pct if side == Side.LONG else 1 - self.slippage_pct
        fill = bar_open * slip
        if side == Side.LONG:
            tp = fill * (1 + take_profit_pct)
            sl = fill * (1 - stop_loss_pct)
        else:
            tp = fill * (1 - take_profit_pct)
            sl = fill * (1 + stop_loss_pct)
        pos = Position(
            side=side,
            qty=qty,
            entry_price=fill,
            take_profit=tp,
            stop_loss=sl,
            opened_at=bar_time,
            reason=reason,
        )
        self.positions.append(pos)
        return pos

    def step(self, bar: pd.Series, bar_time: pd.Timestamp) -> List[ClosedTrade]:
        """Check open positions against this bar's high/low and close
        whichever ones hit TP or SL.
        """
        closed: List[ClosedTrade] = []
        still_open: List[Position] = []
        high = float(bar["high"])
        low = float(bar["low"])
        for p in self.positions:
            hit_sl = (p.side == Side.LONG and low <= p.stop_loss) or (
                p.side == Side.SHORT and high >= p.stop_loss
            )
            hit_tp = (p.side == Side.LONG and high >= p.take_profit) or (
                p.side == Side.SHORT and low <= p.take_profit
            )
            exit_price: Optional[float] = None
            reason = ""
            if hit_sl:
                exit_price = p.stop_loss
                reason = "stop_loss"
            elif hit_tp:
                exit_price = p.take_profit
                reason = "take_profit"
            if exit_price is None:
                still_open.append(p)
                continue
            slip = 1 - self.slippage_pct if p.side == Side.LONG else 1 + self.slippage_pct
            fill = exit_price * slip
            gross = (fill - p.entry_price) * p.qty if p.side == Side.LONG else (
                p.entry_price - fill
            ) * p.qty
            fees = (p.entry_price + fill) * p.qty * self.fee_pct
            closed.append(
                ClosedTrade(
                    side=p.side,
                    qty=p.qty,
                    entry_price=p.entry_price,
                    exit_price=fill,
                    opened_at=p.opened_at,
                    closed_at=bar_time,
                    pnl=gross - fees,
                    fees=fees,
                    exit_reason=reason,
                )
            )
        self.positions = still_open
        self.trades.extend(closed)
        return closed
