"""A small local HTTP server that behaves like the KAUR PostgREST API (test helper).

It reproduces the behaviours that broke real runs: a server-side page cap (``max_rows``),
refusal of aggregate selects (PGRST123), ``Content-Range`` totals on ``Prefer: count=exact``,
``select`` returning *only* the requested columns, unstable page order when no ``order`` is
given, ``order`` with several columns, ``eq.`` and ``not.in.`` filters, and injected transient
failures (HTTP 503) so retry paths can be exercised.
"""

from __future__ import annotations

import json
import random
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse


class FakeState:
    def __init__(
        self, tables: dict[str, list[dict[str, Any]]], max_rows: int, fail_every: int
    ) -> None:
        self.tables = tables
        self.max_rows = max_rows
        self.fail_every = fail_every
        self.requests = 0
        self.lock = threading.Lock()


def _matches(row: dict[str, Any], key: str, spec: str) -> bool:
    if spec.startswith("eq."):
        return str(row.get(key)) == spec[3:]
    if spec.startswith("not.in.("):
        items = [x.strip().strip('"') for x in spec[len("not.in.(") : -1].split(",")]
        return str(row.get(key)) not in items
    raise ValueError(f"unsupported filter {key}={spec}")


def _sort_key(row: dict[str, Any], cols: Sequence[str]) -> tuple[Any, ...]:
    return tuple((row.get(c) is None, str(row.get(c))) for c in cols)


def make_handler(state: FakeState) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: Any) -> None:  # silence
            return

        def _send(self, status: int, body: bytes, headers: dict[str, str] | None = None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            with state.lock:
                state.requests += 1
                n = state.requests
            if state.fail_every and n % state.fail_every == 0:
                self._send(503, b'{"message":"transient"}')
                return
            url = urlparse(self.path)
            table = url.path.strip("/")
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            if table not in state.tables:
                self._send(404, b'{"message":"no such table"}')
                return
            select = q.get("select", "*")
            if "(" in select:
                self._send(400, b'{"code":"PGRST123","message":"Use of aggregate functions"}')
                return
            reserved = {"select", "limit", "offset", "order"}
            rows = [
                r
                for r in state.tables[table]
                if all(_matches(r, k, v) for k, v in q.items() if k not in reserved)
            ]
            if "order" in q:
                cols = [c.split(".")[0] for c in q["order"].split(",")]
                rows.sort(key=lambda r: _sort_key(r, cols))
            else:  # like the real server: unordered pages are not stable between requests
                random.Random(n).shuffle(rows)
            total = len(rows)
            offset = int(q.get("offset", 0))
            limit = min(int(q.get("limit", state.max_rows)), state.max_rows)
            page = rows[offset : offset + limit]
            if select != "*":
                cols = select.split(",")
                missing = [
                    c for c in cols if state.tables[table] and c not in state.tables[table][0]
                ]
                if missing:
                    self._send(
                        400, json.dumps({"message": f"column {missing[0]} does not exist"}).encode()
                    )
                    return
                page = [{c: r[c] for c in cols} for r in page]
            last = offset + len(page) - 1
            rng = f"{offset}-{max(last, offset)}/{total}" if page else f"*/{total}"
            self._send(206 if page else 200, json.dumps(page).encode(), {"Content-Range": rng})

    return Handler


@contextmanager
def fake_server(
    tables: dict[str, list[dict[str, Any]]], max_rows: int = 5, fail_every: int = 0
) -> Iterator[tuple[str, FakeState]]:
    """Serve ``tables`` on a free local port; yields (base_url, state)."""
    state = FakeState(tables, max_rows, fail_every)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(state))
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}", state
    finally:
        srv.shutdown()
        srv.server_close()
