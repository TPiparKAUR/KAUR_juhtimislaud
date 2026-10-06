"""Tree crown condition (needle/leaf loss) from the national forest monitoring rows.

Input: rows of the indicator "Okka/lehekadu kogu võra ulatuses" (``monitoring_extract.py``).  The
value is a *class* written as text in ``vaartus_muu`` (e.g. ">20-25%", "0 %, okka/lehekadu ei
ole", "100 %, surnud puu", "Hindamata"), not a number.

Interpretation (unconfirmed, stated in the output ``meta``):

* A class is represented by its upper bound; dead trees (100 %) are counted as defoliation 100 %.
* Damage classes follow the common ICP Forests convention for defoliation: 0-10 % none,
  >10-25 % slight, >25-60 % moderate, >60 % severe (including dead).  "Damaged" = more than 25 %.
* Trees not assessed ("Hindamata") are excluded from shares and reported.
* Plots are not necessarily the same every year; the number of plots and trees is reported.
"""

from __future__ import annotations

import re
from typing import Any

import polars as pl

INDICATOR = "Okka/lehekadu kogu võra ulatuses"
CLASSES = ("none", "slight", "moderate", "severe")
CLASS_LABELS = {
    "none": "Puudub (0-10%)",
    "slight": "Nõrk (>10-25%)",
    "moderate": "Mõõdukas (>25-60%)",
    "severe": "Tugev (>60%) või surnud",
}
SPECIES = ("harilik mänd", "harilik kuusk", "arukask")
RANGE = re.compile(r">?\s*(\d+)\s*[-\u2013]\s*(\d+)\s*%")
POINT = re.compile(r"^\s*(\d+)\s*%")


def upper_bound(label: str | None) -> float | None:
    """Upper bound (percent) of a defoliation class label; None when not assessed/unparsable."""
    if not label or label.strip().lower().startswith("hindamata"):
        return None
    m = RANGE.search(label)
    if m:
        return float(m.group(2))
    m = POINT.match(label)
    return float(m.group(1)) if m else None


def damage_class(upper: float) -> str:
    if upper <= 10:
        return "none"
    if upper <= 25:
        return "slight"
    if upper <= 60:
        return "moderate"
    return "severe"


def prepare(df: pl.DataFrame) -> pl.DataFrame:
    """Rows of the crown indicator with year, defoliation upper bound and damage class."""
    d = df.filter(pl.col("naitaja_nimetus") == INDICATOR).with_columns(
        pl.col("seireaeg_algus").str.slice(0, 4).cast(pl.Int32, strict=False).alias("year"),
        pl.col("vaartus_muu").map_elements(upper_bound, return_dtype=pl.Float64).alias("upper"),
    )
    return d.with_columns(
        pl.col("upper")
        .map_elements(lambda u: damage_class(u) if u is not None else None, return_dtype=pl.String)
        .alias("cls")
    )


def checks(d: pl.DataFrame) -> dict[str, Any]:
    key = ["year", "seirekoht_kood", "isend_nr", "liik_est"]
    dup = d.group_by(key).agg(n=pl.len())
    labels = d.filter(pl.col("upper").is_null())["vaartus_muu"].value_counts().to_dicts()
    return {
        "rows": d.height,
        "not_assessed_or_unparsed": int(d["upper"].null_count()),
        "unparsed_labels": labels[:10],
        "duplicate_groups": int((dup["n"] > 1).sum()),
        "tree_year_groups": dup.height,
    }


def by_year(d: pl.DataFrame, species: str | None = None) -> list[dict[str, Any]]:
    g = d if species is None else d.filter(pl.col("liik_est") == species)
    g = g.filter(pl.col("cls").is_not_null())
    out = []
    for (year,), t in g.group_by("year", maintain_order=True):
        n = t.height
        counts = {c: int((t["cls"] == c).sum()) for c in CLASSES}
        out.append(
            {
                "year": int(year),
                "trees": n,
                "plots": t["seirekoht_kood"].n_unique(),
                "counts": counts,
                "share_damaged": (counts["moderate"] + counts["severe"]) / n if n else None,
                "mean_upper": t["upper"].mean(),
            }
        )
    return sorted(out, key=lambda r: r["year"])


def build(df: pl.DataFrame) -> dict[str, Any]:
    d = prepare(df)
    species_rows = (
        d.group_by("liik_est").agg(trees=pl.len()).sort("trees", descending=True).head(8).to_dicts()
    )
    return {
        "meta": {
            "indicator": INDICATOR,
            "class_labels": CLASS_LABELS,
            "interpretation": [
                "Okka-/lehekadu on tabelis klassina (nt „>20-25%“), mitte arvuna; klassi "
                "esindab selle ülempiir, surnud puu on 100%.",
                "Kahjustusklassid järgivad ICP Forests tavapärast jaotust (0-10% puudub, >10-25% "
                "nõrk, >25-60% mõõdukas, >60% tugev, sh surnud); „kahjustunud“ = üle 25%. "
                "Rakenduse vastavus Eesti metoodikale on kinnitamata.",
                "Hindamata puud jäetakse osakaaludest välja. Proovialade koosseis aastate lõikes "
                "ei ole tingimata sama; proovialade ja puude arv on näidatud.",
                "Osakaal arvutatakse puude, mitte proovialade lõikes.",
            ],
            "species_in_data": species_rows,
        },
        "checks": checks(d),
        "all": by_year(d),
        "species": {s: by_year(d, s) for s in SPECIES},
    }
