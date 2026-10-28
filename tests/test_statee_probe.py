"""Tests for the Statistics Estonia catalogue probe (no network)."""

from __future__ import annotations

import http.client
from typing import Any

import statee_probe as sp

TREE: dict[str, Any] = {
    "https://x/api": [
        {"id": "05Energeetika", "text": "Energeetika", "type": "l"},
        {"id": "02Rahvastik", "text": "Rahvastik", "type": "l"},
    ],
    "https://x/api/02Rahvastik": [{"id": "RV01.px", "text": "Rahvaarv", "type": "t"}],
    "https://x/api/05Energeetika": [
        {"id": "NRG01.px", "text": "Elektrienergia tarbimine", "type": "t"},
        {"id": "NRG02.px", "text": "Kütuse hind", "type": "t"},
        {"id": "Muu.px", "text": "Midagi muud", "type": "t"},
    ],
    "https://x/api/05Energeetika/NRG01.px": {
        "title": "Elektrienergia",
        "variables": [{"code": "Aasta", "text": "Aasta", "values": [1, 2, 3]}],
    },
}


def fetch(url: str) -> Any:
    return TREE[url]


def test_walk_follows_only_matching_branches_and_records_first_level() -> None:
    r = sp.walk("https://x/api", fetch)
    assert [n["id"] for n in r["first_level"]] == ["05Energeetika", "02Rahvastik"]
    ids = {m["id"] for m in r["matches"]}
    assert ids == {"NRG01.px", "NRG02.px"}  # only tables under matching branches or titles
    assert not r["errors"]


def test_describe_adds_variables_without_values() -> None:
    r = sp.walk("https://x/api", fetch)
    r["matches"] = [m for m in r["matches"] if m["id"] == "NRG01.px"]
    sp.PAUSE_S = 0.0
    sp.describe_tables(r, fetch)
    assert r["matches"][0]["variables"] == [{"code": "Aasta", "text": "Aasta", "n": 3}]


def test_ids_with_spaces_are_quoted_and_bad_urls_are_recorded() -> None:
    tree: dict[str, Any] = {
        "https://x/api": [{"id": "Eri valdkonnad. Arhiiv", "text": "Energia", "type": "l"}],
        "https://x/api/Eri%20valdkonnad.%20Arhiiv": [{"id": "T.px", "text": "Tabel", "type": "t"}],
    }
    r = sp.walk("https://x/api", lambda url: tree[url])
    assert [m["id"] for m in r["matches"]] == ["T.px"]
    assert r["matches"][0]["path"] == "Eri%20valdkonnad.%20Arhiiv/T.px"

    def bad(url: str) -> Any:
        raise http.client.InvalidURL("control characters")

    assert sp.walk("https://x/api", bad)["errors"]


def test_keywords_can_be_replaced() -> None:
    old = sp.KEYWORDS
    try:
        sp.set_keywords(["Jäätme", " ringlus "])
        assert sp.matches("Ringlusse võetud JÄÄTMED") and not sp.matches("Energia")
    finally:
        sp.KEYWORDS = old
