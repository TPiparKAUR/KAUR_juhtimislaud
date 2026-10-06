#!/usr/bin/env python3
"""Extract the rows of one monitoring indicator (optionally one species) with a few columns.

For indicators with a manageable number of rows (tens of thousands) the aggregate of
``monitoring_fetch.py`` is not enough (distributions and per-plot values are needed), so the rows
are read in totally ordered pages and written as Parquet together with a diagnostic summary.
Only the monitoring-site *code* is kept (no coordinates, observer or laboratory columns).

Usage
-----
    uv run python monitoring_extract.py --indicator "<naitaja_nimetus>" --out out/extract
"""

from __future__ import annotations

import argparse
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import polars as pl

from postgrest import BASE_URL, Client

LOG = logging.getLogger("monitoring_extract")
TABLE = "f_keskkonnaseire"
PAGE = 20_000
COLUMNS = [
    "naitaja_kood",
    "naitaja_nimetus",
    "naitaja_abr_unit",
    "vaartus_arv_moodetud",
    "vaartus_erimark",
    "vaartus_tapsustus_extra_tekst",
    "vaartus_tapsustus_extra_arv",
    "vaartus_muu",
    "vaartus_muu_tapsustus",
    "vaartus_mootmata",
    "seireaeg_algus",
    "seirekoht_kood",
    "seirekogum_tyyp",
    "liik_est",
    "takson_est",
    "isend_nr",
    "seiretoo_nimetus",
    "vaatlusgrupp_selg",
    "mootemaaramatus",
]


VALUE = "vaartus_arv_moodetud"


def normalise(df: pl.DataFrame) -> pl.DataFrame:
    """Same dtypes for every indicator (all-null columns are inferred as Null by polars)."""
    return df.with_columns(
        [pl.col(c).cast(pl.Float64) for c in COLUMNS if c == VALUE and c in df.columns]
        + [pl.col(c).cast(pl.Utf8) for c in COLUMNS if c != VALUE and c in df.columns]
    )


def extract(
    client: Client, filters: dict[str, str], workers: int, page: int = PAGE
) -> pl.DataFrame:
    total = client.count(TABLE, filters) or 0
    order = ",".join(COLUMNS)

    def one(offset: int) -> list[dict[str, Any]]:
        local = Client(base_url=client.base_url, transport=client.transport)
        got: list[dict[str, Any]] = []
        want = min(page, total - offset)
        while len(got) < want:
            chunk = local.rows(
                TABLE,
                select=order,
                filters=filters,
                order=order,
                limit=want - len(got),
                offset=offset + len(got),
            )
            if not chunk:
                break
            got += chunk
        return got

    with ThreadPoolExecutor(max_workers=workers) as pool:
        parts = list(pool.map(one, range(0, total, page)))
    rows = [r for p in parts for r in p]
    if len(rows) != total:
        raise RuntimeError(f"read {len(rows)} rows, server says {total}")
    return normalise(pl.DataFrame(rows, infer_schema_length=None)) if rows else pl.DataFrame()


def summary(df: pl.DataFrame, nested: bool = True) -> dict[str, Any]:
    if df.is_empty():
        return {"rows": 0}
    year = df["seireaeg_algus"].str.slice(0, 4).cast(pl.Int32, strict=False)
    d = df.with_columns(year.alias("year"))
    v = df["vaartus_arv_moodetud"].drop_nulls()
    per_indicator = (
        {
            str(name): summary(g.drop("naitaja_nimetus"), nested=False)
            if "naitaja_nimetus" in g.columns
            else {}
            for (name,), g in df.group_by("naitaja_nimetus")
        }
        if nested and df["naitaja_nimetus"].n_unique() > 1
        else {}
    )
    return {
        "per_indicator": per_indicator,
        "rows": df.height,
        "years": [d["year"].min(), d["year"].max()],
        "rows_by_year": d.group_by("year").agg(rows=pl.len()).sort("year").to_dicts(),
        "species": d["liik_est"].value_counts(sort=True).head(30).to_dicts(),
        "plots": df["seirekoht_kood"].n_unique(),
        "null_value": df["vaartus_arv_moodetud"].null_count(),
        "text_values": df["vaartus_tapsustus_extra_tekst"]
        .value_counts(sort=True)
        .head(20)
        .to_dicts(),
        "quantiles": {f"p{q}": v.quantile(q / 100) for q in (0, 5, 25, 50, 75, 95, 100)}
        if len(v)
        else {},
        "distinct_values": v.n_unique(),
        "value_counts_top": v.value_counts(sort=True).head(30).to_dicts(),
        "units": df["naitaja_abr_unit"].value_counts().to_dicts(),
        "special_marks": df["vaartus_erimark"].value_counts().to_dicts(),
        "plot_types": df["seirekogum_tyyp"].value_counts().to_dicts(),
    }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--indicator", action="append", required=True, help="naitaja_nimetus (exact)")
    ap.add_argument("--species", default=None, help="liik_est (exact)")
    ap.add_argument("--out", type=Path, default=Path("out/extract"))
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--base-url", default=BASE_URL)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    client = Client(base_url=args.base_url)
    frames = []
    for name in args.indicator:
        filters = {"naitaja_nimetus": f"eq.{name}"}
        if args.species:
            filters["liik_est"] = f"eq.{args.species}"
        LOG.info("extracting %s", name)
        frames.append(extract(client, filters, args.workers))
    df = pl.concat(frames, how="diagonal") if frames else pl.DataFrame()
    args.out.mkdir(parents=True, exist_ok=True)
    df.write_parquet(args.out / "monitoring_extract.parquet")
    (args.out / "monitoring_extract_summary.json").write_text(
        json.dumps(summary(df), ensure_ascii=False, indent=1, default=str), encoding="utf-8"
    )
    LOG.info("wrote %d rows", df.height)


if __name__ == "__main__":
    main()
