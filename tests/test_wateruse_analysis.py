"""Tests for the water use / discharge analysis."""

from __future__ import annotations

import json

import polars as pl

import run_wateruse as rw
import wateruse_analysis as wu


def use_frame() -> pl.DataFrame:
    base = dict.fromkeys(wu.SECTORS)
    rows = [
        {
            "annual_report_id": 1,
            "aruandeaasta": 2024,
            "kasutuspiirkond": "a",
            "veeliik": "Põhjavesi",
            "kokku": 100.0,
            **base,
            "olme": 60.0,
            "toostus": 40.0,
            "veekadu": 5.0,
        },
        {
            "annual_report_id": 2,
            "aruandeaasta": 2024,
            "kasutuspiirkond": "b",
            "veeliik": None,
            "kokku": 1000.0,
            **base,
            "jahutus": 1000.0,
            "veekadu": None,
        },
        {
            "annual_report_id": 3,
            "aruandeaasta": 2025,
            "kasutuspiirkond": "a",
            "veeliik": "Põhjavesi",
            "kokku": 50.0,
            **base,
            "olme": 10.0,
            "veekadu": None,
        },
    ]
    return pl.DataFrame(
        rows, schema_overrides=dict.fromkeys(wu.SECTORS, pl.Float64) | {"veekadu": pl.Float64}
    )


def abstraction_frame() -> pl.DataFrame:
    row = dict.fromkeys(wu.MONTHS, 1.0)
    return pl.DataFrame(
        [
            {"aruandeaasta": 2024, "annual_report_id": 1, "aastakokku": 12.0, **row},
            {"aruandeaasta": 2024, "annual_report_id": 2, "aastakokku": 12.0, **row},
        ]
    )


def discharge_frame() -> pl.DataFrame:
    base: dict[str, object] = {}
    for _key, (lim, tpl, _label) in wu.POLLUTANTS.items():
        base[lim] = None
        for q in (1, 2, 3, 4):
            base[tpl.format(q=q)] = None
    rows = []
    for code, over in (("o1", 5.0), ("o2", 0.8), ("o3", None)):
        r = dict(base) | {
            "aruandeaasta": 2024,
            "valjalaskmekood": code,
            "heitveehulkaastas": 10.0,
            "arvutusviis": "Arvutuslik" if code != "o2" else "Mõõdetud",
            **dict.fromkeys(wu.LOADS, 1.0),
        }
        if over is not None:
            r["pkontsentratsioonlubatud"] = 1.0
            r["pkontsentratsioon1kv"] = over
            r["pkontsentratsioon2kv"] = 0.5
        rows.append(r)
    return pl.DataFrame(rows, schema_overrides=dict.fromkeys(base, pl.Float64))


def test_use_by_type_keeps_unknown_type_and_counts_reports() -> None:
    t = {(r["aruandeaasta"], r["veeliik"]): r for r in wu.use_by_type(use_frame())}
    assert t[(2024, "määramata")]["m3"] == 1000.0 and t[(2024, "Põhjavesi")]["reports"] == 1


def test_sector_totals_and_tiling_check() -> None:
    s = {r["year"]: r for r in wu.use_by_sector(use_frame())}
    assert s[2024]["olme"] == 60.0 and s[2024]["sectors_sum"] == 1100.0
    t = wu.sector_tiling(use_frame())
    assert (t["rows"], t["within_1pct"]) == (3, 2)  # 2025 row: 10 of 50 does not tile


def test_abstraction_monthly_profile_sums_to_total() -> None:
    a = wu.abstraction(abstraction_frame(), abstraction_frame())
    assert a["groundwater"][0]["m3"] == 24.0
    assert (
        a["monthly_groundwater"][0]["total"] == 24.0
        and len(a["monthly_groundwater"][0]["months"]) == 12
    )


def test_discharge_compliance_counts_only_outlets_with_a_limit() -> None:
    d = wu.discharge(discharge_frame())
    c = {r["key"]: r for r in d["compliance"]}
    assert c["p"]["with_limit"] == 2 and c["p"]["over_limit"] == 1
    assert d["years"][0]["outlets"] == 3 and abs(d["years"][0]["calculated_share"] - 2 / 3) < 1e-9


def test_agglomerations_and_reserves() -> None:
    ra = pl.DataFrame(
        {
            "keht_staatus": ["Kehtiv", "Kehtiv", "Kehtetu"],
            "tyyp_selg": ["Üle 2000 ie", "Alla 2000 ie", "Alla 2000 ie"],
            "elanikke": [1000, 100, 5],
            "koormus": [1500.0, 150.0, 9.0],
            "pindala": [10.0, 1.0, 1.0],
        }
    )
    a = wu.agglomerations(ra)
    assert a["valid"] == 2 and a["load_pe_total"] == 1650.0
    res = pl.DataFrame(
        {"keht_staatus": ["Kehtiv", "Kehtetu"], "geol_indeks": ["O", "O"], "varu_t1_olme": [10, 99]}
    )
    r = wu.reserves(res)
    assert r["t1_olme_total"] == 10 and r["by_aquifer"][0]["deposits"] == 1


def test_build_is_json_serialisable() -> None:
    res = pl.DataFrame({"keht_staatus": ["Kehtiv"], "geol_indeks": ["O"], "varu_t1_olme": [10]})
    ra = pl.DataFrame(
        {
            "keht_staatus": ["Kehtiv"],
            "tyyp_selg": ["Üle 2000 ie"],
            "elanikke": [1],
            "koormus": [1.0],
            "pindala": [1.0],
        }
    )
    d = rw.build(
        use_frame(),
        abstraction_frame(),
        abstraction_frame(),
        discharge_frame(),
        res,
        ra,
        "2026-01-01",
    )
    json.dumps(d)
    assert d["meta"]["years"] == [2024, 2025]
