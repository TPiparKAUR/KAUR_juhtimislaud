"""Tests for ``monitoring_fetch`` (pure aggregation and an end-to-end read on the fake server)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import polars as pl
import pytest

import monitoring_fetch as mf
from tests.fake_postgrest import fake_server


def table() -> list[dict[str, Any]]:
    rows = []
    for year, n in ((2019, 13), (2020, 9)):
        for i in range(n):
            row = dict.fromkeys(mf.KEYS)
            row |= {
                "naitaja_kood": "TN",
                "naitaja_nimetus": "Üldlämmastik",
                "naitaja_abr_unit": "mg/l",
                "liik_est": "kass" if i % 3 == 0 else None,
                mf.TIME: f"{year}-0{1 + i % 9}-15T00:00:00",
                mf.VALUE: -1.0 if i == 0 else float(i),
            }
            rows.append(row)
    rows.append(dict.fromkeys(mf.KEYS) | {mf.TIME: "1990-01-01T00:00:00", mf.VALUE: None})
    return rows


@pytest.fixture(autouse=True)
def no_real_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time, "sleep", lambda _s: None)


def test_aggregate_counts_values_and_negatives() -> None:
    df = mf.aggregate([r for r in table() if r[mf.TIME].startswith("2019")])
    assert df["rows"].sum() == 13 and df["n_value"].sum() == 13 and df["n_negative"].sum() == 1
    assert df.filter(pl.col("liik_est") == "kass")["rows"].sum() == 5


def test_year_filters_cover_before_and_calendar_years() -> None:
    assert mf.year_filter(0) == {mf.TIME: "lt.1995-01-01"}
    assert "2020-01-01" in mf.year_filter(2019)["and"]


def test_end_to_end_read_matches_exact_counts_per_year(tmp_path: Path) -> None:
    with fake_server({mf.TABLE: table()}, max_rows=5, fail_every=7) as (url, _s):
        mf.main(
            [
                "--out",
                str(tmp_path),
                "--years",
                "2019",
                "2020",
                "0",
                "--base-url",
                url,
                "--workers",
                "3",
            ]
        )
    log = json.loads((tmp_path / "monitoring_part_2019_2020_0.json").read_text(encoding="utf-8"))
    assert log["rows_read"] == log["rows_expected"] == 23 and not log["failed"]
    assert log["per_year"]["2019"] == {"rows_expected": 13, "rows_read": 13}
    df = pl.read_parquet(tmp_path / "monitoring_part_2019_2020_0.parquet")
    assert df["rows"].sum() == 23 and set(df["year"].to_list()) == {1990, 2019, 2020}


def test_combine_names_missing_and_mismatching_years(tmp_path: Path) -> None:
    import monitoring_combine as mc

    with fake_server({mf.TABLE: table()}, max_rows=5) as (url, _s):
        mf.main(["--out", str(tmp_path), "--years", "2019", "--base-url", url])
    merged, log = mc.combine(tmp_path, 2019, 2020)
    assert merged["rows"].sum() == 13
    assert log["years_missing"] == [0, 2020] and not log["complete"]
    # corrupt a part: it is reported, not fatal
    (tmp_path / "monitoring_part_2019.parquet").write_bytes(b"not parquet")
    _, log2 = mc.combine(tmp_path, 2019, 2019)
    assert log2["broken_parts"] and not log2["complete"]
