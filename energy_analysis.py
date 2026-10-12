"""Estonian energy balance, electricity production and capacity (Statistics Estonia, PxWeb).

Inputs are the long Parquet files written by ``statee_fetch.py``:

* ``KE0240`` energy balance by fuel/energy type in TJ (Eurostat methodology): variables
  ``Aasta``, ``Näitaja`` (balance item), ``Kütuse/energia liik`` (product), ``value``;
* ``KE033`` electricity plants: production by fuel (GWh) and fuel use;
* ``KE032`` installed capacity of power plants (MW).

Everything is derived from the published tables; shares are computed here, not published ones.
Interpretation choices (repeated in the output ``meta``):

* The balance sign convention of exports and stock change is detected from the identity
  ``GAE = PPRD + IMP -/+ EXP -/+ STK_CHG`` (the variant with the smallest residual is used and the
  residual is reported).
* "Renewable" products of the balance are hydro, wind, solar, solid biofuels, biogas, liquid
  biofuels and renewable municipal waste; the share is **not** the official SHARES indicator
  (no heat pumps, no normalisation, no transport weighting).
* Electricity and heat in the balance are net of trade, so shares of gross available energy include
  the electricity trade balance.
"""

from __future__ import annotations

from typing import Any

import polars as pl

TOTAL = "TOTAL"
RENEWABLE = (
    "RA100",
    "RA300",
    "RA420",
    "R5110-5150_W6000RI",
    "R5300",
    "W6210",
    "R5210P",
    "R5210B",
    "R5220P",
    "R5220B",
)
PRODUCTION_GROUPS: dict[str, tuple[str, ...]] = {
    "Põlevkivi": ("S2000",),
    "Turvas": ("P1100", "P1200"),
    "Biomass ja biogaas": ("R5110-5150_W6000RI", "R5300", "W6210", "R5210P", "R5210B", "R5220P"),
    "Tuul, päike, hüdro": ("RA100", "RA300", "RA420"),
}
FINAL_SECTORS = {
    "FC_IND_E": "Tööstus",
    "FC_TRA_E": "Transport",
    "FC_OTH_HH_E": "Kodumajapidamised",
    "FC_OTH_CP_E": "Äri- ja avalik sektor",
}
ELECTRICITY_GROUPS: dict[str, tuple[str, ...]] = {
    "Põlevkivi ja põlevkiviproduktid": ("S2100_EE", "O4510_EE", "C0361_EE"),
    "Tuul": ("WIND",),
    "Päike": ("SOLAR",),
    "Hüdro": ("HYDRO",),
    "Biomass, biogaas, muu taastuv": ("B5115_EE", "B5300", "N9940_EE"),
    "Maagaas": ("G3000",),
}
ELECTRICITY_RENEWABLE = ("WIND", "SOLAR", "HYDRO", "B5115_EE", "B5300", "N9940_EE")


def balance(df: pl.DataFrame) -> pl.DataFrame:
    """Rename the PxWeb columns to year, item, product, value."""
    return df.rename(
        {"Aasta": "year", "Näitaja": "item", "Kütuse/energia liik": "product"}
    ).with_columns(pl.col("year").cast(pl.Int32))


def item_series(b: pl.DataFrame, item: str, product: str = TOTAL) -> dict[int, float]:
    t = b.filter((pl.col("item") == item) & (pl.col("product") == product)).drop_nulls("value")
    return dict(zip(t["year"].to_list(), t["value"].to_list(), strict=True))


def detect_signs(b: pl.DataFrame) -> dict[str, Any]:
    """Choose the export / stock-change signs that make GAE = PPRD + IMP + s*EXP + s*STK."""
    s = {k: item_series(b, k) for k in ("PPRD", "IMP", "EXP", "STK_CHG", "GAE")}
    years = sorted(set.intersection(*(set(v) for v in s.values())))
    best: dict[str, Any] | None = None
    for se in (-1, 1):
        for st in (-1, 1):
            resid = sum(
                abs(
                    s["GAE"][y]
                    - (s["PPRD"][y] + s["IMP"][y] + se * s["EXP"][y] + st * s["STK_CHG"][y])
                )
                for y in years
            )
            scale = sum(abs(s["GAE"][y]) for y in years) or 1.0
            cand = {"exp": se, "stk": st, "residual_share": resid / scale}
            if best is None or cand["residual_share"] < best["residual_share"]:
                best = cand
    return best or {"exp": -1, "stk": 1, "residual_share": None}


def balance_series(b: pl.DataFrame, signs: dict[str, Any]) -> list[dict[str, Any]]:
    keys = ("PPRD", "IMP", "EXP", "STK_CHG", "GAE", "INTMARB", "GIC", "NRGSUP", "FC_E")
    s = {k: item_series(b, k) for k in keys}
    out = []
    for y in sorted(s["GAE"]):
        gae = s["GAE"][y]
        pprd, imp = s["PPRD"].get(y), s["IMP"].get(y)
        exp = s["EXP"].get(y)
        net = None if imp is None or exp is None else imp + signs["exp"] * exp
        out.append(
            {
                "year": y,
                "production": pprd,
                "imports": imp,
                "exports": exp,
                "net_imports": net,
                "gae": gae,
                "gic": s["GIC"].get(y),
                "final": s["FC_E"].get(y),
                "dependency_pct": None if net is None or not gae else 100.0 * net / gae,
            }
        )
    return out


def production(b: pl.DataFrame) -> list[dict[str, Any]]:
    """Primary energy production by group (TJ)."""
    p = b.filter((pl.col("item") == "PPRD") & (pl.col("product") != TOTAL)).drop_nulls("value")
    total = item_series(b, "PPRD")
    out = []
    for y in sorted(total):
        row: dict[str, Any] = {"year": y, "total": total[y]}
        used = 0.0
        for g, codes in PRODUCTION_GROUPS.items():
            v = float(
                p.filter((pl.col("year") == y) & pl.col("product").is_in(codes))["value"].sum()
            )
            row[g] = v
            used += v
        row["Muu"] = max(0.0, total[y] - used)
        row["renewable"] = float(
            p.filter((pl.col("year") == y) & pl.col("product").is_in(RENEWABLE))["value"].sum()
        )
        out.append(row)
    return out


def renewable_share_gae(b: pl.DataFrame) -> list[dict[str, Any]]:
    """Renewable products in gross available energy as a share of the total (TJ)."""
    t = b.filter((pl.col("item") == "GAE") & pl.col("product").is_in([*RENEWABLE, TOTAL]))
    out = []
    for y in sorted(t["year"].unique().to_list()):
        g = t.filter(pl.col("year") == y)
        tot = g.filter(pl.col("product") == TOTAL)["value"].sum()
        ren = g.filter(pl.col("product") != TOTAL)["value"].sum()
        if tot:
            out.append(
                {
                    "year": y,
                    "renewable_tj": float(ren),
                    "total_tj": float(tot),
                    "share_pct": 100.0 * float(ren) / float(tot),
                }
            )
    return out


def final_consumption(b: pl.DataFrame) -> list[dict[str, Any]]:
    t = b.filter(
        (pl.col("product") == TOTAL) & pl.col("item").is_in(list(FINAL_SECTORS))
    ).drop_nulls("value")
    fc = item_series(b, "FC_E")
    out = []
    for y in sorted(fc):
        row: dict[str, Any] = {"year": y, "total": fc[y]}
        for code, label in FINAL_SECTORS.items():
            v = t.filter((pl.col("year") == y) & (pl.col("item") == code))["value"]
            row[label] = float(v.sum()) if len(v) else None
        out.append(row)
    return out


def electricity(e: pl.DataFrame) -> list[dict[str, Any]]:
    """Electricity production by source group (GWh), all power plants."""
    d = e.rename({"Aasta": "year", "Näitaja": "item", "Kütuse/energia liik": "product"})
    d = d.filter(
        (pl.col("item") == "PROD_E") & (pl.col("Elektritootja liik") == "_T")
    ).with_columns(pl.col("year").cast(pl.Int32))
    out = []
    for y in sorted(d["year"].unique().to_list()):
        g = d.filter(pl.col("year") == y).drop_nulls("value")
        tot = g.filter(pl.col("product") == "_T")["value"]
        if not len(tot):
            continue
        row: dict[str, Any] = {"year": y, "total": float(tot.sum())}
        used = 0.0
        for label, codes in ELECTRICITY_GROUPS.items():
            v = float(g.filter(pl.col("product").is_in(codes))["value"].sum())
            row[label] = v
            used += v
        row["Muu"] = max(0.0, row["total"] - used)
        ren = float(g.filter(pl.col("product").is_in(ELECTRICITY_RENEWABLE))["value"].sum())
        row["renewable_share_pct"] = 100.0 * ren / row["total"] if row["total"] else None
        out.append(row)
    return out


def capacity(c: pl.DataFrame) -> list[dict[str, Any]]:
    d = c.filter(pl.col("Elektritootja liik") == "_T").drop_nulls("value")
    out = []
    for y in sorted(d["Vaatlusperiood"].unique().to_list()):
        g = d.filter(pl.col("Vaatlusperiood") == y)
        row: dict[str, Any] = {"year": int(y)}
        for code in g["Näitaja"].unique().to_list():
            row[code] = float(g.filter(pl.col("Näitaja") == code)["value"].sum())
        out.append(row)
    return out


def build(b0: pl.DataFrame, e: pl.DataFrame, c: pl.DataFrame, generated: str) -> dict[str, Any]:
    b = balance(b0)
    signs = detect_signs(b)
    return {
        "meta": {
            "generated_utc": generated,
            "source": "Statistikaamet (andmed.stat.ee, PxWeb): KE0240, KE033, KE032",
            "interpretation": [
                "Energiabilanss on Eurostati metoodikaga (TJ); ekspordi ja varude muutuse märk "
                "tuvastatakse samasusest GAE = PPRD + IMP ± EXP ± STK ja jääk on kontrollides.",
                "Taastuvad tooted: hüdro, tuul, päike, tahked biokütused, biogaas, vedelad "
                "biokütused ja taastuvast toorainest olmejäätmed. Osakaal on arvutatud "
                "energiabilansist ega ole ametlik SHARES-osakaal (soojuspumbad, normaliseerimine "
                "ja transpordi kaalumine puuduvad).",
                "Elektri ja soojuse tooted on bilansis kaubanduse netona; GAE osakaal sisaldab "
                "seetõttu elektrikaubanduse saldot.",
                "Elektritootmine jaguneb kütuse järgi tabelist KE033 (kõik elektrijaamad); "
                "jäätmekütust ei loeta taastuvaks, sest taastuv osa ei ole tabelis eraldatud.",
                "Litsents (Statistikaameti avaandmed) ja viitamise nõue tuleb enne taaskasutust "
                "üle kontrollida; andmed on ametlik statistika, mitte Keskkonnaagentuuri mõõtmine.",
            ],
        },
        "signs": signs,
        "balance": balance_series(b, signs),
        "production": production(b),
        "renewable_gae": renewable_share_gae(b),
        "final": final_consumption(b),
        "electricity": electricity(e),
        "capacity": capacity(c),
        "checks": {"balance_rows": b.height, "electricity_rows": e.height},
    }
