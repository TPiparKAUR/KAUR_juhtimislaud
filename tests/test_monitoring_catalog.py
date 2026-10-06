"""Tests for the monitoring catalogue."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl

import monitoring_catalog as mc


def agg() -> pl.DataFrame:
    base = {
        "naitaja_alamgrupp_selg": None,
        "vaatlusgrupp_selg": None,
        "seirekogum_tyyp": None,
        "takson_est": None,
        "v_sum": 1.0,
        "n_negative": 0,
    }
    rows = [
        {
            **base,
            mc.PROG: "Metsaseire",
            "naitaja_grupp_selg": "Puud",
            "naitaja_kood": "OK",
            "naitaja_nimetus": "Okkakadu",
            "naitaja_abr_unit": "%",
            "liik_est": "kuusk",
            "year": 2020,
            "rows": 100,
            "n_value": 100,
            "v_min": 0.0,
            "v_max": 90.0,
        },
        {
            **base,
            mc.PROG: "Metsaseire",
            "naitaja_grupp_selg": "Puud",
            "naitaja_kood": "OK",
            "naitaja_nimetus": "Okkakadu",
            "naitaja_abr_unit": "%",
            "liik_est": "mänd",
            "year": 2021,
            "rows": 50,
            "n_value": 50,
            "v_min": 1.0,
            "v_max": 80.0,
        },
        {
            **base,
            mc.PROG: "Veeseire",
            "naitaja_grupp_selg": "Vesi",
            "naitaja_kood": "TN",
            "naitaja_nimetus": "Üldlämmastik",
            "naitaja_abr_unit": "mg/l",
            "liik_est": None,
            "year": 2021,
            "rows": 10,
            "n_value": 8,
            "v_min": 0.1,
            "v_max": 9.0,
        },
    ]
    return pl.DataFrame(rows, schema_overrides={"liik_est": pl.Utf8, "takson_est": pl.Utf8})


def test_catalog_counts_programmes_indicators_and_species() -> None:
    c = mc.catalog(agg())
    assert c["rows"] == 160
    progs = {p[mc.PROG]: p for p in c["programmes"]}
    assert progs["Metsaseire"]["species"] == 2 + 0 or progs["Metsaseire"]["species"] >= 2
    ind = {i["naitaja_kood"]: i for i in c["indicators"]}
    assert ind["OK"]["years"] == 2 and ind["OK"]["units"] == ["%"]
    assert {r["year"]: r["species"] for r in c["species"]["per_year"]} == {2020: 1, 2021: 1}


def test_main_writes_json(tmp_path: Path) -> None:
    agg().write_parquet(tmp_path / "a.parquet")
    mc.main(["--agg", str(tmp_path / "a.parquet"), "--out", str(tmp_path)])
    assert (
        json.loads((tmp_path / "monitoring_catalog.json").read_text(encoding="utf-8"))["rows"]
        == 160
    )
