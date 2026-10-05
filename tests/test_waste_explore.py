"""Tests for ``waste_explore``."""

from __future__ import annotations

from typing import Any

import polars as pl

import waste_explore as we


def frame() -> pl.DataFrame:
    base: dict[str, list[Any]] = {c: ["x"] * 4 for c in we.GRAIN_COLUMNS}
    base["maht_liik"] = ["Eksport", "Eksport", "Kõrvaldamine", "Kõrvaldamine"]
    base["maht"] = [1.0, 1.0, 5.0, -2.0]
    base["aasta"] = [2022] * 4
    base["partner_riik_nimi"] = ["Rootsi", "Rootsi", "Määramata", "Määramata"]
    return pl.DataFrame(base)


def test_grain_diagnostics_counts_negatives_and_duplicates() -> None:
    g = we.grain_diagnostics(frame())
    by = {r["maht_liik"]: r for r in g["by_maht_liik"]}
    assert by["Kõrvaldamine"]["neg"] == 1 and by["Eksport"]["total"] == 2.0
    assert g["duplicates"]["groups_with_multiple_rows"] == 2
    assert g["duplicates"]["groups_with_different_amounts"] == 1
    assert g["partner_countries"][0]["partner_riik_nimi"] == "Rootsi"
