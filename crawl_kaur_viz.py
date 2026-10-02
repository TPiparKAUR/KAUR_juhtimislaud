#!/usr/bin/env python3
"""Crawl keskkonnaportaal.ee and inventory the embedded visualisations.

Renders every page from the sitemap in a headless browser (so that JS-built
``<tableau-viz>`` web components and their shadow-DOM iframes are visible) and
records Tableau / Power BI / ArcGIS embeds and links.  Optionally lists the
content of ``tableau.envir.ee`` via the Tableau Server REST API when a personal
access token is supplied through environment variables.

Usage
-----
    uv sync --all-extras
    uv run playwright install chromium
    uv run python crawl_kaur_viz.py --out out --delay 1.0
    # optional, for tableau.envir.ee (never put credentials in code):
    export TABLEAU_PAT_NAME=... TABLEAU_PAT_SECRET=... TABLEAU_SITE=""

Outputs ``portal_embeds.csv`` and (with a PAT) ``tableau_envir_inventory.csv``.
The pure parsing helpers are unit-tested; the live crawl needs network access to the
target sites.
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright

LOG = logging.getLogger("crawl_kaur_viz")
SITEMAP_INDEX = "https://keskkonnaportaal.ee/sitemap.xml"
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
VIZ_HOSTS = ("tableau", "powerbi.com", "arcgis.com", "arcg.is", "storymaps")
EMBED_KINDS = ("tableau-viz", "iframe", "img")
PORTAL_FIELDS = ["page_url", "kind", "host", "workbook", "view", "src"]
SERVER_FIELDS = ["type", "project", "workbook", "name", "content_url", "updated_at"]

# Collects embeds from light DOM and from open shadow roots.  Lazy-loaded iframes keep their
# URL in ``data-src`` until scrolled into view, so both attributes are read.
JS_COLLECT = r"""
() => {
  const out = [];
  const add = (kind, src) => { if (src) out.push([kind, src]); };
  const walk = (root) => {
    root.querySelectorAll('tableau-viz').forEach(e => add('tableau-viz', e.getAttribute('src')));
    root.querySelectorAll('iframe').forEach(e => {
      add('iframe', e.src);
      add('iframe', e.getAttribute('data-src'));
    });
    root.querySelectorAll('img').forEach(e => add('img', e.currentSrc || e.src));
    root.querySelectorAll('a[href]').forEach(e => add('link', e.href));
    root.querySelectorAll('script[src]').forEach(e => add('script', e.src));
    root.querySelectorAll('*').forEach(e => { if (e.shadowRoot) walk(e.shadowRoot); });
  };
  walk(document);
  return out;
}
"""

RE_VIEWS = re.compile(r"/views/([^/?#]+)/([^/?#]+)")
RE_STATIC = re.compile(r"/static/images/[^/]+/([^/]+)/([^/]+)/")
RE_VIZ = re.compile(r"/viz/([^/?#]+)/([^/?#]+)")
# Tableau Public share links carry only an opaque id, no workbook/view names.
RE_SHARED = re.compile(r"/shared/([^/?#]+)")


def wb_view(url: str) -> tuple[str, str]:
    """Return (workbook, view) parsed from a Tableau URL, else empty strings.

    Shared links (``/shared/<id>``) yield ``(<id>, "")`` because the id is the only stable key.
    """
    path = unquote(urlparse(url).path)
    for rx in (RE_VIEWS, RE_STATIC, RE_VIZ):
        m = rx.search(path)
        if m:
            return m.group(1), m.group(2)
    m = RE_SHARED.search(path)
    if m:
        return m.group(1), ""
    return "", ""


def is_viz(url: str) -> bool:
    """Return True if the URL host belongs to a known visualisation platform."""
    host = urlparse(url).netloc.lower()
    return any(h in host for h in VIZ_HOSTS)


def to_rows(page_url: str, found: Iterable[Sequence[str]]) -> list[dict[str, str]]:
    """Filter raw ``[kind, src]`` pairs from the browser into sorted, de-duplicated rows.

    Links and scripts are kept only when they point to a visualisation host; embeds
    (``tableau-viz``, ``iframe``, ``img``) must as well, so tracking pixels and unrelated frames
    are dropped.
    """
    rows: list[dict[str, str]] = []
    for kind, src in sorted({(str(x[0]), str(x[1])) for x in found}):
        if not is_viz(src):
            continue
        if kind == "img" and "/static/images/" not in src:
            continue
        wb, view = wb_view(src)
        rows.append(
            {
                "page_url": page_url,
                "kind": kind,
                "host": urlparse(src).netloc,
                "workbook": wb,
                "view": view,
                "src": src,
            }
        )
    return rows


def parse_sitemap(xml_text: str) -> tuple[bool, list[str]]:
    """Parse a sitemap document.

    Returns ``(is_index, locs)``.  ``locs`` are ``https`` URLs; the portal advertises ``http``
    in its sitemap index, which is rewritten.
    """
    root = ET.fromstring(xml_text)
    is_index = root.tag.endswith("sitemapindex")
    locs = [
        (e.text or "").strip().replace("http://", "https://", 1)
        for e in root.findall(".//s:loc", NS)
        if e.text and e.text.strip()
    ]
    return is_index, locs


def fetch_text(page: Page, url: str) -> str:
    """GET ``url`` through the browser context and fail loudly on HTTP errors."""
    resp = page.context.request.get(url)
    if not resp.ok:
        raise RuntimeError(f"GET {url} -> HTTP {resp.status}")
    return resp.text()


def sitemap_urls(page: Page) -> list[str]:
    """Expand the sitemap (index or plain urlset) and return all page URLs."""
    is_index, locs = parse_sitemap(fetch_text(page, SITEMAP_INDEX))
    if not is_index:
        return sorted(set(locs))
    urls: set[str] = set()
    for sub in locs:
        _, sub_locs = parse_sitemap(fetch_text(page, sub))
        urls.update(sub_locs)
    return sorted(urls)


def write_csv(path: Path, fields: list[str], rows: Iterable[dict[str, Any]]) -> int:
    """Write ``rows`` to ``path`` (UTF-8, header first) and return the row count."""
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)
            n += 1
    return n


def crawl_portal(
    out: Path, delay: float, max_pages: int | None, chromium: Path | None = None
) -> None:
    """Render every sitemap page and write ``portal_embeds.csv``."""
    rows: list[dict[str, str]] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=str(chromium) if chromium else None)
        page = browser.new_page()
        urls = sitemap_urls(page)[:max_pages]
        LOG.info("%d pages in sitemap", len(urls))
        for i, url in enumerate(urls, 1):
            try:
                page.goto(url, wait_until="load", timeout=60_000)
                try:  # embeds are injected after load; never fail the page on a busy network
                    page.wait_for_load_state("networkidle", timeout=15_000)
                except PlaywrightError:
                    LOG.debug("%s: network not idle, continuing", url)
                found = page.evaluate(JS_COLLECT)
            except PlaywrightError as exc:
                LOG.warning("%s failed: %s", url, exc)
                rows.append({"page_url": url, "kind": "ERROR", "src": str(exc)})
                continue
            rows += to_rows(url, found)
            LOG.info("[%d/%d] %s", i, len(urls), url)
            time.sleep(delay)
        browser.close()
    n = write_csv(out / "portal_embeds.csv", PORTAL_FIELDS, rows)
    LOG.info("wrote %s (%d rows)", out / "portal_embeds.csv", n)


def inventory_tableau_server(out: Path) -> None:
    """List projects, workbooks, views and data sources on tableau.envir.ee."""
    name = os.environ.get("TABLEAU_PAT_NAME")
    secret = os.environ.get("TABLEAU_PAT_SECRET")
    if not (name and secret):
        LOG.warning("TABLEAU_PAT_NAME/SECRET not set - skipping tableau.envir.ee")
        return
    import tableauserverclient as tsc  # optional dependency (extra: server)

    auth = tsc.PersonalAccessTokenAuth(name, secret, os.environ.get("TABLEAU_SITE", ""))
    server = tsc.Server(  # type: ignore[no-untyped-call]
        "https://tableau.envir.ee", use_server_version=True
    )
    server.add_http_options({"timeout": 60})
    rows: list[dict[str, str]] = []
    with server.auth.sign_in(auth):
        for wb in tsc.Pager(server.workbooks):
            server.workbooks.populate_views(wb)
            for v in wb.views:
                rows.append(
                    {
                        "type": "view",
                        "project": wb.project_name or "",
                        "workbook": wb.name or "",
                        "name": v.name or "",
                        "content_url": v.content_url or "",
                        "updated_at": str(wb.updated_at),
                    }
                )
        for ds in tsc.Pager(server.datasources):
            rows.append(
                {
                    "type": "datasource",
                    "project": ds.project_name or "",
                    "workbook": "",
                    "name": ds.name or "",
                    "content_url": ds.content_url or "",
                    "updated_at": str(ds.updated_at),
                }
            )
    n = write_csv(out / "tableau_envir_inventory.csv", SERVER_FIELDS, rows)
    LOG.info("wrote %d rows from tableau.envir.ee", n)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("out"))
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between pages")
    ap.add_argument("--max-pages", type=int, default=None)
    ap.add_argument("--chromium", type=Path, help="use this Chromium instead of the bundled one")
    ap.add_argument("--skip-portal", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not args.skip_portal:
        try:
            crawl_portal(args.out, args.delay, args.max_pages, args.chromium)
        except RuntimeError as exc:  # sitemap unreachable: report cleanly, no traceback
            LOG.error("portal crawl aborted: %s", exc)
            raise SystemExit(1) from exc
    inventory_tableau_server(args.out)


if __name__ == "__main__":
    main()
