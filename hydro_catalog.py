#!/usr/bin/env python3
"""Enumerate the hydrological time series in ``f_hydroseire`` (74 M rows) without downloading them.

PostgREST has no ``DISTINCT``, so stations and series are discovered iteratively: ask for one row
whose station code is *not in* the list found so far, until none is left; then do the same for the
series names of each station.  For every (station, series) the exact row count and the first and
last timestamp are recorded.  Result: ``hydro_catalog.json`` with station metadata and coverage.

Usage
-----
    uv run python hydro_catalog.py --out out/hydro
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path
from typing import Any

from postgrest import Client, PostgrestError

LOG = logging.getLogger("hydro_catalog")
TABLE = "f_hydroseire"
MAX_STATIONS = 2000
STATION_FIELDS = (
    "jaam_kood,jaam_nimi,valgala_nimi,valgala_suurus_km2,kaugus_suudmest_km,"
    "jaam_laiuskraad,jaam_pikkuskraad,veekogu_nimi"
)


def quote_list(values: list[Any]) -> str:
    """PostgREST ``in.(...)`` list; text values are double-quoted."""
    return "(" + ",".join(json_value(v) for v in values) + ")"


def json_value(v: Any) -> str:
    return str(v) if isinstance(v, (int, float)) else '"' + str(v).replace('"', '\\"') + '"'


def discover(
    client: Client, column: str, base: dict[str, str], select: str
) -> list[dict[str, Any]]:
    """One representative row per distinct ``column`` value under the ``base`` filters."""
    found: list[dict[str, Any]] = []
    seen: list[Any] = []
    while len(found) < MAX_STATIONS:
        filters = dict(base)
        if seen:
            filters[column] = f"not.in.{quote_list(seen)}"
        rows = client.rows(TABLE, select=select, filters=filters, limit=1)
        if not rows:
            return found
        found.append(rows[0])
        seen.append(rows[0][column])
    raise PostgrestError(f"more than {MAX_STATIONS} distinct values of {column}")


def edge(client: Client, filters: dict[str, str], order: str) -> str | None:
    rows = client.rows(TABLE, select="timeline_ts_utc", filters=filters, order=order, limit=1)
    return rows[0]["timeline_ts_utc"] if rows else None


def series_coverage(client: Client, station: Any, name: str) -> dict[str, Any]:
    """Row count and first/last timestamp of one series; each query is timed (seconds)."""
    f = {"jaam_kood": f"eq.{station}", "aegrida_nimi": f"eq.{name}"}
    out: dict[str, Any] = {"series": name, "rows": None, "first_utc": None, "last_utc": None}
    steps = (
        ("rows", lambda: client.count(TABLE, f)),
        ("first_utc", lambda: edge(client, f, "timeline_ts_utc.asc")),
        ("last_utc", lambda: edge(client, f, "timeline_ts_utc.desc")),
    )
    for key, call in steps:
        t0 = time.monotonic()
        try:  # e.g. statement timeout: keep what we have and carry on
            out[key] = call()
        except PostgrestError as exc:
            out.setdefault("errors", {})[key] = str(exc)[:160]
        out.setdefault("seconds", {})[key] = round(time.monotonic() - t0, 2)
    return out


def write(out: Path, result: dict[str, Any]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "hydro_catalog.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def run(client: Client, out: Path, budget_s: float = 2400.0) -> dict[str, Any]:
    """Build the catalogue; stops cleanly when ``budget_s`` is used up (``complete`` = False)."""
    start = time.monotonic()
    stations = discover(client, "jaam_kood", {}, STATION_FIELDS)
    LOG.info("%d stations found in %.0fs", len(stations), time.monotonic() - start)
    result: dict[str, Any] = {"table": TABLE, "stations": stations, "complete": False}
    write(out, result)  # a usable station list even if the rest takes too long
    for st in stations:
        if time.monotonic() - start > budget_s:
            LOG.warning("time budget used up at station %s", st["jaam_kood"])
            return result
        names = discover(
            client, "aegrida_nimi", {"jaam_kood": f"eq.{st['jaam_kood']}"}, "jaam_kood,aegrida_nimi"
        )
        st["series"] = [series_coverage(client, st["jaam_kood"], n["aegrida_nimi"]) for n in names]
        LOG.info("%s %s: %s", st["jaam_kood"], st["jaam_nimi"], [s["series"] for s in st["series"]])
        write(out, result)
    result["complete"] = True
    write(out, result)
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("out/hydro"))
    ap.add_argument("--delay", type=float, default=0.3)
    ap.add_argument("--budget-min", type=float, default=40.0, help="stop after this many minutes")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(Client(delay=args.delay), args.out, args.budget_min * 60)


if __name__ == "__main__":
    main()
