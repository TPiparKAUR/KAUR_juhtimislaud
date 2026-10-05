#!/usr/bin/env python3
"""Build ``waste.json`` (aggregated national waste statistics) for the site.

Input: ``waste_agg.parquet`` from ``waste_fetch`` (and optionally its ``waste_fetch_log.json``,
whose completeness checks are copied into the output so the page can state them).

Usage
-----
    uv run python run_waste.py --agg out/waste_agg/waste_agg.parquet \\
        --log out/waste_agg/waste_fetch_log.json --out out/waste_agg
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

import waste_analysis as wa

LOG = logging.getLogger("run_waste")


def build(
    agg: pl.DataFrame, fetch_log: dict[str, Any] | None = None, generated: str | None = None
) -> dict[str, Any]:
    """Return the JSON-ready analysis; ``fetch_log`` supplies completeness statements."""
    d = wa.clean(agg)
    years = sorted(d["aasta"].unique().to_list())
    latest = years[-1]
    names = wa.chapter_names(d)
    flows = wa.flow_totals(d)
    present = {r["maht_liik"] for r in flows}
    return {
        "meta": {
            "generated_utc": generated or datetime.now(UTC).isoformat(timespec="seconds"),
            "source": "keskkonnaandmed.envir.ee: f_jaatmeliikumine_fix_riik (national waste "
            "statistics)",
            "unit_assumption": "t (tonnes); not stated in the table schema",
            "years": years,
            "latest_year": latest,
            "flow_order": [f for f in wa.FLOW_ORDER if f in present]
            + sorted(present - set(wa.FLOW_ORDER)),
            "chapter_names_data": names,
            "chapter_labels_short": wa.CHAPTERS,
            "limits": [
                "Flow types (generation, recovery, landfilling, export, stock, ...) are shown "
                "separately and never added up: the table does not say whether they overlap.",
                "The unit is assumed to be tonnes.",
                "Negative values exist; totals are net and the sum of negative values is shown.",
            ],
            "fetch": {
                k: (fetch_log or {}).get(k)
                for k in ("rows_read", "count_mismatches", "failed", "skipped_over_budget")
            },
        },
        "coverage": wa.coverage(d),
        "flows": flows,
        "generation_by_chapter": wa.by_chapter(d, wa.GENERATION),
        "recovery_by_chapter": wa.by_chapter(d, wa.RECOVERY),
        "landfill_by_chapter": wa.by_chapter(d, wa.LANDFILL),
        "household_by_chapter": wa.by_chapter(d, wa.HOUSEHOLD),
        "hazardous_generation": wa.hazardous(d, wa.GENERATION),
        "top_generation": wa.top_types(d, wa.GENERATION, latest),
        "export_partners": wa.trade_partners(d, wa.EXPORT),
        "import_partners": wa.trade_partners(d, wa.IMPORT),
        "stock_continuity": wa.stock_continuity(d),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--agg", type=Path, required=True)
    ap.add_argument("--log", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=Path("out/waste_agg"))
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    fetch_log = None
    if args.log and args.log.exists():
        fetch_log = json.loads(args.log.read_text(encoding="utf-8"))
    result = build(pl.read_parquet(args.agg), fetch_log)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "waste.json").write_text(
        json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    LOG.info("wrote %s", args.out / "waste.json")


if __name__ == "__main__":
    main()
