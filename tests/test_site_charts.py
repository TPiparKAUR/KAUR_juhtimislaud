"""End-to-end: synthetic analysis -> climate.json -> built site -> charts render without errors."""

from __future__ import annotations

import functools
import http.server
import json
import socketserver
import threading
from collections.abc import Iterator
from pathlib import Path

import polars as pl
import pytest
from playwright.sync_api import Browser, sync_playwright
from playwright.sync_api import Error as PlaywrightError

import build_site as b
import climate_analysis as ca
import run_airenergy as ra
import run_climate as rc
import run_hydro as rh
import run_waste as rw
from tests.test_airenergy_analysis import emissions, heat_rows
from tests.test_climate_analysis import STATIONS
from tests.test_run_climate import monthly_frame
from tests.test_run_hydro import CATALOG, frame
from tests.test_waste_analysis import frame as waste_frame

CHROMIUM_FALLBACK = Path("/opt/pw-browsers/chromium")


def synthetic_daily(code: str, base: float, amp: float) -> pl.DataFrame:
    rows = [
        (s, y, 1 + (d // 31) % 12, base + amp * ((d + i + y) % 7 - 3))
        for i, s in enumerate(STATIONS)
        for y in range(1991, 2026)
        for d in range(366)
    ]
    return pl.DataFrame(rows, schema=["jaam_kood", "aasta", "kuu", "vaartus"], orient="row")


@pytest.fixture(scope="module")
def site(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    tmp = tmp_path_factory.mktemp("site")
    stations = pl.DataFrame(
        {
            "jaam_kood": STATIONS,
            "laiuskraad": 58.0,
            "pikkuskraad": 25.0,
            "korgus_merepinnast_m": 10.0,
        }
    )
    elements = pl.DataFrame(
        {
            "element_kood": [rc.TEMP, rc.PREC],
            "element_nimi": ["T", "P"],
            "element_nimi_eng": ["Temp", "Prec"],
            "element_yhik_eng": ["°C", "mm"],
        }
    )
    idx = ca.daily_indices(
        synthetic_daily("x", 8, 5), synthetic_daily("n", -2, 5), synthetic_daily("p", 1, 2)
    )
    checks = {
        "monthly_vs_daily_mean_temperature": {
            "station": "AJHARK01",
            "months_compared": 10,
            "max_abs_diff_degC": 0.05,
            "median_abs_diff_degC": 0.02,
        }
    }
    data = rc.build(monthly_frame(), idx, stations, elements, checks, reps=50)
    fd = data["extremes"]["FD"]
    assert fd["mean"] and fd["trend"]["n"] == len(fd["aasta"])  # trend is computed on the mean
    cj = tmp / "climate.json"
    cj.write_text(json.dumps(data), encoding="utf-8")
    hydro = rh.build(frame(list(range(1, 8)), {2020, 2023}), CATALOG, climate=data)
    assert hydro["climate_link"] is not None  # synthetic years overlap with the climate series
    hj = tmp / "hydro.json"
    hj.write_text(json.dumps(hydro), encoding="utf-8")
    em = emissions().with_columns(
        aine_arvestus_meetod=pl.lit("AS"), cas_kood=pl.lit("124-38-9"), luba_versioon=pl.lit(1)
    )
    air = ra.build(em, heat_rows([]), generated="2026-01-01T00:00:00+00:00")
    aj = tmp / "airenergy.json"
    aj.write_text(json.dumps(air), encoding="utf-8")
    wj = tmp / "waste.json"
    wj.write_text(json.dumps(rw.build(waste_frame(), None, "2026-01-01")), encoding="utf-8")
    topics = b.load_topics(Path("data/teemad.toml"), Path("data/kaur_viz_inventar.csv"))
    out = tmp / "_site"
    b.build(topics, out, cj, hj, aj, wj)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(out))
    handler.log_message = lambda *a, **k: None  # type: ignore[attr-defined]
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as srv:
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        yield f"http://127.0.0.1:{srv.server_address[1]}"
        srv.shutdown()


@pytest.fixture(scope="module")
def browser() -> Iterator[Browser]:
    with sync_playwright() as pw:
        try:
            br = pw.chromium.launch()
        except PlaywrightError:
            if not CHROMIUM_FALLBACK.exists():
                pytest.skip("no Chromium available")
            br = pw.chromium.launch(executable_path=str(CHROMIUM_FALLBACK))
        yield br
        br.close()


@pytest.mark.browser
@pytest.mark.parametrize(
    "path,min_svgs",
    [
        ("index.html", 3),
        ("ilm-ja-kliima.html", 13),
        ("vesi.html", 9),
        ("valisohk.html", 4),
        ("energeetika.html", 1),
        ("jaatmed.html", 4),
    ],
)
def test_pages_render_charts_without_errors(
    browser: Browser, site: str, path: str, min_svgs: int
) -> None:
    page = browser.new_page(viewport={"width": 1000, "height": 800})
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.route("**/public.tableau.com/**", lambda r: r.abort())  # embeds are not under test
    page.goto(f"{site}/{path}")
    page.wait_for_selector("svg[role=img]")
    page.wait_for_timeout(300)
    real_errors = [e for e in errors if "tableau" not in e.lower() and "ERR_FAILED" not in e]
    assert real_errors == []
    assert page.locator("svg[role=img]").count() >= min_svgs
    assert page.locator(".viz-table table").count() >= 1  # text/table view exists
    assert page.locator(".viz-title").count() >= min_svgs - 1
    assert "Graafikut ei saanud joonistada" not in page.content()
    assert "undefined" not in page.inner_text("main") and "NaN" not in page.inner_text("main")
    page.close()


@pytest.mark.browser
def test_hover_shows_tooltip(browser: Browser, site: str) -> None:
    page = browser.new_page(viewport={"width": 1000, "height": 800})
    page.route("**/public.tableau.com/**", lambda r: r.abort())
    page.goto(f"{site}/index.html")
    page.wait_for_selector("svg[role=img]")
    svg = page.locator("[data-climate=annual] svg").first
    box = svg.bounding_box()
    assert box is not None
    page.mouse.move(box["x"] + box["width"] * 0.5, box["y"] + 100)
    page.wait_for_timeout(100)
    assert page.locator(".viz-tip").is_visible()
    assert "jaama" in page.locator(".viz-tip").inner_text()
    page.close()
