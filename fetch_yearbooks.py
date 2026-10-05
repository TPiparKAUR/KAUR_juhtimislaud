#!/usr/bin/env python3
"""Download public yearbooks / reports and write a structural summary of each.

Why this exists: the analysis sandbox cannot reach most agency sites, but the project's GitHub
Actions runner can.  The runner downloads the documents listed in ``data/allikad.toml`` and
extracts, per document: HTTP status and size, PDF page count and metadata, bookmarks (outline),
the text of the first pages (contents list), figure/table captions with page numbers and the
pages that mention forests.  Full PDFs stay in the workflow artifact; the published summary
holds only structure (titles, captions truncated to 160 characters, short contents excerpts),
so that the design lessons can be studied and summarised in our own words.

Usage
-----
    uv run python fetch_yearbooks.py --sources data/allikad.toml --out out/yearbooks
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
import re
import tomllib
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PyPdfError

LOG = logging.getLogger("fetch_yearbooks")
USER_AGENT = "kaur-juhtimislaud-research/0.1 (+https://github.com/TPiparKAUR/KAUR_juhtimislaud)"
MAX_BYTES = 80_000_000
CAPTION = re.compile(
    r"^\s*(Joonis|Tabel|Figure|Fig\.|Table|Figur|Figuur|Tabell|Tabel|Kuva|Taulukko|Mynd|Tafla)"
    r"\s*[A-Z]?\d+[.:)]?\s*(.*)$",
    re.IGNORECASE,
)
FOREST = re.compile(r"\b(mets|skog|forest|skov|metsä|skóg)\w*", re.IGNORECASE)


class Headings(HTMLParser):
    """Collect the title, h1-h3 headings and PDF links of an HTML page."""

    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.headings: list[str] = []
        self.pdf_links: list[tuple[str, str]] = []
        self._tag = ""
        self._href = ""
        self._buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._tag = tag
        self._buf = []
        if tag == "a":
            self._href = dict(attrs).get("href") or ""

    def handle_data(self, data: str) -> None:
        self._buf.append(data)

    def handle_endtag(self, tag: str) -> None:
        text = " ".join("".join(self._buf).split())
        if tag == "title":
            self.title = text
        elif tag in {"h1", "h2", "h3"} and text:
            self.headings.append(text[:160])
        elif tag == "a" and ".pdf" in self._href.lower() and text:
            self.pdf_links.append((text[:120], self._href))
        self._buf = []


def download(url: str, timeout: int = 120) -> tuple[int, str, bytes, str]:
    """Return (status, content type, body, error); never raises on HTTP errors."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(MAX_BYTES + 1)
            return resp.status, resp.headers.get("Content-Type", ""), body[:MAX_BYTES], ""
    except urllib.error.HTTPError as exc:
        return exc.code, "", b"", str(exc)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return 0, "", b"", str(exc)


def flatten_outline(items: list[Any], reader: PdfReader, depth: int = 0) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for it in items:
        if isinstance(it, list):
            out += flatten_outline(it, reader, depth + 1)
        else:
            page: int | None
            try:
                num = reader.get_destination_page_number(it)
                page = None if num is None else num + 1
            except (PyPdfError, ValueError, KeyError):
                page = None
            out.append({"depth": depth, "title": str(it.title)[:140], "page": page})
    return out


def summarise_pdf(body: bytes) -> dict[str, Any]:
    """Structure of a PDF: pages, outline, captions, forest pages and contents excerpt."""
    reader = PdfReader(io.BytesIO(body))
    n = len(reader.pages)
    captions: list[dict[str, Any]] = []
    forest_pages: list[int] = []
    excerpt = ""
    for i, page in enumerate(reader.pages, 1):
        try:
            text = page.extract_text() or ""
        except (PyPdfError, ValueError, KeyError):
            text = ""
        if i <= 6 and len(excerpt) < 3000:
            excerpt += f"\n[p{i}] " + " ".join(text.split())[:700]
        if FOREST.search(text):
            forest_pages.append(i)
        for line in text.splitlines():
            m = CAPTION.match(line)
            if m and len(captions) < 400:
                captions.append({"page": i, "label": m.group(1).lower(), "text": m.group(2)[:160]})
    meta = reader.metadata
    kinds: dict[str, int] = {}
    for c in captions:
        kinds[c["label"]] = kinds.get(c["label"], 0) + 1
    return {
        "pages": n,
        "title_meta": str(meta.title)[:160] if meta and meta.title else None,
        "outline": flatten_outline(list(reader.outline), reader)[:200],
        "caption_counts": kinds,
        "captions": captions,
        "forest_pages": forest_pages[:300],
        "forest_page_share": round(len(forest_pages) / n, 3) if n else 0,
        "contents_excerpt": excerpt.strip()[:3000],
    }


def summarise_html(body: bytes) -> dict[str, Any]:
    p = Headings()
    p.feed(body.decode("utf-8", errors="replace"))
    return {"title": p.title[:160], "headings": p.headings[:80], "pdf_links": p.pdf_links[:60]}


def process(src: dict[str, Any], out: Path) -> dict[str, Any]:
    status, ctype, body, err = download(src["url"])
    rec: dict[str, Any] = {k: src.get(k) for k in ("id", "riik", "asutus", "nimi", "url")} | {
        "status": status,
        "content_type": ctype,
        "bytes": len(body),
        "error": err,
    }
    if status != 200 or not body:
        return rec
    rec["sha256"] = hashlib.sha256(body).hexdigest()[:16]
    try:
        if body[:5] == b"%PDF-":
            rec["kind"] = "pdf"
            rec.update(summarise_pdf(body))
            (out / "pdf").mkdir(parents=True, exist_ok=True)
            (out / "pdf" / f"{src['id']}.pdf").write_bytes(body)
        else:
            rec["kind"] = "html"
            rec.update(summarise_html(body))
    except (PyPdfError, ValueError, KeyError, OSError) as exc:
        rec["parse_error"] = f"{type(exc).__name__}: {exc}"[:200]
    return rec


def run(sources: list[dict[str, Any]], out: Path) -> list[dict[str, Any]]:
    out.mkdir(parents=True, exist_ok=True)
    results = []
    for src in sources:
        rec = process(src, out)
        LOG.info("%s: HTTP %s, %s bytes", src["id"], rec["status"], rec["bytes"])
        results.append(rec)
        (out / "yearbooks_summary.json").write_text(
            json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    return results


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sources", type=Path, default=Path("data/allikad.toml"))
    ap.add_argument("--out", type=Path, default=Path("out/yearbooks"))
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sources = tomllib.loads(args.sources.read_text(encoding="utf-8"))["allikas"]
    run(sources, args.out)


if __name__ == "__main__":
    main()
