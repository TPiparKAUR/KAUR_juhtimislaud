# Tableau Serveri (`tableau.envir.ee`) ligipääs ilma kogu serverit avamata

Seis 2026-10-02. Autentimata `GET /api/3.0/serverinfo` vastas: Tableau Server 2024.2.1, REST API 3.23.
Projektide, töövihikute ja andmeallikate **täielik loend** vajab autentitud REST-i või Metadata API-t.

## Variandid mandaadi saamiseks

| # | Variant | Kes teeb | Märkused |
|---|---|---|---|
| 1 | **Isiklik pääsuluba (PAT)**: Tableau Server → *My Account Settings* → *Personal Access Tokens* | Taavi ise, kui administraator on PAT-id lubanud | Loa nimi + saladus. Saladus läheb ainult repo *Secrets*'i (`TABLEAU_PAT_NAME`, `TABLEAU_PAT_SECRET`, `TABLEAU_SITE`), mitte koodi ega vestlusse. Pääsuluba kehtib kuni 1 aasta, kasutaja õigustega. |
| 2 | **Teenusekonto + PAT** | Serveri administraator | Parim pikaajaline lahendus: eraldi konto, mis näeb ainult avalikke/KAUR-i projekte (*Viewer* + *View* õigus), ei oma muutmisõigust. |
| 3 | **Käivitus KAUR-i siseselt** (GitLab CI / siseserveri runner) | IT | PAT jääb sisevõrku (GitLab CI variable, masked+protected); tulemused (ainult skeem) saab avalikku repo'sse tuua. Sobib, kui `tableau.envir.ee` REST pole GitHubist ligipääsetav. |
| 4 | **Administraatori eksport** | Serveri administraator | Nt *Administrative Views* / `tabcmd` / REST päring administraatori sessioonis; tulemus CSV-na repo `data/`-sse. Ühekordne, ei uuene automaatselt. |
| 5 | **Tableau Metadata API (GraphQL)** | sama mandaadiga mis 1–2 | Annab ühe päringuga andmeallikad, väljad, töövihikud, andmeallikate päritolu (lineage). Peab olema serveris lubatud. |

Mandaadita (ei vaja midagi) on juba sees:

- `tableau_catalog.py` – vaate `.csv` eksport (töötas 2-l vaatel, Public'is 404);
- `tableau_vizql.py` – lehitseja kahe päringuga (vaatelehe konfig + `bootstrapSession`) leitud lehtede, väljade ja andmeallikate
  nimed avalikele vaadetele (ainult nimed, mitte andmed).

Need katavad ainult **avalikult embed-itud** vaated; serveri kinnised projektid ja andmeallikad jäävad nähtamatuks.

## Mida PAT-iga lisandub
Ligipääs REST-ile: kõik projektid, töövihikud, vaated, andmeallikad ja nende väljad ning uuendusajad
(`crawl_kaur_viz.py` → `tableau_envir_inventory.csv`, mis on juba kirjutatud ja saladused ootab).

## Mida ma **ei** tee
- Ei proovi sisse logida tundmatute või vaikimisi mandaatidega ega külalisena `tableau.envir.ee` REST-i kaudu.
- Ei salvesta alusandmeid; kataloog sisaldab ainult nimesid, tüüpe ja ridade arve.
