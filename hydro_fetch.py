#!/usr/bin/env python3
"""Fetch selected hydrological series from ``f_hydroseire`` and store them as daily values.

The hourly table is far too large to mirror (74 M rows).  For a chosen set of stations and
series, hourly values are streamed page by page and aggregated to **UTC calendar days**
immediately (mean for ``* avg``, max for ``* max``, min for ``* min``), together with the number
of hours that went into each day so that incomplete days can be rejected later.  Raw hourly
values are not kept or redistributed.

Usage
-----
    uv run python hydro_fetch.py --catalog hydro_catalog.json --out out/hydro
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import polars as pl

from postgrest import Client, PostgrestError

LOG = logging.getLogger("hydro_fetch")
TABLE = "f_hydroseire"
DEFAULT_SERIES = ("Äravool avg", "Äravool min", "Äravool max", "WT avg")
MIN_ROWS_FOR_SELECTION = 100_000
AGG = {"avg": "mean", "min": "min", "max": "max"}
SCHEMA = {"jaam_kood": pl.Int64, "timeline_ts_utc": pl.Utf8, "vaartus": pl.Float64}
DAILY_SCHEMA = {
    "jaam_kood": pl.Int64,
    "series": pl.Utf8,
    "date": pl.Date,
    "value": pl.Float64,
    "n_hours": pl.Int32,
}


def select_stations(catalog: dict[str, Any], series: str, min_rows: int) -> list[int]:
    """Stations whose catalogue lists ``series`` with at least ``min_rows`` rows."""
    out = []
    for st in catalog.get("stations", []):
        for s in st.get("series", []):
            if s["series"] == series and (s.get("rows") or 0) >= min_rows:
                out.append(int(st["jaam_kood"]))
    return sorted(set(out))


def daily(rows: list[dict[str, Any]], station: int, series: str) -> pl.DataFrame:
    """Aggregate hourly rows of one series to UTC days."""
    kind = series.rsplit(" ", 1)[-1]
    if kind not in AGG:
        raise ValueError(f"cannot aggregate series {series!r}")
    if not rows:
        return pl.DataFrame(schema=DAILY_SCHEMA)
    df = pl.DataFrame(rows, schema=SCHEMA).with_columns(
        date=pl.col("timeline_ts_utc").str.slice(0, 10).str.to_date("%Y-%m-%d")
    )
    expr = getattr(pl.col("vaartus"), AGG[kind])()
    return (
        df.filter(pl.col("vaartus").is_not_null())
        .group_by("date")
        .agg(value=expr, n_hours=pl.len().cast(pl.Int32))
        .with_columns(jaam_kood=pl.lit(station, dtype=pl.Int64), series=pl.lit(series))
        .select(list(DAILY_SCHEMA))
        .sort("date")
    )


def summarise(df: pl.DataFrame) -> list[dict[str, Any]]:
    """Per station and series: coverage and value quantiles (no raw data) for sanity checks."""
    if df.is_empty():
        return []
    g = (
        df.group_by("jaam_kood", "series")
        .agg(
            days=pl.len(),
            first=pl.col("date").min().cast(pl.Utf8),
            last=pl.col("date").max().cast(pl.Utf8),
            full_days=(pl.col("n_hours") == 24).sum(),
            q00=pl.col("value").min(),
            q05=pl.col("value").quantile(0.05),
            q50=pl.col("value").median(),
            q95=pl.col("value").quantile(0.95),
            q100=pl.col("value").max(),
            n_negative=(pl.col("value") < 0).sum(),
            n_zero=(pl.col("value") == 0).sum(),
        )
        .sort("jaam_kood", "series")
    )
    return g.to_dicts()


def fetch_one(station: int, series: str, delay: float) -> pl.DataFrame:
    client = Client(delay=delay)
    t0 = time.monotonic()
    rows = list(
        client.iter_rows(
            TABLE,
            select="jaam_kood,timeline_ts_utc,vaartus",
            filters={"jaam_kood": f"eq.{station}", "aegrida_nimi": f"eq.{series}"},
            order="timeline_ts_utc.asc",
        )
    )
    out = daily(rows, station, series)
    LOG.info(
        "%s / %s: %d hourly rows -> %d days in %.0fs",
        station,
        series,
        len(rows),
        out.height,
        time.monotonic() - t0,
    )
    return out


def run(
    stations: list[int],
    series: tuple[str, ...],
    out: Path,
    workers: int,
    delay: float,
    budget_s: float,
    fetch: Callable[[int, str, float], pl.DataFrame] = fetch_one,
) -> pl.DataFrame:
    """Fetch all (station, series) pairs with a few parallel workers; honour a time budget."""
    out.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    parts: list[pl.DataFrame] = []
    failed: list[str] = []
    tasks = [(st, s) for st in stations for s in series]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {}
        for st, s in tasks:
            futures[pool.submit(fetch, st, s, delay)] = (st, s)
        for fut in as_completed(futures):
            st, s = futures[fut]
            if time.monotonic() - start > budget_s:
                for f in futures:
                    f.cancel()
            try:
                parts.append(fut.result())
            except PostgrestError as exc:
                failed.append(f"{st}/{s}: {exc}"[:200])
            except Exception as exc:
                failed.append(f"{st}/{s}: {type(exc).__name__}"[:200])
    df = pl.concat(parts) if parts else pl.DataFrame(schema=DAILY_SCHEMA)
    df = df.sort("jaam_kood", "series", "date")
    df.write_parquet(out / "hydro_daily.parquet")
    (out / "hydro_fetch_log.json").write_text(
        json.dumps(
            {
                "tasks": len(tasks),
                "ok": len(parts),
                "failed": failed,
                "seconds": round(time.monotonic() - start),
                "summary": summarise(df),
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    return df


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--catalog", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("out/hydro"))
    ap.add_argument("--series", nargs="*", default=list(DEFAULT_SERIES))
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--delay", type=float, default=0.2)
    ap.add_argument("--budget-min", type=float, default=50.0)
    ap.add_argument("--min-rows", type=int, default=MIN_ROWS_FOR_SELECTION)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    stations = select_stations(catalog, "Äravool avg", args.min_rows)
    LOG.info("%d stations selected: %s", len(stations), stations)
    run(stations, tuple(args.series), args.out, args.workers, args.delay, args.budget_min * 60)


if __name__ == "__main__":
    main()
