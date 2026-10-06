"""Tests for ``waste_analysis``."""

from __future__ import annotations

import polars as pl
import pytest

import waste_analysis as wa


def frame() -> pl.DataFrame:
    def r(year: int, flow: str, t: float, neg: float = 0.0, **kw: object) -> dict[str, object]:
        base: dict[str, object] = {
            "aasta": year,
            "maht_liik": flow,
            "pohigrupp": "20",
            "pohigrupp_nimi": "OLMEJÄÄTMED",
            "jaatmeliik": "20 03 01",
            "jaatmeliik_nimi": "Segaolmejäätmed",
            "ohtlik_lipp": "Ei",
            "biojaatmed_lipp": "Ei",
            "reoveesetted_lipp": "Ei",
            "metallijaatmed_lipp": "Ei",
            "probleemtooted_lipp": "Ei",
            "partner_riik_nimi": None,
            "maht": t,
            "rows": 2,
            "neg_rows": 1 if neg else 0,
            "neg_sum": neg,
        }
        base.update(kw)
        return base

    return pl.DataFrame(
        [
            r(2021, wa.GENERATION, 100.0, -10.0),
            r(2021, wa.GENERATION, 20.0, ohtlik_lipp="Jah", pohigrupp="13"),
            r(2022, wa.GENERATION, 150.0),
            r(2021, wa.STOCK_END, 50.0),
            r(2022, wa.STOCK_START, 45.0),
            r(2021, wa.EXPORT, 7.0, partner_riik_nimi="Rootsi"),
            r(2022, wa.EXPORT, 3.0, partner_riik_nimi="Soome"),
        ],
        infer_schema_length=None,
    )


def test_flow_totals_are_net_and_expose_negatives() -> None:
    d = wa.clean(frame())
    g = {(r["aasta"], r["maht_liik"]): r for r in wa.flow_totals(d)}
    gen = g[(2021, wa.GENERATION)]
    assert gen["tonnes"] == 120.0 and gen["negative_tonnes"] == -10.0 and gen["negative_rows"] == 1


def test_flows_are_never_added_together() -> None:
    d = wa.clean(frame())
    assert {r["maht_liik"] for r in wa.flow_totals(d)} >= {wa.GENERATION, wa.EXPORT}
    assert all(
        r["maht_liik"] in {wa.GENERATION, wa.EXPORT, wa.STOCK_END, wa.STOCK_START}
        for r in wa.flow_totals(d)
    )


def test_hazardous_share() -> None:
    h = {r["aasta"]: r for r in wa.hazardous(wa.clean(frame()), wa.GENERATION)}
    assert h[2021]["share"] == pytest.approx(20 / 120) and h[2022]["share"] == 0.0


def test_stock_continuity_ratio() -> None:
    c = wa.stock_continuity(wa.clean(frame()))
    assert c == [{"aasta": 2021, "closing": 50.0, "next_opening": 45.0, "ratio": 0.9}]


def test_top_types_and_partners_and_names() -> None:
    d = wa.clean(frame())
    assert wa.top_types(d, wa.GENERATION, 2021)[0]["jaatmeliik"] == "20 03 01"
    assert {r["partner_riik_nimi"] for r in wa.trade_partners(d, wa.EXPORT)} == {"Rootsi", "Soome"}
    assert wa.chapter_names(d)["20"] == "OLMEJÄÄTMED"
    assert wa.coverage(d)[0] == {"aasta": 2021, "rows": 8}


def with_packaging() -> pl.DataFrame:
    extra = (
        frame()
        .head(1)
        .with_columns(
            maht_liik=pl.lit(wa.RECOVERY),
            aasta=pl.lit(2021),
            maht=pl.lit(60.0),
            pohigrupp=pl.lit("15"),
            jaatmeliik=pl.lit("15 01 01"),
            biojaatmed_lipp=pl.lit("Jah"),
        )
    )
    return pl.concat([frame(), extra.cast(frame().schema)])


def test_streams_select_by_code_and_flag_and_keep_flows_apart() -> None:
    d = wa.clean(with_packaging())
    st = wa.streams(d, 2022)
    muni = {r["aasta"]: r["tonnes"] for r in st["municipal"]["flows"][wa.GENERATION]}
    assert muni == {2021: 100.0, 2022: 150.0}  # chapter 20 only, hazardous chapter 13 excluded
    assert [r["tonnes"] for r in st["packaging"]["flows"][wa.RECOVERY]] == [60.0]
    assert (
        st["packaging"]["flows"][wa.GENERATION] == []
    )  # no generation rows: stays empty, no ratio
    assert (
        st["bio"]["rows"] == 2 and st["municipal"]["top_generation"][0]["jaatmeliik"] == "20 03 01"
    )


def test_flag_values_report_the_convention_used() -> None:
    fv = wa.flag_values(wa.clean(with_packaging()))
    assert {r["biojaatmed_lipp"] for r in fv["biojaatmed_lipp"]} == {"Ei", "Jah"}
