#!/usr/bin/env python3
"""Build ``energy.json`` (aggregated energy statistics for the site).

Usage
-----
    uv run python run_energy.py --raw out/statee --out out/energy
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

import energy_analysis as ea
import heat_analysis as ha

LOG = logging.getLogger("run_energy")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw", type=Path, default=Path("out/statee"))
    ap.add_argument("--out", type=Path, default=Path("out/energy"))
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    b = pl.read_parquet(args.raw / "KE0240.parquet")
    e = pl.read_parquet(args.raw / "KE033.parquet")
    c = pl.read_parquet(args.raw / "KE032.parquet")
    result = ea.build(b, e, c, datetime.now(UTC).isoformat(timespec="seconds"))
    heat_files = [args.raw / f"{n}.parquet" for n in ("KE034", "KE035", "KE20")]
    if all(f.exists() for f in heat_files):
        result["heat"] = ha.build(*(pl.read_parquet(f) for f in heat_files))
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "energy.json").write_text(
        json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    LOG.info("wrote %s", args.out / "energy.json")


if __name__ == "__main__":
    main()
