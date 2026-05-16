"""Sanity tests. Run with:  python -m pytest trading-bot/tests"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from bot.backtester import run_backtest
from bot.data import synthetic_ohlcv
from bot.risk import RiskLimits
from bot.strategies import build
from bot.strategies.mean_reversion_rsi import rsi


def test_rsi_bounded():
    s = pd.Series(range(1, 200), dtype=float)
    r = rsi(s, 14).dropna()
    assert ((r >= 0) & (r <= 100)).all()


def test_backtest_runs_and_pays_fees():
    df = synthetic_ohlcv(n_bars=60 * 24 * 3)
    strat = build("mean_reversion_rsi", {"take_profit_pct": 0.002, "stop_loss_pct": 0.001})
    result = run_backtest(
        df,
        strategy=strat,
        starting_equity=10_000.0,
        limits=RiskLimits(max_daily_trades=1000),
        fee_pct=0.00075,
        slippage_pct=0.0002,
    )
    assert len(result.equity_curve) == len(df)
    assert result.total_fees >= 0
    if result.trades:
        assert all(t.fees > 0 for t in result.trades)


def test_daily_loss_limit_stops_trading():
    df = synthetic_ohlcv(n_bars=60 * 24 * 2, vol_per_bar=0.003)
    strat = build("mean_reversion_rsi", {})
    result = run_backtest(
        df,
        strategy=strat,
        starting_equity=10_000.0,
        limits=RiskLimits(max_daily_loss_pct=0.001, max_daily_trades=1000),
        fee_pct=0.00075,
        slippage_pct=0.0002,
    )
    if not result.daily_pnl.empty:
        worst = result.daily_pnl.min()
        assert worst >= -10_000.0 * 0.05
