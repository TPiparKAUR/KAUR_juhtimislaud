"""Tests for the monitoring site data."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl

import monitoring_catalog as mc
import run_monitoring as rm
from tests.test_crown_analysis import frame
from tests.test_monitoring_catalog import agg


def test_build_combines_coverage_and_crown_and_is_json() -> None:
    catalog = mc.catalog(agg())
    d = rm.build(catalog, frame(), "2026-01-01")
    json.dumps(d)
    assert d["coverage"]["rows"] == 160
    assert {g["name"] for g in d["coverage"]["groups"]} == {"Puud", "Vesi"}
    assert d["crown"]["all"] and d["meta"]["interpretation"]


def test_main_reads_files(tmp_path: Path) -> None:
    (tmp_path / "c.json").write_text(json.dumps(mc.catalog(agg())), encoding="utf-8")
    frame().write_parquet(tmp_path / "e.parquet")
    rm.main(
        [
            "--catalog",
            str(tmp_path / "c.json"),
            "--extract",
            str(tmp_path / "e.parquet"),
            "--out",
            str(tmp_path),
        ]
    )
    assert (tmp_path / "monitoring.json").exists() and isinstance(
        pl.read_parquet(tmp_path / "e.parquet"), pl.DataFrame
    )
