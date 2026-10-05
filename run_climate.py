#!/usr/bin/env python3
"""Fetch KAUR climate open data and compute the climate analysis (``climate.json``).

Source: ``f_kliima_kuu`` (monthly), ``f_kliima_paev`` (daily), ``f_kliima_jaam_vaatlus``
(stations) and ``f_kliima_element`` (element dictionary) of ``keskkonnaandmed.envir.ee``.
Provenance: published observations; the schema does not state a QC or homogenisation level, so
none is claimed.  Aggregated results only are written; the raw data are not redistributed.

Usage
-----
    uv run python run_climate.py --out out/climate
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

import climate_analysis as ca
from postgrest import Client

LOG = logging.getLogger("run_climate")
TEMP, PREC = "DTA08", "DPREC"
SCHEMA = {
    "jaam_kood": pl.Utf8,
    "jaam_nimi": pl.Utf8,
    "aasta": pl.Int32,
    "kuu": pl.Int32,
    "vaartus": pl.Float64,
    "element_kood": pl.Utf8,
}
DAILY_SCHEMA = {**SCHEMA, "paev": pl.Int32}
CHECK_STATION = "AJHARK01"  # Tallinn-Harku: used to cross-check monthly vs daily aggregation


def fetch_frame(
    client: Client, table: str, element_filter: str, schema: dict[str, Any], extra: dict[str, str]
) -> pl.DataFrame:
    cols = ",".join(schema)
    order = ",".join(
        ["jaam_kood", "element_kood", "aasta", "kuu", *(["paev"] if "paev" in schema else [])]
    )
    rows = list(
        client.iter_rows(
            table,
            select=cols,
            order=order,
            filters={"element_kood": f"in.({element_filter})", **extra},
        )
    )
    LOG.info("%s: %d rows", table, len(rows))
    return (
        pl.DataFrame(rows, schema=schema, orient="row" if False else None)
        if rows
        else pl.DataFrame(schema=schema)
    )


def clean_nan(values: Any) -> list[float | None]:
    """NumPy array -> JSON-safe list (NaN -> null, rounded)."""
    return [None if (v is None or np.isnan(v)) else round(float(v), 3) for v in np.asarray(values)]


def series_block(
    years: list[int], nat: dict[str, np.ndarray], tr: dict[str, float]
) -> dict[str, Any]:
    return {
        "years": years,
        "mean": clean_nan(nat["mean"]),
        "lo": clean_nan(nat["lo"]),
        "hi": clean_nan(nat["hi"]),
        "n_stations": [int(v) for v in nat["n"]],
        "trend": {k: (None if np.isnan(v) else round(float(v), 3)) for k, v in tr.items()},
    }


def analyse_variable(df: pl.DataFrame, kind: str, reps: int = ca.BOOTSTRAP_REPS) -> dict[str, Any]:
    """Annual + seasonal national series, month-by-year grid and station trends for one variable."""
    normals = ca.monthly_normals(df)
    out: dict[str, Any] = {"n_stations_with_normal": normals["jaam_kood"].n_unique()}

    def national(
        per_station: pl.DataFrame, col: str
    ) -> tuple[dict[str, np.ndarray], list[int], np.ndarray, list[str]]:
        mat, stations, years = ca.to_matrix(per_station, col)
        return ca.national_series(mat, reps=reps), years, mat, stations

    if kind == "ratio":
        annual_ps = ca.precipitation_ratio(df, normals, ["aasta"], 12)
        seas_src = ca.with_season(df)
        seasonal_ps = {
            s: ca.precipitation_ratio(
                seas_src.filter(pl.col("season") == s), normals, ["season_year"], 3
            )
            for s in ca.SEASONS
        }
    else:
        anom = ca.anomalies(df, normals, "diff")
        annual_ps = ca.station_period_matrix(anom, ["aasta"], 12)
        seas_anom = ca.with_season(anom)
        seasonal_ps = {
            s: ca.station_period_matrix(seas_anom.filter(pl.col("season") == s), ["season_year"], 3)
            for s in ca.SEASONS
        }

    nat, years, mat, stations = national(annual_ps, "aasta")
    ya = np.array(years)
    out["annual"] = series_block(years, nat, ca.trend(ya, nat["mean"], reps=reps))
    out["annual"]["top_years"] = ca.ranks(nat["mean"], ya, 5)
    out["station_trends"] = []
    for i, st in enumerate(stations):
        tr = ca.trend(ya, mat[i], reps=min(reps, 300))
        out["station_trends"].append(
            {
                "code": st,
                **{k: (None if np.isnan(v) else round(float(v), 3)) for k, v in tr.items()},
            }
        )
    out["seasonal"] = {}
    for s, ps in seasonal_ps.items():
        n_s, y_s, _, _ = national(ps, "season_year")
        out["seasonal"][s] = series_block(y_s, n_s, ca.trend(np.array(y_s), n_s["mean"], reps=reps))

    # month x year grid of national anomalies (temperature only; precipitation ratios are noisy)
    if kind == "diff":
        monthly = ca.anomalies(df, normals, "diff")
        grid = (
            monthly.group_by("aasta", "kuu")
            .agg(mean=pl.col("anom").mean(), n=pl.col("jaam_kood").n_unique())
            .filter(pl.col("n") >= ca.MIN_STATIONS)
            .sort("aasta", "kuu")
        )
        out["monthly_grid"] = {
            "years": sorted(grid["aasta"].unique().to_list()),
            "cells": [
                [int(a), int(k), round(float(m), 3), int(n)]
                for a, k, m, n in grid.select("aasta", "kuu", "mean", "n").iter_rows()
            ],
        }
    return out


def build(
    monthly: pl.DataFrame,
    idx: pl.DataFrame,
    stations_meta: pl.DataFrame,
    elements: pl.DataFrame,
    checks: dict[str, Any],
    reps: int = ca.BOOTSTRAP_REPS,
    generated: str | None = None,
) -> dict[str, Any]:
    """Assemble the JSON document consumed by the site."""
    temp = monthly.filter(pl.col("element_kood") == TEMP)
    prec = monthly.filter(pl.col("element_kood") == PREC)
    comp = ca.completeness(temp)
    names = dict(zip(temp["jaam_kood"].to_list(), temp["jaam_nimi"].to_list(), strict=False))
    meta_by_code = {r["jaam_kood"]: r for r in stations_meta.iter_rows(named=True)}
    st_codes = sorted(names)
    out: dict[str, Any] = {
        "meta": {
            "generated_utc": generated or datetime.now(UTC).isoformat(timespec="seconds"),
            "source": "keskkonnaandmed.envir.ee (PostgREST, profile apijahiala): f_kliima_kuu, "
            "f_kliima_paev, f_kliima_jaam_vaatlus, f_kliima_element",
            "provenance": "Published observations (daily/monthly aggregates). QC and "
            "homogenisation level are not stated in the data schema and are not assumed.",
            "baseline": [ca.BASE_START, ca.BASE_END],
            "time_basis": "Year/month/day in UTC as published; no conversion to local time.",
            "elements": {
                r["element_kood"]: {
                    "name_et": r["element_nimi"],
                    "name_en": r["element_nimi_eng"],
                    "unit": r["element_yhik_eng"],
                }
                for r in elements.iter_rows(named=True)
                if r["element_kood"] in {TEMP, PREC}
            },
            "limits": [
                "Series start in 1991: century-scale warming cannot be assessed from this source.",
                "National values are unweighted station means; interval = station bootstrap only.",
                "Trends are Theil-Sen with 3-year block bootstrap; ~35 years is a short record.",
            ],
        },
        "stations": [
            {
                "code": c,
                "name": names[c],
                "lat": meta_by_code.get(c, {}).get("laiuskraad"),
                "lon": meta_by_code.get(c, {}).get("pikkuskraad"),
                "alt_m": meta_by_code.get(c, {}).get("korgus_merepinnast_m"),
            }
            for c in st_codes
        ],
        "completeness": {
            "years": sorted(comp["aasta"].unique().to_list()),
            "cells": [
                [r[0], int(r[1]), int(r[2])]
                for r in comp.select("jaam_kood", "aasta", "months").iter_rows()
            ],
        },
        "temperature": analyse_variable(temp, "diff", reps),
        "precipitation": analyse_variable(prec, "ratio", reps) if not prec.is_empty() else None,
        "extremes": {
            name: ca.index_series(idx, name)
            for name in ("FD", "ID", "SU25", "HD30", "TR20", "R10", "R20", "Rx1day")
            if name in idx.columns
        },
        "checks": checks,
    }
    for block in out["extremes"].values():
        if block.get("aasta"):
            yrs, med = np.array(block["aasta"]), np.array(block["median"], dtype=float)
            block["trend"] = {
                k: (None if np.isnan(v) else round(float(v), 3))
                for k, v in ca.trend(yrs, med, reps=reps).items()
            }
    return out


def consistency_check(monthly: pl.DataFrame, daily_temp: pl.DataFrame) -> dict[str, Any]:
    """Compare published monthly mean temperature with the mean of published daily values."""
    m = monthly.filter((pl.col("element_kood") == TEMP) & (pl.col("jaam_kood") == CHECK_STATION))
    d = (
        daily_temp.filter(pl.col("jaam_kood") == CHECK_STATION)
        .group_by("aasta", "kuu")
        .agg(daily_mean=pl.col("vaartus").mean(), n_days=pl.len())
        .filter(pl.col("n_days") >= 28)
    )
    j = m.join(d, on=["aasta", "kuu"], how="inner").with_columns(
        diff=(pl.col("vaartus") - pl.col("daily_mean")).abs()
    )
    if j.is_empty():
        return {"station": CHECK_STATION, "months_compared": 0}
    return {
        "station": CHECK_STATION,
        "months_compared": j.height,
        "max_abs_diff_degC": round(float(j["diff"].max()), 3),  # type: ignore[arg-type]
        "median_abs_diff_degC": round(float(j["diff"].median()), 3),  # type: ignore[arg-type]
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("out/climate"))
    ap.add_argument("--delay", type=float, default=0.3)
    ap.add_argument("--reps", type=int, default=ca.BOOTSTRAP_REPS)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    client = Client(delay=args.delay)

    monthly = fetch_frame(client, "f_kliima_kuu", f"{TEMP},{PREC}", SCHEMA, {})
    daily = fetch_frame(
        client, "f_kliima_paev", "DTAX,DTAN,DPREC", DAILY_SCHEMA, {"aasta": f"gte.{ca.BASE_START}"}
    )
    daily_check = fetch_frame(
        client, "f_kliima_paev", TEMP, DAILY_SCHEMA, {"jaam_kood": f"eq.{CHECK_STATION}"}
    )
    meta_rows = list(client.iter_rows("f_kliima_jaam_vaatlus", order="jaam_kood,element_kood"))
    stations = pl.DataFrame(meta_rows).unique("jaam_kood") if meta_rows else pl.DataFrame()
    elements = pl.DataFrame(list(client.iter_rows("f_kliima_element")))

    def one(code: str) -> pl.DataFrame:
        return daily.filter(pl.col("element_kood") == code) if not daily.is_empty() else daily

    idx = ca.daily_indices(one("DTAX"), one("DTAN"), one("DPREC"))
    checks = {
        "monthly_vs_daily_mean_temperature": consistency_check(monthly, daily_check),
        "rows": {"monthly": monthly.height, "daily": daily.height},
        "daily_elements_present": sorted(daily["element_kood"].unique().to_list())
        if not daily.is_empty()
        else [],
    }
    result = build(monthly, idx, stations, elements, checks, args.reps)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "climate.json").write_text(
        json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    LOG.info("wrote %s", args.out / "climate.json")


if __name__ == "__main__":
    main()
