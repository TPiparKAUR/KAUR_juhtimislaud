"""Tests for the large carnivore observation summaries."""

from __future__ import annotations

import json

import polars as pl

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


def test_effort_and_indicator_structure() -> None:
    b = pa.build(frame())
    h = b["species"]["hunt"]
    assert set(b["species"]) == {"hunt"}
    assert h["effort"][0] == {"year": 2010, "districts": 25, "observations": 25}
    ind = {r["naitaja_nimetus"]: r for r in h["by_indicator"]}
    assert ind[pa.IND_MIN]["districts"] == 25 and ind[pa.IND_AD]["rows"] == 8
    assert "minimum" not in h and "juvenile" not in h
    json.dumps(b)


def test_has_predators() -> None:
    assert pa.has_predators(frame()) and not pa.has_predators(frame().drop("liik_est"))
