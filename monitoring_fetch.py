#!/usr/bin/env python3
"""Aggregate the national environmental monitoring table (``f_keskkonnaseire``, ~10 million rows).

One row of the table is one measured value or observation (long format).  This job reads one
calendar year (selected by ``seireaeg_algus``) in totally ordered pages of at most 20 000 rows,
aggregates every page to counts and numeric summaries per (year, programme, indicator group,
indicator, unit, observation group, monitoring-unit type, species) and writes a Parquet part
plus a JSON log with exact row counts.  Coordinates, observer names, laboratories and free text
are never requested.

Usage
-----
    uv run python monitoring_fetch.py --years 2019 --workers 3 --out out/parts
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl

from postgrest import BASE_URL, Client, PostgrestError

LOG = logging.getLogger("monitoring_fetch")
TABLE = "f_keskkonnaseire"
PAGE = 20_000
FIRST_YEAR = 1995
KEYS = [
    "seiretoo_seotud_programmi_nimi_i",
    "naitaja_grupp_selg",
    "naitaja_alamgrupp_selg",
    "naitaja_kood",
    "naitaja_nimetus",
    "naitaja_abr_unit",
    "vaatlusgrupp_selg",
    "seirekogum_tyyp",
    "liik_est",
    "takson_est",
]
VALUE = "vaartus_arv_moodetud"
TIME = "seireaeg_algus"
SELECT = [*KEYS, TIME, VALUE]  # exactly what aggregate() needs; also the total sort order
SCHEMA: dict[str, Any] = {**dict.fromkeys(KEYS, pl.Utf8), TIME: pl.Utf8, VALUE: pl.Float64}
GROUP = [*KEYS, "year"]


@dataclass(frozen=True)
class Page:
    """One ordered page of one year (``year`` 0 = before ``FIRST_YEAR``)."""

    year: int
    offset: int
    expected: int


def year_filter(year: int) -> dict[str, str]:
    if year == 0:
        return {TIME: f"lt.{FIRST_YEAR}-01-01"}
    return {"and": f"({TIME}.gte.{year}-01-01,{TIME}.lt.{year + 1}-01-01)"}


def make_pages(year_counts: dict[int, int], page: int = PAGE) -> list[Page]:
    out: list[Page] = []
    for y in sorted(year_counts, reverse=True):
        total = year_counts[y]
        out += [Page(y, o, min(page, total - o)) for o in range(0, total, page)]
    return out


def aggregate(rows: list[dict[str, Any]]) -> pl.DataFrame:
    """Counts and numeric summaries per key and year; null keys are kept (as null)."""
    if not rows:
        return pl.DataFrame()
    df = pl.DataFrame(rows, schema=SCHEMA, strict=False).with_columns(
        pl.col(TIME).str.slice(0, 4).cast(pl.Int32, strict=False).alias("year")
    )
    return df.group_by(GROUP).agg(
        rows=pl.len(),
        n_value=pl.col(VALUE).is_not_null().sum(),
        v_sum=pl.col(VALUE).sum(),
        v_min=pl.col(VALUE).min(),
        v_max=pl.col(VALUE).max(),
        n_negative=(pl.col(VALUE) < 0).sum(),
    )


def merge(parts: list[pl.DataFrame]) -> pl.DataFrame:
    parts = [p for p in parts if not p.is_empty()]
    if not parts:
        return pl.DataFrame()
    return (
        pl.concat(parts)
        .group_by(GROUP)
        .agg(
            rows=pl.col("rows").sum(),
            n_value=pl.col("n_value").sum(),
            v_sum=pl.col("v_sum").sum(),
            v_min=pl.col("v_min").min(),
            v_max=pl.col("v_max").max(),
            n_negative=pl.col("n_negative").sum(),
        )
        .sort("year", "naitaja_grupp_selg", "naitaja_kood")
    )


def fetch_page(page: Page, client: Client) -> tuple[pl.DataFrame, int]:
    rows: list[dict[str, Any]] = []
    while len(rows) < page.expected:
        got = client.rows(
            TABLE,
            select=",".join(SELECT),
            filters=year_filter(page.year),
            order=",".join(SELECT),
            limit=page.expected - len(rows),
            offset=page.offset + len(rows),
        )
        if not got:
            break
        rows += got
    return aggregate(rows), len(rows)


def run(
    year_counts: dict[int, int],
    out: Path,
    workers: int,
    budget_s: float,
    base_url: str = BASE_URL,
    tag: str = "all",
    page_size: int = PAGE,
) -> pl.DataFrame:
    out.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    pages = make_pages(year_counts, page_size)
    parts: list[pl.DataFrame] = []
    read: dict[int, int] = dict.fromkeys(year_counts, 0)
    failed: list[str] = []
    skipped = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch_page, p, Client(base_url=base_url)): p for p in pages}
        for fut in as_completed(futures):
            p = futures[fut]
            if time.monotonic() - start > budget_s:
                for f in futures:
                    f.cancel()
            if fut.cancelled():
                skipped += 1
                continue
            try:
                df, got = fut.result()
            except PostgrestError as exc:
                failed.append(f"{p}: {exc}"[:240])
                continue
            except Exception as exc:  # keep the run alive and report the page
                failed.append(f"{p}: {type(exc).__name__}: {exc}"[:240])
                continue
            read[p.year] += got
            parts.append(df)
            if len(parts) % 25 == 0:
                LOG.info("%d/%d pages, %d rows", len(parts), len(pages), sum(read.values()))
    try:
        result = merge(parts)
    except Exception as exc:
        failed.append(f"merge: {type(exc).__name__}: {exc}"[:240])
        result = pl.DataFrame()
    result.write_parquet(out / f"monitoring_part_{tag}.parquet")
    (out / f"monitoring_part_{tag}.json").write_text(
        json.dumps(
            {
                "tag": tag,
                "per_year": {
                    str(y): {"rows_expected": n, "rows_read": read[y]}
                    for y, n in sorted(year_counts.items())
                },
                "rows_read": sum(read.values()),
                "rows_expected": sum(year_counts.values()),
                "pages": len(pages),
                "skipped_over_budget": skipped,
                "failed": failed[:50],
                "seconds": round(time.monotonic() - start),
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    return result


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("out/parts"))
    ap.add_argument("--years", type=int, nargs="+", required=True, help="0 = before 1995")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--page-size", type=int, default=PAGE)
    ap.add_argument("--budget-min", type=float, default=38.0)
    ap.add_argument("--base-url", default=BASE_URL)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    client = Client(base_url=args.base_url)
    counts: dict[int, int] = {}
    for y in args.years:
        n = client.count(TABLE, year_filter(y)) or 0
        LOG.info("%d: %d rows", y, n)
        if n:
            counts[y] = n
    tag = "_".join(str(y) for y in args.years)
    run(counts, args.out, args.workers, args.budget_min * 60, args.base_url, tag, args.page_size)


if __name__ == "__main__":
    main()
