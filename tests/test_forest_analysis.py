"""Tests for ``forest_analysis`` on a synthetic cube with the shapes of the real table."""

from __future__ import annotations

import math
from typing import Any

import polars as pl
import pytest

import forest_analysis as fa

COLS = ["tabeli_number", "tunnus", "arvutus", "periood", "aasta", "arvvaartus", "suhteline_viga",
        *fa.DIMS]  # fmt: skip


def row(table: int, indicator: str, calc: str, year: int, value: float, err: float | None,
        period: str = "5", **dims: str) -> dict[str, Any]:  # fmt: skip
    base: dict[str, Any] = dict.fromkeys(COLS)
    base.update(tabeli_number=table, tunnus=indicator, arvutus=calc, periood=period, aasta=year,
                arvvaartus=value, suhteline_viga=err, **dims)  # fmt: skip
    return base


def cube() -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for y, scale in ((2019, 1.0), (2024, 1.1)):
        lnd = {"maakategooria": "Metsamaa"}
        rows += [
            row(24, "Pindala", fa.SUM, y, 2300 * scale, 0.01, **lnd),
            row(24, "Pindala", fa.SUM, y, 999.0, 0.6, **lnd, maakond="Harju"),  # must not leak
            row(24, "Kasvavate puude maht", fa.SUM, y, 400_000 * scale, 0.02, **lnd),
            row(24, "Kasvavate puude maht", fa.MEAN, y, 170 * scale, 0.01, **lnd),
            row(6, "Juurdekasv", fa.SUM, y, 15_000.0, 0.014, **lnd, enamuspuuliik="Puistud"),
            row(6, "Juurdekasv", fa.SUM, y, 7_000.0, 0.02, **lnd, enamuspuuliik="Mänd"),
            row(23, "Raiutud maht", fa.SUM, y, 10_000.0, 0.08, "5", **lnd, filtri_tunnus1="Raieliik",
                filter1="Raied kokku", filtri_tunnus2="Raie aeg", filter2="Hooajaraie"),
            row(23, "Raiutud maht", fa.SUM, y, 3_000.0, 0.2, "5", **lnd, filtri_tunnus1="Raieliik",
                filter1="Lageraie", filtri_tunnus2="Raie aeg", filter2="Hooajaraie"),
            row(5351, "Kuivanud puude maht", fa.SUM, y, 3000.0, 0.1, **lnd, omand="Riigimetsamaa"),
            row(5351, "Kuivanud puude maht", fa.SUM, y, 1000.0, 0.2, **lnd, omand="Teised maaomanikud"),
            row(5351, "Lamapuidu maht", fa.SUM, y, 5000.0, 0.1, **lnd, omand="Riigimetsamaa"),
            row(5351, "Lamapuidu maht", fa.SUM, y, 3000.0, 0.1, **lnd, omand="Teised maaomanikud"),
            row(1, "Pindala", fa.SUM, y, 1000.0, 0.02, **lnd, omand="Riigimetsamaa"),
            row(1, "Pindala", fa.SUM, y, 1300.0, 0.02, **lnd, omand="Teised maaomanikud"),
            row(13, "Pindala", fa.SUM, y, 100.0, 0.05, **lnd, omand="Riigimetsamaa",
                filtri_tunnus2="Vanus", filter2="81…100 a"),
            row(13, "Pindala", fa.SUM, y, 200.0, 0.05, **lnd, omand="Teised maaomanikud",
                filtri_tunnus2="Vanus", filter2="81…100 a"),
        ]  # fmt: skip
    return pl.DataFrame(rows, infer_schema_length=None)


def test_exact_ignores_sub_totals_with_extra_classifiers() -> None:
    area = fa.series(fa.exact(cube(), 24, "Pindala", fa.SUM, maakategooria="Metsamaa"))
    assert [r["value"] for r in area] == [2300.0, 2530.0]  # the Harju row (999) is not mixed in


def test_national_picks_totals_not_species_or_cutting_types() -> None:
    n = fa.national(cube())
    assert n["increment"][0]["value"] == 15_000.0  # 'Puistud', not Mänd (7000)
    assert n["felling_5y"][0]["value"] == 10_000.0  # 'Raied kokku', not Lageraie (3000)
    ratio = n["felling_to_increment_5y"][0]
    assert ratio["value"] == pytest.approx(10 / 15)
    assert ratio["err"] == pytest.approx(math.hypot(0.08, 0.014))


def test_total_over_owners_adds_values_and_combines_errors() -> None:
    t = fa.total_over(
        cube(), "omand", 5351, "Kuivanud puude maht", fa.SUM, maakategooria="Metsamaa"
    )
    assert t[0]["value"] == 4000.0
    assert t[0]["err"] == pytest.approx(math.hypot(300.0, 200.0) / 4000.0)


def test_deadwood_per_ha_adds_standing_and_lying() -> None:
    n = fa.national(cube())
    assert n["deadwood_total"][0]["value"] == 12_000.0
    assert n["deadwood_per_ha"][0]["value"] == pytest.approx(12_000.0 / 2300.0)


def test_change_flags_only_differences_larger_than_the_combined_error() -> None:
    a = {"year": 2019, "value": 100.0, "err": 0.05}
    big = fa.change(a, {"year": 2024, "value": 130.0, "err": 0.05})
    assert big["distinguishable"] and big["pct"] == pytest.approx(0.3)
    small = fa.change(a, {"year": 2024, "value": 104.0, "err": 0.05})
    assert small["distinguishable"] is False
    assert fa.change(a, {"year": 2024, "value": 130.0, "err": None})["distinguishable"] is None


def test_owner_age_and_error_summaries() -> None:
    d = cube()
    assert set(fa.owners(d)) == {"Riigimetsamaa", "Teised maaomanikud"}
    assert fa.age_structure(d)["81…100 a"][0]["value"] == 300.0
    q = fa.error_summary(d)
    assert q["rows"] == d.height and q["share_over_50pct"] == pytest.approx(2 / d.height)


def test_categories_without_a_matching_series_are_dropped_not_returned_empty() -> None:
    """Regression: a species present only in the increment rows gave an empty stock series."""
    d = cube()
    assert "Mänd" in set(d["enamuspuuliik"].drop_nulls())
    assert fa.species(d) == {}  # no stock-by-species rows in the cube -> nothing, not {"Mänd": []}
    assert fa.management(d) == {} and fa.counties(d) == {}


def test_age_class_scheme_is_chosen_by_numbers_not_by_the_dot_character() -> None:
    """Regression: 10-year and 20-year classes share one classifier, with look-alike dots."""
    ten = ["...10 a", "11...20 a", "21...30 a", "31...40 a", "141...  a"]
    for dots in ("…", "\u2025", "..."):  # real data used a character that is not U+2026
        twenty = [f"{dots}20 a", f"21{dots}40 a", f"41{dots}60 a", f"61{dots}80 a", f"81{dots}100 a",
                  f"101{dots}120 a", f"121{dots} a"]  # fmt: skip
        assert fa.age_class_set(ten + twenty) == twenty
    assert fa.age_class_set(ten + twenty, 10)[:2] == ["...10 a", "11...20 a"]
    assert fa.age_class_set([]) == []


def test_age_structure_keeps_the_chosen_scheme_in_order() -> None:
    rows = []
    for name, v in (("81…100 a", 100.0), ("21…40 a", 400.0), ("21...30 a", 250.0), ("31...40 a", 150.0),
                    ("41…60 a", 300.0), ("61…80 a", 200.0), ("…20 a", 50.0), ("101…120 a", 70.0),
                    ("121… a", 30.0)):  # fmt: skip
        rows.append(row(13, "Pindala", fa.SUM, 2024, v, 0.05, maakategooria="Metsamaa",
                        omand="Riigimetsamaa", filtri_tunnus2="Vanus", filter2=name))  # fmt: skip
    got = fa.age_structure(pl.DataFrame(rows, infer_schema_length=None))
    assert list(got) == [
        "…20 a",
        "21…40 a",
        "41…60 a",
        "61…80 a",
        "81…100 a",
        "101…120 a",
        "121… a",
    ]


def test_shares_check_flags_classes_that_do_not_tile_the_total() -> None:
    assert fa.shares_check([600.0, 400.0], 1000.0) == pytest.approx(1.0)
    assert fa.shares_check([600.0, 900.0], 1000.0) == pytest.approx(1.5)  # overlapping classes
    assert fa.shares_check([1.0], None) is None
