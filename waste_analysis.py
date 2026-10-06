"""Pure analysis functions for the aggregated national waste statistics.

Input is the output of ``waste_fetch`` (one row per year x ``maht_liik`` x waste type x flags x
partner country, with ``maht`` summed, ``rows`` and negative-value counts).  Every function
returns JSON-ready records.

Principles
----------
* ``maht_liik`` values are different *kinds of flow* (generation, recovery, landfilling, export,
  stock, ...).  The schema does not say whether they overlap, so they are **never added up**;
  each is shown on its own.
* The unit of ``maht`` is not in the schema and is assumed to be tonnes.
* Negative values occur (notably in generation).  Totals are net; the sum of the negative values
  is reported next to them so that corrections are visible, not silently removed.
* Only aggregates are used; no operator or facility identity is present in the input.
"""

from __future__ import annotations

from typing import Any

import polars as pl

GENERATION = "Jäätmeteke"
RECOVERY = "Taaskasutamine"
LANDFILL = "Ladestatud prügilasse"
PRETREAT = "Jäätmete sortimine või muu eeltöötlus (toimingud R12)"
UNSPECIFIED = "Määratlemata käitlemine"
HOUSEHOLD = "Saadud kodumajapidamistelt"
EXPORT = "Eksport"
IMPORT = "Import"
STOCK_START = "Laoseis aasta alguses"
STOCK_END = "Laoseis aasta lõpul"
FLOW_ORDER = [
    GENERATION,
    HOUSEHOLD,
    RECOVERY,
    PRETREAT,
    LANDFILL,
    UNSPECIFIED,
    EXPORT,
    IMPORT,
    STOCK_START,
    STOCK_END,
]
# Short Estonian titles of the European Waste Catalogue chapters (the codes come from the data;
# these labels are abbreviations written for this page and have not been checked by the owner).
CHAPTERS = {
    "01": "Maavarade kaevandamine ja töötlemine",
    "02": "Põllumajandus, toiduainete tööstus",
    "03": "Puidu- ja paberitööstus",
    "04": "Naha- ja tekstiilitööstus",
    "05": "Nafta, gaasi ja kivisöe töötlemine",
    "06": "Anorgaaniline keemia",
    "07": "Orgaaniline keemia",
    "08": "Värvid, liimid, trükivärvid",
    "09": "Fototööstus",
    "10": "Termilised protsessid (sh põlevkivituhk)",
    "11": "Metallide pinnatöötlus",
    "12": "Metallide ja plastide vormimine",
    "13": "Õli- ja vedelkütusejäätmed",
    "14": "Orgaanilised lahustid",
    "15": "Pakendid, absorbendid",
    "16": "Mujal nimetamata jäätmed",
    "17": "Ehitus- ja lammutusjäätmed",
    "18": "Tervishoid ja loomaarstiabi",
    "19": "Jäätme- ja veekäitlus",
    "20": "Olmejäätmed",
}


def clean(df: pl.DataFrame) -> pl.DataFrame:
    """Normalise types and flags; drop rows without a year or flow type."""
    return df.filter(
        pl.col("aasta").is_not_null() & pl.col("maht_liik").is_not_null()
    ).with_columns(
        pl.col("aasta").cast(pl.Int32),
        pl.col("maht").cast(pl.Float64),
        pl.col("neg_sum").fill_null(0.0).cast(pl.Float64),
    )


def coverage(df: pl.DataFrame) -> list[dict[str, Any]]:
    """Rows per year (completeness check against the server's counts is in the fetch log)."""
    return df.group_by("aasta").agg(rows=pl.col("rows").sum()).sort("aasta").to_dicts()


def flow_totals(df: pl.DataFrame) -> list[dict[str, Any]]:
    """Net amount, sum of negative values and row counts per year and flow type."""
    return (
        df.group_by("aasta", "maht_liik")
        .agg(
            tonnes=pl.col("maht").sum(),
            negative_tonnes=pl.col("neg_sum").sum(),
            rows=pl.col("rows").sum(),
            negative_rows=pl.col("neg_rows").sum(),
        )
        .sort("aasta", "maht_liik")
        .to_dicts()
    )


def by_chapter(df: pl.DataFrame, flow: str) -> list[dict[str, Any]]:
    """Net amount per year and waste-catalogue chapter (``pohigrupp``) for one flow type."""
    return (
        df.filter(pl.col("maht_liik") == flow)
        .group_by("aasta", "pohigrupp")
        .agg(tonnes=pl.col("maht").sum(), negative_tonnes=pl.col("neg_sum").sum())
        .sort("aasta", "pohigrupp")
        .to_dicts()
    )


def hazardous(df: pl.DataFrame, flow: str) -> list[dict[str, Any]]:
    """Amount flagged hazardous and its share, per year, for one flow type."""
    g = (
        df.filter(pl.col("maht_liik") == flow)
        .group_by("aasta")
        .agg(
            total=pl.col("maht").sum(),
            hazardous=pl.col("maht").filter(pl.col("ohtlik_lipp") == "Jah").sum(),
        )
        .sort("aasta")
    )
    return g.with_columns(
        share=pl.when(pl.col("total") > 0).then(pl.col("hazardous") / pl.col("total"))
    ).to_dicts()


def top_types(df: pl.DataFrame, flow: str, year: int, n: int = 12) -> list[dict[str, Any]]:
    """Largest waste types (catalogue code and name) for one flow type and year."""
    return (
        df.filter((pl.col("maht_liik") == flow) & (pl.col("aasta") == year))
        .group_by("jaatmeliik", "jaatmeliik_nimi")
        .agg(tonnes=pl.col("maht").sum())
        .sort("tonnes", descending=True)
        .head(n)
        .to_dicts()
    )


def trade_partners(df: pl.DataFrame, flow: str, n: int = 10) -> list[dict[str, Any]]:
    """Export or import per year for the ``n`` partners with the largest all-year total."""
    d = df.filter((pl.col("maht_liik") == flow) & pl.col("partner_riik_nimi").is_not_null())
    top = (
        d.group_by("partner_riik_nimi")
        .agg(t=pl.col("maht").sum())
        .sort("t", descending=True)
        .head(n)["partner_riik_nimi"]
        .to_list()
    )
    return (
        d.filter(pl.col("partner_riik_nimi").is_in(top))
        .group_by("aasta", "partner_riik_nimi")
        .agg(tonnes=pl.col("maht").sum())
        .sort("aasta", "partner_riik_nimi")
        .to_dicts()
    )


def stock_continuity(df: pl.DataFrame) -> list[dict[str, Any]]:
    """Closing stock of year Y against opening stock of Y+1 (should match if both are complete)."""
    s = (
        df.filter(pl.col("maht_liik").is_in([STOCK_START, STOCK_END]))
        .group_by("aasta", "maht_liik")
        .agg(t=pl.col("maht").sum())
    )
    end = {r["aasta"]: r["t"] for r in s.filter(pl.col("maht_liik") == STOCK_END).to_dicts()}
    start = {r["aasta"]: r["t"] for r in s.filter(pl.col("maht_liik") == STOCK_START).to_dicts()}
    return [
        {
            "aasta": y,
            "closing": end[y],
            "next_opening": start[y + 1],
            "ratio": start[y + 1] / end[y] if end[y] else None,
        }
        for y in sorted(end)
        if y + 1 in start
    ]


def chapter_names(df: pl.DataFrame) -> dict[str, str]:
    """Group names as reported in the data (longest observed per code)."""
    rows = df.filter(pl.col("pohigrupp_nimi").is_not_null()).select("pohigrupp", "pohigrupp_nimi")
    return {
        r["pohigrupp"]: r["pohigrupp_nimi"]
        for r in rows.unique()
        .sort("pohigrupp", pl.col("pohigrupp_nimi").str.len_chars())
        .to_dicts()
    }


# Waste streams: a stream is a subset of rows picked by catalogue code or by a Jah/Ei flag.
# The streams are *not* additive (a row can belong to several), and flows within a stream are
# shown side by side, never summed or divided (overlap of flows is not documented).
STREAM_FLOWS = (GENERATION, RECOVERY, LANDFILL, HOUSEHOLD, EXPORT, IMPORT)
STREAMS: dict[str, tuple[str, pl.Expr]] = {
    "municipal": ("Olmejäätmed (peatükk 20)", pl.col("pohigrupp") == "20"),
    "packaging": ("Pakendijäätmed (liik 15 01)", pl.col("jaatmeliik").str.starts_with("15 01")),
    "bio": ("Biojäätmed (märge)", pl.col("biojaatmed_lipp") == "Jah"),
    "sludge": ("Reoveesetted (märge)", pl.col("reoveesetted_lipp") == "Jah"),
    "metal": ("Metallijäätmed (märge)", pl.col("metallijaatmed_lipp") == "Jah"),
    "problem": ("Probleemtooted (märge)", pl.col("probleemtooted_lipp") == "Jah"),
}


def flag_values(df: pl.DataFrame) -> dict[str, list[dict[str, Any]]]:
    """Distinct values of each flag column with row counts (to verify the 'Jah' convention)."""
    cols = (
        "ohtlik_lipp",
        "biojaatmed_lipp",
        "reoveesetted_lipp",
        "metallijaatmed_lipp",
        "probleemtooted_lipp",
    )
    return {
        c: df.group_by(c).agg(rows=pl.col("rows").sum()).sort("rows", descending=True).to_dicts()
        for c in cols
        if c in df.columns
    }


def streams(df: pl.DataFrame, latest: int) -> dict[str, Any]:
    """Per stream: flows by year (net, negative tonnes) and the largest types of the latest year."""
    out: dict[str, Any] = {}
    for key, (label, pred) in STREAMS.items():
        sub = df.filter(pred)
        flows = {
            f: sub.filter(pl.col("maht_liik") == f)
            .group_by("aasta")
            .agg(tonnes=pl.col("maht").sum(), negative_tonnes=pl.col("neg_sum").sum())
            .sort("aasta")
            .to_dicts()
            for f in STREAM_FLOWS
        }
        top = (
            sub.filter((pl.col("maht_liik") == GENERATION) & (pl.col("aasta") == latest))
            .group_by("jaatmeliik", "jaatmeliik_nimi")
            .agg(tonnes=pl.col("maht").sum())
            .sort("tonnes", descending=True)
            .head(8)
            .to_dicts()
        )
        out[key] = {
            "label": label,
            "rows": int(sub["rows"].sum() or 0),
            "flows": flows,
            "top_generation": top,
        }
    return out
