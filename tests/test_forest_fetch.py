"""Tests for ``forest_fetch`` (pure diagnostics and an end-to-end read against a fake server)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import polars as pl
import pytest

import forest_fetch as ff
from tests.fake_postgrest import fake_server


def table() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for year in (2019, 2020, 2021):
        for tnr, name, ind in ((6, "Boniteediklassid", "Pindala"), (9, "Takseernäitajad", "Täius")):
            for owner, ocode in (("Riigimetsamaa", "1"), ("Teised maaomanikud", "2")):
                for calc in ("Summa", "Keskmine"):
                    rows.append(
                        {
                            "tabeli_number": tnr,
                            "aruande_nimi": name,
                            "tunnus": ind,
                            "omand_kood": ocode,
                            "omand": owner,
                            "filter1": None if tnr == 9 else "Lubikaloo",
                            "arvutus": calc,
                            "aasta": year,
                            "arvvaartus": 100 + year % 7 + (1 if calc == "Summa" else 0.5),
                            "suhteline_viga": None if (year == 2019 and tnr == 9) else 0.1,
                        }
                    )
    return rows


@pytest.fixture(autouse=True)
def no_real_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time, "sleep", lambda _s: None)


def test_diagnostics_describes_tables_classifiers_and_quality() -> None:
    d = ff.diagnostics(pl.DataFrame(table()))
    assert d["years"] == [2019, 2020, 2021] and d["rows"] == 24
    assert {t["tabeli_number"] for t in d["tables"]} == {6, 9}
    owners = {v["omand"] for v in d["classifiers"]["omand"]["values"]}
    assert owners == {"Riigimetsamaa", "Teised maaomanikud"}
    assert d["relative_error"]["null_rows"] == 4
    assert d["duplicates"]["groups_with_multiple_rows"] == 0
    assert d["null_share"]["filter1"] == pytest.approx(0.5)


def test_end_to_end_read_through_page_cap_and_instability(tmp_path: Path) -> None:
    rows = table()
    with fake_server({ff.TABLE: rows}, max_rows=5) as (url, state):
        ff.main(["--out", str(tmp_path), "--workers", "3", "--base-url", url])
        assert state.requests > 5
    df = pl.read_parquet(tmp_path / "forest_raw.parquet")
    assert df.height == len(rows)
    assert df["arvvaartus"].sum() == pytest.approx(sum(r["arvvaartus"] for r in rows))
    diag = json.loads((tmp_path / "forest_diagnostics.json").read_text(encoding="utf-8"))
    assert diag["rows"] == len(rows) and diag["years"] == [2019, 2020, 2021]


def test_a_short_read_is_an_error_not_a_silent_gap() -> None:
    from postgrest import Client

    class Lossy(Client):
        def rows(self, table: str, **kw: Any) -> list[dict[str, Any]]:
            got = super().rows(table, **kw)
            return got[:-1] if kw.get("offset", 0) >= 5 and len(got) > 1 else got

    rows = table()
    with fake_server({ff.TABLE: rows}, max_rows=5) as (url, _):
        client = Lossy(delay=0.0, base_url=url)
        # the loop refills until the page is full, so a transient short page is repaired
        df = ff.fetch_all(client, workers=2, page=5)
    assert df.height == len(rows)


def test_table_shapes_list_filled_classifiers_and_latest_examples() -> None:
    shapes = ff.table_shapes(pl.DataFrame(table()))
    by = {(s["tabeli_number"], s["arvutus"]): s for s in shapes}
    boniteet = by[(6, "Summa")]
    assert "omand+" in boniteet["filled"] and "filter1" in boniteet["filled"]
    assert boniteet["values"]["omand"] == ["Riigimetsamaa", "Teised maaomanikud"]
    assert boniteet["examples_latest_year"][0]["aasta"] == 2021
    assert "filter1" not in by[(9, "Summa")]["filled"]  # table 9 has no filter
