#!/usr/bin/env python3
"""Fetch water-use, abstraction, discharge and groundwater-reserve tables and describe them.

Tables of schema ``apijahiala`` (water reports of permit holders and reserve registers):
``t_awtabel004_curr`` (water use by sector), ``t_awtabel002_01_curr`` / ``_02_curr`` (groundwater /
surface-water abstraction), ``t_awtabel006_01_curr`` (waste-water discharge and loads),
``f_pohjaveevarud`` (approved groundwater reserves), ``f_reoveealad`` and ``f_reoveealad_koormus``
(sewage agglomerations and their pollution load).

Columns that name facilities, outlets, plants or authors, free text and coordinates are not
requested: only aggregates are published.  ``wateruse_diagnostics.json`` lists columns, null
shares, years and low-cardinality value counts.

Usage
-----
    uv run python wateruse_fetch.py --out out/wateruse
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from postgrest import BASE_URL, Client
from water_fetch import run

LOG = logging.getLogger("wateruse_fetch")
TABLES = (
    "t_awtabel004_curr",
    "t_awtabel002_01_curr",
    "t_awtabel002_02_curr",
    "t_awtabel006_01_curr",
    "f_pohjaveevarud",
    "f_reoveealad",
    "f_reoveealad_koormus",
)
DROP = (
    "kesk_",
    "tx_",
    "markus",
    "veehaardenimetus",
    "jaamanimi",
    "valjalaskmenimetus",
    "puhasti_nimi",
    "nimi",
    "veemaardla_nimi",
    "ehak_tekst",
    "ehak_id",
    "ehak_nimi",
    "ehak_kood2",
    "ehak_kood3",
    "autor",
    "aruande_nr",
)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("out/wateruse"))
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
        "wateruse_diagnostics.json",
    )


if __name__ == "__main__":
    main()
