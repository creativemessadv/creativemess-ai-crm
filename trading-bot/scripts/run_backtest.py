#!/usr/bin/env python3
"""Run a backtest from a YAML config file.

Usage:
    python scripts/run_backtest.py --config config.yaml --data data/btc.parquet
    python scripts/run_backtest.py --config config.yaml --synthetic  # offline demo
"""

import argparse
from pathlib import Path
import sys

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot import strategies
from bot.backtester import run_backtest
from bot.data import load_parquet, synthetic_ohlcv
from bot.reporting import format_summary, summary
from bot.risk import RiskLimits


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, default=Path("config.yaml"))
    p.add_argument("--data", type=Path, default=None)
    p.add_argument("--synthetic", action="store_true", help="Use synthetic OHLCV (offline demo)")
    p.add_argument("--synthetic-days", type=int, default=30)
    p.add_argument("--csv-out", type=Path, default=None)
    args = p.parse_args()

    cfg = yaml.safe_load(args.config.read_text())

    if args.synthetic:
        bars = 60 * 24 * args.synthetic_days
        print(f"Generating {bars:,} synthetic 1-minute bars ({args.synthetic_days} days)...")
        df = synthetic_ohlcv(n_bars=bars)
    elif args.data:
        print(f"Loading data from {args.data}...")
        df = load_parquet(args.data)
    else:
        p.error("Pass either --data or --synthetic")
        return 2

    print(f"Bars loaded: {len(df):,}  range: {df.index[0]} -> {df.index[-1]}")

    strat = strategies.build(cfg["strategy"]["name"], cfg["strategy"]["params"])
    limits = RiskLimits(**cfg["risk"])
    result = run_backtest(
        df,
        strategy=strat,
        starting_equity=cfg["capital"],
        limits=limits,
        fee_pct=cfg["execution"]["fee_pct"],
        slippage_pct=cfg["execution"]["slippage_pct"],
    )

    s = summary(result, cfg["reporting"]["daily_target_eur"])
    print(format_summary(s, cfg["reporting"]["daily_target_eur"]))

    if args.csv_out:
        args.csv_out.parent.mkdir(parents=True, exist_ok=True)
        rows = [
            {
                "opened_at": t.opened_at,
                "closed_at": t.closed_at,
                "side": t.side.value,
                "qty": t.qty,
                "entry": t.entry_price,
                "exit": t.exit_price,
                "pnl": t.pnl,
                "fees": t.fees,
                "reason": t.exit_reason,
            }
            for t in result.trades
        ]
        import pandas as pd
        pd.DataFrame(rows).to_csv(args.csv_out, index=False)
        print(f"Wrote {len(rows)} trades to {args.csv_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
