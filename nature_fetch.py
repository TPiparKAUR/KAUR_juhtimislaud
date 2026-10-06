#!/usr/bin/env python3
"""Fetch nature-conservation tables (protected areas, Natura habitats and species, species sites,
woodland key habitats) and describe their structure.

Tables of schema ``apijahiala``.  Coordinates (``kesk_*``) and free-text descriptions (``tx_*``)
are not requested: they are not needed for aggregated statistics, and the locations of protected
species are sensitive.  ``nature_diagnostics.json`` lists per table the columns, null shares and
the value counts of low-cardinality columns.

Usage
-----
    uv run python nature_fetch.py --out out/nature
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from postgrest import BASE_URL, Client
from water_fetch import run

LOG = logging.getLogger("nature_fetch")
TABLES = (
    "f_alad",
    "f_rahvalad",
    "f_rahvalad_elupaikstat",
    "f_rahvalad_lkohtstat",
    "f_lkohad",
    "f_lkohad_lnim",
    "f_vepid",
)
DROP = ("kesk_", "tx_")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("out/nature"))
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
        "nature_diagnostics.json",
    )


if __name__ == "__main__":
    main()
