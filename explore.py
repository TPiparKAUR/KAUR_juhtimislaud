#!/usr/bin/env python3
"""Profile selected KAUR open-data tables so charts can be designed from facts, not guesses.

For each table: exact row count, a sample spread over the whole table (several offsets, so a
time-ordered table is not judged by its first rows), and per-column statistics: non-null share,
distinct values in the sample, top values of low-cardinality text columns, min/max of numbers
and timestamps.  Output: ``explore/<table>.json`` and ``explore/INDEX.md``.

Tables holding natural persons (``*_fjisik``) are deliberately excluded.

Usage
-----
    uv run python explore.py --out out/explore [--tables f_kliima_kuu ...]
"""

from __future__ import annotations

import argparse
import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any

from postgrest import Client, PostgrestError

LOG = logging.getLogger("explore")
DEFAULT_TABLES = [
    "f_kliima_element",
    "f_kliima_jaam_vaatlus",
    "f_kliima_kuu",
    "f_kliima_paev",
    "f_hydroseire",
    "f_keskkonnaseire",
    "f_seirejaamad",
    "f_veekogumi_seisundid",
    "f_pohjaveekogumi_seisud",
    "f_veekogumid_naitaja",
    "f_veekogumid_koormus",
    "f_veenaitajad_W10_W1_public",
    "f_hks_seisud",
    "stat_t_heitkogus_allikas_curr",
    "t_heitkogus_kaitis_curr",
    "t_soojatoodang_curr",
    "stat_t_awtabel004_curr",
    "f_jaatmeliikumine_fix_riik",
    "jaatmeliik_kogus",
    "f_smi_tulemused",
    "f_rongastused",
    "f_alad",
    "f_rahvalad_elupaikstat",
    "f_rahvalad_lkohtstat",
]
EXCLUDED_SUFFIXES = ("_fjisik",)
SAMPLE_OFFSETS = 5
SAMPLE_SIZE = 400


def sample_table(client: Client, table: str, total: int | None) -> list[dict[str, Any]]:
    """Rows from evenly spread offsets (or the head when the total is unknown/small)."""
    if not total or total <= SAMPLE_SIZE * SAMPLE_OFFSETS:
        return client.rows(table, limit=SAMPLE_SIZE * SAMPLE_OFFSETS)
    step = total // SAMPLE_OFFSETS
    rows: list[dict[str, Any]] = []
    for i in range(SAMPLE_OFFSETS):
        rows += client.rows(table, limit=SAMPLE_SIZE, offset=min(i * step, total - SAMPLE_SIZE))
    return rows


def column_stats(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per-column profile of a list of JSON records."""
    stats: dict[str, dict[str, Any]] = {}
    columns = list(dict.fromkeys(k for r in rows for k in r))
    for col in columns:
        values = [r.get(col) for r in rows]
        present = [v for v in values if v is not None and v != ""]
        s: dict[str, Any] = {
            "non_null_share": round(len(present) / len(values), 3) if values else 0.0,
            "n_distinct_in_sample": len({json.dumps(v, sort_keys=True) for v in present}),
        }
        if present and all(
            isinstance(v, (int, float)) and not isinstance(v, bool) for v in present
        ):
            s["min"], s["max"] = min(present), max(present)
        elif present and all(isinstance(v, str) for v in present):
            if s["n_distinct_in_sample"] <= 40:
                s["top_values"] = Counter(present).most_common(8)
            else:
                s["min"], s["max"] = min(present)[:40], max(present)[:40]
        stats[col] = s
    return stats


def profile(client: Client, table: str) -> dict[str, Any]:
    total = client.count(table)
    rows = sample_table(client, table, total)
    return {
        "table": table,
        "total_rows": total,
        "sample_rows": len(rows),
        "columns": column_stats(rows),
        "head": rows[:2],
    }


def run(client: Client, tables: list[str], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    lines = ["# Explore index\n", "| table | rows | columns |", "|---|---|---|"]
    for table in tables:
        if table.endswith(EXCLUDED_SUFFIXES):
            LOG.warning("skipping %s (person data)", table)
            continue
        try:
            prof = profile(client, table)
        except (PostgrestError, json.JSONDecodeError) as exc:
            LOG.error("%s failed: %s", table, exc)
            lines.append(f"| {table} | ERROR | {exc} |")
            continue
        (out / f"{table}.json").write_text(
            json.dumps(prof, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
        )
        lines.append(f"| {table} | {prof['total_rows']} | {len(prof['columns'])} |")
        LOG.info("%s: %s rows", table, prof["total_rows"])
    (out / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("out/explore"))
    ap.add_argument("--tables", nargs="*", default=DEFAULT_TABLES)
    ap.add_argument("--delay", type=float, default=0.5)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(Client(delay=args.delay), args.tables, args.out)


if __name__ == "__main__":
    main()
