"""Tests for the yearbook caption classifier."""

from __future__ import annotations

import analyse_yearbooks as ay


def rec() -> dict[str, object]:
    return {
        "id": "x",
        "riik": "EE",
        "kind": "pdf",
        "pages": 100,
        "captions": [
            {"page": 1, "label": "joonis", "text": "Raiete pindala raieliigiti aastail 1993-2022"},
            {"page": 1, "label": "figure", "text": "Felling area by type in 1993-2022"},
            {"page": 2, "label": "joonis", "text": "Metsamaa jaotus omandivormiti (SMI 2021)"},
            {"page": 3, "label": "tabel", "text": "Tagavara maakonniti, suhteline viga"},
            {"page": 4, "label": "joonis", "text": "Lühike"},
        ],
        "keyword_hits": {"uncertainty": [{"page": 3, "word": "viga", "context": ""}]},
    }


def test_english_duplicates_and_stubs_are_not_counted() -> None:
    d = ay.classify(rec())
    assert d["figures"]["n"] == 2 and d["tables"]["n"] == 1
    assert d["figures_per_100_pages"] == 2.0


def test_forms_dimensions_and_themes_are_tagged_from_the_caption() -> None:
    d = ay.classify(rec())
    assert d["figures"]["forms"] == {"time": 1, "composition": 1}
    assert d["figures"]["dimensions"]["ownership"] == 1
    assert d["figures"]["themes"]["felling"] == 1
    assert d["tables"]["caption_mentions_uncertainty"] == 1
    assert d["uncertainty_keyword_pages"] == 1


def test_documents_without_captions_are_skipped() -> None:
    out = ay.build([rec(), {"id": "y", "kind": "pdf", "captions": []}, {"id": "z", "kind": "html"}])
    assert out["totals"]["documents"] == 1 and out["totals"]["figures"] == 2
