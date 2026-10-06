#!/usr/bin/env python3
"""Build ``nature.json`` (aggregated conservation statistics for the site) from the raw tables.

Usage
-----
    uv run python run_nature.py --raw out/nature --out out/nature
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

import nature_analysis as na

LOG = logging.getLogger("run_nature")


def build(
    alad: pl.DataFrame,
    rahvalad: pl.DataFrame,
    el: pl.DataFrame,
    ls: pl.DataFrame,
    lk: pl.DataFrame,
    vp: pl.DataFrame,
    generated: str | None = None,
) -> dict[str, Any]:
    return {
        "meta": {
            "generated_utc": generated or datetime.now(UTC).isoformat(timespec="seconds"),
            "source": "keskkonnaandmed.envir.ee: f_alad, f_rahvalad, f_rahvalad_elupaikstat, "
            "f_rahvalad_lkohtstat, f_lkohad, f_vepid",
            "interpretation": [
                "Kaitsealade pindalad kattuvad (vööndid, püsielupaigad kaitsealade sees), seega "
                "pindalasid ei liideta tüüpide vahel; ühik (ha) on eeldatud.",
                "Natura standardbaasi versioone tähistab tabeli selgitus (2010, 2012, 2015, 2026); "
                "mõne versiooni numbriline kood erineb selgitusest, kasutatakse selgitust.",
                "Natura elupaigaklass „säilinud“ on ala-taseme hinnang, mitte riiklik soodsa "
                "seisundi hinnang; paaritatud võrdlus sama ala ja elupaigatüübi kohta.",
                "Leiukohtade arv sõltub inventeerimise ulatusest ja registreerimise tavast, mitte "
                "liigi arvukusest; aegridu ei esitata.",
                "Koordinaate, nimesid ega vabateksti ei laadita ega avaldata.",
            ],
        },
        "protected_areas": na.protected_areas(alad),
        "natura_sites": na.natura_sites(rahvalad),
        "habitats": na.habitats(el),
        "species_stats": na.species_stats(ls),
        "species_sites": na.species_sites(lk),
        "key_habitats": na.key_habitats(vp),
    }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw", type=Path, default=Path("out/nature"))
    ap.add_argument("--out", type=Path, default=Path("out/nature"))
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    rd = args.raw
    names = (
        "f_alad",
        "f_rahvalad",
        "f_rahvalad_elupaikstat",
        "f_rahvalad_lkohtstat",
        "f_lkohad",
        "f_vepid",
    )
    a, r, el, ls, lk, vp = (pl.read_parquet(rd / f"{t}.parquet") for t in names)
    result = build(a, r, el, ls, lk, vp)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "nature.json").write_text(
        json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    LOG.info("wrote %s", args.out / "nature.json")


if __name__ == "__main__":
    main()
