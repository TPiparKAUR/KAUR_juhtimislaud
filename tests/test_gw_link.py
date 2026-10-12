"""Tests for the groundwater abstraction / reserve link probe."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl

import gw_link as gl


def tables() -> tuple[pl.DataFrame, pl.DataFrame]:
    gw = pl.DataFrame(
        {
            "veehaardekood": [" a1", "B2", "C3", None],
            "jaamakood": ["x", "y", "z", "w"],
            "aastakokku": [100.0, 300.0, 600.0, 50.0],
        }
    )
    res = pl.DataFrame({"kood": ["A1", "B2", "Q9"], "kkr_kood": [None, None, None]})
    return gw, res


def test_matching_codes_are_normalised_and_volume_weighted() -> None:
    gw, res = tables()
    rep = {(r["abstraction_column"], r["reserve_column"]): r for r in gl.link_report(gw, res)}
    r = rep[("veehaardekood", "kood")]
    assert r["matching_codes"] == 2 and r["distinct_abstraction"] == 3
    assert abs(r["matching_volume_share"] - 400 / 1050) < 1e-9
    assert rep[("veehaardekood", "kkr_kood")]["matching_codes"] == 0
    assert ("veehaardekood", "veemaardla_kood") not in rep  # missing column is skipped


def test_main_writes_counts_only(tmp_path: Path) -> None:
    gw, res = tables()
    gw.write_parquet(tmp_path / "t_awtabel002_01_curr.parquet")
    res.write_parquet(tmp_path / "f_pohjaveevarud.parquet")
    gl.main(["--raw", str(tmp_path), "--out", str(tmp_path / "o")])
    text = (tmp_path / "o" / "gw_link.json").read_text(encoding="utf-8")
    assert "A1" not in text and json.loads(text)["pairs"]


def test_registry_report_counts_matches_and_boreholes() -> None:
    gw, _ = tables()
    intakes = pl.DataFrame({"id": [1, 2, 3], "id_text": ["a1", "B2", "zz"], "kkr_kood": [None] * 3})
    boreholes = pl.DataFrame({"veehaare_id": [1, 1, 2], "pohjaveekogum_id": [7, None, None]})
    rep = {r["intake_column"]: r for r in gl.registry_report(gw, intakes, boreholes)}
    r = rep["id_text"]
    assert r["matching_codes"] == 2 and r["matched_intakes"] == 2
    assert r["matched_intakes_with_borehole_body"] == 1
    assert rep["kkr_kood"]["matching_codes"] == 0
