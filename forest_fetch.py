#!/usr/bin/env python3
"""Fetch the statistical forest inventory (SMI) results table and describe its structure.

Table (public API ``keskkonnaandmed.envir.ee``): ``f_smi_tulemused`` (~330 000 rows).  Each row is
one published SMI result: a table number and report name, an indicator (``tunnus``), up to three
classification filters, a calculation type (sum or mean), the inventory year, the value
(``arvvaartus``) and its relative sampling error (``suhteline_viga``).

Because the grain is not documented, the script first writes ``forest_diagnostics.json``: which
tables and indicators exist, the distinct values of every classifying column, year coverage, the
share of null errors and rows that repeat on all descriptive columns.  The rows themselves are
aggregated survey statistics (no personal data); the Parquet stays in the workflow artifact.

Server facts used (measured for the waste table, see ``waste_probe.py``): at most 20 000 rows per
request, ~10 s per request, unordered paging unstable -> pages are totally ordered by every column.

Usage
-----
    uv run python forest_fetch.py --out out/forest
"""

from __future__ import annotations

import argparse
import json
import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import polars as pl

from postgrest import BASE_URL, Client

LOG = logging.getLogger("forest_fetch")
TABLE = "f_smi_tulemused"
PAGE = 20_000
VALUE = "arvvaartus"
ERROR = "suhteline_viga"
YEAR = "aasta"


def fetch_all(client: Client, workers: int, page: int = PAGE) -> pl.DataFrame:
    """Read every row in totally ordered pages, in parallel; verify the count."""
    total = client.count(TABLE) or 0
    head = client.rows(TABLE, limit=1)
    if not head:
        return pl.DataFrame()
    cols = list(head[0])
    order = ",".join(cols)

    def one(offset: int) -> list[dict[str, Any]]:
        local = Client(delay=client.delay, base_url=client.base_url, transport=client.transport)
        got: list[dict[str, Any]] = []
        want = min(page, total - offset)
        while len(got) < want:
            chunk = local.rows(TABLE, order=order, limit=want - len(got), offset=offset + len(got))
            if not chunk:
                break
            got += chunk
        return got

    with ThreadPoolExecutor(max_workers=workers) as pool:
        parts = list(pool.map(one, range(0, total, page)))
    rows = [r for p in parts for r in p]
    if len(rows) != total:
        raise RuntimeError(f"{TABLE}: read {len(rows)} rows, server says {total}")
    return pl.DataFrame(rows, infer_schema_length=None)


def classify_columns(df: pl.DataFrame) -> dict[str, list[str]]:
    """Split columns into measure, error, time and descriptive (classifying) columns."""
    skip = {VALUE, ERROR, YEAR, "ajatempel"}
    desc = [c for c in df.columns if c not in skip]
    return {"descriptive": desc}


DIMS = [
    "maakategooria", "omand", "maakond", "majandkategooria", "enamuspuuliik",
    "filtri_tunnus1", "filter1", "filtri_tunnus2", "filter2", "filtri_tunnus3", "filter3",
]  # fmt: skip


def table_shapes(
    df: pl.DataFrame, sample_year: int | None = None, max_values: int = 14
) -> list[dict[str, Any]]:
    """For every table: which classifying columns are filled, their values, and example rows.

    A "shape" is the set of non-null classifier columns plus indicator and calculation type;
    the latest year's rows give units and magnitudes at a glance.
    """
    dims = [c for c in DIMS if c in df.columns]
    year = sample_year or int(df[YEAR].cast(pl.Int64).max() or 0)
    shapes: list[dict[str, Any]] = []
    keyed = df.with_columns(
        pl.concat_str(
            [
                pl.when(pl.col(c).is_not_null()).then(pl.lit(c[:7] + "+")).otherwise(pl.lit(""))
                for c in dims
            ]
        ).alias("_shape")
    )
    for (tnr, name, tunnus, calc, shape), g in keyed.group_by(
        "tabeli_number", "aruande_nimi", "tunnus", "arvutus", "_shape", maintain_order=True
    ):
        entry: dict[str, Any] = {
            "tabeli_number": tnr, "aruande_nimi": name, "tunnus": tunnus, "arvutus": calc,
            "filled": shape, "rows": g.height,
            "years": [int(g[YEAR].cast(pl.Int64).min() or 0), int(g[YEAR].cast(pl.Int64).max() or 0)],
            "values": {},
        }  # fmt: skip
        for c in dims:
            n = g[c].drop_nulls().n_unique()
            if 0 < n <= max_values:
                entry["values"][c] = sorted(g[c].drop_nulls().unique().to_list())
            elif n:
                entry["values"][c] = f"{n} distinct"
        ex = g.filter(pl.col(YEAR) == year).sort(VALUE, descending=True, nulls_last=True).head(3)
        entry["examples_latest_year"] = ex.select(
            [c for c in (*dims, YEAR, "periood", VALUE, ERROR) if c in ex.columns]
        ).to_dicts()
        shapes.append(entry)
    return shapes


def diagnostics(df: pl.DataFrame, max_values: int = 60) -> dict[str, Any]:
    """Describe tables, indicators, classifiers, years and data quality."""
    desc = classify_columns(df)["descriptive"]
    out: dict[str, Any] = {"rows": df.height, "columns": df.columns}
    out["years"] = sorted(df[YEAR].unique().to_list())
    out["null_share"] = {c: round(df[c].null_count() / df.height, 4) for c in df.columns}
    if "tabeli_number" in df.columns and "aruande_nimi" in df.columns:
        out["tables"] = (
            df.group_by("tabeli_number", "aruande_nimi")
            .agg(
                rows=pl.len(),
                indicators=pl.col("tunnus").unique().sort() if "tunnus" in df.columns else None,
                first_year=pl.col(YEAR).min(),
                last_year=pl.col(YEAR).max(),
            )
            .sort("tabeli_number")
            .to_dicts()
        )
    values: dict[str, Any] = {}
    for c in desc:
        n = df[c].n_unique()
        entry: dict[str, Any] = {"distinct": n}
        if n <= max_values:
            entry["values"] = (
                df.group_by(c).agg(rows=pl.len()).sort("rows", descending=True).to_dicts()
            )
        values[c] = entry
    out["classifiers"] = values
    if "arvutus" in df.columns:
        out["calculation_types"] = df["arvutus"].unique().to_list()
    err = df[ERROR].drop_nulls() if ERROR in df.columns else pl.Series([], dtype=pl.Float64)
    out["relative_error"] = {
        "null_rows": df[ERROR].null_count() if ERROR in df.columns else None,
        "quantiles": {f"p{q}": err.quantile(q / 100) for q in (0, 10, 50, 90, 99, 100)}
        if len(err)
        else {},
        "share_over_0_5": (float(err.gt(0.5).sum()) / len(err)) if len(err) else None,
    }
    val = df[VALUE].drop_nulls()
    out["value"] = {
        "null_rows": df[VALUE].null_count(),
        "negative_rows": int((val < 0).sum()),
        "zero_rows": int((val == 0).sum()),
    }
    out["table_shapes"] = table_shapes(df)
    key = [c for c in desc if c in df.columns] + [YEAR]
    dup = df.group_by(key).agg(n=pl.len(), distinct=pl.col(VALUE).n_unique())
    out["duplicates"] = {
        "key_groups": dup.height,
        "groups_with_multiple_rows": int((dup["n"] > 1).sum()),
        "groups_with_different_values": int((dup["distinct"] > 1).sum()),
    }
    return out


def run(
    client: Client, out: Path, workers: int, fetch: Callable[..., pl.DataFrame] = fetch_all
) -> None:
    out.mkdir(parents=True, exist_ok=True)
    df = fetch(client, workers)
    df.write_parquet(out / "forest_raw.parquet")
    (out / "forest_diagnostics.json").write_text(
        json.dumps(diagnostics(df), ensure_ascii=False, indent=1, default=str), encoding="utf-8"
    )
    LOG.info("wrote %d rows", df.height)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("out/forest"))
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--delay", type=float, default=0.0)
    ap.add_argument("--base-url", default=BASE_URL)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(Client(delay=args.delay, base_url=args.base_url), args.out, args.workers)


if __name__ == "__main__":
    main()
