"""Material flows, waste and the circular material use rate against economic output.

Inputs (long Parquet from ``statee_fetch.py`` / ``eurostat_fetch.py``):

* ``KK99`` material flow indicators (domestic extraction, DMC, resource productivity);
* ``KK610`` waste balance by waste type (generation, treatment, landfill);
* ``KK068`` waste generation by waste type and activity (every second year);
* ``RAA0012`` GDP (chain-linked, reference year 2020; annual totals, not seasonally adjusted);
* ``cei_srm030`` Eurostat circular material use rate (Estonia and EU27).

Everything is derived from the published tables.  Waste quantities are assumed to be in tonnes
(the PxWeb tables carry no unit; the order of magnitude is reported in ``checks``).  Waste
generation is dominated by mining and energy-sector (oil shale) waste, so totals are shown with and
without those chapters.  Recovery includes all recovery operations (energy recovery is not
separable) and quantities treated in a year can include stocks from earlier years.
"""

from __future__ import annotations

import re
from typing import Any

import polars as pl

CHAPTER = re.compile(r"^(\d{2})0000 ")
MINING_ENERGY = ("01", "10")  # chapters 01 (mining) and 10 (thermal processes: ash, slag)
KK99_ITEMS = {
    "2": "extraction",
    "9": "dmc",
    "10": "dmc_per_capita",
    "11": "resource_productivity",
    "14": "material_intensity",
}


def pivot_values(df: pl.DataFrame, key: str, code: str, year: str = "Aasta") -> dict[int, float]:
    t = df.filter(pl.col(key) == code).drop_nulls("value")
    return {int(y): float(v) for y, v in zip(t[year].to_list(), t["value"].to_list(), strict=True)}


def kk99(df: pl.DataFrame) -> list[dict[str, Any]]:
    cols = {name: pivot_values(df, "Näitaja", code) for code, name in KK99_ITEMS.items()}
    years = sorted(set().union(*(set(v) for v in cols.values())))
    return [{"year": y, **{n: cols[n].get(y) for n in cols}} for y in years]


def gdp(df: pl.DataFrame) -> dict[int, float]:
    """Annual real GDP, million EUR (reference year 2020), not seasonally adjusted."""
    t = df.filter((pl.col("Kvartal") == "1") & (pl.col("Sesoonne korrigeerimine") == "1"))
    return pivot_values(t, "Näitaja", "2")


def chapters(waste: pl.DataFrame, texts: dict[str, str]) -> dict[str, str]:
    """Waste-type code -> two-digit chapter for the chapter rows ('NN0000 ...')."""
    out = {}
    for code in waste["Jäätmeliik"].unique().to_list():
        m = CHAPTER.match(texts.get(code, ""))
        if m:
            out[code] = m.group(1)
    return out


def waste_series(
    waste: pl.DataFrame, chapter_of: dict[str, str]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Generation, recovery and landfill for all waste and for waste without chapters 01 and 10."""
    gen = waste.filter(pl.col("Näitaja") == "3").drop_nulls("value")
    drop = {c for c, ch in chapter_of.items() if ch in MINING_ENERGY}
    total = pivot_values(gen, "Jäätmeliik", "1")
    chap_total = sum_by_year(gen, set(chapter_of))
    rows = []
    for y in sorted(total):
        g = total[y]
        removed = sum_by_year(gen, drop).get(y, 0.0)
        row: dict[str, Any] = {"year": y, "generated": g, "mining_energy": removed}
        row["generated_other"] = g - removed
        for code, name in (
            ("7", "recovery"),
            ("8", "disposal"),
            ("9", "landfilled"),
            ("6", "treated"),
        ):
            t = waste.filter(
                (pl.col("Näitaja") == code) & (pl.col("Jäätmeliik") == "1")
            ).drop_nulls("value")
            row[name] = dict(
                zip(t["Aasta"].cast(pl.Int32).to_list(), t["value"].to_list(), strict=True)
            ).get(y)
            to = waste.filter(
                (pl.col("Näitaja") == code) & pl.col("Jäätmeliik").is_in(sorted(drop))
            ).drop_nulls("value")
            row[name + "_mining_energy"] = float(
                to.filter(pl.col("Aasta") == str(y))["value"].sum()
            )
        rows.append(row)
    checks = {
        "chapter_sum_share_of_total": (
            {y: chap_total.get(y, 0.0) / total[y] for y in total if total[y]}
        ),
    }
    return rows, checks


def sum_by_year(gen: pl.DataFrame, codes: set[str]) -> dict[int, float]:
    t = gen.filter(pl.col("Jäätmeliik").is_in(sorted(codes)))
    s = t.group_by("Aasta").agg(v=pl.col("value").sum())
    return {int(y): float(v) for y, v in zip(s["Aasta"].to_list(), s["v"].to_list(), strict=True)}


def by_activity(df: pl.DataFrame, texts: dict[str, str]) -> list[dict[str, Any]]:
    t = df.filter(pl.col("Jäätmeliik") == "1").drop_nulls("value")
    out = []
    for y in sorted(t["Aasta"].unique().to_list()):
        g = t.filter(pl.col("Aasta") == y)
        total = float(g.filter(pl.col("Tegevusala (EMTAK 2008)") == "1")["value"].sum())
        rows = [
            {
                "name": texts.get(r["Tegevusala (EMTAK 2008)"], r["Tegevusala (EMTAK 2008)"]),
                "value": r["value"],
            }
            for r in g.filter(pl.col("Tegevusala (EMTAK 2008)") != "1").to_dicts()
        ]
        out.append({"year": int(y), "total": total, "activities": rows})
    return out


def cmu(df: pl.DataFrame) -> list[dict[str, Any]]:
    t = df.filter(pl.col("unit") == "PC").drop_nulls("value")
    years = sorted(t["time"].unique().to_list())
    out = []
    for y in years:
        g = t.filter(pl.col("time") == y)
        row: dict[str, Any] = {"year": int(y)}
        for geo, key in (("EE", "ee"), ("EU27_2020", "eu")):
            v = g.filter(pl.col("geo") == geo)["value"]
            row[key] = float(v[0]) if len(v) else None
        out.append(row)
    return out


def index_series(series: dict[int, float], base_year: int) -> dict[int, float]:
    base = series.get(base_year)
    return {y: 100.0 * v / base for y, v in series.items()} if base else {}


def decoupling(
    mat: list[dict[str, Any]], gdp_s: dict[int, float], waste: list[dict[str, Any]]
) -> dict[str, Any]:
    """Indices (first year with all series = 100) of real GDP, DMC and waste generation."""
    dmc = {r["year"]: r["dmc"] for r in mat if r["dmc"] is not None}
    wt = {r["year"]: r["generated"] for r in waste}
    wo = {r["year"]: r["generated_other"] for r in waste}
    common = sorted(set(gdp_s) & set(dmc) & set(wt))
    if not common:
        return {"base_year": None, "years": []}
    base = common[0]
    ix = {
        "gdp": index_series(gdp_s, base),
        "dmc": index_series(dmc, base),
        "waste": index_series(wt, base),
        "waste_other": index_series(wo, base),
    }
    return {
        "base_year": base,
        "years": [{"year": y, **{k: ix[k].get(y) for k in ix}} for y in common],
    }


def build(
    kk99_df: pl.DataFrame,
    kk610_df: pl.DataFrame,
    kk068_df: pl.DataFrame,
    gdp_df: pl.DataFrame,
    cmu_df: pl.DataFrame,
    texts: dict[str, dict[str, str]],
    generated: str,
) -> dict[str, Any]:
    chapter_of = chapters(kk610_df, texts["KK610_waste"])
    waste, wchecks = waste_series(kk610_df, chapter_of)
    mat = kk99(kk99_df)
    g = gdp(gdp_df)
    return {
        "meta": {
            "generated_utc": generated,
            "source": "Statistikaamet (andmed.stat.ee): KK99, KK610, KK068, RAA0012; "
            "Eurostat: cei_srm030",
            "interpretation": [
                "Jäätmekogused on eeldatud tonnides (PxWeb tabelis ühikut ei ole; suurusjärk on "
                "kontrollide all). Jäätmetekke kogusummas võivad domineerida mäetööstuse "
                "(jäätmenimistu peatükk 01) ja termiliste protsesside jäätmed (peatükk 10); "
                "seetõttu näidatakse kogusummat koos ja ilma nende peatükkideta (domineerimine "
                "on kontrollide all).",
                "SKP on aheldatud väärtus (referentsaasta 2020), aasta kokku, sesoonselt "
                "korrigeerimata; DMC (kodumaine materjalitarbimine) on Statistikaameti "
                "materjalivoo arvepidamisest.",
                "Taaskasutus hõlmab kõiki taaskasutustoiminguid (energiakasutus ei ole eraldatav); "
                "aastas töödeldud kogus võib sisaldada varasemate aastate varusid.",
                "Ringleva materjali määr on Eurostati arvutatud näitaja (cei_srm030, protsent); "
                "Statistikaameti tabelitest seda arvutada ei saa.",
                "Lahtisidumise (decoupling) hinnang on kirjeldav (indeksite võrdlus), mitte "
                "põhjuslik; SKP struktuuri muutus ja kaubandus mõjutavad indekseid.",
                "Litsents ja viitamise nõue (Statistikaamet, Eurostat) tuleb enne taaskasutust "
                "üle kontrollida.",
            ],
        },
        "materials": mat,
        "gdp": [{"year": y, "gdp_meur": v} for y, v in sorted(g.items())],
        "waste": waste,
        "decoupling": decoupling(mat, g, waste),
        "activity": by_activity(kk068_df, texts["KK068_activity"]),
        "cmu": cmu(cmu_df),
        "checks": {
            **wchecks,
            "waste_total_latest": waste[-1]["generated"] if waste else None,
            "dmc_latest_kt": next((r["dmc"] for r in reversed(mat) if r["dmc"] is not None), None),
        },
    }
