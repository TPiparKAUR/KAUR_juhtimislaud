"""Climate analysis of KAUR open data (``f_kliima_*``): anomalies, trends, completeness, extremes.

Pure functions on Polars frames and NumPy arrays; no network access.  Definitions follow common
climatological practice and every choice that affects results is a named constant here:

* Baseline = WMO climatological standard normal 1991-2020.  A station-month normal needs at
  least ``MIN_NORMAL_YEARS`` of the 30 baseline years.
* Anomalies are computed per station (value minus own normal; precipitation as % of normal) and
  only then averaged, so changes in the station network do not bias the national series.
* Seasons use the meteorological definition (DJF = Dec of the *previous* year + Jan + Feb).
* A station-period value is accepted only when all its months are present.
* The national value is the unweighted mean over stations (no area weighting).  Its 95%
  interval comes from bootstrapping stations and captures station-sampling spread only - not
  measurement error, siting or homogenisation uncertainty.
* Trends are Theil-Sen slopes with a moving-block bootstrap interval (block = 3 years) to respect
  short-term persistence.
"""

from __future__ import annotations

import warnings
from typing import Any

import numpy as np
import polars as pl

BASE_START, BASE_END = 1991, 2020
MIN_NORMAL_YEARS = 25
MIN_STATIONS = 5
BOOTSTRAP_REPS = 1000
BLOCK_LEN = 3
SEASONS = {"DJF": (12, 1, 2), "MAM": (3, 4, 5), "JJA": (6, 7, 8), "SON": (9, 10, 11)}
MIN_DAYS_PER_YEAR = 355


def monthly_normals(
    df: pl.DataFrame,
    base: tuple[int, int] = (BASE_START, BASE_END),
    min_years: int = MIN_NORMAL_YEARS,
) -> pl.DataFrame:
    """Per station and calendar month: mean over the baseline years and how many years it used."""
    return (
        df.filter(pl.col("aasta").is_between(base[0], base[1]) & pl.col("vaartus").is_not_null())
        .group_by("jaam_kood", "kuu")
        .agg(normal=pl.col("vaartus").mean(), n_years=pl.len())
        .filter(pl.col("n_years") >= min_years)
    )


def anomalies(df: pl.DataFrame, normals: pl.DataFrame, kind: str = "diff") -> pl.DataFrame:
    """Join normals and compute ``anom`` (``diff``: value-normal; ``ratio``: 100*value/normal)."""
    joined = df.filter(pl.col("vaartus").is_not_null()).join(
        normals, on=["jaam_kood", "kuu"], how="inner"
    )
    if kind == "diff":
        return joined.with_columns(anom=pl.col("vaartus") - pl.col("normal"))
    if kind == "ratio":
        return joined.filter(pl.col("normal") > 0).with_columns(
            anom=100.0 * pl.col("vaartus") / pl.col("normal")
        )
    raise ValueError(f"unknown anomaly kind: {kind}")


def with_season(df: pl.DataFrame) -> pl.DataFrame:
    """Add ``season`` (DJF/MAM/JJA/SON) and ``season_year`` (December counts to the next year)."""
    month_to_season = {m: s for s, ms in SEASONS.items() for m in ms}
    return df.with_columns(
        season=pl.col("kuu").replace_strict(month_to_season),
        season_year=pl.when(pl.col("kuu") == 12)
        .then(pl.col("aasta") + 1)
        .otherwise(pl.col("aasta")),
    )


def station_period_matrix(
    anom: pl.DataFrame, period_cols: list[str], n_required: int
) -> pl.DataFrame:
    """Mean anomaly per station and period, keeping only periods with all ``n_required`` months."""
    return (
        anom.group_by("jaam_kood", *period_cols)
        .agg(anom=pl.col("anom").mean(), n=pl.len())
        .filter(pl.col("n") == n_required)
        .drop("n")
    )


def to_matrix(df: pl.DataFrame, period: str) -> tuple[np.ndarray, list[str], list[int]]:
    """Pivot to a ``stations x periods`` float array (NaN = missing)."""
    wide = df.pivot(on=period, index="jaam_kood", values="anom").sort("jaam_kood")
    periods = sorted(int(c) for c in wide.columns if c != "jaam_kood")
    stations = wide["jaam_kood"].to_list()
    mat = np.full((len(stations), len(periods)), np.nan)
    for j, p in enumerate(periods):
        mat[:, j] = wide[str(p)].cast(pl.Float64).fill_null(np.nan).to_numpy()
    return mat, stations, periods


def national_series(
    mat: np.ndarray,
    min_stations: int = MIN_STATIONS,
    reps: int = BOOTSTRAP_REPS,
    seed: int = 20260205,
) -> dict[str, np.ndarray]:
    """Mean over stations per period with a station-bootstrap 95% interval."""
    n_st = np.sum(~np.isnan(mat), axis=0)
    rng = np.random.default_rng(seed)
    boot = np.full((reps, mat.shape[1]), np.nan)
    with warnings.catch_warnings():  # all-NaN columns are expected and masked below
        warnings.simplefilter("ignore", RuntimeWarning)
        mean = np.nanmean(mat, axis=0)
        for r in range(reps):
            idx = rng.integers(0, mat.shape[0], mat.shape[0])
            boot[r] = np.nanmean(mat[idx], axis=0)
        lo, hi = np.nanpercentile(boot, [2.5, 97.5], axis=0)
    ok = n_st >= min_stations
    return {
        "mean": np.where(ok, mean, np.nan),
        "lo": np.where(ok, lo, np.nan),
        "hi": np.where(ok, hi, np.nan),
        "n": n_st,
    }


def theil_sen(x: np.ndarray, y: np.ndarray) -> float:
    """Median of pairwise slopes; NaNs are dropped."""
    ok = ~(np.isnan(x) | np.isnan(y))
    x, y = x[ok], y[ok]
    if len(x) < 3:
        return float("nan")
    i, j = np.triu_indices(len(x), k=1)
    dx = x[j] - x[i]
    keep = dx != 0
    return float(np.median((y[j] - y[i])[keep] / dx[keep]))


def trend(
    years: np.ndarray,
    values: np.ndarray,
    reps: int = BOOTSTRAP_REPS,
    seed: int = 7,
    block: int = BLOCK_LEN,
) -> dict[str, float]:
    """Theil-Sen slope per decade with a moving-block bootstrap 95% interval."""
    ok = ~np.isnan(values)
    x, y = years[ok].astype(float), values[ok]
    n = len(x)
    out = {"slope_per_decade": float("nan"), "lo": float("nan"), "hi": float("nan"), "n": n}
    if n < 10:
        return out
    out["slope_per_decade"] = 10 * theil_sen(x, y)
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block))
    slopes = np.empty(reps)
    for r in range(reps):
        starts = rng.integers(0, n - block + 1, n_blocks)
        idx = np.concatenate([np.arange(s, s + block) for s in starts])[:n]
        slopes[r] = theil_sen(x[idx], y[idx])
    out["lo"], out["hi"] = (10 * float(v) for v in np.nanpercentile(slopes, [2.5, 97.5]))
    return out


def precipitation_ratio(
    df: pl.DataFrame, normals: pl.DataFrame, period_cols: list[str], n_required: int
) -> pl.DataFrame:
    """Period precipitation total as % of the period's normal total, per station.

    Uses ratio of totals (not the mean of monthly ratios, which over-weights dry months).
    Periods lacking any of the ``n_required`` months are dropped.
    """
    joined = df.filter(pl.col("vaartus").is_not_null()).join(
        normals, on=["jaam_kood", "kuu"], how="inner"
    )
    return (
        joined.group_by("jaam_kood", *period_cols)
        .agg(total=pl.col("vaartus").sum(), norm=pl.col("normal").sum(), n=pl.len())
        .filter((pl.col("n") == n_required) & (pl.col("norm") > 0))
        .with_columns(anom=100.0 * pl.col("total") / pl.col("norm"))
        .select("jaam_kood", *period_cols, "anom")
    )


def completeness(df: pl.DataFrame) -> pl.DataFrame:
    """Months with a value per station and year (0-12)."""
    return (
        df.filter(pl.col("vaartus").is_not_null())
        .group_by("jaam_kood", "aasta")
        .agg(months=pl.len())
        .sort("jaam_kood", "aasta")
    )


def ranks(values: np.ndarray, years: np.ndarray, top: int = 5) -> list[tuple[int, float]]:
    """The ``top`` warmest/highest periods as (year, value)."""
    ok = ~np.isnan(values)
    order = np.argsort(-values[ok])[:top]
    return [(int(years[ok][i]), float(values[ok][i])) for i in order]


# ---- daily indices (ETCCDI-style) -------------------------------------------------------------


def daily_indices(tmax: pl.DataFrame, tmin: pl.DataFrame, prec: pl.DataFrame) -> pl.DataFrame:
    """Per station-year counts of frost/ice/summer/hot days, tropical nights, heavy rain.

    FD: Tmin<0, ID: Tmax<0, SU25: Tmax>=25, HD30: Tmax>=30, TR20: Tmin>=20 (all deg C),
    R10/R20: precipitation >= 10/20 mm, Rx1day: maximum 1-day precipitation (mm).
    A station-year is kept for an index only when it has >= ``MIN_DAYS_PER_YEAR`` valid days of
    the variable it uses.
    """

    def per_year(df: pl.DataFrame, aggs: list[pl.Expr]) -> pl.DataFrame:
        return (
            df.filter(pl.col("vaartus").is_not_null())
            .group_by("jaam_kood", "aasta")
            .agg(pl.len().alias("n_days"), *aggs)
            .filter(pl.col("n_days") >= MIN_DAYS_PER_YEAR)
            .drop("n_days")
        )

    v = pl.col("vaartus")
    hot = per_year(
        tmax,
        [(v < 0).sum().alias("ID"), (v >= 25).sum().alias("SU25"), (v >= 30).sum().alias("HD30")],
    )
    cold = per_year(tmin, [(v < 0).sum().alias("FD"), (v >= 20).sum().alias("TR20")])
    rain = per_year(
        prec, [(v >= 10).sum().alias("R10"), (v >= 20).sum().alias("R20"), v.max().alias("Rx1day")]
    )
    out = hot.join(cold, on=["jaam_kood", "aasta"], how="full", coalesce=True)
    return out.join(rain, on=["jaam_kood", "aasta"], how="full", coalesce=True).sort(
        "jaam_kood", "aasta"
    )


def index_series(idx: pl.DataFrame, name: str, min_stations: int = MIN_STATIONS) -> dict[str, Any]:
    """Across-station median and inter-quartile range per year for one index."""
    g = (
        idx.filter(pl.col(name).is_not_null())
        .group_by("aasta")
        .agg(
            median=pl.col(name).median(),
            q25=pl.col(name).quantile(0.25),
            q75=pl.col(name).quantile(0.75),
            n=pl.len(),
        )
        .filter(pl.col("n") >= min_stations)
        .sort("aasta")
    )
    return {c: g[c].to_list() for c in g.columns}
