"""Nature-conservation statistics: protected areas, Natura habitats and species, species sites,
woodland key habitats.  All outputs are aggregates; no names, coordinates or free text.

Interpretation choices (repeated in the output ``meta``):

* Protected areas overlap (zones, permanent habitats inside protected areas), so areas are never
  summed across area types.  Units of ``pindala_*`` are assumed to be hectares.
* Natura standard-database versions are labelled by ``elpst_tyyp_selg`` ("2010", "2012", "2015",
  "2026"); the numeric code differs for two versions (2014, 2023), the label is used.
* Species-site counts reflect survey effort and registration practice, not abundance.
"""

from __future__ import annotations

import re
from typing import Any

import polars as pl

KEEP = "kaitsealune"
CONSERVATION = {
    "Väga hästi säilinud": 1,
    "Hästi säilinud": 2,
    "Keskmiselt või vähe säilinud": 3,
}
SPECIES_CONSERVATION = {
    "Kaitsestaatus eeskujulik": 1,
    "Hea kaitsestaatus": 2,
    "Keskmine või vähenenud kaitsestaatus": 3,
}
CATEGORIES = ("I kategooria", "II kategooria", "III kategooria")
YEAR_RE = re.compile(r"(?:19|20)\d{2}")


def protected_areas(alad: pl.DataFrame) -> dict[str, Any]:
    """Count and area per area type (no summation across types: areas overlap)."""
    designated = alad.filter(pl.col("al_staatus_selg").str.starts_with(KEEP))
    planned = alad.filter(~pl.col("al_staatus_selg").str.starts_with(KEEP))

    def agg(df: pl.DataFrame, col: str) -> list[dict[str, Any]]:
        out = (
            df.group_by(col)
            .agg(
                n=pl.len(),
                land_ha=pl.col("pindala_maa").sum(),
                sea_ha=pl.col("pindala_meri").sum(),
                n_land_area=pl.col("pindala_maa").is_not_null().sum(),
            )
            .sort("n", descending=True)
        )
        return [
            {"name": r[col] or "määramata", **{k: r[k] for k in out.columns[1:]}}
            for r in out.to_dicts()
        ]

    return {
        "designated": designated.height,
        "planned": planned.height,
        "by_type": agg(designated, "tyyp_selg"),
        "by_iucn": agg(designated, "iucn_tyyp_selg"),
        "planned_by_type": agg(planned, "tyyp_selg"),
    }


def natura_sites(rahvalad: pl.DataFrame) -> list[dict[str, Any]]:
    return (
        rahvalad.group_by("tyyp_selg")
        .agg(n=pl.len(), land_ha=pl.col("pindala_maa").sum(), sea_ha=pl.col("pindala_meri").sum())
        .sort("n", descending=True)
        .rename({"tyyp_selg": "name"})
        .to_dicts()
    )


def version_label(selg: str) -> str:
    m = YEAR_RE.search(selg or "")
    return m.group(0) if m else "?"


def with_version(df: pl.DataFrame, col: str) -> pl.DataFrame:
    return df.with_columns(
        pl.col(col).map_elements(version_label, return_dtype=pl.String).alias("version")
    )


def habitats(el: pl.DataFrame) -> dict[str, Any]:
    """Natura habitat records per version: counts, area, conservation shares and paired change."""
    df = with_version(el, "elpst_tyyp_selg").filter(~pl.col("elupst_on_endine"))
    df = df.with_columns(
        pl.col("elupst_kaitse_selg").replace_strict(CONSERVATION, default=None).alias("cons")
    )
    versions = sorted(df["version"].unique().to_list())
    per_version = []
    for v in versions:
        g = df.filter(pl.col("version") == v)
        rated = g.filter(pl.col("cons").is_not_null())
        per_version.append(
            {
                "version": v,
                "records": g.height,
                "sites": g["elpst_obj_id"].n_unique(),
                "habitat_types": g["elupaigatyyp_kood"].n_unique(),
                "area_ha": g["elupst_pindala_alal"].sum(),
                "rated": rated.height,
                "counts": {str(k): int((rated["cons"] == k).sum()) for k in (1, 2, 3)},
            }
        )
    groups = []
    last = versions[-1]
    for (name,), g in df.filter(pl.col("version") == last).group_by("elupaigatyyp_grupp_selg"):
        rated = g.filter(pl.col("cons").is_not_null())
        groups.append(
            {
                "name": name,
                "records": g.height,
                "area_ha": g["elupst_pindala_alal"].sum(),
                "rated": rated.height,
                "counts": {str(k): int((rated["cons"] == k).sum()) for k in (1, 2, 3)},
            }
        )
    groups.sort(key=lambda r: float(r["area_ha"] or 0), reverse=True)
    first = versions[0]
    a = df.filter(pl.col("version") == first).select(
        "elpst_obj_id", "elupaigatyyp_kood", pl.col("cons").alias("c0")
    )
    b = df.filter(pl.col("version") == last).select(
        "elpst_obj_id", "elupaigatyyp_kood", pl.col("cons").alias("c1")
    )
    j = a.join(b, on=["elpst_obj_id", "elupaigatyyp_kood"]).filter(
        pl.col("c0").is_not_null() & pl.col("c1").is_not_null()
    )
    paired = {
        "from": first,
        "to": last,
        "n": j.height,
        "improved": int((j["c1"] < j["c0"]).sum()),
        "same": int((j["c1"] == j["c0"]).sum()),
        "worsened": int((j["c1"] > j["c0"]).sum()),
    }
    return {"per_version": per_version, "groups_latest": groups, "paired": paired}


def species_stats(ls: pl.DataFrame) -> dict[str, Any]:
    df = with_version(ls, "lkohtst_tyyp_selg").filter(~pl.col("lkohtst_on_endine"))
    df = df.with_columns(
        pl.col("lkohtst_kaitse_selg")
        .replace_strict(SPECIES_CONSERVATION, default=None)
        .alias("cons")
    )
    versions = sorted(df["version"].unique().to_list())
    per_version = []
    for v in versions:
        g = df.filter(pl.col("version") == v)
        rated = g.filter(pl.col("cons").is_not_null())
        per_version.append(
            {
                "version": v,
                "records": g.height,
                "species": g["lkohtst_lnim_id"].n_unique(),
                "sites": g["lkohtst_obj_id"].n_unique(),
                "rated": rated.height,
                "counts": {str(k): int((rated["cons"] == k).sum()) for k in (1, 2, 3)},
            }
        )
    last = versions[-1]
    g = df.filter(pl.col("version") == last)
    by_group = [
        {"name": r["ryhm_selg"] or "määramata", "records": r["records"], "species": r["species"]}
        for r in g.group_by("ryhm_selg")
        .agg(records=pl.len(), species=pl.col("lkohtst_lnim_id").n_unique())
        .sort("records", descending=True)
        .to_dicts()
    ]
    return {"per_version": per_version, "by_group_latest": by_group, "latest": last}


def species_sites(lk: pl.DataFrame) -> dict[str, Any]:
    """Registered species sites by species group and protection category (effort-dependent)."""
    sp = lk.filter(pl.col("liik_tyyp_selg") == "Kaitsealune liik")
    by_group: list[dict[str, Any]] = []
    for (grp,), g in sp.group_by("lnim_ryhm_selg"):
        by_group.append(
            {
                "name": grp or "määramata",
                "sites": g.height,
                "species": g["lnim_id"].n_unique(),
                "by_category": {
                    c: int((g["lnim_kaitsekategooria_selg"] == c).sum()) for c in CATEGORIES
                },
            }
        )
    by_group.sort(key=lambda r: r["sites"], reverse=True)
    alien = lk.filter(pl.col("liik_tyyp_selg") == "Võõrliik")
    inv = [
        {"name": r["lnim_ryhm_selg"] or "määramata", "sites": r["sites"], "species": r["species"]}
        for r in alien.group_by("lnim_ryhm_selg")
        .agg(sites=pl.len(), species=pl.col("lnim_id").n_unique())
        .sort("sites", descending=True)
        .to_dicts()
    ]
    return {
        "total_sites": lk.height,
        "protected_species_sites": sp.height,
        "alien_sites": alien.height,
        "invasive_sites": int((lk["voorliik_tyyp_selg"] == "Invasiivne").sum()),
        "by_group": by_group,
        "alien_by_group": inv,
        "by_category": {c: int((sp["lnim_kaitsekategooria_selg"] == c).sum()) for c in CATEGORIES},
    }


def registration_year(s: str | None) -> int | None:
    m = YEAR_RE.search(s or "")
    return int(m.group(0)) if m else None


def key_habitats(vp: pl.DataFrame) -> dict[str, Any]:
    """Woodland key habitats: counts, area, contract protection and registration by year."""
    kh = vp.filter(pl.col("tyyp_selg") == "Vääriselupaik").with_columns(
        pl.col("esmane_kp").map_elements(registration_year, return_dtype=pl.Int64).alias("year")
    )
    by_type = [
        {"name": r["veptyyp_selg"] or "määramata", "n": r["n"], "area_ha": r["area_ha"]}
        for r in kh.group_by("veptyyp_selg")
        .agg(n=pl.len(), area_ha=pl.col("pindala").sum())
        .sort("area_ha", descending=True)
        .to_dicts()
    ]
    yearly = (
        kh.filter(pl.col("year").is_between(1990, 2026))
        .group_by("year")
        .agg(n=pl.len(), area_ha=pl.col("pindala").sum())
        .sort("year")
    )
    cum_n = cum_a = 0.0
    series = []
    for r in yearly.to_dicts():
        cum_n += r["n"]
        cum_a += r["area_ha"] or 0.0
        series.append({"year": r["year"], "n": r["n"], "cum_n": cum_n, "cum_area_ha": cum_a})
    own = [
        {
            "name": r["omandiv_selg"] or "määramata",
            "n": r["n"],
            "area_ha": r["area_ha"],
            "with_contract": r["contract"],
        }
        for r in kh.group_by("omandiv_selg")
        .agg(
            n=pl.len(),
            area_ha=pl.col("pindala").sum(),
            contract=(pl.col("kaitse_selg") == "On kehtiv leping").sum(),
        )
        .sort("n", descending=True)
        .to_dicts()
    ]
    return {
        "n": kh.height,
        "area_ha": kh["pindala"].sum(),
        "with_contract": int((kh["kaitse_selg"] == "On kehtiv leping").sum()),
        "by_type": by_type,
        "by_year": series,
        "by_owner": own,
        "year_unparsed": int(kh["year"].is_null().sum()),
    }
