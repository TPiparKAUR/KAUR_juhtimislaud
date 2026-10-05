"""Tests for ``fetch_yearbooks`` against a local HTTP server serving a generated PDF and HTML."""

from __future__ import annotations

import io
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
from pypdf import PdfReader, PdfWriter

import fetch_yearbooks as fy


def make_pdf(pages: list[str]) -> bytes:
    """A minimal PDF with one text line per page (Helvetica), plus a bookmark."""
    objs: list[bytes] = []
    n = len(pages)
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(n))
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode())
    for i, text in enumerate(pages):
        content = f"BT /F1 12 Tf 50 700 Td ({text}) Tj ET".encode()
        objs.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {4 + 2 * i} 0 R "
            f"/Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> "
            f">> >> >>".encode()
        )
        objs.append(f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream")
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for i, o in enumerate(objs, 1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj\n".encode() + o + b"\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode())
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(
        f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    )
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(out.getvalue())))
    writer.add_outline_item("Metsad", 1)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


HTML = b"""<html><head><title>Landing</title></head><body><h1>Yearbooks</h1>
<h2>Forest</h2><a href="/mets.pdf">Mets 2021 (PDF)</a><a href="/x.html">other</a></body></html>"""


@pytest.fixture
def server() -> Any:
    pdf = make_pdf(
        [
            "Sisukord",
            "Joonis 1. Metsa pindala vanuseklassi jargi",
            "Tabel 2. Raie maht suhteline viga 5%",
        ]
    )

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a: Any) -> None:
            return

        def do_GET(self) -> None:
            routes = {
                "/mets.pdf": (200, pdf),
                "/land.html": (200, HTML),
                "/bad.pdf": (200, b"%PDF-1.4 broken"),
            }
            status, body = routes.get(self.path, (404, b"nope"))
            self.send_response(status)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def test_pdf_structure_is_extracted(server: str, tmp_path: Path) -> None:
    rec = fy.process({"id": "a", "url": f"{server}/mets.pdf"}, tmp_path)
    assert rec["status"] == 200 and rec["kind"] == "pdf" and rec["pages"] == 3
    assert rec["caption_counts"] == {"joonis": 1, "tabel": 1}
    assert rec["captions"][0]["page"] == 2 and "vanuseklassi" in rec["captions"][0]["text"]
    assert rec["outline"][0]["title"] == "Metsad" and rec["outline"][0]["page"] == 2
    assert 2 in rec["forest_pages"] and (tmp_path / "pdf" / "a.pdf").exists()


def test_html_headings_and_pdf_links(server: str, tmp_path: Path) -> None:
    rec = fy.process({"id": "b", "url": f"{server}/land.html"}, tmp_path)
    assert rec["kind"] == "html" and rec["title"] == "Landing"
    assert rec["headings"] == ["Yearbooks", "Forest"]
    assert rec["pdf_links"] == [("Mets 2021 (PDF)", "/mets.pdf")]


def test_http_errors_and_broken_pdfs_are_recorded_not_raised(server: str, tmp_path: Path) -> None:
    missing = fy.process({"id": "c", "url": f"{server}/missing.pdf"}, tmp_path)
    assert missing["status"] == 404 and "kind" not in missing
    broken = fy.process({"id": "d", "url": f"{server}/bad.pdf"}, tmp_path)
    assert broken["status"] == 200 and broken["kind"] == "pdf" and "parse_error" in broken
    unreachable = fy.process({"id": "e", "url": "http://127.0.0.1:9/x"}, tmp_path)
    assert unreachable["status"] == 0 and unreachable["error"]


def test_run_writes_a_summary_after_every_document(server: str, tmp_path: Path) -> None:
    srcs = [{"id": "a", "url": f"{server}/mets.pdf"}, {"id": "c", "url": f"{server}/missing"}]
    fy.run(srcs, tmp_path)
    data = json.loads((tmp_path / "yearbooks_summary.json").read_text(encoding="utf-8"))
    assert [d["id"] for d in data] == ["a", "c"]


def test_source_list_is_well_formed() -> None:
    import tomllib

    root = Path(__file__).resolve().parent.parent
    items = tomllib.loads((root / "data" / "allikad.toml").read_text(encoding="utf-8"))["allikas"]
    ids = [i["id"] for i in items]
    assert len(ids) == len(set(ids)) and all(i["url"].startswith("https://") for i in items)


def test_uncertainty_and_target_words_are_found_with_context(server: str, tmp_path: Path) -> None:
    rec = fy.process({"id": "a", "url": f"{server}/mets.pdf"}, tmp_path)
    words = [h["word"] for h in rec["keyword_hits"]["uncertainty"]]
    assert words == ["suhteline viga"]
    assert rec["keyword_hits"]["uncertainty"][0]["page"] == 3
