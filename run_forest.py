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


def checks(
    nat: dict[str, list[dict[str, Any]]],
    species: dict[str, list[dict[str, Any]]],
    owners: dict[str, list[dict[str, Any]]],
    management: dict[str, list[dict[str, Any]]],
    age: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Do the classes tile the total in the latest year? (selection sanity checks)"""

    def latest(s: list[dict[str, Any]]) -> float:
        return float(s[-1]["value"])

    out: dict[str, Any] = {}
    if nat["stock"] and species:
        out["species_vs_stock"] = fa.shares_check(
            [latest(s) for s in species.values()], latest(nat["stock"])
        )
    if nat["area"] and owners:
        out["owners_vs_area"] = fa.shares_check(
            [latest(s) for s in owners.values()], latest(nat["area"])
        )
    parts = [latest(management[k]) for k in fa.MANAGEMENT_PARTS if k in management]
    if management.get("Kokku mets") and len(parts) == len(fa.MANAGEMENT_PARTS):
        out["management_vs_total"] = fa.shares_check(parts, latest(management["Kokku mets"]))
    if nat["area"] and age:
        out["age_vs_area"] = fa.shares_check([latest(s) for s in age.values()], latest(nat["area"]))
    return out


def build(df: pl.DataFrame, generated: str | None = None) -> dict[str, Any]:
    """Return the JSON-ready analysis."""
    nat = fa.national(df)
    species, owners = fa.species(df), fa.owners(df)
    management, age = fa.management(df), fa.age_structure(df)
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
            "age_labels_seen": sorted(
                df.filter((pl.col("tabeli_number") == 13) & (pl.col("filtri_tunnus2") == "Vanus"))[
                    "filter2"
                ]
                .drop_nulls()
                .unique()
                .to_list()
            ),
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
        "species": species,
        "owners": owners,
        "management": management,
        "management_parts": fa.MANAGEMENT_PARTS,
        "counties": fa.counties(df),
        "age": age,
        "checks": checks(nat, species, owners, management, age),
        "traces": {
            "age": fa.filter_trace(
                df,
                13,
                "Pindala",
                fa.SUM,
                by=("omand", "enamuspuuliik"),
                maakategooria=fa.LAND,
                filtri_tunnus2="Vanus",
                filter2="21…40 a",
            )
        }
        if not age
        else {},
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
