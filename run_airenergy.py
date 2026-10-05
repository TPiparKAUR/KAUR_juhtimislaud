#!/usr/bin/env python3
"""Compute ``airenergy.json`` from the Parquet files written by ``airenergy_explore``.

Aggregated results only: no company, facility or permit identities are written.

Usage
-----
    uv run python run_airenergy.py --emissions emissions.parquet --heat heat.parquet \\
        --climate climate.json --out out/airenergy
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

import airenergy_analysis as aa

LOG = logging.getLogger("run_airenergy")


def rows(df: pl.DataFrame) -> list[dict[str, Any]]:
    return df.to_dicts()


def climate_link(
    heat_by_year: dict[int, float], climate: dict[str, Any] | None
) -> dict[str, Any] | None:
    """Pair yearly heat production with the winter (DJF) anomaly of the climate analysis."""
    if not climate:
        return None
    djf = climate["temperature"]["seasonal"]["DJF"]
    anom = dict(zip(djf["years"], djf["mean"], strict=True))
    years = [y for y in sorted(heat_by_year) if anom.get(y) is not None]
    if len(years) < 4:
        return None
    return {
        "years": years,
        "djf_anomaly_degC": [anom[y] for y in years],
        "heat_mwh": [round(heat_by_year[y]) for y in years],
        "note": "Seven points at most: shown for orientation only, no statistic is computed.",
    }


def build(
    emissions: pl.DataFrame,
    heat: pl.DataFrame,
    climate: dict[str, Any] | None = None,
    generated: str | None = None,
) -> dict[str, Any]:
    em, em_info = aa.prepare_emissions(emissions)
    clean_heat, heat_info = aa.prepare_heat(heat)
    groups = [aa.CO2, aa.CO2_BIO, *aa.POLLUTANTS]
    fuel = aa.energy_by_fuel(clean_heat)
    heat_total = (
        clean_heat.group_by("aruanne_aasta")
        .agg(heat=pl.col("soojus_kokku").sum())
        .sort("aruanne_aasta")
    )
    heat_by_year = {
        int(r["aruanne_aasta"]): float(r["heat"]) for r in heat_total.iter_rows(named=True)
    }
    years = sorted(em["aruanne_aasta"].unique().to_list())
    reports = (
        em.group_by("aruanne_aasta")
        .agg(reports=pl.col("aruanne_id").n_unique())
        .sort("aruanne_aasta")
    )
    return {
        "meta": {
            "generated_utc": generated or datetime.now(UTC).isoformat(timespec="seconds"),
            "source": "keskkonnaandmed.envir.ee: stat_t_heitkogus_allikas_curr, "
            "t_soojatoodang_curr (KOTKAS facility reports)",
            "scope": "Facility-reported emissions of permitted/registered installations 2019-2025; "
            "NOT the national emission inventory.",
            "provenance": "Operator-declared annual reports; calculation methods are mixed "
            "(system-calculated, calculated, measured). No QC level is stated and none is assumed.",
            "units": {
                "emissions": "tonnes (converted from t/kg/mg)",
                "heat_electricity": "MWh (assumed; not in schema, inferred from fuel energy)",
            },
            "years": years,
            "pollutants": aa.POLLUTANTS,
            "nfr_names": aa.NFR_NAMES,
            "limits": [
                "The number of reporting installations changes between years; totals are not a "
                "complete or constant population.",
                "Only 2019-2025: no long-term trend; 7 points carry no significance test.",
                "Rows that share report, source, substance and fuel are kept as reported; the "
                "sensitivity block shows how much would change without them.",
            ],
            "data_quality": {"emissions": em_info, "heat": heat_info},
        },
        "coverage": rows(reports),
        "co2": rows(aa.yearly_totals(em, [aa.CO2, aa.CO2_BIO])),
        "pollutants": rows(aa.yearly_totals(em, list(aa.POLLUTANTS))),
        "sectors": {g: rows(aa.sector_totals(em, g)) for g in (aa.CO2, "NO2", "NH3")},
        "counties": {g: rows(aa.county_totals(em, g)) for g in (aa.CO2, "NO2")},
        "ets": rows(aa.ets_split(em, aa.CO2)),
        "concentration": {g: rows(aa.concentration(em, g)) for g in (aa.CO2, "NO2", "SO2")},
        "sensitivity": rows(aa.dedup_gap(em, groups)),
        "energy": {
            "by_fuel": rows(fuel),
            "heat_total_mwh": [
                {"year": y, "heat": round(v)} for y, v in sorted(heat_by_year.items())
            ],
            "climate_link": climate_link(heat_by_year, climate),
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--emissions", type=Path, required=True)
    ap.add_argument("--heat", type=Path, required=True)
    ap.add_argument("--climate", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=Path("out/airenergy"))
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    climate = None
    if args.climate and args.climate.exists():
        climate = json.loads(args.climate.read_text(encoding="utf-8"))
    result = build(pl.read_parquet(args.emissions), pl.read_parquet(args.heat), climate)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "airenergy.json").write_text(
        json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    LOG.info("wrote %s", args.out / "airenergy.json")


if __name__ == "__main__":
    main()
