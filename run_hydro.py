#!/usr/bin/env python3
"""Compute the hydrology analysis (``hydro.json``) from daily series written by ``hydro_fetch``.

Optionally links annual runoff with the national annual precipitation (% of 1991-2020 normal)
from the climate analysis (``climate.json``) to show how rainfall translates into runoff.

Usage
-----
    uv run python run_hydro.py --daily out/hydro/hydro_daily.parquet \\
        --catalog hydro_catalog.json --climate climate.json --out out/hydro
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

import hydro_analysis as ha

LOG = logging.getLogger("run_hydro")


def num(v: Any, d: int = 3) -> float | None:
    """JSON-safe rounded number (NaN/None -> None)."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    return round(float(v), d)


def series_by_year(df: pl.DataFrame, cols: list[str]) -> dict[str, list[Any]]:
    out: dict[str, list[Any]] = {"years": df["year"].to_list()}
    for c in cols:
        out[c] = [num(v) for v in df[c].to_list()]
    return out


def link_with_climate(
    national: pl.DataFrame, climate: dict[str, Any] | None
) -> dict[str, Any] | None:
    """Pair national runoff index with national annual precipitation (% of normal) per year."""
    if not climate or not climate.get("precipitation"):
        return None
    prec = climate["precipitation"]["annual"]
    p_by_year = dict(zip(prec["years"], prec["mean"], strict=True))
    years, runoff, rain = [], [], []
    for yr, pct in zip(national["year"].to_list(), national["pct_of_mean"].to_list(), strict=True):
        if p_by_year.get(yr) is not None:
            years.append(int(yr))
            runoff.append(float(pct))
            rain.append(float(p_by_year[yr]))
    if len(years) < 6:
        return None
    return {
        "years": years,
        "runoff_pct_of_mean": [num(v, 1) for v in runoff],
        "precip_pct_of_normal": [num(v, 1) for v in rain],
        "spearman": {k: num(v) for k, v in ha.spearman(np.array(rain), np.array(runoff)).items()},
    }


def build(
    daily: pl.DataFrame,
    catalog: dict[str, Any],
    climate: dict[str, Any] | None = None,
    generated: str | None = None,
) -> dict[str, Any]:
    meta = {s["jaam_kood"]: s for s in catalog.get("stations", [])}
    area = {int(k): v.get("valgala_suurus_km2") for k, v in meta.items()}
    q_avg = ha.valid_days(daily, ha.Q_AVG)
    q_max = ha.valid_days(daily, ha.Q_MAX)
    wt = ha.valid_days(daily, ha.WT_AVG)
    codes = sorted(q_avg["jaam_kood"].unique().to_list())
    max_year = q_avg["year"].max() if not q_avg.is_empty() else None
    current = int(max_year) if isinstance(max_year, int) else datetime.now(UTC).year

    annual = ha.annual_runoff(q_avg, area)
    national = ha.runoff_anomaly(annual)
    extremes = ha.annual_extremes(q_avg, q_max)
    temp = ha.water_temperature(wt)
    cov = ha.coverage(q_avg)

    def per_station(df: pl.DataFrame, cols: list[str]) -> dict[str, Any]:
        return {
            str(c): series_by_year(df.filter(pl.col("jaam_kood") == c), cols)
            for c in codes
            if not df.filter(pl.col("jaam_kood") == c).is_empty()
        }

    stations = []
    for c in codes:
        m = meta.get(c, {})
        days = q_avg.filter(pl.col("jaam_kood") == c)
        stations.append(
            {
                "code": c,
                "name": m.get("jaam_nimi"),
                "river": m.get("veekogu_nimi"),
                "area_km2": m.get("valgala_suurus_km2"),
                "lat": m.get("jaam_laiuskraad"),
                "lon": m.get("jaam_pikkuskraad"),
                "first": str(days["date"].min()),
                "last": str(days["date"].max()),
                "valid_days": days.height,
            }
        )
    return {
        "meta": {
            "generated_utc": generated or datetime.now(UTC).isoformat(timespec="seconds"),
            "source": "keskkonnaandmed.envir.ee, f_hydroseire (hourly, aggregated to UTC days)",
            "provenance": "Published monitoring series; schema states no QC level, none assumed.",
            "units": {
                "discharge": "m3/s (assumed, not in schema)",
                "water_temperature": "degC (assumed)",
            },
            "time_basis": "UTC calendar days; a day needs >= 20 hourly values.",
            "reference": "All complete years per station (about 2013-2025); no 30-year normal.",
            "limits": [
                "Records start in 2012: no return periods or long-term trends can be derived.",
                "Stations chosen for record length; regulation by lakes or dams is not flagged.",
            ],
            "current_year": current,
        },
        "stations": stations,
        "regime": {str(k): v for k, v in ha.regime(q_avg, current).items()},
        "annual": per_station(annual, ["q_mean", "specific_ls_km2", "runoff_mm"]),
        "national_runoff": {
            k: [num(v, 1) if k != "year" else v for v in national[k].to_list()]
            for k in ("year", "pct_of_mean", "p10", "p90", "n")
        },
        "flow_duration": {str(k): v for k, v in ha.flow_duration(q_avg, area).items()},
        "extremes": per_station(extremes, ["peak", "q7min"]),
        "water_temperature": per_station(temp, ["annual_mean", "summer_mean"]),
        "coverage": {
            "cells": [
                [int(a), int(b), num(c, 3)]
                for a, b, c in cov.select("jaam_kood", "year", "share").iter_rows()
            ]
        },
        "plausibility": ha.plausibility(annual, wt),
        "climate_link": link_with_climate(national, climate),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--daily", type=Path, required=True)
    ap.add_argument("--catalog", type=Path, required=True)
    ap.add_argument("--climate", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=Path("out/hydro"))
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    climate = (
        json.loads(args.climate.read_text(encoding="utf-8"))
        if args.climate and args.climate.exists()
        else None
    )
    result = build(
        pl.read_parquet(args.daily), json.loads(args.catalog.read_text(encoding="utf-8")), climate
    )
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "hydro.json").write_text(
        json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    LOG.info("wrote %s (%d stations)", args.out / "hydro.json", len(result["stations"]))


if __name__ == "__main__":
    main()
