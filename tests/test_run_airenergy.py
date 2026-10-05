"""Tests for ``run_airenergy``."""

from __future__ import annotations

import json

import polars as pl

import run_airenergy as ra
from tests.test_airenergy_analysis import emissions, heat_rows


def test_build_is_json_safe_and_contains_no_identities() -> None:
    em = emissions().with_columns(
        aine_arvestus_meetod=pl.lit("AS"), cas_kood=pl.lit("124-38-9"), luba_versioon=pl.lit(1)
    )
    out = ra.build(em, heat_rows([]), generated="2026-01-01T00:00:00+00:00")
    blob = json.dumps(out)
    assert out["meta"]["data_quality"]["emissions"]["rows_unknown_unit"] == 1
    assert {r["aine_stat_grupp"] for r in out["co2"]} == {"CO2", "CO2 bio"}
    assert out["sensitivity"] and out["concentration"]["CO2"][0]["reports"] >= 1
    assert out["energy"]["by_fuel"][0]["fuel"] == "Maagaas"
    assert "kaitaja" not in blob and "registrikood" not in blob and "luba_number" not in blob
    assert out["energy"]["climate_link"] is None


def test_climate_link_needs_four_overlapping_years() -> None:
    clim = {
        "temperature": {
            "seasonal": {
                "DJF": {
                    "years": [2019, 2020, 2021, 2022, 2023],
                    "mean": [1.0, 2.0, None, 0.5, -0.2],
                }
            }
        }
    }
    heat = {2019: 10.0, 2020: 9.0, 2021: 8.0, 2022: 7.0, 2023: 6.0}
    link = ra.climate_link(heat, clim)
    assert link is not None and link["years"] == [2019, 2020, 2022, 2023]  # 2021 has no anomaly
    assert ra.climate_link(heat, None) is None
    assert ra.climate_link({2019: 1.0}, clim) is None
