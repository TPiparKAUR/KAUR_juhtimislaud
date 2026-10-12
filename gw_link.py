#!/usr/bin/env python3
"""Can groundwater abstraction be linked to approved groundwater reserves?

``t_awtabel002_01_curr`` (abstraction by intake) and ``f_pohjaveevarud`` (approved reserves per
deposit) have no documented foreign key.  This probe tests whether the code columns of the two
tables share values (after trimming and upper-casing) and reports, per column pair, how many
distinct codes match and which share of the abstracted volume sits on matching intakes.  Only
counts and shares are written: no codes, names or coordinates.

Usage
-----
    uv run python gw_link.py --raw out/wateruse --out out/gwlink
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

import polars as pl

LOG = logging.getLogger("gw_link")
ABSTRACTION_CODES = ("veehaardekood", "jaamakood")
RESERVE_CODES = ("kood", "kkr_kood", "veemaardla_kood")


def norm(s: pl.Series) -> pl.Series:
    return s.cast(pl.Utf8).str.strip_chars().str.to_uppercase()


def link_report(gw: pl.DataFrame, res: pl.DataFrame) -> list[dict[str, Any]]:
    """One row per (abstraction column, reserve column) pair with match counts."""
    total_m3 = float(gw["aastakokku"].sum() or 0.0)
    out = []
    for a in ABSTRACTION_CODES:
        if a not in gw.columns:
            continue
        g = gw.with_columns(norm(gw[a]).alias("_k")).filter(pl.col("_k").is_not_null())
        keys_a = set(g["_k"].unique().to_list())
        for r in RESERVE_CODES:
            if r not in res.columns:
                continue
            keys_r = set(norm(res[r]).drop_nulls().unique().to_list())
            common = keys_a & keys_r
            m3 = float(g.filter(pl.col("_k").is_in(list(common)))["aastakokku"].sum() or 0.0)
            out.append(
                {
                    "abstraction_column": a,
                    "reserve_column": r,
                    "distinct_abstraction": len(keys_a),
                    "distinct_reserve": len(keys_r),
                    "matching_codes": len(common),
                    "matching_volume_share": m3 / total_m3 if total_m3 else None,
                }
            )
    return out


INTAKE_CODES = ("id_text", "kkr_kood", "kood_grupp")


def registry_report(
    gw: pl.DataFrame, intakes: pl.DataFrame, boreholes: pl.DataFrame
) -> list[dict[str, Any]]:
    """Match abstraction codes to the intake register; count boreholes with a groundwater body."""
    total_m3 = float(gw["aastakokku"].sum() or 0.0)
    out = []
    if "veehaare_id" in boreholes.columns and "pohjaveekogum_id" in boreholes.columns:
        with_body = set(
            boreholes.filter(pl.col("pohjaveekogum_id").is_not_null())["veehaare_id"]
            .drop_nulls()
            .to_list()
        )
    else:
        with_body = set()
    g = gw.with_columns(norm(gw["veehaardekood"]).alias("_k")).filter(pl.col("_k").is_not_null())
    keys_a = set(g["_k"].unique().to_list())
    for c in INTAKE_CODES:
        if c not in intakes.columns:
            continue
        ik = intakes.with_columns(norm(intakes[c]).alias("_k")).filter(pl.col("_k").is_not_null())
        common = keys_a & set(ik["_k"].unique().to_list())
        ids = set(ik.filter(pl.col("_k").is_in(list(common)))["id"].to_list())
        m3 = float(g.filter(pl.col("_k").is_in(list(common)))["aastakokku"].sum() or 0.0)
        out.append(
            {
                "intake_column": c,
                "distinct_abstraction": len(keys_a),
                "distinct_intake": ik["_k"].n_unique(),
                "matching_codes": len(common),
                "matching_volume_share": m3 / total_m3 if total_m3 else None,
                "matched_intakes_with_borehole_body": len(ids & with_body),
                "matched_intakes": len(ids),
            }
        )
    return out


def build(gw: pl.DataFrame, res: pl.DataFrame) -> dict[str, Any]:
    return {
        "abstraction_rows": gw.height,
        "reserve_rows": res.height,
        "pairs": link_report(gw, res),
    }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw", type=Path, default=Path("out/wateruse"))
    ap.add_argument("--registry", type=Path, default=None, help="dir with intake/borehole parquet")
    ap.add_argument("--out", type=Path, default=Path("out/gwlink"))
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    gw = pl.read_parquet(args.raw / "t_awtabel002_01_curr.parquet")
    res = pl.read_parquet(args.raw / "f_pohjaveevarud.parquet")
    result = build(gw, res)
    reg = args.registry
    if reg is not None and (reg / "f_veehaarded.parquet").exists():
        result["registry"] = registry_report(
            gw,
            pl.read_parquet(reg / "f_veehaarded.parquet"),
            pl.read_parquet(reg / "f_veehaarded_puurauk.parquet"),
        )
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "gw_link.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    LOG.info("wrote %s", args.out / "gw_link.json")


if __name__ == "__main__":
    main()
