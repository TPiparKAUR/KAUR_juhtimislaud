#!/usr/bin/env python3
"""Build ``wateruse.json`` (aggregated water use / discharge results for the site).

Usage
-----
    uv run python run_wateruse.py --raw out/wateruse --out out/wateruse
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

import wateruse_analysis as wu

LOG = logging.getLogger("run_wateruse")
NAMES = (
    "t_awtabel004_curr",
    "t_awtabel002_01_curr",
    "t_awtabel002_02_curr",
    "t_awtabel006_01_curr",
    "f_pohjaveevarud",
    "f_reoveealad",
)


def build(
    use: pl.DataFrame,
    gw: pl.DataFrame,
    sw: pl.DataFrame,
    dis: pl.DataFrame,
    res: pl.DataFrame,
    ra: pl.DataFrame,
    generated: str | None = None,
) -> dict[str, Any]:
    return {
        "meta": {
            "generated_utc": generated or datetime.now(UTC).isoformat(timespec="seconds"),
            "source": "keskkonnaandmed.envir.ee: t_awtabel004_curr, t_awtabel002_01_curr, "
            "t_awtabel002_02_curr, t_awtabel006_01_curr, f_pohjaveevarud, f_reoveealad",
            "years": sorted(use["aruandeaasta"].unique().to_list()),
            "interpretation": [
                "Veearuannete tabelid sisaldavad ainult viimaseid aruandeaastaid; aastate vahelist "
                "muutust ei saa lahutada aruandluse muutusest (aruannete arv erineb).",
                "Mahud on m3 aastas, kogused t aastas, kontsentratsioonid mg/l (eeldatud, tabeli "
                "veerukirjelduste järgi).",
                "Jahutusvesi on väga suur ja pärineb enamasti pinna- või merevee kasutusest; seda "
                "näidatakse eraldi.",
                "Vastavus = vähemalt üks kvartali kontsentratsioon ületab lubatud piirmäära "
                "väljalaskmetel, millel on piirmäär märgitud; kontsentratsioonid on suures osas "
                "arvutuslikud, mitte mõõdetud.",
                "Põhja- ja pinnaveevõtu summa ühtib veekasutuse kogusummaga, kuid veeliikide "
                "jaotus erineb (tõenäoliselt kaevandus- ja karjäärivesi; kinnitamata).",
                "Põhjaveevarusid ei võrrelda veevõtuga: veevõtu tabel ei seo veehaaret varuga.",
                "Käitiste, väljalaskmete ja veehaarete nimesid ei laeta ega avaldata.",
            ],
        },
        "use_by_type": wu.use_by_type(use),
        "use_by_sector": wu.use_by_sector(use),
        "abstraction": wu.abstraction(gw, sw),
        "discharge": wu.discharge(dis),
        "agglomerations": wu.agglomerations(ra),
        "reserves": wu.reserves(res),
        "checks": {
            "sector_tiling": wu.sector_tiling(use),
            "use_duplicates": wu.duplicates(use),
            "abstraction_vs_use": wu.abstraction_vs_use(use, gw, sw),
        },
    }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw", type=Path, default=Path("out/wateruse"))
    ap.add_argument("--out", type=Path, default=Path("out/wateruse"))
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    use, gw, sw, dis, res, ra = (pl.read_parquet(args.raw / f"{n}.parquet") for n in NAMES)
    result = build(use, gw, sw, dis, res, ra)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "wateruse.json").write_text(
        json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    LOG.info("wrote %s", args.out / "wateruse.json")


if __name__ == "__main__":
    main()
