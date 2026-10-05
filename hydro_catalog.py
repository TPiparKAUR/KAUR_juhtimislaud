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
    f = {"jaam_kood": f"eq.{station}", "aegrida_nimi": f"eq.{name}"}
    out: dict[str, Any] = {"series": name, "rows": None, "first_utc": None, "last_utc": None}
    try:
        out["rows"] = client.count(TABLE, f)
        out["first_utc"] = edge(client, f, "timeline_ts_utc.asc")
        out["last_utc"] = edge(client, f, "timeline_ts_utc.desc")
    except PostgrestError as exc:  # e.g. statement timeout: keep what we have
        out["error"] = str(exc)[:200]
    return out


def run(client: Client, out: Path) -> dict[str, Any]:
    stations = discover(client, "jaam_kood", {}, STATION_FIELDS)
    LOG.info("%d stations", len(stations))
    for st in stations:
        names = discover(
            client, "aegrida_nimi", {"jaam_kood": f"eq.{st['jaam_kood']}"}, "jaam_kood,aegrida_nimi"
        )
        st["series"] = [series_coverage(client, st["jaam_kood"], n["aegrida_nimi"]) for n in names]
        LOG.info("%s %s: %s", st["jaam_kood"], st["jaam_nimi"], [s["series"] for s in st["series"]])
    result = {"table": TABLE, "total_rows": client.count(TABLE), "stations": stations}
    out.mkdir(parents=True, exist_ok=True)
    (out / "hydro_catalog.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("out/hydro"))
    ap.add_argument("--delay", type=float, default=0.3)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(Client(delay=args.delay), args.out)


if __name__ == "__main__":
    main()
