#!/usr/bin/env python3
"""Probe the national waste-statistics table and diagnose what one row means.

Table (public API ``keskkonnaandmed.envir.ee``): ``f_jaatmeliikumine_fix_riik`` (about 20 million
rows, 2004-2025, columns for waste type, volume type ``maht_liik`` and amount ``maht``).  The unit
of ``maht`` and the meaning of ``maht_liik`` are not in the schema, so this script learns them
from the data before any sum is computed:

* does the server support aggregation (``select=maht.sum()``)?  If so the full table can be
  summarised without streaming 20 million rows;
* row counts per year, distinct ``maht_liik`` values and their totals per year;
* a bounded sample of one year for grain checks (duplicates, negatives, flag columns).

Only aggregated diagnostics are written; no operator or facility names are stored.

Usage
-----
    uv run python waste_explore.py --out out/waste --grain-year 2022
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

import polars as pl

from postgrest import Client, PostgrestError

LOG = logging.getLogger("waste_explore")
TABLE = "f_jaatmeliikumine_fix_riik"
SMALL_TABLE = "jaatmeliik_kogus"
GRAIN_COLUMNS = [
    "aasta",
    "pohigrupp",
    "alamgrupp",
    "jaatmeliik",
    "jaatmeliik_nimi",
    "partner_riik_nimi",
    "ohtlik_lipp",
    "biojaatmed_lipp",
    "reoveesetted_lipp",
    "metallijaatmed_lipp",
    "probleemtooted_lipp",
    "riik",
    "yhte_liiki_tegevus",
    "komplekstegevus",
    "materjali_kood",
    "materjali_nimetus",
    "maht_liik",
    "maht",
]


def probe_aggregation(client: Client) -> dict[str, Any]:
    """Return whether PostgREST aggregate selects work, plus the by-year/type totals if so."""
    out: dict[str, Any] = {"supported": False}
    try:
        rows = client.rows(
            TABLE, select="aasta,maht_liik,maht.sum(),count()", order="aasta.asc", limit=5000
        )
    except PostgrestError as exc:
        out["error"] = str(exc)[:300]
        return out
    out["supported"] = bool(rows) and any("sum" in r for r in rows)
    out["rows"] = rows[:2000]
    return out


def year_counts(client: Client, years: range) -> list[dict[str, Any]]:
    return [{"aasta": y, "rows": client.count(TABLE, {"aasta": f"eq.{y}"})} for y in years]


def grain_diagnostics(df: pl.DataFrame) -> dict[str, Any]:
    """Diagnose one year of rows: types, flags, duplicates, negatives and magnitude."""
    out: dict[str, Any] = {"rows": df.height}
    out["by_maht_liik"] = (
        df.group_by("maht_liik")
        .agg(rows=pl.len(), total=pl.col("maht").sum(), neg=(pl.col("maht") < 0).sum())
        .sort("maht_liik")
        .to_dicts()
    )
    out["by_type_group"] = (
        df.group_by("maht_liik", "pohigrupp")
        .agg(rows=pl.len(), total=pl.col("maht").sum())
        .sort("maht_liik", "pohigrupp")
        .to_dicts()
    )
    key = [c for c in df.columns if c != "maht"]
    dup = df.group_by(key).agg(n=pl.len(), distinct=pl.col("maht").n_unique())
    out["duplicates"] = {
        "key_groups": dup.height,
        "groups_with_multiple_rows": dup.filter(pl.col("n") > 1).height,
        "groups_with_different_amounts": dup.filter(pl.col("distinct") > 1).height,
    }
    out["maht_quantiles"] = {
        f"p{q}": df["maht"].quantile(q / 100) for q in (0, 1, 25, 50, 75, 99, 100)
    }
    out["flags"] = {
        c: df.group_by(c).agg(rows=pl.len(), total=pl.col("maht").sum()).sort(c).to_dicts()
        for c in (
            "ohtlik_lipp",
            "biojaatmed_lipp",
            "reoveesetted_lipp",
            "metallijaatmed_lipp",
            "probleemtooted_lipp",
        )
    }
    out["partner_countries"] = (
        df.filter(pl.col("maht_liik") == "Eksport")
        .group_by("partner_riik_nimi")
        .agg(rows=pl.len(), total=pl.col("maht").sum())
        .sort("total", descending=True)
        .head(15)
        .to_dicts()
    )
    out["activity_codes"] = (
        df.group_by("yhte_liiki_tegevus")
        .agg(rows=pl.len(), total=pl.col("maht").sum())
        .sort("total", descending=True)
        .head(30)
        .to_dicts()
    )
    return out


def write_diag(out: Path, diag: dict[str, Any]) -> None:
    (out / "diagnostics.json").write_text(
        json.dumps(diag, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
    )


def run(client: Client, out: Path, grain_year: int, first: int, last: int, grain_rows: int) -> None:
    """Write diagnostics after every stage so a slow later stage never loses earlier results."""
    out.mkdir(parents=True, exist_ok=True)
    diag: dict[str, Any] = {"table": TABLE, "total_rows": client.count(TABLE)}
    write_diag(out, diag)
    diag["aggregation"] = probe_aggregation(client)
    LOG.info("aggregation supported: %s", diag["aggregation"]["supported"])
    write_diag(out, diag)
    diag["year_counts"] = year_counts(client, range(first, last + 1))
    diag["small_table_rows"] = client.count(SMALL_TABLE)
    write_diag(out, diag)
    LOG.info("reading up to %d rows of %d for grain checks", grain_rows, grain_year)
    # No ORDER BY: sorting a million rows for every page is what made the first attempt crawl.
    # The sample is the first rows the server returns; it is used for grain, not for totals.
    rows = list(
        client.iter_rows(
            TABLE,
            select=",".join(GRAIN_COLUMNS),
            filters={"aasta": f"eq.{grain_year}"},
            max_rows=grain_rows,
        )
    )
    df = pl.DataFrame(rows, infer_schema_length=None)
    diag["grain_year"] = grain_year
    diag["grain_sample"] = True
    # Offset paging without ORDER BY may repeat or skip rows, so duplicate counts are indicative.
    diag["duplicates_reliable"] = False
    diag["grain"] = grain_diagnostics(df)
    write_diag(out, diag)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("out/waste"))
    ap.add_argument("--grain-year", type=int, default=2022)
    ap.add_argument("--first", type=int, default=2004)
    ap.add_argument("--last", type=int, default=2025)
    ap.add_argument("--grain-rows", type=int, default=100_000)
    ap.add_argument("--delay", type=float, default=0.2)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(
        Client(delay=args.delay),
        args.out,
        args.grain_year,
        args.first,
        args.last,
        args.grain_rows,
    )


if __name__ == "__main__":
    main()
