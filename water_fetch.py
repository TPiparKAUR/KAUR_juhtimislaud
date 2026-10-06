#!/usr/bin/env python3
"""Fetch the water-body status tables of the KAUR open-data API and describe their structure.

Tables (schema ``apijahiala``): surface water body register and status assessments
(``f_veekogumid``, ``f_veekogumi_seisundid``), pressures (``f_veekogumid_koormus``), groundwater
body status (``f_pohjaveekogumi_seisud``).  The tables are small (water bodies, not
measurements), so each is read completely in totally ordered pages and the row count is checked
against the server's exact count.  ``water_diagnostics.json`` lists per table: columns, null
shares, year coverage and the distinct values of every low-cardinality column with counts, so
that classification codes can be interpreted before any analysis is written.

Usage
-----
    uv run python water_fetch.py --out out/water
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

import polars as pl

from forest_fetch import fetch_all
from postgrest import BASE_URL, Client

LOG = logging.getLogger("water_fetch")
TABLES = (
    "f_veekogumid",
    "f_veekogumi_seisundid",
    "f_veekogumid_koormus",
    "f_pohjaveekogumi_seisud",
)
MAX_DISTINCT = 40


def describe(df: pl.DataFrame, max_distinct: int = MAX_DISTINCT) -> dict[str, Any]:
    """Columns, null shares, year coverage and value counts of low-cardinality columns."""
    out: dict[str, Any] = {"rows": df.height, "columns": {}}
    for name, dtype in df.schema.items():
        col = df[name]
        entry: dict[str, Any] = {
            "dtype": str(dtype),
            "null_share": round(col.null_count() / df.height, 4) if df.height else None,
            "distinct": col.n_unique(),
        }
        if 0 < col.n_unique() <= max_distinct:
            counts = df.group_by(name).agg(rows=pl.len()).sort("rows", descending=True)
            entry["values"] = [{"value": r[name], "rows": r["rows"]} for r in counts.to_dicts()]
        if dtype.is_numeric() and col.drop_nulls().len():
            entry["min"], entry["max"] = col.min(), col.max()
        out["columns"][name] = entry
    for year_col in ("aasta", "koormus_alg_aasta", "koormus_lopp_aasta"):
        if year_col in df.columns and df[year_col].drop_nulls().len():
            out.setdefault("years", {})[year_col] = sorted(
                df[year_col].drop_nulls().unique().to_list()
            )
    return out


def run(client: Client, out: Path, workers: int, tables: tuple[str, ...] = TABLES) -> None:
    out.mkdir(parents=True, exist_ok=True)
    diag: dict[str, Any] = {}
    for table in tables:
        df = fetch_all(client, workers, table=table)
        df.write_parquet(out / f"{table}.parquet")
        diag[table] = describe(df)
        LOG.info("%s: %d rows", table, df.height)
    (out / "water_diagnostics.json").write_text(
        # ASCII escapes make look-alike characters in class names visible.
        json.dumps(diag, ensure_ascii=True, indent=1, default=str),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("out/water"))
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--base-url", default=BASE_URL)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(Client(base_url=args.base_url), args.out, args.workers)


if __name__ == "__main__":
    main()
