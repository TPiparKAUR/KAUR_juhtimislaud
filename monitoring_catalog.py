#!/usr/bin/env python3
"""Catalogue of the monitoring table from the aggregate written by ``monitoring_combine.py``.

Answers: which programmes, indicator groups and indicators exist, in which years, how many rows,
which units, which species groups are monitored and how many species per year.  Pure aggregation;
no coordinates, observers or free text are involved.

Usage
-----
    uv run python monitoring_catalog.py --agg out/monitoring_agg.parquet --out out/catalog
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

import polars as pl

LOG = logging.getLogger("monitoring_catalog")
PROG = "seiretoo_seotud_programmi_nimi_i"


def by_programme(df: pl.DataFrame) -> list[dict[str, Any]]:
    return (
        df.group_by(PROG)
        .agg(
            rows=pl.col("rows").sum(),
            first_year=pl.col("year").min(),
            last_year=pl.col("year").max(),
            indicators=pl.col("naitaja_kood").n_unique(),
            species=pl.col("liik_est").n_unique(),
        )
        .sort("rows", descending=True)
        .to_dicts()
    )


def by_indicator(df: pl.DataFrame, top: int = 400) -> list[dict[str, Any]]:
    """Largest indicators with years covered, units and numeric share."""
    return (
        df.group_by(PROG, "naitaja_grupp_selg", "naitaja_kood", "naitaja_nimetus")
        .agg(
            rows=pl.col("rows").sum(),
            n_value=pl.col("n_value").sum(),
            first_year=pl.col("year").min(),
            last_year=pl.col("year").max(),
            years=pl.col("year").n_unique(),
            units=pl.col("naitaja_abr_unit").drop_nulls().unique().sort(),
            species=pl.col("liik_est").n_unique(),
            v_min=pl.col("v_min").min(),
            v_max=pl.col("v_max").max(),
            negatives=pl.col("n_negative").sum(),
        )
        .sort("rows", descending=True)
        .head(top)
        .to_dicts()
    )


def rows_by_year(df: pl.DataFrame) -> list[dict[str, Any]]:
    return df.group_by("year").agg(rows=pl.col("rows").sum()).sort("year").to_dicts()


def species_overview(df: pl.DataFrame) -> dict[str, Any]:
    sp = df.filter(pl.col("liik_est").is_not_null())
    per_year = (
        sp.group_by("year")
        .agg(rows=pl.col("rows").sum(), species=pl.col("liik_est").n_unique())
        .sort("year")
        .to_dicts()
    )
    top = (
        sp.group_by("liik_est", PROG, "naitaja_nimetus")
        .agg(
            rows=pl.col("rows").sum(),
            first_year=pl.col("year").min(),
            last_year=pl.col("year").max(),
        )
        .sort("rows", descending=True)
        .head(60)
        .to_dicts()
    )
    return {"per_year": per_year, "top_species_indicators": top}


def groups_by_year(df: pl.DataFrame) -> list[dict[str, Any]]:
    return (
        df.group_by("naitaja_grupp_selg", "year")
        .agg(rows=pl.col("rows").sum())
        .sort("naitaja_grupp_selg", "year")
        .to_dicts()
    )


def catalog(df: pl.DataFrame) -> dict[str, Any]:
    return {
        "rows": int(df["rows"].sum()),
        "rows_by_year": rows_by_year(df),
        "programmes": by_programme(df),
        "indicators": by_indicator(df),
        "species": species_overview(df),
        "groups_by_year": groups_by_year(df),
    }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--agg", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("out/catalog"))
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "monitoring_catalog.json").write_text(
        json.dumps(catalog(pl.read_parquet(args.agg)), ensure_ascii=False, default=str),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
