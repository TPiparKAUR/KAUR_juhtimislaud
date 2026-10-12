"""Preliminary breeding-bird index from the point counts of the monitoring table.

Input: rows of the indicator "Liigi haudepaaride arv" (pairs per species and counting point)
from ``monitoring_extract.py``.  Only programme "Haudelinnustiku punktloendused" is used.

Method (simplified, **not** TRIM and not the official index): the table lists only species that
were observed, so zeros are implied for the points surveyed in a year (a point is surveyed in a year
if it has any row that year).  Per species the link ratio between consecutive years is the sum of
counts over points surveyed in both years in year t divided by the same in year t-1 (the larger of
repeated visits is used).  The chain of link ratios gives the species index (base year = 100).  The
composite index is the geometric mean over species whose chain is valid in every year; its
uncertainty is a bootstrap over points.  Points are not a random sample of Estonia and habitats are
not stratified, so the result is a monitoring-network index, not national abundance.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import polars as pl

PROGRAMME = "Haudelinnustiku punktloendused"
FIRST_YEAR = 2010  # earlier years have very few points
MIN_LINK_COUNT = 10.0  # minimum summed pairs (both years) for a valid link ratio
MIN_POINTS_LINK = 20  # minimum points surveyed in both years
BOOTSTRAP = 300
SEED = 20260412


def has_birds(df: pl.DataFrame) -> bool:
    need = {"seiretoo_nimetus", "liik_est", "seirekoht_kood", "vaartus_arv_moodetud"}
    return need <= set(df.columns) and bool(
        df["seiretoo_nimetus"].str.starts_with(PROGRAMME).fill_null(False).any()
    )


def prepare(df: pl.DataFrame) -> pl.DataFrame:
    return (
        df.filter(
            pl.col("seiretoo_nimetus").str.starts_with(PROGRAMME)
            & pl.col("vaartus_arv_moodetud").is_not_null()
            & (pl.col("vaartus_arv_moodetud") >= 0)
            & pl.col("liik_est").is_not_null()
        )
        .with_columns(
            pl.col("seireaeg_algus").str.slice(0, 4).cast(pl.Int32, strict=False).alias("year")
        )
        .filter(pl.col("year") >= FIRST_YEAR)
    )


def cube(d: pl.DataFrame, years: list[int]) -> tuple[list[str], np.ndarray, np.ndarray]:
    """Counts [species, point, year] (max of visits) and surveyed mask [point, year]."""
    pts = sorted(d["seirekoht_kood"].unique().to_list())
    sp = sorted(d["liik_est"].unique().to_list())
    pi = {p: i for i, p in enumerate(pts)}
    si = {s: i for i, s in enumerate(sp)}
    yi = {y: i for i, y in enumerate(years)}
    counts = np.zeros((len(sp), len(pts), len(years)))
    c = d.group_by("liik_est", "seirekoht_kood", "year").agg(v=pl.col("vaartus_arv_moodetud").max())
    for r in c.iter_rows(named=True):
        counts[si[r["liik_est"]], pi[r["seirekoht_kood"]], yi[r["year"]]] = r["v"]
    mask = np.zeros((len(pts), len(years)), dtype=bool)
    for p, y in d.select("seirekoht_kood", "year").unique().iter_rows():
        mask[pi[p], yi[y]] = True
    return sp, counts, mask


def links(
    counts: np.ndarray, mask: np.ndarray, w: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Link ratios [species, year-1], summed counts of the earlier year, and points per link."""
    n_years = counts.shape[2]
    ratio = np.full((counts.shape[0], n_years - 1), np.nan)
    base = np.zeros((counts.shape[0], n_years - 1))
    npts = np.zeros(n_years - 1)
    for t in range(1, n_years):
        both = mask[:, t - 1] & mask[:, t]
        wb = w * both
        npts[t - 1] = float((wb > 0).sum())
        a = counts[:, :, t - 1] @ wb
        b = counts[:, :, t] @ wb
        base[:, t - 1] = a
        ok = (a + b >= MIN_LINK_COUNT) & (a > 0) & (b > 0) & (npts[t - 1] >= MIN_POINTS_LINK)
        ratio[ok, t - 1] = b[ok] / a[ok]
    return ratio, base, npts


def chain(ratio: np.ndarray) -> np.ndarray:
    """Species index (100 in the first year); NaN after the first invalid link."""
    idx = np.full((ratio.shape[0], ratio.shape[1] + 1), np.nan)
    idx[:, 0] = 100.0
    for t in range(ratio.shape[1]):
        idx[:, t + 1] = idx[:, t] * ratio[:, t]
    return idx


def composite(idx: np.ndarray) -> tuple[np.ndarray, int]:
    """Geometric mean (100 in the first year) over species with a valid chain in every year."""
    valid = ~np.isnan(idx).any(axis=1)
    if not valid.any():
        return np.full(idx.shape[1], np.nan), 0
    g = np.exp(np.log(idx[valid] / 100.0).mean(axis=0)) * 100.0
    return g, int(valid.sum())


def build(df: pl.DataFrame) -> dict[str, Any]:
    d = prepare(df)
    years = sorted(d["year"].unique().to_list())
    sp, counts, mask = cube(d, years)
    n_points = mask.shape[0]
    w1 = np.ones(n_points)
    ratio, _, npts = links(counts, mask, w1)
    idx = chain(ratio)
    comp, n_sp = composite(idx)
    valid_species = ~np.isnan(idx).any(axis=1)
    rng = np.random.default_rng(SEED)
    boots = []
    for _ in range(BOOTSTRAP):
        w = np.bincount(rng.integers(0, n_points, n_points), minlength=n_points).astype(float)
        r, _, _ = links(counts, mask, w)
        i, _ = composite(chain(r)[valid_species]) if valid_species.any() else (comp, 0)
        boots.append(i)
    b = np.array(boots)
    lo, hi = np.nanpercentile(b, 2.5, axis=0), np.nanpercentile(b, 97.5, axis=0)
    species: list[dict[str, Any]] = []
    for s in np.flatnonzero(valid_species):
        species.append(
            {
                "name": sp[s],
                "first": 100.0,
                "last": float(idx[s, -1]),
                "pairs_total": float(counts[s].sum()),
            }
        )
    species.sort(key=lambda r: r["last"])
    return {
        "meta": {
            "programme": PROGRAMME,
            "interpretation": [
                "Põhjaks on haudelinnustiku punktloenduste read (liigi haudepaaride arv punktis); "
                "tabelis on ainult nähtud liigid, seega loendatud punktis loetakse mittenähtud "
                "liigi arvuks 0 (punkt on aastas loendatud, kui sel on selle aasta mis tahes "
                "rida).",
                "Indeks on lihtsustatud ahelindeks (mitte TRIM ega ametlik lindude indeks): liigi "
                "aastavahe on kahel järjestikusel aastal loendatud punktide paarisummade suhe; "
                "korduskülastuste suurim väärtus; ahel algab 100-st esimesel aastal.",
                "Koondindeks on geomeetriline keskmine liikidest, mille ahel on kõigil aastatel "
                "kehtiv (vähemalt 10 paari ja 20 punkti iga lüli kohta); 95% vahemik on "
                "punktide bootstrap.",
                "Punktid ei ole Eesti juhuvalim ning elupaigad ei ole kihistatud: tulemus "
                "kirjeldab seirevõrgu punkte, mitte kogu Eesti arvukust. Liikide valik "
                "(ainult liigid, mille ahel on kõigil aastatel kehtiv) võib kallutada "
                "koondindeksit sagedaste liikide poole.",
                "Loendusmeetodi muutused, loendajate vahetused ja punktide lisandumine ei ole "
                "andmetest nähtavad.",
            ],
        },
        "years": years,
        "points_per_link": [int(x) for x in npts],
        "composite": [
            {"year": y, "index": float(c), "lo": float(a), "hi": float(h)}
            for y, c, a, h in zip(years, comp, lo, hi, strict=True)
        ],
        "species_used": n_sp,
        "species_total": len(sp),
        "species": species,
        "checks": {
            "rows": d.height,
            "points": n_points,
            "points_per_year": [int(x) for x in mask.sum(axis=0)],
        },
    }
