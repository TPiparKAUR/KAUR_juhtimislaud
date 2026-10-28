"""Tests for the Eurostat fetch helpers (no network)."""

from __future__ import annotations

import pytest

import eurostat_fetch as ef


def test_url_and_filters() -> None:
    filters = ef.parse_filters(["geo=EE", "geo=EU27_2020"])
    url = ef.url_for("cei_srm030", filters)
    assert url.startswith(ef.BASE + "/cei_srm030?") and "geo=EE" in url and "geo=EU27_2020" in url
    with pytest.raises(ValueError):
        ef.parse_filters(["broken"])


def test_dimension_labels() -> None:
    js = {
        "id": ["geo"],
        "dimension": {
            "geo": {"label": "Geo", "category": {"index": ["EE"], "label": {"EE": "Estonia"}}}
        },
    }
    assert ef.dimension_labels(js) == {"geo": {"label": "Geo", "values": {"EE": "Estonia"}}}
