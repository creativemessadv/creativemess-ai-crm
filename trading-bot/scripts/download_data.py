#!/usr/bin/env python3
"""Download historical klines from Binance public API.

Usage:
    python scripts/download_data.py --symbol BTCUSDT --interval 1m \\
        --start 2025-01-01 --end 2025-02-01 \\
        --out data/BTCUSDT_1m_2025-01.parquet
"""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.data import download_binance


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", required=True)
    p.add_argument("--interval", default="1m")
    p.add_argument("--start", required=True, help="YYYY-MM-DD")
    p.add_argument("--end", default=None)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args()

    print(f"Downloading {args.symbol} {args.interval} from {args.start} to {args.end or 'now'}...")
    df = download_binance(args.symbol, args.interval, args.start, args.end, args.out)
    print(f"Saved {len(df):,} bars to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
