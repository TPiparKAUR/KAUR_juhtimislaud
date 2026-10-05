"""Tests for ``waste_fetch``."""

from __future__ import annotations

import json
import urllib.parse
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import polars as pl

import waste_fetch as wf
from postgrest import Client, PgResponse, PostgrestError


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


def test_pages_cover_every_row_once_newest_year_first() -> None:
    pages = wf.make_pages({2021: 45_000, 2022: 20_000}, page=20_000)
    assert [(p.year, p.offset, p.expected) for p in pages] == [
        (2022, 0, 20_000),
        (2021, 0, 20_000),
        (2021, 20_000, 20_000),
        (2021, 40_000, 5_000),
    ]


def test_merge_sums_keys_that_span_several_pages() -> None:
    a = wf.aggregate([row(maht=5.0), row(maht=-2.0)])
    b = wf.aggregate([row(maht=4.0)])
    m = wf.merge([a, b, pl.DataFrame()])
    assert m.height == 1 and m["maht"][0] == 7.0 and m["rows"][0] == 3 and m["neg_rows"][0] == 1


def test_select_covers_every_key_and_the_amount() -> None:
    assert set(wf.SELECT) == {*wf.KEYS, "maht"}


def fake_client(total: int, cap: int) -> tuple[Client, list[dict[str, str]]]:
    """A server holding ``total`` identical rows that returns at most ``cap`` rows per request."""
    full: dict[str, object] = dict.fromkeys(wf.SELECT, "x")
    full.update(aasta=2022, materjali_kood=1, maht=2.5)
    seen: list[dict[str, str]] = []

    def transport(url: str, headers: Mapping[str, str]) -> PgResponse:
        q = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(url).query).items()}
        seen.append(q)
        cols = q["select"].split(",")  # a real server returns only the selected columns
        n = max(0, min(int(q["limit"]), cap, total - int(q["offset"])))
        return PgResponse(200, json.dumps([{c: full[c] for c in cols if c in full}] * n).encode())

    return Client(transport, delay=0.0, sleep=lambda _s: None), seen


def test_fetch_page_requests_only_known_columns_and_orders_totally() -> None:
    """Regression: the server returns only the selected columns, so the select must be complete."""
    client, seen = fake_client(total=3, cap=100)
    df, got = wf.fetch_page(wf.Page(2022, 0, 3), 0.0, client)
    assert got == 3 and df["maht"].to_list() == [7.5] and df["rows"].to_list() == [3]
    assert seen[0]["order"] == seen[0]["select"] and seen[0]["aasta"] == "eq.2022"


def test_fetch_page_continues_when_server_returns_fewer_rows() -> None:
    client, seen = fake_client(total=5, cap=2)
    _, got = wf.fetch_page(wf.Page(2022, 0, 5), 0.0, client)
    assert got == 5 and [q["offset"] for q in seen] == ["0", "2", "4"]


def test_run_reports_failures_and_count_mismatches(tmp_path: Path) -> None:
    def fake(p: wf.Page, delay: float) -> tuple[pl.DataFrame, int]:
        if p.year == 2020:
            raise PostgrestError("timeout")
        if p.year == 2021:
            return wf.aggregate([row(aasta=2021)]), 1  # short read
        return wf.aggregate([row(maht=4.0)]), p.expected

    df = wf.run(
        {2022: 2, 2021: 2, 2020: 2}, tmp_path, workers=2, delay=0.0, budget_s=60, fetch=fake
    )
    log = json.loads((tmp_path / "waste_part_all.json").read_text(encoding="utf-8"))
    assert df.height >= 1 and (tmp_path / "waste_part_all.parquet").exists()
    assert "timeout" in log["failed"][0]
    assert {"year": 2021, "expected": 2, "got": 1} in log["count_mismatches"]
    assert log["rows_read"] == 3 and log["rows_expected"] == 6


def test_pages_with_whole_number_amounts_and_null_columns_still_merge() -> None:
    """Regression: a page of integer amounts / an all-null column broke the final concat."""
    ints = wf.aggregate([row(maht=5, partner_riik_nimi=None, materjali_kood=1)])
    floats = wf.aggregate([row(maht=2.5, partner_riik_nimi="Rootsi")])
    assert ints.schema == floats.schema
    m = wf.merge([ints, floats])
    assert sorted(m["maht"].to_list()) == [2.5, 5.0]


def test_run_still_writes_log_when_merge_fails(tmp_path: Path) -> None:
    def bad(p: wf.Page, delay: float) -> tuple[pl.DataFrame, int]:
        return pl.DataFrame({"aasta": [1]}), p.expected  # wrong schema -> merge error

    wf.run({2022: 1, 2021: 1}, tmp_path, workers=1, delay=0.0, budget_s=60, fetch=bad)
    log = json.loads((tmp_path / "waste_part_all.json").read_text(encoding="utf-8"))
    assert any(f.startswith("merge:") for f in log["failed"]) and log["rows_read"] == 2
