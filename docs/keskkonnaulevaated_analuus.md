# KAUR Keskkonnaülevaate vaated: kasutus, katvus ja prioriteedid

Seis: 2026-10-06 (uuendatud pärast veekasutuse ja heitvee lisamist). Tabel «vaated ja katvus» on genereeritud (`analyse_ulevaated.py`, väljund
`docs/ulevaated_kaetus.md` ja `.json`). Sisend: (1) Tableau Public profiili `keskkonnaagentuur.kaur`
töövihikute loetelu koos vaatamiste arvuga (`data/tableau_public_workbooks.csv`, 70 töövihikut),
(2) minu hinnang, kas vaade on meie saidil olemas (`data/ulevaate_kaetus.toml`, 54 vaadet).

## Mida ei ole tehtud (ausalt)

- Tableau vaateid ei ole avatud: hostid on sandboxist blokeeritud ja Tableau Public'i CSV-/töövihiku-
  allalaadimised andsid 404, seega **vaadete sisu, diagrammitüüpe ega filtreid ei tea**. Teada on ainult
  pealkiri, töövihiku nimi ja vaatamiste arv.
- Vaatamiste arv on eeldatud kogu perioodi näit (alates avaldamisest); avaldamisaastad ja ajalugu
  puuduvad, seega vanemad vaated on eelisseisus.
- Katvuse hinnang («olemas / osaliselt / puudub») on minu hinnang pealkirja ja meie lehe põhjal;
  valdkonnaeksperdid peavad kinnitama.
- Andmeallikas «teadmata» tähendab, et KAUR-i avalikus API kataloogis (302 tabelit) ei leitud ilmselget
  vastet; tabel võib siiski olla olemas, kuid ei ole tuvastatud.

## Tulemused (54 vaadet, kokku 17 888 vaatamist)

| Katvus | Vaateid | Vaatamisi | Osakaal vaatamistest |
|---|---|---|---|
| olemas | 22 | 7 288 | 41% |
| osaliselt | 13 | 4 366 | 24% |
| puudub | 19 | 6 234 | 35% |

Teemati (vaatamised; katmata osa vaatamistest):

| Teema | Vaatamisi | Katmata |
|---|---|---|
| Jäätmed | 3 509 | 19% (oli 38% enne olme-, pakendi- ja biojäätmete vooge) |
| Liigid | 2 627 | **100%** |
| Ilm ja kliima | 2 371 | 18% |
| Vesi | 2 132 | 0% katmata (osaliselt kaetud: põhjaveebilanss, eutrofeerumine, reostuskoormus merre, põhjavee koondseisund) |
| Välisõhk | 1 932 | 24% |
| Mets | 1 849 | 21% |
| Seire (RKSP) | 1 259 | 31% (metsaseire lisandus) |
| Energeetika | 772 | 71% |
| Ökosüsteemid | 761 | 35% |
| Muld ja maahõive | 676 | **100%** |

Kõige vaadatumad katmata või osaliselt kaetud vaated: Põhjaveebilanss (1011), Liikide seisund (785),
Lindude indeks (649), Punase nimestiku liigid (631), Olmejäätmed (579), Suurkiskjate arvukus (562),
Loodusdirektiivi elupaigatüüpide seisund (497, osaliselt), Kuuse-kooreüraskid (391), Pakendijäätmed (359).

## Järeldused

1. **Huvi ja meie katvus ei kattu.** Teema «Liigid» annab 2 627 vaatamist (kolmas suurim), aga meie
   leht kajastab ainult registreeritud leiukohti, mitte liikide seisundit, Punast nimestikku, lindude
   indeksit ega suurkiskjate arvukust. Ilm ja mets, kus oleme tugevad, on vaatamistes sama suurusjärk
   kui jäätmed ja vesi, kus on suured lüngad.
2. **Odavad, andmetega kaetavad lüngad.** (a) Vesi: põhjaveebilanss (1 011), veekasutus ja reostuskoormus
   merre; vastavad tabelid on API-s (`f_pohjaveevarud`, `t_awtabel004_curr`, `f_reoveealad_koormus`),
   tõlgendus on kontrollimata. (b) Jäätmed: olmejäätmed (peatükk 20), pakend (15 01), biojäätmed on
   tuletatavad juba koondatud jäätmeandmetest (tehtud ei ole).
3. **Liikide seisundi allikat ei tea.** Andmed on tõenäoliselt Tableau'sse laaditud muust allikast
   (seireandmed, EL aruandlus); enne ehitamist tuleb allikas välja selgitada (andmeomanik, KESE või
   `f_keskkonnaseire`). Soovitus: küsida KAUR-i liikide ja elupaikade ekspertidelt.
4. **Välised näitajad.** Taastuvenergia osakaal, ringleva materjali määr, mahepõllumajandusmaa osakaal,
   jäätmed vs SKP ja õhusaaste tervisemõju eeldavad väliseid allikaid (Statistikaamet, Eurostat, EEA);
   neid võib lisada ainult koos allika ja litsentsi märkimisega.
5. **Seire (RKSP) vaated on madala kasutusega** (77–439, mediaan 141): metsaseire, välisõhu seire,
   kiirgus ja kompleksseire ei ole meil kaetud ja nende sihtrühm on pigem eksperdid. Madalam prioriteet.
6. **Meie lisandväärtus.** Meil on olemas, mida Tableau pealkirjade põhjal ei paista olevat: veapiirid
   SMI näitajatel, paaritatud võrdlused (vesi, Natura), märgitud võrreldamatused (vee seisund pärast 2015,
   jäätmete negatiivsed read), puänt igal graafikul. Soovitus: säilitada.

## Soovitatud järjekord

| # | Valdkond | Põhjus | Eeldus |
|---|---|---|---|
| 1 | Vesi: veekasutus, veevõtt, heitvesi (**tehtud**); põhjaveebilanss, eutrofeerumine, nitraat avatud | 1 011 + 156 + 186 vaatamist | veevõtu ja varu seos; N/P ühik |
| 2 | Jäätmed: olmejäätmed, pakend, bio (**tehtud**) | 579 + 359 + 341 | ringleva materjali määr ja SKP-seos vajavad väliseid allikaid |
| 3 | Liigid: seisund, Punane nimestik, linnud, suurkiskjad | 2 627 vaatamist, 100% katmata | allika leidmine |
| 4 | Mets: üraskid, kaitstav mets | 391 + 283 | allika leidmine / `f_alad` |
| 5 | Energeetika, muld ja maahõive, seire | madalam kasutus, välised allikad | allikad ja litsentsid |

Järgmise sammuna tuleks #1 jaoks teha `water`-sarja uuring: `f_pohjaveevarud`, `f_pohjaveekogumid_pohjaveevaru`,
`t_awtabel004_curr`, `f_reoveealad_koormus` struktuuri ja grain-i raport (nagu veekogumite puhul), enne
analüüsi kirjutamist.

## Täiendus 2026-10-06: liikide ja seire allikas leitud

Avalikus API-s on `f_keskkonnaseire` (KESE keskkonnaseire pikk tabel, 9,98 mln rida 1949–2025, 29 näitajate
rühma, 2,9 mln liigiga rida). See katab metsaseire (okka-/lehekadu), vee- ja põhjavee seire, mullaseire,
välisõhu seire, kiirguse (väga väike maht) ja liikide loendused (isendite arv, haudepaarid, jäljerajad).
Tehtud: kataloog (`monitoring_catalog.py`), metsaseire võra seisund (`crown_analysis.py`, Mets leht),
seire ulatus ja liikide arv aastas (Liigid leht). **Tegemata:** lindude indeks, suurkiskjate arvukus,
liikide seisund ja Punane nimestik, sest nende arvutamine eeldab seiremeetodi (valim, kordused, mitmekordne
vaatlus) tundmist ja eksperdi kinnitust; tabelis ei ole ka Punase nimestiku kategooriat (ainult
kaitsekategooria `liik_kategooria`). Seiretabel katab veel mitu vaadet (nitraat põhjavees, jõgede TN/TP,
mullaseire raskmetallid), mille analüüs on järgmine samm.

## Täiendus 2026-10-06 (hiljem): vee kvaliteet seiretabelist

Põhjavee nitraat (90. protsentiil ja normi ületanute osakaal; mediaan jäetud välja, sest kuni 46% väärtustest on
märgitud „<“) ning üldlämmastiku ja -fosfori mediaanid jõgedes, järvedes ja rannikuvees on „Vesi“ lehel
(`wq_analysis.py`). Tulemused kirjeldavad seireandmeid (seirekohad ja proovivõtt erinevad aastati), mitte
veekogumi seisundi hinnangut. Põhjaveebilanss on endiselt osaliselt kaetud (varud + võtt eraldi).

## Täiendus 2026-10-06 (hiljem): muld seiretabelist

Mullaseire (pH, orgaaniline süsinik, huumus, P, K, Cu, Zn, Pb, Cd, Cr, Ni, Hg) on lehel „Muld ja maahõive“
(`soil_analysis.py`, 5-aastased perioodid alates 2002; mediaan, p10, p90). Maahõive ja mahepõllumajandus
vajavad välist allikat ja jäävad katmata. **Hoiatus:** analüüsimeetodid on perioodide jooksul muutunud
(pH KCl → ISO 10390, P Egner-Riehm → Mehlich III, Corg Tjurin → Dumas), seega perioodide erinevus ei ole
puhas ajatrend; korduvalt mõõdetud proovialasid on pH ja Corg paarisvõrdluseks alla 20.
