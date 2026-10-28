#!/usr/bin/env python3
"""Fetch Statistics Estonia PxWeb tables (metadata and, if small enough, all cells).

For every table path the variable codes, texts and value codes/texts are written to
``statee_meta.json`` (public classification labels only).  The data are requested with all values
of all variables in ``json-stat2`` and flattened to a long Parquet file ``<table>.parquet`` (one
row per cell, columns = variable codes, ``value``, ``status``).  Tables above ``--max-cells`` are
not requested.

Usage
-----
    uv run python statee_fetch.py --table majandus/energeetika/.../KE0230.PX --out out/statee
"""

from __future__ import annotations

import argparse
import itertools
import json
import logging
import math
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import polars as pl

LOG = logging.getLogger("statee_fetch")
BASE = "https://andmed.stat.ee/api/v1/et/stat"
DEFAULT_MAX_CELLS = 90_000
PAUSE_S = 0.5


def request(url: str, body: dict[str, Any] | None = None) -> Any:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"User-Agent": "kaur-juhtimislaud", "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def meta_summary(meta: dict[str, Any]) -> dict[str, Any]:
    variables = []
    for v in meta.get("variables", []):
        values = v.get("values", [])
        texts = v.get("valueTexts", [])
        variables.append(
            {
                "code": v.get("code"),
                "text": v.get("text"),
                "elimination": v.get("elimination", False),
                "time": v.get("time", False),
                "n": len(values),
                "values": [{"code": c, "text": t} for c, t in zip(values, texts, strict=False)],
            }
        )
    return {"title": meta.get("title"), "variables": variables}


def cells(meta: dict[str, Any]) -> int:
    return math.prod(max(1, len(v.get("values", []))) for v in meta.get("variables", []))


def query_body(meta: dict[str, Any]) -> dict[str, Any]:
    return {
        "query": [
            {"code": v["code"], "selection": {"filter": "all", "values": ["*"]}}
            for v in meta.get("variables", [])
        ],
        "response": {"format": "json-stat2"},
    }


def flatten(js: dict[str, Any]) -> pl.DataFrame:
    """json-stat2 dataset to one row per cell with the *codes* of every dimension."""
    ids = js["id"]
    codes: list[list[str]] = []
    for d in ids:
        index = js["dimension"][d]["category"]["index"]
        if isinstance(index, dict):
            codes.append([k for k, _ in sorted(index.items(), key=lambda kv: kv[1])])
        else:
            codes.append(list(index))
    rows = list(itertools.product(*codes))
    values = js["value"]
    status = js.get("status") or {}
    out: dict[str, list[Any]] = {d: [r[i] for r in rows] for i, d in enumerate(ids)}
    if isinstance(values, dict):  # sparse json-stat: position -> value
        values = [values.get(str(i)) for i in range(len(rows))]
    out["value"] = list(values)
    out["status"] = [
        status.get(str(i)) if isinstance(status, dict) else None for i in range(len(rows))
    ]
    return pl.DataFrame(out, schema_overrides={"value": pl.Float64, "status": pl.Utf8})


def fetch_table(path: str, out: Path, max_cells: int) -> dict[str, Any]:
    url = f"{BASE}/{path}"
    meta = request(url)
    summary = meta_summary(meta)
    summary["cells"] = cells(meta)
    if summary["cells"] > max_cells:
        summary["data"] = "skipped (too many cells)"
        return summary
    time.sleep(PAUSE_S)
    js = request(url, query_body(meta))
    df = flatten(js)
    name = urllib.parse.unquote(path.rsplit("/", 1)[-1]).replace(".PX", "")
    df.write_parquet(out / f"{name}.parquet")
    summary["data"] = {"rows": df.height, "file": f"{name}.parquet"}
    summary["units"] = {
        d: js["dimension"][d]["category"]["unit"]
        for d in js["id"]
        if "unit" in js["dimension"].get(d, {}).get("category", {})
    }
    summary["notes"] = (js.get("note") or [])[:5]
    summary["dimension_labels"] = {
        d: js["dimension"][d].get("label") for d in js["id"] if d in js.get("dimension", {})
    }
    return summary


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--table", action="append", required=True, help="PxWeb table path")
    ap.add_argument("--out", type=Path, default=Path("out/statee"))
    ap.add_argument("--max-cells", type=int, default=DEFAULT_MAX_CELLS)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args.out.mkdir(parents=True, exist_ok=True)
    result: dict[str, Any] = {}
    for path in args.table:
        try:
            result[path] = fetch_table(path, args.out, args.max_cells)
        except Exception as exc:
            LOG.warning("%s failed: %s", path, exc)
            result[path] = {"error": str(exc)[:300]}
        time.sleep(PAUSE_S)
    (args.out / "statee_meta.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
