"""Tests for ``hydro_fetch``."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import polars as pl
import pytest

import hydro_fetch as hf
from postgrest import PostgrestError

CATALOG = {
    "stations": [
        {
            "jaam_kood": 1,
            "series": [{"series": "Äravool avg", "rows": 129000}, {"series": "WT avg", "rows": 10}],
        },
        {"jaam_kood": 2, "series": [{"series": "Äravool avg", "rows": 50}]},
        {"jaam_kood": 3},
        {"jaam_kood": 4, "series": [{"series": "Äravool avg", "rows": None}]},
    ]
}


def hourly(day: str, values: Sequence[float | None]) -> list[dict[str, object]]:
    return [
        {"jaam_kood": 1, "timeline_ts_utc": f"{day}T{h:02d}:00:00", "vaartus": v}
        for h, v in enumerate(values)
    ]


def test_select_stations_by_rows() -> None:
    assert hf.select_stations(CATALOG, "Äravool avg", 100_000) == [1]
    assert hf.select_stations(CATALOG, "Äravool avg", 10) == [1, 2]


def test_daily_mean_min_max_and_hour_counts() -> None:
    rows = hourly("2020-05-01", [1.0] * 12 + [3.0] * 12) + hourly("2020-05-02", [5.0, None, 7.0])
    avg = hf.daily(rows, 1, "Äravool avg").to_dicts()
    assert avg[0]["value"] == pytest.approx(2.0) and avg[0]["n_hours"] == 24
    assert avg[1]["value"] == pytest.approx(6.0) and avg[1]["n_hours"] == 2  # null hour dropped
    assert hf.daily(rows, 1, "Äravool max")["value"].to_list() == [3.0, 7.0]
    assert hf.daily(rows, 1, "Äravool min")["value"].to_list() == [1.0, 5.0]


def test_daily_rejects_unknown_series_and_handles_empty() -> None:
    with pytest.raises(ValueError, match="cannot aggregate"):
        hf.daily(hourly("2020-01-01", [1.0]), 1, "Mingi näit")
    assert hf.daily([], 1, "WT avg").is_empty()


def test_run_collects_failures_and_writes_parquet(tmp_path: Path) -> None:
    def fake(station: int, series: str, delay: float) -> pl.DataFrame:
        if station == 2:
            raise PostgrestError("timeout")
        return hf.daily(hourly("2020-05-01", [float(station)] * 24), station, series)

    df = hf.run(
        [1, 2], ("Äravool avg", "WT avg"), tmp_path, workers=2, delay=0, budget_s=60, fetch=fake
    )
    assert sorted(df["series"].unique().to_list()) == ["WT avg", "Äravool avg"]
    assert df["jaam_kood"].unique().to_list() == [1]
    log = (tmp_path / "hydro_fetch_log.json").read_text(encoding="utf-8")
    assert '"ok": 2' in log and "2/" in log
    assert pl.read_parquet(tmp_path / "hydro_daily.parquet").height == 2


def test_summarise_quantiles_and_flags() -> None:
    rows = (
        hourly("2020-05-01", [1.0] * 24)
        + hourly("2020-05-02", [0.0] * 5)
        + hourly("2020-05-03", [4.0] * 24)
    )
    df = hf.daily(rows, 1, "Äravool avg")
    (s,) = hf.summarise(df)
    assert (s["days"], s["full_days"], s["n_zero"], s["n_negative"]) == (3, 2, 1, 0)
    assert (s["first"], s["last"]) == ("2020-05-01", "2020-05-03")
    assert s["q50"] == 1.0 and s["q100"] == 4.0
    assert hf.summarise(df.clear()) == []
