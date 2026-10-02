"""Tests for the pure helpers and the in-browser collector of ``crawl_kaur_viz``."""

from __future__ import annotations

import csv
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Browser, sync_playwright
from playwright.sync_api import Error as PlaywrightError

import crawl_kaur_viz as c

CHROMIUM_FALLBACK = Path("/opt/pw-browsers/chromium")

SITEMAP_INDEX = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>http://keskkonnaportaal.ee/et/sitemap.xml?page=1</loc></sitemap>
  <sitemap><loc> http://keskkonnaportaal.ee/et/sitemap.xml?page=2 </loc></sitemap>
</sitemapindex>"""

URLSET = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://keskkonnaportaal.ee/et/a</loc></url>
  <url><loc>https://keskkonnaportaal.ee/et/b</loc></url>
  <url><loc></loc></url>
</urlset>"""

FIXTURE_HTML = """
<html><body>
  <tableau-viz id="v1" src="https://tableau.envir.ee/views/Kultiveerimismaterjal/Joonis?:embed=y">
  </tableau-viz>
  <iframe src="https://app.powerbi.com/view?r=abc"></iframe>
  <iframe data-src="https://public.tableau.com/views/WB/Lazy?:showVizHome=no"></iframe>
  <iframe src="https://www.youtube.com/embed/xyz"></iframe>
  <img src="https://public.tableau.com/static/images/Ke/WB1/V1/1_rss.png">
  <img src="https://keskkonnaportaal.ee/logo.png">
  <a href="https://public.tableau.com/app/profile/keskkonnaagentuur.kaur">profiil</a>
  <a href="https://example.org/">muu</a>
  <script src="https://public.tableau.com/javascripts/api/tableau.embedding.3.latest.min.js">
  </script>
  <div id="host"></div>
  <script>
    const root = document.getElementById('host').attachShadow({mode: 'open'});
    root.innerHTML = '<iframe src="https://public.tableau.com/views/Shadow/Inside"></iframe>';
  </script>
</body></html>
"""


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://public.tableau.com/views/WB/View?:embed=y", ("WB", "View")),
        ("https://tableau.envir.ee/t/site/views/WB/View#1", ("WB", "View")),
        ("https://public.tableau.com/static/images/Ke/WB1/V1/1_rss.png", ("WB1", "V1")),
        ("https://public.tableau.com/viz/WB2/V2", ("WB2", "V2")),
        ("https://public.tableau.com/views/R%C3%B5ng/Ee", ("Rõng", "Ee")),
        ("https://public.tableau.com/shared/ZB37GT9CT?:display_count=n", ("ZB37GT9CT", "")),
        ("https://app.powerbi.com/view?r=abc", ("", "")),
        ("", ("", "")),
    ],
)
def test_wb_view(url: str, expected: tuple[str, str]) -> None:
    assert c.wb_view(url) == expected


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://public.tableau.com/views/a/b", True),
        ("https://tableau.envir.ee/", True),
        ("https://app.powerbi.com/view", True),
        ("https://storymaps.arcgis.com/stories/x", True),
        ("https://arcg.is/1fP8TD2", True),
        ("https://www.youtube.com/embed/x", False),
        ("https://example.org/tableau", False),  # keyword in path, not host
        ("not a url", False),
    ],
)
def test_is_viz(url: str, expected: bool) -> None:
    assert c.is_viz(url) is expected


def test_parse_sitemap_index_rewrites_http_and_strips_whitespace() -> None:
    is_index, locs = c.parse_sitemap(SITEMAP_INDEX)
    assert is_index
    assert locs == [
        "https://keskkonnaportaal.ee/et/sitemap.xml?page=1",
        "https://keskkonnaportaal.ee/et/sitemap.xml?page=2",
    ]


def test_parse_sitemap_urlset_skips_empty_loc() -> None:
    is_index, locs = c.parse_sitemap(URLSET)
    assert not is_index
    assert locs == ["https://keskkonnaportaal.ee/et/a", "https://keskkonnaportaal.ee/et/b"]


def test_parse_sitemap_rejects_garbage() -> None:
    with pytest.raises(ET.ParseError):
        c.parse_sitemap("<html>not xml")


def test_to_rows_filters_dedups_and_is_deterministic() -> None:
    raw = [
        ["iframe", "https://www.youtube.com/embed/xyz"],
        ["img", "https://keskkonnaportaal.ee/logo.png"],
        ["img", "https://public.tableau.com/other/pixel.gif"],
        ["link", "https://example.org/"],
        ["tableau-viz", "https://tableau.envir.ee/views/K/J?:embed=y"],
        ["tableau-viz", "https://tableau.envir.ee/views/K/J?:embed=y"],
        ["img", "https://public.tableau.com/static/images/Ke/WB1/V1/1_rss.png"],
    ]
    rows = c.to_rows("https://p/", raw)
    assert rows == c.to_rows("https://p/", list(reversed(raw)))
    assert [(r["kind"], r["workbook"], r["view"]) for r in rows] == [
        ("img", "WB1", "V1"),
        ("tableau-viz", "K", "J"),
    ]
    assert {r["page_url"] for r in rows} == {"https://p/"}


def test_write_csv_roundtrip_and_ignores_extra_keys(tmp_path: Path) -> None:
    path = tmp_path / "sub" / "x.csv"
    n = c.write_csv(path, ["a", "b"], [{"a": "1", "b": "ä", "zzz": "dropped"}, {"a": "2"}])
    assert n == 2
    with path.open(encoding="utf-8", newline="") as fh:
        assert list(csv.DictReader(fh)) == [{"a": "1", "b": "ä"}, {"a": "2", "b": ""}]


def test_server_inventory_skipped_without_credentials(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("TABLEAU_PAT_NAME", raising=False)
    monkeypatch.delenv("TABLEAU_PAT_SECRET", raising=False)
    c.inventory_tableau_server(tmp_path)
    assert not (tmp_path / "tableau_envir_inventory.csv").exists()


@pytest.fixture(scope="module")
def browser() -> Iterator[Browser]:
    with sync_playwright() as pw:
        try:
            br = pw.chromium.launch()
        except PlaywrightError:
            if not CHROMIUM_FALLBACK.exists():
                pytest.skip("no Chromium available for Playwright")
            br = pw.chromium.launch(executable_path=str(CHROMIUM_FALLBACK))
        yield br
        br.close()


@pytest.mark.browser
def test_js_collect_sees_light_dom_lazy_iframes_and_shadow_root(browser: Browser) -> None:
    page = browser.new_page()
    # Block all network so the test is hermetic; only the DOM is under test.
    page.route("**/*", lambda route: route.abort())
    page.set_content(FIXTURE_HTML)
    rows = c.to_rows("https://p/", page.evaluate(c.JS_COLLECT))
    got = {(r["kind"], r["workbook"], r["view"]) for r in rows}
    assert ("tableau-viz", "Kultiveerimismaterjal", "Joonis") in got
    assert ("iframe", "WB", "Lazy") in got  # data-src
    assert ("iframe", "Shadow", "Inside") in got  # open shadow root
    assert ("img", "WB1", "V1") in got
    assert ("iframe", "", "") in got  # Power BI
    kinds_hosts = {(r["kind"], r["host"]) for r in rows}
    assert ("link", "public.tableau.com") in kinds_hosts
    assert ("script", "public.tableau.com") in kinds_hosts
    assert not any("youtube" in r["src"] or "example.org" in r["src"] for r in rows)
