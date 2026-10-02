"""Tests for ``tableau_catalog`` (network is faked)."""

from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path

import pytest

import tableau_catalog as t


def fake_fetch(routes: dict[str, t.Response]) -> t.Fetch:
    def fetch(url: str) -> t.Response:
        if url in routes:
            return routes[url]
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


TWB = """<?xml version='1.0'?>
<workbook xmlns:user='http://www.tableausoftware.com/xml/user'>
  <datasources>
    <datasource name='Parameters'><column name='[P]'/></datasource>
    <datasource name='federated.1' caption='Heide'>
      <connection class='federated'><named-connections><named-connection>
        <connection class='hyper' dbname='x.hyper'/></named-connection></named-connections>
      </connection>
      <column name='[Aasta]' datatype='integer' role='dimension'/>
      <column name='[Kokku]' caption='Kokku (kt)' datatype='real' role='measure'>
        <calculation class='tableau' formula='SUM([x])'/></column>
    </datasource>
  </datasources>
  <worksheets><worksheet name='Leht 1'/><worksheet name='Leht 2'/></worksheets>
  <dashboards><dashboard name='Töölaud'/></dashboards>
</workbook>""".encode()


def test_inspect_twb() -> None:
    info = t.inspect_twb(TWB)
    assert info["sheets"] == [
        ("Leht 1", "worksheet"),
        ("Leht 2", "worksheet"),
        ("Töölaud", "dashboard"),
    ]
    (ds,) = info["datasources"]  # "Parameters" is skipped
    assert ds["caption"] == "Heide" and ds["connection"] == "federated|hyper"
    assert [(f["field"], f["calculated"]) for f in ds["fields"]] == [
        ("[Aasta]", False),
        ("[Kokku]", True),
    ]


def make_twbx(xml: bytes = TWB) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("Data/Extracts/x.hyper", b"\x00" * 10)
        zf.writestr("wb.twb", xml)
    return buf.getvalue()


def test_twb_from_package_zip_and_bare() -> None:
    assert t.twb_from_package(make_twbx()) == TWB
    assert t.twb_from_package(TWB) == TWB
    with pytest.raises(ValueError, match=r"no \.twb"):
        t.twb_from_package(b"PK\x05\x06" + b"\0" * 18)


def test_probe_workbook_twbx_then_twb_fallback_and_errors() -> None:
    base = "https://public.tableau.com/workbooks/W"
    ok = fake_fetch({base + ".twbx": t.Response(200, "application/octet-stream", make_twbx())})
    row, info = t.probe_workbook(ok, "W")
    assert row["download"] == "twbx" and info is not None and len(info["sheets"]) == 3

    fallback = fake_fetch(
        {base + ".twbx": t.Response(404, "", b""), base + ".twb": t.Response(200, "text/xml", TWB)}
    )
    row, info = t.probe_workbook(fallback, "W")
    assert row["download"] == "twb" and info is not None

    row, info = t.probe_workbook(fake_fetch({}), "W")
    assert info is None and row["http_status"] == 404

    bad = fake_fetch({base + ".twbx": t.Response(200, "x", b"<not xml")})
    row, info = t.probe_workbook(bad, "W")
    assert info is None and "unparsable" in row["error"]

    big = fake_fetch({base + ".twbx": t.Response(200, "x", b"PK", truncated=True)})
    assert "larger than" in t.probe_workbook(big, "W")[0]["error"]


def test_run_catalogues_profile_workbooks(tmp_path: Path) -> None:
    inv = tmp_path / "inv.csv"
    inv.write_text("host,workbook,view\npublic.tableau.com,wb,V\n", encoding="utf-8")
    page = {
        "contents": [
            {"workbookRepoUrl": "WB", "title": "T", "viewCount": 3},
            {"workbookRepoUrl": "Other"},
        ]
    }
    fetch = fake_fetch(
        {t.PROFILE_ENDPOINT: t.Response(200, "application/json", json.dumps(page).encode())}
    )
    big = fake_fetch(
        {"https://public.tableau.com/workbooks/WB.twbx": t.Response(200, "x", make_twbx())}
    )
    out = tmp_path / "out"
    t.run([inv], out, ["p"], delay=0, fetch=fetch, fetch_big=big)
    with (out / "tableau_public_workbooks.csv").open(encoding="utf-8") as fh:
        rows = {r["workbook"]: r for r in csv.DictReader(fh)}
    assert rows["WB"]["in_inventory"] == "jah" and rows["WB"]["n_worksheets"] == "2"
    assert rows["Other"]["in_inventory"] == "ei" and rows["Other"]["http_status"] == "404"
    with (out / "tableau_public_fields.csv").open(encoding="utf-8") as fh:
        assert len(list(csv.DictReader(fh))) == 2
    probes = json.loads((out / "tableau_probes.json").read_text(encoding="utf-8"))
    assert "workbooks" not in probes["profiles"][0]
