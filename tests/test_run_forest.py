"""Tests for ``run_forest``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import run_forest as rf
from tests.test_forest_analysis import cube


def test_build_is_json_safe_and_keeps_errors() -> None:
    out = rf.build(cube(), "2026-01-01")
    json.dumps(out)
    assert out["meta"]["latest_year"] == 2024
    assert out["national"]["stock"][-1]["err"] == pytest.approx(0.02)
    c = out["changes"]["stock"]["since_start"]
    assert c["from"] == 2019 and c["to"] == 2024 and c["pct"] == pytest.approx(0.1)
    assert c["distinguishable"] is True  # +10% vs. combined 95% half-width of about 3%
    assert out["changes"]["stock"]["last_10_years"] is None  # only 5 years of history
    assert "Riigimetsamaa" in out["owners"]
    assert any("95%" in line for line in out["meta"]["interpretation"])


def test_cli_roundtrip(tmp_path: Path) -> None:
    cube().write_parquet(tmp_path / "raw.parquet")
    rf.main(["--raw", str(tmp_path / "raw.parquet"), "--out", str(tmp_path)])
    data = json.loads((tmp_path / "forest.json").read_text(encoding="utf-8"))
    assert data["national"]["area"][0]["value"] == 2300.0


def test_checks_report_how_well_classes_tile_the_totals() -> None:
    out = rf.build(cube(), "2026-01-01")["checks"]
    # owners (1000 + 1300 in both years) against the national area (2300 -> 2530 in 2024)
    assert out["owners_vs_area"] == pytest.approx(2300.0 / 2530.0)
    assert "species_vs_stock" not in out  # no species rows in the cube
