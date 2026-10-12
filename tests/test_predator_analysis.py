"""Tests for the large carnivore observation summaries."""

from __future__ import annotations

import json

import polars as pl
import pytest

import predator_analysis as pa


def frame() -> pl.DataFrame:
    rows: list[dict[str, object]] = []

    def add(ind: str, value: float, year: int, district: str, species: str = "hunt") -> None:
        rows.append(
            {
                "seiretoo_nimetus": "Hundivaatlused jahipiirkondades 2020",
                "naitaja_nimetus": ind,
                "liik_est": species,
                "seirekoht_kood": district,
                "seireaeg_algus": f"{year}-02-01T00:00:00",
                "vaartus_arv_moodetud": value,
            }
        )

    for year in range(2010, 2018):
        for d in range(25):
            add(pa.IND_MIN, 2.0 if year < 2013 else 3.0, year, f"D{d}")
            add(pa.IND_ALL, 1.0 + (d % 2), year, f"D{d}")
        add(pa.IND_AD, 3.0, year, "D0")
        add(pa.IND_JUV, 1.0, year, "D0")
    add(pa.IND_ALL, 9.0, 2017, "D0", species="rebane")  # other species, ignored
    rows.append(rows[0] | {"seiretoo_nimetus": "Muu seire", "vaartus_arv_moodetud": 99.0})
    return pl.DataFrame(rows)


def test_effort_group_juvenile_and_paired_minimum() -> None:
    b = pa.build(frame())
    h = b["species"]["hunt"]
    assert set(b["species"]) == {"hunt"}
    assert h["effort"][0] == {"year": 2010, "districts": 25, "observations": 25}
    assert h["group"][0]["mean"] == pytest.approx(1.48)  # 13 districts report 1 and 12 report 2
    assert h["juvenile"][0]["share"] == pytest.approx(0.25)
    p = h["minimum"]["paired"]
    assert p["districts"] == 25 and p["mean_first"] == pytest.approx(2.0)
    assert p["mean_last"] == pytest.approx(3.0) and p["share_increased"] == 1.0
    json.dumps(b)


def test_has_predators() -> None:
    assert pa.has_predators(frame()) and not pa.has_predators(frame().drop("liik_est"))
