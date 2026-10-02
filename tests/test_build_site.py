"""Tests for ``build_site``."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

import build_site as b

TOPICS = """
[[teema]]
slug = "a"
group = "Keskkonnaülevaade: a"
pealkiri = "Teema <A>"
seotud = ["b"]
seose_pohjus = "Seos."
allikas = "Allikas X"
viited = [{tekst = "Viide", url = "https://example.org/r"}]

[[teema]]
slug = "b"
group = "Keskkonnaülevaade: b"
pealkiri = "Teema B"
"""

HEADER = ["group", "page_url", "host", "workbook", "view", "title"]


def write_inventory(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(HEADER)
        w.writerows(rows)


@pytest.fixture
def files(tmp_path: Path) -> tuple[Path, Path]:
    t = tmp_path / "t.toml"
    t.write_text(TOPICS, encoding="utf-8")
    inv = tmp_path / "i.csv"
    write_inventory(
        inv,
        [
            ["Keskkonnaülevaade: a", "https://p/a", b.TABLEAU_PUBLIC, "WB A", "V1", "Vaade 1"],
            [
                "Keskkonnaülevaade: a",
                "https://p/a",
                b.TABLEAU_PUBLIC,
                "ZB37GT9CT",
                "(ei tuvastatud)",
                "Jagatud",
            ],
            ["Keskkonnaülevaade: a", "https://p/a", "tableau.envir.ee", "W", "V", "Sisemine"],
            ["Keskkonnaülevaade: b", "https://p/b", b.TABLEAU_PUBLIC, "WB-B", "V2", "Vaade 2"],
            ["Seire", "https://p/s", b.TABLEAU_PUBLIC, "RKSP", "M", "Meteo"],
        ],
    )
    return t, inv


def test_view_urls() -> None:
    v = b.View("WB A", "V 1", "t", "p")
    assert v.embed_url.startswith("https://public.tableau.com/views/WB%20A/V%201?")
    assert v.open_url == "https://public.tableau.com/views/WB%20A/V%201"
    shared = b.View("ZB37GT9CT", "(ei tuvastatud)", "t", "p")
    assert "/shared/ZB37GT9CT?" in shared.embed_url


def test_load_topics_filters_hosts_and_groups(files: tuple[Path, Path]) -> None:
    topics = b.load_topics(*files)
    assert [len(t.views) for t in topics] == [2, 1]  # envir.ee and Seire rows excluded


def test_unknown_related_topic_raises(tmp_path: Path, files: tuple[Path, Path]) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text(TOPICS.replace('seotud = ["b"]', 'seotud = ["zzz"]'), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown related"):
        b.load_topics(bad, files[1])


def test_build_escapes_and_links(tmp_path: Path, files: tuple[Path, Path]) -> None:
    topics = b.load_topics(*files)
    out = tmp_path / "site"
    written = b.build(topics, out)
    assert {p.name for p in written} == {"index.html", "a.html", "b.html"}
    page = (out / "a.html").read_text(encoding="utf-8")
    assert "Teema &lt;A&gt;" in page and "Teema <A>" not in page
    assert '<html lang="et">' in page
    assert 'title="Vaade 1"' in page
    assert 'href="b.html"' in page  # related topic
    assert "Allikas X" in page and "https://example.org/r" in page
    assert "Päritolu" not in page  # unfilled optional metadata is not rendered
    assert (out / ".nojekyll").exists()
    assert "Teema B" in (out / "index.html").read_text(encoding="utf-8")


def test_real_inventory_builds(tmp_path: Path) -> None:
    topics = b.load_topics(Path("data/teemad.toml"), Path("data/kaur_viz_inventar.csv"))
    assert sum(len(t.views) for t in topics) == 34
    b.build(topics, tmp_path)
