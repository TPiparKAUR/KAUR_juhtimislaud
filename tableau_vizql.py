#!/usr/bin/env python3
"""Anonymous field/sheet discovery for embeddable Tableau views (no PAT needed).

A public Tableau view loads in a browser by (1) fetching the view page, which embeds a
``tsConfigContainer`` JSON with a session id, and (2) POSTing ``bootstrapSession`` to ``/vizql``.
The bootstrap response describes the workbook as the viewer sees it: sheet names and the field
captions of the data behind each sheet.  This script performs exactly those two requests that
every visitor's browser makes, for views the owner already publishes, and records only the
**names** (sheets, fields, data source captions) - never the data values.

The response format is not a documented API and may change; parsing is deliberately generic
(it collects well-known keys wherever they occur) and failures are recorded per view.

Usage
-----
    uv run python tableau_vizql.py --inventory data/kaur_viz_inventar.csv --out out
"""

from __future__ import annotations

import argparse
import html
import http.cookiejar
import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tableau_catalog import TABLEAU_HOSTS, USER_AGENT, Response, read_views, write_csv

LOG = logging.getLogger("tableau_vizql")
MAX_BYTES = 30 * 1024 * 1024
FIELD_KEYS = {"fieldCaption": "field", "datasourceCaption": "datasource", "sheetName": "sheet"}
STATUS_FIELDS = [
    "host",
    "workbook",
    "view",
    "config_status",
    "bootstrap_status",
    "n_fields",
    "n_sheets",
    "n_datasources",
    "error",
]
NAME_FIELDS = ["host", "workbook", "view", "kind", "name"]
RE_CONFIG = re.compile(
    r'<textarea[^>]*id="tsConfigContainer"[^>]*>(.*?)</textarea>', re.DOTALL | re.IGNORECASE
)

Http = Callable[[str, bytes | None], Response]


def make_session_http(timeout: float = 120.0) -> Http:
    """HTTP callable (GET, or POST when a body is given) with a cookie jar shared across calls."""
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )

    def call(url: str, data: bytes | None = None) -> Response:
        req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT})
        try:
            with opener.open(req, timeout=timeout) as resp:
                body = resp.read(MAX_BYTES + 1)
                return Response(
                    resp.status,
                    resp.headers.get("Content-Type", ""),
                    body[:MAX_BYTES],
                    truncated=len(body) > MAX_BYTES,
                )
        except urllib.error.HTTPError as exc:
            return Response(exc.code, "", b"", error=str(exc))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return Response(0, "", b"", error=str(exc))

    return call


def parse_ts_config(page: str) -> dict[str, Any] | None:
    """The ``tsConfigContainer`` JSON of a Tableau view page, or None."""
    m = RE_CONFIG.search(page)
    if not m:
        return None
    try:
        cfg = json.loads(html.unescape(m.group(1)))
    except json.JSONDecodeError:
        return None
    return cfg if isinstance(cfg, dict) else None


def parse_bootstrap(text: str) -> dict[str, Any] | None:
    """First JSON document of a ``<len>;<json><len>;<json>`` bootstrap response."""
    head, sep, rest = text.partition(";")
    if not sep or not head.strip().isdigit():
        return None
    try:
        doc = json.loads(rest[: int(head)])
    except json.JSONDecodeError:
        return None
    return doc if isinstance(doc, dict) else None


def collect_names(node: Any, found: dict[str, set[str]] | None = None) -> dict[str, set[str]]:
    """Gather values of the keys in ``FIELD_KEYS`` anywhere in a nested structure."""
    found = found if found is not None else {"field": set(), "sheet": set(), "datasource": set()}
    if isinstance(node, dict):
        for k, v in node.items():
            kind = FIELD_KEYS.get(k)
            if kind and isinstance(v, str) and v.strip():
                found[kind].add(v.strip())
            else:
                collect_names(v, found)
    elif isinstance(node, list):
        for v in node:
            collect_names(v, found)
    return found


def probe_view(http: Http, host: str, workbook: str, view: str) -> dict[str, Any]:
    """Run config + bootstrap for one view; return status fields plus ``names``."""
    out: dict[str, Any] = {
        "host": host,
        "workbook": workbook,
        "view": view,
        "config_status": "",
        "bootstrap_status": "",
        "n_fields": "",
        "n_sheets": "",
        "n_datasources": "",
        "error": "",
        "names": {},
    }
    if not view or view == "(ei tuvastatud)":
        out["error"] = "view name unknown (shared link)"
        return out
    page_url = (
        f"https://{host}/views/{urllib.parse.quote(workbook)}/{urllib.parse.quote(view)}"
        "?:embed=y&:showVizHome=no"
    )
    page = http(page_url, None)
    out["config_status"] = page.status
    if page.status != 200:
        out["error"] = page.error or f"view page HTTP {page.status}"
        return out
    cfg = parse_ts_config(page.body.decode("utf-8", errors="replace"))
    if not cfg or "sessionid" not in cfg:
        out["error"] = "no tsConfigContainer/sessionid in page"
        return out
    root = str(cfg.get("vizql_root") or "/vizql")
    url = f"https://{host}{root}/bootstrapSession/sessions/{urllib.parse.quote(str(cfg['sessionid']))}"
    form = urllib.parse.urlencode({"sheet_id": str(cfg.get("sheetId", ""))}).encode()
    boot = http(url, form)
    out["bootstrap_status"] = boot.status
    if boot.status != 200 or boot.truncated:
        out["error"] = boot.error or ("bootstrap truncated" if boot.truncated else "")
        return out
    doc = parse_bootstrap(boot.body.decode("utf-8", errors="replace"))
    if doc is None:
        out["error"] = "bootstrap response not in '<len>;<json>' format"
        return out
    names = collect_names(doc)
    out.update(
        n_fields=len(names["field"]),
        n_sheets=len(names["sheet"]),
        n_datasources=len(names["datasource"]),
        names=names,
    )
    return out


def default_views_from_profiles(out: Path) -> list[tuple[str, str, str]]:
    """Default views of every workbook in ``profile_*.json`` files written by tableau_catalog."""
    views: list[tuple[str, str, str]] = []
    for path in sorted(out.glob("profile_*.json")):
        for page in json.loads(path.read_text(encoding="utf-8")):
            for w in page.get("contents", []):
                repo = str(w.get("workbookRepoUrl", ""))
                view = str(w.get("defaultViewRepoUrl", "")).split("/sheets/", 1)[-1]
                if repo and view and "/" not in view:
                    views.append(("public.tableau.com", repo, view))
    return views


def run(
    inventories: list[Path], out: Path, delay: float, limit: int | None, http: Http | None = None
) -> None:
    http = http or make_session_http()
    targets = sorted({*read_views(inventories), *default_views_from_profiles(out)})
    targets = [t for t in targets if t[0] in TABLEAU_HOSTS][:limit]
    LOG.info("probing %d views", len(targets))
    status: list[dict[str, Any]] = []
    names: list[dict[str, Any]] = []
    for i, (host, wb, view) in enumerate(targets, 1):
        res = probe_view(http, host, wb, view)
        for kind, values in res.pop("names").items():
            names += [
                {"host": host, "workbook": wb, "view": view, "kind": kind, "name": n}
                for n in sorted(values)
            ]
        status.append(res)
        LOG.info(
            "[%d/%d] %s/%s config=%s bootstrap=%s fields=%s %s",
            i,
            len(targets),
            wb,
            view,
            res["config_status"],
            res["bootstrap_status"],
            res["n_fields"],
            res["error"],
        )
        time.sleep(delay)
    write_csv(out / "tableau_vizql_status.csv", STATUS_FIELDS, status)
    write_csv(out / "tableau_vizql_names.csv", NAME_FIELDS, names)
    ok = sum(1 for s in status if s["n_fields"] != "")
    LOG.info("%d/%d views parsed, %d names", ok, len(status), len(names))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--inventory", type=Path, action="append", required=True)
    ap.add_argument("--out", type=Path, default=Path("out"))
    ap.add_argument("--delay", type=float, default=3.0)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(args.inventory, args.out, args.delay, args.limit)


if __name__ == "__main__":
    main()
