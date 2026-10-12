"""Groundwater abstraction against approved reserves, per groundwater body.

Abstraction reports (``t_awtabel002_01_curr``, m3 per year per intake) are linked to the intake
register by the KKR code (``f_veehaarded.kkr_kood``, all abstraction codes match) and from there
to the boreholes of the intake, which carry the groundwater body (``pohjaveekogum_id``).  An
intake whose boreholes lie in one body is allocated to it; intakes spanning several bodies, or
without a borehole body, are reported separately and never split.  Approved reserves are the
sum of category T1 "olme" over *valid* reserve records of a body.  Units are assumed: abstraction
m3 per year, reserves m3 per day (not confirmed); the comparison is abstraction / 365 against the
reserve.  Reserves cover approved deposits only, so a ratio above 1 is *not* over-abstraction.
Only aggregates and body codes are produced (no names, no intake codes).
"""

from __future__ import annotations

from typing import Any

import polars as pl

DAYS = 365.0
KOG = {"1": "Hea", "2": "Ohustatud", "3": "Halb"}


def norm(col: str) -> pl.Expr:
    return pl.col(col).cast(pl.Utf8).str.strip_chars().str.to_uppercase()


def intake_bodies(intakes: pl.DataFrame, boreholes: pl.DataFrame) -> pl.DataFrame:
    """Per intake (by normalised KKR code): number of distinct bodies and the body if unique."""
    bh = boreholes.filter(
        pl.col("pohjaveekogum_id").is_not_null() & (pl.col("keht_staatus") == "Kehtiv")
    )
    per_id = bh.group_by("veehaare_id").agg(
        bodies=pl.col("pohjaveekogum_id").n_unique(), body=pl.col("pohjaveekogum_id").first()
    )
    k = intakes.select(pl.col("id"), norm("kkr_kood").alias("code")).filter(
        pl.col("code").is_not_null()
    )
    j = k.join(per_id, left_on="id", right_on="veehaare_id", how="left")
    return j.group_by("code").agg(
        intakes=pl.len(),
        bodies=pl.col("bodies").max().fill_null(0),
        body=pl.col("body").first(),
        # a code shared by several intakes is ambiguous unless all agree on one body
        body_n=pl.col("body").drop_nulls().n_unique(),
    )


def allocate(gw: pl.DataFrame, ib: pl.DataFrame) -> pl.DataFrame:
    """Abstraction rows with a ``class`` (single, multiple, none) and the body for singles."""
    g = gw.with_columns(norm("veehaardekood").alias("code")).join(ib, on="code", how="left")
    cls = (
        pl.when(pl.col("body_n").is_null() | (pl.col("body_n") == 0))
        .then(pl.lit("none"))
        .when((pl.col("bodies") > 1) | (pl.col("body_n") > 1))
        .then(pl.lit("multiple"))
        .otherwise(pl.lit("single"))
    )
    return g.with_columns(cls.alias("class"))


def reserve_by_body(res: pl.DataFrame) -> pl.DataFrame:
    return (
        res.filter((pl.col("keht_staatus") == "Kehtiv") & pl.col("pohjaveekogum_id").is_not_null())
        .group_by("pohjaveekogum_id")
        .agg(
            deposits=pl.len(),
            t1_olme=pl.col("varu_t1_olme").sum(),
            n_with_t1=pl.col("varu_t1_olme").is_not_null().sum(),
        )
    )


def latest_status(states: pl.DataFrame) -> pl.DataFrame:
    """Latest assessment per groundwater body (the status table has one row per body and year)."""
    return (
        states.sort("aasta", "muut_aeg", nulls_last=False)
        .group_by("pohjaveekogum_id")
        .agg(
            kood=pl.col("kood").last(),
            seis_kog=pl.col("seis_kog").last(),
            aasta=pl.col("aasta").last(),
        )
    )


def shares(g: pl.DataFrame) -> list[dict[str, Any]]:
    out = []
    for (year,), t in g.group_by("aruandeaasta", maintain_order=True):
        total = float(t["aastakokku"].sum() or 0.0)
        row: dict[str, Any] = {"year": int(year), "m3": total, "rows": t.height}
        for c in ("single", "multiple", "none"):
            m = float(t.filter(pl.col("class") == c)["aastakokku"].sum() or 0.0)
            row[c] = m / total if total else None
        out.append(row)
    return sorted(out, key=lambda r: r["year"])


def by_body(g: pl.DataFrame, year: int, res: pl.DataFrame, st: pl.DataFrame) -> dict[str, Any]:
    a = (
        g.filter((pl.col("aruandeaasta") == year) & (pl.col("class") == "single"))
        .group_by("body")
        .agg(m3=pl.col("aastakokku").sum(), intakes=pl.col("code").n_unique())
    )
    j = (
        a.join(res, left_on="body", right_on="pohjaveekogum_id", how="full", coalesce=True)
        .join(st, left_on="body", right_on="pohjaveekogum_id", how="left")
        .with_columns(
            (pl.col("m3") / DAYS).alias("abstraction_m3_d"),
        )
    )
    both = j.filter((pl.col("abstraction_m3_d") > 0) & (pl.col("t1_olme") > 0)).with_columns(
        (pl.col("abstraction_m3_d") / pl.col("t1_olme")).alias("ratio")
    )
    rows = [
        {
            "kood": r["kood"],
            "abstraction_m3_d": r["abstraction_m3_d"],
            "reserve_t1_olme": r["t1_olme"],
            "ratio": r["ratio"],
            "deposits": r["deposits"],
            "quantity_status": r["seis_kog"],
        }
        for r in both.sort("ratio", descending=True).to_dicts()
    ]
    r = both["ratio"]
    return {
        "year": year,
        "bodies_with_abstraction": a.height,
        "bodies_with_reserve": res.height,
        "bodies_with_both": both.height,
        "abstraction_without_reserve_m3_d": float(
            j.filter(pl.col("t1_olme").is_null() | (pl.col("t1_olme") <= 0))[
                "abstraction_m3_d"
            ].sum()
            or 0.0
        ),
        "ratio_gt1": int((r > 1).sum()),
        "ratio_05_1": int(((r > 0.5) & (r <= 1)).sum()),
        "ratio_lt05": int((r <= 0.5).sum()),
        "abstraction_in_both_m3_d": float(both["abstraction_m3_d"].sum() or 0.0),
        "reserve_in_both": float(both["t1_olme"].sum() or 0.0),
        "bodies": rows,
    }


def by_intake_type(g: pl.DataFrame, intakes: pl.DataFrame) -> list[dict[str, Any]]:
    """Abstraction volume per intake water type (register ``veeliik``) in the latest year."""
    year = int(g["aruandeaasta"].max())  # type: ignore[arg-type]
    t = intakes.select(norm("kkr_kood").alias("code"), pl.col("veeliik_selg")).unique("code")
    j = g.filter(pl.col("aruandeaasta") == year).join(t, on="code", how="left")
    out = (
        j.with_columns(pl.col("veeliik_selg").fill_null("Märkimata"))
        .group_by("veeliik_selg")
        .agg(m3=pl.col("aastakokku").sum(), intakes=pl.col("code").n_unique())
        .sort("m3", descending=True)
    )
    return [{"year": year, **r} for r in out.to_dicts()]


def build(
    gw: pl.DataFrame,
    intakes: pl.DataFrame,
    boreholes: pl.DataFrame,
    res: pl.DataFrame,
    states: pl.DataFrame,
) -> dict[str, Any]:
    g = allocate(gw.filter(pl.col("aastakokku").is_not_null()), intake_bodies(intakes, boreholes))
    rb, st = reserve_by_body(res), latest_status(states)
    year = int(g["aruandeaasta"].max())  # type: ignore[arg-type]
    return {
        "meta": {
            "interpretation": [
                "Põhjaveevõtt on veearuannete (t_awtabel002_01) aastamaht m³ aastas veehaarde "
                "kohta; "
                "veehaare seotakse registriga KKR koodi alusel (kõik võtukoodid ühtivad) ja "
                "registri puuraukude kaudu põhjaveekogumiga.",
                "Veehaare arvestatakse põhjaveekogumi alla ainult siis, kui kõik tema kehtivad "
                "puuraugud asuvad ühes kogumis; mitme kogumi või kogumita veehaarded on eraldi ja "
                "neid ei jaotata.",
                "Kinnitatud varu on põhjaveekogumi kehtivate varukirjete T1 'olme' summa; "
                "ühik m³ ööpäevas on eeldatud, kinnitamata. Võrdlus: aastamaht / 365 ning varu.",
                "Varu kehtib kinnitatud veemaardlatele, mitte kogu põhjaveekogumile; suhe üle 1 "
                "ei tähenda üleekspluateerimist. Põhjaveekogumi koguseline seisund (KOG) on "
                "veekogumite hindamise tulemus ja eraldi allikas.",
                "Võtt hõlmab ka kaevandus- ja karjäärivett (veehaarde veeliik registris on "
                "enamasti märkimata), mis ei kuulu olmeveevarude hulka.",
                "Aruandeaastaid on vähe ja aruannete arv aastas erineb; "
                "veehaarde koode ei avaldata, põhjaveekogumid on tähistatud registrikoodiga.",
            ]
        },
        "allocation": shares(g),
        "latest": by_body(g, year, rb, st),
        "intake_types": by_intake_type(g, intakes),
        "checks": {
            "abstraction_rows": gw.height,
            "intakes": intakes.height,
            "boreholes": boreholes.height,
            "reserve_valid": res.filter(pl.col("keht_staatus") == "Kehtiv").height,
        },
    }
