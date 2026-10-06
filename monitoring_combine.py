#!/usr/bin/env python3
"""Merge the per-year parts written by ``monitoring_fetch.py`` and report completeness.

Never fails because a part is missing: it records missing years (0 = before 1995), corrupt parts
and years whose rows read differ from the server's exact count, and sets ``complete``.

Usage
-----
    uv run python monitoring_combine.py --parts out/parts --out out/monitoring_agg
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

import polars as pl

from monitoring_fetch import FIRST_YEAR, merge

LOG = logging.getLogger("monitoring_combine")


def combine(
    parts_dir: Path, first: int = FIRST_YEAR, last: int = 2025
) -> tuple[pl.DataFrame, dict[str, Any]]:
    frames: list[pl.DataFrame] = []
    years: dict[int, dict[str, int]] = {}
    broken: list[str] = []
    failed: list[str] = []
    for meta in sorted(parts_dir.rglob("monitoring_part_*.json")):
        try:
            log = json.loads(meta.read_text(encoding="utf-8"))
            df = pl.read_parquet(meta.with_suffix(".parquet"))
        except (OSError, ValueError, pl.exceptions.PolarsError) as exc:
            broken.append(f"{meta.name}: {type(exc).__name__}")
            continue
        failed += [f"{meta.name}: {f}" for f in log.get("failed", [])]
        frames.append(df)
        for y, v in log.get("per_year", {}).items():
            years[int(y)] = v
    merged = merge(frames) if frames else pl.DataFrame()
    wanted = [0, *range(first, last + 1)]
    missing = [y for y in wanted if y not in years]
    bad = [y for y, v in years.items() if v["rows_read"] != v["rows_expected"]]
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
        "note": "rows without a monitoring start time are not selected by any year filter",
    }
    return merged, combined


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--parts", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("out/monitoring_agg"))
    ap.add_argument("--first", type=int, default=FIRST_YEAR)
    ap.add_argument("--last", type=int, default=2025)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    merged, log = combine(args.parts, args.first, args.last)
    args.out.mkdir(parents=True, exist_ok=True)
    merged.write_parquet(args.out / "monitoring_agg.parquet")
    (args.out / "monitoring_fetch_log.json").write_text(
        json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    LOG.info("complete=%s missing=%s", log["complete"], log["years_missing"])


if __name__ == "__main__":
    main()
