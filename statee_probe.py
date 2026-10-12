#!/usr/bin/env python3
"""Probe the Statistics Estonia PxWeb API for energy-related tables (catalogue only).

Walks the public PxWeb tree (``/api/v1/et/stat``) breadth-first to a limited depth and keeps the
nodes whose text mentions energy keywords.  Nothing is assumed about the tree: HTTP status and the
first-level node names are recorded so that a wrong base URL is visible.  Only table identifiers,
titles and the variable names of the first matching tables are written; no values.

Usage
-----
    uv run python statee_probe.py --out out/statee
"""

from __future__ import annotations

import argparse
import json
import logging
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

LOG = logging.getLogger("statee_probe")
BASE = "https://andmed.stat.ee/api/v1/et/stat"
KEYWORDS = ("energi", "elektri", "taastuv", "kütus", "soojus", "gaas", "põlevkivi", "kasvuhoone")
MAX_DEPTH = 3
MAX_NODES = 400
PAUSE_S = 0.4


def get_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "kaur-juhtimislaud-probe"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def matches(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in KEYWORDS)


def walk(base: str = BASE, fetch: Any = get_json) -> dict[str, Any]:
    """Breadth-first walk; returns visited count, first-level names and matching nodes."""
    out: dict[str, Any] = {
        "base": base,
        "first_level": [],
        "second_level": [],
        "matches": [],
        "errors": [],
    }
    queue: list[tuple[str, str, int]] = [("", "", 0)]
    visited = 0
    while queue and visited < MAX_NODES:
        path, trail, depth = queue.pop(0)
        url = f"{base}/{path}".rstrip("/")
        try:
            nodes = fetch(url)
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            out["errors"].append({"path": path, "error": str(exc)[:200]})
            continue
        visited += 1
        time.sleep(PAUSE_S)
        if not isinstance(nodes, list):
            out["errors"].append({"path": path, "error": "not a list"})
            continue
        for n in nodes:
            nid, text, typ = str(n.get("id", "")), str(n.get("text", "")), str(n.get("type", ""))
            sub = f"{path}/{nid}".strip("/")
            label = f"{trail} > {text}".strip(" >")
            if depth == 0:
                out["first_level"].append({"id": nid, "text": text})
            if depth == 1:
                out["second_level"].append({"parent": trail, "id": nid, "text": text, "type": typ})
            if typ == "t" and (matches(text) or matches(trail)):
                out["matches"].append({"path": sub, "id": nid, "text": text, "trail": trail})
            elif typ in ("l", "s") and depth + 1 < MAX_DEPTH + 1 and (depth < 2 or matches(label)):
                queue.append((sub, label, depth + 1))
    out["visited"] = visited
    return out


def describe_tables(result: dict[str, Any], fetch: Any = get_json, limit: int = 15) -> None:
    """Add the variable names (no values) of the first matching tables."""
    for m in result["matches"][:limit]:
        try:
            meta = fetch(f"{result['base']}/{m['path']}")
            m["variables"] = [
                {"code": v.get("code"), "text": v.get("text"), "n": len(v.get("values", []))}
                for v in meta.get("variables", [])
            ]
            m["title"] = meta.get("title")
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            m["error"] = str(exc)[:200]
        time.sleep(PAUSE_S)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("out/statee"))
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = walk()
    describe_tables(result)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "statee_probe.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    LOG.info("visited %d nodes, %d matches", result["visited"], len(result["matches"]))


if __name__ == "__main__":
    main()
