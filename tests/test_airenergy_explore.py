"""Tests for ``airenergy_explore`` diagnostics on small synthetic frames."""

from __future__ import annotations

import polars as pl

import airenergy_explore as ae


def emissions() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "aruanne_id": [1, 1, 1, 2, 2],
            "aruanne_aasta": [2020, 2020, 2020, 2021, 2021],
            "heiteallikas_kood": ["H1", "H1", "H1", "H2", "H2"],
            "aine_nimetus": ["CO2", "NOx", "NOx", "CO2", "CO2"],
            "aine_stat_grupp": ["CO2", "NO2", "NO2", "CO2", "CO2"],
            "aine_kogus_maarus_yhik": [10.0, 2000.0, 1.0, 5.0, 5.0],
            "aine_yhik_maarus": ["t", "kg", "t", "t", "x"],
            "kytus_kood": ["301", "301", "301", "204", "204"],
            "kytus_kogus": [7.0, 7.0, 7.0, 3.0, 4.0],
            "tegevusala_nfr": ["1A1a"] * 5,
            "aine_arvestus_meetod": ["A"] * 5,
            "ets_kohuslane": ["Jah", "Jah", "Jah", "Ei", "Ei"],
            "cas_kood": ["124-38-9", "x", "x", "124-38-9", "124-38-9"],
            "luba_versioon": [1, 1, 2, 1, 1],
        }
    )


def test_emission_diagnostics_units_groups_and_grain() -> None:
    d = ae.emission_diagnostics(emissions())
    assert d["unknown_unit_rows"] == 1  # unit "x"
    groups = {g["aine_stat_grupp"]: g["total_t"] for g in d["groups"]}
    assert groups["CO2"] == 15.0  # 10 t + 5 t (unknown-unit row ignored by sum)
    assert groups["NO2"] == 3.0  # 2000 kg = 2 t + 1 t
    fr = d["fuel_repeats"]
    assert fr["groups"] == 2 and fr["groups_with_multiple_rows"] == 2
    assert (
        fr["multi_row_groups_with_single_amount"] == 1
    )  # H1/301 repeats 7.0, H2/204 has 3.0 and 4.0
    assert d["duplicate_substance_rows"]["with_n_gt_1"] == 2


def test_heat_diagnostics_report_level_totals() -> None:
    df = pl.DataFrame(
        {
            "aruanne_id": [1, 1, 2],
            "aruanne_aasta": [2020, 2020, 2020],
            "snap": ["a", "a", "b"],
            "kytus_liik": ["Gaaskütus", "Tahke kütus", "Gaaskütus"],
            "kytus_nimetus_val": ["Maagaas", "Puit", "Maagaas"],
            "kytus_kogus": [1.0, 2.0, 3.0],
            "kytus_yhik": ["tonni"] * 3,
            "soojus_kokku": [100.0, 100.0, 50.0],
            "soojus_omatarve": [0.0, 0.0, 0.0],
            "soojus_myyk": [0.0, 0.0, 0.0],
            "elekter_kokku": [10.0, 10.0, 0.0],
            "luba_versioon": [1, 1, 1],
        }
    )
    d = ae.heat_diagnostics(df)
    assert d["heat_repeats"]["multi_row_with_constant_heat"] == 1
    (row,) = d["report_level_totals_by_year"]
    assert row["heat"] == 150.0 and row["electricity"] == 10.0 and row["reports"] == 2


def test_duplicate_diagnostics_detects_versions_and_excess() -> None:
    d = ae.emission_diagnostics(emissions())["duplicates"]
    assert d["groups_n_gt_1"] == 2 and d["differing_permit_versions"] == 1
    assert d["identical_amounts"] == 1  # the two CO2 rows with 5 t each
    assert (
        d["excess_if_first_row_only_t"] == 1.0
    )  # NOx 3 t vs first row 2 t; CO2 repeat has unknown unit


def test_heat_additivity_and_outliers() -> None:
    df = pl.DataFrame(
        {
            "aruanne_id": [1, 1, 2],
            "aruanne_aasta": [2020, 2020, 2020],
            "snap": ["a", "a", "b"],
            "kytus_liik": ["g", "t", "g"],
            "kytus_nimetus_val": ["Maagaas", "Puit", "Maagaas"],
            "kytus_kogus": [1.0, 2.0, 3.0],
            "kytus_yhik": ["tonni"] * 3,
            "soojus_kokku": [100.0, 40.0, 10_000.0],
            "soojus_omatarve": [0.0] * 3,
            "soojus_myyk": [0.0] * 3,
            "elekter_kokku": [5.0, 5.0, 0.0],
            "luba_versioon": [1, 2, 1],
        }
    )
    d = ae.heat_diagnostics(df)
    a = d["additivity"]
    assert a["multi_row_reports"] == 1 and a["nonzero_electricity_constant"] == 1
    assert a["nonzero_heat_constant"] == 0 and a["reports_with_several_permit_versions"] == 1
    assert d["top_heat_rows"][0]["soojus_kokku"] == 10_000.0
