# KAUR Keskkonnaülevaate vaated: kasutus, katvus ja prioriteedid

Seis: 2026-10-06. Tabel «vaated ja katvus» on genereeritud (`analyse_ulevaated.py`, väljund
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
| olemas | 15 | 5 359 | 30% |
| osaliselt | 10 | 3 381 | 19% |
| puudub | 29 | 9 148 | 51% |

Teemati (vaatamised; katmata osa vaatamistest):

| Teema | Vaatamisi | Katmata |
|---|---|---|
| Jäätmed | 3 509 | 38% |
| Liigid | 2 627 | **100%** |
| Ilm ja kliima | 2 371 | 18% |
| Vesi | 2 132 | 78% |
| Välisõhk | 1 932 | 24% |
| Mets | 1 849 | 21% |
| Seire (RKSP) | 1 259 | 59% |
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
| 1 | Vesi: põhjaveebilanss, veekasutus, reostuskoormus | 1 011 + 173 + 138 vaatamist; tabelid API-s | tabelite tõlgendus (grain-uuring) |
| 2 | Jäätmed: olmejäätmed, pakend, bio | 579 + 359 + 341; andmed juba olemas | pipeline'i laiendus (lõige liigi koodi järgi) |
| 3 | Liigid: seisund, Punane nimestik, linnud, suurkiskjad | 2 627 vaatamist, 100% katmata | allika leidmine |
| 4 | Mets: üraskid, kaitstav mets | 391 + 283 | allika leidmine / `f_alad` |
| 5 | Energeetika, muld ja maahõive, seire | madalam kasutus, välised allikad | allikad ja litsentsid |

Järgmise sammuna tuleks #1 jaoks teha `water`-sarja uuring: `f_pohjaveevarud`, `f_pohjaveekogumid_pohjaveevaru`,
`t_awtabel004_curr`, `f_reoveealad_koormus` struktuuri ja grain-i raport (nagu veekogumite puhul), enne
analüüsi kirjutamist.
