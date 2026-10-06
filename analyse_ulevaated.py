#!/usr/bin/env python3
"""Coverage and priority of KAUR's Tableau "Keskkonnaülevaade" views on this site.

Joins ``data/ulevaate_kaetus.toml`` (analyst's coverage assessment) with the public view counts
of the Tableau Public profile (``data/tableau_public_workbooks.csv``; the count is assumed to be
total views since publication) and writes ``out/ulevaated/ulevaated_kaetus.json`` plus a Markdown
table.  The Tableau views themselves were not opened: their content is known by title only.

Usage
-----
    uv run python analyse_ulevaated.py --out docs
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import tomllib
from collections import defaultdict
from pathlib import Path
from typing import Any

LOG = logging.getLogger("analyse_ulevaated")
STATUSES = ("olemas", "osaliselt", "puudub")
THEME_TITLES = {
    "ilm-ja-kliima": "Ilm ja kliima",
    "energeetika": "Energeetika",
    "valisohk": "Välisõhk",
    "mets": "Mets",
    "liigid": "Liigid",
    "okosusteemid": "Ökosüsteemid",
    "vesi": "Vesi",
    "muld-ja-maahoive": "Muld ja maahõive",
    "jaatmed": "Jäätmed",
    "seire": "Seire (RKSP)",
}


def load(coverage: Path, workbooks: Path) -> list[dict[str, Any]]:
    cov = tomllib.loads(coverage.read_text(encoding="utf-8"))["vaade"]
    with workbooks.open(encoding="utf-8", newline="") as fh:
        wb = {r["workbook"]: r for r in csv.DictReader(fh)}
    rows = []
    for c in cov:
        w = wb.get(c["workbook"])
        if w is None:
            raise KeyError(f"workbook not in profile list: {c['workbook']}")
        rows.append({**c, "title": w["title"], "views": int(w["view_count"] or 0)})
    return rows


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    themes: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "views": 0,
            "n": 0,
            **dict.fromkeys(STATUSES, 0),
            **{f"views_{s}": 0 for s in STATUSES},
        }
    )
    for r in rows:
        t = themes[r["teema"]]
        t["views"] += r["views"]
        t["n"] += 1
        t[r["meie"]] += 1
        t[f"views_{r['meie']}"] += r["views"]
    for t in themes.values():
        t["share_views_uncovered"] = (
            round(t["views_puudub"] / t["views"], 3) if t["views"] else None
        )
    total = sum(r["views"] for r in rows)
    return {
        "total_views": total,
        "n_views": len(rows),
        "by_status": {
            s: {
                "n": sum(r["meie"] == s for r in rows),
                "views": sum(r["views"] for r in rows if r["meie"] == s),
            }
            for s in STATUSES
        },
        "themes": dict(themes),
        "top_gaps": sorted((r for r in rows if r["meie"] != "olemas"), key=lambda r: -r["views"])[
            :12
        ],
    }


def markdown(rows: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    out = [
        "# Keskkonnaülevaate vaated ja nende katvus (genereeritud)",
        "",
        "Genereeritud `analyse_ulevaated.py` poolt failidest `data/ulevaate_kaetus.toml` ja "
        "`data/tableau_public_workbooks.csv`. Vaatamiste arv on eeldatud kogu perioodi näit.",
        "",
        "| Teema | Vaateid | Vaatamisi | Olemas | Osaliselt | Puudub | Vaatamistest katmata, % |",
        "|---|---|---|---|---|---|---|",
    ]
    for slug, t in sorted(summary["themes"].items(), key=lambda kv: -kv[1]["views"]):
        share = (
            f"{100 * t['share_views_uncovered']:.0f}"
            if t["share_views_uncovered"] is not None
            else "-"
        )
        out.append(
            f"| {THEME_TITLES.get(slug, slug)} | {t['n']} | {t['views']} | {t['olemas']} | "
            f"{t['osaliselt']} | {t['puudub']} | {share} |"
        )
    out += [
        "",
        "## Vaated",
        "",
        "| Teema | Vaade | Vaatamisi | Meie | Andmed | Märkus |",
        "|---|---|---|---|---|---|",
    ]
    for r in sorted(rows, key=lambda r: (r["teema"], -r["views"])):
        out.append(
            f"| {THEME_TITLES.get(r['teema'], r['teema'])} | {r['title']} | {r['views']} | "
            f"{r['meie']} | {r['andmed']} | {r['markus']} |"
        )
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--coverage", type=Path, default=Path("data/ulevaate_kaetus.toml"))
    ap.add_argument("--workbooks", type=Path, default=Path("data/tableau_public_workbooks.csv"))
    ap.add_argument("--out", type=Path, default=Path("docs"))
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    rows = load(args.coverage, args.workbooks)
    summary = summarise(rows)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "ulevaated_kaetus.json").write_text(
        json.dumps({"summary": summary, "views": rows}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    (args.out / "ulevaated_kaetus.md").write_text(markdown(rows, summary), encoding="utf-8")
    LOG.info("wrote %d views", len(rows))


if __name__ == "__main__":
    main()
