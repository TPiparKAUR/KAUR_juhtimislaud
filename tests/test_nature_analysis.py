"""Tests for the nature-conservation analysis."""

from __future__ import annotations

import json

import polars as pl

import nature_analysis as na
import run_nature as rn


def alad() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "al_staatus_selg": ["kaitsealune", "kaitsealune", "kavandatav kaitstav ala"],
            "tyyp_selg": ["looduskaitseala", "püsielupaik", "looduskaitseala"],
            "iucn_tyyp_selg": ["Ib - Kõnnumaa", None, None],
            "pindala_maa": [100.0, None, 50.0],
            "pindala_meri": [None, None, None],
        }
    )


def rahvalad() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "tyyp_selg": ["Natura (loodusala)", "IBA"],
            "pindala_maa": [10.0, 5.0],
            "pindala_meri": [1.0, None],
        }
    )


def habitats_frame() -> pl.DataFrame:
    rows = []
    for ver, cons in (
        ("2010 Natura standardbaas", "Hästi säilinud"),
        ("2026 Natura standardbaas", "Keskmiselt või vähe säilinud"),
    ):
        for site, code in ((1, "9010"), (2, "6270")):
            rows.append(
                {
                    "elpst_tyyp_selg": ver,
                    "elupst_on_endine": False,
                    "elpst_obj_id": site,
                    "elupaigatyyp_kood": code,
                    "elupaigatyyp_grupp_selg": "Metsad",
                    "elupst_pindala_alal": 10.0,
                    "elupst_kaitse_selg": cons if site == 1 else "Väga hästi säilinud",
                }
            )
    return pl.DataFrame(rows)


def species_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "lkohtst_tyyp_selg": ["2010 Natura standardbaas", "2026 Natura standardbaas"],
            "lkohtst_on_endine": [False, False],
            "lkohtst_lnim_id": [1, 1],
            "lkohtst_obj_id": [1, 1],
            "ryhm_selg": ["Linnud", "Linnud"],
            "lkohtst_kaitse_selg": ["Hea kaitsestaatus", None],
        }
    )


def sites_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "liik_tyyp_selg": ["Kaitsealune liik", "Kaitsealune liik", "Võõrliik"],
            "lnim_ryhm_selg": ["Linnud", "Linnud", "Katteseemnetaimed"],
            "lnim_id": [1, 2, 3],
            "lnim_kaitsekategooria_selg": ["I kategooria", "III kategooria", None],
            "voorliik_tyyp_selg": [None, None, "Invasiivne"],
        }
    )


def vepid_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "tyyp_selg": ["Vääriselupaik", "Vääriselupaik", "Vääriselupaik", "Vepi lepinguga ala"],
            "veptyyp_selg": ["Männikud", "Männikud", "Lepikud", None],
            "pindala": [2.0, 3.0, 1.0, 9.0],
            "esmane_kp": ["2005-03-01", "2005-07-01", "12.05.2007", None],
            "omandiv_selg": ["Riigiomand", "Eraomand", "Riigiomand", None],
            "kaitse_selg": [
                "On kehtiv leping",
                "Ei ole kehtivat lepingut",
                "Ei ole kehtivat lepingut",
                None,
            ],
        }
    )


def test_protected_areas_split_designated_and_planned_without_summing_types() -> None:
    p = na.protected_areas(alad())
    assert (p["designated"], p["planned"]) == (2, 1)
    by = {r["name"]: r for r in p["by_type"]}
    assert by["looduskaitseala"]["land_ha"] == 100.0 and by["püsielupaik"]["n_land_area"] == 0
    assert all("total" not in k for k in p)


def test_habitat_versions_are_labelled_and_paired_by_site_and_type() -> None:
    h = na.habitats(habitats_frame())
    assert [v["version"] for v in h["per_version"]] == ["2010", "2026"]
    assert h["paired"] == {
        "from": "2010",
        "to": "2026",
        "n": 2,
        "improved": 0,
        "same": 1,
        "worsened": 1,
    }
    assert h["groups_latest"][0]["records"] == 2


def test_species_stats_exclude_unrated_from_counts() -> None:
    s = na.species_stats(species_frame())
    assert s["per_version"][0]["rated"] == 1 and s["per_version"][1]["rated"] == 0


def test_species_sites_aliens_separate_from_protected() -> None:
    s = na.species_sites(sites_frame())
    assert (s["protected_species_sites"], s["alien_sites"], s["invasive_sites"]) == (2, 1, 1)
    assert s["by_category"]["I kategooria"] == 1


def test_key_habitats_cumulative_and_contract_share() -> None:
    k = na.key_habitats(vepid_frame())
    assert k["n"] == 3 and k["with_contract"] == 1 and k["area_ha"] == 6.0
    assert [(r["year"], r["cum_n"]) for r in k["by_year"]] == [(2005, 2.0), (2007, 3.0)]


def test_build_is_json_serialisable() -> None:
    d = rn.build(
        alad(),
        rahvalad(),
        habitats_frame(),
        species_frame(),
        sites_frame(),
        vepid_frame(),
        "2026-01-01",
    )
    json.dumps(d)
    assert "kesk_x" not in json.dumps(d)
