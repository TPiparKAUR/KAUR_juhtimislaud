#!/usr/bin/env python3
"""Classify the figures and tables of the yearbooks by what their *captions* say.

Input is ``yearbooks_summary.json`` from ``fetch_yearbooks.py`` (captions only, no page images).
The classification is therefore a keyword heuristic on caption text, not on the drawn chart: it
tells *what a figure is about* (time, composition, group comparison, map, which breakdown) but
not whether it is a line, bar or stacked chart.  Captions in a second language (the Estonian
yearbooks print Estonian and English captions) are counted once.

Usage
-----
    uv run python analyse_yearbooks.py --summary yearbooks_summary.json --out out/yearbooks
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from collections import Counter
from pathlib import Path
from typing import Any

LOG = logging.getLogger("analyse_yearbooks")
FIGURE_LABELS = {"joonis", "figure", "fig.", "figur", "figuur"}
TABLE_LABELS = {"tabel", "table", "tabell"}
# Labels of the second (English) caption line, ignored when the document also has native labels.
SECOND_LANGUAGE = {"figure", "table"}

FORMS: dict[str, str] = {
    "time": r"aastail|aastatel|perioodil|muutumi|muutus|dünaamika|utvikling|udvikling|utveckling|"
    r"over tid|\bsiden\b|trend|\b(19|20)\d{2}\s*[-\u2013]\s*(19|20)?\d{2}",
    "composition": r"jagunemi|jaotus|jaotumi|osakaal|fordel|fördel|andel|oppdelt|share",
    "map": r"\bkaart|\bkart\b|\bmap\b|\bkort\b",
}
DIMENSIONS: dict[str, str] = {
    "geography": r"maakon|jahipiirkon|regio|fylke|kommun|piirkon",
    "species": r"puuliik|enamuspuuliig|treslag|artsgrupp|\barter\b|liigi",
    "age": r"vanus|alder|aldersklasse|hogstklasse|vanuseklass",
    "ownership": r"omand|eraomand|riigimets|eraomanik",
    "diameter": r"diameeter|diameterklasse|rinnasdiameeter",
}
THEMES: dict[str, str] = {
    "area": r"pindala|areal|arealet|skovareal",
    "stock": r"tagavara|volum|vedmasse|stående|hektaritagavara",
    "increment": r"juurdekasv|tilvækst|tilvekst",
    "felling": r"raie|raiemaht|hugst|hogst|avverk",
    "health_damage": r"tervis|okkakadu|afløvning|nåletab|kahjust|skad",
    "fire_hunting": r"tulekahju|küttimi|jahi",
    "economy": r"hind|raha|turu|majandus|kostnad|tulu",
    "biodiversity": r"elupaik|natura|liigid|surnud puit|dødt ved|habitat",
}
UNCERTAINTY_IN_CAPTION = re.compile(
    r"viga|usaldus|confidence|error|konfidens|usikkerhet|standardfejl|osäkerhet", re.I
)


def tags(text: str, rules: dict[str, str]) -> list[str]:
    low = text.lower()
    return [name for name, rx in rules.items() if re.search(rx, low)]


def native_captions(rec: dict[str, Any]) -> list[dict[str, Any]]:
    """Captions with labels of the document's own language (English duplicates dropped)."""
    caps = rec.get("captions") or []
    labels = {c["label"] for c in caps}
    native_exists = bool(labels - SECOND_LANGUAGE)
    return [c for c in caps if not (native_exists and c["label"] in SECOND_LANGUAGE)]


def classify(rec: dict[str, Any]) -> dict[str, Any]:
    caps = native_captions(rec)
    figs = [c for c in caps if c["label"] in FIGURE_LABELS and len(c["text"]) > 12]
    tabs = [c for c in caps if c["label"] in TABLE_LABELS and len(c["text"]) > 12]

    def summarise(items: list[dict[str, Any]]) -> dict[str, Any]:
        forms: Counter[str] = Counter()
        dims: Counter[str] = Counter()
        themes: Counter[str] = Counter()
        none_form = unc = 0
        for c in items:
            f = tags(c["text"], FORMS)
            forms.update(f)
            dims.update(tags(c["text"], DIMENSIONS))
            themes.update(tags(c["text"], THEMES))
            none_form += not f
            unc += bool(UNCERTAINTY_IN_CAPTION.search(c["text"]))
        return {
            "n": len(items),
            "forms": dict(forms),
            "dimensions": dict(dims),
            "themes": dict(themes),
            "no_form_keyword": none_form,
            "caption_mentions_uncertainty": unc,
        }

    pages = rec.get("pages") or 0
    return {
        "id": rec["id"],
        "country": rec.get("riik"),
        "pages": pages,
        "figures": summarise(figs),
        "tables": summarise(tabs),
        "figures_per_100_pages": round(100 * len(figs) / pages, 1) if pages else None,
        "tables_per_100_pages": round(100 * len(tabs) / pages, 1) if pages else None,
        "uncertainty_keyword_pages": len(
            {h["page"] for h in (rec.get("keyword_hits") or {}).get("uncertainty", [])}
        ),
    }


def build(summary: list[dict[str, Any]]) -> dict[str, Any]:
    docs = [classify(r) for r in summary if r.get("kind") == "pdf" and r.get("captions")]
    total_f = sum(d["figures"]["n"] for d in docs)
    forms: Counter[str] = Counter()
    dims: Counter[str] = Counter()
    for d in docs:
        forms.update(d["figures"]["forms"])
        dims.update(d["figures"]["dimensions"])
    return {
        "method": "caption keyword heuristic; no page images were analysed",
        "documents": docs,
        "totals": {
            "documents": len(docs),
            "figures": total_f,
            "tables": sum(d["tables"]["n"] for d in docs),
            "figure_forms": dict(forms),
            "figure_dimensions": dict(dims),
        },
    }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--summary", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("out/yearbooks"))
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "yearbook_figures.json").write_text(
        json.dumps(build(summary), ensure_ascii=False, indent=1), encoding="utf-8"
    )
    LOG.info("wrote %s", args.out / "yearbook_figures.json")


if __name__ == "__main__":
    main()
