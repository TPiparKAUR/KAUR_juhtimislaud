# Seis ja järgmised sammud (salvestatud 2026-10-06)

Selle faili eesmärk on lasta jätkata ilma varasemat vestlust lugemata. Kõik analüüsid jooksevad GitHub
Actionsis (sandbox ei pääse Eesti hostidele); tulemused loetakse harudest `git fetch origin <haru>` +
`git show origin/<haru>:<fail>`.

## Valmis analüüsilehed (saidil)

| Lehe slug | Analüüs | Töövoog (andmed → analüüs) | Tulemuse haru |
|---|---|---|---|
| ilm-ja-kliima | kliima | climate_* | climate-results |
| vesi | hüdroloogia + veekogumite seisund | hydro_data, water_explore → water_analyse | hydro-analysis, water-analysis |
| valisohk, energeetika | käitiste õhuheited, soojus | airenergy_* | airenergy-analysis |
| mets | SMI metsainventuur | forest_explore → forest_analyse | forest-analysis |
| jaatmed | riigi jäätmestatistika (22 aastat) | waste_data (maatriks) → waste_analyse | waste-data-log, waste-analysis |
| okosusteemid, liigid | kaitsealad, Natura, leiukohad, vääriselupaigad | nature_explore → nature_analyse | nature-analysis |

Leht ehitatakse `pages.yml` poolt kõigist harudest; lisatud tulemused ilmuvad automaatselt.

## Uurimisdokumendid

- `docs/aastaraamatute_oppetunnid.md`: aastaraamatute ülesehitus, kümme põhimõtet (tõend/üldpraktika).
- `docs/aastaraamatute_graafikud.md`: jooniste ülevaade ja analüüs pealkirjade põhjal, soovitused.
- `docs/keskkonnaulevaated_analuus.md` + `docs/ulevaated_kaetus.md`: Tableau vaated, kasutus ja katvus.
- `docs/personad_ja_graafikute_ulevaade.md`: personad, graafikute kontroll, päris andmete leiud.

## Põhireeglid (kehtivad jätkuvalt)

- Eestikeelne tekst saidil, inglise keel koodis ja commit'ides; tõlgendused märgitud «kinnitamata»;
  ühikud, päritolu ja võrreldavus nähtavad; ei mingeid koordinaate, nimesid ega isikuandmeid.
- Iga graafik saab puänti (andmetest tuletatud ühe lause põhisõnum), mis ei väida rohkem kui andmed.
- Enne push'i: `uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest -q`
  (iga käsk eraldi gate; varem lasti MyPy viga läbi).
- API: ≤20 000 rida päringu kohta, järjestatud lehitsemine, ühine `kaur-api` concurrency-grupp.

## Järgmised valdkonnad (prioriteedi järjekorras; põhjendus `keskkonnaulevaated_analuus.md`)

1. **Vesi**: põhjaveebilanss, veekasutus (`t_awtabel004_curr`), reostuskoormus (`f_reoveealad_koormus`);
   esmalt struktuuri- ja grain-uuring (nagu `water_fetch.py` / `water_grain.py`).
2. **Jäätmed**: olmejäätmed (peatükk 20), pakend (15 01), biojäätmed koondatud andmetest.
3. **Liigid**: leida liikide seisundi, Punase nimestiku, lindude indeksi ja suurkiskjate allikas.
4. **Mets**: üraskid, kaitstav mets.
5. Energeetika, muld ja maahõive, seire: välised allikad ja litsentsid.

## Avatud küsimused / ekspertide kinnitus

- Vee koondhinnangu koostis (ÖSE/KESE, ökoloogiline seisund vs potentsiaal); seisundiklassi muutus järvedes.
- SMI suhtelise vea tõlgendus (95% pool-laius) ja `periood` tähendus.
- Jäätmetabeli ühik (t), negatiivsed read, ohtlike jäätmete osakaalu hüpe 2019 → 2020.
- Natura SDF säilimishinnangu seos EL aruandluse seisundiga.
- Aastaraamatute PDF-id ei ole repos (artefakt `yearbooks-raw`, 30 päeva); Soome, Island, Rootsi Skogsdata puuduvad.
