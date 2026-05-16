from __future__ import annotations

import pandas as pd

from .backtester import BacktestResult


def summary(result: BacktestResult, daily_target_eur: float) -> dict:
    n = len(result.trades)
    days = max(len(result.daily_pnl), 1)
    avg_daily = result.daily_pnl.mean() if n else 0.0
    median_daily = result.daily_pnl.median() if n else 0.0
    days_hitting_target = int((result.daily_pnl >= daily_target_eur).sum()) if n else 0
    return {
        "trades": n,
        "trades_per_day_avg": n / days,
        "win_rate": result.win_rate,
        "total_pnl_eur": result.total_pnl,
        "total_fees_eur": result.total_fees,
        "avg_daily_pnl_eur": float(avg_daily),
        "median_daily_pnl_eur": float(median_daily),
        "best_day_eur": float(result.daily_pnl.max()) if n else 0.0,
        "worst_day_eur": float(result.daily_pnl.min()) if n else 0.0,
        "days_hitting_target": days_hitting_target,
        "days_total": days,
        "max_drawdown_pct": result.max_drawdown * 100,
        "final_equity_eur": float(result.equity_curve.iloc[-1]) if len(result.equity_curve) else result.starting_equity,
    }


def format_summary(s: dict, daily_target_eur: float) -> str:
    lines = [
        "=" * 56,
        " BACKTEST REPORT",
        "=" * 56,
        f"  Trades total        : {s['trades']}",
        f"  Trades / day (avg)  : {s['trades_per_day_avg']:.1f}",
        f"  Win rate            : {s['win_rate'] * 100:.1f}%",
        f"  Total PnL           : {s['total_pnl_eur']:+,.2f} EUR",
        f"  Total fees paid     : {s['total_fees_eur']:,.2f} EUR",
        f"  Avg daily PnL       : {s['avg_daily_pnl_eur']:+,.2f} EUR",
        f"  Median daily PnL    : {s['median_daily_pnl_eur']:+,.2f} EUR",
        f"  Best day            : {s['best_day_eur']:+,.2f} EUR",
        f"  Worst day           : {s['worst_day_eur']:+,.2f} EUR",
        f"  Max drawdown        : {s['max_drawdown_pct']:.2f}%",
        f"  Final equity        : {s['final_equity_eur']:,.2f} EUR",
        "-" * 56,
        f"  Days >= {daily_target_eur:.0f} EUR target : "
        f"{s['days_hitting_target']} / {s['days_total']}",
        "=" * 56,
    ]
    return "\n".join(lines)


def daily_table(result: BacktestResult) -> pd.DataFrame:
    df = result.daily_pnl.to_frame()
    df.index.name = "day"
    df["cumulative"] = df["daily_pnl"].cumsum()
    return df
