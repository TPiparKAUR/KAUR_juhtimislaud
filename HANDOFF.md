# KAUR Tableau → teenuste veebileht: üleandmise kokkuvõte (Claude Code)

Koostatud 2026-10-02 Cowork-sessioonis. Eesmärk: võtta KAUR-i Tableau töölauad, ehitada neist paremini sisustatud, asjalikum ja automaatselt uuenev veebileht, kasutades teaduskirjandust, GitHub Actionsi (või GitLab CI) ja Pagesi.

## 1. Eesmärk ja piirangud

- Algatus: Taavi (AI/ML nõunik, KAUR). Idee: Tableau töölaud(ad) → sisukam veebileht + selgitused/metoodika + viited teaduskirjandusele, uuendus automatiseeritud minimaalse käsitööga.
- Organisatsiooni vaikimisi: sisemine versioonihaldus **GitLab (gitlab.sise.envir.ee)**, CI GitLab CI. GitHub/Pages sobib avaliku koodi ja avaandmete jaoks. Sisemisi ja isikuandmeid GitHubi ei panda.
- Standardid: CRS EPSG:3301 (rahvuslik), 4326 (vahetus), 3857 (veeb). Kõrgused EH2000. Ajad UTC/ISO 8601 andmetes, EET/EEST avalikus väljundis märgistatult. Ühikud nähtavad (veerunimedes).
- Andmete päritolu märgistada: toor, QC-tud, täidetud, homogeniseeritud, mudelanalüüs, reanalüüs, prognoos, tuletatud indeks. Mitte segada.
- Litsentsid (Copernicus, ECMWF, ärilised) kontrollida enne taasavaldamist. Mitte mingeid mandaate koodis.
- Kood: Python 3.12, uv, Ruff, pytest, tüübivihjed, logging, pathlib; Parquet CSV asemel; kood ja commitid inglise keeles; avalik tekst eesti keeles.
- Eeskuju samalt autorilt: repo `TPiparKAUR/kaur-oppekataloog` (staatiline sait; `scripts/build.py` + `catalog.py`, `data/`, uv, GitHub Pages, kuine Lychee link-check workflow). Sama muster sobib siia.

## 2. Mida leiti (Tableau inventar)

Fail: `kaur_tableau_inventar.csv` (46 vaadet; veerud: group, page_url, host, workbook, view, title).

- **Iseseisvad töölauad (5):** tuuleenergeetika võimsus (`Tuuleenergeetika/Tuul`, nimi tuletatud pildi URL-ist), kaitstavad alad / Natura 2000 (`KaitstavatejaNaturaaladeavalikvaade/Kaitstavadalad`), rõngastamised (`rngastamised-avalik/Eestirngastamised`, nädalane uuendus), liigivaatluste levikukaardid (`tableau.envir.ee`, `vaatlusedUTM10ruuduga/Loodusvaatlused`), kultiveerimismaterjal (`tableau.envir.ee`, `Kultiveerimismaterjal/Kultiveerimismaterjaljoonis`, leht „Metsainfo hetkeseis").
- **Seire tulemuste ülevaated (7)**, töövihikud `RKSP-*`: meteo, hüdro, mets, välisõhk, kiirgus, komplekss, muld.
- **Keskkonnaülevaade (9 teemalehte, 34 vaadet)**: töövihikud `Keskkonnalevaade-*` ja `Rohemdikud-*`.
- Tableau Public profiil: `keskkonnaagentuur.kaur` (profiili ennast ei avatud).
- Kaks serverit: **public.tableau.com** (enamus) ja **tableau.envir.ee** (KAUR-i oma Tableau Server).
- Teised tehnoloogiad portaalis: ArcGIS StoryMaps (aastaülevaated, taastuvenergia kaardirakendus `arcg.is/1fP8TD2`), Power BI (3 RMK vaadet lehel „Metsainfo hetkeseis"; kuuluvus RMK/KAUR ebaselge), Kliimaatlas, KESE (`kese.envir.ee`), `register.keskkonnaportaal.ee`, avaandmete failihoidla `avaandmed.keskkonnaportaal.ee`.

## 3. Teadaolevad lüngad ja riskid

- Inventar põhineb veebitööriista lehekokkuvõtetel, **mitte renderdatud HTML-il**. Keskkonnaülevaate/seire lehtedel nähti staatilisi pilte (`1_rss.png`); JS-ga ehitatud `<tableau-viz>` embed'id (nt kultiveerimismaterjal) jäid algul märkamata. Tõenäoliselt on veel vaateid, eriti `tableau.envir.ee` serveris ja `/teemad/*` lehtedel.
- `tableau.envir.ee` sisu (projektid, töövihikud, andmeallikad) on **kaardistamata**; avaleht on JS-rakendus.
- Tuuleenergia vaate nimi ja kõik vaadete sisu tõlgendused tuletatud URL-idest/lehekokkuvõtetest; kontrollida.
- Cowork-sessiooni egress-proxy blokeeris `keskkonnaportaal.ee` ja `tableau.envir.ee` (organisatsiooni poliitika), seega renderdatud läbikammimist seal teha ei saadud.
- Sitemap: indeks, alamsitemapid `https://keskkonnaportaal.ee/et/sitemap.xml?page=1` ja `?page=2` (lehtede arv teadmata).

## 4. Olemasolevad failid

- `crawl_kaur_viz.py`: **testimata** Playwright-skript (portaali sitemap → renderdatud lehed → `tableau-viz`, iframe, pildid, lingid, Power BI/ArcGIS; väljund `portal_embeds.csv`) + valikuline `tableau.envir.ee` inventar `tableauserverclient`-iga PAT-i abil (`TABLEAU_PAT_NAME`, `TABLEAU_PAT_SECRET`, `TABLEAU_SITE` keskkonnamuutujatest; väljund `tableau_envir_inventory.csv`).
- `kaur_tableau_inventar.csv`: eelnimetatud 46 vaadet.

## 5. Järgmised sammud Claude Code'is

1. Käivita `crawl_kaur_viz.py` võrgus, kust saidid kättesaadavad (KAUR-i võrk/arvuti). Paranda vead, lisa testid (ühikutestid `wb_view` ja URL-filtri jaoks, fikseeritud HTML-fiksuurid), Ruff + MyPy.
2. Liida `portal_embeds.csv` ja `tableau_envir_inventory.csv` olemasoleva inventariga; lisa veerg `tehnoloogia` (Tableau Public / Server / Power BI / ArcGIS StoryMaps) ja `omanik` (KAUR/RMK/muu).
3. Vali **üks pilootvaade** (soovitus: seire või keskkonnaülevaade — regulaarne uuendus, selge allikas KESE/EELIS). Dokumenteeri andmeallikas, päritolu tase (toor/QC-tud/…), ühikud, ajavahemik, uuendussagedus.
4. Veebileht: staatiline sait (nagu `kaur-oppekataloog`): metoodika, andmeallikad, tõlgendus, viited teaduskirjandusele (tegelikud kontrollitud viited, DOI-d ainult kui verifitseeritud), litsentsi- ja kvaliteedimärkused. Tableau embed + ligipääsetav tabelivaade/CSV allalaadimine.
5. Automaatika: CI (GitLab CI sisemiselt; GitHub Actions + Pages avaliku osa jaoks): ajastatud ehitus, link-check (Lychee), andmekvaliteedikontrollid, metaandmete valideerimine, Pages deploy.
6. Hindamine: ligipääsetavus (WCAG), eesti/inglise keel, mobiil.

## 6. Avatud küsimused Taavile

- Kas veebileht on avalik (GitHub Pages) või sisemine (GitLab Pages)? Kellele (avalikkus, otsustajad, spetsialistid)?
- Milline töölaud on pilootvaade?
- Kas Power BI RMK vaated on KAUR-i hallatud?
- Kas on olemas PAT/ligipääs `tableau.envir.ee` serverisse (või administraatori kontakt)?
- Kas teaduskirjanduse viited tulevad kindlast nimekirjast (nt valdkonnaeksperdid) või otsib neid TI?

## 7. Soovituslik esimene prompt Claude Code'ile

> Loe `HANDOFF.md`, `kaur_tableau_inventar.csv` ja `crawl_kaur_viz.py`. Seadista Python 3.12 projekt (uv, Ruff, pytest), kirjuta `crawl_kaur_viz.py` testid ja paranda see; seejärel käivita see siin võrgus (kui võimalik) ja liida tulemused inventariga. Ära kirjuta mandaate koodi. Pakkumine pilootvaate valikuks enne ehitamist.
