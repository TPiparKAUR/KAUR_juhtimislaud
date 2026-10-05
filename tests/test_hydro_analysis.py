"""Tests for ``hydro_analysis`` with synthetic daily series of known shape (tests only)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from itertools import pairwise

import numpy as np
import polars as pl
import pytest

import hydro_analysis as ha


def daily(
    station: int,
    series: str,
    start: date,
    end: date,
    fn: Callable[[date], float],
    n_hours: int = 24,
) -> pl.DataFrame:
    days = (end - start).days + 1
    dates = [start + timedelta(d) for d in range(days)]
    return pl.DataFrame(
        {
            "jaam_kood": station,
            "series": series,
            "date": dates,
            "value": [fn(d) for d in dates],
            "n_hours": n_hours,
        },
        schema={
            "jaam_kood": pl.Int64,
            "series": pl.Utf8,
            "date": pl.Date,
            "value": pl.Float64,
            "n_hours": pl.Int32,
        },
    )


def seasonal(d: date) -> float:
    """Spring-flood-like: high in April, low in August (m3/s)."""
    return float(10 + 8 * np.cos(2 * np.pi * (d.timetuple().tm_yday - 100) / 365.25))


Q = daily(1, ha.Q_AVG, date(2013, 1, 1), date(2025, 12, 31), seasonal)
AREA = {1: 1000.0}


def test_valid_days_drops_incomplete_hours_and_wrong_series() -> None:
    inc = daily(1, ha.Q_AVG, date(2020, 1, 1), date(2020, 1, 10), lambda d: 1.0, n_hours=10)
    other = daily(1, ha.WT_AVG, date(2020, 1, 1), date(2020, 1, 10), lambda d: 1.0)
    df = pl.concat([inc, other, Q.head(5)])
    out = ha.valid_days(df, ha.Q_AVG)
    assert out.height == 5 and set(out["series"]) == {ha.Q_AVG}
    assert {"year", "month"} <= set(out.columns)


def test_monthly_means_requires_enough_days() -> None:
    q = ha.valid_days(
        Q.filter(
            ~(
                (pl.col("date").dt.year() == 2020)
                & (pl.col("date").dt.month() == 3)
                & (pl.col("date").dt.day() > 10)
            )
        ),
        ha.Q_AVG,
    )
    mm = ha.monthly_means(q)
    assert mm.filter((pl.col("year") == 2020) & (pl.col("month") == 3)).is_empty()
    assert mm.filter((pl.col("year") == 2020) & (pl.col("month") == 4)).height == 1


def test_regime_has_spring_peak_and_current_year() -> None:
    q = ha.valid_days(Q, ha.Q_AVG)
    r = ha.regime(q, current_year=2025)[1]
    med = dict(zip(r["months"], r["median"], strict=True))
    assert med[4] > med[8] and r["current_months"] == list(range(1, 13))
    assert all(lo <= m <= hi for lo, m, hi in zip(r["q10"], r["median"], r["q90"], strict=True))
    assert r["n_years"][0] == 12  # 2013-2024


def test_annual_runoff_units_and_incomplete_years() -> None:
    const = daily(1, ha.Q_AVG, date(2013, 1, 1), date(2015, 12, 31), lambda d: 10.0)
    short = daily(1, ha.Q_AVG, date(2016, 1, 1), date(2016, 6, 30), lambda d: 10.0)
    q = ha.valid_days(pl.concat([const, short]), ha.Q_AVG)
    a = ha.annual_runoff(q, AREA)
    assert a["year"].to_list() == [2013, 2014, 2015]  # 2016 incomplete
    row = a.row(0, named=True)
    assert row["specific_ls_km2"] == pytest.approx(10.0)  # 10 m3/s over 1000 km2
    assert row["runoff_mm"] == pytest.approx(
        10 * ha.SECONDS_PER_YEAR / 1_000_000, rel=1e-6
    )  # 315.6 mm
    unknown = ha.annual_runoff(q, {1: None})
    assert unknown["runoff_mm"].null_count() == unknown.height


def test_runoff_anomaly_is_percent_of_station_mean_and_needs_stations() -> None:
    rows = []
    for st in range(1, 7):
        for yr, f in ((2013, 0.5), (2014, 1.5)):
            rows.append({"jaam_kood": st, "year": yr, "runoff_mm": 100.0 * st * f})
    annual = pl.DataFrame(rows)
    out = ha.runoff_anomaly(annual)
    assert out["pct_of_mean"].to_list() == [pytest.approx(50.0), pytest.approx(150.0)]
    assert ha.runoff_anomaly(annual, min_stations=7).is_empty()


def test_flow_duration_monotonic_and_skips_short_or_unknown_area() -> None:
    q = ha.valid_days(Q, ha.Q_AVG)
    fdc = ha.flow_duration(q, AREA)[1]
    v = fdc["specific_ls_km2"]
    assert all(a >= b for a, b in pairwise(v))  # exceeded less often = larger
    assert ha.flow_duration(q, {1: None}) == {}
    assert ha.flow_duration(q.head(300), AREA) == {}


def test_annual_extremes_peak_and_q7min() -> None:
    qa = ha.valid_days(Q, ha.Q_AVG)
    qm = ha.valid_days(
        daily(1, ha.Q_MAX, date(2013, 1, 1), date(2025, 12, 31), lambda d: seasonal(d) * 1.5),
        ha.Q_MAX,
    )
    ex = ha.annual_extremes(qa, qm)
    assert ex.height == 13
    r = ex.row(0, named=True)
    assert 25 < r["peak"] <= 27.1 and 1.5 < r["q7min"] < 3.5


def test_water_temperature_annual_and_summer() -> None:
    wt = daily(
        1,
        ha.WT_AVG,
        date(2013, 1, 1),
        date(2015, 12, 31),
        lambda d: 10 - 9 * np.cos(2 * np.pi * (d.timetuple().tm_yday - 15) / 365.25),
    )
    out = ha.water_temperature(ha.valid_days(wt, ha.WT_AVG))
    assert out.height == 3
    r = out.row(0, named=True)
    assert 9.5 < r["annual_mean"] < 10.5 and r["summer_mean"] > r["annual_mean"] + 5


def test_coverage_share() -> None:
    q = ha.valid_days(Q.filter(pl.col("date").dt.year() == 2020).head(100), ha.Q_AVG)
    c = ha.coverage(q)
    assert c["share"][0] == pytest.approx(100 / 365.25)


def test_plausibility_reports_ranges() -> None:
    q = ha.valid_days(Q, ha.Q_AVG)
    wt = ha.valid_days(
        daily(1, ha.WT_AVG, date(2013, 1, 1), date(2013, 12, 31), lambda d: 5.0), ha.WT_AVG
    )
    out = ha.plausibility(ha.annual_runoff(q, AREA), wt)
    assert 9 < out["specific_runoff_ls_km2"]["median"] < 11
    assert out["water_temperature"]["min"] == 5.0
    assert ha.plausibility(ha.annual_runoff(q, AREA).clear(), wt.clear()) == {}


def test_spearman_detects_monotone_relation_and_handles_small_n() -> None:
    x = np.arange(15, dtype=float)
    r = ha.spearman(x, x**2)
    assert r["rho"] == pytest.approx(1.0) and r["lo"] > 0.9
    noise = ha.spearman(x, np.random.default_rng(0).normal(size=15))
    assert abs(noise["rho"]) < 0.7 and noise["hi"] - noise["lo"] > 0.4
    assert np.isnan(ha.spearman(x[:4], x[:4])["rho"])
