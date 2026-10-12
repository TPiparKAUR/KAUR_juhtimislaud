"""Tests for the energy statistics analysis."""

from __future__ import annotations

import json

import polars as pl
import pytest

import energy_analysis as ea

P, PRD, K = "Näitaja", "Kütuse/energia liik", "Aasta"


def balance_frame(exp_sign: int = 1) -> pl.DataFrame:
    rows = []

    def add(year: str, item: str, product: str, value: float | None) -> None:
        rows.append({K: year, P: item, PRD: product, "value": value, "status": None})

    for year, scale in (("2020", 1.0), ("2021", 2.0)):
        for item, v in (
            ("PPRD", 100 * scale),
            ("IMP", 50 * scale),
            ("EXP", exp_sign * 20 * scale),
            ("STK_CHG", -5 * scale),
            ("GAE", 125 * scale),
            ("GIC", 120 * scale),
            ("FC_E", 80 * scale),
            ("FC_IND_E", 30 * scale),
            ("FC_TRA_E", 20 * scale),
            ("FC_OTH_HH_E", 20 * scale),
            ("FC_OTH_CP_E", 10 * scale),
        ):
            add(year, item, "TOTAL", v)
        add(year, "PPRD", "S2000", 60 * scale)
        add(year, "PPRD", "RA300", 10 * scale)
        add(year, "PPRD", "R5110-5150_W6000RI", 20 * scale)
        add(
            year, "PPRD", "O4680", 1 * scale
        )  # unclassified product -> "Muu" together with the rest
        add(year, "GAE", "RA300", 10 * scale)
        add(year, "GAE", "R5110-5150_W6000RI", 15 * scale)
    return pl.DataFrame(rows)


def electricity_frame() -> pl.DataFrame:
    rows = []
    for year, wind in (("2020", 100.0), ("2021", 300.0)):
        for prod, v in (("_T", 1000.0), ("WIND", wind), ("S2100_EE", 600.0), ("B5115_EE", 100.0)):
            rows.append(
                {
                    K: year,
                    P: "PROD_E",
                    PRD: prod,
                    "Elektritootja liik": "_T",
                    "value": v,
                    "status": None,
                }
            )
        rows.append(
            {
                K: year,
                P: "PROD_E",
                PRD: "WIND",
                "Elektritootja liik": "PP_AUTO",
                "value": 5.0,
                "status": None,
            }
        )
    return pl.DataFrame(rows)


def capacity_frame() -> pl.DataFrame:
    rows = [
        {
            "Näitaja": "CAP_I_WIND",
            "Elektritootja liik": "_T",
            "Vaatlusperiood": "2020",
            "value": 320.0,
            "status": None,
        },
        {
            "Näitaja": "CAP_I_WIND",
            "Elektritootja liik": "PP_PUB",
            "Vaatlusperiood": "2020",
            "value": 1.0,
            "status": None,
        },
    ]
    return pl.DataFrame(rows)


def test_signs_are_detected_for_positive_and_negative_exports() -> None:
    assert ea.detect_signs(ea.balance(balance_frame(1)))["exp"] == -1
    assert ea.detect_signs(ea.balance(balance_frame(-1)))["exp"] == 1
    assert ea.detect_signs(ea.balance(balance_frame(1)))["residual_share"] == pytest.approx(0.0)


def test_dependency_production_groups_and_renewable_share() -> None:
    r = ea.build(balance_frame(), electricity_frame(), capacity_frame(), "2026-01-01")
    y0 = r["balance"][0]
    assert y0["net_imports"] == 30.0 and y0["dependency_pct"] == pytest.approx(100 * 30 / 125)
    p = r["production"][0]
    assert (
        p["Põlevkivi"] == 60.0
        and p["Tuul, päike, hüdro"] == 10.0
        and p["Muu"] == pytest.approx(10.0)
    )
    assert p["renewable"] == 30.0
    assert r["renewable_gae"][0]["share_pct"] == pytest.approx(100 * 25 / 125)
    f = r["final"][1]
    assert f["Tööstus"] == 60.0 and f["Kodumajapidamised"] == 40.0
    json.dumps(r)


def test_electricity_groups_ignore_other_plant_types_and_capacity_uses_all_plants() -> None:
    r = ea.build(balance_frame(), electricity_frame(), capacity_frame(), "2026-01-01")
    e = r["electricity"]
    assert e[1]["Tuul"] == 300.0 and e[1]["Põlevkivi ja põlevkiviproduktid"] == 600.0
    assert e[1]["renewable_share_pct"] == pytest.approx(100 * 400 / 1000)
    assert e[1]["Muu"] == pytest.approx(0.0)
    assert r["capacity"] == [{"year": 2020, "CAP_I_WIND": 320.0}]
