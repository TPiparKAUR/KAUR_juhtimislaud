#!/usr/bin/env python3
"""Build ``circular.json`` (material flows, waste, GDP and circular material use rate).

Usage
-----
    uv run python run_circular.py --statee out/statee --eurostat out/eurostat --out out/circular
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

import circular_analysis as ca

LOG = logging.getLogger("run_circular")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--statee", type=Path, default=Path("out/statee"))
    ap.add_argument("--eurostat", type=Path, default=Path("out/eurostat"))
    ap.add_argument("--out", type=Path, default=Path("out/circular"))
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    rd = args.statee

    def labels(table: str, variable: str) -> dict[str, str]:
        data = json.loads((rd / f"{table}.labels.json").read_text(encoding="utf-8"))
        labels_: dict[str, str] = data[variable]
        return labels_

    texts = {
        "KK610_waste": labels("KK610", "Jäätmeliik"),
        "KK068_activity": labels("KK068", "Tegevusala (EMTAK 2008)"),
    }
    result = ca.build(
        pl.read_parquet(rd / "KK99.parquet"),
        pl.read_parquet(rd / "KK610.parquet"),
        pl.read_parquet(rd / "KK068.parquet"),
        pl.read_parquet(rd / "RAA0012.parquet"),
        pl.read_parquet(args.eurostat / "cei_srm030.parquet"),
        texts,
        datetime.now(UTC).isoformat(timespec="seconds"),
    )
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "circular.json").write_text(
        json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    LOG.info("wrote %s", args.out / "circular.json")


if __name__ == "__main__":
    main()
