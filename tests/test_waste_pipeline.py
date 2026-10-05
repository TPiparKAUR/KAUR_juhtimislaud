"""End-to-end tests of the waste fetch -> combine pipeline against a fake PostgREST server.

These reproduce, locally and in seconds, the failures seen in GitHub Actions: a column missing
from the select, mixed integer/float JSON amounts breaking the final concatenation, the server
page cap, transient 5xx responses, a missing year and a corrupt part.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import polars as pl
import pytest

import waste_combine as wc
import waste_fetch as wf
from tests.fake_postgrest import fake_server
from waste_explore import TABLE


def make_rows() -> list[dict[str, Any]]:
    """Rows for 2021 and 2022 with whole-number and fractional amounts and null partners."""
    rows: list[dict[str, Any]] = []
    for year in (2021, 2022):
        for i in range(13):
            r: dict[str, Any] = dict.fromkeys(wf.SELECT, f"v{i % 3}")
            r.update(
                aasta=year,
                maht_liik="Import" if i % 2 else "Jäätmeteke",
                pohigrupp="20",
                materjali_kood=i % 4,
                maht=(i * 2) if i % 3 == 0 else i + 0.5,  # int on some rows, float on others
                partner_riik_nimi=None if i % 4 else "Rootsi",
            )
            rows.append(r)
    return rows


def truth(rows: list[dict[str, Any]], year: int) -> float:
    return sum(float(r["maht"]) for r in rows if r["aasta"] == year)


@pytest.fixture(autouse=True)
def no_real_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time, "sleep", lambda _s: None)


def test_cli_reads_every_row_through_a_small_page_cap(tmp_path: Path) -> None:
    rows = make_rows()
    with fake_server({TABLE: rows}, max_rows=4) as (url, state):
        # page size above the server cap: continuation logic must fill every page
        wf.main(
            [
                "--out",
                str(tmp_path),
                "--years",
                "2021",
                "2022",
                "--page-size",
                "10",
                "--workers",
                "3",
                "--base-url",
                url,
            ]
        )
        assert state.requests > 6
    log = json.loads((tmp_path / "waste_part_2021_2022.json").read_text(encoding="utf-8"))
    df = pl.read_parquet(tmp_path / "waste_part_2021_2022.parquet")
    assert log["rows_read"] == log["rows_expected"] == len(rows)
    assert log["failed"] == [] and log["count_mismatches"] == []
    for y in (2021, 2022):
        assert df.filter(pl.col("aasta") == y)["maht"].sum() == pytest.approx(truth(rows, y))
    assert df["rows"].sum() == len(rows)


def test_transient_server_errors_are_retried(tmp_path: Path) -> None:
    rows = make_rows()
    with fake_server({TABLE: rows}, max_rows=5, fail_every=3) as (url, _):
        wf.main(
            [
                "--out",
                str(tmp_path),
                "--years",
                "2022",
                "--page-size",
                "5",
                "--workers",
                "2",
                "--base-url",
                url,
            ]
        )
    log = json.loads((tmp_path / "waste_part_2022.json").read_text(encoding="utf-8"))
    assert log["failed"] == [] and log["rows_read"] == log["rows_expected"] == 13


def test_a_column_the_server_lacks_is_reported_not_swallowed(tmp_path: Path) -> None:
    rows = [{k: v for k, v in r.items() if k != "pohigrupp_nimi"} for r in make_rows()]
    with fake_server({TABLE: rows}, max_rows=5) as (url, _):
        wf.main(["--out", str(tmp_path), "--years", "2022", "--page-size", "5", "--base-url", url])
    log = json.loads((tmp_path / "waste_part_2022.json").read_text(encoding="utf-8"))
    assert log["rows_read"] == 0 and log["failed"]  # visible in the log, not a silent success


def run_parts(tmp_path: Path, url: str, years: list[int]) -> None:
    for y in years:
        wf.main(["--out", str(tmp_path), "--years", str(y), "--page-size", "5", "--base-url", url])


def test_combine_merges_parts_and_matches_ground_truth(tmp_path: Path) -> None:
    rows = make_rows()
    with fake_server({TABLE: rows}, max_rows=5) as (url, _):
        run_parts(tmp_path, url, [2021, 2022])
    merged, log = wc.combine(tmp_path, 2021, 2022)
    assert log["complete"] and log["years_missing"] == [] and log["rows_read"] == len(rows)
    assert merged["maht"].sum() == pytest.approx(truth(rows, 2021) + truth(rows, 2022))


def test_combine_names_the_missing_year_instead_of_failing(tmp_path: Path) -> None:
    rows = make_rows()
    with fake_server({TABLE: rows}, max_rows=5) as (url, _):
        run_parts(tmp_path, url, [2022])
    merged, log = wc.combine(tmp_path, 2021, 2022)
    assert not log["complete"] and log["years_missing"] == [2021]
    assert merged["maht"].sum() == pytest.approx(truth(rows, 2022))


def test_combine_survives_a_corrupt_part(tmp_path: Path) -> None:
    rows = make_rows()
    with fake_server({TABLE: rows}, max_rows=5) as (url, _):
        run_parts(tmp_path, url, [2021, 2022])
    (tmp_path / "waste_part_2021.parquet").write_bytes(b"not a parquet file")
    merged, log = wc.combine(tmp_path, 2021, 2022)
    assert log["broken_parts"] and 2021 in log["years_missing"] and not log["complete"]
    assert not merged.is_empty()


def test_combine_cli_writes_outputs(tmp_path: Path) -> None:
    rows = make_rows()
    parts, out = tmp_path / "parts", tmp_path / "out"
    with fake_server({TABLE: rows}, max_rows=5) as (url, _):
        run_parts(parts, url, [2021, 2022])
    wc.main(["--parts", str(parts), "--out", str(out), "--first", "2021", "--last", "2022"])
    assert json.loads((out / "waste_fetch_log.json").read_text(encoding="utf-8"))["complete"]
    assert (out / "waste_agg.parquet").exists()
