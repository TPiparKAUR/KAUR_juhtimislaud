"""Tests for ``hydro_catalog`` against an in-memory fake PostgREST."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import hydro_catalog as h
import postgrest as p

ROWS: list[dict[str, object]] = [
    {
        "jaam_kood": 1,
        "jaam_nimi": "A",
        "aegrida_nimi": "WT avg",
        "timeline_ts_utc": "2020-01-02T00:00:00",
    },
    {
        "jaam_kood": 1,
        "jaam_nimi": "A",
        "aegrida_nimi": "WT avg",
        "timeline_ts_utc": "2020-01-01T00:00:00",
    },
    {
        "jaam_kood": 1,
        "jaam_nimi": "A",
        "aegrida_nimi": "Äravool avg",
        "timeline_ts_utc": "2021-05-05T00:00:00",
    },
    {
        "jaam_kood": 2,
        "jaam_nimi": "B",
        "aegrida_nimi": 'WL "x"',
        "timeline_ts_utc": "2019-03-03T00:00:00",
    },
]


def fake(url: str, headers: Mapping[str, str]) -> p.PgResponse:
    q = {k: unquote(v[0]) for k, v in parse_qs(urlparse(url).query).items()}
    rows = list(ROWS)
    for col, cond in q.items():
        if col in {"select", "limit", "offset", "order"}:
            continue
        op, _, val = cond.partition(".")
        if op == "eq":
            rows = [r for r in rows if str(r[col]) == val]
        elif op == "not":
            vals = [
                (v[1:-1] if v.startswith('"') else v).replace('\\"', '"')
                for v in re.findall(r'"(?:[^"\\]|\\.)*"|[^,()]+', val[4:-1])
            ]
            rows = [r for r in rows if str(r[col]) not in vals]
    if "order" in q:
        key, _, direction = q["order"].partition(".")
        rows.sort(key=lambda r: str(r[key]), reverse=direction == "desc")
    total = len(rows)
    rows = rows[: int(q.get("limit", 1000))]
    rows = [
        {k: r.get(k) for k in q["select"].split(",")} if q.get("select", "*") != "*" else r
        for r in rows
    ]
    cr = f"0-0/{total}" if headers.get("Prefer") == "count=exact" else ""
    return p.PgResponse(200, json.dumps(rows).encode(), cr)


def client() -> p.Client:
    return p.Client(fake, delay=0, sleep=lambda _s: None)


def test_quote_list() -> None:
    assert h.quote_list([1, "a", 'b"c']) == '(1,"a","b\\"c")'


def test_discover_distinct_values() -> None:
    rows = h.discover(client(), "jaam_kood", {}, "jaam_kood,jaam_nimi")
    assert [r["jaam_kood"] for r in rows] == [1, 2]
    series = h.discover(client(), "aegrida_nimi", {"jaam_kood": "eq.1"}, "jaam_kood,aegrida_nimi")
    assert sorted(r["aegrida_nimi"] for r in series) == ["WT avg", "Äravool avg"]


def test_series_coverage_counts_and_edges() -> None:
    cov = h.series_coverage(client(), 1, "WT avg")
    assert (cov["rows"], cov["first_utc"], cov["last_utc"]) == (
        2,
        "2020-01-01T00:00:00",
        "2020-01-02T00:00:00",
    )


def test_run_writes_catalog(tmp_path: Path) -> None:
    res = h.run(client(), tmp_path)
    assert [s["jaam_kood"] for s in res["stations"]] == [1, 2]
    assert res["complete"] is True
    assert {s["series"] for s in res["stations"][0]["series"]} == {"WT avg", "Äravool avg"}
    assert (
        json.loads((tmp_path / "hydro_catalog.json").read_text(encoding="utf-8"))["table"]
        == h.TABLE
    )


def test_series_coverage_records_timings_and_survives_errors() -> None:
    def flaky(url: str, headers: Mapping[str, str]) -> p.PgResponse:
        if "order=" in url:
            return p.PgResponse(500, b"", error="statement timeout")
        return fake(url, headers)

    c = p.Client(flaky, delay=0, sleep=lambda _s: None)
    cov = h.series_coverage(c, 1, "WT avg")
    assert cov["rows"] == 2 and cov["first_utc"] is None
    assert set(cov["errors"]) == {"first_utc", "last_utc"}
    assert set(cov["seconds"]) == {"rows", "first_utc", "last_utc"}


def test_run_stops_at_budget_and_keeps_station_list(tmp_path: Path) -> None:
    res = h.run(client(), tmp_path, budget_s=-1)
    assert res["complete"] is False and len(res["stations"]) == 2
    saved = json.loads((tmp_path / "hydro_catalog.json").read_text(encoding="utf-8"))
    assert saved["complete"] is False
