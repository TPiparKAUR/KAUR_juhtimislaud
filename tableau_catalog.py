#!/usr/bin/env python3
"""Catalogue the data reachable through KAUR's Tableau views (Tableau Public + tableau.envir.ee).

Three independent probes, each logged and tolerant of failure so one blocked endpoint does not
lose the others:

1. ``--profile``: enumerate a Tableau Public profile's workbooks (undocumented JSON endpoint,
   response shape is NOT guaranteed; the raw response is saved to ``profile_<name>.json``).
2. ``serverinfo``: unauthenticated Tableau Server REST ``serverinfo`` of ``tableau.envir.ee``
   (version/product, shows whether the REST API is reachable at all).
3. For every view in the inventory: request ``<view URL>.csv`` (the data behind the view as
   Tableau exposes it) and record status, row count and column names.  The data itself is NOT
   stored - only the schema - because redistribution needs a licence check per dataset.

4. For every workbook of the profile: download ``/workbooks/<repo>.twbx`` (falling back to ``.twb``)
   when the author allows it and read the workbook XML (datasources, fields, worksheets,
   dashboards).  Only the structure is recorded; the packaged data extract is discarded.

Outputs in ``--out``: ``tableau_catalog.csv`` (one row per view), ``tableau_columns.csv`` (one row
per view column), ``tableau_public_workbooks.csv`` / ``_sheets.csv`` / ``_datasources.csv`` /
``_fields.csv`` (workbook structure) and ``tableau_probes.json`` (profile/serverinfo status).
No credentials are used.

Usage
-----
    uv run python tableau_catalog.py --inventory data/kaur_viz_inventar.csv --out out
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any
from urllib.parse import quote

LOG = logging.getLogger("tableau_catalog")
USER_AGENT = "kaur-juhtimislaud-catalog/0.1 (+https://github.com/TPiparKAUR/KAUR_juhtimislaud)"
MAX_BYTES = 20 * 1024 * 1024
MAX_WORKBOOK_BYTES = 300 * 1024 * 1024
MAX_TWB_XML_BYTES = 100 * 1024 * 1024
TABLEAU_HOSTS = ("public.tableau.com", "tableau.envir.ee")
PROFILE_ENDPOINT = "https://public.tableau.com/public/apis/workbooks"
SERVERINFO_URL = "https://tableau.envir.ee/api/3.0/serverinfo"
CATALOG_FIELDS = [
    "host",
    "workbook",
    "view",
    "csv_url",
    "status",
    "content_type",
    "bytes",
    "truncated",
    "rows",
    "n_columns",
    "error",
]
COLUMN_FIELDS = ["host", "workbook", "view", "position", "column"]
WORKBOOK_FIELDS = [
    "workbook",
    "title",
    "default_view",
    "view_count",
    "in_inventory",
    "download",
    "http_status",
    "bytes",
    "n_datasources",
    "n_worksheets",
    "n_dashboards",
    "error",
]
SHEET_FIELDS = ["workbook", "sheet", "kind"]
DATASOURCE_FIELDS = ["workbook", "datasource", "caption", "connection", "n_fields"]
FIELD_FIELDS = ["workbook", "datasource", "field", "caption", "datatype", "role", "calculated"]

Fetch = Callable[[str], "Response"]


@dataclass
class Response:
    status: int
    content_type: str
    body: bytes
    truncated: bool = False
    error: str = ""


def http_get(url: str, timeout: float = 120.0, max_bytes: int = MAX_BYTES) -> Response:
    """GET ``url`` with a size cap; never raises for HTTP/network errors."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(max_bytes + 1)
            return Response(
                resp.status,
                resp.headers.get("Content-Type", ""),
                body[:max_bytes],
                truncated=len(body) > max_bytes,
            )
    except urllib.error.HTTPError as exc:
        return Response(exc.code, exc.headers.get("Content-Type", ""), b"", error=str(exc))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return Response(0, "", b"", error=str(exc))


def view_csv_url(host: str, workbook: str, view: str) -> str:
    """URL of the CSV export of a view; shared links (no view name) use ``/shared/<id>``."""
    if not view or view == "(ei tuvastatud)":
        return f"https://{host}/shared/{quote(workbook)}.csv"
    return f"https://{host}/views/{quote(workbook)}/{quote(view)}.csv"


def parse_csv(body: bytes) -> tuple[list[str], int]:
    """Return (column names, data-row count) of a CSV payload (UTF-8, BOM tolerated)."""
    text = body.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    header = next(reader, [])
    return header, sum(1 for _ in reader)


def looks_like_csv(resp: Response) -> bool:
    ctype = resp.content_type.lower()
    return resp.status == 200 and "html" not in ctype and bool(resp.body)


def probe_view(
    fetch: Fetch, host: str, workbook: str, view: str
) -> tuple[dict[str, Any], list[str]]:
    """Probe one view; returns (catalog row, column names)."""
    url = view_csv_url(host, workbook, view)
    resp = fetch(url)
    row: dict[str, Any] = {
        "host": host,
        "workbook": workbook,
        "view": view,
        "csv_url": url,
        "status": resp.status,
        "content_type": resp.content_type,
        "bytes": len(resp.body),
        "truncated": "jah" if resp.truncated else "",
        "rows": "",
        "n_columns": "",
        "error": resp.error,
    }
    columns: list[str] = []
    if looks_like_csv(resp):
        columns, n_rows = parse_csv(resp.body)
        row["n_columns"] = len(columns)
        # A truncated payload cuts the last row, so the count is only a lower bound.
        row["rows"] = n_rows
    elif resp.status == 200:
        row["error"] = row["error"] or "200 but not CSV (HTML login/error page?)"
    return row, columns


def find_workbooks(data: Any) -> list[dict[str, Any]]:
    """Collect dicts that look like Tableau Public workbook records, wherever they are nested."""
    found: list[dict[str, Any]] = []
    if isinstance(data, dict):
        if "workbookRepoUrl" in data:
            found.append(data)
        for v in data.values():
            found.extend(find_workbooks(v))
    elif isinstance(data, list):
        for v in data:
            found.extend(find_workbooks(v))
    return found


def probe_profile(fetch: Fetch, profile: str, out: Path, page_size: int = 50) -> dict[str, Any]:
    """Page through a Tableau Public profile's workbooks; save raw JSON; return a status dict."""
    workbooks: list[dict[str, Any]] = []
    raw_pages: list[Any] = []
    status = 0
    for start in range(0, 2000, page_size):
        url = (
            f"{PROFILE_ENDPOINT}?profileName={quote(profile)}"
            f"&start={start}&count={page_size}&visibility=NON_HIDDEN"
        )
        resp = fetch(url)
        status = resp.status
        if resp.status != 200:
            LOG.warning("profile %s: HTTP %s %s", profile, resp.status, resp.error)
            break
        try:
            data = json.loads(resp.body)
        except json.JSONDecodeError:
            LOG.warning("profile %s: response is not JSON", profile)
            break
        raw_pages.append(data)
        page = find_workbooks(data)
        workbooks += page
        if len(page) < page_size:
            break
    out.mkdir(parents=True, exist_ok=True)
    (out / f"profile_{profile}.json").write_text(
        json.dumps(raw_pages, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return {
        "profile": profile,
        "http_status": status,
        "workbooks_found": len(workbooks),
        "workbook_repo_urls": sorted({str(w["workbookRepoUrl"]) for w in workbooks}),
        "workbooks": {str(w["workbookRepoUrl"]): w for w in workbooks},
    }


def probe_serverinfo(fetch: Fetch) -> dict[str, Any]:
    resp = fetch(SERVERINFO_URL)
    return {
        "url": SERVERINFO_URL,
        "http_status": resp.status,
        "error": resp.error,
        "body": resp.body[:2000].decode("utf-8", errors="replace"),
    }


def local(tag: str) -> str:
    """XML tag name without namespace."""
    return tag.rsplit("}", 1)[-1]


def inspect_twb(xml_bytes: bytes) -> dict[str, Any]:
    """Extract structure (sheets, dashboards, datasources, fields) from Tableau workbook XML."""
    root = ET.fromstring(xml_bytes)
    sheets: list[tuple[str, str]] = []
    datasources: list[dict[str, Any]] = []
    for el in root.iter():
        tag = local(el.tag)
        if tag in ("worksheet", "dashboard") and el.get("name"):
            sheets.append((el.get("name", ""), tag))
        if tag == "datasource" and el.get("name") and el.get("name") != "Parameters":
            conns = sorted({c.get("class", "") for c in el.iter() if local(c.tag) == "connection"})
            fields = [
                {
                    "field": c.get("name", ""),
                    "caption": c.get("caption", ""),
                    "datatype": c.get("datatype", ""),
                    "role": c.get("role", ""),
                    "calculated": any(local(k.tag) == "calculation" for k in c),
                }
                for c in el
                if local(c.tag) == "column"
            ]
            datasources.append(
                {
                    "name": el.get("name", ""),
                    "caption": el.get("caption", ""),
                    "connection": "|".join(x for x in conns if x),
                    "fields": fields,
                }
            )
    # Worksheets also appear nested inside dashboards as <zone name=..>; only top-level counted.
    return {"sheets": sorted(set(sheets)), "datasources": datasources}


def twb_from_package(body: bytes) -> bytes:
    """Return the workbook XML from a ``.twbx`` zip or a bare ``.twb`` payload."""
    if body[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(body)) as zf:
            for info in zf.infolist():
                if info.filename.lower().endswith(".twb"):
                    if info.file_size > MAX_TWB_XML_BYTES:
                        raise ValueError(f"workbook XML too large: {info.file_size}")
                    return zf.read(info)
        raise ValueError("no .twb inside package")
    return body


def probe_workbook(fetch_big: Fetch, repo: str) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Try ``.twbx`` then ``.twb`` download; return (status row, parsed structure or None)."""
    row: dict[str, Any] = {"download": "", "http_status": "", "bytes": "", "error": ""}
    for ext in ("twbx", "twb"):
        resp = fetch_big(f"https://public.tableau.com/workbooks/{quote(repo)}.{ext}")
        row.update(download=ext, http_status=resp.status, bytes=len(resp.body), error=resp.error)
        if resp.status != 200 or not resp.body:
            continue
        if resp.truncated:
            row["error"] = f"larger than {MAX_WORKBOOK_BYTES} bytes, skipped"
            return row, None
        try:
            return row, inspect_twb(twb_from_package(resp.body))
        except (ET.ParseError, zipfile.BadZipFile, ValueError) as exc:
            row["error"] = f"unparsable {ext}: {exc}"
            return row, None
    return row, None


def read_views(paths: Iterable[Path]) -> list[tuple[str, str, str]]:
    """Unique (host, workbook, view) triples on Tableau hosts from the given CSV files."""
    seen: dict[tuple[str, str, str], None] = {}
    for path in paths:
        with path.open(encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                host = (r.get("host") or "").strip().lower()
                if host in TABLEAU_HOSTS and r.get("workbook"):
                    seen[(host, r["workbook"].strip(), (r.get("view") or "").strip())] = None
    return sorted(seen)


def write_csv(path: Path, fields: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def catalog_workbooks(
    fetch_big: Fetch,
    profile: dict[str, Any],
    inventory_workbooks: set[str],
    out: Path,
    delay: float,
) -> None:
    """Download and inspect every workbook of a profile; write the four workbook-level CSVs."""
    wb_rows: list[dict[str, Any]] = []
    sheet_rows: list[dict[str, Any]] = []
    ds_rows: list[dict[str, Any]] = []
    field_rows: list[dict[str, Any]] = []
    known = {w.casefold() for w in inventory_workbooks}
    for repo, meta in sorted(profile["workbooks"].items()):
        row, info = probe_workbook(fetch_big, repo)
        row.update(
            workbook=repo,
            title=meta.get("title", ""),
            default_view=meta.get("defaultViewName", ""),
            view_count=meta.get("viewCount", ""),
            in_inventory="jah" if repo.casefold() in known else "ei",
            n_datasources="",
            n_worksheets="",
            n_dashboards="",
        )
        if info:
            row.update(
                n_datasources=len(info["datasources"]),
                n_worksheets=sum(1 for _, k in info["sheets"] if k == "worksheet"),
                n_dashboards=sum(1 for _, k in info["sheets"] if k == "dashboard"),
            )
            sheet_rows += [{"workbook": repo, "sheet": n, "kind": k} for n, k in info["sheets"]]
            for ds in info["datasources"]:
                ds_rows.append(
                    {
                        "workbook": repo,
                        "datasource": ds["name"],
                        "caption": ds["caption"],
                        "connection": ds["connection"],
                        "n_fields": len(ds["fields"]),
                    }
                )
                field_rows += [
                    {"workbook": repo, "datasource": ds["name"], **f} for f in ds["fields"]
                ]
        wb_rows.append(row)
        LOG.info("workbook %s: %s %s", repo, row["download"], row["http_status"])
        time.sleep(delay)
    write_csv(out / "tableau_public_workbooks.csv", WORKBOOK_FIELDS, wb_rows)
    write_csv(out / "tableau_public_sheets.csv", SHEET_FIELDS, sheet_rows)
    write_csv(out / "tableau_public_datasources.csv", DATASOURCE_FIELDS, ds_rows)
    write_csv(out / "tableau_public_fields.csv", FIELD_FIELDS, field_rows)
    LOG.info(
        "%d workbooks, %d sheets, %d datasources, %d fields",
        len(wb_rows),
        len(sheet_rows),
        len(ds_rows),
        len(field_rows),
    )


def run(
    inventories: list[Path],
    out: Path,
    profiles: list[str],
    delay: float,
    fetch: Fetch = http_get,
    fetch_big: Fetch | None = None,
) -> None:
    fetch_big = fetch_big or partial(http_get, max_bytes=MAX_WORKBOOK_BYTES)
    profile_results = [probe_profile(fetch, p, out) for p in profiles]
    probes: dict[str, Any] = {
        "serverinfo": probe_serverinfo(fetch),
        "profiles": [{k: v for k, v in r.items() if k != "workbooks"} for r in profile_results],
    }
    views = read_views(inventories)
    inventory_workbooks = {wb for host, wb, _ in views if host == "public.tableau.com"}
    for res in profile_results:
        catalog_workbooks(fetch_big, res, inventory_workbooks, out, delay)
    LOG.info("probing %d views", len(views))
    catalog: list[dict[str, Any]] = []
    columns: list[dict[str, Any]] = []
    for i, (host, wb, view) in enumerate(views, 1):
        row, cols = probe_view(fetch, host, wb, view)
        catalog.append(row)
        columns += [
            {"host": host, "workbook": wb, "view": view, "position": n, "column": c}
            for n, c in enumerate(cols, 1)
        ]
        LOG.info(
            "[%d/%d] %s/%s -> HTTP %s, %s rows",
            i,
            len(views),
            wb,
            view,
            row["status"],
            row["rows"] or "-",
        )
        time.sleep(delay)
    write_csv(out / "tableau_catalog.csv", CATALOG_FIELDS, catalog)
    write_csv(out / "tableau_columns.csv", COLUMN_FIELDS, columns)
    (out / "tableau_probes.json").write_text(
        json.dumps(probes, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    ok = sum(1 for r in catalog if r["n_columns"] != "")
    LOG.info("%d/%d views returned CSV data; %d columns catalogued", ok, len(catalog), len(columns))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--inventory",
        type=Path,
        action="append",
        required=True,
        help="inventory/crawl CSV with host,workbook,view columns (repeatable)",
    )
    ap.add_argument("--out", type=Path, default=Path("out"))
    ap.add_argument(
        "--profile",
        action="append",
        default=["keskkonnaagentuur.kaur"],
        help="Tableau Public profile name (repeatable)",
    )
    ap.add_argument("--delay", type=float, default=1.0)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(args.inventory, args.out, sorted(set(args.profile)), args.delay)


if __name__ == "__main__":
    main()
