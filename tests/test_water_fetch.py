"""Tests for ``water_fetch`` against the fake PostgREST server."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import polars as pl
import pytest

import water_fetch as wf
from tests.fake_postgrest import fake_server


@pytest.fixture(autouse=True)
def no_real_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time, "sleep", lambda _s: None)


def test_describe_lists_values_years_and_nulls() -> None:
    df = pl.DataFrame(
        {
            "aasta": [2015, 2015, 2021, 2021],
            "seis": ["Hea", "Kesine", "Hea", None],
            "fyke_nyld": [1.0, 2.5, None, 3.0],
        }
    )
    d = wf.describe(df)
    assert d["years"]["aasta"] == [2015, 2021]
    assert d["columns"]["seis"]["null_share"] == 0.25
    assert {v["value"] for v in d["columns"]["seis"]["values"]} == {"Hea", "Kesine", None}
    assert d["columns"]["fyke_nyld"]["max"] == 3.0


def test_end_to_end_reads_every_table_completely(tmp_path: Path) -> None:
    tables: dict[str, list[dict[str, Any]]] = {
        "f_veekogumid": [{"id": i, "nimi": f"V{i}", "tyyp": "J"} for i in range(1, 8)],
        "f_veekogumi_seisundid": [
            {"id": i, "vkm_id": i % 7 + 1, "aasta": "2021", "seis": "Hea"} for i in range(1, 13)
        ],
        "f_veekogumid_koormus": [{"koormus_id": 1, "koormus_veekogum_id": 1}],
        "f_pohjaveekogumi_seisud": [{"id": 1, "aasta": 2021, "seis": "Hea"}],
    }
    with fake_server(tables, max_rows=5) as (url, state):
        wf.main(["--out", str(tmp_path), "--base-url", url])
        assert state.requests > 4
    assert pl.read_parquet(tmp_path / "f_veekogumid.parquet").height == 7
    assert pl.read_parquet(tmp_path / "f_veekogumi_seisundid.parquet").height == 12
    diag = json.loads((tmp_path / "water_diagnostics.json").read_text(encoding="utf-8"))
    assert diag["f_veekogumid"]["rows"] == 7
