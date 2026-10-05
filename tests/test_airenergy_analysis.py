"""Tests for ``airenergy_analysis`` with small synthetic frames of known totals (tests only)."""

from __future__ import annotations

import polars as pl
import pytest

import airenergy_analysis as aa


def emissions() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "aruanne_id": [1, 1, 2, 3, 3, 4, 5],
            "aruanne_aasta": [2020, 2020, 2020, 2021, 2021, 2021, 2021],
            "heiteallikas_kood": ["A", "A", "B", "C", "C", "D", "E"],
            "aine_nimetus": ["CO2", "CO2", "CO2", "CO2", "CO2", "CO2 b", "CO2"],
            "aine_stat_grupp": ["CO2", "CO2", "CO2", "CO2", "CO2", "CO2 bio", "CO2"],
            "aine_kogus_maarus_yhik": [100.0, 50.0, 2000.0, 10.0, 10.0, 7.0, 5.0],
            "aine_yhik_maarus": ["t", "t", "kg", "t", "t", "t", None],
            "kytus_kood": ["301"] * 7,
            "tegevusala_nfr": ["1A1a", "1A1a", "1A2gviii", "1A1a", "1A1a", None, "1A4ai"],
            "tegevuskoht_maakond_nimi_curr": [
                "Harju",
                "Harju",
                "Tartu",
                "Harju",
                "Harju",
                None,
                "Tartu",
            ],
            "ets_kohuslane": ["Jah", "Jah", "Ei", "Jah", "Jah", None, "Ei"],
        }
    )


def test_prepare_emissions_converts_units_and_drops_unknown() -> None:
    d, info = aa.prepare_emissions(emissions())
    assert info == {"rows_unknown_unit": 1} and d.height == 6
    assert d.filter(pl.col("aruanne_id") == 2)["amount_t"][0] == pytest.approx(2.0)  # 2000 kg
    assert set(d["ets"]) == {"Jah", "Ei", "teadmata"}


def test_yearly_totals_keep_fossil_and_biogenic_co2_apart() -> None:
    d, _ = aa.prepare_emissions(emissions())
    t = aa.yearly_totals(d, [aa.CO2, aa.CO2_BIO])
    got = {(r["aine_stat_grupp"], r["aruanne_aasta"]): r["tonnes"] for r in t.iter_rows(named=True)}
    assert got[("CO2", 2020)] == pytest.approx(152.0)
    assert got[("CO2", 2021)] == pytest.approx(20.0)  # the 5 (unknown unit) row is gone
    assert got[("CO2 bio", 2021)] == pytest.approx(7.0)


def test_dedup_gap_counts_repeated_keys() -> None:
    d, _ = aa.prepare_emissions(emissions())
    g = aa.dedup_gap(d, [aa.CO2]).filter(pl.col("aruanne_aasta") == 2020).row(0, named=True)
    # report 1 / source A / CO2 / fuel 301 appears twice (100 t, 50 t): first row only -> 100
    assert g["all_t"] == pytest.approx(152.0) and g["first_t"] == pytest.approx(102.0)
    assert g["gap_share"] == pytest.approx(50 / 152)


def test_sector_county_ets_and_concentration() -> None:
    d, _ = aa.prepare_emissions(emissions())
    s = aa.sector_totals(d, aa.CO2, top=1)
    assert set(s["sector"]) == {"1A1a", "Muu"}
    c = aa.county_totals(d, aa.CO2).filter(pl.col("aruanne_aasta") == 2020)
    assert dict(zip(c["county"], c["tonnes"], strict=True)) == {"Harju": 150.0, "Tartu": 2.0}
    e = aa.ets_split(d, aa.CO2).filter(pl.col("aruanne_aasta") == 2020)
    assert dict(zip(e["ets"], e["tonnes"], strict=True)) == {"Jah": 150.0, "Ei": 2.0}
    conc = (
        aa.concentration(d, aa.CO2, tops=(1,))
        .filter(pl.col("aruanne_aasta") == 2020)
        .row(0, named=True)
    )
    assert conc["reports"] == 2 and conc["top1_share"] == pytest.approx(150 / 152)


def test_fuel_group_mapping() -> None:
    assert aa.fuel_group("Puiduhake") == "Puit ja biomass"
    assert aa.fuel_group("Põlevkivi tolmpõletamisel") == "Põlevkivi"
    assert aa.fuel_group("Põlevkiviõli (raske fraktsioon)") == "Põlevkiviõli"
    assert aa.fuel_group("Maagaas (välja arvatud vedelal kujul)") == "Maagaas"
    assert aa.fuel_group("Poolkoksigaas") == "Tööstus- ja muud gaasid"
    assert aa.fuel_group("Vedeldatud naftagaas (LPG)") == "Nafta- ja veeldatud gaasid"
    assert aa.fuel_group(None) == "Muu" and aa.fuel_group("Kivisüsi") == "Muu"


def heat_rows(extra: list[dict[str, object]]) -> pl.DataFrame:
    base = [
        {
            "aruanne_id": i,
            "aruanne_aasta": 2020,
            "kytus_nimetus_val": "Maagaas",
            "kytus_yhik": "tuh. Nm³",
            "kytus_kogus": 100.0,
            "soojus_kokku": 860.0,
            "elekter_kokku": 0.0,
        }
        for i in range(10)
    ]
    return pl.DataFrame(base + extra)


def test_prepare_heat_flags_unit_errors_and_no_fuel_rows() -> None:
    bad = [
        {
            "aruanne_id": 90,
            "aruanne_aasta": 2019,
            "kytus_nimetus_val": "Maagaas",
            "kytus_yhik": "tuh. Nm³",
            "kytus_kogus": 100.0,
            "soojus_kokku": 5_000_000.0,
            "elekter_kokku": 0.0,
        },  # unit error
        {
            "aruanne_id": 91,
            "aruanne_aasta": 2019,
            "kytus_nimetus_val": "Maagaas",
            "kytus_yhik": "tuh. Nm³",
            "kytus_kogus": 0.0,
            "soojus_kokku": 10.0,
            "elekter_kokku": 0.0,
        },  # heat without fuel
    ]
    clean, rep = aa.prepare_heat(heat_rows(bad))
    assert rep["flagged_rows"] == 2 and clean.height == 10
    assert rep["flagged_heat_by_year"][0]["aruanne_aasta"] == 2019
    assert set(clean["fuel"]) == {"Maagaas"}


def test_energy_by_fuel_sums_rows() -> None:
    clean, _ = aa.prepare_heat(heat_rows([]))
    e = aa.energy_by_fuel(clean).row(0, named=True)
    assert e["heat"] == pytest.approx(8600.0) and e["reports"] == 10
