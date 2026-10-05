#!/usr/bin/env python3
"""Stream the national waste-statistics table and aggregate it while reading.

``f_jaatmeliikumine_fix_riik`` has about 20 million rows (2004-2025).  Measurements
(``waste_probe.py``) showed: aggregate selects are refused (PGRST123); every request takes about
9-11 s regardless of size; the server returns at most 20 000 rows per request; and *unordered*
offset pages are not stable (the same request returned different rows).  The table is therefore
read in totally ordered pages of 20 000 rows (ordered by every selected column, so rows that tie
are identical) and many pages are fetched in parallel.  Each page is reduced to sums immediately.
The number of rows read per year is compared with the server's exact count for that year.

Only aggregates (no operator or facility identity) are kept.  The unit of ``maht`` is not in the
schema and is assumed to be tonnes (to be confirmed with the data owner).

The work is split by year so that a lost runner costs one year, not the whole read: each run
(``--years 2022``) writes ``waste_part_<tag>.parquet`` plus a small JSON log, and
``waste_combine.py`` merges the parts and states which years are missing.

Usage
-----
    uv run python waste_fetch.py --out out/parts --years 2022 --workers 6
    uv run python waste_combine.py --parts out/parts --out out/waste_agg
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl

from postgrest import BASE_URL, Client, PostgrestError
from waste_explore import TABLE

LOG = logging.getLogger("waste_fetch")
KEYS = [
    "aasta",
    "maht_liik",
    "pohigrupp",
    "alamgrupp",
    "jaatmeliik",
    "jaatmeliik_nimi",
    "pohigrupp_nimi",
    "ohtlik_lipp",
    "biojaatmed_lipp",
    "reoveesetted_lipp",
    "metallijaatmed_lipp",
    "probleemtooted_lipp",
    "partner_riik_nimi",
    "riik",
    "materjali_kood",
    "materjali_nimetus",
]


# Explicit types: a JSON page whose amounts are all whole numbers (or whose partner column is
# entirely null) would otherwise infer a different dtype and break the final concatenation.
SCHEMA: dict[str, Any] = {
    **dict.fromkeys(KEYS, pl.Utf8),
    "aasta": pl.Int32,
    "materjali_kood": pl.Int64,
    "maht": pl.Float64,
}
SELECT = [*KEYS, "maht"]  # exactly the columns aggregate() needs; also the total sort order
PAGE = 20_000  # the server returns at most this many rows per request


@dataclass(frozen=True)
class Page:
    """One ordered page of one year: rows ``offset`` .. ``offset + expected - 1``."""

    year: int
    offset: int
    expected: int


def make_pages(year_counts: dict[int, int], page: int = PAGE) -> list[Page]:
    """All pages, newest year first (a time budget then drops the oldest data, not the latest)."""
    out: list[Page] = []
    for y in sorted(year_counts, reverse=True):
        total = year_counts[y]
        out += [Page(y, o, min(page, total - o)) for o in range(0, total, page)]
    return out


def aggregate(rows: list[dict[str, Any]]) -> pl.DataFrame:
    """Sum ``maht`` over the descriptive columns; keep row and negative-value counts."""
    if not rows:
        return pl.DataFrame()
    df = pl.DataFrame(rows, schema=SCHEMA, strict=False)
    return df.group_by(KEYS).agg(
        maht=pl.col("maht").sum(),
        rows=pl.len(),
        neg_rows=(pl.col("maht") < 0).sum(),
        neg_sum=pl.col("maht").filter(pl.col("maht") < 0).sum(),
    )


def merge(parts: list[pl.DataFrame]) -> pl.DataFrame:
    """Combine page aggregates: the same key can occur on several pages, so sum again."""
    parts = [p for p in parts if not p.is_empty()]
    if not parts:
        return pl.DataFrame()
    return (
        pl.concat(parts)
        .group_by(KEYS)
        .agg(
            maht=pl.col("maht").sum(),
            rows=pl.col("rows").sum(),
            neg_rows=pl.col("neg_rows").sum(),
            neg_sum=pl.col("neg_sum").sum(),
        )
        .sort("aasta", "maht_liik", "pohigrupp", "jaatmeliik")
    )


def fetch_page(page: Page, delay: float, client: Client | None = None) -> tuple[pl.DataFrame, int]:
    """Return (aggregate, rows read) for one page; continue if the server returns fewer rows."""
    client = client or Client(delay=delay)
    rows: list[dict[str, Any]] = []
    while len(rows) < page.expected:
        got = client.rows(
            TABLE,
            select=",".join(SELECT),
            filters={"aasta": f"eq.{page.year}"},
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
    delay: float,
    budget_s: float,
    fetch: Callable[[Page, float], tuple[pl.DataFrame, int]] = fetch_page,
    tag: str = "all",
    page_size: int = PAGE,
) -> pl.DataFrame:
    """Fetch all pages in parallel within a time budget; write the aggregate and a log."""
    out.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    pages = make_pages(year_counts, page_size)
    parts: list[pl.DataFrame] = []
    read: dict[int, int] = dict.fromkeys(year_counts, 0)
    failed: list[str] = []
    skipped = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch, p, delay): p for p in pages}
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
            except Exception as exc:  # keep the whole run alive; report the page
                failed.append(f"{p}: {type(exc).__name__}: {exc}"[:240])
                continue
            read[p.year] += got
            parts.append(df)
            if len(parts) % 25 == 0:
                LOG.info("%d/%d pages, %d rows", len(parts), len(pages), sum(read.values()))
    try:
        result = merge(parts)
    except Exception as exc:  # report instead of losing a long fetch silently
        failed.append(f"merge: {type(exc).__name__}: {exc}"[:240])
        result = pl.DataFrame()
    result.write_parquet(out / f"waste_part_{tag}.parquet")
    mismatches = [
        {"year": y, "expected": n, "got": read[y]} for y, n in year_counts.items() if read[y] != n
    ]
    (out / f"waste_part_{tag}.json").write_text(
        json.dumps(
            {
                "tag": tag,
                "per_year": {
                    str(y): {"rows_expected": n, "rows_read": read[y]}
                    for y, n in sorted(year_counts.items())
                },
                "years": sorted(year_counts),
                "pages": len(pages),
                "rows_read": sum(read.values()),
                "rows_expected": sum(year_counts.values()),
                "skipped_over_budget": skipped,
                "failed": failed[:50],
                "count_mismatches": mismatches,
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
    ap.add_argument("--years", type=int, nargs="*", help="years to read (default: all)")
    ap.add_argument("--first", type=int, default=2004)
    ap.add_argument("--last", type=int, default=2025)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--page-size", type=int, default=PAGE, help="rows per request (server cap)")
    ap.add_argument("--delay", type=float, default=0.0)
    ap.add_argument("--budget-min", type=float, default=35.0)
    ap.add_argument("--base-url", default=BASE_URL)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    years = args.years or list(range(args.first, args.last + 1))
    client = Client(delay=args.delay, base_url=args.base_url)
    counts: dict[int, int] = {}
    for y in years:
        n = client.count(TABLE, {"aasta": f"eq.{y}"}) or 0
        LOG.info("%d: %d rows", y, n)
        if n:
            counts[y] = n
    tag = "all" if not args.years else "_".join(str(y) for y in years)

    def fetch(page: Page, delay: float) -> tuple[pl.DataFrame, int]:
        return fetch_page(page, delay, Client(delay=delay, base_url=args.base_url))

    run(
        counts, args.out, args.workers, args.delay, args.budget_min * 60, fetch, tag, args.page_size
    )


if __name__ == "__main__":
    main()
