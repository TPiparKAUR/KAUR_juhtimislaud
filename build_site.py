#!/usr/bin/env python3
"""Build the static public site (variant A: Keskkonnaülevaade) from the inventory.

Reads ``data/kaur_viz_inventar.csv`` and ``data/teemad.toml`` and writes a hub page plus one page
per topic into ``--out`` (default ``_site``).  Only Tableau Public views are embedded; every
embed has a text link to the original, so the page works without the iframe.

Usage
-----
    uv run python build_site.py --out _site
"""

from __future__ import annotations

import argparse
import csv
import html
import logging
import shutil
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

LOG = logging.getLogger("build_site")
GROUP_PREFIX = "Keskkonnaülevaade: "
ASSET_DIR = Path(__file__).parent / "site_src"
# Analysis sections (chart builders in site_src/climate-page.js) per topic slug.
ANALYSES: dict[str, list[tuple[str, list[tuple[str, str]]]]] = {
    "ilm-ja-kliima": [
        (
            "climate",
            [
                ("findings", "Peamised tulemused"),
                ("annual", ""),
                ("forest", ""),
                ("grid", ""),
                ("stations", ""),
                ("precip", "Sademed"),
                ("precipForest", ""),
                ("extremes", "Äärmusnäitajad"),
                ("coverage", "Andmete kvaliteet ja katvus"),
                ("methods", ""),
            ],
        ),
    ],
    "vesi": [
        (
            "hydro",
            [
                ("findings", "Jõgede vooluhulk: peamised tulemused"),
                ("regime", ""),
                ("specific", ""),
                ("fdc", ""),
                ("runoff", "Aastane äravool"),
                ("link", ""),
                ("extremes", "Suur- ja madalvesi"),
                ("temp", "Veetemperatuur"),
                ("coverage", "Andmete kvaliteet ja katvus"),
                ("methods", ""),
            ],
        ),
        (
            "water",
            [
                ("findings", "Veekogumite seisund: peamised tulemused"),
                ("status", "Pinnaveekogumite seisund"),
                ("paired", ""),
                ("sectors", "Survetegurid"),
                ("impacts", ""),
                ("groundwater", "Põhjavesi"),
                ("methods", ""),
            ],
        ),
    ],
    "valisohk": [
        (
            "airenergy",
            [
                ("findings", "Käitiste õhuheited: peamised tulemused"),
                ("co2", ""),
                ("bio", ""),
                ("sectors", "Sektorid ja ained"),
                ("pollutants", ""),
                ("counties", "Maakonnad"),
                ("concentration", "Kontsentratsioon ja andmete tundlikkus"),
                ("sensitivity", ""),
                ("methods", ""),
            ],
        ),
    ],
    "energeetika": [
        (
            "airenergy",
            [
                ("efindings", "Soojus- ja elektritoodang: peamised tulemused"),
                ("fuel", ""),
                ("electricity", ""),
                ("heatclimate", "Talv ja soojatoodang"),
                ("methods", ""),
            ],
        ),
    ],
    "mets": [
        (
            "forest",
            [
                ("findings", "Mets: peamised tulemused"),
                ("area", "Metsavarud"),
                ("stock", ""),
                ("perha", ""),
                ("balance", "Juurdekasv ja raie"),
                ("species", "Metsa struktuur"),
                ("owners", ""),
                ("management", ""),
                ("age", ""),
                ("counties", "Maakonnad"),
                ("deadwood", "Surnud puit"),
                ("methods", ""),
            ],
        ),
    ],
    "jaatmed": [
        (
            "waste",
            [
                ("findings", "Jäätmed: peamised tulemused"),
                ("generation", "Jäätmeteke"),
                ("generationRest", ""),
                ("hazardous", ""),
                ("top", ""),
                ("flows", "Käitlus ja liikumine"),
                ("trade", ""),
                ("stocks", "Andmete järjepidevus"),
                ("methods", ""),
            ],
        ),
    ],
}
SCRIPTS = {
    "climate": ["charts.js", "climate-page.js"],
    "hydro": ["charts.js", "hydro-charts.js", "hydro-page.js"],
    "forest": ["charts.js", "forest-charts.js", "forest-page.js"],
    "water": [
        "charts.js",
        "hydro-charts.js",
        "airenergy-charts.js",
        "water-charts.js",
        "water-page.js",
    ],
    "waste": [
        "charts.js",
        "hydro-charts.js",
        "airenergy-charts.js",
        "waste-charts.js",
        "waste-page.js",
    ],
    "airenergy": ["charts.js", "hydro-charts.js", "airenergy-charts.js", "airenergy-page.js"],
}
TABLEAU_PUBLIC = "public.tableau.com"
EMBED_QUERY = ":showVizHome=no&:embed=true&:toolbar=yes"

CSS = """
:root{--bg:#fff;--fg:#1b2a22;--muted:#51605a;--accent:#0b6b3a;--card:#f3f7f4;--line:#cfdad3}
@media (prefers-color-scheme:dark){:root{--bg:#121a16;--fg:#e8f0eb;--muted:#a9b8b0;
--accent:#6fcf97;--card:#1a2520;--line:#2f3f37}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:16px/1.55 system-ui,sans-serif}
a{color:var(--accent)}.wrap{max-width:70rem;margin:0 auto;padding:0 1rem}
header.site{border-bottom:1px solid var(--line);padding:1rem 0}
header.site a.brand{font-weight:700;text-decoration:none;color:var(--fg)}
nav.topics ul{display:flex;flex-wrap:wrap;gap:.5rem;list-style:none;padding:0;margin:.5rem 0 0}
nav.topics a{display:inline-block;padding:.25rem .7rem;border:1px solid var(--line);
border-radius:1rem;text-decoration:none}
nav.topics a[aria-current=page]{background:var(--accent);color:var(--bg)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(16rem,1fr));gap:1rem;
list-style:none;padding:0}
.card{background:var(--card);border:1px solid var(--line);border-radius:.5rem;padding:1rem;
height:100%}
.card h3{margin-top:0}.muted{color:var(--muted)}
figure.viz{margin:2rem 0}figure.viz iframe{width:100%;height:42rem;border:1px solid var(--line);
border-radius:.5rem;background:#fff}
.skip{position:absolute;left:-999px}.skip:focus{left:1rem;top:1rem;background:var(--bg);
padding:.5rem}
footer{border-top:1px solid var(--line);margin-top:3rem;padding:1rem 0;color:var(--muted)}
@media (max-width:40rem){figure.viz iframe{height:30rem}}
"""


@dataclass(frozen=True)
class View:
    workbook: str
    view: str
    title: str
    page_url: str

    @property
    def embed_url(self) -> str:
        """Tableau Public embed URL; shared-link ids (no view name) use ``/shared/``."""
        if not self.view or self.view == "(ei tuvastatud)":
            return f"https://{TABLEAU_PUBLIC}/shared/{quote(self.workbook)}?:showVizHome=no&:embed=true"
        return f"https://{TABLEAU_PUBLIC}/views/{quote(self.workbook)}/{quote(self.view)}?{EMBED_QUERY}"

    @property
    def open_url(self) -> str:
        return self.embed_url.split("?", 1)[0]


@dataclass
class Topic:
    slug: str
    group: str
    title: str
    related: list[str] = field(default_factory=list)
    related_reason: str = ""
    summary: str = ""
    source: str = ""
    provenance: str = ""
    update: str = ""
    references: list[dict[str, str]] = field(default_factory=list)
    views: list[View] = field(default_factory=list)


def load_topics(topics_path: Path, inventory_path: Path) -> list[Topic]:
    """Join topic metadata with inventory views (Tableau Public only)."""
    meta = tomllib.loads(topics_path.read_text(encoding="utf-8"))["teema"]
    topics = [
        Topic(
            slug=t["slug"],
            group=t["group"],
            title=t["pealkiri"],
            related=list(t.get("seotud", [])),
            related_reason=t.get("seose_pohjus", ""),
            summary=t.get("kokkuvote", ""),
            source=t.get("allikas", ""),
            provenance=t.get("paritolu", ""),
            update=t.get("uuendus", ""),
            references=list(t.get("viited", [])),
        )
        for t in meta
    ]
    by_group = {t.group: t for t in topics}
    with inventory_path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            topic = by_group.get(row["group"])
            if topic is None:
                if row["group"].startswith(GROUP_PREFIX):
                    LOG.warning("inventory group without topic metadata: %s", row["group"])
                continue
            if row["host"] != TABLEAU_PUBLIC:
                LOG.warning("skipping non-Tableau-Public view %s/%s", row["host"], row["view"])
                continue
            topic.views.append(View(row["workbook"], row["view"], row["title"], row["page_url"]))
    slugs = {t.slug for t in topics}
    for t in topics:
        unknown = [s for s in t.related if s not in slugs]
        if unknown:
            raise ValueError(f"{t.slug}: unknown related topics {unknown}")
        if not t.views:
            LOG.warning("topic %s has no views", t.slug)
        for name, value in (
            ("allikas", t.source),
            ("paritolu", t.provenance),
            ("uuendus", t.update),
            ("viited", t.references),
        ):
            if not value:
                LOG.warning("topic %s: metadata '%s' not filled in", t.slug, name)
    return topics


def e(text: str) -> str:
    return html.escape(text, quote=True)


def layout(
    title: str,
    body: str,
    topics: list[Topic],
    current: str,
    prefix: str,
    features: frozenset[str] = frozenset(),
) -> str:
    links = "".join(
        f'<li><a href="{prefix}{t.slug}.html"'
        f"{' aria-current="page"' if t.slug == current else ''}>{e(t.title)}</a></li>"
        for t in topics
    )
    names: list[str] = []
    for feat in ("climate", "hydro", "airenergy", "waste", "forest", "water"):
        if feat in features:
            names += [n for n in SCRIPTS[feat] if n not in names]
    scripts = "".join(f'<script src="assets/{n}"></script>' for n in names)
    return f"""<!doctype html>
<html lang="et"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title><style>{CSS}</style>
{'<link rel="stylesheet" href="assets/charts.css">' if features else ""}</head><body>
<a class="skip" href="#main">Mine põhisisu juurde</a>
<header class="site"><div class="wrap">
<a class="brand" href="{prefix}index.html">Keskkonnaülevaade</a>
<nav class="topics" aria-label="Teemad"><ul>{links}</ul></nav></div></header>
<main id="main" class="wrap">{body}</main>
<footer><div class="wrap">Andmed: Keskkonnaagentuur (KAUR),
<a href="https://keskkonnaportaal.ee/">keskkonnaportaal.ee</a>.
Vaated on Tableau Public sisu.</div></footer>
{scripts}</body></html>
"""


def render_index(topics: list[Topic], features: frozenset[str] = frozenset()) -> str:
    cards = "".join(
        f'<li><div class="card"><h3><a href="{t.slug}.html">{e(t.title)}</a></h3>'
        f"<p>{e(t.summary) if t.summary else ''}</p>"
        f'<p class="muted">{len(t.views)} vaadet'
        + (
            " · seotud: "
            + ", ".join(
                f'<a href="{r}.html">{e(next(x.title for x in topics if x.slug == r))}</a>'
                for r in t.related
            )
            if t.related
            else ""
        )
        + "</p></div></li>"
        for t in topics
    )
    hero = ""
    if "climate" in features:
        hero += (
            '<section aria-labelledby="kliima">'
            '<h2 id="kliima">Kliima: mis on viimase 35 aastaga muutunud?</h2>'
            '<div data-climate="kpis"></div><div data-climate="annual"></div>'
            '<div data-climate="forest"></div>'
            '<p><a href="ilm-ja-kliima.html">Kogu kliimaanalüüs: kuud, jaamad, sademed, äärmused, '
            "andmete kvaliteet →</a></p></section>"
        )
    if "hydro" in features:
        hero += (
            '<section aria-labelledby="vesi">'
            '<h2 id="vesi">Kliima ja vesi: kuidas sademed jõgedesse jõuavad?</h2>'
            '<div data-hydro="link"></div>'
            '<p><a href="vesi.html">Kogu hüdroloogia analüüs: režiim, erivool, kestvuskõver, '
            "ekstreemid, veetemperatuur →</a></p></section>"
        )
    body = (
        "<h1>Keskkonnaülevaade</h1>"
        "<p>Eesti keskkonnaseisundi teemad ühes kohas: iga teema all on vaated ja teemade "
        "omavahelised seosed.</p>"
        f"{hero}<h2>Teemad</h2>"
        f'<ul class="grid">{cards}</ul>'
    )
    return layout("Keskkonnaülevaade", body, topics, "", "", features)


def render_topic(topic: Topic, topics: list[Topic], features: frozenset[str] = frozenset()) -> str:
    figs = "".join(
        f'<figure class="viz"><figcaption><h2>{e(v.title)}</h2></figcaption>'
        f'<iframe src="{e(v.embed_url)}" title="{e(v.title)}" loading="lazy"></iframe>'
        f'<p class="muted"><a href="{e(v.open_url)}">Ava vaade Tableau Publicus</a></p></figure>'
        for v in topic.views
    )
    meta_rows = [
        ("Allikas", topic.source),
        ("Andmete päritolu", topic.provenance),
        ("Uuendussagedus", topic.update),
    ]
    meta = "".join(f"<dt>{k}</dt><dd>{e(v)}</dd>" for k, v in meta_rows if v)
    refs = "".join(
        f'<li><a href="{e(r["url"])}">{e(r["tekst"])}</a></li>' for r in topic.references
    )
    related = ""
    if topic.related:
        by_slug = {t.slug: t for t in topics}
        items = "".join(
            f'<li><a href="{s}.html">{e(by_slug[s].title)}</a></li>' for s in topic.related
        )
        related = f"<h2>Seotud teemad</h2><p>{e(topic.related_reason)}</p><ul>{items}</ul>"
    sections = ""
    used: frozenset[str] = frozenset()
    blocks = [(k, p) for k, p in ANALYSES.get(topic.slug, []) if k in features]
    if blocks:
        used = frozenset(k for k, _ in blocks)
        for kind, parts in blocks:
            for key, heading in parts:
                sections += (
                    f"<h2>{e(heading)}</h2>" if heading else ""
                ) + f'<div data-{kind}="{key}"></div>'
        figs = "<h2>Keskkonnaportaali vaated (Tableau)</h2>" + figs
    body = (
        f"<h1>{e(topic.title)}</h1>"
        + (f"<p>{e(topic.summary)}</p>" if topic.summary else "")
        + (f"<dl>{meta}</dl>" if meta else "")
        + sections
        + figs
        + related
        + (f"<h2>Viited</h2><ul>{refs}</ul>" if refs else "")
    )
    return layout(
        f"{topic.title} | Keskkonnaülevaade",
        body,
        topics,
        topic.slug,
        "",
        used,
    )


def build(
    topics: list[Topic],
    out: Path,
    climate_json: Path | None = None,
    hydro_json: Path | None = None,
    airenergy_json: Path | None = None,
    waste_json: Path | None = None,
    forest_json: Path | None = None,
    water_json: Path | None = None,
) -> list[Path]:
    """Write the site; analysis sections appear only for the JSON inputs that exist."""
    out.mkdir(parents=True, exist_ok=True)
    written = [out / "index.html"]
    inputs = {
        "climate": climate_json,
        "hydro": hydro_json,
        "airenergy": airenergy_json,
        "waste": waste_json,
        "forest": forest_json,
        "water": water_json,
    }
    features: set[str] = set()
    for name, path in inputs.items():
        if path and path.exists():
            (out / "data").mkdir(exist_ok=True)
            shutil.copyfile(path, out / "data" / f"{name}.json")
            features.add(name)
        else:
            LOG.warning("no %s.json: %s analysis sections omitted", name, name)
    if features:
        shutil.copytree(ASSET_DIR, out / "assets", dirs_exist_ok=True)
    feats = frozenset(features)
    written[0].write_text(render_index(topics, feats), encoding="utf-8")
    for t in topics:
        path = out / f"{t.slug}.html"
        path.write_text(render_topic(t, topics, feats), encoding="utf-8")
        written.append(path)
    (out / ".nojekyll").write_text("", encoding="utf-8")
    return written


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--inventory", type=Path, default=Path("data/kaur_viz_inventar.csv"))
    ap.add_argument("--topics", type=Path, default=Path("data/teemad.toml"))
    ap.add_argument("--out", type=Path, default=Path("_site"))
    ap.add_argument("--climate", type=Path, default=None, help="aggregated climate.json to embed")
    ap.add_argument("--hydro", type=Path, default=None, help="aggregated hydro.json to embed")
    ap.add_argument(
        "--airenergy", type=Path, default=None, help="aggregated airenergy.json to embed"
    )
    ap.add_argument("--waste", type=Path, default=None, help="aggregated waste.json to embed")
    ap.add_argument("--forest", type=Path, default=None, help="aggregated forest.json to embed")
    ap.add_argument("--water", type=Path, default=None, help="aggregated water.json to embed")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    topics = load_topics(args.topics, args.inventory)
    files = build(
        topics,
        args.out,
        args.climate,
        args.hydro,
        args.airenergy,
        args.waste,
        args.forest,
        args.water,
    )
    LOG.info("wrote %d pages to %s", len(files), args.out)


if __name__ == "__main__":
    main()
