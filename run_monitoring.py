#!/usr/bin/env python3
"""Build ``monitoring.json`` for the site: monitoring coverage plus tree-crown condition.

Inputs: ``monitoring_catalog.json`` (``monitoring_catalog.py``) and the extract Parquet of the
crown indicator (``monitoring_extract.py``).  Only aggregates are written.

Usage
-----
    uv run python run_monitoring.py --catalog monitoring_catalog.json \
        --extract out/extract/monitoring_extract.parquet --out out/monitoring
"""

from __future__ import annotations

import argparse
import json
import logging
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

import crown_analysis as ca
import wq_analysis as wq

LOG = logging.getLogger("run_monitoring")
FIRST_SITE_YEAR = 1990


def coverage(catalog: dict[str, Any]) -> dict[str, Any]:
    """Indicator groups (rows, years) and species coverage per year from the catalogue."""
    groups: dict[str, dict[str, Any]] = defaultdict(lambda: {"rows": 0, "years": set()})
    for r in catalog["groups_by_year"]:
        g = groups[r["naitaja_grupp_selg"] or "määramata"]
        g["rows"] += r["rows"]
        g["years"].add(r["year"])
    group_rows = sorted(
        (
            {
                "name": k,
                "rows": v["rows"],
                "first_year": min(v["years"]),
                "last_year": max(v["years"]),
                "years": len(v["years"]),
            }
            for k, v in groups.items()
        ),
        key=lambda r: -r["rows"],
    )
    return {
        "rows": catalog["rows"],
        "rows_by_year": [r for r in catalog["rows_by_year"] if r["year"] >= FIRST_SITE_YEAR],
        "groups": group_rows,
        "species_per_year": [
            r for r in catalog["species"]["per_year"] if r["year"] >= FIRST_SITE_YEAR
        ],
        "species_indicators": [
            i
            for i in catalog["indicators"]
            if i["species"] >= 5 and "arv" in (i["naitaja_nimetus"] or "").lower()
        ][:12],
    }


def build(
    catalog: dict[str, Any], extract: pl.DataFrame, generated: str | None = None
) -> dict[str, Any]:
    return {
        "meta": {
            "generated_utc": generated or datetime.now(UTC).isoformat(timespec="seconds"),
            "source": "keskkonnaandmed.envir.ee: f_keskkonnaseire (KESE keskkonnaseire andmed)",
            "interpretation": [
                "Tabel on pikk (üks väärtus või vaatlus rea kohta); ridade arv sõltub seire "
                "ulatusest ja andmete sisestamisest, mitte keskkonnaseisundist.",
                "Liikide arv aastas näitab seiretöödes registreeritud liike, mitte liigirikkust "
                "Eestis; see sõltub seirekavadest ja määramistäpsusest.",
                "Proovialade koordinaate, vaatlejaid ega vabateksti ei laeta ega avaldata.",
            ],
        },
        "coverage": coverage(catalog),
        "crown": ca.build(extract),
        "water_quality": wq.build(extract) if "pohjaveekogum_kood" in extract.columns else None,
    }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--catalog", type=Path, required=True)
    ap.add_argument("--extract", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("out/monitoring"))
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    result = build(catalog, pl.read_parquet(args.extract))
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "monitoring.json").write_text(
        json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    LOG.info("wrote %s", args.out / "monitoring.json")


if __name__ == "__main__":
    main()
