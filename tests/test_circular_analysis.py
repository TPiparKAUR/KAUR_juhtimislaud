"""Tests for the circular economy analysis."""

from __future__ import annotations

import json
from typing import Any

import polars as pl
import pytest

import circular_analysis as ca

WASTE_TEXTS = {
    "1": "Jäätmed kokku",
    "2": "010000 Kaevandus",
    "3": "010100 Maavara",
    "4": "200000 Olme",
}


def waste_frame() -> pl.DataFrame:
    rows = []
    for y, scale in (("2010", 1.0), ("2011", 1.5)):
        for code, item, v in (
            ("1", "3", 1000 * scale),
            ("2", "3", 700 * scale),
            ("3", "3", 700 * scale),
            ("4", "3", 300 * scale),
            ("1", "7", 400 * scale),
            ("1", "8", 100 * scale),
            ("1", "6", 500 * scale),
            ("1", "9", 80 * scale),
            ("2", "7", 50 * scale),
        ):
            rows.append(
                {"Aasta": y, "Jäätmeliik": code, "Näitaja": item, "value": v, "status": None}
            )
    return pl.DataFrame(rows)


def kk99_frame() -> pl.DataFrame:
    rows = []
    for y, dmc in (("2010", 500.0), ("2011", 450.0)):
        rows.append({"Näitaja": "9", "Aasta": y, "value": dmc, "status": None})
        rows.append({"Näitaja": "2", "Aasta": y, "value": dmc * 1.1, "status": None})
        rows.append({"Näitaja": "11", "Aasta": y, "value": 0.7, "status": None})
    return pl.DataFrame(rows)


def gdp_frame() -> pl.DataFrame:
    rows = []
    for y, v in (("2010", 100.0), ("2011", 110.0)):
        for kv, sa in (("1", "1"), ("I", "1"), ("1", "2")):
            rows.append(
                {
                    "Aasta": y,
                    "Kvartal": kv,
                    "Sesoonne korrigeerimine": sa,
                    "Näitaja": "2",
                    "value": v + (5 if sa == "2" else 0) + (7 if kv == "I" else 0),
                    "status": None,
                }
            )
    return pl.DataFrame(rows)


def cmu_frame() -> pl.DataFrame:
    rows = [
        {"freq": "A", "unit": "PC", "geo": g, "time": y, "value": v, "status": None}
        for g, y, v in (("EE", "2010", 9.0), ("EE", "2011", 10.0), ("EU27_2020", "2010", 11.0))
    ]
    return pl.DataFrame(rows)


def activity_frame() -> pl.DataFrame:
    rows = [
        {
            "Aasta": "2024",
            "Jäätmeliik": "1",
            "Tegevusala (EMTAK 2008)": a,
            "value": v,
            "status": None,
        }
        for a, v in (("1", 100.0), ("5", 60.0), ("6", 40.0))
    ]
    return pl.DataFrame(rows)


def build() -> dict[str, Any]:
    return ca.build(
        kk99_frame(),
        waste_frame(),
        activity_frame(),
        gdp_frame(),
        cmu_frame(),
        {"KK610_waste": WASTE_TEXTS, "KK068_activity": {"5": "Mäetööstus", "6": "Toit"}},
        "2026-01-01",
    )


def test_chapters_and_waste_without_mining_and_energy() -> None:
    assert ca.chapters(waste_frame(), WASTE_TEXTS) == {"2": "01", "4": "20"}
    r = build()
    w = r["waste"][0]
    assert w["generated"] == 1000 and w["mining_energy"] == 700 and w["generated_other"] == 300
    assert w["recovery"] == 400 and w["recovery_mining_energy"] == 50
    assert r["checks"]["chapter_sum_share_of_total"][2010] == pytest.approx(1.0)


def test_decoupling_indices_use_the_first_common_year_and_unadjusted_annual_gdp() -> None:
    r = build()
    dc = r["decoupling"]
    assert dc["base_year"] == 2010
    last = dc["years"][-1]
    assert last["gdp"] == pytest.approx(110.0) and last["dmc"] == pytest.approx(90.0)
    assert last["waste"] == pytest.approx(150.0)


def test_cmu_activity_and_json() -> None:
    r = build()
    assert r["cmu"][0] == {"year": 2010, "ee": 9.0, "eu": 11.0}
    assert r["cmu"][1]["eu"] is None
    a = r["activity"][0]
    assert a["total"] == 100.0 and {x["name"] for x in a["activities"]} == {"Mäetööstus", "Toit"}
    json.dumps(r)
