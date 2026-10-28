"""Tests for the heat production analysis."""

from __future__ import annotations

import json

import polars as pl
import pytest

import heat_analysis as ha


def ke034() -> pl.DataFrame:
    rows = []
    for y, h in (("2020", 3000.0), ("2021", 3100.0)):
        for gen, v in (("CHP_T", h), ("BP_TURB", h * 0.6), ("INT_COMB", h * 0.4)):
            rows.append(
                {
                    "Näitaja": "PROD_H_CHP",
                    "Generaatori liik": gen,
                    "Vaatlusperiood": y,
                    "value": v,
                    "status": None,
                }
            )
        rows.append(
            {
                "Näitaja": "PROD_E_CHP",
                "Generaatori liik": "CHP_T",
                "Vaatlusperiood": y,
                "value": 1000.0,
                "status": None,
            }
        )
    return pl.DataFrame(rows)


def ke035() -> pl.DataFrame:
    rows = []
    for y in ("2020", "2021"):
        for fuel, tj in (
            ("G3000X3100_3200", 6000.0),
            ("B51151_EE", 3000.0),
            ("W6220_EE", 1000.0),
            ("XX", 500.0),
        ):
            rows.append(
                {
                    "Näitaja": "CONS_FUEL_NRG",
                    "Kütuse/energia liik": fuel,
                    "Generaatori liik": "CHP_T",
                    "Vaatlusperiood": y,
                    "value": tj,
                    "status": None,
                }
            )
        rows.append(
            {
                "Näitaja": "CONS_FUEL",
                "Kütuse/energia liik": "B51151_EE",
                "Generaatori liik": "CHP_T",
                "Vaatlusperiood": y,
                "value": 9.0,
                "status": None,
            }
        )
    return pl.DataFrame(rows)


def ke20() -> pl.DataFrame:
    rows = []
    for y in ("2023", "2024"):
        for m in range(1, 13):
            rows.append(
                {
                    "Näitaja": "PROD",
                    "Energia liik": "H8000",
                    "Vaatlusperiood": f"{y}M{m:02d}",
                    "value": 100.0 + 10 * (m in (1, 2, 12)),
                    "status": None,
                }
            )
            rows.append(
                {
                    "Näitaja": "PROD",
                    "Energia liik": "E7000",
                    "Vaatlusperiood": f"{y}M{m:02d}",
                    "value": 500.0,
                    "status": None,
                }
            )
    for m in range(1, 4):  # incomplete year
        rows.append(
            {
                "Näitaja": "PROD",
                "Energia liik": "H8000",
                "Vaatlusperiood": f"2025M{m:02d}",
                "value": 120.0,
                "status": None,
            }
        )
    return pl.DataFrame(rows)


def test_chp_and_fuel_groups() -> None:
    r = ha.build(ke034(), ke035(), ke20())
    c = r["chp"][0]
    assert c["PROD_H_CHP"] == 3000.0 and c["heat_by_generator"]["BP_TURB"] == pytest.approx(1800.0)
    f = r["fuels"][0]
    assert f["total_tj"] == 10500.0 and f["Maagaas"] == 6000.0 and f["Muu"] == pytest.approx(500.0)
    assert f["renewable_share_pct"] == pytest.approx(100 * 3000 / 10500)
    assert f["output_to_fuel"] == pytest.approx((1000 + 3000) * 3.6 / 10500)


def test_monthly_uses_complete_years_only() -> None:
    m = ha.build(ke034(), ke035(), ke20())["monthly"]
    assert [a["year"] for a in m["annual"]] == [2023, 2024]
    assert m["annual"][0]["heat_gwh"] == pytest.approx(9 * 100 + 3 * 110)
    assert len(m["profile"]) == 2 and len(m["profile"][0]["months"]) == 12
    assert m["last_month"] == "2025M03"
    json.dumps(ha.build(ke034(), ke035(), ke20()))


def test_non_breaking_space_in_column_names_is_normalised() -> None:
    f = ke20().rename({"Energia liik": "Energia\u00a0liik"})
    m = ha.build(ke034(), ke035(), f)["monthly"]
    assert [a["year"] for a in m["annual"]] == [2023, 2024]
