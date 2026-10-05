"""Tests for ``waste_fetch``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import polars as pl

import waste_fetch as wf
from postgrest import PostgrestError


def row(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = dict.fromkeys(wf.KEYS, "x")
    base.update(aasta=2022, materjali_kood=1, maht=1.0)
    base.update(kw)
    return base


def test_aggregate_sums_and_counts_negatives() -> None:
    df = wf.aggregate([row(maht=5.0), row(maht=-2.0), row(jaatmeliik="y", maht=1.0)])
    x = df.filter(pl.col("jaatmeliik") == "x").to_dicts()[0]
    assert x["maht"] == 3.0 and x["rows"] == 2 and x["neg_rows"] == 1 and x["neg_sum"] == -2.0
    assert wf.aggregate([]).is_empty()


def test_tasks_cover_residual_slices_and_newest_year_first() -> None:
    tasks = wf.make_tasks(2020, 2021)
    assert tasks[0].year == 2021 and len(tasks) == 2 * (len(wf.TYPES) + 1) * (len(wf.GROUPS) + 1)
    residual = wf.Task(2021, None, None).filters()
    assert residual["maht_liik"].startswith("not.in.(") and '"Eksport"' in residual["maht_liik"]
    assert wf.Task(2021, "Import", "20").filters()["pohigrupp"] == "eq.20"


def test_run_collects_failures_mismatches_and_writes_outputs(tmp_path: Path) -> None:
    tasks = [
        wf.Task(2022, "Import", "01"),
        wf.Task(2022, "Import", "02"),
        wf.Task(2022, None, None),
    ]

    def fake(t: wf.Task, delay: float) -> tuple[pl.DataFrame, int, int]:
        if t.pohigrupp == "02":
            raise PostgrestError("timeout")
        if t.pohigrupp is None:
            return wf.aggregate([row()]), 2, 1  # server said 2 rows, only 1 came back
        return wf.aggregate([row(maht=4.0)]), 1, 1

    df = wf.run(tasks, tmp_path, workers=2, delay=0.0, budget_s=60, fetch=fake)
    log = (tmp_path / "waste_fetch_log.json").read_text(encoding="utf-8")
    assert df.height >= 1 and (tmp_path / "waste_agg.parquet").exists()
    assert "timeout" in log and '"expected": 2' in log
