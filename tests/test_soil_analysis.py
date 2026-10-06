"""Tests for the soil monitoring analysis."""

from __future__ import annotations

import json

import polars as pl
import pytest

import soil_analysis as sa


def frame() -> pl.DataFrame:
    rows = []

    def add(name: str, value: float, unit: str | None, year: int, plot: str, **kw: object) -> None:
        rows.append(
            {
                "seiretoo_nimetus": "Mullaseire 2004",
                "naitaja_proovimaatriks_nimi": "Muld, pinnas",
                "naitaja_nimetus": name,
                "vaartus_arv_moodetud": value,
                "naitaja_abr_unit": unit,
                "seireaeg_algus": f"{year}-07-01T00:00:00",
                "seirekoht_kood": plot,
                "vaartus_erimark": None,
            }
            | kw
        )

    for i in range(25):  # pH in two periods, same plots, acidifying by 0.5
        add("pH", 6.0, None, 2003, f"P{i}")
        add("pH", 5.5, None, 2019, f"P{i}")
    add("pH", 42921.0, None, 2003, "BAD")  # data error, excluded
    add("Plii", 10.0, "mg/kg KA", 2003, "P0")
    add("Plii", 20000.0, "µg/kg KA", 2003, "P1")  # = 20 mg/kg
    add("Plii", 30.0, "ppm", 2003, "P2")
    add("pH", 7.0, None, 2003, "F1", seiretoo_nimetus="Metsaseire 2004")  # other programme
    add("pH", 7.0, None, 2003, "S1", naitaja_proovimaatriks_nimi="Põhjasetted (veekogust)")
    return pl.DataFrame(
        rows, schema_overrides={"naitaja_abr_unit": pl.Utf8, "vaartus_erimark": pl.Utf8}
    )


def test_periods_are_five_years_from_2002() -> None:
    assert [sa.period_label(y) for y in (2002, 2006, 2007, 2019, 2025)] == [
        "2002-2006", "2002-2006", "2007-2011", "2017-2021", "2022-2026",
    ]  # fmt: skip


def test_only_soil_programme_rows_and_ph_range() -> None:
    d = sa.prepare(frame())
    assert set(d["seiretoo_nimetus"]) == {"Mullaseire 2004"}
    ph = sa.value_column(d, "pH")
    assert ph.height == 50 and max(ph["v"].to_list()) <= 10


def test_units_are_converted_to_mg_per_kg() -> None:
    g = sa.value_column(sa.prepare(frame()), "Plii")
    assert sorted(g["v"].to_list()) == [10.0, 20.0, 30.0]


def test_paired_change_uses_plots_present_in_both_periods() -> None:
    b = sa.build(frame())
    p = b["indicators"]["pH"]["paired"]
    assert (
        p["plots"] == 25
        and p["median_change"] == pytest.approx(-0.5)
        and p["share_increased"] == 0.0
    )
    assert b["indicators"]["Plii"]["paired"] is None  # fewer than two periods with >= 20 plots
    json.dumps(b)
