#!/usr/bin/env python3
"""24/7 paper-trading loop. Polls Binance public REST every `--poll` seconds,
appends each new closed bar to a rolling window, asks the strategy, and
executes simulated fills via the same PaperBroker used in backtests.
No API key, no real orders. Press Ctrl-C to stop.

Usage:
    python scripts/run_paper.py --config config.yaml
"""

import argparse
import signal
import time
from collections import deque
from pathlib import Path
import sys
from typing import Deque

import pandas as pd
import requests
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot import strategies
from bot.broker.paper import PaperBroker
from bot.data import BINANCE_URL
from bot.risk import RiskLimits, RiskManager
from bot.strategies.base import Side


_stop = False


def _handle_stop(signum, frame):
    global _stop
    _stop = True


def fetch_recent(symbol: str, interval: str, limit: int) -> pd.DataFrame:
    r = requests.get(
        BINANCE_URL,
        params={"symbol": symbol, "interval": interval, "limit": limit},
        timeout=10,
    )
    r.raise_for_status()
    rows = r.json()
    df = pd.DataFrame(
        rows,
        columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "qav", "trades", "tbbav", "tbqav", "ignore",
        ],
    )
    df = df[["open_time", "open", "high", "low", "close", "volume"]].astype(
        {"open": float, "high": float, "low": float, "close": float, "volume": float}
    )
    df["timestamp"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    return df.set_index("timestamp").drop(columns=["open_time"])


def main() -> int:
    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)

    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, default=Path("config.yaml"))
    p.add_argument("--poll", type=float, default=10.0, help="Seconds between polls")
    p.add_argument("--window", type=int, default=500, help="Bars kept in memory")
    args = p.parse_args()

    cfg = yaml.safe_load(args.config.read_text())
    strat = strategies.build(cfg["strategy"]["name"], cfg["strategy"]["params"])
    limits = RiskLimits(**cfg["risk"])
    broker = PaperBroker(
        fee_pct=cfg["execution"]["fee_pct"],
        slippage_pct=cfg["execution"]["slippage_pct"],
    )
    equity = float(cfg["capital"])
    risk = RiskManager(limits, equity)
    current_day: pd.Timestamp | None = None

    symbol = cfg["symbol"]
    interval = cfg["timeframe"]
    print(f"[paper] starting on {symbol} {interval}, equity={equity:.2f}")

    last_closed_ts: pd.Timestamp | None = None
    window: Deque = deque(maxlen=args.window)

    while not _stop:
        try:
            df = fetch_recent(symbol, interval, limit=max(args.window, strat.warmup() + 5))
        except Exception as e:
            print(f"[paper] fetch error: {e}")
            time.sleep(args.poll)
            continue

        closed_bars = df.iloc[:-1]
        if last_closed_ts is None:
            for ts, row in closed_bars.iterrows():
                window.append((ts, row))
            last_closed_ts = closed_bars.index[-1]
            print(f"[paper] warmed up with {len(window)} bars")
        else:
            new_bars = closed_bars[closed_bars.index > last_closed_ts]
            for ts, row in new_bars.iterrows():
                window.append((ts, row))
                day = ts.normalize()
                if current_day is None:
                    current_day = day
                if day != current_day:
                    risk.reset_day(equity)
                    current_day = day

                closed = broker.step(row, ts)
                for t in closed:
                    equity += t.pnl
                    risk.record_trade(t.pnl)
                    print(
                        f"[paper] CLOSE {t.side.value} qty={t.qty:.6f} "
                        f"pnl={t.pnl:+.2f} reason={t.exit_reason} equity={equity:.2f}"
                    )

                if risk.can_open(len(broker.positions)):
                    win_df = pd.DataFrame([r for _, r in window], index=[t for t, _ in window])
                    signal_obj = strat.on_bar(win_df)
                    if signal_obj and signal_obj.side != Side.FLAT:
                        price = float(row["close"])
                        qty = risk.position_size(equity, price, signal_obj.stop_loss_pct)
                        if qty > 0:
                            broker.open(
                                side=signal_obj.side,
                                qty=qty,
                                bar_open=price,
                                take_profit_pct=signal_obj.take_profit_pct,
                                stop_loss_pct=signal_obj.stop_loss_pct,
                                bar_time=ts,
                                reason=signal_obj.reason,
                            )
                            print(
                                f"[paper] OPEN  {signal_obj.side.value} qty={qty:.6f} "
                                f"@ {price:.2f} ({signal_obj.reason})"
                            )
            if not new_bars.empty:
                last_closed_ts = new_bars.index[-1]

        time.sleep(args.poll)

    print(f"[paper] stopped. final equity={equity:.2f}, trades={len(broker.trades)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
