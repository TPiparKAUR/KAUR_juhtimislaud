"""Tests for groundwater abstraction against approved reserves."""

from __future__ import annotations

import json

import polars as pl
import pytest

import gw_balance as gb


def inputs() -> tuple[pl.DataFrame, ...]:
    gw = pl.DataFrame(
        {
            "aruandeaasta": [2024] * 5,
            "veehaardekood": ["k1", "K2 ", "k3", "k4", "k5"],
            "aastakokku": [365_000.0, 36_500.0, 1000.0, 2000.0, 4000.0],
        }
    )
    intakes = pl.DataFrame(
        {
            "id": [1, 2, 3, 4, 5],
            "kkr_kood": ["K1", "K2", "K3", "K4", "K5"],
            "veeliik_selg": ["Põhjavesi", None, "Karjäärivesi", None, None],
        }
    )
    boreholes = pl.DataFrame(
        {
            "veehaare_id": [1, 1, 2, 3, 3, 4],
            "pohjaveekogum_id": [10, 10, 20, 10, 20, None],
            "keht_staatus": ["Kehtiv"] * 6,
        }
    )
    res = pl.DataFrame(
        {
            "pohjaveekogum_id": [10, 20, 20, 30],
            "keht_staatus": ["Kehtiv", "Kehtiv", "Kehtetu", "Kehtiv"],
            "varu_t1_olme": [500, 100, 9999, 50],
        }
    )
    states = pl.DataFrame(
        {
            "pohjaveekogum_id": [10, 20],
            "aasta": [2020, 2020],
            "muut_aeg": ["2021-01-01", "2021-01-01"],
            "kood": ["A", "B"],
            "seis_kog": ["1", "3"],
        }
    )
    return gw, intakes, boreholes, res, states


def test_allocation_classes_and_shares() -> None:
    gw, intakes, boreholes, *_ = inputs()
    g = gb.allocate(gw, gb.intake_bodies(intakes, boreholes))
    cls = dict(zip(g["code"].to_list(), g["class"].to_list(), strict=True))
    assert cls == {"K1": "single", "K2": "single", "K3": "multiple", "K4": "none", "K5": "none"}
    s = gb.shares(g)[0]
    assert s["single"] == pytest.approx(401_500 / 408_500)
    assert s["multiple"] == pytest.approx(1000 / 408_500)


def test_balance_ratio_uses_valid_reserves_only() -> None:
    b = gb.build(*inputs())
    latest = b["latest"]
    rows = {r["kood"]: r for r in latest["bodies"]}
    assert rows["A"]["abstraction_m3_d"] == pytest.approx(1000.0)  # 365 000 m3/yr
    assert rows["A"]["ratio"] == pytest.approx(2.0)  # reserve 500
    assert rows["B"]["ratio"] == pytest.approx(1.0)  # 36 500 / 365 = 100 vs 100; invalid dropped
    assert rows["B"]["quantity_status"] == "3"
    assert latest["bodies_with_both"] == 2 and latest["ratio_gt1"] == 1
    assert latest["bodies_with_reserve"] == 3
    types = {r["veeliik_selg"]: r["m3"] for r in b["intake_types"]}
    assert types["Karjäärivesi"] == 1000.0 and types["Märkimata"] == 42_500.0
    json.dumps(b)
