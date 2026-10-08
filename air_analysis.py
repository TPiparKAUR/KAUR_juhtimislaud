"""Ambient air quality monitoring (programme "Välisõhu kvaliteedi seire" and Tahkuse complex study).

Input: rows of the indicator group "Saasteained välisõhus" from ``monitoring_extract.py``.
Rows are treated as *daily means per station* (assumption derived from the row counts: about 365
rows per station and year for the continuous gases and particulates).  Heavy metals, benzene and
benzo(a)pyrene have far fewer samples per year (indicative measurements).

Per indicator the output holds, per year, the distribution of *station annual means* over stations
with enough days (no station codes are published), a fixed-station paired comparison between the
first and the last years, and the reference levels used.  Station type (urban, traffic,
background) is not in the table, so values must not be read as population exposure.
"""

from __future__ import annotations

from typing import Any

import polars as pl

PROGRAMME_PREFIX = "Välisõhu kvaliteedi"
GROUP = "Saasteained välisõhus"
CONTINUOUS_MIN_SHARE = 0.75  # of 365 days
INDICATIVE_MIN_DAYS = 52  # about 14 % of the year
PAIR_YEARS = 3

# name -> target unit, annual EU limit/target now and from 2030, WHO 2021 level, measurement kind
SPEC: dict[str, dict[str, Any]] = {
    "Lämmastikdioksiid": {"unit": "µg/m³", "limit": 40.0, "limit2030": 20.0, "who": 10.0},
    "Peened osakesed (PM 10)": {"unit": "µg/m³", "limit": 40.0, "limit2030": 20.0, "who": 15.0},
    "Eriti peened osakesed (PM 2,5)": {
        "unit": "µg/m³",
        "limit": 25.0,
        "limit2030": 10.0,
        "who": 5.0,
    },
    "Osoon": {"unit": "µg/m³"},
    "Vääveldioksiid": {"unit": "µg/m³"},
    "Süsinikoksiid": {"unit": "mg/m³"},
    "Benseen": {"unit": "µg/m³", "limit": 5.0, "limit2030": 3.4, "kind": "indicative"},
    "Benso(a)püreen": {"unit": "ng/m³", "limit": 1.0, "limit2030": 1.0, "kind": "indicative"},
    "Arseen": {"unit": "ng/m³", "limit": 6.0, "limit2030": 6.0, "kind": "indicative"},
    "Kaadmium": {"unit": "ng/m³", "limit": 5.0, "limit2030": 5.0, "kind": "indicative"},
    "Nikkel": {"unit": "ng/m³", "limit": 20.0, "limit2030": 20.0, "kind": "indicative"},
    "Plii": {"unit": "ng/m³", "limit": 500.0, "limit2030": 500.0, "kind": "indicative"},
}
FACTORS = {
    ("ng/m³", "µg/m³"): 1e-3,
    ("µg/m³", "ng/m³"): 1e3,
}
PM10_DAILY_LIMIT = 50.0
PM10_ALLOWED_DAYS = 35


def has_air(df: pl.DataFrame) -> bool:
    """True when the extract carries air-quality rows (columns and the indicator group)."""
    need = {"naitaja_grupp_selg", "seiretoo_nimetus", "seirekoht_kood", "naitaja_abr_unit"}
    return need <= set(df.columns) and bool((df["naitaja_grupp_selg"] == GROUP).any())


def prepare(df: pl.DataFrame) -> pl.DataFrame:
    """Numeric rows of the air indicators with station, day and year."""
    return df.filter(
        pl.col("naitaja_grupp_selg").eq(GROUP)
        & pl.col("seiretoo_nimetus").str.starts_with(PROGRAMME_PREFIX)
        & pl.col("vaartus_arv_moodetud").is_not_null()
        & pl.col("naitaja_nimetus").is_in(list(SPEC))
    ).with_columns(
        pl.col("seireaeg_algus").str.slice(0, 10).alias("day"),
        pl.col("seireaeg_algus").str.slice(0, 4).cast(pl.Int32, strict=False).alias("year"),
    )


def value_column(d: pl.DataFrame, name: str) -> tuple[pl.DataFrame, dict[str, int]]:
    """Rows of one indicator in the target unit, plus counts of rows left out and why."""
    target = SPEC[name]["unit"]
    g = d.filter(pl.col("naitaja_nimetus") == name)
    total = g.height
    to_target = {target: 1.0} | {src: f for (src, dst), f in FACTORS.items() if dst == target}
    factor = pl.col("naitaja_abr_unit").replace_strict(
        to_target, default=None, return_dtype=pl.Float64
    )
    g = g.with_columns((pl.col("vaartus_arv_moodetud") * factor).alias("v"))
    wrong_unit = g.filter(pl.col("v").is_null()).height
    g = g.filter(pl.col("v").is_not_null())
    negative = g.filter(pl.col("v") < 0).height
    g = g.filter(pl.col("v") >= 0)
    return g, {"rows": total, "other_unit": wrong_unit, "negative_or_sentinel": negative}


def daily(g: pl.DataFrame) -> pl.DataFrame:
    return g.group_by("seirekoht_kood", "year", "day").agg(
        v=pl.col("v").mean(), below_loq=pl.col("vaartus_erimark").is_not_null().any()
    )


def station_years(day: pl.DataFrame, indicative: bool) -> pl.DataFrame:
    """Annual mean per station and year with the data-completeness rule applied."""
    t = day.group_by("seirekoht_kood", "year").agg(
        days=pl.len(),
        mean=pl.col("v").mean(),
        loq_days=pl.col("below_loq").sum(),
        over50=(pl.col("v") > PM10_DAILY_LIMIT).sum(),
    )
    need = INDICATIVE_MIN_DAYS if indicative else CONTINUOUS_MIN_SHARE * 365
    return t.filter(pl.col("days") >= need).sort("year", "seirekoht_kood")


def by_year(sy: pl.DataFrame, name: str) -> list[dict[str, Any]]:
    out = []
    for (year,), t in sy.group_by("year", maintain_order=True):
        row: dict[str, Any] = {
            "year": year,
            "stations": t.height,
            "median": t["mean"].median(),
            "min": t["mean"].min(),
            "max": t["mean"].max(),
            "days": int(t["days"].sum()),
            "loq_share": float(t["loq_days"].sum()) / float(t["days"].sum()),
        }
        if name == "Peened osakesed (PM 10)":
            row["over50_max"] = int(t["over50"].max())  # type: ignore[arg-type]
            row["over50_stations_above_allowed"] = int((t["over50"] > PM10_ALLOWED_DAYS).sum())
        out.append(row)
    return sorted(out, key=lambda r: r["year"])


def paired(sy: pl.DataFrame) -> dict[str, Any] | None:
    """Stations with a complete year in both the first and the last ``PAIR_YEARS`` years."""
    years = sorted(sy["year"].unique().to_list())
    if len(years) < 2 * PAIR_YEARS:
        return None
    first, last = years[:PAIR_YEARS], years[-PAIR_YEARS:]
    a = (
        sy.filter(pl.col("year").is_in(first))
        .group_by("seirekoht_kood")
        .agg(a=pl.col("mean").mean())
    )
    b = (
        sy.filter(pl.col("year").is_in(last))
        .group_by("seirekoht_kood")
        .agg(b=pl.col("mean").mean())
    )
    w = a.join(b, on="seirekoht_kood", how="inner")
    if w.is_empty():
        return None
    change = (w["b"] / w["a"] - 1.0) * 100.0 if (w["a"] > 0).all() else None
    return {
        "first_years": [first[0], first[-1]],
        "last_years": [last[0], last[-1]],
        "stations": w.height,
        "median_first": w["a"].median(),
        "median_last": w["b"].median(),
        "median_change_pct": None if change is None else change.median(),
        "share_decreased": float((w["b"] < w["a"]).sum()) / w.height,
    }


def build(df: pl.DataFrame) -> dict[str, Any]:
    d = prepare(df)
    indicators: dict[str, Any] = {}
    for name, spec in SPEC.items():
        g, left_out = value_column(d, name)
        if g.is_empty():
            continue
        indicative = spec.get("kind") == "indicative"
        day = daily(g)
        sy = station_years(day, indicative)
        years = by_year(sy, name)
        if not years:
            continue
        indicators[name] = {
            "unit": spec["unit"],
            "kind": "indicative" if indicative else "continuous",
            "limit": spec.get("limit"),
            "limit2030": spec.get("limit2030"),
            "who": spec.get("who"),
            "years": years,
            "paired": paired(sy),
            "left_out": left_out,
        }
    return {
        "meta": {
            "programmes": sorted(d["seiretoo_nimetus"].str.strip_chars().unique().to_list()),
            "interpretation": [
                "Read on tõlgendatud kui jaamade päevakeskmised (eeldus: ridade arv ≈ 365 päeva "
                "kohta jaama ja aasta kohta); mõõtmise ajaline samm ei ole tabelis kinnitatud.",
                "Aasta keskmine arvutatakse jaama kohta ainult siis, kui jaamal on vähemalt 75% "
                "aasta päevi (pidevmõõtmine) või vähemalt 52 päeva (indikatiivne mõõtmine: "
                "raskmetallid, benseen, benso(a)püreen; ligikaudu 14% aastast, kinnitamata). "
                "Pildil on jaamade aastakeskmiste mediaan ning vähim ja suurim jaam; jaamade "
                "koode ei avaldata.",
                "Jaama tüüp (linn, liiklus, taust) ei ole tabelis; väärtused ei kirjelda "
                "elanikkonna kokkupuudet ja jaamade hulk muutub aastate vahel.",
                "Ühikud: ainult µg/m³ read gaaside ja tahkete osakeste puhul (ppbv read on välja "
                "jäetud, sest teisendus vajab temperatuuri ja rõhku); raskmetallid on ng/m³ "
                "(µg/m³ read korrutatud 1000-ga; ühiku märgistuse õigsus on kinnitamata). "
                "Negatiivsed ja puuduvate väärtuste koodid (näiteks -999) on välja jäetud.",
                "Võrdlustasemed (EL aastapiir- ja sihtväärtused ning 2030. aasta tasemed, WHO "
                "2021 soovituslikud tasemed) on sisestatud käsitsi ja tuleb enne kasutamist "
                "õigusakti tekstist üle kontrollida; need on võrdlus, mitte vastavushinnang, "
                "sest jaamade tüüp ja mõõtmise kvaliteedinõuded ei ole tabelis.",
                "Osooni 8-tunni liikuva keskmise sihtväärtust ei saa päevakeskmistest arvutada.",
            ],
        },
        "checks": {
            "rows": d.height,
            "stations": d["seirekoht_kood"].n_unique(),
            "units": d["naitaja_abr_unit"].value_counts().to_dicts(),
        },
        "indicators": indicators,
    }
