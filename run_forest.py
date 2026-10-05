#!/usr/bin/env python3
"""Build ``forest.json`` (aggregated SMI results for the site) from ``forest_raw.parquet``.

The raw table holds published survey estimates (no personal data).  The output keeps the
estimate *and its relative error* for every series so that charts can show intervals.

Usage
-----
    uv run python run_forest.py --raw out/forest/forest_raw.parquet --out out/forest
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

import forest_analysis as fa

LOG = logging.getLogger("run_forest")
CHANGE_KEYS = ("area", "stock", "stock_per_ha", "increment", "deadwood_per_ha")


def changes(national: dict[str, list[dict[str, Any]]], span: int) -> dict[str, Any]:
    """First-to-last and last ``span`` years change per headline series, with flags."""
    out: dict[str, Any] = {}
    for key in CHANGE_KEYS:
        s = national.get(key) or []
        if len(s) < 2:
            continue
        last = s[-1]
        earlier = [r for r in s if r["year"] <= last["year"] - span]
        out[key] = {
            "since_start": fa.change(s[0], last),
            f"last_{span}_years": fa.change(earlier[-1], last) if earlier else None,
        }
    return out


def build(df: pl.DataFrame, generated: str | None = None) -> dict[str, Any]:
    """Return the JSON-ready analysis."""
    nat = fa.national(df)
    years = sorted(df["aasta"].unique().to_list())
    return {
        "meta": {
            "generated_utc": generated or datetime.now(UTC).isoformat(timespec="seconds"),
            "source": "keskkonnaandmed.envir.ee: f_smi_tulemused (SMI arvutustulemused)",
            "years": years,
            "latest_year": years[-1],
            "units": {
                "area": "tuhat ha",
                "volume": "tuhat m3",
                "flow": "tuhat m3 aastas",
                "per_ha": "m3/ha",
            },
            "interpretation": [
                "Ühikud on tuletatud suurusjärgust (2,35 mln ha metsamaad, 453 mln m3 tagavara) "
                "ja neid ei ole tabeli skeemis.",
                "suhteline_viga on käsitletud kui 95% usaldusnivool antud ±% (Aastaraamat Mets "
                "2021, lk 17 ja 124); andmebaasi veerg usaldusnivoo on kõigil ridadel 0.",
                "periood = 5 (raie tabelis 22: 3) tähendab mitmeaastast inventeerimisperioodi: "
                "järjestikused aastad kattuvad ega ole sõltumatud.",
                "Vigade liitmine summades ja suhetes on ligikaudne (sõltumatuse eeldus).",
            ],
        },
        "national": nat,
        "changes": changes(nat, 10),
        "species": fa.species(df),
        "owners": fa.owners(df),
        "management": fa.management(df),
        "counties": fa.counties(df),
        "age": fa.age_structure(df),
        "errors": fa.error_summary(df),
    }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("out/forest"))
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = build(pl.read_parquet(args.raw))
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "forest.json").write_text(
        json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    LOG.info("wrote %s", args.out / "forest.json")


if __name__ == "__main__":
    main()
