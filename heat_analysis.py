"""Heat production: combined heat and power (CHP) plants and monthly production.

Inputs (long Parquet from ``statee_fetch.py``): ``KE034`` (CHP capacity and production),
``KE035`` (fuel used in CHP plants) and ``KE20`` (monthly electricity and heat production, GWh).
The monthly table is not split by producer type, so CHP heat is compared with it only as an
approximate share (scope differences are possible).
"""

from __future__ import annotations

from typing import Any

import polars as pl

TOTAL_GEN = "CHP_T"
FUEL_GROUPS: dict[str, tuple[str, ...]] = {
    "Põlevkivi ja põlevkiviproduktid": ("S2100_EE", "O4510_EE", "C0361_EE"),
    "Maagaas": ("G3000X3100_3200",),
    "Biomass ja biogaas": ("B51151_EE", "B5110_W_NVA", "B5300"),
    "Kivisüsi ja turvas": ("C0100", "P1120"),
    "Jäätmekütus": ("W6220_EE",),
    "Muud taastuvad": ("N9940_EE",),
}
RENEWABLE = ("B51151_EE", "B5110_W_NVA", "B5300", "N9940_EE")


def clean(df: pl.DataFrame) -> pl.DataFrame:
    """PxWeb variable codes can contain non-breaking spaces; use plain spaces."""
    return df.rename({c: c.replace("\u00a0", " ") for c in df.columns})


def chp(df: pl.DataFrame) -> list[dict[str, Any]]:
    t = df.filter(pl.col("Generaatori liik") == TOTAL_GEN).drop_nulls("value")
    out = []
    for y in sorted(t["Vaatlusperiood"].unique().to_list()):
        g = t.filter(pl.col("Vaatlusperiood") == y)
        row: dict[str, Any] = {"year": int(y)}
        for code in ("PROD_E_CHP", "PROD_H_CHP", "CAP_E", "CAP_H"):
            v = g.filter(pl.col("Näitaja") == code)["value"]
            row[code] = float(v[0]) if len(v) else None
        types = df.filter((pl.col("Vaatlusperiood") == y) & (pl.col("Näitaja") == "PROD_H_CHP"))
        row["heat_by_generator"] = {
            r["Generaatori liik"]: r["value"]
            for r in types.filter(pl.col("Generaatori liik") != TOTAL_GEN)
            .drop_nulls("value")
            .to_dicts()
        }
        out.append(row)
    return out


def fuels(df: pl.DataFrame, chp_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    t = df.filter(
        (pl.col("Generaatori liik") == TOTAL_GEN) & (pl.col("Näitaja") == "CONS_FUEL_NRG")
    ).drop_nulls("value")
    out = []
    for y in sorted(t["Vaatlusperiood"].unique().to_list()):
        g = t.filter(pl.col("Vaatlusperiood") == y)
        total = float(g["value"].sum())
        row: dict[str, Any] = {"year": int(y), "total_tj": total}
        used = 0.0
        for label, codes in FUEL_GROUPS.items():
            v = float(g.filter(pl.col("Kütuse/energia liik").is_in(codes))["value"].sum())
            row[label] = v
            used += v
        row["Muu"] = max(0.0, total - used)
        ren = float(g.filter(pl.col("Kütuse/energia liik").is_in(RENEWABLE))["value"].sum())
        row["renewable_share_pct"] = 100.0 * ren / total if total else None
        c = next((r for r in chp_rows if r["year"] == row["year"]), None)
        if c and c["PROD_E_CHP"] is not None and c["PROD_H_CHP"] is not None and total:
            # useful output (GWh x 3.6 = TJ) per fuel energy; above 1 the fuel data are incomplete
            row["output_to_fuel"] = (c["PROD_E_CHP"] + c["PROD_H_CHP"]) * 3.6 / total
        out.append(row)
    return out


def monthly(df: pl.DataFrame) -> dict[str, Any]:
    """Annual heat/electricity totals for complete years and the monthly profile of recent years."""
    t = (
        df.filter(pl.col("Näitaja") == "PROD")
        .drop_nulls("value")
        .with_columns(
            pl.col("Vaatlusperiood").str.slice(0, 4).cast(pl.Int32).alias("year"),
            pl.col("Vaatlusperiood").str.slice(5, 2).cast(pl.Int32).alias("month"),
        )
    )
    complete = (
        t.group_by("year", "Energia liik")
        .agg(n=pl.len(), total=pl.col("value").sum())
        .filter(pl.col("n") == 12)
    )
    annual: dict[int, dict[str, float]] = {}
    for r in complete.to_dicts():
        annual.setdefault(r["year"], {})[r["Energia liik"]] = r["total"]
    years_heat = sorted(y for y, v in annual.items() if "H8000" in v)
    profile = []
    for y in years_heat[-3:]:
        h = t.filter((pl.col("year") == y) & (pl.col("Energia liik") == "H8000")).sort("month")
        profile.append({"year": y, "months": h["value"].to_list()})
    last_row = t.sort("Vaatlusperiood").tail(1).to_dicts()
    return {
        "annual": [
            {
                "year": y,
                "heat_gwh": annual[y].get("H8000"),
                "electricity_gwh": annual[y].get("E7000"),
            }
            for y in sorted(annual)
        ],
        "profile": profile,
        "last_month": last_row[0]["Vaatlusperiood"] if last_row else None,
    }


def build(ke034: pl.DataFrame, ke035: pl.DataFrame, ke20: pl.DataFrame) -> dict[str, Any]:
    chp_rows = chp(clean(ke034))
    return {
        "chp": chp_rows,
        "fuels": fuels(clean(ke035), chp_rows),
        "monthly": monthly(clean(ke20)),
        "meta": {
            "interpretation": [
                "Koostootmisjaamade (KE034, KE035) ja kuise elektri- ja soojatoodangu (KE20) "
                "tabelid on Statistikaameti ametlik statistika; KE20 ei ole jaotatud tootja "
                "tüübi järgi, seega koostootmise osa kogu soojatoodangus on ligikaudne.",
                "Kütuse energia (TJ) on tabelis antud kütuseliikide kaupa; taastuvate hulka "
                "on loetud biomass, biogaas ja muud taastuvad allikad, jäätmekütus ei ole "
                "taastuvaks arvatud.",
                "Aastasummad (KE20) on arvutatud ainult aastatele, millel on kõik 12 kuud.",
                "Kui koostootmise kasulik toodang (soojus + elekter) ületab kütuse energia "
                "(suhe üle 1,2), loetakse kütuse andmed puudulikuks ja aasta jäetakse kütuse "
                "graafikult välja.",
            ]
        },
    }
