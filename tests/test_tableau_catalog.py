"""Tests for ``tableau_catalog`` (network is faked)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

import tableau_catalog as t


def fake_fetch(routes: dict[str, t.Response]) -> t.Fetch:
    def fetch(url: str) -> t.Response:
        for prefix, resp in routes.items():
            if url.startswith(prefix):
                return resp
        return t.Response(404, "", b"", error="not found")

    return fetch


def test_view_csv_url() -> None:
    assert t.view_csv_url("public.tableau.com", "WB A", "V") == (
        "https://public.tableau.com/views/WB%20A/V.csv"
    )
    assert t.view_csv_url("public.tableau.com", "ZB37GT9CT", "(ei tuvastatud)").endswith(
        "/shared/ZB37GT9CT.csv"
    )


def test_parse_csv_bom_and_counts() -> None:
    cols, n = t.parse_csv("﻿Aasta,Väärtus (°C)\n2020,1.5\n2021,2.0\n".encode())
    assert cols == ["Aasta", "Väärtus (°C)"]
    assert n == 2
    assert t.parse_csv(b"") == ([], 0)


def test_probe_view_csv_html_and_error() -> None:
    ok = t.Response(200, "text/csv; charset=utf-8", b"a,b\n1,2\n")
    row, cols = t.probe_view(fake_fetch({"https://h/views/W/V.csv": ok}), "h", "W", "V")
    assert (row["status"], row["rows"], row["n_columns"], cols) == (200, 1, 2, ["a", "b"])

    html = t.Response(200, "text/html", b"<html>login</html>")
    row, cols = t.probe_view(fake_fetch({"https://h/": html}), "h", "W", "V")
    assert cols == [] and row["rows"] == "" and "not CSV" in row["error"]

    row, cols = t.probe_view(fake_fetch({}), "h", "W", "V")
    assert row["status"] == 404 and cols == []


def test_find_workbooks_nested() -> None:
    data = {"contents": [{"workbookRepoUrl": "A", "x": {"workbookRepoUrl": "B"}}], "n": 1}
    assert [w["workbookRepoUrl"] for w in t.find_workbooks(data)] == ["A", "B"]
    assert t.find_workbooks("nothing") == []


def test_probe_profile_pages_and_saves_raw(tmp_path: Path) -> None:
    page = {"contents": [{"workbookRepoUrl": f"W{i}"} for i in range(2)]}
    fetch = fake_fetch(
        {t.PROFILE_ENDPOINT: t.Response(200, "application/json", json.dumps(page).encode())}
    )
    res = t.probe_profile(fetch, "p.q", tmp_path, page_size=50)
    assert res["workbooks_found"] == 2 and res["workbook_repo_urls"] == ["W0", "W1"]
    assert (tmp_path / "profile_p.q.json").exists()


def test_probe_profile_http_error(tmp_path: Path) -> None:
    res = t.probe_profile(fake_fetch({}), "p", tmp_path)
    assert res["http_status"] == 404 and res["workbooks_found"] == 0


def test_run_end_to_end(tmp_path: Path) -> None:
    inv = tmp_path / "inv.csv"
    inv.write_text(
        "host,workbook,view\npublic.tableau.com,W,V\npublic.tableau.com,W,V\n"
        "example.org,X,Y\ntableau.envir.ee,E,F\n",
        encoding="utf-8",
    )
    assert t.read_views([inv]) == [("public.tableau.com", "W", "V"), ("tableau.envir.ee", "E", "F")]
    fetch = fake_fetch(
        {"https://public.tableau.com/views/W/V.csv": t.Response(200, "text/csv", b"a,b\n1,2\n")}
    )
    out = tmp_path / "out"
    t.run([inv], out, [], delay=0, fetch=fetch)
    with (out / "tableau_catalog.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert [r["status"] for r in rows] == ["200", "404"]
    with (out / "tableau_columns.csv").open(encoding="utf-8") as fh:
        assert [r["column"] for r in csv.DictReader(fh)] == ["a", "b"]
    assert json.loads((out / "tableau_probes.json").read_text())["serverinfo"]["http_status"] == 404


@pytest.mark.parametrize(
    "resp,expected",
    [
        (t.Response(200, "text/csv", b"x"), True),
        (t.Response(200, "text/html", b"x"), False),
        (t.Response(200, "text/csv", b""), False),
        (t.Response(403, "text/csv", b"x"), False),
    ],
)
def test_looks_like_csv(resp: t.Response, expected: bool) -> None:
    assert t.looks_like_csv(resp) is expected
