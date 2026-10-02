# KAUR juhtimislaud

Inventory and tooling for turning KAUR Tableau dashboards into an annotated, automatically
updated public web page. Context and decisions: see [HANDOFF.md](HANDOFF.md).

## Setup

```bash
uv sync --all-extras
uv run playwright install chromium   # skip if a Chromium is already available
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

## Crawl and merge

```bash
uv run python crawl_kaur_viz.py --out out --delay 1.0
uv run python merge_inventory.py --out data/kaur_viz_inventar.csv
```

`tableau.envir.ee` is only inventoried if `TABLEAU_PAT_NAME` / `TABLEAU_PAT_SECRET`
(and optionally `TABLEAU_SITE`) are set in the environment. Never put credentials in code.

## Status of the live crawl

The crawler logic is tested against fixtures (including shadow DOM and lazy iframes). The
live crawl of `keskkonnaportaal.ee`, `tableau.envir.ee` and `public.tableau.com` has **not** been
run yet: the cloud sandbox network policy returns HTTP 403 for those hosts. Run it from a KAUR
machine (or allow the hosts) and then merge. Chromium can be supplied with `--chromium PATH`.
