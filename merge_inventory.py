#!/usr/bin/env python3
"""Merge crawl results into the hand-made visualisation inventory.

Reads the baseline ``data/kaur_tableau_inventar.csv`` and, when present, the crawler outputs
``portal_embeds.csv`` and ``tableau_envir_inventory.csv``.  Adds the columns ``tehnoloogia``,
``omanik``, ``allikas`` and ``leitud_crawlis``.  Baseline rows are never dropped: a row the crawl
did not see is flagged (``leitud_crawlis = ei``), not removed.

Usage
-----
    uv run python merge_inventory.py --crawl-dir out --out data/kaur_viz_inventar.csv
"""

from __future__ import annotations

import argparse
import csv
import logging
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import unquote, urlparse

LOG = logging.getLogger("merge_inventory")
BASE_FIELDS = ["group", "page_url", "host", "workbook", "view", "title"]
OUT_FIELDS = [*BASE_FIELDS, "tehnoloogia", "omanik", "allikas", "leitud_crawlis"]
EMBED_KINDS = frozenset({"tableau-viz", "iframe", "img"})
UNIDENTIFIED_VIEW = "(ei tuvastatud)"
CRAWL_GROUP = "Leitud crawliga"
SERVER_GROUP = "Tableau Server"

Key = tuple[str, str, str, str]


def technology(host: str) -> str:
    """Map a host name to a platform label."""
    h = host.lower()
    if h == "public.tableau.com":
        return "Tableau Public"
    if h == "tableau.envir.ee":
        return "Tableau Server"
    if "tableau" in h:
        return "Tableau"
    if "powerbi.com" in h:
        return "Power BI"
    if any(x in h for x in ("arcgis.com", "arcg.is", "storymaps")):
        return "ArcGIS"
    return "muu"


def owner(host: str) -> str:
    """Return the maintaining organisation for a host.

    Tableau content on the KAUR portal is KAUR-run (the Tableau Public profile is
    ``keskkonnaagentuur.kaur``; the Server is KAUR's own).  Power BI views on the portal
    are RMK's and not KAUR-managed (confirmed by the product owner).  Everything else is
    unknown until someone verifies it.
    """
    tech = technology(host)
    if tech.startswith("Tableau"):
        return "KAUR"
    if tech == "Power BI":
        return "RMK"
    return "tundmatu"


def norm_page(url: str) -> str:
    """Normalise a page URL for matching: decode, drop query/fragment and trailing slash."""
    p = urlparse(unquote(url.strip()))
    return f"{p.scheme}://{p.netloc.lower()}{p.path.rstrip('/')}"


def key_of(row: dict[str, str]) -> Key:
    view = row.get("view", "").strip()
    if view == UNIDENTIFIED_VIEW:
        view = ""
    return (
        norm_page(row.get("page_url", "")),
        row.get("host", "").strip().lower(),
        row.get("workbook", "").strip().casefold(),
        view.casefold(),
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return [{k: (v or "") for k, v in row.items() if k} for row in csv.DictReader(fh)]


def server_rows(rows: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    """Convert Tableau Server views (content URL ``Workbook/sheets/View``) to inventory rows."""
    out: list[dict[str, str]] = []
    for r in rows:
        if r.get("type") != "view":
            continue
        parts = r.get("content_url", "").split("/sheets/", 1)
        workbook, view = (parts[0], parts[1]) if len(parts) == 2 else (r.get("workbook", ""), "")
        out.append(
            {
                "group": f"{SERVER_GROUP}: {r.get('project', '')}".rstrip(": "),
                "page_url": "",
                "host": "tableau.envir.ee",
                "workbook": workbook,
                "view": view or r.get("name", ""),
                "title": r.get("name", ""),
            }
        )
    return out


def merge(
    baseline: list[dict[str, str]],
    portal: list[dict[str, str]] | None,
    server: list[dict[str, str]] | None,
) -> list[dict[str, str]]:
    """Return enriched baseline rows plus rows that only the crawl found."""
    crawled: dict[Key, dict[str, str]] = {}
    for r in portal or []:
        if r.get("kind") in EMBED_KINDS and r.get("host"):
            crawled.setdefault(key_of(r), r)
    # Server views have no portal page; match them on host + workbook + view only.
    server_inv = server_rows(server or [])

    merged: list[dict[str, str]] = []
    seen: set[Key] = set()
    for row in baseline:
        k = key_of(row)
        seen.add(k)
        found = "" if portal is None else ("jah" if k in crawled else "ei")
        merged.append(
            {
                **{f: row.get(f, "") for f in BASE_FIELDS},
                "tehnoloogia": technology(row["host"]),
                "omanik": owner(row["host"]),
                "allikas": "inventar",
                "leitud_crawlis": found,
            }
        )
    baseline_view_keys = {key_of(r)[1:] for r in baseline}
    for k, r in sorted(crawled.items()):
        if k in seen:
            continue
        seen.add(k)
        merged.append(
            {
                "group": CRAWL_GROUP,
                "page_url": r["page_url"],
                "host": r["host"],
                "workbook": r["workbook"],
                "view": r["view"] or UNIDENTIFIED_VIEW,
                "title": "",
                "tehnoloogia": technology(r["host"]),
                "omanik": owner(r["host"]),
                "allikas": "crawl",
                "leitud_crawlis": "jah",
            }
        )
    for r in server_inv:
        vk = key_of(r)[1:]
        if vk in baseline_view_keys:
            # Already listed via its portal page: just note the server confirms it.
            continue
        merged.append(
            {
                **r,
                "tehnoloogia": "Tableau Server",
                "omanik": "KAUR",
                "allikas": "server",
                "leitud_crawlis": "",
            }
        )
    LOG.info(
        "%d baseline rows, %d crawled embeds, %d server views",
        len(baseline),
        len(crawled),
        len(server_inv),
    )
    return merged


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--baseline", type=Path, default=Path("data/kaur_tableau_inventar.csv"))
    ap.add_argument("--crawl-dir", type=Path, default=Path("out"))
    ap.add_argument("--out", type=Path, default=Path("data/kaur_viz_inventar.csv"))
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    portal_path = args.crawl_dir / "portal_embeds.csv"
    server_path = args.crawl_dir / "tableau_envir_inventory.csv"
    portal = read_csv(portal_path) if portal_path.exists() else None
    server = read_csv(server_path) if server_path.exists() else None
    if portal is None:
        LOG.warning("%s missing - leitud_crawlis left empty", portal_path)
    if server is None:
        LOG.warning("%s missing - tableau.envir.ee not merged", server_path)

    rows = merge(read_csv(args.baseline), portal, server)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=OUT_FIELDS)
        w.writeheader()
        w.writerows(rows)
    LOG.info("wrote %s (%d rows)", args.out, len(rows))


if __name__ == "__main__":
    main()
