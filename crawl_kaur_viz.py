#!/usr/bin/env python3
"""Crawl keskkonnaportaal.ee and inventory the embedded visualisations.

Renders every page from the sitemap in a headless browser (so that JS-built
``<tableau-viz>`` web components and their shadow-DOM iframes are visible) and
records Tableau / Power BI / ArcGIS embeds and links.  Optionally lists the
content of ``tableau.envir.ee`` via the Tableau Server REST API when a personal
access token is supplied through environment variables.

Usage
-----
    pip install playwright tableauserverclient   # tableauserverclient optional
    playwright install chromium
    python crawl_kaur_viz.py --out out --delay 1.0
    # optional, for tableau.envir.ee (never put credentials in code):
    export TABLEAU_PAT_NAME=... TABLEAU_PAT_SECRET=... TABLEAU_SITE=""

Status: UNTESTED draft (written without network access to the target sites).
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Page, sync_playwright

LOG = logging.getLogger("crawl_kaur_viz")
SITEMAP_INDEX = "https://keskkonnaportaal.ee/sitemap.xml"
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
VIZ_HOSTS = ("tableau", "powerbi.com", "arcgis.com", "arcg.is", "storymaps")

# Collects embeds from light DOM and from open shadow roots.
JS_COLLECT = r"""
() => {
  const out = [];
  const add = (kind, src) => { if (src) out.push([kind, src]); };
  const walk = (root) => {
    root.querySelectorAll('tableau-viz').forEach(e => add('tableau-viz', e.getAttribute('src')));
    root.querySelectorAll('iframe').forEach(e => add('iframe', e.src));
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


def wb_view(url: str) -> tuple[str, str]:
    """Return (workbook, view) parsed from a Tableau URL, else empty strings."""
    for rx in (RE_VIEWS, RE_STATIC, RE_VIZ):
        m = rx.search(url)
        if m:
            return m.group(1), m.group(2)
    return "", ""


def is_viz(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return any(h in host for h in VIZ_HOSTS)


def sitemap_urls(page: Page) -> list[str]:
    """Expand the sitemap index (http->https) and return all page URLs."""
    ctx = page.context.request
    index = ET.fromstring(ctx.get(SITEMAP_INDEX).text())
    subs = [e.text.replace("http://", "https://") for e in index.findall(".//s:loc", NS)]
    urls: list[str] = []
    for sub in subs:
        root = ET.fromstring(ctx.get(sub).text())
        urls += [e.text for e in root.findall(".//s:loc", NS)]
    return sorted(set(urls))


def crawl_portal(out: Path, delay: float, max_pages: int | None) -> None:
    rows: list[dict[str, str]] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        urls = sitemap_urls(page)[:max_pages]
        LOG.info("%d pages in sitemap", len(urls))
        for i, url in enumerate(urls, 1):
            try:
                page.goto(url, wait_until="networkidle", timeout=60_000)
                found = page.evaluate(JS_COLLECT)
            except Exception as exc:  # noqa: BLE001 - keep crawling, log the failure
                LOG.warning("%s failed: %s", url, exc)
                rows.append({"page_url": url, "kind": "ERROR", "src": str(exc)})
                continue
            for kind, src in {tuple(x) for x in found}:
                if kind in ("script", "link") and not is_viz(src):
                    continue
                if kind == "img" and "tableau" not in src:
                    continue
                if kind == "iframe" and not is_viz(src):
                    continue
                wb, view = wb_view(src)
                rows.append({"page_url": url, "kind": kind,
                             "host": urlparse(src).netloc, "workbook": wb,
                             "view": view, "src": src})
            LOG.info("[%d/%d] %s", i, len(urls), url)
            time.sleep(delay)
        browser.close()
    out.mkdir(parents=True, exist_ok=True)
    fields = ["page_url", "kind", "host", "workbook", "view", "src"]
    with (out / "portal_embeds.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    LOG.info("wrote %s (%d rows)", out / "portal_embeds.csv", len(rows))


def inventory_tableau_server(out: Path) -> None:
    """List projects, workbooks, views and data sources on tableau.envir.ee."""
    name = os.environ.get("TABLEAU_PAT_NAME")
    secret = os.environ.get("TABLEAU_PAT_SECRET")
    if not (name and secret):
        LOG.warning("TABLEAU_PAT_NAME/SECRET not set - skipping tableau.envir.ee")
        return
    import tableauserverclient as TSC  # optional dependency

    auth = TSC.PersonalAccessTokenAuth(name, secret, os.environ.get("TABLEAU_SITE", ""))
    server = TSC.Server("https://tableau.envir.ee", use_server_version=True)
    rows: list[dict[str, str]] = []
    with server.auth.sign_in(auth):
        for wb in TSC.Pager(server.workbooks):
            server.workbooks.populate_views(wb)
            for v in wb.views:
                rows.append({"type": "view", "project": wb.project_name,
                             "workbook": wb.name, "name": v.name,
                             "content_url": v.content_url or "",
                             "updated_at": str(wb.updated_at)})
        for ds in TSC.Pager(server.datasources):
            rows.append({"type": "datasource", "project": ds.project_name,
                         "workbook": "", "name": ds.name,
                         "content_url": ds.content_url or "",
                         "updated_at": str(ds.updated_at)})
    out.mkdir(parents=True, exist_ok=True)
    fields = ["type", "project", "workbook", "name", "content_url", "updated_at"]
    with (out / "tableau_envir_inventory.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    LOG.info("wrote %d rows from tableau.envir.ee", len(rows))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("out"))
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between pages")
    ap.add_argument("--max-pages", type=int, default=None)
    ap.add_argument("--skip-portal", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not args.skip_portal:
        crawl_portal(args.out, args.delay, args.max_pages)
    inventory_tableau_server(args.out)


if __name__ == "__main__":
    main()
