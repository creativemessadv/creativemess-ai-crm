from dataclasses import dataclass


@dataclass
class RiskLimits:
    risk_per_trade_pct: float = 0.005
    max_concurrent_positions: int = 3
    max_daily_loss_pct: float = 0.02
    max_daily_trades: int = 1000


class RiskManager:
    """Stateful daily risk tracker. The backtester resets it at the start
    of every UTC day.
    """

    def __init__(self, limits: RiskLimits, starting_equity: float):
        self.limits = limits
        self.day_start_equity = starting_equity
        self.daily_realized_pnl = 0.0
        self.daily_trade_count = 0

    def reset_day(self, equity: float) -> None:
        self.day_start_equity = equity
        self.daily_realized_pnl = 0.0
        self.daily_trade_count = 0

    def record_trade(self, pnl: float) -> None:
        self.daily_realized_pnl += pnl
        self.daily_trade_count += 1

    def can_open(self, open_positions: int) -> bool:
        if self.daily_trade_count >= self.limits.max_daily_trades:
            return False
        if open_positions >= self.limits.max_concurrent_positions:
            return False
        loss_limit = -self.limits.max_daily_loss_pct * self.day_start_equity
        if self.daily_realized_pnl <= loss_limit:
            return False
        return True

    def position_size(self, equity: float, entry_price: float, stop_loss_pct: float) -> float:
        if stop_loss_pct <= 0 or entry_price <= 0:
            return 0.0
        risk_eur = equity * self.limits.risk_per_trade_pct
        loss_per_unit = entry_price * stop_loss_pct
        return max(risk_eur / loss_per_unit, 0.0)
