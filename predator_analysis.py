"""Large carnivores (wolf, brown bear, lynx) from the hunting-district observation programmes.

Input: rows of the indicators "Liigi isendite arv" (individuals per observation), "... (ad)",
"... (juv)" and "..., min" for species hunt, pruunkaru and ilves (programmes "Hundivaatlused /
Karuvaatlused / Ilvesevaatlused jahipiirkondades") from ``monitoring_extract.py``.  The plot code
is a hunting district.

These are reports of observations and district estimates, **not** a census or an abundance index:
the number of reports and of reporting districts changes a lot between years (see ``effort``), so
raw totals are not comparable.  Four effort-aware summaries are produced per species:

* ``effort``: reporting districts and observations per year (what the data volume reflects);
* ``group``: mean and median individuals per observation per year;
* ``minimum``: the district-level annual minimum number ("..., min"): mean per reporting district,
  and a paired comparison for districts reporting in both the first and the last years;
* ``juvenile``: juveniles as a share of adults + juveniles (summed counts, assuming the "ad" and
  "juv" rows describe the same kind of observation).
"""

from __future__ import annotations

from typing import Any

import polars as pl

PROGRAMME_RE = "^(Hundi|Karu|Ilvese)vaatlused"
SPECIES = {"hunt": "Hunt", "pruunkaru": "Pruunkaru", "ilves": "Ilves"}
IND_ALL = "Liigi isendite arv"
IND_AD = "Liigi isendite arv (ad)"
IND_JUV = "Liigi isendite arv (juv)"
IND_MIN = "Liigi isendite arv, min"
FIRST_YEAR = 2006  # earlier years have a handful of rows
MIN_DISTRICTS = 20
PAIR_YEARS = 3


def has_predators(df: pl.DataFrame) -> bool:
    need = {"seiretoo_nimetus", "liik_est", "seirekoht_kood", "naitaja_nimetus"}
    return need <= set(df.columns) and bool(
        df["seiretoo_nimetus"].str.contains(PROGRAMME_RE).fill_null(False).any()
    )


def prepare(df: pl.DataFrame) -> pl.DataFrame:
    return (
        df.filter(
            pl.col("seiretoo_nimetus").str.contains(PROGRAMME_RE)
            & pl.col("liik_est").is_in(list(SPECIES))
            & pl.col("vaartus_arv_moodetud").is_not_null()
            & (pl.col("vaartus_arv_moodetud") >= 0)
        )
        .with_columns(
            pl.col("seireaeg_algus").str.slice(0, 4).cast(pl.Int32, strict=False).alias("year")
        )
        .filter(pl.col("year") >= FIRST_YEAR)
    )


def effort(g: pl.DataFrame) -> list[dict[str, Any]]:
    o = g.filter(pl.col("naitaja_nimetus") == IND_ALL)
    t = o.group_by("year").agg(districts=pl.col("seirekoht_kood").n_unique(), observations=pl.len())
    return t.sort("year").to_dicts()


def group_size(g: pl.DataFrame) -> list[dict[str, Any]]:
    o = g.filter(pl.col("naitaja_nimetus") == IND_ALL)
    t = o.group_by("year").agg(
        mean=pl.col("vaartus_arv_moodetud").mean(),
        median=pl.col("vaartus_arv_moodetud").median(),
        n=pl.len(),
    )
    return t.sort("year").to_dicts()


def minimum(g: pl.DataFrame) -> dict[str, Any]:
    m = g.filter(pl.col("naitaja_nimetus") == IND_MIN)
    per = m.group_by("seirekoht_kood", "year").agg(v=pl.col("vaartus_arv_moodetud").max())
    years = (
        per.group_by("year")
        .agg(
            districts=pl.len(),
            mean=pl.col("v").mean(),
            total=pl.col("v").sum(),
            p90=pl.col("v").quantile(0.9),
        )
        .sort("year")
        .to_dicts()
    )
    ys = [r["year"] for r in years if r["districts"] >= MIN_DISTRICTS]
    pair = None
    if len(ys) >= 2 * PAIR_YEARS:
        first, last = ys[:PAIR_YEARS], ys[-PAIR_YEARS:]
        a = (
            per.filter(pl.col("year").is_in(first))
            .group_by("seirekoht_kood")
            .agg(a=pl.col("v").mean())
        )
        b = (
            per.filter(pl.col("year").is_in(last))
            .group_by("seirekoht_kood")
            .agg(b=pl.col("v").mean())
        )
        w = a.join(b, on="seirekoht_kood", how="inner")
        if w.height >= MIN_DISTRICTS:
            pair = {
                "first_years": [first[0], first[-1]],
                "last_years": [last[0], last[-1]],
                "districts": w.height,
                "mean_first": w["a"].mean(),
                "mean_last": w["b"].mean(),
                "share_increased": float((w["b"] > w["a"]).sum()) / w.height,
                "share_decreased": float((w["b"] < w["a"]).sum()) / w.height,
            }
    return {"years": years, "paired": pair}


def juvenile(g: pl.DataFrame) -> list[dict[str, Any]]:
    s = (
        g.filter(pl.col("naitaja_nimetus").is_in([IND_AD, IND_JUV]))
        .group_by("year", "naitaja_nimetus")
        .agg(total=pl.col("vaartus_arv_moodetud").sum(), n=pl.len())
    )
    out = []
    for year in sorted(s["year"].unique().to_list()):
        t = {r["naitaja_nimetus"]: r for r in s.filter(pl.col("year") == year).to_dicts()}
        ad, ju = t.get(IND_AD), t.get(IND_JUV)
        if ad and ju and ad["total"] + ju["total"] > 0:
            out.append(
                {
                    "year": year,
                    "share": ju["total"] / (ad["total"] + ju["total"]),
                    "adults": ad["total"],
                    "juveniles": ju["total"],
                    "n": ad["n"] + ju["n"],
                }
            )
    return out


def build(df: pl.DataFrame) -> dict[str, Any]:
    d = prepare(df)
    species: dict[str, Any] = {}
    for key, label in SPECIES.items():
        g = d.filter(pl.col("liik_est") == key)
        if g.is_empty():
            continue
        species[key] = {
            "label": label,
            "effort": effort(g),
            "group": group_size(g),
            "minimum": minimum(g),
            "juvenile": juvenile(g),
        }
    return {
        "meta": {
            "interpretation": [
                "Read on jahipiirkondade vaatlusaruanded ja piirkondlikud hinnangud (hundi-, "
                "karu- ja ilvesevaatlused), mitte loendus; neid ei ole kasutatud arvukuse "
                "hinnanguna.",
                "Aruannete ja aruandvate jahipiirkondade arv muutub aastate vahel tugevalt; "
                "seetõttu ei ole aastasummad võrreldavad ja neid ei näidata.",
                "„Min“ näitaja on piirkonna aastane minimaalne isendite arv (tõlgendus "
                "kinnitamata); näidatud on keskmine aruandva piirkonna kohta ning paarisvõrdlus "
                "piirkondadele, mis aruandsid nii esimestel kui viimastel aastatel.",
                "Noorloomade osakaal on noorloomade summa jagatud täiskasvanute ja noorloomade "
                "summaga (eeldus: „ad“ ja „juv“ read kirjeldavad samasugust vaatlust).",
                "Piirkondade koode ega koordinaate ei avaldata; tulemus on koond.",
            ]
        },
        "species": species,
        "checks": {
            "rows": d.height,
            "districts": d["seirekoht_kood"].n_unique(),
            "indicators": d["naitaja_nimetus"].value_counts().to_dicts(),
        },
    }
