"""Tests for the crown-condition analysis."""

from __future__ import annotations

import polars as pl
import pytest

import crown_analysis as ca


@pytest.mark.parametrize(
    "label,expected",
    [
        (">20-25%", 25.0),
        (">0-5%", 5.0),
        ("0 %, okka/lehekadu ei ole", 0.0),
        ("0%, okka/lehekadu ei ole", 0.0),
        ("100 %, surnud puu", 100.0),
        ("Hindamata", None),
        (None, None),
        ("tundmatu", None),
    ],
)
def test_upper_bound_of_class_labels(label: str | None, expected: float | None) -> None:
    assert ca.upper_bound(label) == expected


def test_damage_class_boundaries() -> None:
    assert [ca.damage_class(u) for u in (0, 10, 15, 25, 30, 60, 65, 100)] == [
        "none", "none", "slight", "slight", "moderate", "moderate", "severe", "severe",
    ]  # fmt: skip


def frame() -> pl.DataFrame:
    rows = []
    for year, labels in (
        (2000, [">20-25%", ">25-30%", ">0-5%", "Hindamata"]),
        (2001, [">30-35%"] * 2),
    ):
        for i, lab in enumerate(labels):
            rows.append(
                {
                    "naitaja_nimetus": ca.INDICATOR,
                    "seireaeg_algus": f"{year}-08-01T00:00:00",
                    "seirekoht_kood": f"P{i % 2}",
                    "isend_nr": str(i),
                    "liik_est": "harilik mänd",
                    "vaartus_muu": lab,
                }
            )
    rows.append({**rows[0], "naitaja_nimetus": "Muu"})
    return pl.DataFrame(rows)


def test_by_year_excludes_not_assessed_and_counts_damaged_share() -> None:
    d = ca.prepare(frame())
    y = {r["year"]: r for r in ca.by_year(d)}
    assert y[2000]["trees"] == 3 and y[2000]["plots"] == 2  # 'Hindamata' dropped
    assert y[2000]["share_damaged"] == pytest.approx(1 / 3)
    assert y[2001]["share_damaged"] == 1.0 and y[2001]["counts"]["moderate"] == 2


def test_checks_report_unassessed_and_duplicates() -> None:
    c = ca.checks(ca.prepare(frame()))
    assert c["rows"] == 6 and c["not_assessed_or_unparsed"] == 1
    assert c["duplicate_groups_among_numbered"] == 0 and c["tree_number_null_share"] == 0.0


def test_build_has_all_and_per_species_series() -> None:
    b = ca.build(frame())
    assert b["all"] and set(b["species"]) == set(ca.SPECIES) and b["species"]["harilik kuusk"] == []
