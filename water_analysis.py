"""Water-body status analysis (EU Water Framework Directive style classes).

Inputs are the register (``f_veekogumid``), the status assessments (``f_veekogumi_seisundid``),
the pressures (``f_veekogumid_koormus``) and the groundwater status (``f_pohjaveekogumi_seisud``).
Everything is aggregated over water bodies; no water-body names leave this module.

Interpretation choices (all documented in the output ``meta``):

* ``tyyp = 'S'`` rows are assessed *states*, ``'E'`` rows are *objectives*; only valid rows
  (``keht_staatus = 'Kehtiv'``) are used, duplicates per (body, year) keep the latest ``muut_aeg``.
* ``seis`` is the overall classification: 1 very good ... 5 very bad; any other code (U, N, O, 6)
  is counted as "not classified" and excluded from shares, but reported.
* After 2015 each year assesses only a rotating subset (~150 bodies), so years are not
  comparable as a national time series; the like-for-like comparison is *paired by body*.
"""

from __future__ import annotations

from typing import Any

import polars as pl

CLASSES = ("1", "2", "3", "4", "5")
CLASS_NAMES = {
    "1": "Väga hea",
    "2": "Hea",
    "3": "Kesine",
    "4": "Halb",
    "5": "Väga halb",
}
CATEGORY_GROUP = {
    "11": "Vooluveekogu",
    "12": "Vooluveekogu",
    "13": "Vooluveekogu",
    "14": "Vooluveekogu",
    "15": "Vooluveekogu",
    "21": "Järv",
    "22": "Järv",
    "23": "Järv",
    "30": "Meri",
}
OTHER = "Muu / teadmata"
BASELINE_YEAR = 2015  # last year in which almost every body (~720) was assessed
GOOD = ("1", "2")
GW_CLASSES = {"1": "Hea", "2": "Ohustatud", "3": "Halb"}


def category(code: str | None) -> str:
    return CATEGORY_GROUP.get(code or "", OTHER)


def valid_states(states: pl.DataFrame, register: pl.DataFrame) -> pl.DataFrame:
    """Valid state assessments, one row per (body, year), with the water body category."""
    cur = (
        states.filter((pl.col("tyyp") == "S") & (pl.col("keht_staatus") == "Kehtiv"))
        .sort("muut_aeg", nulls_last=False)
        .unique(subset=["vkm_id", "aasta"], keep="last")
        .with_columns(pl.col("aasta").cast(pl.Int64).alias("year"))
    )
    cats = register.select(
        pl.col("id").alias("vkm_id"),
        pl.col("veekogu_tyyp").map_elements(category, return_dtype=pl.String).alias("group"),
    )
    return cur.join(cats, on="vkm_id", how="left").with_columns(
        pl.col("group").fill_null(OTHER),
        pl.when(pl.col("seis").is_in(CLASSES)).then(pl.col("seis")).otherwise(None).alias("cls"),
    )


def distribution(df: pl.DataFrame) -> dict[str, Any]:
    """Counts per class, not classified, and the share of good-or-better among classified."""
    n = df.height
    counts = {c: int((df["cls"] == c).sum()) for c in CLASSES}
    classified = sum(counts.values())
    good = counts["1"] + counts["2"]
    return {
        "n": n,
        "classified": classified,
        "not_classified": n - classified,
        "counts": counts,
        "share_good": good / classified if classified else None,
    }


def by_year(cur: pl.DataFrame) -> list[dict[str, Any]]:
    out = []
    for (year,), g in cur.group_by("year", maintain_order=True):
        out.append({"year": int(year), **distribution(g)})
    return sorted(out, key=lambda r: r["year"])


def by_group_baseline(cur: pl.DataFrame, year: int = BASELINE_YEAR) -> list[dict[str, Any]]:
    out = []
    for group in ("Vooluveekogu", "Järv", "Meri"):
        g = cur.filter((pl.col("year") == year) & (pl.col("group") == group))
        out.append({"group": group, "year": year, **distribution(g)})
    return out


def latest_after(cur: pl.DataFrame, year: int = BASELINE_YEAR) -> pl.DataFrame:
    """The most recent assessment per body made after ``year``."""
    return (
        cur.filter(pl.col("year") > year)
        .sort("year")
        .unique(subset=["vkm_id"], keep="last")
        .select("vkm_id", pl.col("year").alias("year_later"), pl.col("cls").alias("cls_later"))
    )


def paired(cur: pl.DataFrame, year: int = BASELINE_YEAR) -> dict[str, Any]:
    """Like-for-like change: bodies classified in ``year`` and again later (latest assessment)."""
    base = cur.filter(pl.col("year") == year).select("vkm_id", "group", pl.col("cls").alias("cls0"))
    j = base.join(latest_after(cur, year), on="vkm_id").filter(
        pl.col("cls0").is_not_null() & pl.col("cls_later").is_not_null()
    )
    j = j.with_columns(
        (pl.col("cls_later").cast(pl.Int64) - pl.col("cls0").cast(pl.Int64)).alias("delta")
    )

    def tally(g: pl.DataFrame) -> dict[str, Any]:
        return {
            "n": g.height,
            "improved": int((g["delta"] < 0).sum()),
            "same": int((g["delta"] == 0).sum()),
            "worsened": int((g["delta"] > 0).sum()),
            "good_before": int(g["cls0"].is_in(GOOD).sum()),
            "good_after": int(g["cls_later"].is_in(GOOD).sum()),
        }

    by_group = {
        grp: tally(j.filter(pl.col("group") == grp)) for grp in ("Vooluveekogu", "Järv", "Meri")
    }
    years_later = j["year_later"].to_list()
    matrix = {
        a: {b: int(((j["cls0"] == a) & (j["cls_later"] == b)).sum()) for b in CLASSES}
        for a in CLASSES
    }
    return {
        "baseline_year": year,
        "all": tally(j),
        "by_group": by_group,
        "matrix": matrix,
        "later_years": {"min": min(years_later), "max": max(years_later)} if years_later else None,
        "later_year_counts": {
            int(y): int(c)
            for y, c in j.group_by("year_later").agg(c=pl.len()).sort("year_later").iter_rows()
        },
    }


def targets(states: pl.DataFrame, year: int = BASELINE_YEAR) -> dict[str, Any]:
    """Objective achievement flags (``staatus``) of the objective rows of ``year``."""
    e = states.filter(
        (pl.col("tyyp") == "E")
        & (pl.col("keht_staatus") == "Kehtiv")
        & (pl.col("aasta") == str(year))
    )
    flagged = e.filter(pl.col("staatus").is_not_null())
    achieved = int((flagged["staatus"] == "saavutatud").sum())
    return {
        "year": year,
        "objective_rows": e.height,
        "flagged": flagged.height,
        "achieved": achieved,
        "not_achieved": flagged.height - achieved,
    }


def pressures(load: pl.DataFrame, register: pl.DataFrame) -> dict[str, Any]:
    """Share of valid water bodies with at least one significant current pressure, by sector/impact.

    Denominator: valid bodies that have at least one pressure record (assessed bodies).
    """
    valid = register.filter(pl.col("keht_staatus") == "Kehtiv").select(
        pl.col("id").alias("koormus_veekogum_id"),
        pl.col("veekogu_tyyp").map_elements(category, return_dtype=pl.String).alias("group"),
    )
    j = load.join(valid, on="koormus_veekogum_id")
    assessed = j["koormus_veekogum_id"].n_unique()
    sig = j.filter(
        pl.col("olulisus_selg").is_in(["Oluline", "Oluline leevendusmeetmega"])
        & (pl.col("koormus_staatus_selg") == "Survetegur on aktuaalne")
    )

    def share(col: str, groups: list[str] | None = None) -> list[dict[str, Any]]:
        t = sig.filter(pl.col(col).is_not_null())
        rows = []
        for (name,), g in t.group_by(col):
            rows.append(
                {
                    "name": name,
                    "bodies": g["koormus_veekogum_id"].n_unique(),
                    "pressures": g.height,
                }
            )
        return sorted(rows, key=lambda r: -r["bodies"])

    any_sig = sig["koormus_veekogum_id"].n_unique()
    return {
        "assessed_bodies": assessed,
        "bodies_with_significant": any_sig,
        "by_sector": share("pohjus_selg"),
        "by_impact": share("hinnang_moju_selg"),
        "by_group": {
            g: {
                "assessed": j.filter(pl.col("group") == g)["koormus_veekogum_id"].n_unique(),
                "significant": sig.filter(pl.col("group") == g)["koormus_veekogum_id"].n_unique(),
            }
            for g in ("Vooluveekogu", "Järv", "Meri")
        },
    }


def groundwater(gw: pl.DataFrame) -> dict[str, Any]:
    """Groundwater body status per assessment year and paired by body."""
    out: dict[str, Any] = {"years": {}}
    for year in sorted(gw["aasta"].unique().to_list()):
        g = gw.filter(pl.col("aasta") == year)
        out["years"][int(year)] = {
            "n": g.height,
            "counts": {k: int((g["seis"] == k).sum()) for k in GW_CLASSES},
            "chemical": {k: int((g["seis_kem"] == k).sum()) for k in GW_CLASSES},
            "quantity": {k: int((g["seis_kog"] == k).sum()) for k in GW_CLASSES},
        }
    ys = sorted(gw["aasta"].unique().to_list())
    if len(ys) >= 2:
        a = gw.filter(pl.col("aasta") == ys[0]).select(
            "pohjaveekogum_id", pl.col("seis").alias("a")
        )
        b = gw.filter(pl.col("aasta") == ys[-1]).select(
            "pohjaveekogum_id", pl.col("seis").alias("b")
        )
        j = a.join(b, on="pohjaveekogum_id")
        out["paired"] = {
            "from": int(ys[0]),
            "to": int(ys[-1]),
            "n": j.height,
            "improved": int((j["b"].cast(pl.Int64) < j["a"].cast(pl.Int64)).sum()),
            "same": int((j["b"] == j["a"]).sum()),
            "worsened": int((j["b"].cast(pl.Int64) > j["a"].cast(pl.Int64)).sum()),
        }
    return out
