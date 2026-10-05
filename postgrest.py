"""Minimal read-only client for the KAUR PostgREST open-data API (keskkonnaandmed.envir.ee).

Schema profile ``apijahiala`` is required (header ``Accept-Profile``).  Only ``GET`` is used,
page size is capped, requests are spaced by ``delay`` and 429/5xx are retried with back-off.
No credentials are involved: the API is public.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any

LOG = logging.getLogger("postgrest")
BASE_URL = "https://keskkonnaandmed.envir.ee"
PROFILE = "apijahiala"
USER_AGENT = "kaur-juhtimislaud-analysis/0.1 (+https://github.com/TPiparKAUR/KAUR_juhtimislaud)"
PAGE_SIZE = 5000
MAX_ATTEMPTS = 4


@dataclass
class PgResponse:
    status: int
    body: bytes
    content_range: str = ""
    error: str = ""


Transport = Callable[[str, Mapping[str, str]], PgResponse]


def urllib_transport(url: str, headers: Mapping[str, str]) -> PgResponse:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **headers})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return PgResponse(resp.status, resp.read(), resp.headers.get("Content-Range", "") or "")
    except urllib.error.HTTPError as exc:
        return PgResponse(exc.code, b"", error=f"{exc} {exc.read()[:300]!r}")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return PgResponse(0, b"", error=str(exc))


def parse_total(content_range: str) -> int | None:
    """Total row count from a ``Content-Range: 0-0/123`` header, or None when unknown."""
    _, _, total = content_range.partition("/")
    return int(total) if total.isdigit() else None


class PostgrestError(RuntimeError):
    """Raised when a request keeps failing after retries."""


class Client:
    def __init__(
        self,
        transport: Transport = urllib_transport,
        *,
        base_url: str = BASE_URL,
        delay: float = 0.5,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self.transport = transport
        self.base_url = base_url.rstrip("/")
        self.delay = delay
        # Looked up at construction time (not at import) so tests can patch ``time.sleep``.
        self.sleep = sleep or time.sleep

    def _get(self, table: str, query: Mapping[str, str], extra: Mapping[str, str]) -> PgResponse:
        url = f"{self.base_url}/{table}"
        if query:
            url += "?" + urllib.parse.urlencode(query, safe=",.*():")
        headers = {"Accept-Profile": PROFILE, "Accept": "application/json", **extra}
        resp = PgResponse(0, b"")
        for attempt in range(MAX_ATTEMPTS):
            resp = self.transport(url, headers)
            if resp.status in (200, 206):
                self.sleep(self.delay)
                return resp
            if resp.status not in (0, 429, 500, 502, 503, 504):
                break
            wait = 5.0 * (2**attempt)
            LOG.warning("%s: HTTP %s, retrying in %.0fs", table, resp.status, wait)
            self.sleep(wait)
        raise PostgrestError(f"{table}: HTTP {resp.status} {resp.error}")

    def count(self, table: str, filters: Mapping[str, str] | None = None) -> int | None:
        """Exact row count via ``Prefer: count=exact`` (single-row request)."""
        resp = self._get(
            table, {"limit": "1", **(filters or {})}, {"Prefer": "count=exact", "Range": "0-0"}
        )
        return parse_total(resp.content_range)

    def rows(
        self,
        table: str,
        *,
        select: str = "*",
        filters: Mapping[str, str] | None = None,
        order: str | None = None,
        limit: int = PAGE_SIZE,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        query = {"select": select, "limit": str(limit), "offset": str(offset), **(filters or {})}
        if order:
            query["order"] = order
        data = json.loads(self._get(table, query, {}).body or b"[]")
        if not isinstance(data, list):
            raise PostgrestError(f"{table}: expected a JSON array")
        return data

    def iter_rows(
        self,
        table: str,
        *,
        select: str = "*",
        filters: Mapping[str, str] | None = None,
        order: str | None = None,
        page_size: int = PAGE_SIZE,
        max_rows: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Stream all matching rows page by page (a stable ``order`` is strongly advised).

        The exact total comes from the first response, so a server-side row cap (``db-max-rows``)
        that returns fewer rows than ``page_size`` does not end the stream early.
        """
        offset = 0
        total: int | None = None
        while True:
            query = {
                "select": select,
                "limit": str(page_size),
                "offset": str(offset),
                **(filters or {}),
            }
            if order:
                query["order"] = order
            resp = self._get(table, query, {"Prefer": "count=exact"} if total is None else {})
            if total is None:
                total = parse_total(resp.content_range)
            data = json.loads(resp.body or b"[]")
            if not isinstance(data, list):
                raise PostgrestError(f"{table}: expected a JSON array")
            yield from data
            offset += len(data)
            done = not data or (max_rows is not None and offset >= max_rows)
            short = offset >= total if total is not None else len(data) < page_size
            if done or short:
                return
