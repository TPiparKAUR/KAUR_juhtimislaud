"""Quality gates for the built site: accessibility, layout stability, keyboard access.

Each gate is a published, measurable criterion rather than a taste:

* axe-core with the WCAG 2.0/2.1/2.2 A+AA rule sets must report no violation (WCAG 2.2 is the
  W3C Recommendation of October 2023; EN 301 549 and Directive (EU) 2016/2102 point at it for
  public-sector sites). Automated rules find only part of the problems, so this is a floor.
* Cumulative Layout Shift <= 0.1, the "good" limit of Google's Core Web Vitals. Measured in a lab
  run on a local server, where CLS is structural (content that moves after first paint) and so
  transfers; LCP/INP are not asserted because they do not.
* One Tab stop per chart (WAI-ARIA Authoring Practices, roving tabindex). Before the fix a page
  had up to 1902 stops.

All pages are loaded once per viewport and measured together, then asserted one criterion at a
time so a failure names the page and the rule.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import Browser

from tests import test_site_charts as charts

site = charts.site
browser = charts.browser

PAGES = charts.PUNCH_PAGES
VIEWPORTS = {"desktop": {"width": 1280, "height": 900}, "mobile": {"width": 375, "height": 740}}
CLS_LIMIT = 0.1
AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"]

CLS_PROBE = """
window.__cls = 0;
new PerformanceObserver((list) => {
  for (const e of list.getEntries()) if (!e.hadRecentInput) window.__cls += e.value;
}).observe({ type: 'layout-shift', buffered: true });
"""

TAB_STOPS_PER_CHART = """() => [...document.querySelectorAll('svg[role=img]')]
  .map((svg) => svg.querySelectorAll('[tabindex="0"]').length)"""


@dataclass(frozen=True)
class Measured:
    cls: float
    violations: list[dict[str, Any]]
    tab_stops: list[int]
    charts_ready: bool
    hidden: bool


Measure = Callable[[str, str], Measured]


@pytest.fixture(scope="module")
def measure(browser: Browser, site: str) -> Measure:
    cache: dict[tuple[str, str], Measured] = {}

    def run(path: str, viewport: str) -> Measured:
        key = (path, viewport)
        if key not in cache:
            page = browser.new_page(viewport=VIEWPORTS[viewport])  # type: ignore[arg-type]
            page.route("**/public.tableau.com/**", lambda r: r.abort())  # third-party embeds
            page.add_init_script(CLS_PROBE)
            page.goto(f"{site}/{path}", wait_until="networkidle")
            page.wait_for_timeout(1000)
            axe = Axe().run(page, options={"runOnly": {"type": "tag", "values": AXE_TAGS}})
            cache[key] = Measured(
                cls=float(page.evaluate("window.__cls")),
                violations=axe.response["violations"],
                tab_stops=page.evaluate(TAB_STOPS_PER_CHART),
                charts_ready=not page.evaluate(
                    "document.documentElement.classList.contains('js-loading')"
                ),
                hidden=not page.locator("main h2").first.is_visible(),
            )
            page.close()
        return cache[key]

    return run


def describe(violations: list[dict[str, Any]]) -> str:
    return json.dumps(
        [
            {
                "rule": v["id"],
                "impact": v["impact"],
                "nodes": len(v["nodes"]),
                "e.g.": v["nodes"][0]["target"] if v["nodes"] else None,
            }
            for v in violations
        ],
        ensure_ascii=False,
    )


@pytest.mark.browser
@pytest.mark.parametrize("viewport", VIEWPORTS)
@pytest.mark.parametrize("path", PAGES)
def test_axe_finds_no_violations(measure: Measure, path: str, viewport: str) -> None:
    violations = measure(path, viewport).violations
    assert violations == [], describe(violations)


@pytest.mark.browser
@pytest.mark.parametrize("viewport", VIEWPORTS)
@pytest.mark.parametrize("path", PAGES)
def test_layout_does_not_shift(measure: Measure, path: str, viewport: str) -> None:
    cls = measure(path, viewport).cls
    assert cls <= CLS_LIMIT, f"CLS {cls:.3f} > {CLS_LIMIT} (Core Web Vitals 'good')"


@pytest.mark.browser
@pytest.mark.parametrize("path", PAGES)
def test_each_chart_is_one_tab_stop(measure: Measure, path: str) -> None:
    stops = measure(path, "desktop").tab_stops
    assert stops, "page has no charts"
    assert max(stops) <= 1, f"{sum(1 for s in stops if s > 1)} charts have several Tab stops"


@pytest.mark.browser
@pytest.mark.parametrize("path", PAGES)
def test_body_is_shown_once_charts_are_mounted(measure: Measure, path: str) -> None:
    m = measure(path, "desktop")
    assert m.charts_ready
    assert not m.hidden


@pytest.mark.browser
def test_arrow_keys_move_between_marks_and_keep_a_single_tab_stop(
    browser: Browser, site: str
) -> None:
    page = browser.new_page(viewport=VIEWPORTS["desktop"])  # type: ignore[arg-type]
    page.route("**/public.tableau.com/**", lambda r: r.abort())
    page.goto(f"{site}/ilm-ja-kliima.html", wait_until="networkidle")
    page.focus("svg[role=img] [tabindex='0']")
    state = """() => {
        const svg = document.activeElement.closest('svg');
        const marks = [...svg.querySelectorAll('[tabindex]')];
        return { index: marks.indexOf(document.activeElement),
                 tabbable: marks.filter((m) => m.getAttribute('tabindex') === '0').length,
                 total: marks.length };
    }"""
    assert page.evaluate(state)["index"] == 0
    page.keyboard.press("ArrowRight")
    page.keyboard.press("ArrowRight")
    after = page.evaluate(state)
    assert after["index"] == 2
    assert after["tabbable"] == 1  # roving: only the focused mark is tabbable
    tip = page.locator(".viz-tip")
    first_tip = tip.inner_text()
    page.keyboard.press("End")
    assert page.evaluate(state)["index"] == after["total"] - 1
    assert tip.inner_text() != first_tip  # the tooltip follows keyboard focus
    page.keyboard.press("Home")
    assert page.evaluate(state)["index"] == 0
    page.close()


@pytest.mark.browser
def test_page_is_readable_without_javascript(browser: Browser, site: str) -> None:
    """Without JS the loading class is never set, so nothing may be hidden."""
    ctx = browser.new_context(java_script_enabled=False)
    page = ctx.new_page()
    page.goto(f"{site}/vesi.html")
    assert page.locator("main h2").first.is_visible()
    ctx.close()


@pytest.mark.browser
def test_body_is_revealed_even_if_the_ready_script_fails(browser: Browser, site: str) -> None:
    """The head script's timer is the failsafe: a broken asset must not leave a blank page."""
    page = browser.new_page(viewport=VIEWPORTS["desktop"])  # type: ignore[arg-type]
    page.route("**/public.tableau.com/**", lambda r: r.abort())
    page.route("**/assets/page-ready.js", lambda r: r.abort())
    page.goto(f"{site}/vesi.html", wait_until="domcontentloaded")
    page.wait_for_function(
        "!document.documentElement.classList.contains('js-loading')", timeout=9000
    )
    assert page.locator("main h2").first.is_visible()
    page.close()
