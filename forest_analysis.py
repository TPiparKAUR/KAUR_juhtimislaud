"""Pure analysis functions for the statistical forest inventory (SMI) results.

Input is the long table ``f_smi_tulemused`` (see ``forest_fetch.py``): each row is a published
estimate with a relative error (``suhteline_viga``).  The table is a cube with optional
classifiers, so a series is selected by *exact shape*: the named classifiers are fixed and every
other classifier must be empty, otherwise totals and sub-totals would be mixed.

Interpretation (documented, to be confirmed by the data owner)
--------------------------------------------------------------
* Units: area in thousand ha, volume in thousand m3, increment/felling in thousand m3 per year,
  means per hectare in m3/ha.  Inferred from magnitudes (2.35 M ha forest land, 453 M m3 stock).
* ``suhteline_viga`` is a relative error as a fraction; the Forest Yearbook 2021 (p. 17, 124)
  describes SMI errors as +-% at confidence level 0.95, so it is treated as a 95% half-width.  The
  database column ``usaldusnivoo`` is 0 on every row (unspecified).
* ``periood`` 5 (3 for the felling table 22): the estimate rests on a multi-year inventory
  period, so consecutive years overlap and are NOT independent.
* Errors of sums over groups are combined as a root sum of squares (groups independent), and of
  differences/ratios likewise; these are approximations and are labelled as such.
"""

from __future__ import annotations

import math
from typing import Any

import polars as pl

DIMS = [
    "maakategooria",
    "omand",
    "maakond",
    "majandkategooria",
    "enamuspuuliik",
    "filtri_tunnus1",
    "filter1",
    "filtri_tunnus2",
    "filter2",
    "filtri_tunnus3",
    "filter3",
]
LAND = "Metsamaa"  # forest land (incl. temporarily unstocked), the national headline category
ALL_STANDS = "Puistud"  # the "all species" row of the species breakdown
SUM, MEAN = "Summa", "Keskmine"


def exact(
    df: pl.DataFrame,
    table: int,
    indicator: str,
    calc: str,
    period: str | None = None,
    **fixed: str,
) -> pl.DataFrame:
    """Rows of one table/indicator/calculation whose filled classifiers are exactly ``fixed``."""
    d = df.filter(
        (pl.col("tabeli_number") == table)
        & (pl.col("tunnus") == indicator)
        & (pl.col("arvutus") == calc)
    )
    if period is not None:
        d = d.filter(pl.col("periood").cast(pl.Utf8) == period)
    for col in DIMS:
        d = d.filter(pl.col(col) == fixed[col]) if col in fixed else d.filter(pl.col(col).is_null())
    return d


def series(d: pl.DataFrame) -> list[dict[str, Any]]:
    """``[{year, value, err}]`` sorted by year; ``err`` is the relative error (fraction) or None."""
    rows = d.filter(pl.col("arvvaartus").is_not_null()).sort("aasta")
    return [
        {"year": int(r["aasta"]), "value": float(r["arvvaartus"]), "err": _f(r["suhteline_viga"])}
        for r in rows.iter_rows(named=True)
    ]


def _f(x: Any) -> float | None:
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else float(x)


def total_over(
    df: pl.DataFrame, by: str, table: int, indicator: str, calc: str = SUM, **fixed: str
) -> list[dict[str, Any]]:
    """Add the groups of ``by`` (e.g. owners) per year; combine errors as a root sum of squares."""
    rows: dict[int, list[tuple[float, float | None]]] = {}
    sub = df.filter(
        (pl.col("tabeli_number") == table)
        & (pl.col("tunnus") == indicator)
        & (pl.col("arvutus") == calc)
        & pl.col(by).is_not_null()
    )
    for col in DIMS:
        if col == by:
            continue
        sub = (
            sub.filter(pl.col(col) == fixed[col])
            if col in fixed
            else sub.filter(pl.col(col).is_null())
        )
    for r in sub.filter(pl.col("arvvaartus").is_not_null()).iter_rows(named=True):
        rows.setdefault(int(r["aasta"]), []).append(
            (float(r["arvvaartus"]), _f(r["suhteline_viga"]))
        )
    out = []
    for y in sorted(rows):
        parts = rows[y]
        value = sum(v for v, _ in parts)
        if value == 0 or any(e is None for _, e in parts):
            err = None
        else:
            err = math.sqrt(sum((v * (e or 0.0)) ** 2 for v, e in parts)) / value
        out.append({"year": y, "value": value, "err": err})
    return out


def change(first: dict[str, Any], last: dict[str, Any]) -> dict[str, Any]:
    """Difference last - first with a combined 95% half-width and a distinguishability flag."""
    diff = last["value"] - first["value"]
    if first["err"] is None or last["err"] is None:
        half = None
    else:
        half = math.hypot(first["value"] * first["err"], last["value"] * last["err"])
    return {
        "from": first["year"],
        "to": last["year"],
        "diff": diff,
        "pct": diff / first["value"] if first["value"] else None,
        "half_width": half,
        "distinguishable": None if half is None else abs(diff) > half,
    }


def add(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Series a + b on common years; absolute errors combined as a root sum of squares."""
    bm = {r["year"]: r for r in b}
    out = []
    for r in a:
        o = bm.get(r["year"])
        if o is None:
            continue
        value = r["value"] + o["value"]
        if r["err"] is None or o["err"] is None or not value:
            err = None
        else:
            err = math.hypot(r["value"] * r["err"], o["value"] * o["err"]) / value
        out.append({"year": r["year"], "value": value, "err": err})
    return out


def ratio(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Series a / b on common years; relative error of a ratio as sqrt(ea^2 + eb^2)."""
    bm = {r["year"]: r for r in b}
    out = []
    for r in a:
        o = bm.get(r["year"])
        if o is None or not o["value"]:
            continue
        err = None if r["err"] is None or o["err"] is None else math.hypot(r["err"], o["err"])
        out.append({"year": r["year"], "value": r["value"] / o["value"], "err": err})
    return out


def national(df: pl.DataFrame) -> dict[str, Any]:
    """Headline series for forest land: area, stock, increment, felling, dead wood."""
    stands = {"enamuspuuliik": ALL_STANDS}
    out: dict[str, Any] = {
        "area": series(exact(df, 24, "Pindala", SUM, maakategooria=LAND)),
        "stock": series(exact(df, 24, "Kasvavate puude maht", SUM, maakategooria=LAND)),
        "stock_per_ha": series(exact(df, 24, "Kasvavate puude maht", MEAN, maakategooria=LAND)),
        "increment": series(exact(df, 6, "Juurdekasv", SUM, maakategooria=LAND, **stands)),
        "increment_per_ha": series(exact(df, 6, "Juurdekasv", MEAN, maakategooria=LAND, **stands)),
        "felling_5y": series(
            exact(df, 23, "Raiutud maht", SUM, "5", maakategooria=LAND, filtri_tunnus1="Raieliik",
                  filter1="Raied kokku", filtri_tunnus2="Raie aeg", filter2="Hooajaraie")
        ),
        "felling_3y": series(
            exact(df, 22, "Raiutud maht", SUM, "3", maakategooria=LAND, filtri_tunnus1="Raieliik",
                  filter1="Raied kokku", filtri_tunnus2="Raie aeg", filter2="Hooajaraie")
        ),
        "deadwood_standing": total_over(
            df, "omand", 5351, "Kuivanud puude maht", SUM, maakategooria=LAND
        ),
        "deadwood_lying": total_over(df, "omand", 5351, "Lamapuidu maht", SUM, maakategooria=LAND),
    }  # fmt: skip
    out["felling_to_increment_5y"] = ratio(out["felling_5y"], out["increment"])
    out["deadwood_total"] = add(out["deadwood_standing"], out["deadwood_lying"])
    out["deadwood_per_ha"] = ratio(out["deadwood_total"], out["area"])
    return out


def species(df: pl.DataFrame) -> dict[str, list[dict[str, Any]]]:
    """Growing stock and area by dominant species (excluding the all-stands total)."""
    out: dict[str, list[dict[str, Any]]] = {}
    for sp in sorted(
        df.filter(pl.col("tabeli_number") == 6)["enamuspuuliik"].drop_nulls().unique()
    ):
        if sp == ALL_STANDS:
            continue
        data = series(
            exact(df, 6, "Kasvavate puude maht", SUM, maakategooria=LAND, enamuspuuliik=sp)
        )
        if data:
            out[sp] = data
    return out


def owners(df: pl.DataFrame) -> dict[str, list[dict[str, Any]]]:
    """Forest land area by ownership group (table 1)."""
    out: dict[str, list[dict[str, Any]]] = {}
    for o in sorted(df.filter(pl.col("tabeli_number") == 1)["omand"].drop_nulls().unique()):
        data = series(exact(df, 1, "Pindala", SUM, maakategooria=LAND, omand=o))
        if data:
            out[o] = data
    return out


def management(df: pl.DataFrame) -> dict[str, list[dict[str, Any]]]:
    """Forest land area by management category (table 4)."""
    out: dict[str, list[dict[str, Any]]] = {}
    cats = df.filter(pl.col("tabeli_number") == 4)["majandkategooria"].drop_nulls().unique()
    for c in sorted(cats):
        data = series(exact(df, 4, "Pindala", SUM, maakategooria=LAND, majandkategooria=c))
        if data:
            out[c] = data
    return out


def counties(df: pl.DataFrame) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Growing stock, stock per hectare and area by county (table 24)."""
    out: dict[str, dict[str, list[dict[str, Any]]]] = {}
    names = df.filter(pl.col("tabeli_number") == 24)["maakond"].drop_nulls().unique()
    for c in sorted(names):
        entry = {
            "stock": series(
                exact(df, 24, "Kasvavate puude maht", SUM, maakategooria=LAND, maakond=c)
            ),
            "stock_per_ha": series(
                exact(df, 24, "Kasvavate puude maht", MEAN, maakategooria=LAND, maakond=c)
            ),
            "area": series(exact(df, 24, "Pindala", SUM, maakategooria=LAND, maakond=c)),
        }
        if entry["stock_per_ha"]:
            out[c] = entry
    return out


AGE_20_YEAR = "…"  # the 20-year classes ("21…40 a") use the ellipsis character, the 10-year
# classes ("21...30 a") three dots; both sets sit in the same classifier and must not be mixed.
MANAGEMENT_PARTS = ["Majandusmets", "Majanduspiiranguga mets", "Rangelt kaitstav mets"]
# ^ non-overlapping: "Majandatavad mets" and "Kaitstav mets" are sums of these.


def age_structure(df: pl.DataFrame, scheme: str = AGE_20_YEAR) -> dict[str, list[dict[str, Any]]]:
    """Area by age class, owners added (table 13, classifier 'Vanus', one class scheme only)."""
    classes = (
        df.filter(
            (pl.col("tabeli_number") == 13)
            & (pl.col("filtri_tunnus2") == "Vanus")
            & pl.col("filter2").str.contains(scheme, literal=True)
        )["filter2"]
        .drop_nulls()
        .unique()
    )
    out: dict[str, list[dict[str, Any]]] = {}
    for c in sorted(classes):
        data = total_over(
            df, "omand", 13, "Pindala", SUM, maakategooria=LAND, filtri_tunnus2="Vanus", filter2=c
        )
        if data:
            out[c] = data
    return out


def shares_check(parts: list[float], total: float | None) -> float | None:
    """Sum of parts divided by the stated total: ~1 means the classes tile the total."""
    return None if not total else sum(parts) / total


def error_summary(df: pl.DataFrame) -> dict[str, Any]:
    """Distribution of relative errors over all rows, for the quality section."""
    err = df["suhteline_viga"].drop_nulls()
    return {
        "rows": df.height,
        "null_error_share": 1 - len(err) / df.height if df.height else None,
        "quantiles": {f"p{q}": err.quantile(q / 100) for q in (10, 50, 90, 99)} if len(err) else {},
        "share_over_50pct": float(err.gt(0.5).sum()) / len(err) if len(err) else None,
    }
