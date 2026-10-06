"""Tests for the water-body status analysis."""

from __future__ import annotations

import json
from typing import Any

import polars as pl

import run_water as rw
import water_analysis as wa


def register() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "id": [1, 2, 3, 4, 5],
            "veekogu_tyyp": ["12", "12", "22", "30", None],
            "keht_staatus": ["Kehtiv", "Kehtiv", "Kehtiv", "Kehtiv", "Kehtetu"],
        }
    )


def states() -> pl.DataFrame:
    rows: list[dict[str, Any]] = []

    def add(vkm: int, year: str, seis: str | None, tyyp: str = "S", **kw: Any) -> None:
        rows.append(
            {
                "vkm_id": vkm,
                "aasta": year,
                "tyyp": tyyp,
                "seis": seis,
                "keht_staatus": kw.get("keht", "Kehtiv"),
                "muut_aeg": kw.get("muut", "2020-01-01"),
                "staatus": kw.get("staatus"),
            }
        )

    for vkm, seis in ((1, "2"), (2, "3"), (3, "4"), (4, "U")):
        add(vkm, "2015", seis)
    add(1, "2021", "3")  # worsened 2 -> 3
    add(2, "2022", "3")  # same
    add(3, "2023", "2")  # improved 4 -> 2
    add(4, "2023", "3")  # baseline not classified: excluded from pairs
    add(1, "2021", "5", muut="2019-01-01")  # older duplicate must lose
    add(2, "2015", "1", keht="Kehtetu")  # invalid rows are ignored
    add(1, "2015", "2", tyyp="E", staatus="saavutatud")
    add(2, "2015", "3", tyyp="E", staatus="saavutamata")
    add(3, "2015", "2", tyyp="E")
    return pl.DataFrame(rows)


def pressures() -> pl.DataFrame:
    base = {"koormus_staatus_selg": "Survetegur on aktuaalne"}
    rows = [
        {
            "koormus_veekogum_id": 1,
            "olulisus_selg": "Oluline",
            "pohjus_selg": "Põllumajandus",
            "hinnang_moju_selg": "Saastus toitainetega",
            **base,
        },
        {
            "koormus_veekogum_id": 1,
            "olulisus_selg": "Oluline",
            "pohjus_selg": "Tööstus",
            "hinnang_moju_selg": "Keemiline saastus",
            **base,
        },
        {
            "koormus_veekogum_id": 2,
            "olulisus_selg": "Väheoluline",
            "pohjus_selg": "Tööstus",
            "hinnang_moju_selg": "Keemiline saastus",
            **base,
        },
        {
            "koormus_veekogum_id": 5,
            "olulisus_selg": "Oluline",
            "pohjus_selg": "Tööstus",
            "hinnang_moju_selg": "Keemiline saastus",
            **base,
        },  # invalid body: ignored
    ]
    return pl.DataFrame(rows)


def gw() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "aasta": [2014, 2014, 2020, 2020],
            "pohjaveekogum_id": [1, 2, 1, 2],
            "seis": ["1", "3", "2", "3"],
            "seis_kem": ["1", "3", "2", "3"],
            "seis_kog": ["1", "1", "1", "1"],
        }
    )


def test_valid_states_drops_invalid_and_keeps_latest_duplicate() -> None:
    cur = wa.valid_states(states(), register())
    one = cur.filter((pl.col("vkm_id") == 1) & (pl.col("year") == 2021))
    assert one.height == 1 and one["seis"][0] == "3"
    assert cur.filter(pl.col("tyyp") != "S").is_empty()
    assert cur.filter((pl.col("vkm_id") == 2) & (pl.col("year") == 2015))["seis"][0] == "3"


def test_distribution_excludes_unclassified_from_share() -> None:
    cur = wa.valid_states(states(), register())
    d = wa.distribution(cur.filter(pl.col("year") == 2015))
    assert d["n"] == 4 and d["classified"] == 3 and d["not_classified"] == 1
    assert d["share_good"] == 1 / 3 and d["counts"]["2"] == 1


def test_paired_compares_the_same_bodies_only() -> None:
    cur = wa.valid_states(states(), register())
    p = wa.paired(cur)
    assert p["all"] == {
        "n": 3,
        "improved": 1,
        "same": 1,
        "worsened": 1,
        "good_before": 1,
        "good_after": 1,
    }
    assert p["by_group"]["Vooluveekogu"]["n"] == 2 and p["by_group"]["Meri"]["n"] == 0
    assert p["matrix"]["4"]["2"] == 1 and p["later_years"] == {"min": 2021, "max": 2023}


def test_targets_count_only_flagged_objectives() -> None:
    t = wa.targets(states())
    assert (t["objective_rows"], t["flagged"], t["achieved"], t["not_achieved"]) == (3, 2, 1, 1)


def test_pressures_use_valid_bodies_and_significant_current_only() -> None:
    p = wa.pressures(pressures(), register())
    assert p["assessed_bodies"] == 2 and p["bodies_with_significant"] == 1
    assert {r["name"]: r["bodies"] for r in p["by_sector"]} == {"Põllumajandus": 1, "Tööstus": 1}


def test_groundwater_paired_by_body() -> None:
    g = wa.groundwater(gw())
    assert g["years"][2014]["counts"] == {"1": 1, "2": 0, "3": 1}
    assert g["paired"] == {
        "from": 2014,
        "to": 2020,
        "n": 2,
        "improved": 0,
        "same": 1,
        "worsened": 1,
    }


def test_build_is_json_serialisable_with_consistent_totals() -> None:
    d = rw.build(register(), states(), pressures(), gw(), "2026-01-01")
    json.dumps(d)
    assert d["checks"]["by_year_total"] == d["checks"]["status_rows_valid_S"]
    assert d["baseline_distribution"]["n"] == 4
