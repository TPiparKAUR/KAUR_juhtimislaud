"""Test for ``monitoring_probe`` against the fake PostgREST server."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

import monitoring_probe as mp
from tests.fake_postgrest import fake_server


@pytest.fixture(autouse=True)
def no_real_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time, "sleep", lambda _s: None)


def test_probe_counts_and_samples_without_failing_on_unsupported_filters(tmp_path: Path) -> None:
    rows = [
        {
            "seiretoo_kood": "S1",
            "liik_est": "kass" if i % 2 else None,
            "seireaeg_algus": "2020-05-01",
        }
        for i in range(12)
    ]
    ring = [{"vaatlus_id": i, "vaatlus_kp": "2010-01-01"} for i in range(4)]
    with fake_server({mp.TABLE: rows, mp.RINGING: ring}, max_rows=5) as (url, _state):
        mp.main(["--out", str(tmp_path), "--base-url", url])
    res = json.loads((tmp_path / "monitoring_probe.json").read_text(encoding="utf-8"))
    assert res["total"] == 12 and res["ringing_total"] == 4
    assert set(res["filters"]) == set(mp.FILTERS)
