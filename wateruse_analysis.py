"""Water use, abstraction, waste-water discharge and sewage agglomerations (national aggregates).

Sources are permit-holder water reports (tables ``t_awtabel*_curr``: only the latest reporting
years are in the API) and registers.  Everything is summed over reporting units; no names are used.

Interpretation choices (repeated in the output ``meta``):

* Volumes are m3 per year (column descriptions), loads t per year, concentrations mg/l (assumed).
* Reporting years are few (the tables hold only recent years) and the number of reports differs
  by year, so year-to-year changes can reflect reporting, not use.
* Cooling water (``jahutus``) is huge and mostly surface/sea water; it is shown separately.
* Compliance = any quarterly concentration above the permitted limit among outlets that state a
  limit; concentrations are partly *calculated* (``arvutusviis``), not measured.
* Groundwater reserves are not compared with abstraction: the abstraction table has no link to
  the reserve deposit.
"""

from __future__ import annotations

from typing import Any

import polars as pl

SECTORS = ("olme", "toostus", "jahutus", "energeetika", "pollumajandus", "niisutus", "muu")
MONTHS = (
    "jaanuar",
    "veebruar",
    "marts",
    "aprill",
    "mai",
    "juuni",
    "juuli",
    "august",
    "september",
    "oktoober",
    "november",
    "detsember",
)
LOADS = {
    "bht7kogus": "BHT7",
    "helkogus": "Heljum",
    "khtkogus": "KHT",
    "pkogus": "Üldfosfor",
    "nyldkogus": "Üldlämmastik",
}
POLLUTANTS = {
    "bht7": ("bht7kontsentratsioonlubatud", "bht7kontsentratsioon{q}kv", "BHT7"),
    "helj": ("helkontsentratsioonlubatud", "helkontsentratsioon{q}kv", "Heljum"),
    "kht": ("khtkontsentratsioonlubatud", "khtkontsentratsioon{q}kv", "KHT"),
    "p": ("pkontsentratsioonlubatud", "pkontsentratsioon{q}kv", "Üldfosfor"),
    "n": ("nyldkontsentratsioonlubatud", "nyldkontsentratsioon{q}kv", "Üldlämmastik"),
}


def clean_water_types(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns(pl.col("veeliik").fill_null("määramata"))


def use_by_type(use: pl.DataFrame) -> list[dict[str, Any]]:
    """Total declared water use (m3) per year and water type, with number of reports."""
    df = clean_water_types(use)
    out = (
        df.group_by("aruandeaasta", "veeliik")
        .agg(m3=pl.col("kokku").sum(), reports=pl.col("annual_report_id").n_unique(), rows=pl.len())
        .sort("aruandeaasta", "m3", descending=[False, True])
    )
    return out.to_dicts()


def use_by_sector(use: pl.DataFrame) -> list[dict[str, Any]]:
    """Declared use per year and sector (m3); sectors are optional columns, nulls count as zero."""
    rows = []
    for (year,), g in use.group_by("aruandeaasta", maintain_order=True):
        entry: dict[str, Any] = {
            "year": int(year),
            "kokku": g["kokku"].sum(),
            "reports": g["annual_report_id"].n_unique(),
        }
        for s in SECTORS:
            entry[s] = g[s].sum()
        entry["sectors_sum"] = sum(entry[s] or 0 for s in SECTORS)
        entry["veekadu"] = g["veekadu"].sum()
        rows.append(entry)
    return sorted(rows, key=lambda r: r["year"])


def sector_tiling(use: pl.DataFrame) -> dict[str, Any]:
    """Do the sector columns add up to ``kokku`` per row (within 1%)?"""
    df = use.filter(pl.col("kokku").is_not_null() & (pl.col("kokku") > 0))
    parts = sum((pl.col(s).fill_null(0) for s in SECTORS), start=pl.lit(0.0))
    df = df.with_columns(parts.alias("parts"))
    ok = df.filter(((pl.col("parts") - pl.col("kokku")).abs() / pl.col("kokku")) <= 0.01)
    return {
        "rows": df.height,
        "within_1pct": ok.height,
        "share": ok.height / df.height if df.height else None,
    }


def duplicates(use: pl.DataFrame) -> dict[str, Any]:
    key = ["annual_report_id", "aruandeaasta", "kasutuspiirkond", "veeliik"]
    d = use.group_by(key).agg(n=pl.len())
    return {"groups": d.height, "groups_with_multiple_rows": int((d["n"] > 1).sum())}


def abstraction(gw: pl.DataFrame, sw: pl.DataFrame) -> dict[str, Any]:
    """Annual abstraction totals (m3) and monthly profile of groundwater abstraction per year."""
    out: dict[str, Any] = {"groundwater": [], "surface": [], "monthly_groundwater": []}
    for label, df in (("groundwater", gw), ("surface", sw)):
        g = (
            df.group_by("aruandeaasta")
            .agg(
                m3=pl.col("aastakokku").sum().cast(pl.Float64),
                reports=pl.col("annual_report_id").n_unique(),
                rows=pl.len(),
            )
            .sort("aruandeaasta")
        )
        out[label] = [
            {"year": r["aruandeaasta"], **{k: r[k] for k in ("m3", "reports", "rows")}}
            for r in g.to_dicts()
        ]
    for (year,), g in gw.group_by("aruandeaasta", maintain_order=True):
        m = [float(g[c].sum() or 0.0) for c in MONTHS]
        out["monthly_groundwater"].append({"year": int(year), "months": m, "total": sum(m)})
    out["monthly_groundwater"].sort(key=lambda r: r["year"])
    return out


def discharge(dis: pl.DataFrame) -> dict[str, Any]:
    """National discharge volume and loads per year, measured-share and outlet compliance."""
    years = []
    for (year,), g in dis.group_by("aruandeaasta", maintain_order=True):
        entry: dict[str, Any] = {
            "year": int(year),
            "outlets": g["valjalaskmekood"].n_unique(),
            "volume_m3": g["heitveehulkaastas"].sum(),
            "calculated_share": float((g["arvutusviis"] == "Arvutuslik").sum()) / g.height
            if g.height
            else None,
        }
        for col in LOADS:
            entry[col] = g[col].sum()
        years.append(entry)
    years.sort(key=lambda r: r["year"])
    compliance: list[dict[str, Any]] = []
    for key, (limit_col, conc_tpl, label) in POLLUTANTS.items():
        conc_cols = [conc_tpl.format(q=q) for q in (1, 2, 3, 4)]
        for (year,), g in dis.group_by("aruandeaasta", maintain_order=True):
            g = g.filter(pl.col(limit_col).is_not_null() & (pl.col(limit_col) > 0))
            if not g.height:
                continue
            over = g.filter(pl.max_horizontal(*[pl.col(c) for c in conc_cols]) > pl.col(limit_col))
            compliance.append(
                {
                    "pollutant": label,
                    "key": key,
                    "year": int(year),
                    "with_limit": g.height,
                    "over_limit": over.height,
                }
            )
    compliance.sort(key=lambda r: (r["key"], r["year"]))
    return {"years": years, "compliance": compliance}


def agglomerations(ra: pl.DataFrame) -> dict[str, Any]:
    """Valid sewage agglomerations by size class: number, population, load (pe)."""
    v = ra.filter(pl.col("keht_staatus") == "Kehtiv")
    by = (
        v.group_by("tyyp_selg")
        .agg(
            n=pl.len(),
            residents=pl.col("elanikke").sum(),
            load_pe=pl.col("koormus").sum(),
            area_ha=pl.col("pindala").sum(),
        )
        .sort("n")
    )
    return {
        "valid": v.height,
        "by_size": by.to_dicts(),
        "load_pe_total": v["koormus"].sum(),
        "residents_total": v["elanikke"].sum(),
    }


def reserves(res: pl.DataFrame) -> dict[str, Any]:
    """Approved groundwater reserves (valid records) by aquifer index: sum of category T1 'olme'."""
    v = res.filter(pl.col("keht_staatus") == "Kehtiv")
    by = (
        v.group_by("geol_indeks")
        .agg(
            deposits=pl.len(),
            t1_olme=pl.col("varu_t1_olme").sum(),
            n_with_t1=pl.col("varu_t1_olme").is_not_null().sum(),
        )
        .sort("t1_olme", descending=True, nulls_last=True)
    )
    return {
        "valid_records": v.height,
        "all_records": res.height,
        "t1_olme_total": v["varu_t1_olme"].sum(),
        "by_aquifer": [r for r in by.to_dicts() if r["geol_indeks"]][:12],
    }


def abstraction_vs_use(
    use: pl.DataFrame, gw: pl.DataFrame, sw: pl.DataFrame
) -> list[dict[str, Any]]:
    """Does groundwater + surface abstraction equal the declared use total per year?"""
    out = []
    for (year,), g in use.group_by("aruandeaasta", maintain_order=True):
        a = sum(
            float(df.filter(pl.col("aruandeaasta") == year)["aastakokku"].sum() or 0)
            for df in (gw, sw)
        )
        total = float(g["kokku"].sum() or 0)
        out.append(
            {
                "year": int(year),
                "use_total": total,
                "abstraction_total": a,
                "ratio": a / total if total else None,
            }
        )
    return sorted(out, key=lambda r: r["year"])
