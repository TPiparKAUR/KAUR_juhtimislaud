"""Soil monitoring (programme "Mullaseire"): acidity, organic matter and trace elements.

Input: rows of the soil indicator groups from ``monitoring_extract.py``.  Only rows of the soil
monitoring programme with matrix "Muld, pinnas" are used.  Concentrations are converted to mg/kg dry
matter (assumptions in the output ``meta``): ppm = mg/kg, ug/kg and ppb /1000, % x 10000.
Values are summarised per five-year period (median, 10th and 90th percentile, samples, plots).
Plots differ between periods, so a *paired* comparison on plots measured in both the first and the
last period is added; it is the only like-for-like change estimate here.
"""

from __future__ import annotations

from typing import Any

import polars as pl

PROGRAMME = "Mullaseire"
MATRIX = "Muld, pinnas"
INDICATORS = {
    "pH": ("pH", None),
    "Orgaaniline süsinik": ("Orgaaniline süsinik", "% KA"),
    "Huumussisaldus": ("Huumussisaldus", "% KA"),
    "Fosfor": ("Fosfor", "mg/kg"),
    "Kaalium": ("Kaalium", "mg/kg"),
    "Vask": ("Vask", "mg/kg"),
    "Tsink": ("Tsink", "mg/kg"),
    "Plii": ("Plii", "mg/kg"),
    "Kaadmium": ("Kaadmium", "mg/kg"),
    "Kroom": ("Kroom", "mg/kg"),
    "Nikkel": ("Nikkel", "mg/kg"),
    "Elavhõbe": ("Elavhõbe", "mg/kg"),
    "Arseen": ("Arseen", "mg/kg"),
}
TO_MG_KG = {"mg/kg KA": 1.0, "ppm": 1.0, "µg/kg KA": 1e-3, "ppb": 1e-3, "% KA": 1e4}
PH_RANGE = (2.0, 10.0)
PERIOD_LEN = 5
FIRST_YEAR = 2002


def period_label(year: int) -> str:
    start = FIRST_YEAR + PERIOD_LEN * ((year - FIRST_YEAR) // PERIOD_LEN)
    return f"{start}-{start + PERIOD_LEN - 1}"


def prepare(df: pl.DataFrame) -> pl.DataFrame:
    d = df.filter(
        pl.col("seiretoo_nimetus").str.starts_with(PROGRAMME)
        & (pl.col("naitaja_proovimaatriks_nimi") == MATRIX)
        & pl.col("vaartus_arv_moodetud").is_not_null()
        & pl.col("naitaja_nimetus").is_in(list(INDICATORS))
    ).with_columns(
        pl.col("seireaeg_algus").str.slice(0, 4).cast(pl.Int32, strict=False).alias("year")
    )
    d = d.filter(pl.col("year") >= FIRST_YEAR)
    return d.with_columns(
        pl.col("year").map_elements(period_label, return_dtype=pl.String).alias("period")
    )


def value_column(d: pl.DataFrame, name: str) -> pl.DataFrame:
    """Rows of one indicator with a comparable ``v`` column (pH as is, others in mg/kg or %)."""
    g = d.filter(pl.col("naitaja_nimetus") == name)
    if name == "pH":
        lo, hi = PH_RANGE
        return g.filter(pl.col("vaartus_arv_moodetud").is_between(lo, hi)).with_columns(
            pl.col("vaartus_arv_moodetud").alias("v")
        )
    target = INDICATORS[name][1]
    factor = pl.col("naitaja_abr_unit").replace_strict(
        TO_MG_KG, default=None, return_dtype=pl.Float64
    )
    g = g.with_columns((pl.col("vaartus_arv_moodetud") * factor).alias("v")).filter(
        pl.col("v").is_not_null() & (pl.col("v") >= 0)
    )
    if target == "% KA":  # keep organic matter in % of dry matter
        g = g.with_columns((pl.col("v") / 1e4).alias("v"))
    return g


def by_period(g: pl.DataFrame) -> list[dict[str, Any]]:
    out = []
    for (period,), t in g.group_by("period", maintain_order=True):
        out.append(
            {
                "period": period,
                "samples": t.height,
                "plots": t["seirekoht_kood"].n_unique(),
                "median": t["v"].median(),
                "p10": t["v"].quantile(0.1),
                "p90": t["v"].quantile(0.9),
                "below_loq_mark": int(t["vaartus_erimark"].is_not_null().sum()),
            }
        )
    return sorted(out, key=lambda r: r["period"])


def paired(g: pl.DataFrame, first: str, last: str) -> dict[str, Any] | None:
    """Plots measured in both periods: per-plot median in each, and the change."""
    per = (
        g.filter(pl.col("period").is_in([first, last]))
        .group_by("seirekoht_kood", "period")
        .agg(v=pl.col("v").median())
    )
    wide = per.pivot(on="period", index="seirekoht_kood", values="v").drop_nulls()
    if first not in wide.columns or last not in wide.columns or wide.is_empty():
        return None
    diff = wide[last] - wide[first]
    return {
        "from": first,
        "to": last,
        "plots": wide.height,
        "median_first": wide[first].median(),
        "median_last": wide[last].median(),
        "median_change": diff.median(),
        "share_increased": float((diff > 0).sum()) / wide.height,
    }


def build(df: pl.DataFrame) -> dict[str, Any]:
    d = prepare(df)
    indicators: dict[str, Any] = {}
    for name in INDICATORS:
        g = value_column(d, name)
        periods = by_period(g)
        if not periods:
            continue
        labels = [p["period"] for p in periods if p["plots"] >= 20]
        indicators[name] = {
            "unit": "mg/kg KA" if INDICATORS[name][1] == "mg/kg" else INDICATORS[name][1] or "",
            "periods": periods,
            "paired": paired(g, labels[0], labels[-1]) if len(labels) >= 2 else None,
        }
    return {
        "meta": {
            "programme": PROGRAMME,
            "interpretation": [
                "Kasutatud on ainult mullaseire programmi mulla (Muld, pinnas) read alates 2002; "
                "metsaseire ja setete read on välja jäetud.",
                "Kontsentratsioonid on teisendatud mg/kg kuivaines (ppm = mg/kg; µg/kg ja ppb "
                "jagatud 1000-ga); orgaaniline süsinik ja huumus on % kuivaines. pH väärtused "
                "väljaspool vahemikku 2-10 on välja jäetud (andmevead).",
                "Perioodid on 5-aastased; proovialad ei ole perioodide vahel samad. Muutuse "
                "hinnang tehakse ainult proovialadele, mida on mõõdetud nii esimeses kui viimases "
                "perioodis (paaritatud mediaanimuutus).",
                "Väärtused, mis on märgitud „<“ (alla määramispiiri), on arvutustes määramispiiri "
                "väärtusega; nende arv on iga perioodi juures näidatud.",
                "Piirväärtuste ja sihttasemetega võrdlust ei ole tehtud (kehtivaid norme ei ole "
                "siin kinnitatud).",
            ],
        },
        "checks": {
            "rows": d.height,
            "plots": d["seirekoht_kood"].n_unique(),
            "units": d["naitaja_abr_unit"].value_counts().to_dicts(),
        },
        "indicators": indicators,
    }
