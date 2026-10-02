#!/usr/bin/env python3
"""Catalogue KAUR's open data APIs: endpoints, tables, columns and operations.

Reads the endpoint inventory of the sibling repository ``kaur-api-status``
(``config/endpoints.toml``) and enriches it with what the services themselves publish:

* PostgREST (``keskkonnaandmed.envir.ee``, schema profile ``apijahiala``): the root document is an
  OpenAPI description with every table, column, type and column comment.
* OpenAPI/Swagger documents (e.g. KAIA ``swagger.json``): the list of operations.
* Plain JSON/XML endpoints (e.g. EstModel, Ilmateenistus): field names of the first record.

Only read-only ``GET`` requests are made, with a size cap, a delay and no credentials.  Data
values are never stored, only names and types.

Usage
-----
    uv run python api_catalog.py --endpoints ../kaur-api-status/config/endpoints.toml --out out
"""

from __future__ import annotations

import argparse
import json
import logging
import time
import tomllib
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from tableau_catalog import USER_AGENT, Response, write_csv

LOG = logging.getLogger("api_catalog")
POSTGREST_ROOT = "https://keskkonnaandmed.envir.ee/"
POSTGREST_HEADERS = {"Accept-Profile": "apijahiala", "Accept": "application/openapi+json"}
PROBE_MAX_BYTES = 512 * 1024
OPENAPI_MAX_BYTES = 20 * 1024 * 1024

ENDPOINT_FIELDS = [
    "id",
    "system",
    "group",
    "method",
    "url",
    "expect",
    "source",
    "verified",
    "enabled",
    "probe",
    "http_status",
    "content_type",
    "bytes",
    "error",
]
TABLE_FIELDS = ["api", "table", "description", "n_columns"]
COLUMN_FIELDS = ["api", "table", "column", "type", "format", "required", "description"]
OPERATION_FIELDS = ["api", "method", "path", "summary", "operation_id"]

Fetch = Callable[[str, Mapping[str, str], int], Response]


def fetch_with_headers(url: str, headers: Mapping[str, str], max_bytes: int) -> Response:
    """GET with custom headers via ``tableau_catalog.http_get`` machinery (size-capped)."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **headers}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
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


def load_endpoints(path: Path) -> list[dict[str, Any]]:
    """Endpoint tables from a ``kaur-api-status`` ``endpoints.toml``."""
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    eps = data.get("endpoint", [])
    if not isinstance(eps, list):
        raise ValueError("endpoints.toml: [[endpoint]] must be an array of tables")
    return [dict(e) for e in eps]


def is_postgrest(ep: Mapping[str, Any]) -> bool:
    return "Accept-Profile" in (ep.get("headers") or {})


def parse_openapi_schemas(doc: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Return ``{table: {description, required, properties}}`` from Swagger 2 or OpenAPI 3."""
    if isinstance(doc.get("definitions"), dict):
        schemas = doc["definitions"]
    else:
        schemas = (doc.get("components") or {}).get("schemas") or {}
    out: dict[str, dict[str, Any]] = {}
    for name, sch in schemas.items():
        if isinstance(sch, dict) and isinstance(sch.get("properties"), dict):
            out[name] = {
                "description": sch.get("description", ""),
                "required": set(sch.get("required", [])),
                "properties": sch["properties"],
            }
    return out


def schema_rows(
    api: str, schemas: Mapping[str, Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    tables: list[dict[str, Any]] = []
    columns: list[dict[str, Any]] = []
    for name in sorted(schemas):
        sch = schemas[name]
        props: Mapping[str, Any] = sch["properties"]
        tables.append(
            {"api": api, "table": name, "description": sch["description"], "n_columns": len(props)}
        )
        for col, p in props.items():
            p = p if isinstance(p, dict) else {}
            columns.append(
                {
                    "api": api,
                    "table": name,
                    "column": col,
                    "type": p.get("type", ""),
                    "format": p.get("format", ""),
                    "required": "jah" if col in sch["required"] else "",
                    "description": str(p.get("description", "")).replace("\n", " "),
                }
            )
    return tables, columns


def parse_operations(api: str, doc: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path, item in (doc.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        for method, op in item.items():
            if method.lower() in {"get", "post", "put", "patch", "delete", "head"} and isinstance(
                op, dict
            ):
                rows.append(
                    {
                        "api": api,
                        "method": method.upper(),
                        "path": path,
                        "summary": op.get("summary", ""),
                        "operation_id": op.get("operationId", ""),
                    }
                )
    return sorted(rows, key=lambda r: (r["path"], r["method"]))


def json_fields(value: Any) -> dict[str, str]:
    """Field name -> JSON type of the first record in a payload (list, or object wrapping one)."""
    rec: Any = value
    for _ in range(3):  # unwrap {"data": [...]} style envelopes
        if isinstance(rec, list):
            rec = rec[0] if rec else {}
        elif (
            isinstance(rec, dict)
            and len(rec) <= 3
            and any(isinstance(v, list) for v in rec.values())
        ):
            rec = next(v for v in rec.values() if isinstance(v, list))
        else:
            break
    if not isinstance(rec, dict):
        return {}
    names = {
        bool: "boolean",
        int: "integer",
        float: "number",
        str: "string",
        list: "array",
        dict: "object",
        type(None): "null",
    }
    return {k: names.get(type(v), "unknown") for k, v in rec.items()}


def xml_fields(body: bytes) -> dict[str, str]:
    """Child element names (and attributes) of the first repeated record element in an XML doc."""
    root = ET.fromstring(body)
    counts: dict[str, int] = {}
    for child in root:
        counts[child.tag] = counts.get(child.tag, 0) + 1
    if not counts:
        return {}
    record_tag = max(counts, key=lambda t: counts[t])
    first = next(c for c in root if c.tag == record_tag)
    fields = {f"@{a}": "attribute" for a in first.attrib}
    fields.update({c.tag: "element" for c in first})
    return fields


def probe_endpoint(
    fetch: Fetch, ep: Mapping[str, Any], api: str
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Probe a plain endpoint; returns (probe columns for the endpoint row, columns, operations)."""
    headers = {str(k): str(v) for k, v in (ep.get("headers") or {}).items()}
    max_bytes = min(int(ep.get("max_bytes", PROBE_MAX_BYTES)), OPENAPI_MAX_BYTES)
    resp = fetch(str(ep["url"]), headers, max_bytes)
    info: dict[str, Any] = {
        "probe": "jah",
        "http_status": resp.status,
        "content_type": resp.content_type,
        "bytes": len(resp.body),
        "error": resp.error,
    }
    columns: list[dict[str, Any]] = []
    operations: list[dict[str, Any]] = []
    if resp.status != 200 or not resp.body:
        return info, columns, operations
    table = urlsplit(str(ep["url"])).path.strip("/") or str(ep["id"])
    try:
        if ep.get("expect") == "xml":
            fields = xml_fields(resp.body)
        else:
            doc = json.loads(resp.body)
            if isinstance(doc, dict) and ("openapi" in doc or "swagger" in doc):
                operations = parse_operations(api, doc)
                return info, columns, operations
            fields = json_fields(doc)
    except (json.JSONDecodeError, ET.ParseError) as exc:
        # A response cut at max_bytes is not valid JSON/XML; that is expected for large ones.
        info["error"] = info["error"] or (
            "truncated, fields not read" if resp.truncated else f"unparsable: {exc}"
        )
        return info, columns, operations
    columns = [
        {
            "api": api,
            "table": table,
            "column": k,
            "type": v,
            "format": "sample",
            "required": "",
            "description": "",
        }
        for k, v in fields.items()
    ]
    return info, columns, operations


def run(endpoints_path: Path, out: Path, delay: float, fetch: Fetch = fetch_with_headers) -> None:
    eps = load_endpoints(endpoints_path)
    out.mkdir(parents=True, exist_ok=True)
    tables: list[dict[str, Any]] = []
    columns: list[dict[str, Any]] = []
    operations: list[dict[str, Any]] = []

    resp = fetch(POSTGREST_ROOT, POSTGREST_HEADERS, OPENAPI_MAX_BYTES)
    if resp.status != 200:  # older PostgREST: JSON root only with a plain JSON Accept
        resp = fetch(
            POSTGREST_ROOT, {**POSTGREST_HEADERS, "Accept": "application/json"}, OPENAPI_MAX_BYTES
        )
    LOG.info("PostgREST root: HTTP %s, %d bytes", resp.status, len(resp.body))
    postgrest_status = {"http_status": resp.status, "error": resp.error}
    if resp.status == 200 and not resp.truncated:
        try:
            schemas = parse_openapi_schemas(json.loads(resp.body))
            t, c = schema_rows("EELIS/PostgREST", schemas)
            tables += t
            columns += c
        except json.JSONDecodeError as exc:
            postgrest_status["error"] = f"root is not JSON: {exc}"

    rows: list[dict[str, Any]] = []
    for ep in eps:
        row: dict[str, Any] = {
            "id": ep.get("id", ""),
            "system": ep.get("system", ""),
            "group": ep.get("group", ""),
            "method": ep.get("method", "GET"),
            "url": ep.get("url", ""),
            "expect": ep.get("expect", ""),
            "source": ep.get("source", ""),
            "verified": ep.get("verified", ""),
            "enabled": ep.get("enabled", True),
            "probe": "",
            "http_status": "",
            "content_type": "",
            "bytes": "",
            "error": "",
        }
        probeable = (
            row["method"] == "GET"
            and "body" not in ep
            and ep.get("enabled", True) is not False
            and ep.get("expect") in ("json", "xml")
            and not is_postgrest(ep)
        )
        if probeable:
            info, cols, ops = probe_endpoint(fetch, ep, str(ep.get("system", "")))
            row.update(info)
            columns += cols
            operations += ops
            LOG.info("%s -> HTTP %s", ep.get("id"), info["http_status"])
            time.sleep(delay)
        elif is_postgrest(ep):
            row["probe"] = "via PostgREST root"
            row["http_status"] = postgrest_status["http_status"]
        rows.append(row)

    write_csv(out / "api_endpoints.csv", ENDPOINT_FIELDS, rows)
    write_csv(out / "api_tables.csv", TABLE_FIELDS, tables)
    write_csv(out / "api_columns.csv", COLUMN_FIELDS, columns)
    write_csv(out / "api_operations.csv", OPERATION_FIELDS, operations)
    (out / "api_probes.json").write_text(
        json.dumps({"postgrest_root": postgrest_status}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    LOG.info(
        "%d endpoints, %d tables, %d columns, %d operations",
        len(rows),
        len(tables),
        len(columns),
        len(operations),
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--endpoints", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("out"))
    ap.add_argument("--delay", type=float, default=1.0)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(args.endpoints, args.out, args.delay)


if __name__ == "__main__":
    main()
