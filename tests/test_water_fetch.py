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


def test_grain_runs_on_fetched_tables(tmp_path: Path) -> None:
    import water_grain as wg

    pl.DataFrame(
        {
            "id": [1, 2],
            "kood": ["1_a", "2_b"],
            "veekogu_tyyp": ["11", "12"],
            "veekogu_tyyp_selg": ["a", "b"],
            "keht_staatus": ["Kehtiv"] * 2,
            "vee_tyyp": ["V1", "V2"],
            "vee_tyyp_selg": ["x", "y"],
            "alamkategooria": ["LV", "LV"],
        }
    ).write_parquet(tmp_path / "f_veekogumid.parquet")
    pl.DataFrame(
        {
            "vkm_id": [1, 1, 2],
            "aasta": ["2015", "2021", "2021"],
            "tyyp": ["S"] * 3,
            "keht_staatus": ["Kehtiv"] * 3,
            "muut_staatus": [None] * 3,
            "seis": ["2", "3", "2"],
            "kood": ["a", "a", "b"],
            "staatus": [None] * 3,
        }
    ).write_parquet(tmp_path / "f_veekogumi_seisundid.parquet")
    pl.DataFrame(
        {
            "koormus_id": [1],
            "koormus_tyyp": ["t"],
            "koormus_tyyp_selg": ["T"],
            "koormus_veekogum_id": [1],
            "koormus_staatus": ["a"],
        }
    ).write_parquet(tmp_path / "f_veekogumid_koormus.parquet")
    pl.DataFrame(
        {"aasta": [2014], "seis": ["1"], "seis_kem": ["1"], "seis_kog": ["1"]}
    ).write_parquet(tmp_path / "f_pohjaveekogumi_seisud.parquet")
    g = wg.grain(tmp_path)
    assert g["status_join_ok"] == {"status_bodies": 2, "found_in_register": 2}
    assert g["status_duplicates"]["groups_with_multiple_rows"] == 0
