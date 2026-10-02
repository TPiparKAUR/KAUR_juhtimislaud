"""Tests for ``tableau_vizql`` (network is faked)."""

from __future__ import annotations

import csv
import html
import json
from collections.abc import Mapping
from pathlib import Path

import tableau_vizql as v
from tableau_catalog import Response

CFG = {"sessionid": "S1", "sheetId": "Dash 1", "vizql_root": "/vizql"}
PAGE = (
    '<html><textarea id="tsConfigContainer" style="display:none">'
    + html.escape(json.dumps(CFG))
    + "</textarea></html>"
)
DOC = {
    "worldUpdate": {
        "a": [
            {"sheetName": "Leht", "x": {"fieldCaption": "Aasta"}},
            {"fieldCaption": "Kogus (t)", "datasourceCaption": "Heide"},
        ],
        "n": 5,
    }
}


def bootstrap_text(doc: Mapping[str, object]) -> str:
    body = json.dumps(doc)
    return f"{len(body)};{body}2;{{}}"


def test_parse_ts_config() -> None:
    assert v.parse_ts_config(PAGE) == CFG
    assert v.parse_ts_config("<html></html>") is None
    assert v.parse_ts_config('<textarea id="tsConfigContainer">{bad</textarea>') is None


def test_parse_bootstrap() -> None:
    assert v.parse_bootstrap(bootstrap_text(DOC)) == DOC
    assert v.parse_bootstrap("not;json") is None
    assert v.parse_bootstrap("5;{") is None


def test_collect_names() -> None:
    names = v.collect_names(DOC)
    assert names == {"field": {"Aasta", "Kogus (t)"}, "sheet": {"Leht"}, "datasource": {"Heide"}}


def make_http(page: Response, boot: Response) -> v.Http:
    def http(url: str, data: bytes | None) -> Response:
        return boot if data is not None else page

    return http


def test_probe_view_ok_and_failures() -> None:
    ok = make_http(
        Response(200, "text/html", PAGE.encode()),
        Response(200, "text/plain", bootstrap_text(DOC).encode()),
    )
    res = v.probe_view(ok, "h", "WB", "V")
    assert (res["n_fields"], res["n_sheets"], res["n_datasources"]) == (2, 1, 1)

    gone = v.probe_view(
        make_http(Response(404, "", b"", error="nf"), Response(0, "", b"")), "h", "WB", "V"
    )
    assert gone["config_status"] == 404 and "nf" in gone["error"]

    nocfg = v.probe_view(
        make_http(Response(200, "", b"<html/>"), Response(0, "", b"")), "h", "WB", "V"
    )
    assert "tsConfigContainer" in nocfg["error"]

    badboot = v.probe_view(
        make_http(Response(200, "", PAGE.encode()), Response(500, "", b"", error="boom")),
        "h",
        "WB",
        "V",
    )
    assert badboot["bootstrap_status"] == 500 and badboot["error"] == "boom"

    shared = v.probe_view(ok, "h", "ZB37GT9CT", "(ei tuvastatud)")
    assert "unknown" in shared["error"]


def test_default_views_from_profiles(tmp_path: Path) -> None:
    prof = [
        {
            "contents": [
                {"workbookRepoUrl": "W1", "defaultViewRepoUrl": "W1/sheets/Riigitasand"},
                {"workbookRepoUrl": "W2"},
            ]
        }
    ]
    (tmp_path / "profile_p.json").write_text(json.dumps(prof), encoding="utf-8")
    assert v.default_views_from_profiles(tmp_path) == [("public.tableau.com", "W1", "Riigitasand")]


def test_run_writes_outputs(tmp_path: Path) -> None:
    inv = tmp_path / "inv.csv"
    inv.write_text("host,workbook,view\npublic.tableau.com,WB,V\n", encoding="utf-8")
    http = make_http(
        Response(200, "", PAGE.encode()), Response(200, "", bootstrap_text(DOC).encode())
    )
    out = tmp_path / "out"
    v.run([inv], out, delay=0, limit=None, http=http)
    with (out / "tableau_vizql_names.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert {(r["kind"], r["name"]) for r in rows} == {
        ("field", "Aasta"),
        ("field", "Kogus (t)"),
        ("sheet", "Leht"),
        ("datasource", "Heide"),
    }
    with (out / "tableau_vizql_status.csv").open(encoding="utf-8") as fh:
        assert next(csv.DictReader(fh))["n_fields"] == "2"
