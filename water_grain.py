#!/usr/bin/env python3
"""Describe the grain of the water-body tables (what one row is, how cycles overlap).

Runs on the Parquet files written by ``water_fetch.py``; writes ``water_grain.json`` with
aggregate counts only (no water-body names).
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

import polars as pl

LOG = logging.getLogger("water_grain")


def counts(df: pl.DataFrame, cols: list[str], top: int = 40) -> list[dict[str, Any]]:
    return df.group_by(cols).agg(rows=pl.len()).sort("rows", descending=True).head(top).to_dicts()


def grain(raw: Path) -> dict[str, Any]:
    reg = pl.read_parquet(raw / "f_veekogumid.parquet")
    st = pl.read_parquet(raw / "f_veekogumi_seisundid.parquet")
    out: dict[str, Any] = {}
    out["register_category"] = counts(reg, ["veekogu_tyyp", "veekogu_tyyp_selg", "keht_staatus"])
    out["register_kood_prefix"] = counts(
        reg.with_columns(pl.col("kood").str.slice(0, 3).alias("prefix")), ["prefix", "keht_staatus"]
    )
    out["register_kood_sample"] = reg["kood"].head(12).to_list()
    out["register_vee_tyyp_selg"] = counts(reg, ["vee_tyyp", "vee_tyyp_selg"], 30)
    out["status_by_year_type_validity"] = (
        st.group_by("aasta", "tyyp", "keht_staatus", "muut_staatus")
        .agg(rows=pl.len(), bodies=pl.col("vkm_id").n_unique())
        .sort("aasta", "tyyp")
        .to_dicts()
    )
    key = ["vkm_id", "aasta", "tyyp", "keht_staatus"]
    dup = st.group_by(key).agg(n=pl.len())
    out["status_duplicates"] = {
        "groups": dup.height,
        "groups_with_multiple_rows": int((dup["n"] > 1).sum()),
    }
    out["status_kood_sample"] = st["kood"].head(10).to_list()
    out["status_join_ok"] = {
        "status_bodies": st["vkm_id"].n_unique(),
        "found_in_register": st.filter(pl.col("vkm_id").is_in(reg["id"])).n_unique("vkm_id"),
    }
    cur = st.filter((pl.col("tyyp") == "S") & (pl.col("keht_staatus") == "Kehtiv"))
    out["status_S_valid_overall"] = counts(cur, ["aasta", "seis"], 200)
    sj = cur.join(
        reg.select(pl.col("id").alias("vkm_id"), "veekogu_tyyp", "alamkategooria"), on="vkm_id"
    )
    out["status_S_valid_by_category"] = counts(sj, ["aasta", "veekogu_tyyp", "seis"], 400)
    out["status_S_valid_per_body_year"] = (
        cur.group_by("vkm_id", "aasta").agg(n=pl.len()).group_by("n").agg(k=pl.len()).to_dicts()
    )
    out["status_goal_example_columns"] = counts(
        st.filter(pl.col("tyyp") == "E"), ["aasta", "seis", "staatus"], 40
    )
    load = pl.read_parquet(raw / "f_veekogumid_koormus.parquet")
    out["pressure_by_type"] = counts(load, ["koormus_tyyp", "koormus_tyyp_selg"], 70)
    out["pressure_bodies"] = load["koormus_veekogum_id"].n_unique()
    out["pressure_dupes"] = {
        "rows": load.height,
        "distinct_koormus_id": load["koormus_id"].n_unique(),
    }
    out["pressure_status_over_reg"] = counts(
        load.join(
            reg.select(pl.col("id").alias("koormus_veekogum_id"), "keht_staatus"),
            on="koormus_veekogum_id",
            how="left",
        ),
        ["keht_staatus", "koormus_staatus"],
    )
    gw = pl.read_parquet(raw / "f_pohjaveekogumi_seisud.parquet")
    out["groundwater"] = counts(gw, ["aasta", "seis", "seis_kem", "seis_kog"], 60)
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw", type=Path, default=Path("out/water"))
    ap.add_argument("--out", type=Path, default=Path("out/water"))
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    (args.out / "water_grain.json").write_text(
        json.dumps(grain(args.raw), ensure_ascii=False, indent=1, default=str), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
