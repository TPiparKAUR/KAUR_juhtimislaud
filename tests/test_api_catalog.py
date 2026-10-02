"""Tests for ``api_catalog`` (network is faked)."""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping
from pathlib import Path

import pytest

import api_catalog as a
from tableau_catalog import Response

ENDPOINTS = """
[[endpoint]]
id = "eelis-x"
system = "EELIS"
url = "https://keskkonnaandmed.envir.ee/f_x?limit=1"
expect = "json"
headers = { "Accept-Profile" = "apijahiala" }

[[endpoint]]
id = "estmodel-countries"
system = "EstModel"
url = "https://estmodel.envir.ee/countries"
expect = "json"

[[endpoint]]
id = "kaia-swagger"
system = "KAIA"
url = "https://avaandmed.example/swagger/v1/swagger.json"
expect = "json"

[[endpoint]]
id = "ilm-obs"
system = "Ilmateenistus"
url = "https://ilmateenistus.example/observations.php"
expect = "xml"

[[endpoint]]
id = "kaia-query"
system = "KAIA"
method = "POST"
url = "https://avaandmed.example/api/query"
expect = "json"
body = "{}"

[[endpoint]]
id = "off"
system = "KOTKAS"
url = "https://kotkas.example/x"
expect = "json"
enabled = false
"""

PGRST = {
    "swagger": "2.0",
    "definitions": {
        "f_x": {
            "description": "Tabel X",
            "required": ["id"],
            "properties": {
                "id": {"type": "integer", "format": "bigint", "description": "Võti\nrida"},
                "nimi": {"type": "string"},
            },
        },
        "empty": {"description": "no props"},
    },
}


def fake(routes: Mapping[str, Response]) -> a.Fetch:
    calls: list[str] = []

    def fetch(url: str, headers: Mapping[str, str], max_bytes: int) -> Response:
        calls.append(url)
        return routes.get(url, Response(404, "", b"", error="nf"))

    fetch.calls = calls  # type: ignore[attr-defined]
    return fetch


def test_parse_openapi_schemas_swagger2_and_openapi3() -> None:
    assert set(a.parse_openapi_schemas(PGRST)) == {"f_x"}
    v3 = {"components": {"schemas": {"T": {"properties": {"a": {"type": "string"}}}}}}
    assert set(a.parse_openapi_schemas(v3)) == {"T"}
    assert a.parse_openapi_schemas({}) == {}


def test_schema_rows() -> None:
    tables, cols = a.schema_rows("API", a.parse_openapi_schemas(PGRST))
    assert tables == [{"api": "API", "table": "f_x", "description": "Tabel X", "n_columns": 2}]
    assert cols[0]["required"] == "jah" and cols[0]["description"] == "Võti rida"
    assert cols[1]["required"] == ""


def test_json_fields_unwraps_lists_and_envelopes() -> None:
    assert a.json_fields([{"a": 1, "b": "x", "c": None}]) == {
        "a": "integer",
        "b": "string",
        "c": "null",
    }
    assert a.json_fields({"data": [{"k": 1.5}], "n": 1}) == {"k": "number"}
    assert a.json_fields([]) == {}
    assert a.json_fields("text") == {}


def test_xml_fields_picks_repeated_record() -> None:
    xml = b"<obs><s id='1'><name>A</name><t>1</t></s><s id='2'><name>B</name></s><ts>x</ts></obs>"
    assert a.xml_fields(xml) == {"@id": "attribute", "name": "element", "t": "element"}
    assert a.xml_fields(b"<empty/>") == {}


def test_parse_operations() -> None:
    doc = {
        "paths": {
            "/b": {"post": {"summary": "S", "operationId": "o"}},
            "/a": {"get": {}, "parameters": []},
        }
    }
    ops = a.parse_operations("KAIA", doc)
    assert [(o["path"], o["method"]) for o in ops] == [("/a", "GET"), ("/b", "POST")]


def test_load_endpoints_rejects_wrong_shape(tmp_path: Path) -> None:
    p = tmp_path / "e.toml"
    p.write_text("endpoint = 3\n", encoding="utf-8")
    with pytest.raises(ValueError, match="array of tables"):
        a.load_endpoints(p)


def test_run_end_to_end(tmp_path: Path) -> None:
    eps = tmp_path / "e.toml"
    eps.write_text(ENDPOINTS, encoding="utf-8")
    routes = {
        a.POSTGREST_ROOT: Response(200, "application/openapi+json", json.dumps(PGRST).encode()),
        "https://estmodel.envir.ee/countries": Response(
            200, "application/json", b'[{"code": "EE", "name": "Eesti"}]'
        ),
        "https://avaandmed.example/swagger/v1/swagger.json": Response(
            200, "application/json", b'{"openapi": "3.0.1", "paths": {"/api/lists": {"get": {}}}}'
        ),
        "https://ilmateenistus.example/observations.php": Response(
            200, "text/xml", b"<o><s><name>A</name></s></o>"
        ),
    }
    fetch = fake(routes)
    out = tmp_path / "out"
    a.run(eps, out, delay=0, fetch=fetch)
    calls: list[str] = fetch.calls  # type: ignore[attr-defined]
    # Never calls POST, disabled, or PostgREST table endpoints individually.
    assert not any("query" in c or "kotkas" in c or "f_x?" in c for c in calls)

    def read(name: str) -> list[dict[str, str]]:
        with (out / name).open(encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))

    eps_rows = {r["id"]: r for r in read("api_endpoints.csv")}
    assert len(eps_rows) == 6
    assert eps_rows["eelis-x"]["probe"] == "via PostgREST root"
    assert eps_rows["kaia-query"]["probe"] == "" and eps_rows["off"]["probe"] == ""
    assert eps_rows["estmodel-countries"]["http_status"] == "200"
    cols = {(r["api"], r["table"], r["column"]) for r in read("api_columns.csv")}
    assert ("EELIS/PostgREST", "f_x", "id") in cols
    assert ("EstModel", "countries", "code") in cols
    assert ("Ilmateenistus", "observations.php", "name") in cols
    assert [(o["api"], o["path"]) for o in read("api_operations.csv")] == [("KAIA", "/api/lists")]
    assert json.loads((out / "api_probes.json").read_text())["postgrest_root"]["http_status"] == 200


def test_run_survives_blocked_postgrest(tmp_path: Path) -> None:
    eps = tmp_path / "e.toml"
    eps.write_text(ENDPOINTS, encoding="utf-8")
    a.run(eps, tmp_path / "o", delay=0, fetch=fake({}))
    with (tmp_path / "o" / "api_tables.csv").open(encoding="utf-8") as fh:
        assert len(list(csv.DictReader(fh))) == 0
