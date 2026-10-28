#!/usr/bin/env python3
"""Fetch Eurostat datasets (JSON-stat 2.0, dissemination API) into long Parquet.

Usage
-----
    uv run python eurostat_fetch.py --dataset cei_srm030 --filter geo=EE --filter geo=EU27_2020 \
        --out out/eurostat
"""

from __future__ import annotations

import argparse
import json
import logging
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from statee_fetch import flatten

LOG = logging.getLogger("eurostat_fetch")
BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"


def url_for(dataset: str, filters: list[tuple[str, str]]) -> str:
    params = [("format", "JSON"), ("lang", "EN"), *filters]
    return f"{BASE}/{dataset}?{urllib.parse.urlencode(params)}"


def parse_filters(items: list[str]) -> list[tuple[str, str]]:
    out = []
    for it in items:
        key, _, value = it.partition("=")
        if not key or not value:
            raise ValueError(f"filter must look like name=value: {it!r}")
        out.append((key, value))
    return out


def dimension_labels(js: dict[str, Any]) -> dict[str, Any]:
    """Code -> label for every dimension (classification labels only)."""
    out: dict[str, Any] = {}
    for d in js["id"]:
        dim = js["dimension"][d]
        labels = dim["category"].get("label", {})
        out[d] = {"label": dim.get("label"), "values": labels}
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset", action="append", required=True)
    ap.add_argument("--filter", action="append", default=[], help="name=value, repeatable")
    ap.add_argument("--out", type=Path, default=Path("out/eurostat"))
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args.out.mkdir(parents=True, exist_ok=True)
    filters = parse_filters(args.filter)
    summary: dict[str, Any] = {}
    for ds in args.dataset:
        url = url_for(ds, filters)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "kaur-juhtimislaud"})
            with urllib.request.urlopen(req, timeout=120) as r:
                js = json.loads(r.read().decode("utf-8"))
            df = flatten(js)
            df.write_parquet(args.out / f"{ds}.parquet")
            summary[ds] = {
                "label": js.get("label"),
                "updated": js.get("updated"),
                "rows": df.height,
                "dimensions": dimension_labels(js),
            }
        except Exception as exc:
            LOG.warning("%s failed: %s", ds, exc)
            summary[ds] = {"error": str(exc)[:300], "url": url}
    (args.out / "eurostat_meta.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
