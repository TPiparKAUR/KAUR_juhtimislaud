"""Tests for the Statistics Estonia fetcher (flattening only, no network)."""

from __future__ import annotations

import statee_fetch as sf

META = {
    "title": "KE0230",
    "variables": [
        {
            "code": "Aasta",
            "text": "Aasta",
            "values": ["2020", "2021"],
            "valueTexts": ["2020", "2021"],
            "time": True,
        },
        {"code": "Liik", "text": "Liik", "values": ["A", "B", "C"], "valueTexts": ["a", "b", "c"]},
    ],
}
JS = {
    "id": ["Aasta", "Liik"],
    "dimension": {
        "Aasta": {"label": "Aasta", "category": {"index": {"2020": 0, "2021": 1}}},
        "Liik": {"label": "Liik", "category": {"index": ["A", "B", "C"]}},
    },
    "value": [1, 2, None, 4, 5, 6],
    "status": {"2": "..", "4": "x"},
}


def test_cells_summary_and_query() -> None:
    assert sf.cells(META) == 6
    s = sf.meta_summary(META)
    assert (
        s["variables"][1]["values"][0] == {"code": "A", "text": "a"} and s["variables"][0]["time"]
    )
    q = sf.query_body(META)
    assert [x["code"] for x in q["query"]] == ["Aasta", "Liik"]
    assert q["response"]["format"] == "json-stat2"


def test_flatten_gives_codes_values_and_status_in_cell_order() -> None:
    df = sf.flatten(JS)
    assert df.height == 6 and df.columns == ["Aasta", "Liik", "value", "status"]
    assert df.row(0) == ("2020", "A", 1.0, None)
    assert df.row(2) == ("2020", "C", None, "..")
    assert df.row(5) == ("2021", "C", 6.0, None)
