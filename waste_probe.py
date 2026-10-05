#!/usr/bin/env python3
"""Time page sizes and ordering for the national waste table (one small year).

Decides how the 20-million-row table can be read: how long a count and a first page take, whether
the server caps the page size, and whether unordered offset paging returns the same rows twice.

Usage
-----
    uv run python waste_probe.py --out out/waste_probe --year 2004
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any

from postgrest import Client, PostgrestError
from waste_explore import GRAIN_COLUMNS, TABLE

LOG = logging.getLogger("waste_probe")


def timed(label: str, fn: Any, out: dict[str, Any], path: Path) -> Any:
    t0 = time.monotonic()
    try:
        res = fn()
        out[label] = {
            "seconds": round(time.monotonic() - t0, 2),
            **(res if isinstance(res, dict) else {}),
        }
    except PostgrestError as exc:
        out[label] = {"seconds": round(time.monotonic() - t0, 2), "error": str(exc)[:200]}
    LOG.info("%s: %s", label, out[label])
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out[label]


def digest(rows: list[dict[str, Any]]) -> str:
    return hashlib.sha1(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()[:12]


def run(client: Client, out_dir: Path, year: int) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "probe.json"
    out: dict[str, Any] = {"year": year}
    flt = {"aasta": f"eq.{year}"}
    cols = ",".join(GRAIN_COLUMNS)
    order = ",".join(GRAIN_COLUMNS)
    timed("count_year", lambda: {"n": client.count(TABLE, flt)}, out, path)
    timed(
        "count_year_type_group",
        lambda: {"n": client.count(TABLE, {**flt, "maht_liik": "eq.Import", "pohigrupp": "eq.20"})},
        out,
        path,
    )
    for size in (5_000, 50_000, 200_000):
        timed(
            f"ordered_page_{size}",
            lambda size=size: {
                "got": len(client.rows(TABLE, select=cols, filters=flt, order=order, limit=size))
            },
            out,
            path,
        )

    # Unordered paging: is the same page returned twice, and are consecutive pages disjoint?
    def unordered() -> dict[str, Any]:
        a = client.rows(TABLE, select=cols, filters=flt, limit=50_000, offset=0)
        b = client.rows(TABLE, select=cols, filters=flt, limit=50_000, offset=0)
        c = client.rows(TABLE, select=cols, filters=flt, limit=50_000, offset=50_000)
        return {
            "got": len(a),
            "same_page_twice": digest(a) == digest(b),
            "next_page_differs": digest(a) != digest(c),
        }

    timed("unordered_pages", unordered, out, path)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("out/waste_probe"))
    ap.add_argument("--year", type=int, default=2004)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(Client(delay=0.0), args.out, args.year)


if __name__ == "__main__":
    main()
