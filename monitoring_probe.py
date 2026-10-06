#!/usr/bin/env python3
"""Probe the environmental-monitoring table (``f_keskkonnaseire``) and bird ringing table.

The monitoring table is in long format (one measured value or observation per row) and may be
very large, so this probe first *counts* rows (exact counts via ``Content-Range``) overall, per
filter and per period, and reads small samples of descriptive columns.  Coordinates, observer
names and free text are never requested.  Output: ``monitoring_probe.json``.

Usage
-----
    uv run python monitoring_probe.py --out out/monitoring
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

from postgrest import BASE_URL, Client, PostgrestError

LOG = logging.getLogger("monitoring_probe")
TABLE = "f_keskkonnaseire"
RINGING = "f_rongastused"
SAMPLE_COLS = (
    "seiretoo_kood,seiretoo_nimetus,seiretoo_liik_selg,seiretoo_algusaasta,seiretoo_loppaasta,"
    "naitaja_grupp_selg,naitaja_alamgrupp_selg,naitaja_kood,naitaja_nimetus,naitaja_abr_unit,"
    "vaartus_staatus,vaatlusgrupp_selg,seirekogum_tyyp,takson_tyyp_selg,liik_est,liik_kategooria,"
    "takson_est,seireaeg_algus,mootemaaramatus"
)
FILTERS: dict[str, dict[str, str]] = {
    "species_set": {"liik_est": "not.is.null"},
    "taxon_set": {"takson_est": "not.is.null"},
    "value_numeric": {"vaartus_arv_moodetud": "not.is.null"},
    "uncertainty_set": {"mootemaaramatus": "not.is.null"},
    "observation_group": {"vaatlusgrupp_selg": "not.is.null"},
    "water_body": {"veekogum_kood": "not.is.null"},
    "groundwater_body": {"pohjaveekogum_kood": "not.is.null"},
}


def safe(label: str, fn: Any) -> Any:
    try:
        return fn()
    except PostgrestError as exc:  # keep probing the rest
        LOG.warning("%s failed: %s", label, exc)
        return {"error": str(exc)[:300]}


def run(client: Client, out: Path, years: range = range(1995, 2027, 5)) -> dict[str, Any]:
    res: dict[str, Any] = {"table": TABLE}
    res["total"] = safe("total", lambda: client.count(TABLE))
    res["filters"] = {k: safe(k, lambda f=f: client.count(TABLE, f)) for k, f in FILTERS.items()}
    res["by_period_start"] = {
        str(y): safe(
            f"p{y}",
            lambda y=y: client.count(
                TABLE, {"and": f"(seireaeg_algus.gte.{y}-01-01,seireaeg_algus.lt.{y + 5}-01-01)"}
            ),
        )
        for y in years
    }
    res["sample_species"] = safe(
        "sample_species",
        lambda: client.rows(
            TABLE, select=SAMPLE_COLS, filters={"liik_est": "not.is.null"}, limit=300
        ),
    )
    res["sample_any"] = safe(
        "sample_any", lambda: client.rows(TABLE, select=SAMPLE_COLS, limit=300, offset=5_000_000)
    )
    res["ringing_total"] = safe("ringing", lambda: client.count(RINGING))
    res["ringing_by_period"] = {
        str(y): safe(
            f"r{y}",
            lambda y=y: client.count(
                RINGING, {"and": f"(vaatlus_kp.gte.{y}-01-01,vaatlus_kp.lt.{y + 5}-01-01)"}
            ),
        )
        for y in range(1995, 2027, 5)
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "monitoring_probe.json").write_text(
        json.dumps(res, ensure_ascii=True, indent=1, default=str), encoding="utf-8"
    )
    return res


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("out/monitoring"))
    ap.add_argument("--base-url", default=BASE_URL)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(Client(base_url=args.base_url), args.out)


if __name__ == "__main__":
    main()
