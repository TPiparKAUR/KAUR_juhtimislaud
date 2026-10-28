"""Greenhouse gas emissions by source sector (Eurostat ``env_air_gge``, UNFCCC CRF categories).

Input: long Parquet from ``eurostat_fetch.py`` (columns ``src_crf``, ``geo``, ``time``, ``value``;
airpol = GHG, unit = million tonnes CO2 equivalent) for Estonia and the EU27.  The data are the
national inventory submissions aggregated by Eurostat, not Environment Agency measurements; the
latest year is typically a proxy/early estimate.  Totals are shown excluding and including LULUCF
(CRF 4, usually a net sink).  Sector shares use the total *excluding* LULUCF.
"""

from __future__ import annotations

from typing import Any

import polars as pl

TOTAL_EX = "TOTX4_MEMO"
TOTAL_IN = "TOTXMEMO"
MAIN = {
    "CRF1": "Energia",
    "CRF2": "Tööstusprotsessid ja tootekasutus",
    "CRF3": "Põllumajandus",
    "CRF5": "Jäätmed",
}
ENERGY = {
    "CRF1A1": "Energiatööstus (elekter, soojus, rafineerimine)",
    "CRF1A2": "Töötlev tööstus ja ehitus",
    "CRF1A3": "Transport",
    "CRF1A4": "Kodumajapidamised, teenindus, põllumajandus",
    "CRF1B": "Fugitiivsed heited",
}
LULUCF = "CRF4"


def series(df: pl.DataFrame, geo: str, code: str) -> dict[int, float]:
    t = df.filter((pl.col("geo") == geo) & (pl.col("src_crf") == code)).drop_nulls("value")
    return {
        int(y): float(v) for y, v in zip(t["time"].to_list(), t["value"].to_list(), strict=True)
    }


def rows(df: pl.DataFrame, geo: str, codes: dict[str, str]) -> list[dict[str, Any]]:
    s = {label: series(df, geo, code) for code, label in codes.items()}
    total = series(df, geo, TOTAL_EX)
    years = sorted(total)
    out = []
    for y in years:
        row: dict[str, Any] = {"year": y, "total": total[y]}
        used = 0.0
        for label, v in s.items():
            row[label] = v.get(y)
            used += v.get(y) or 0.0
        row["Muu"] = max(0.0, total[y] - used)
        out.append(row)
    return out


def index_vs_first(s: dict[int, float], base: int) -> dict[int, float]:
    b = s.get(base)
    return {y: 100.0 * v / b for y, v in s.items()} if b else {}


def comparison(df: pl.DataFrame, base: int = 1990) -> list[dict[str, Any]]:
    ee = index_vs_first(series(df, "EE", TOTAL_EX), base)
    eu = index_vs_first(series(df, "EU27_2020", TOTAL_EX), base)
    ee_en = index_vs_first(series(df, "EE", "CRF1"), base)
    return [
        {"year": y, "ee_total": ee.get(y), "eu_total": eu.get(y), "ee_energy": ee_en.get(y)}
        for y in sorted(ee)
    ]


def build(df: pl.DataFrame, generated: str) -> dict[str, Any]:
    total_in = series(df, "EE", TOTAL_IN)
    lulucf = series(df, "EE", LULUCF)
    return {
        "meta": {
            "generated_utc": generated,
            "source": "Eurostat env_air_gge (UNFCCC CRF; kasvuhoonegaaside inventuur)",
            "interpretation": [
                "Andmed on riiklik kasvuhoonegaaside inventuur (UNFCCC CRF kategooriad), mille "
                "Eurostat on koondanud; need ei ole Keskkonnaagentuuri mõõtmised ja viimane aasta "
                "võib olla esialgne (proxy) hinnang.",
                "Ühik on miljonit tonni CO2 ekvivalenti (kõik kasvuhoonegaasid, GWP kaalutud). "
                "Sektorite osakaalud on arvutatud kogusummast ilma LULUCF-ita (maakasutus, "
                "maakasutuse muutus ja metsandus; netonõrist või netoallikas, sõltuvalt aastast).",
                "Energiasektori alamsektorid (CRF 1A1, 1A2, 1A3, 1A4, 1B); rahvusvaheline "
                "lennundus ja laevandus on memo-kirjed ja kogusummas ei sisaldu.",
                "Võrdlus EL27-ga on indeksina (1990 = 100), mitte absoluutse tasemena; "
                "baasaasta tulemuste muutused ja metoodikaparandused mõjutavad indekseid.",
                "Litsents ja viitamise nõue (Eurostat) tuleb enne taaskasutust üle kontrollida.",
            ],
        },
        "sectors": rows(df, "EE", MAIN),
        "energy": rows_energy(df),
        "comparison": comparison(df),
        "lulucf": [
            {"year": y, "lulucf": lulucf.get(y), "total_incl": total_in.get(y)}
            for y in sorted(total_in)
        ],
    }


def rows_energy(df: pl.DataFrame) -> list[dict[str, Any]]:
    s = {label: series(df, "EE", code) for code, label in ENERGY.items()}
    energy = series(df, "EE", "CRF1")
    out = []
    for y in sorted(energy):
        row: dict[str, Any] = {"year": y, "energy": energy[y]}
        used = 0.0
        for label, v in s.items():
            row[label] = v.get(y)
            used += v.get(y) or 0.0
        row["Muu"] = max(0.0, energy[y] - used)
        out.append(row)
    return out
