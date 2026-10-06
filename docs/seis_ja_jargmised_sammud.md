# Seis ja järgmised sammud (salvestatud 2026-10-06)

Selle faili eesmärk on lasta jätkata ilma varasemat vestlust lugemata. Kõik analüüsid jooksevad GitHub
Actionsis (sandbox ei pääse Eesti hostidele); tulemused loetakse harudest `git fetch origin <haru>` +
`git show origin/<haru>:<fail>`.

## Valmis analüüsilehed (saidil)

| Lehe slug | Analüüs | Töövoog (andmed → analüüs) | Tulemuse haru |
|---|---|---|---|
| ilm-ja-kliima | kliima | climate_* | climate-results |
| vesi | hüdroloogia + veekogumite seisund + veekasutus/heitvesi | hydro_data, water_explore → water_analyse, wateruse_explore → wateruse_analyse | hydro-analysis, water-analysis, wateruse-analysis |
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

1. **Vesi (tehtud 2026-10-06)**: veekasutus, veevõtt, heitvesi, reoveekogumisalad, põhjaveevarud. Avatud:
   põhjaveebilanss (varu vs võtt vajab veehaarde ja varu seost), eutrofeerumine (FÜKE N/P, ühik kinnitamata),
   nitraat põhjavees, reostuskoormus merre (merre jõudev osa).
2. **Jäätmed (tehtud 2026-10-06)**: olmejäätmed (ch 20), pakend (15 01), biojäätmete märge. Avatud:
   ringleva materjali määr ja jäätmed vs SKP (välised allikad), biojäätmete täpne definitsioon, olmejäätmete
   ametlik määratlus (võib erineda peatükist 20), märgete (sete, metall, probleemtooted) tähendus.
3. **Liigid / seire (käimas 2026-10-06)**: allikas leitud: `f_keskkonnaseire` (~10 mln rida, KESE
   keskkonnaseire pikk tabel: 2,9 mln liigiga ridu, 8,1 mln arvväärtust, 0,2 mln mõõtemääramatusega; ridu
   perioodil 1995–2025 ~9,7 mln). Samas tabelis on ka metsaseire, mulla-, vee-, põhjavee- ja välisõhuseire, mis
   katab mitu Tableau vaadet (metsaseire okka-/lehekadu, nitraat põhjavees, jõgede TN/TP, mullaseire).
   Samm 1: `monitoring_data.yml` (matriks aastate kaupa, kataloog näitaja × aasta × liik) →
   `monitoring-agg` artefakt + `monitoring-data-log` haru. Samm 2: kataloogi põhjal sihitud analüüsid.
   Lisaks: `f_rongastused` (1,3 mln rõngastust, 1995–2025; pingutuse näitaja, mitte arvukus).
4. **Mets**: üraskid, kaitstav mets.
5. Energeetika, muld ja maahõive, seire: välised allikad ja litsentsid.

## Avatud küsimused / ekspertide kinnitus

- Vee koondhinnangu koostis (ÖSE/KESE, ökoloogiline seisund vs potentsiaal); seisundiklassi muutus järvedes.
- SMI suhtelise vea tõlgendus (95% pool-laius) ja `periood` tähendus.
- Veevõtu ja veekasutuse veeliikide erinevus (põhjavesi 237 vs 45 Mm³ 2022; summa ühtib ±0,1%): kas kaevandus- ja karjäärivesi?
- Jäätmetabeli märked (`biojaatmed_lipp` jt) hõlmavad kirjeid, mille liik pole selle voo jäätmed (nt segaolmejäätmed ja sõnnik biojäätmete märkega).
- Jäätmetabeli ühik (t), negatiivsed read, ohtlike jäätmete osakaalu hüpe 2019 → 2020.
- Natura SDF säilimishinnangu seos EL aruandluse seisundiga.
- Aastaraamatute PDF-id ei ole repos (artefakt `yearbooks-raw`, 30 päeva); Soome, Island, Rootsi Skogsdata puuduvad.
