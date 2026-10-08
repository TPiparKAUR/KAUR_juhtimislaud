"""Tests for the ambient air quality analysis."""

from __future__ import annotations

import json
from datetime import date, timedelta

import polars as pl
import pytest

import air_analysis as aa


def frame() -> pl.DataFrame:
    rows: list[dict[str, object]] = []

    def add(name: str, value: float, unit: str, d: date, station: str, **kw: object) -> None:
        rows.append(
            {
                "naitaja_grupp_selg": aa.GROUP,
                "seiretoo_nimetus": "Välisõhu kvaliteedi seire ",
                "naitaja_nimetus": name,
                "vaartus_arv_moodetud": value,
                "naitaja_abr_unit": unit,
                "seireaeg_algus": f"{d.isoformat()}T00:00:00",
                "seirekoht_kood": station,
                "vaartus_erimark": None,
            }
            | kw
        )

    for year, level in (
        (2010, 20.0),
        (2011, 20.0),
        (2012, 20.0),
        (2020, 10.0),
        (2021, 10.0),
        (2022, 10.0),
    ):
        for i in range(365):
            day = date(year, 1, 1) + timedelta(days=i)
            for st in ("A", "B", "C"):
                add("Lämmastikdioksiid", level, "µg/m³", day, st)
    for year in (2010, 2011, 2012, 2020, 2021, 2022):
        for i in range(365):
            add(
                "Peened osakesed (PM 10)",
                60.0 if i < 40 else 12.0,
                "µg/m³",
                date(year, 1, 1) + timedelta(days=i),
                "A",
            )
    add("Lämmastikdioksiid", 99.0, "ppbv", date(2020, 1, 1), "A")  # other unit, excluded
    add("Lämmastikdioksiid", -999.0, "µg/m³", date(2020, 1, 2), "A")  # sentinel, excluded
    for i in range(60):  # indicative: Pb in µg/m³ and ng/m³
        add("Plii", 0.01, "µg/m³", date(2015, 1, 1) + timedelta(days=i), "A")
    add("Plii", 5.0, "ng/m³", date(2015, 3, 5), "B")
    return pl.DataFrame(rows, schema_overrides={"vaartus_erimark": pl.Utf8})


def test_units_and_sentinels_are_left_out_and_counted() -> None:
    d = aa.prepare(frame())
    g, left = aa.value_column(d, "Lämmastikdioksiid")
    assert left["other_unit"] == 1 and left["negative_or_sentinel"] == 1
    assert g["v"].max() == 20.0


def test_lead_in_other_unit_is_not_converted() -> None:
    g, left = aa.value_column(aa.prepare(frame()), "Plii")
    assert g["v"].to_list() == [5.0] and left["other_unit"] == 60


def test_completeness_rule_and_paired_change() -> None:
    b = aa.build(frame())
    no2 = b["indicators"]["Lämmastikdioksiid"]
    assert [r["year"] for r in no2["years"]][:2] == [2010, 2011]
    assert no2["years"][0]["stations"] == 3
    p = no2["paired"]
    assert p["stations"] == 3 and p["median_change_pct"] == pytest.approx(-50.0)
    assert p["share_decreased"] == 1.0
    assert "Plii" not in b["indicators"]  # 1 usable day only
    assert aa.has_air(frame()) and not aa.has_air(frame().drop("seirekoht_kood"))
    json.dumps(b)


def test_pm10_exceedance_days() -> None:
    rows = [
        {
            "naitaja_grupp_selg": aa.GROUP,
            "seiretoo_nimetus": "Välisõhu kvaliteedi seire ",
            "naitaja_nimetus": "Peened osakesed (PM 10)",
            "vaartus_arv_moodetud": 60.0 if i < 40 else 10.0,
            "naitaja_abr_unit": "µg/m³",
            "seireaeg_algus": f"{(date(2015, 1, 1) + timedelta(days=i)).isoformat()}T00:00:00",
            "seirekoht_kood": "A",
            "vaartus_erimark": None,
        }
        for i in range(365)
    ]
    r = aa.build(pl.DataFrame(rows, schema_overrides={"vaartus_erimark": pl.Utf8}))
    y = r["indicators"]["Peened osakesed (PM 10)"]["years"][0]
    assert y["over50_max"] == 40 and y["over50_stations_above_allowed"] == 1


def test_paired_needs_enough_stations() -> None:
    f = frame().filter(pl.col("seirekoht_kood") != "C")
    assert aa.build(f)["indicators"]["Lämmastikdioksiid"]["paired"] is None
