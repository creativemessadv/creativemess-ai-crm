"""Data loaders. Two paths:

1. Public Binance klines downloader (works wherever Binance is reachable;
   no API key required for historical data).
2. Synthetic OHLCV generator so backtests can run offline.

Both produce a DataFrame with index=UTC timestamp and columns
[open, high, low, close, volume].
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import requests

BINANCE_URL = "https://api.binance.com/api/v3/klines"
INTERVAL_TO_MS = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "1h": 3_600_000,
    "4h": 14_400_000,
    "1d": 86_400_000,
}


def download_binance(
    symbol: str,
    interval: str,
    start: str,
    end: Optional[str] = None,
    out_path: Optional[Path] = None,
) -> pd.DataFrame:
    if interval not in INTERVAL_TO_MS:
        raise ValueError(f"Unsupported interval: {interval}")
    start_ms = int(pd.Timestamp(start, tz="UTC").timestamp() * 1000)
    end_ms = int(
        (pd.Timestamp(end, tz="UTC") if end else pd.Timestamp.utcnow()).timestamp() * 1000
    )
    step = INTERVAL_TO_MS[interval] * 1000
    rows: list[list] = []
    cursor = start_ms
    while cursor < end_ms:
        resp = requests.get(
            BINANCE_URL,
            params={
                "symbol": symbol,
                "interval": interval,
                "startTime": cursor,
                "endTime": min(cursor + step, end_ms),
                "limit": 1000,
            },
            timeout=15,
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        rows.extend(batch)
        cursor = batch[-1][0] + INTERVAL_TO_MS[interval]
        time.sleep(0.15)
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
    df = df.set_index("timestamp").drop(columns=["open_time"])
    df = df[~df.index.duplicated(keep="first")].sort_index()
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(out_path)
    return df


def synthetic_ohlcv(
    n_bars: int = 60 * 24 * 30,
    start: str = "2024-01-01",
    interval_minutes: int = 1,
    start_price: float = 60_000.0,
    drift_per_bar: float = 0.0,
    vol_per_bar: float = 0.0008,
    seed: int = 42,
) -> pd.DataFrame:
    """Geometric-Brownian-motion 1-minute OHLCV. Defaults model BTC-like
    volatility (~0.08% per minute). For offline demos only — real
    backtest decisions must use real data.
    """
    rng = np.random.default_rng(seed)
    returns = rng.normal(drift_per_bar, vol_per_bar, size=n_bars)
    close = start_price * np.exp(np.cumsum(returns))
    open_ = np.concatenate(([start_price], close[:-1]))
    intra_vol = vol_per_bar * 0.7
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, intra_vol, size=n_bars)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, intra_vol, size=n_bars)))
    volume = rng.lognormal(mean=2.0, sigma=0.5, size=n_bars)
    idx = pd.date_range(start=start, periods=n_bars, freq=f"{interval_minutes}min", tz="UTC")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


def load_parquet(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df
