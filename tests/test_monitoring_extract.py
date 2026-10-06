"""Tests for ``monitoring_extract`` against the fake PostgREST server."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import polars as pl
import pytest

import monitoring_extract as me
from tests.fake_postgrest import fake_server


def table() -> list[dict[str, Any]]:
    rows = []
    for i in range(23):
        r = dict.fromkeys(me.COLUMNS)
        r |= {
            "naitaja_nimetus": "Okka/lehekadu kogu võra ulatuses" if i < 17 else "Muu",
            "vaartus_arv_moodetud": float(5 * (i % 6)),
            "seireaeg_algus": f"{2000 + i % 3}-08-01T00:00:00",
            "seirekoht_kood": f"P{i % 4}",
            "liik_est": "harilik mänd" if i % 2 else "harilik kuusk",
            "isend_nr": str(i),
        }
        rows.append(r)
    return rows


@pytest.fixture(autouse=True)
def no_real_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time, "sleep", lambda _s: None)


def test_extract_reads_only_the_indicator_and_every_row(tmp_path: Path) -> None:
    with fake_server({me.TABLE: table()}, max_rows=5) as (url, _s):
        me.main(
            [
                "--indicator",
                "Okka/lehekadu kogu võra ulatuses",
                "--out",
                str(tmp_path),
                "--base-url",
                url,
            ]
        )
    df = pl.read_parquet(tmp_path / "monitoring_extract.parquet")
    assert df.height == 17 and set(df["naitaja_nimetus"]) == {"Okka/lehekadu kogu võra ulatuses"}
    s = json.loads((tmp_path / "monitoring_extract_summary.json").read_text(encoding="utf-8"))
    assert s["rows"] == 17 and s["plots"] == 4 and s["years"] == [2000, 2002]


def test_indicators_with_different_null_columns_can_be_combined(tmp_path: Path) -> None:
    rows = table()
    for r in rows:
        if r["naitaja_nimetus"] == "Muu":
            r["naitaja_abr_unit"] = "mg/l"  # the other indicator has no unit at all
    with fake_server({me.TABLE: rows}, max_rows=5) as (url, _s):
        me.main(
            [
                "--indicator",
                "Okka/lehekadu kogu võra ulatuses",
                "--indicator",
                "Muu",
                "--out",
                str(tmp_path),
                "--base-url",
                url,
            ]
        )
    df = pl.read_parquet(tmp_path / "monitoring_extract.parquet")
    assert df.height == 23 and df["naitaja_abr_unit"].null_count() == 17
    s = json.loads((tmp_path / "monitoring_extract_summary.json").read_text(encoding="utf-8"))
    assert set(s["per_indicator"]) == {"Okka/lehekadu kogu võra ulatuses", "Muu"}


def test_group_selection_reads_all_indicators_of_the_group(tmp_path: Path) -> None:
    rows = table()
    for r in rows:
        r["naitaja_grupp_selg"] = "Muld" if r["naitaja_nimetus"] == "Muu" else "Puud"
    with fake_server({me.TABLE: rows}, max_rows=5) as (url, _s):
        me.main(["--group", "Muld", "--out", str(tmp_path), "--base-url", url])
    df = pl.read_parquet(tmp_path / "monitoring_extract.parquet")
    assert df.height == 6 and set(df["naitaja_grupp_selg"]) == {"Muld"}
