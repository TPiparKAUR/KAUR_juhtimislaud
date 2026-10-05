#!/usr/bin/env python3
"""Fetch facility-level air-emission and heat-production reports (KOTKAS); diagnose their grain.

Tables (public API ``keskkonnaandmed.envir.ee``): ``stat_t_heitkogus_allikas_curr`` (emissions per
source and substance) and ``t_soojatoodang_curr`` (fuel, heat and electricity per facility).  The
aim is to learn, from the data themselves, what one row means (which columns repeat across
rows, which units occur, which substance groups exist) before any sum is computed.

Only aggregated diagnostics are written (``diagnostics.json``); company and facility identities are
never stored.  Raw rows are kept as Parquet in the workflow artifact only.

Usage
-----
    uv run python airenergy_explore.py --out out/airenergy
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

import polars as pl

from postgrest import Client

LOG = logging.getLogger("airenergy_explore")
EMISSIONS = "stat_t_heitkogus_allikas_curr"
HEAT = "t_soojatoodang_curr"
EMISSION_COLUMNS = [
    "aruanne_id",
    "aruanne_aasta",
    "heiteallikas_kood",
    "aine_nimetus",
    "aine_stat_grupp",
    "aine_kogus_maarus_yhik",
    "aine_yhik_maarus",
    "aine_arvestus_meetod",
    "tegevusala_nfr",
    "tegevusala_snap",
    "tegevusala_snap_name",
    "tegevuskoht_maakond_nimi_curr",
    "kytus_kood",
    "kytus_nimetus",
    "kytus_kogus",
    "kytus_yhik",
    "ets_kohuslane",
    "eprtr_kohuslane",
    "aruande_esitaja_emtak_nimetus",
    "kaitis_pohitegevus_emtak_nimetus",
]
HEAT_COLUMNS = [
    "aruanne_id",
    "aruanne_aasta",
    "snap",
    "kytus_liik",
    "kytus_kood",
    "kytus_nimetus_val",
    "kytus_kogus",
    "kytus_yhik",
    "soojus_kokku",
    "soojus_omatarve",
    "soojus_myyk",
    "elekter_kokku",
    "elekter_omatarve",
    "elekter_myyk",
    "ets_kohuslane",
    "tegevuskoht_maakond_nimi_curr",
    "kaitis_pohitegevus_emtak_nimetus",
]
TO_TONNES = {"t": 1.0, "kg": 1e-3, "mg": 1e-9}


def fetch(client: Client, table: str, columns: list[str], order: str) -> pl.DataFrame:
    rows = list(client.iter_rows(table, select=",".join(columns), order=order))
    LOG.info("%s: %d rows", table, len(rows))
    return pl.DataFrame(rows, infer_schema_length=None)


def emission_diagnostics(df: pl.DataFrame) -> dict[str, Any]:
    df = df.with_columns(
        amount_t=pl.col("aine_kogus_maarus_yhik").cast(pl.Float64)
        * pl.col("aine_yhik_maarus").replace_strict(
            TO_TONNES, default=None, return_dtype=pl.Float64
        )
    )
    out: dict[str, Any] = {"rows": df.height, "columns": df.columns}
    out["rows_by_year"] = (
        df.group_by("aruanne_aasta")
        .agg(rows=pl.len(), reports=pl.col("aruanne_id").n_unique())
        .sort("aruanne_aasta")
        .to_dicts()
    )
    out["units"] = df.group_by("aine_yhik_maarus").agg(n=pl.len()).to_dicts()
    out["unknown_unit_rows"] = df.filter(pl.col("amount_t").is_null()).height
    out["negative_or_zero"] = {
        "negative": df.filter(pl.col("amount_t") < 0).height,
        "zero": df.filter(pl.col("amount_t") == 0).height,
    }
    out["groups"] = (
        df.group_by("aine_stat_grupp")
        .agg(
            rows=pl.len(),
            names=pl.col("aine_nimetus").n_unique(),
            example=pl.col("aine_nimetus").first(),
            total_t=pl.col("amount_t").sum(),
        )
        .sort("total_t", descending=True, nulls_last=True)
        .to_dicts()
    )
    out["by_year_group_t"] = (
        df.group_by("aruanne_aasta", "aine_stat_grupp")
        .agg(total_t=pl.col("amount_t").sum())
        .sort("aruanne_aasta", "aine_stat_grupp")
        .to_dicts()
    )
    out["nfr"] = (
        df.group_by("tegevusala_nfr")
        .agg(rows=pl.len())
        .sort("rows", descending=True)
        .head(40)
        .to_dicts()
    )
    out["methods"] = df.group_by("aine_arvestus_meetod").agg(n=pl.len()).to_dicts()
    # Grain checks: does the fuel quantity repeat across substances of the same source/report?
    key = ["aruanne_id", "heiteallikas_kood", "kytus_kood"]
    fuel = (
        df.filter(pl.col("kytus_kood").is_not_null())
        .group_by(key)
        .agg(n=pl.len(), distinct_amounts=pl.col("kytus_kogus").n_unique())
    )
    out["fuel_repeats"] = {
        "groups": fuel.height,
        "groups_with_multiple_rows": fuel.filter(pl.col("n") > 1).height,
        "multi_row_groups_with_single_amount": fuel.filter(
            (pl.col("n") > 1) & (pl.col("distinct_amounts") == 1)
        ).height,
    }
    dup = df.group_by("aruanne_id", "heiteallikas_kood", "aine_nimetus", "kytus_kood").agg(
        n=pl.len()
    )
    out["duplicate_substance_rows"] = {
        "groups": dup.height,
        "with_n_gt_1": dup.filter(pl.col("n") > 1).height,
    }
    out["ets_flag"] = df.group_by("ets_kohuslane").agg(rows=pl.len()).to_dicts()
    return out


def heat_diagnostics(df: pl.DataFrame) -> dict[str, Any]:
    out: dict[str, Any] = {"rows": df.height, "columns": df.columns}
    out["rows_by_year"] = (
        df.group_by("aruanne_aasta")
        .agg(rows=pl.len(), reports=pl.col("aruanne_id").n_unique())
        .sort("aruanne_aasta")
        .to_dicts()
    )
    out["fuel_units"] = df.group_by("kytus_yhik").agg(n=pl.len()).to_dicts()
    out["fuel_types"] = (
        df.group_by("kytus_liik", "kytus_nimetus_val")
        .agg(rows=pl.len(), total=pl.col("kytus_kogus").sum())
        .sort("total", descending=True, nulls_last=True)
        .head(40)
        .to_dicts()
    )
    per_report = df.group_by("aruanne_id").agg(
        n=pl.len(),
        heat_unique=pl.col("soojus_kokku").n_unique(),
        el_unique=pl.col("elekter_kokku").n_unique(),
    )
    out["heat_repeats"] = {
        "reports": per_report.height,
        "multi_row_reports": per_report.filter(pl.col("n") > 1).height,
        "multi_row_with_constant_heat": per_report.filter(
            (pl.col("n") > 1) & (pl.col("heat_unique") == 1)
        ).height,
        "multi_row_with_constant_electricity": per_report.filter(
            (pl.col("n") > 1) & (pl.col("el_unique") == 1)
        ).height,
    }
    rep = df.group_by("aruanne_id", "aruanne_aasta").agg(
        heat=pl.col("soojus_kokku").max(), electricity=pl.col("elekter_kokku").max()
    )
    out["report_level_totals_by_year"] = (
        rep.group_by("aruanne_aasta")
        .agg(heat=pl.col("heat").sum(), electricity=pl.col("electricity").sum(), reports=pl.len())
        .sort("aruanne_aasta")
        .to_dicts()
    )
    out["snap"] = (
        df.group_by("snap").agg(rows=pl.len()).sort("rows", descending=True).head(20).to_dicts()
    )
    out["quantiles_heat"] = {q: df["soojus_kokku"].quantile(q) for q in (0.5, 0.9, 0.99, 1.0)}
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("out/airenergy"))
    ap.add_argument("--delay", type=float, default=0.2)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    client = Client(delay=args.delay)
    args.out.mkdir(parents=True, exist_ok=True)
    em = fetch(client, EMISSIONS, EMISSION_COLUMNS, "aruanne_id,heiteallikas_kood,aine_nimetus")
    heat = fetch(client, HEAT, HEAT_COLUMNS, "aruanne_id,kytus_kood")
    em.write_parquet(args.out / "emissions.parquet")
    heat.write_parquet(args.out / "heat.parquet")
    diag = {"emissions": emission_diagnostics(em), "heat": heat_diagnostics(heat)}
    (args.out / "diagnostics.json").write_text(
        json.dumps(diag, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
    )
    LOG.info("diagnostics written")


if __name__ == "__main__":
    main()
