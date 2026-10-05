"""Tests for ``run_climate`` (synthetic data with a known trend; network faked)."""

from __future__ import annotations

import json

import numpy as np
import polars as pl

import run_climate as rc
from tests.test_climate_analysis import STATIONS, TREND_PER_DECADE, synthetic


def synthetic_precip() -> pl.DataFrame:
    rng = np.random.default_rng(3)
    rows = [
        (st, y, m, 50.0 * (1 + 0.1 * rng.normal()))
        for st in STATIONS
        for y in range(1991, 2026)
        for m in range(1, 13)
    ]
    return pl.DataFrame(rows, schema=["jaam_kood", "aasta", "kuu", "vaartus"], orient="row")


def monthly_frame() -> pl.DataFrame:
    t = synthetic().with_columns(element_kood=pl.lit(rc.TEMP))
    p = synthetic_precip().with_columns(element_kood=pl.lit(rc.PREC))
    return pl.concat([t, p]).with_columns(jaam_nimi=pl.col("jaam_kood") + " nimi")


def test_build_structure_and_signal() -> None:
    stations = pl.DataFrame(
        {
            "jaam_kood": STATIONS,
            "laiuskraad": 58.0,
            "pikkuskraad": 25.0,
            "korgus_merepinnast_m": 10.0,
        }
    )
    elements = pl.DataFrame(
        {
            "element_kood": [rc.TEMP, rc.PREC],
            "element_nimi": ["T", "P"],
            "element_nimi_eng": ["Temp", "Prec"],
            "element_yhik_eng": ["°C", "mm"],
        }
    )
    out = rc.build(
        monthly_frame(),
        pl.DataFrame(),
        stations,
        elements,
        {"x": 1},
        reps=100,
        generated="2026-01-01T00:00:00+00:00",
    )
    json.dumps(out)  # must be JSON serialisable (no NaN/numpy leaks)
    assert (
        out["meta"]["baseline"] == [1991, 2020] and out["meta"]["elements"][rc.TEMP]["unit"] == "°C"
    )
    ann = out["temperature"]["annual"]
    assert ann["years"][0] == 1991 and ann["years"][-1] == 2025
    tr = ann["trend"]
    assert tr["lo"] <= TREND_PER_DECADE <= tr["hi"]
    assert set(out["temperature"]["seasonal"]) == {"DJF", "MAM", "JJA", "SON"}
    assert out["temperature"]["seasonal"]["DJF"]["years"][0] == 1992  # Dec 1990 is missing
    assert len(out["temperature"]["station_trends"]) == len(STATIONS)
    assert out["temperature"]["monthly_grid"]["cells"][0][:2] == [1991, 1]
    prec = out["precipitation"]["annual"]
    assert abs(np.mean([v for v in prec["mean"] if v is not None]) - 100) < 5  # % of normal
    assert out["completeness"]["cells"][0][2] == 12
    assert out["extremes"] == {}


def test_clean_nan() -> None:
    assert rc.clean_nan(np.array([1.23456, np.nan])) == [1.235, None]


def test_consistency_check() -> None:
    monthly = pl.DataFrame(
        {
            "jaam_kood": [rc.CHECK_STATION] * 2,
            "aasta": [2000, 2000],
            "kuu": [1, 2],
            "vaartus": [-5.0, 0.0],
            "element_kood": [rc.TEMP] * 2,
        }
    )
    days = pl.DataFrame(
        {
            "jaam_kood": rc.CHECK_STATION,
            "aasta": 2000,
            "kuu": [1] * 30 + [2] * 29,
            "vaartus": [-5.0] * 30 + [0.4] * 29,
        }
    )
    r = rc.consistency_check(monthly, days)
    assert r["months_compared"] == 2 and r["max_abs_diff_degC"] == 0.4
    assert rc.consistency_check(monthly, days.clear())["months_compared"] == 0
