"""Tests for ``run_waste``."""

from __future__ import annotations

import json

import run_waste as rw
from tests.test_waste_analysis import frame


def test_build_is_json_safe_and_keeps_flows_separate() -> None:
    out = rw.build(frame(), {"rows_read": 7, "count_mismatches": [], "failed": []}, "2026-01-01")
    json.dumps(out)
    assert out["meta"]["years"] == [2021, 2022] and out["meta"]["latest_year"] == 2022
    assert out["meta"]["flow_order"][0] == "Jäätmeteke"
    assert out["meta"]["fetch"]["rows_read"] == 7
    assert out["hazardous_generation"][0]["aasta"] == 2021
    assert out["stock_continuity"][0]["ratio"] == 0.9
    assert "kaitaja" not in json.dumps(out)
