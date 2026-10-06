"""Water-quality monitoring: groundwater nitrate and nutrient concentrations in surface waters.

Input: rows of the indicators nitrate (NO3), nitrate nitrogen (NO3-N), total nitrogen and total
phosphorus from the national monitoring table (``monitoring_extract.py``).  Values are converted
to common units (assumptions stated in the output ``meta``):

* nitrate as NO3 in mg/l: NO3-N (mg N/l) x 4.427 (62.004 / 14.007);
* total nitrogen in mg N/l: umol N/l x 0.014007, ug/l / 1000, mg/m3 / 1000;
* total phosphorus in mg P/l: umol P/l x 0.030974, ug/l / 1000, mg/m3 / 1000.

Rows without a numeric value, with an unknown unit or non-positive conversion factor are
excluded and counted.  Water category comes from the monitoring-unit type code (V = flowing
water, S = standing water, R = coastal water); groundwater rows have a groundwater body code.
Statistics are over *samples* (not flow-weighted, sites differ between years), so they describe
the monitoring data, not national loads.
"""

from __future__ import annotations

from typing import Any

import polars as pl

NO3_FACTOR = 62.004 / 14.007
UNIT_TO_MG_N = {"mg/l": 1.0, "mgN/l": 1.0, "µg/l": 1e-3, "mg/m³": 1e-3, "µmolN/l": 0.014007}
UNIT_TO_MG_P = {"mg/l": 1.0, "mgP/l": 1.0, "µg/l": 1e-3, "mg/m³": 1e-3, "µmolP/l": 0.030974}
NITRATE_LIMIT = 50.0  # mg NO3/l, EU groundwater quality standard for nitrate
CATEGORIES = {"V": "Vooluveekogu", "S": "Seisuveekogu", "R": "Rannikuvesi"}
NAMES_NO3 = {"Nitraat (NO3)": "no3", "Nitraatlämmastik (NO3N)": "no3n"}
NAMES_TN = {"Üldlämmastik"}
NAMES_TP = {"Üldfosfor"}


def category(code: str | None) -> str | None:
    return CATEGORIES.get((code or "")[:1])


def prepare(df: pl.DataFrame) -> pl.DataFrame:
    """Add year, category, groundwater flag; keep rows with a numeric value."""
    return df.with_columns(
        pl.col("seireaeg_algus").str.slice(0, 4).cast(pl.Int32, strict=False).alias("year"),
        pl.col("seirekogum_tyyp").map_elements(category, return_dtype=pl.String).alias("category"),
        pl.col("pohjaveekogum_kood").is_not_null().alias("groundwater"),
    )


def nitrate_mg_no3(df: pl.DataFrame) -> pl.DataFrame:
    """Groundwater nitrate as mg NO3/l (rows converted from NO3-N use the 4.427 factor)."""
    g = df.filter(
        pl.col("naitaja_nimetus").is_in(list(NAMES_NO3))
        & pl.col("groundwater")
        & pl.col("vaartus_arv_moodetud").is_not_null()
        & (pl.col("vaartus_arv_moodetud") >= 0)
    )
    factor = (
        pl.when(pl.col("naitaja_nimetus") == "Nitraatlämmastik (NO3N)")
        .then(pl.lit(NO3_FACTOR))
        .otherwise(pl.lit(1.0))
    )
    is_n = pl.col("naitaja_nimetus") == "Nitraatlämmastik (NO3N)"
    ok_units = g.filter(
        (is_n & pl.col("naitaja_abr_unit").is_in(["mg/l", "mgN/l"]))
        | (~is_n & (pl.col("naitaja_abr_unit") == "mg/l"))
    )
    return ok_units.with_columns((pl.col("vaartus_arv_moodetud") * factor).alias("no3"))


def groundwater_nitrate(df: pl.DataFrame) -> dict[str, Any]:
    d = nitrate_mg_no3(prepare(df))
    years = []
    for (year,), g in d.group_by("year", maintain_order=True):
        site = g.group_by("seirekoht_kood").agg(med=pl.col("no3").median())
        years.append(
            {
                "year": int(year),
                "samples": g.height,
                "sites": g["seirekoht_kood"].n_unique(),
                "median": g["no3"].median(),
                "p90": g["no3"].quantile(0.9),
                "share_over_limit": float((g["no3"] > NITRATE_LIMIT).sum()) / g.height,
                "site_share_over_limit": float((site["med"] > NITRATE_LIMIT).sum()) / site.height
                if site.height
                else None,
                "share_below_loq_mark": float(g["vaartus_erimark"].is_not_null().sum()) / g.height,
            }
        )
    return {
        "limit_mg_no3_l": NITRATE_LIMIT,
        "rows_used": d.height,
        "rows_excluded_unit_or_value": int(
            prepare(df)
            .filter(pl.col("naitaja_nimetus").is_in(list(NAMES_NO3)) & pl.col("groundwater"))
            .height
            - d.height
        ),
        "years": sorted(years, key=lambda r: r["year"]),
    }


def nutrient(df: pl.DataFrame, names: set[str], units: dict[str, float]) -> pl.DataFrame:
    d = prepare(df).filter(
        pl.col("naitaja_nimetus").is_in(list(names))
        & pl.col("category").is_not_null()
        & ~pl.col("groundwater")
        & pl.col("vaartus_arv_moodetud").is_not_null()
        & (pl.col("vaartus_arv_moodetud") >= 0)
        & pl.col("naitaja_abr_unit").is_in(list(units))
    )
    f = pl.col("naitaja_abr_unit").replace_strict(units, return_dtype=pl.Float64)
    return d.with_columns((pl.col("vaartus_arv_moodetud") * f).alias("mg"))


def surface_nutrients(df: pl.DataFrame) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, names, units in (("tn", NAMES_TN, UNIT_TO_MG_N), ("tp", NAMES_TP, UNIT_TO_MG_P)):
        d = nutrient(df, names, units)
        rows = []
        for (cat, year), g in d.group_by("category", "year", maintain_order=True):
            if g.height < 5:
                continue
            rows.append(
                {
                    "category": cat,
                    "year": int(year),
                    "samples": g.height,
                    "sites": g["seirekoht_kood"].n_unique(),
                    "median": g["mg"].median(),
                    "p25": g["mg"].quantile(0.25),
                    "p75": g["mg"].quantile(0.75),
                }
            )
        out[key] = sorted(rows, key=lambda r: (r["category"], r["year"]))
    return out


def checks(df: pl.DataFrame) -> dict[str, Any]:
    d = prepare(df)
    return {
        "rows": d.height,
        "units": d["naitaja_abr_unit"].value_counts().to_dicts(),
        "indicator_names": d["naitaja_nimetus"].value_counts().to_dicts(),
        "category_counts": d["category"].value_counts().to_dicts(),
        "groundwater_rows": int(d["groundwater"].sum()),
        "numeric_share": d["vaartus_arv_moodetud"].is_not_null().sum() / d.height
        if d.height
        else None,
    }


def build(df: pl.DataFrame) -> dict[str, Any]:
    return {
        "meta": {
            "interpretation": [
                "Nitraat on teisendatud mg NO3/l: nitraatlämmastik (mg N/l) korrutatud 4,427-ga.",
                "Üldlämmastik mg N/l ja üldfosfor mg P/l: µmol/l, µg/l ja mg/m³ on teisendatud "
                "aatommassidega (N 14,007; P 30,974); tundmatu ühikuga read jäetakse välja.",
                "Veekogu liik tuleneb seirekogumi tüübi koodi esitähest (V vooluvesi, S seisuvesi, "
                "R rannikuvesi); põhjavee read tuvastatakse põhjaveekogumi koodi järgi.",
                "Statistikud on proovide mediaanid ja protsentiilid (mitte vooluhulgaga kaalutud), "
                "seirekohad ja proovivõtt erinevad aastati; need kirjeldavad seireandmeid, "
                "mitte riiklikku koormust.",
                "Nitraadi piirväärtus 50 mg NO3/l on EL põhjavee kvaliteedinorm; "
                "veekogumi seisundi hinnang selle põhjal ei ole tehtud.",
            ]
        },
        "checks": checks(df),
        "groundwater_nitrate": groundwater_nitrate(df),
        "surface": surface_nutrients(df),
    }
