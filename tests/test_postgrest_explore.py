"""Tests for ``postgrest`` and ``explore`` with a fake transport."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

import explore as e
import postgrest as p


class FakeApi:
    """Serves a table of N rows ``{"id": i, "g": "a"/"b", "v": i * 0.5}`` with PostgREST paging."""

    def __init__(self, n: int, status: list[int] | None = None) -> None:
        self.n = n
        self.calls: list[tuple[str, Mapping[str, str]]] = []
        self.statuses = list(status or [])

    def __call__(self, url: str, headers: Mapping[str, str]) -> p.PgResponse:
        self.calls.append((url, headers))
        if self.statuses:
            code = self.statuses.pop(0)
            if code != 200:
                return p.PgResponse(code, b"", error="x")
        q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
        limit, offset = int(q.get("limit", 1000)), int(q.get("offset", 0))
        rows = [
            {"id": i, "g": "ab"[i % 2], "v": i * 0.5, "n": None}
            for i in range(offset, min(offset + limit, self.n))
        ]
        cr = f"0-0/{self.n}" if headers.get("Prefer") == "count=exact" else ""
        return p.PgResponse(200, json.dumps(rows).encode(), cr)


def client(api: FakeApi) -> p.Client:
    return p.Client(api, delay=0, sleep=lambda _s: None)


def test_parse_total() -> None:
    assert p.parse_total("0-0/123") == 123
    assert p.parse_total("*/0") == 0
    assert p.parse_total("0-9/*") is None
    assert p.parse_total("") is None


def test_headers_and_count() -> None:
    api = FakeApi(10)
    assert client(api).count("t") == 10
    _, headers = api.calls[0]
    assert headers["Accept-Profile"] == "apijahiala" and headers["Prefer"] == "count=exact"


def test_iter_rows_pages_and_max_rows() -> None:
    api = FakeApi(25)
    assert len(list(client(api).iter_rows("t", page_size=10))) == 25
    assert len(api.calls) == 3
    api2 = FakeApi(25)
    assert len(list(client(api2).iter_rows("t", page_size=10, max_rows=10))) == 10


def test_iter_rows_survives_server_side_row_cap() -> None:
    class Capped(FakeApi):
        def __call__(self, url: str, headers: Mapping[str, str]) -> p.PgResponse:
            resp = super().__call__(url, headers)
            if resp.status == 200 and not resp.content_range:
                rows = json.loads(resp.body)[:7]  # server returns at most 7 rows per request
                return p.PgResponse(200, json.dumps(rows).encode())
            if resp.content_range:
                rows = json.loads(resp.body)[:7]
                return p.PgResponse(200, json.dumps(rows).encode(), resp.content_range)
            return resp

    api = Capped(30)
    assert [r["id"] for r in client(api).iter_rows("t", page_size=20)] == list(range(30))


def test_retry_then_success_and_failure() -> None:
    api = FakeApi(3, status=[503, 200])
    assert len(client(api).rows("t")) == 3
    with pytest.raises(p.PostgrestError):
        client(FakeApi(3, status=[500] * 4)).rows("t")
    with pytest.raises(p.PostgrestError):  # non-retryable
        client(FakeApi(3, status=[404])).rows("t")


def test_column_stats() -> None:
    rows = [{"a": 1, "b": "x", "c": None}, {"a": 3, "b": "y", "c": None}, {"a": 2, "b": "x"}]
    s = e.column_stats(rows)
    assert (s["a"]["min"], s["a"]["max"]) == (1, 3)
    assert s["b"]["top_values"][0] == ["x", 2] or s["b"]["top_values"][0] == ("x", 2)
    assert s["c"]["non_null_share"] == 0.0


def test_sample_table_spreads_offsets() -> None:
    api = FakeApi(100_000)
    rows = e.sample_table(client(api), "t", 100_000)
    assert len(rows) == e.SAMPLE_OFFSETS * e.SAMPLE_SIZE
    assert rows[0]["id"] == 0 and max(r["id"] for r in rows) > 70_000


def test_run_writes_files_and_skips_person_tables(tmp_path: Path) -> None:
    api = FakeApi(50)
    e.run(client(api), ["t1", "x_fjisik"], tmp_path)
    assert json.loads((tmp_path / "t1.json").read_text())["total_rows"] == 50
    assert not (tmp_path / "x_fjisik.json").exists()
    assert "| t1 | 50 |" in (tmp_path / "INDEX.md").read_text()


def test_run_records_errors(tmp_path: Path) -> None:
    api = FakeApi(5, status=[404])
    e.run(client(api), ["bad"], tmp_path)
    assert "ERROR" in (tmp_path / "INDEX.md").read_text()
