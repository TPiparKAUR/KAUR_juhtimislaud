"""Hydrological analysis of daily discharge (``Äravool``) and water temperature (``WT``) series.

Input frames have the columns written by ``hydro_fetch``: ``jaam_kood``, ``series``, ``date``
(UTC day), ``value``, ``n_hours``.  Pure functions, no network.  Conventions:

* A day counts only with at least ``MIN_HOURS`` hourly values.
* A month needs ``MIN_DAYS_MONTH`` valid days, a year ``MIN_DAYS_YEAR``.
* Discharge is assumed to be in m3/s and water temperature in degC; the source schema does not
  state units, so ``plausibility`` checks the implied specific runoff and temperature range.
* Reference = all complete years of the station (a short record: no 30-year normal exists).
* Days are UTC days as aggregated by ``hydro_fetch``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import polars as pl

MIN_HOURS = 20
MIN_DAYS_MONTH = 25
MIN_DAYS_YEAR = 350
SECONDS_PER_YEAR = 365.25 * 86400
Q_AVG, Q_MIN, Q_MAX, WT_AVG = "Äravool avg", "Äravool min", "Äravool max", "WT avg"
EXCEEDANCE = [0.5, 1, 2, 5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 98, 99, 99.5]


def valid_days(df: pl.DataFrame, series: str) -> pl.DataFrame:
    """Complete days of one series with year/month columns added."""
    return (
        df.filter((pl.col("series") == series) & (pl.col("n_hours") >= MIN_HOURS))
        .filter(pl.col("value").is_not_null())
        .with_columns(year=pl.col("date").dt.year(), month=pl.col("date").dt.month())
    )


def monthly_means(q: pl.DataFrame) -> pl.DataFrame:
    """Mean of daily values per station, year and month (months with enough valid days)."""
    return (
        q.group_by("jaam_kood", "year", "month")
        .agg(value=pl.col("value").mean(), n=pl.len())
        .filter(pl.col("n") >= MIN_DAYS_MONTH)
        .drop("n")
    )


def regime(q: pl.DataFrame, current_year: int) -> dict[int, dict[str, Any]]:
    """Seasonal regime per station: monthly q10/median/q90 over past years + the current year."""
    mm = monthly_means(q)
    out: dict[int, dict[str, Any]] = {}
    for st in sorted(mm["jaam_kood"].unique().to_list()):
        s = mm.filter(pl.col("jaam_kood") == st)
        past = s.filter(pl.col("year") < current_year)
        stats = (
            past.group_by("month")
            .agg(
                q10=pl.col("value").quantile(0.10),
                median=pl.col("value").median(),
                q90=pl.col("value").quantile(0.90),
                n_years=pl.len(),
            )
            .sort("month")
        )
        cur = s.filter(pl.col("year") == current_year).sort("month")
        out[int(st)] = {
            "months": stats["month"].to_list(),
            "q10": stats["q10"].to_list(),
            "median": stats["median"].to_list(),
            "q90": stats["q90"].to_list(),
            "n_years": stats["n_years"].to_list(),
            "current_year": current_year,
            "current_months": cur["month"].to_list(),
            "current": cur["value"].to_list(),
        }
    return out


def annual_runoff(q: pl.DataFrame, area_km2: Mapping[int, float | None]) -> pl.DataFrame:
    """Annual mean discharge and runoff depth (mm) for years with enough valid days.

    depth [mm] = Q [m3/s] * seconds / (A [km2] * 1000)
    """
    g = (
        q.group_by("jaam_kood", "year")
        .agg(q_mean=pl.col("value").mean(), n_days=pl.len())
        .filter(pl.col("n_days") >= MIN_DAYS_YEAR)
    )
    area = pl.DataFrame(
        {"jaam_kood": list(area_km2), "area": [a if a else None for a in area_km2.values()]},
        schema={"jaam_kood": pl.Int64, "area": pl.Float64},
    )
    return (
        g.join(area, on="jaam_kood", how="left")
        .with_columns(
            specific_ls_km2=pl.col("q_mean") * 1000 / pl.col("area"),
            runoff_mm=pl.col("q_mean") * SECONDS_PER_YEAR / (pl.col("area") * 1000),
        )
        .sort("jaam_kood", "year")
    )


def runoff_anomaly(annual: pl.DataFrame, min_stations: int = 5) -> pl.DataFrame:
    """National runoff index: mean over stations of annual runoff as % of the station's own mean."""
    ref = annual.filter(pl.col("runoff_mm").is_not_null()).with_columns(
        pct=100.0 * pl.col("runoff_mm") / pl.col("runoff_mm").mean().over("jaam_kood")
    )
    return (
        ref.group_by("year")
        .agg(
            pct_of_mean=pl.col("pct").mean(),
            p10=pl.col("pct").quantile(0.1),
            p90=pl.col("pct").quantile(0.9),
            n=pl.len(),
        )
        .filter(pl.col("n") >= min_stations)
        .sort("year")
    )


def flow_duration(
    q: pl.DataFrame, area_km2: Mapping[int, float | None]
) -> dict[int, dict[str, Any]]:
    """Exceedance curve of specific discharge (l/s/km2) per station over all valid days."""
    out: dict[int, dict[str, Any]] = {}
    for st in sorted(q["jaam_kood"].unique().to_list()):
        a = area_km2.get(int(st))
        vals = q.filter(pl.col("jaam_kood") == st)["value"].to_numpy()
        if not a or len(vals) < 3 * 365:
            continue
        # value exceeded p% of the time = the (100-p)th percentile
        curve = np.percentile(vals, [100 - p for p in EXCEEDANCE]) * 1000 / a
        out[int(st)] = {
            "p": EXCEEDANCE,
            "specific_ls_km2": [round(float(v), 3) for v in curve],
            "n_days": len(vals),
        }
    return out


def annual_extremes(q_avg: pl.DataFrame, q_max: pl.DataFrame) -> pl.DataFrame:
    """Per station-year: highest hourly-maximum discharge and the lowest 7-day mean (``Q7min``).

    Years need >= MIN_DAYS_YEAR valid days of the daily-mean series.
    """
    full = (
        q_avg.group_by("jaam_kood", "year")
        .agg(n_days=pl.len())
        .filter(pl.col("n_days") >= MIN_DAYS_YEAR)
    )
    peaks = q_max.group_by("jaam_kood", "year").agg(peak=pl.col("value").max())
    rows = []
    for (st, yr), grp in q_avg.sort("date").group_by(["jaam_kood", "year"], maintain_order=True):
        v = grp["value"].to_numpy()
        if len(v) < 7:
            continue
        roll = np.convolve(v, np.ones(7) / 7, mode="valid")  # consecutive valid days assumed
        rows.append({"jaam_kood": st, "year": yr, "q7min": float(roll.min())})
    q7 = pl.DataFrame(rows, schema={"jaam_kood": pl.Int64, "year": pl.Int32, "q7min": pl.Float64})
    return (
        full.join(peaks, on=["jaam_kood", "year"], how="left")
        .join(q7, on=["jaam_kood", "year"], how="left")
        .drop("n_days")
        .sort("jaam_kood", "year")
    )


def water_temperature(wt: pl.DataFrame) -> pl.DataFrame:
    """Per station-year: annual mean and summer (JJA) mean of daily mean water temperature."""
    annual = (
        wt.group_by("jaam_kood", "year")
        .agg(annual_mean=pl.col("value").mean(), n_days=pl.len())
        .filter(pl.col("n_days") >= MIN_DAYS_YEAR)
    )
    summer = (
        wt.filter(pl.col("month").is_between(6, 8))
        .group_by("jaam_kood", "year")
        .agg(summer_mean=pl.col("value").mean(), n_summer=pl.len())
        .filter(pl.col("n_summer") >= 80)
    )
    return annual.join(summer, on=["jaam_kood", "year"], how="left").sort("jaam_kood", "year")


def coverage(q: pl.DataFrame) -> pl.DataFrame:
    """Share of the year with a valid daily mean, per station and year (0-1)."""
    return (
        q.group_by("jaam_kood", "year")
        .agg(valid=pl.len())
        .with_columns(share=(pl.col("valid") / 365.25).clip(0, 1))
        .sort("jaam_kood", "year")
    )


def plausibility(annual: pl.DataFrame, wt: pl.DataFrame) -> dict[str, Any]:
    """Sanity checks that stand in for the missing unit metadata (not a proof of the unit)."""
    spec = annual["specific_ls_km2"].drop_nulls()
    out: dict[str, Any] = {}
    if len(spec):
        out["specific_runoff_ls_km2"] = {
            "median": round(float(spec.median()), 2),  # type: ignore[arg-type]
            "min": round(float(spec.min()), 2),  # type: ignore[arg-type]
            "max": round(float(spec.max()), 2),  # type: ignore[arg-type]
            "note": "Assuming m3/s; order-of-magnitude check only.",
        }
    if not wt.is_empty():
        v = wt["value"]
        out["water_temperature"] = {
            "min": round(float(v.min()), 2),  # type: ignore[arg-type]
            "max": round(float(v.max()), 2),  # type: ignore[arg-type]
            "note": "Assuming degC; physical range for open water is about -1..35.",
        }
    return out


def spearman(x: np.ndarray, y: np.ndarray, reps: int = 2000, seed: int = 11) -> dict[str, float]:
    """Spearman rank correlation with a percentile bootstrap interval (pairs resampled)."""
    ok = ~(np.isnan(x) | np.isnan(y))
    x, y = x[ok], y[ok]
    n = len(x)
    out = {"rho": float("nan"), "lo": float("nan"), "hi": float("nan"), "n": float(n)}
    if n < 6:
        return out

    def rho(a: np.ndarray, b: np.ndarray) -> float:
        ra = np.argsort(np.argsort(a)).astype(float)
        rb = np.argsort(np.argsort(b)).astype(float)
        if ra.std() == 0 or rb.std() == 0:
            return float("nan")
        return float(np.corrcoef(ra, rb)[0, 1])

    out["rho"] = rho(x, y)
    rng = np.random.default_rng(seed)
    boots = []
    for _ in range(reps):
        idx = rng.integers(0, n, n)
        boots.append(rho(x[idx], y[idx]))
    out["lo"], out["hi"] = (float(v) for v in np.nanpercentile(boots, [2.5, 97.5]))
    return out
