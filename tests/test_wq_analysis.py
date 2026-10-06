"""Tests for the water-quality monitoring analysis."""

from __future__ import annotations

import json

import polars as pl
import pytest

import wq_analysis as wq


def frame() -> pl.DataFrame:
    base = {"vaartus_erimark": None, "pohjaveekogum_kood": None, "seirekogum_tyyp": None}
    rows = []

    def add(name: str, unit: str, value: float | None, year: int, site: str, **kw: object) -> None:
        rows.append(
            {
                **base,
                "naitaja_nimetus": name,
                "naitaja_abr_unit": unit,
                "vaartus_arv_moodetud": value,
                "seireaeg_algus": f"{year}-06-01T00:00:00",
                "seirekoht_kood": site,
                **kw,
            }
        )

    for i in range(4):  # groundwater nitrate: 2 NO3 rows, 2 NO3-N rows (12 mgN = 53.1 mgNO3)
        add("Nitraat (NO3)", "mg/l", 20.0 + i, 2020, f"G{i % 2}", pohjaveekogum_kood="PV1")
    add("Nitraatlämmastik (NO3N)", "mgN/l", 12.0, 2020, "G9", pohjaveekogum_kood="PV1")
    add("Nitraatlämmastik (NO3N)", "mgN/l", None, 2020, "G9", pohjaveekogum_kood="PV1")
    add("Nitraat (NO3)", "ppb", 5.0, 2020, "G9", pohjaveekogum_kood="PV1")
    for i in range(6):  # river total nitrogen in mixed units; 1 mg N/l each
        unit, v = (("mg/l", 1.0), ("µg/l", 1000.0), ("µmolN/l", 71.39))[i % 3]
        add("Üldlämmastik", unit, v, 2021, f"R{i}", seirekogum_tyyp="V2B")
    for i in range(5):  # coastal total phosphorus
        add("Üldfosfor", "mg/m³", 30.0, 2021, f"C{i}", seirekogum_tyyp="R3")
    return pl.DataFrame(
        rows,
        schema_overrides={
            "vaartus_arv_moodetud": pl.Float64,
            "vaartus_erimark": pl.Utf8,
            "pohjaveekogum_kood": pl.Utf8,
            "seirekogum_tyyp": pl.Utf8,
        },
    )


def test_nitrate_is_converted_to_no3_and_bad_rows_excluded() -> None:
    g = wq.groundwater_nitrate(frame())
    y = g["years"][0]
    assert g["rows_used"] == 5 and g["rows_excluded_unit_or_value"] == 2  # null value and ppb unit
    assert y["samples"] == 5 and y["median"] == pytest.approx(22.0)
    assert y["share_over_limit"] == pytest.approx(1 / 5)  # only the 12 mgN/l = 53 mg NO3/l row
    assert y["sites"] == 3


def test_surface_nutrients_convert_units_and_group_by_category() -> None:
    s = wq.surface_nutrients(frame())
    tn = {(r["category"], r["year"]): r for r in s["tn"]}
    assert tn[("Vooluveekogu", 2021)]["median"] == pytest.approx(1.0, abs=0.01)
    tp = {(r["category"], r["year"]): r for r in s["tp"]}
    assert tp[("Rannikuvesi", 2021)]["median"] == pytest.approx(0.03)


def test_small_groups_are_not_reported_and_build_is_json() -> None:
    d = wq.build(frame().filter(pl.col("naitaja_nimetus") != "Üldfosfor"))
    json.dumps(d)
    assert d["surface"]["tp"] == [] and d["checks"]["groundwater_rows"] == 7
