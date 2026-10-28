"""Tests for the greenhouse gas inventory analysis."""

from __future__ import annotations

import json

import polars as pl
import pytest

import ghg_analysis as ga


def frame() -> pl.DataFrame:
    rows = []

    def add(geo: str, code: str, year: str, v: float | None) -> None:
        rows.append({"geo": geo, "src_crf": code, "time": year, "value": v, "status": None})

    for y, k in (("1990", 1.0), ("2020", 0.5)):
        for code, v in (
            ("TOTX4_MEMO", 40.0 * k),
            ("TOTXMEMO", 38.0 * k),
            ("CRF4", -2.0),
            ("CRF1", 30.0 * k),
            ("CRF1A1", 18.0 * k),
            ("CRF1A3", 8.0 * k),
            ("CRF2", 3.0),
            ("CRF3", 4.0),
            ("CRF5", 3.0 * k),
        ):
            add("EE", code, y, v)
        add("EU27_2020", "TOTX4_MEMO", y, 4000.0 * (1 if y == "1990" else 0.7))
    return pl.DataFrame(rows)


def test_sector_rows_with_remainder_and_energy_breakdown() -> None:
    b = ga.build(frame(), "2026-01-01")
    s = b["sectors"][0]
    assert s["Energia"] == 30.0 and s["Põllumajandus"] == 4.0
    assert s["Muu"] == pytest.approx(0.0)
    e = b["energy"][0]
    assert e["Transport"] == 8.0 and e["Muu"] == pytest.approx(30 - 18 - 8)
    json.dumps(b)


def test_index_against_eu_and_lulucf() -> None:
    b = ga.build(frame(), "2026-01-01")
    c = b["comparison"][-1]
    assert c["ee_total"] == pytest.approx(50.0) and c["eu_total"] == pytest.approx(70.0)
    assert c["ee_energy"] == pytest.approx(50.0)
    assert b["lulucf"][0] == {"year": 1990, "lulucf": -2.0, "total_incl": 38.0}
