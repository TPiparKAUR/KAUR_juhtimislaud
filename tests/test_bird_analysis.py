"""Tests for the preliminary breeding-bird index."""

from __future__ import annotations

import json

import polars as pl
import pytest

import bird_analysis as ba


def frame(decline: bool = True) -> pl.DataFrame:
    rows: list[dict[str, object]] = []
    for year in (2010, 2011, 2012):
        for p in range(30):
            rows.append(  # a species that halves every year
                {
                    "seiretoo_nimetus": "Haudelinnustiku punktloendused ",
                    "liik_est": "A",
                    "seirekoht_kood": f"P{p}",
                    "seireaeg_algus": f"{year}-06-01T00:00:00",
                    "vaartus_arv_moodetud": (8.0 / 2 ** (year - 2010)) if decline else 2.0,
                }
            )
            rows.append(  # a stable species, present in the same points and years
                {
                    "seiretoo_nimetus": "Haudelinnustiku punktloendused ",
                    "liik_est": "B",
                    "seirekoht_kood": f"P{p}",
                    "seireaeg_algus": f"{year}-06-10T00:00:00",
                    "vaartus_arv_moodetud": 1.0,
                }
            )
    rows.append(
        {
            "seiretoo_nimetus": "Põldtsiitsitaja seire ",
            "liik_est": "C",
            "seirekoht_kood": "X",
            "seireaeg_algus": "2011-06-10T00:00:00",
            "vaartus_arv_moodetud": 50.0,
        }
    )
    return pl.DataFrame(rows)


def test_chain_index_follows_halving_species_and_composite_is_geometric_mean() -> None:
    b = ba.build(frame())
    assert b["species_used"] == 2 and b["species_total"] == 2  # programme C is ignored
    sp = {s["name"]: s for s in b["species"]}
    assert sp["A"]["last"] == pytest.approx(25.0) and sp["B"]["last"] == pytest.approx(100.0)
    comp = [c["index"] for c in b["composite"]]
    assert comp[0] == pytest.approx(100.0)
    assert comp[1] == pytest.approx((50.0 * 100.0) ** 0.5)
    assert comp[2] == pytest.approx((25.0 * 100.0) ** 0.5)
    assert all(c["lo"] <= c["index"] <= c["hi"] for c in b["composite"])
    json.dumps(b)


def test_species_with_too_few_pairs_are_dropped() -> None:
    f = frame().filter(~((pl.col("liik_est") == "A") & (pl.col("seirekoht_kood") != "P0")))
    b = ba.build(f)
    assert [s["name"] for s in b["species"]] == ["B"]


def test_has_birds() -> None:
    assert ba.has_birds(frame()) and not ba.has_birds(frame().drop("liik_est"))
