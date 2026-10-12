#!/usr/bin/env python3
"""Fetch the water-intake register and its boreholes (no names, addresses or coordinates).

``f_veehaarded`` (intakes) and ``f_veehaarded_puurauk`` (boreholes of an intake, with the
groundwater body and aquifer index) are the candidate bridge between groundwater abstraction
reports and approved reserves.  Columns that identify owners, operators, places or people are not
requested; diagnostics list columns, null shares and low-cardinality value counts.

Usage
-----
    uv run python gw_registry_fetch.py --out out/gwregistry
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from postgrest import BASE_URL, Client
from water_fetch import run

LOG = logging.getLogger("gw_registry_fetch")
TABLES = ("f_veehaarded", "f_veehaarded_puurauk")
DROP = (
    "kesk_",
    "tx_",
    "nimi",
    "markus",
    "ehak_",
    "haldaja_",
    "puhasti_",
    "puurija_",
    "valdaja_",
    "jaakreostusala_",
    "aadress",
    "maayksus",
    "katastri_nr",
    "pass_nr",
    "invent_nr",
    "puur_nr",
    "seire_nr",
    "akti_nr",
    "arv_k_nr",
    "aruande_nr",
    "veekogu_selg",
    "vesikond_kuulub_nimi",
    "pohjaveekogum_nimi",
    "veekiht_nimi",
    "puur_org",
    "tehn_seisund",
    "kivimikiht_nimi",
)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("out/gwregistry"))
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--base-url", default=BASE_URL)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(
        Client(base_url=args.base_url),
        args.out,
        args.workers,
        TABLES,
        DROP,
        "gwregistry_diagnostics.json",
    )


if __name__ == "__main__":
    main()
