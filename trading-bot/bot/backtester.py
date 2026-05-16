from dataclasses import dataclass, field
from typing import List

import pandas as pd

from .broker.paper import ClosedTrade, PaperBroker
from .risk import RiskLimits, RiskManager
from .strategies.base import Side, Strategy


@dataclass
class BacktestResult:
    trades: List[ClosedTrade]
    equity_curve: pd.Series
    daily_pnl: pd.Series
    starting_equity: float

    @property
    def total_pnl(self) -> float:
        return float(sum(t.pnl for t in self.trades))

    @property
    def total_fees(self) -> float:
        return float(sum(t.fees for t in self.trades))

    @property
    def win_rate(self) -> float:
        if not self.trades:
            return 0.0
        wins = sum(1 for t in self.trades if t.pnl > 0)
        return wins / len(self.trades)

    @property
    def max_drawdown(self) -> float:
        if self.equity_curve.empty:
            return 0.0
        roll_max = self.equity_curve.cummax()
        dd = (self.equity_curve - roll_max) / roll_max
        return float(dd.min())


def run_backtest(
    df: pd.DataFrame,
    strategy: Strategy,
    starting_equity: float,
    limits: RiskLimits,
    fee_pct: float,
    slippage_pct: float,
) -> BacktestResult:
    if df.empty:
        raise ValueError("Empty dataframe")

    broker = PaperBroker(fee_pct=fee_pct, slippage_pct=slippage_pct)
    risk = RiskManager(limits, starting_equity)
    equity = starting_equity
    equity_points: list[tuple[pd.Timestamp, float]] = []
    daily_pnl: dict[pd.Timestamp, float] = {}

    warmup = max(strategy.warmup(), 1)
    current_day = df.index[0].normalize()

    for i, (ts, bar) in enumerate(df.iterrows()):
        day = ts.normalize()
        if day != current_day:
            risk.reset_day(equity)
            current_day = day

        closed = broker.step(bar, ts)
        for t in closed:
            equity += t.pnl
            risk.record_trade(t.pnl)
            daily_pnl[day] = daily_pnl.get(day, 0.0) + t.pnl

        if i >= warmup and risk.can_open(len(broker.positions)):
            window = df.iloc[max(0, i - warmup - 50) : i + 1]
            signal = strategy.on_bar(window)
            if signal is not None and signal.side != Side.FLAT:
                next_idx = i + 1
                if next_idx < len(df):
                    next_bar = df.iloc[next_idx]
                    qty = risk.position_size(
                        equity, float(next_bar["open"]), signal.stop_loss_pct
                    )
                    if qty > 0:
                        broker.open(
                            side=signal.side,
                            qty=qty,
                            bar_open=float(next_bar["open"]),
                            take_profit_pct=signal.take_profit_pct,
                            stop_loss_pct=signal.stop_loss_pct,
                            bar_time=df.index[next_idx],
                            reason=signal.reason,
                        )

        equity_points.append((ts, equity))

    equity_curve = pd.Series(
        [v for _, v in equity_points],
        index=pd.DatetimeIndex([t for t, _ in equity_points]),
        name="equity",
    )
    daily = pd.Series(daily_pnl, name="daily_pnl").sort_index()
    return BacktestResult(
        trades=broker.trades,
        equity_curve=equity_curve,
        daily_pnl=daily,
        starting_equity=starting_equity,
    )
