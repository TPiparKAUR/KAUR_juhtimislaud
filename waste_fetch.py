#!/usr/bin/env python3
"""Stream the national waste-statistics table and aggregate it while reading.

``f_jaatmeliikumine_fix_riik`` has about 20 million rows (2004-2025) and the server refuses
aggregate selects (PostgREST error PGRST123).  Rows are therefore read in small, completely
ordered slices (year x ``maht_liik`` x main group), so that offset paging is stable and the
server never sorts a whole year per page, and each slice is reduced to sums immediately.  Slices
for values *not* in the known lists catch types or groups that appear only in some years; the
returned row count of every slice is compared with the server's exact count.

Only aggregates (no operator or facility identity) are kept.  The unit of ``maht`` is not in the
schema and is assumed to be tonnes (to be confirmed with the data owner).

Usage
-----
    uv run python waste_fetch.py --out out/waste_agg --first 2004 --last 2025
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

from postgrest import Client, PostgrestError
from waste_explore import GRAIN_COLUMNS, TABLE

LOG = logging.getLogger("waste_fetch")
TYPES = (
    "Eksport",
    "Import",
    "Jäätmete sortimine või muu eeltöötlus (toimingud R12)",
    "Jäätmeteke",
    "Ladestatud prügilasse",
    "Laoseis aasta alguses",
    "Laoseis aasta lõpul",
    "Määratlemata käitlemine",
    "Saadud kodumajapidamistelt",
    "Taaskasutamine",
)
GROUPS = tuple(f"{i:02d}" for i in range(1, 21))
KEYS = [
    "aasta",
    "maht_liik",
    "pohigrupp",
    "alamgrupp",
    "jaatmeliik",
    "ohtlik_lipp",
    "biojaatmed_lipp",
    "reoveesetted_lipp",
    "metallijaatmed_lipp",
    "probleemtooted_lipp",
    "partner_riik_nimi",
    "riik",
    "materjali_kood",
]


@dataclass(frozen=True)
class Task:
    """One slice of the table; ``maht_liik``/``pohigrupp`` of ``None`` mean 'not in the list'."""

    year: int
    maht_liik: str | None
    pohigrupp: str | None

    def filters(self) -> dict[str, str]:
        f = {"aasta": f"eq.{self.year}"}
        f["maht_liik"] = (
            f"eq.{self.maht_liik}"
            if self.maht_liik is not None
            else "not.in.(" + ",".join(f'"{t}"' for t in TYPES) + ")"
        )
        f["pohigrupp"] = (
            f"eq.{self.pohigrupp}"
            if self.pohigrupp is not None
            else "not.in.(" + ",".join(f'"{g}"' for g in GROUPS) + ")"
        )
        return f


def make_tasks(first: int, last: int) -> list[Task]:
    """All slices, newest year first (so a time budget drops the oldest data, not the latest)."""
    out: list[Task] = []
    for y in range(last, first - 1, -1):
        for t in (*TYPES, None):
            out += [Task(y, t, g) for g in (*GROUPS, None)]
    return out


def aggregate(rows: list[dict[str, Any]]) -> pl.DataFrame:
    """Sum ``maht`` over the descriptive columns; keep row and negative-value counts."""
    if not rows:
        return pl.DataFrame()
    df = pl.DataFrame(rows, infer_schema_length=None).select(*KEYS, "maht")
    return df.group_by(KEYS).agg(
        maht=pl.col("maht").sum(),
        rows=pl.len(),
        neg_rows=(pl.col("maht") < 0).sum(),
        neg_sum=pl.col("maht").filter(pl.col("maht") < 0).sum(),
    )


def fetch_one(task: Task, delay: float) -> tuple[pl.DataFrame, int, int]:
    """Return (aggregate, server count, rows read) for one slice."""
    client = Client(delay=delay)
    flt = task.filters()
    expected = client.count(TABLE, flt) or 0
    if expected == 0:
        return pl.DataFrame(), 0, 0
    rows = list(
        client.iter_rows(
            TABLE, select=",".join(GRAIN_COLUMNS), filters=flt, order=",".join(GRAIN_COLUMNS)
        )
    )
    return aggregate(rows), expected, len(rows)


def run(
    tasks: list[Task],
    out: Path,
    workers: int,
    delay: float,
    budget_s: float,
    fetch: Callable[[Task, float], tuple[pl.DataFrame, int, int]] = fetch_one,
) -> pl.DataFrame:
    """Run slices in parallel within a time budget; write the aggregate and a log."""
    out.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    parts: list[pl.DataFrame] = []
    mismatches: list[dict[str, Any]] = []
    failed: list[str] = []
    skipped = 0
    rows_read = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch, t, delay): t for t in tasks}
        for fut in as_completed(futures):
            t = futures[fut]
            if time.monotonic() - start > budget_s:
                for f in futures:
                    f.cancel()
            if fut.cancelled():
                skipped += 1
                continue
            try:
                df, expected, got = fut.result()
            except PostgrestError as exc:
                failed.append(f"{t}: {exc}"[:240])
                continue
            except Exception as exc:  # keep the whole run alive; report the slice
                failed.append(f"{t}: {type(exc).__name__}"[:240])
                continue
            rows_read += got
            if expected != got:
                mismatches.append({"task": t.__dict__, "expected": expected, "got": got})
            if not df.is_empty():
                parts.append(df)
    result = pl.concat(parts) if parts else pl.DataFrame()
    if not result.is_empty():
        result = result.sort("aasta", "maht_liik", "pohigrupp", "jaatmeliik")
    result.write_parquet(out / "waste_agg.parquet")
    (out / "waste_fetch_log.json").write_text(
        json.dumps(
            {
                "tasks": len(tasks),
                "rows_read": rows_read,
                "skipped_over_budget": skipped,
                "failed": failed[:50],
                "count_mismatches": mismatches[:50],
                "seconds": round(time.monotonic() - start),
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("out/waste_agg"))
    ap.add_argument("--first", type=int, default=2004)
    ap.add_argument("--last", type=int, default=2025)
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--delay", type=float, default=0.2)
    ap.add_argument("--budget-min", type=float, default=100.0)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(
        make_tasks(args.first, args.last),
        args.out,
        args.workers,
        args.delay,
        args.budget_min * 60,
    )


if __name__ == "__main__":
    main()
