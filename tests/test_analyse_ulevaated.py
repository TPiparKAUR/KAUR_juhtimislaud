"""Tests for the dashboard-view coverage analysis."""

from __future__ import annotations

from pathlib import Path

import pytest

import analyse_ulevaated as au


def test_repository_mapping_matches_the_profile_list_and_is_complete() -> None:
    rows = au.load(Path("data/ulevaate_kaetus.toml"), Path("data/tableau_public_workbooks.csv"))
    assert {r["meie"] for r in rows} <= set(au.STATUSES)
    assert {r["teema"] for r in rows} <= set(au.THEME_TITLES)
    assert len({r["workbook"] for r in rows}) == len(rows)


def test_summary_weights_gaps_by_views() -> None:
    rows = [
        {
            "teema": "vesi",
            "meie": "olemas",
            "views": 100,
            "title": "a",
            "andmed": "x",
            "markus": "",
        },
        {
            "teema": "vesi",
            "meie": "puudub",
            "views": 300,
            "title": "b",
            "andmed": "x",
            "markus": "",
        },
    ]
    s = au.summarise(rows)
    assert s["themes"]["vesi"]["share_views_uncovered"] == 0.75
    assert s["top_gaps"][0]["title"] == "b" and s["by_status"]["olemas"]["views"] == 100


def test_unknown_workbook_is_an_error(tmp_path: Path) -> None:
    cov = tmp_path / "c.toml"
    cov.write_text(
        '[[vaade]]\nworkbook = "nope"\nteema = "vesi"\nmeie = "puudub"\n', encoding="utf-8"
    )
    with pytest.raises(KeyError):
        au.load(cov, Path("data/tableau_public_workbooks.csv"))
