#!/usr/bin/env python3
"""Merge the per-year parts written by ``waste_fetch.py`` into one aggregate and a combined log.

Never fails because a part is missing: it records which expected years are absent, which parts
are corrupt and whether a year's rows read differ from the server's count, and sets
``complete`` accordingly, so the next step can decide to re-run only the missing years.

Usage
-----
    uv run python waste_combine.py --parts out/parts --out out/waste_agg --first 2004 --last 2025
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

import polars as pl

from waste_fetch import merge

LOG = logging.getLogger("waste_combine")


def combine(parts_dir: Path, first: int, last: int) -> tuple[pl.DataFrame, dict[str, Any]]:
    """Return (merged aggregate, combined log) for all parts found in ``parts_dir``."""
    frames: list[pl.DataFrame] = []
    years: dict[int, dict[str, int]] = {}  # year -> rows_expected / rows_read
    broken: list[str] = []
    failed: list[str] = []
    for meta in sorted(parts_dir.rglob("waste_part_*.json")):
        pq = meta.with_suffix(".parquet")
        try:
            log = json.loads(meta.read_text(encoding="utf-8"))
            df = pl.read_parquet(pq)
        except (OSError, ValueError, pl.exceptions.PolarsError) as exc:
            broken.append(f"{meta.name}: {type(exc).__name__}")
            continue
        failed += [f"{meta.name}: {f}" for f in log.get("failed", [])]
        frames.append(df)
        for y, v in log.get("per_year", {}).items():
            years[int(y)] = v
    merged = merge(frames) if frames else pl.DataFrame()
    wanted = list(range(first, last + 1))
    missing = [y for y in wanted if y not in years]
    bad = [
        y for y, v in years.items() if v["rows_expected"] and v["rows_read"] != v["rows_expected"]
    ]
    combined = {
        "years_present": sorted(years),
        "years_missing": missing,
        "years_row_mismatch": sorted(bad),
        "per_year": {str(y): years[y] for y in sorted(years)},
        "rows_read": sum(v["rows_read"] for v in years.values()),
        "rows_expected": sum(v["rows_expected"] for v in years.values()),
        "broken_parts": broken,
        "failed": failed[:50],
        "complete": not missing and not bad and not broken and not failed,
    }
    return merged, combined


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--parts", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("out/waste_agg"))
    ap.add_argument("--first", type=int, default=2004)
    ap.add_argument("--last", type=int, default=2025)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    merged, log = combine(args.parts, args.first, args.last)
    args.out.mkdir(parents=True, exist_ok=True)
    merged.write_parquet(args.out / "waste_agg.parquet")
    (args.out / "waste_fetch_log.json").write_text(
        json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    LOG.info("complete=%s missing=%s", log["complete"], log["years_missing"])


if __name__ == "__main__":
    main()
