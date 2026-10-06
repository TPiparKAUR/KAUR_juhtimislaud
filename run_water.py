#!/usr/bin/env python3
"""Build ``water.json`` (aggregated water-body status results for the site) from the raw tables.

Usage
-----
    uv run python run_water.py --raw out/water --out out/water
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

import water_analysis as wa

LOG = logging.getLogger("run_water")


def build(
    register: pl.DataFrame,
    states: pl.DataFrame,
    load: pl.DataFrame,
    gw: pl.DataFrame,
    generated: str | None = None,
) -> dict[str, Any]:
    cur = wa.valid_states(states, register)
    by_year = wa.by_year(cur)
    snapshot = wa.distribution(cur.filter(pl.col("year") == wa.BASELINE_YEAR))
    return {
        "meta": {
            "generated_utc": generated or datetime.now(UTC).isoformat(timespec="seconds"),
            "source": "keskkonnaandmed.envir.ee: f_veekogumid, f_veekogumi_seisundid, "
            "f_veekogumid_koormus, f_pohjaveekogumi_seisud",
            "baseline_year": wa.BASELINE_YEAR,
            "class_names": wa.CLASS_NAMES,
            "register_valid_bodies": int((register["keht_staatus"] == "Kehtiv").sum()),
            "register_all_bodies": register.height,
            "status_bodies": int(cur["vkm_id"].n_unique()),
            "interpretation": [
                "tüüp S = hinnatud seisund, E = eesmärk; kasutatakse ainult kehtivaid ridu "
                "(Kehtiv), mitu rida sama veekogumi ja aasta kohta: jäetakse viimati muudetud.",
                "seis = koondhinnang klassidena 1 (väga hea) ... 5 (väga halb); muud koodid "
                "(U, N, O, 6) loetakse klassifitseerimata ja jäetakse osakaalu nimetajast välja. "
                "Koondhinnangu täpne koostis (ÖSE/KESE, ökoloogiline seisund vs potentsiaal) "
                "on kinnitamata.",
                "Pärast 2015. aastat hinnatakse igal aastal ainult osa veekogumeid (~150), seega "
                "aastaid ei saa riikliku aegreana võrrelda; võrdlus tehakse veekogumite kaupa "
                "paarituna (2015 vs viimane hilisem hinnang).",
                "Hindamismeetod ja piirväärtused võivad ajas muutuda; muutuse põhjus (tegelik "
                "seisund vs meetod) on andmetest nähtamatu.",
                "Kategooria on rühmitatud tabeli veekogu_tyyp põhjal (11-15 vooluveekogu, "
                "21-23 järv, 30 meri).",
            ],
        },
        "by_year": by_year,
        "baseline_distribution": snapshot,
        "by_group_baseline": wa.by_group_baseline(cur),
        "paired": wa.paired(cur),
        "targets": wa.targets(states),
        "pressures": wa.pressures(load, register),
        "groundwater": wa.groundwater(gw),
        "checks": {
            "status_rows_valid_S": cur.height,
            "by_year_total": sum(r["n"] for r in by_year),
        },
    }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw", type=Path, default=Path("out/water"))
    ap.add_argument("--out", type=Path, default=Path("out/water"))
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    rd = args.raw
    result = build(
        pl.read_parquet(rd / "f_veekogumid.parquet"),
        pl.read_parquet(rd / "f_veekogumi_seisundid.parquet"),
        pl.read_parquet(rd / "f_veekogumid_koormus.parquet"),
        pl.read_parquet(rd / "f_pohjaveekogumi_seisud.parquet"),
    )
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "water.json").write_text(
        json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    LOG.info("wrote %s", args.out / "water.json")


if __name__ == "__main__":
    main()
