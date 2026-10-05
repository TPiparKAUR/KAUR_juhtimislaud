"""Tests for ``climate_analysis`` on synthetic data with a known trend (tests only)."""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

import climate_analysis as ca

TREND_PER_DECADE = 0.5
STATIONS = [f"S{i}" for i in range(12)]


def synthetic(seed: int = 1, drop: set[tuple[str, int]] | None = None) -> pl.DataFrame:
    """Monthly temperature = seasonal cycle + station offset + known trend + noise."""
    rng = np.random.default_rng(seed)
    rows = []
    for i, st in enumerate(STATIONS):
        for year in range(1991, 2026):
            for month in range(1, 13):
                if drop and (st, year) in drop:
                    continue
                season = -8 * np.cos(2 * np.pi * (month - 1) / 12)
                value = 5 + i * 0.1 + season + TREND_PER_DECADE * (year - 2005) / 10
                rows.append((st, year, month, value + rng.normal(0, 0.6)))
    return pl.DataFrame(rows, schema=["jaam_kood", "aasta", "kuu", "vaartus"], orient="row")


def test_normals_require_enough_baseline_years() -> None:
    df = synthetic(drop={("S0", y) for y in range(1991, 2000)})  # S0 has only 21 baseline years
    n = ca.monthly_normals(df)
    assert "S0" not in n["jaam_kood"].to_list()
    assert n.filter(pl.col("jaam_kood") == "S1").height == 12


def test_anomalies_average_zero_over_baseline() -> None:
    df = synthetic()
    anom = ca.anomalies(df, ca.monthly_normals(df))
    base = anom.filter(pl.col("aasta").is_between(1991, 2020))
    mean = base["anom"].mean()
    assert isinstance(mean, float) and abs(mean) < 1e-9


def test_ratio_anomaly_excludes_zero_normals() -> None:
    df = pl.DataFrame(
        {
            "jaam_kood": ["A"] * 30,
            "aasta": list(range(1991, 2021)),
            "kuu": [1] * 30,
            "vaartus": [10.0] * 30,
        }
    )
    n = ca.monthly_normals(df)
    r = ca.anomalies(df, n, "ratio")
    assert r["anom"].to_list() == [100.0] * 30
    zero = df.with_columns(vaartus=pl.lit(0.0))
    assert ca.anomalies(zero, ca.monthly_normals(zero), "ratio").is_empty()
    with pytest.raises(ValueError, match="unknown anomaly kind"):
        ca.anomalies(df, n, "bogus")


def test_season_assigns_december_to_next_year() -> None:
    df = pl.DataFrame({"aasta": [2000, 2001, 2001], "kuu": [12, 1, 7]})
    out = ca.with_season(df)
    assert out["season"].to_list() == ["DJF", "DJF", "JJA"]
    assert out["season_year"].to_list() == [2001, 2001, 2001]


def test_annual_matrix_drops_incomplete_years() -> None:
    df = synthetic(drop={("S3", 2000)})
    df = df.filter(
        ~((pl.col("jaam_kood") == "S4") & (pl.col("aasta") == 2001) & (pl.col("kuu") == 5))
    )
    anom = ca.anomalies(df, ca.monthly_normals(df))
    mat, stations, years = ca.to_matrix(ca.station_period_matrix(anom, ["aasta"], 12), "aasta")
    s3, s4 = stations.index("S3"), stations.index("S4")
    assert np.isnan(mat[s3, years.index(2000)]) and np.isnan(mat[s4, years.index(2001)])
    assert not np.isnan(mat[stations.index("S0"), years.index(2000)])


def test_national_series_and_trend_recover_known_signal() -> None:
    df = synthetic()
    anom = ca.anomalies(df, ca.monthly_normals(df))
    mat, _, years = ca.to_matrix(ca.station_period_matrix(anom, ["aasta"], 12), "aasta")
    nat = ca.national_series(mat, reps=200)
    assert np.all(nat["lo"] <= nat["mean"]) and np.all(nat["mean"] <= nat["hi"])
    tr = ca.trend(np.array(years), nat["mean"], reps=300)
    assert tr["lo"] <= TREND_PER_DECADE <= tr["hi"]
    assert abs(tr["slope_per_decade"] - TREND_PER_DECADE) < 0.15


def test_national_series_masks_periods_with_too_few_stations() -> None:
    mat = np.full((6, 3), 1.0)
    mat[:3, 1] = np.nan  # only 3 stations left in period 1
    nat = ca.national_series(mat, min_stations=5, reps=50)
    assert np.isnan(nat["mean"][1]) and not np.isnan(nat["mean"][0])
    assert nat["n"].tolist() == [6, 3, 6]


def test_theil_sen_robust_to_outlier_and_short_input() -> None:
    x = np.arange(20, dtype=float)
    y = 2 * x
    y[5] = 500
    assert ca.theil_sen(x, y) == pytest.approx(2.0)
    assert np.isnan(ca.theil_sen(np.array([1.0, 2.0]), np.array([1.0, 2.0])))


def test_trend_needs_ten_values() -> None:
    out = ca.trend(np.arange(5), np.arange(5, dtype=float))
    assert np.isnan(out["slope_per_decade"]) and out["n"] == 5


def test_completeness_counts_months() -> None:
    df = synthetic(drop={("S2", 1995)})
    df = df.filter(
        ~((pl.col("jaam_kood") == "S1") & (pl.col("aasta") == 1996) & (pl.col("kuu") < 4))
    )
    c = ca.completeness(df)
    assert c.filter((pl.col("jaam_kood") == "S1") & (pl.col("aasta") == 1996))["months"][0] == 9
    assert c.filter((pl.col("jaam_kood") == "S2") & (pl.col("aasta") == 1995)).is_empty()


def test_ranks() -> None:
    r = ca.ranks(np.array([1.0, 3.0, np.nan, 2.0]), np.array([2000, 2001, 2002, 2003]), top=2)
    assert r == [(2001, 3.0), (2003, 2.0)]


def daily(values: list[float], year: int = 2000, station: str = "A") -> pl.DataFrame:
    return pl.DataFrame({"jaam_kood": station, "aasta": year, "vaartus": values})


def test_daily_indices_counts_and_completeness() -> None:
    n = 365
    tmax = daily([-1.0] * 10 + [26.0] * 20 + [31.0] * 5 + [10.0] * (n - 35))
    tmin = daily([-5.0] * 50 + [21.0] * 3 + [5.0] * (n - 53))
    prec = daily([0.0] * (n - 3) + [12.0, 25.0, 3.0])
    out = ca.daily_indices(tmax, tmin, prec).row(0, named=True)
    assert (out["ID"], out["SU25"], out["HD30"]) == (10, 25, 5)  # SU counts >=25 incl. >=30
    assert (out["FD"], out["TR20"]) == (50, 3)
    assert (out["R10"], out["R20"], out["Rx1day"]) == (2, 1, 25.0)
    short = ca.daily_indices(daily([30.0] * 200), tmin, prec)
    assert short["SU25"].null_count() == short.height  # tmax year too incomplete -> no value


def test_index_series_quantiles_and_min_stations() -> None:
    idx = pl.DataFrame(
        {
            "jaam_kood": [f"S{i}" for i in range(6)] + ["S0", "S1"],
            "aasta": [2000] * 6 + [2001] * 2,
            "FD": [10, 20, 30, 40, 50, 60, 5, 6],
        }
    )
    s = ca.index_series(idx, "FD", min_stations=5)
    assert s["aasta"] == [2000] and s["median"] == [35.0] and s["n"] == [6]


def test_precipitation_ratio_uses_totals_and_full_periods() -> None:
    rows = []
    for year in range(1991, 2021):
        rows += [("A", year, m, 10.0) for m in range(1, 13)]
    rows += [("A", 2021, m, 20.0) for m in range(1, 13)]  # exactly double
    rows += [("A", 2022, m, 20.0) for m in range(1, 12)]  # December missing -> dropped
    df = pl.DataFrame(rows, schema=["jaam_kood", "aasta", "kuu", "vaartus"], orient="row")
    out = ca.precipitation_ratio(df, ca.monthly_normals(df), ["aasta"], 12)
    by_year = dict(zip(out["aasta"].to_list(), out["anom"].to_list(), strict=True))
    assert by_year[2021] == pytest.approx(200.0) and by_year[2000] == pytest.approx(100.0)
    assert 2022 not in by_year
