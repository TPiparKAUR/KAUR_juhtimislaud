"""Analysis of facility-reported air emissions and heat/electricity production (KOTKAS 2019-2025).

Pure functions on Polars frames.  Findings of the grain diagnostics drive every rule here:

* Amounts are converted to tonnes (``t``, ``kg``, ``mg``); rows with an unknown unit are dropped
  and counted.
* ``CO2`` (fossil) and ``CO2 bio`` (biomass) are separate substance groups in the source and are
  never added together.
* Rows sharing (report, source, substance, fuel) are NOT always true duplicates (they differ in
  calculation method or CAS code).  Totals therefore use all rows as reported, and
  ``dedup_gap`` quantifies how much would change if only one row per key were kept.
* Fuel quantities repeat across substance rows of the same source in the emission table, so fuel
  is taken from the heat table only.
* Heat and electricity are per-row (per fuel) values and additive.  Their unit is not in the
  schema; heat/fuel ratios match MWh (natural gas ~8.6 MWh per 1000 Nm3, wood chips ~2.3 MWh/t),
  so MWh is assumed.  Rows whose heat/fuel ratio is far from the fuel's median are treated as unit
  or entry errors and excluded.
* No company or facility identity leaves this module: only aggregates.
"""

from __future__ import annotations

from typing import Any

import polars as pl

TO_TONNES = {"t": 1.0, "kg": 1e-3, "mg": 1e-9}
CO2, CO2_BIO = "CO2", "CO2 bio"
POLLUTANTS = {
    "NO2": "NOx (NO2-na)",
    "SO2": "SO2",
    "NH3": "NH3",
    "CO": "CO",
    "LOÜ": "NMVOC (LOÜ)",
    "PM10": "PM10",
    "PM2,5": "PM2,5",
}
# EMEP/EEA NFR sector names for the codes that matter most; unlisted codes show the code only.
NFR_NAMES = {
    "1A1a": "Avalik elektri- ja soojatootmine",
    "1A1b": "Naftatöötlemine",
    "1A1c": "Tahkete kütuste valmistamine",
    "1A2a": "Raua ja terase tootmine (põletus)",
    "1A2b": "Mitteraudmetallid (põletus)",
    "1A2c": "Keemia (põletus)",
    "1A2d": "Tselluloos, paber, trükk (põletus)",
    "1A2e": "Toiduainetööstus (põletus)",
    "1A2f": "Mittemetallilised mineraalid (põletus)",
    "1A2gviii": "Muu töötlev tööstus (põletus)",
    "1A4ai": "Äri- ja avalik sektor (põletus)",
    "1A4bi": "Kodumajapidamised (põletus)",
    "1A4ci": "Põllu-, metsa- ja kalamajandus (põletus)",
    "2C1": "Raua ja terase tootmine (protsess)",
    "2D3d": "Katmine (lahustid)",
    "2D3e": "Rasvaeemaldus (lahustid)",
    "2D3i": "Muu lahustite kasutus",
    "3B1a": "Piimakarjad (sõnnik)",
    "3B1b": "Muu veis (sõnnik)",
    "3B3": "Sead (sõnnik)",
    "3Dc": "Põllumajanduse tegevused",
}
FUEL_GROUPS = [
    ("Puit ja biomass", ("puidu", "küttepuud", "puidugraan", "hake", "biogaas", "must leelis")),
    ("Põlevkivi", ("põlevkivi keevkihtpõletamisel", "põlevkivi tolmpõletamisel")),
    ("Põlevkiviõli", ("põlevkiviõli",)),
    ("Maagaas", ("maagaas",)),
    ("Tööstus- ja muud gaasid", ("generaatorgaas", "poolkoksigaas", "muud gaaskütused")),
    ("Turvas", ("turvas",)),
    ("Jäätmed", ("olmejäätmed", "jäätmed")),
    ("Nafta- ja veeldatud gaasid", ("diisel", "kütteõli", "veeldatud", "lpg", "lng", "bensiin")),
]
RATIO_LOW, RATIO_HIGH = 0.1, 10.0  # heat/fuel accepted around the fuel's median ratio


def prepare_emissions(df: pl.DataFrame) -> tuple[pl.DataFrame, dict[str, int]]:
    """Add ``amount_t`` and drop rows with unknown units; returns the frame and a drop count."""
    d = df.with_columns(
        amount_t=pl.col("aine_kogus_maarus_yhik").cast(pl.Float64)
        * pl.col("aine_yhik_maarus").replace_strict(
            TO_TONNES, default=None, return_dtype=pl.Float64
        ),
        ets=pl.col("ets_kohuslane").fill_null("teadmata"),
    )
    bad = d.filter(pl.col("amount_t").is_null())
    return d.filter(pl.col("amount_t").is_not_null()), {"rows_unknown_unit": bad.height}


def yearly_totals(df: pl.DataFrame, groups: list[str]) -> pl.DataFrame:
    """Tonnes per year for the given ``aine_stat_grupp`` values."""
    return (
        df.filter(pl.col("aine_stat_grupp").is_in(groups))
        .group_by("aruanne_aasta", "aine_stat_grupp")
        .agg(tonnes=pl.col("amount_t").sum(), reports=pl.col("aruanne_id").n_unique())
        .sort("aine_stat_grupp", "aruanne_aasta")
    )


def dedup_gap(df: pl.DataFrame, groups: list[str]) -> pl.DataFrame:
    """Relative difference between all-rows totals and one-row-per-key totals.

    Key = report, source, substance name, fuel.  ``gap_share`` is the share of the all-rows total
    that would disappear if only the first row of each key were kept.
    """
    d = df.filter(pl.col("aine_stat_grupp").is_in(groups))
    key = ["aruanne_id", "heiteallikas_kood", "aine_nimetus", "kytus_kood"]
    first = d.group_by(key, maintain_order=True).agg(
        pl.col("aruanne_aasta").first(),
        pl.col("aine_stat_grupp").first(),
        first_t=pl.col("amount_t").first(),
    )
    a = d.group_by("aruanne_aasta", "aine_stat_grupp").agg(all_t=pl.col("amount_t").sum())
    b = first.group_by("aruanne_aasta", "aine_stat_grupp").agg(first_t=pl.col("first_t").sum())
    return (
        a.join(b, on=["aruanne_aasta", "aine_stat_grupp"], how="left")
        .with_columns(gap_share=(pl.col("all_t") - pl.col("first_t")) / pl.col("all_t"))
        .sort("aine_stat_grupp", "aruanne_aasta")
    )


def sector_totals(df: pl.DataFrame, group: str, top: int = 8) -> pl.DataFrame:
    """Tonnes by NFR sector and year for one substance group; smaller sectors fold into 'Muu'."""
    d = df.filter(pl.col("aine_stat_grupp") == group).with_columns(
        nfr=pl.col("tegevusala_nfr").fill_null("teadmata")
    )
    ranked = d.group_by("nfr").agg(t=pl.col("amount_t").sum()).sort("t", descending=True)
    keep = ranked.head(top)["nfr"].to_list()
    return (
        d.with_columns(
            sector=pl.when(pl.col("nfr").is_in(keep)).then(pl.col("nfr")).otherwise(pl.lit("Muu"))
        )
        .group_by("aruanne_aasta", "sector")
        .agg(tonnes=pl.col("amount_t").sum())
        .sort("sector", "aruanne_aasta")
    )


def county_totals(df: pl.DataFrame, group: str) -> pl.DataFrame:
    return (
        df.filter(pl.col("aine_stat_grupp") == group)
        .with_columns(county=pl.col("tegevuskoht_maakond_nimi_curr").fill_null("teadmata"))
        .group_by("aruanne_aasta", "county")
        .agg(tonnes=pl.col("amount_t").sum())
        .sort("county", "aruanne_aasta")
    )


def ets_split(df: pl.DataFrame, group: str) -> pl.DataFrame:
    return (
        df.filter(pl.col("aine_stat_grupp") == group)
        .group_by("aruanne_aasta", "ets")
        .agg(tonnes=pl.col("amount_t").sum())
        .sort("ets", "aruanne_aasta")
    )


def concentration(df: pl.DataFrame, group: str, tops: tuple[int, ...] = (1, 5, 10)) -> pl.DataFrame:
    """Share of a substance's yearly total from the largest N reports (identities not kept)."""
    per = (
        df.filter(pl.col("aine_stat_grupp") == group)
        .group_by("aruanne_aasta", "aruanne_id")
        .agg(t=pl.col("amount_t").sum())
    )
    rows = []
    for year in sorted(per["aruanne_aasta"].unique().to_list()):
        v = per.filter(pl.col("aruanne_aasta") == year)["t"].sort(descending=True)
        total = float(v.sum())
        row: dict[str, Any] = {"aruanne_aasta": year, "reports": v.len(), "total_t": total}
        for n in tops:
            row[f"top{n}_share"] = float(v.head(n).sum()) / total if total > 0 else None
        rows.append(row)
    return pl.DataFrame(rows)


def fuel_group(name: str | None) -> str:
    n = (name or "").lower()
    for label, keys in FUEL_GROUPS:
        if any(k in n for k in keys):
            return label
    return "Muu"


def prepare_heat(df: pl.DataFrame) -> tuple[pl.DataFrame, dict[str, Any]]:
    """Group fuels and screen rows whose heat/fuel ratio is far from the fuel's median ratio."""
    d = df.with_columns(
        fuel=pl.col("kytus_nimetus_val").map_elements(fuel_group, return_dtype=pl.Utf8),
        ratio=pl.when(pl.col("kytus_kogus") > 0).then(
            pl.col("soojus_kokku") / pl.col("kytus_kogus")
        ),
    )
    med = (
        d.filter((pl.col("soojus_kokku") > 0) & pl.col("ratio").is_not_null())
        .group_by("kytus_nimetus_val", "kytus_yhik")
        .agg(med_ratio=pl.col("ratio").median())
    )
    d = d.join(med, on=["kytus_nimetus_val", "kytus_yhik"], how="left").with_columns(
        no_fuel=(pl.col("soojus_kokku") > 0) & ~(pl.col("kytus_kogus") > 0),
        off_ratio=(pl.col("soojus_kokku") > 0)
        & pl.col("ratio").is_not_null()
        & pl.col("med_ratio").is_not_null()
        & (
            (pl.col("ratio") > RATIO_HIGH * pl.col("med_ratio"))
            | (pl.col("ratio") < RATIO_LOW * pl.col("med_ratio"))
        ),
    )
    flagged = d.filter(pl.col("no_fuel") | pl.col("off_ratio"))
    report = {
        "rows": d.height,
        "flagged_rows": flagged.height,
        "flagged_heat_by_year": flagged.group_by("aruanne_aasta")
        .agg(heat=pl.col("soojus_kokku").sum(), rows=pl.len())
        .sort("aruanne_aasta")
        .to_dicts(),
        "rule": (
            f"heat/fuel outside {RATIO_LOW}x..{RATIO_HIGH}x of the fuel's median ratio, "
            "or heat without fuel"
        ),
    }
    clean = d.filter(~(pl.col("no_fuel") | pl.col("off_ratio")))
    return clean, report


def energy_by_fuel(heat: pl.DataFrame) -> pl.DataFrame:
    """Heat and electricity (assumed MWh) by fuel group and year; additive over rows."""
    return (
        heat.group_by("aruanne_aasta", "fuel")
        .agg(
            heat=pl.col("soojus_kokku").sum(),
            electricity=pl.col("elekter_kokku").sum(),
            reports=pl.col("aruanne_id").n_unique(),
        )
        .sort("fuel", "aruanne_aasta")
    )
