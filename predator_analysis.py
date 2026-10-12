"""Large carnivores (wolf, brown bear, lynx): structure of the hunting-district observation data.

Input: rows of the indicators "Liigi isendite arv", "... (ad)", "... (juv)" and "..., min" for
species hunt, pruunkaru and ilves (programmes "Hundivaatlused / Karuvaatlused / Ilvesevaatlused
jahipiirkondades") from ``monitoring_extract.py``.  The plot code is a hunting district.

A first look showed that the reporting structure changes a lot between years (the number of
reporting districts for one species falls from hundreds to one while the number of observations
rises, indicators exist for some years only), so no abundance or trend statistic is derived.  Only
the per-year reporting structure is published: reporting districts and observations per species
and indicator.
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


def by_indicator(g: pl.DataFrame) -> list[dict[str, Any]]:
    """Rows, reporting districts and the year range of each indicator."""
    t = g.group_by("naitaja_nimetus").agg(
        rows=pl.len(),
        districts=pl.col("seirekoht_kood").n_unique(),
        first_year=pl.col("year").min(),
        last_year=pl.col("year").max(),
    )
    return t.sort("rows", descending=True).to_dicts()


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
            "by_indicator": by_indicator(g),
        }
    return {
        "meta": {
            "interpretation": [
                "Read on jahipiirkondade vaatlusaruanded ja piirkondlikud hinnangud (hundi-, "
                "karu- ja ilvesevaatlused), mitte loendus.",
                "Aruandvate jahipiirkondade ja vaatluste arv muutub aastate vahel tugevalt ning "
                "osa näitajaid on olemas ainult mõne aasta kohta; seetõttu ei ole arvutatud "
                "arvukuse ega trendinäitajaid.",
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
