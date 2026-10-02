"""Tests for ``merge_inventory``."""

from __future__ import annotations

from pathlib import Path

import pytest

import merge_inventory as m

BASE = [
    {
        "group": "Seire",
        "page_url": "https://keskkonnaportaal.ee/r%C3%B5ngastusstatistika",
        "host": "public.tableau.com",
        "workbook": "rngastamised-avalik",
        "view": "Eestirngastamised",
        "title": "Eesti rõngastamised",
    },
    {
        "group": "Keskkonnaülevaade: muld ja maahõive",
        "page_url": "https://keskkonnaportaal.ee/et/x",
        "host": "public.tableau.com",
        "workbook": "ZB37GT9CT",
        "view": "(ei tuvastatud)",
        "title": "Maahõive",
    },
    {
        "group": "Iseseisev",
        "page_url": "https://keskkonnaportaal.ee/et/y",
        "host": "tableau.envir.ee",
        "workbook": "Vaatlused",
        "view": "V",
        "title": "Vaatlused",
    },
]


def crawl_row(page: str, kind: str, host: str, wb: str, view: str) -> dict[str, str]:
    return {
        "page_url": page,
        "kind": kind,
        "host": host,
        "workbook": wb,
        "view": view,
        "src": "x",
    }


@pytest.mark.parametrize(
    ("host", "tech", "own"),
    [
        ("public.tableau.com", "Tableau Public", "KAUR"),
        ("tableau.envir.ee", "Tableau Server", "KAUR"),
        ("app.powerbi.com", "Power BI", "RMK"),
        ("storymaps.arcgis.com", "ArcGIS", "tundmatu"),
        ("arcg.is", "ArcGIS", "tundmatu"),
        ("example.org", "muu", "tundmatu"),
    ],
)
def test_technology_and_owner(host: str, tech: str, own: str) -> None:
    assert m.technology(host) == tech
    assert m.owner(host) == own


def test_norm_page_decodes_and_strips() -> None:
    a = m.norm_page("https://KeskkonnaPortaal.ee/r%C3%B5ngastusstatistika/?x=1#f")
    assert a == "https://keskkonnaportaal.ee/rõngastusstatistika"


def test_merge_without_crawl_only_enriches() -> None:
    out = m.merge(BASE, None, None)
    assert len(out) == 3
    assert [r["leitud_crawlis"] for r in out] == ["", "", ""]
    assert [r["allikas"] for r in out] == ["inventar"] * 3
    assert out[2]["tehnoloogia"] == "Tableau Server"


def test_merge_flags_found_missing_and_adds_new() -> None:
    portal = [
        # matches baseline 0 despite percent-encoding / case differences
        crawl_row(
            "https://keskkonnaportaal.ee/rõngastusstatistika",
            "tableau-viz",
            "public.tableau.com",
            "RNGASTAMISED-avalik",
            "Eestirngastamised",
        ),
        # shared link matches the "(ei tuvastatud)" baseline row
        crawl_row(
            "https://keskkonnaportaal.ee/et/x", "iframe", "public.tableau.com", "ZB37GT9CT", ""
        ),
        # new Power BI embed
        crawl_row("https://keskkonnaportaal.ee/et/z", "iframe", "app.powerbi.com", "", ""),
        # not an embed kind -> ignored
        crawl_row("https://keskkonnaportaal.ee/et/z", "link", "public.tableau.com", "A", "B"),
    ]
    out = m.merge(BASE, portal, None)
    assert [r["leitud_crawlis"] for r in out[:3]] == ["jah", "jah", "ei"]
    new = out[3:]
    assert len(new) == 1
    assert (new[0]["allikas"], new[0]["tehnoloogia"], new[0]["omanik"]) == (
        "crawl",
        "Power BI",
        "RMK",
    )
    assert new[0]["view"] == m.UNIDENTIFIED_VIEW


def test_merge_never_drops_baseline_rows_and_dedups_crawl() -> None:
    portal = [
        crawl_row("https://p/a", "img", "public.tableau.com", "W", "V"),
        crawl_row("https://p/a", "tableau-viz", "public.tableau.com", "W", "V"),
    ]
    out = m.merge(BASE, portal, None)
    assert len(out) == len(BASE) + 1


def test_server_rows_and_merge() -> None:
    server = [
        {
            "type": "view",
            "project": "Avalik",
            "workbook": "Vaatlused WB",
            "name": "V",
            "content_url": "Vaatlused/sheets/V",
        },
        {
            "type": "view",
            "project": "Sise",
            "workbook": "Uus",
            "name": "Leht",
            "content_url": "Uus/sheets/Leht",
        },
        {"type": "datasource", "project": "Sise", "name": "DS", "content_url": "DS"},
    ]
    out = m.merge(BASE, None, server)
    assert len(out) == 4  # first server view already in baseline, datasource ignored
    added = out[-1]
    assert (added["host"], added["workbook"], added["view"], added["allikas"]) == (
        "tableau.envir.ee",
        "Uus",
        "Leht",
        "server",
    )
    assert added["group"] == "Tableau Server: Sise"


def test_read_csv_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "a.csv"
    p.write_text("a,b\n1,ä\n", encoding="utf-8")
    assert m.read_csv(p) == [{"a": "1", "b": "ä"}]
