"""Tests for ``run_hydro`` with synthetic daily data."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date

import numpy as np
import polars as pl
import pytest

import hydro_analysis as ha
import run_hydro as rh
from tests.test_hydro_analysis import daily, seasonal


def scaled(k: float, wet_years: set[int]) -> Callable[[date], float]:
    return lambda d: k * seasonal(d) * (1.4 if d.year in wet_years else 1.0)


def water_temp(d: date) -> float:
    return float(8 - 7 * np.cos(2 * np.pi * (d.timetuple().tm_yday - 15) / 365.25))


def frame(codes: list[int], wet_years: set[int]) -> pl.DataFrame:
    start, end = date(2013, 1, 1), date(2025, 12, 31)
    parts = []
    for c in codes:
        for series, f in ((ha.Q_AVG, 1.0), (ha.Q_MAX, 1.5), (ha.Q_MIN, 0.6)):
            parts.append(daily(c, series, start, end, scaled(f * c, wet_years)))
        parts.append(daily(c, ha.WT_AVG, start, end, water_temp))
    return pl.concat(parts)


CATALOG = {
    "stations": [
        {
            "jaam_kood": c,
            "jaam_nimi": f"J{c}",
            "veekogu_nimi": f"R{c}",
            "valgala_suurus_km2": 100.0 * c,
            "jaam_laiuskraad": 58.0,
            "jaam_pikkuskraad": 25.0,
        }
        for c in range(1, 8)
    ]
}


def test_build_structure_and_json_safe() -> None:
    out = rh.build(frame(list(range(1, 8)), {2020}), CATALOG, generated="2026-01-01T00:00:00+00:00")
    json.dumps(out)
    assert len(out["stations"]) == 7 and out["stations"][0]["name"] == "J1"
    assert out["meta"]["current_year"] == 2025
    assert set(out["regime"]) == {str(c) for c in range(1, 8)}
    assert out["annual"]["1"]["years"][0] == 2013
    assert out["national_runoff"]["year"][0] == 2013
    spike = dict(
        zip(out["national_runoff"]["year"], out["national_runoff"]["pct_of_mean"], strict=True)
    )
    assert spike[2020] > 120 > spike[2014]  # the synthetic wet year stands out
    assert (
        out["flow_duration"]["3"]["specific_ls_km2"][0]
        > out["flow_duration"]["3"]["specific_ls_km2"][-1]
    )
    assert out["extremes"]["1"]["peak"][0] > out["extremes"]["1"]["q7min"][0]
    assert 5 < out["water_temperature"]["1"]["annual_mean"][0] < 11
    assert out["plausibility"]["specific_runoff_ls_km2"]["median"] > 0
    assert out["climate_link"] is None


def test_climate_link_pairs_years_and_reports_spearman() -> None:
    national = pl.DataFrame(
        {"year": list(range(2013, 2026)), "pct_of_mean": [float(v) for v in range(80, 145, 5)]}
    )
    climate = {
        "precipitation": {
            "annual": {
                "years": list(range(2013, 2026)),
                "mean": [float(v) for v in range(90, 116, 2)],
            }
        }
    }
    link = rh.link_with_climate(national, climate)
    assert link is not None and link["spearman"]["rho"] == pytest.approx(1.0)
    assert rh.link_with_climate(national, None) is None
    assert rh.link_with_climate(national, {"precipitation": None}) is None
    few = {"precipitation": {"annual": {"years": [2013, 2014], "mean": [100.0, 90.0]}}}
    assert rh.link_with_climate(national, few) is None


def test_num_handles_nan_and_none() -> None:
    assert rh.num(float("nan")) is None and rh.num(None) is None and rh.num(1.23456, 2) == 1.23
