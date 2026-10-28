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
| olemas | 27 | 9 319 | 52% |
| osaliselt | 13 | 4 063 | 23% |
| puudub | 14 | 4 506 | 25% |

Teemati (vaatamised; katmata osa vaatamistest):

| Teema | Vaatamisi | Katmata |
|---|---|---|
| Jäätmed | 3 509 | 0% (SKP ja ringleva materjali määra vaated lisandusid) |
| Liigid | 2 627 | 75% (esialgne lindude indeks lisandus) |
| Ilm ja kliima | 2 371 | 18% |
| Vesi | 2 132 | 0% katmata (osaliselt kaetud: põhjaveebilanss, eutrofeerumine, reostuskoormus merre, põhjavee koondseisund) |
| Välisõhk | 1 932 | 24% |
| Mets | 1 849 | 21% |
| Seire (RKSP) | 1 259 | 20% (metsa-, mulla- ja välisõhuseire lisandus) |
| Energeetika | 772 | 34% (Statistikaameti energiabilanss lisandus) |
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

## Täiendus 2026-10-08: välisõhu seire seiretabelist

Lehele „Välisõhk“ lisandus jaamade mõõtmiste plokk (`air_analysis.py`): NO2, PM10, PM2,5, O3, SO2, CO,
benseen, benso(a)püreen ja metallid jaamade aastakeskmiste mediaanina (ning vähim ja suurim jaam), PM10
päevakeskmise ületuspäevad ja paaritatud muutus samade jaamade vahel (vähemalt 3 jaama). Eeldused:
read on päevakeskmised (tuletatud ridade arvust), jaama tüüpi tabelis ei ole, EL ja WHO võrdlustasemed on
käsitsi sisestatud ning kinnitamata. **Andmekvaliteet:** plii read on suures osas märgitud µg/m³, kuid väärtused
on ng/m³ suurusjärgus; need on välja jäetud, mistõttu plii jada lõpeb 2019. Õhukvaliteedi vastavushinnang
vajab ametlikku aruandlust ja jaamatüüpe.

## Täiendus 2026-10-12: põhjaveebilanss

Kõige vaadatum katmata vaade (Põhjaveebilanss, 1 011 vaatamist) on ehitatud (`gw_balance.py`). Veearuande
veehaarde kood ühtib registri (`f_veehaarded.kkr_kood`) koodiga 100% võetud mahust; registri puuraugud
(`f_veehaarded_puurauk.pohjaveekogum_id`) seovad veehaarde põhjaveekogumiga. Tulemus: (1) 2025. aasta
„põhjaveevõtust“ (252 Mm³) on 45% kaevandusvesi, 35% karjäärivesi ja 19% põhjavesi (48 Mm³), mis lahendab
varasema avatud küsimuse veevõtu ja veekasutuse veeliikide erinevuse kohta; (2) põhjaveekogumiga seotav võtt
(~19–24% kogumahust, ülejäänu kaevandus- ja karjäärivesi) on 20 kogumis kokku ~52% kinnitatud olmevarust ja
ainult ühes kogumis üle varu. Piirangud: varu ühik (m³/ööpäevas) on eeldatud, varu kehtib veemaardlatele
(mitte kogu kogumile), mitme kogumiga veehaarded on välja jäetud. Raskus: algselt arvasin, et seost ei ole
(koodid ei ühtinud varutabeli koodidega); see oli õige vaid otse varu tabeliga, registri kaudu seos on olemas.

## Täiendus 2026-10-12 (hiljem): lindude esialgne indeks; üraskid puuduvad avaandmetest

Haudelinnustiku punktloendustest (KESE, „Liigi haudepaaride arv“, 147 tuhat rida programmis „Haudelinnustiku
punktloendused“) on ehitatud lihtsustatud ahelindeks (`bird_analysis.py`, mitte TRIM ega ametlik indeks).
Koondindeks (74 liiki, 2 äärmusliku ahelaga liiki välja jäetud) on 2025. aastal 109 (2010 = 100), 95%
bootstrap-vahemik 96–118, st muutus ei ole eristatav; kõigi 76 kehtiva ahelaga liigiga oleks 117 (tundlik kahe
äärmusliku liigi suhtes, mida meetod ei suuda eristada artefaktist). Punktid ei ole juhuvalim ega elupaigati kaalutud.
**Üraskid ja kaitstav mets:** avaandmete tabelites ega seirekataloogis (400 näitajat)
üraskite andmeid ei leitud (otsitud tabelite nimedest ja kirjeldustest ning seirekataloogi näitajate nimedest); „Päevane püügiarv“ on linnujaamade rõngastuspüük, mitte üraskite püük.
Üraskite vaade jääb katmata kuni allika (metsakaitse seire, mitte KESE) leidmiseni.

## Täiendus 2026-10-12 (hiljem): suurkiskjad ei anna arvukust

Hundi-, karu- ja ilvesevaatluste (112 tuhat rida, 329 jahipiirkonda) esmane analüüs näitas, et aruandluse struktuur
muutub: nt karu aruandvaid piirkondi oli 268 (2022) ja 1 (2025), samal ajal kui vaatlusi 3 958 ja 5 510; ilvese
„Liigi isendite arv“ on ainult 2025. aasta kohta. Noorloomade osakaal ligi 100% (karu) viitab sellele, et „ad“
ja „juv“ read ei ole sama vaatluse osad. Seega ei ole arvukust, „min“ keskmist ega noorloomade osakaalu avaldatud;
lehel on ainult aruandluse struktuur. Vaade jääb „puudub“ kuni ametliku meetodi ja tabelistruktuuri selgituseni.

## Täiendus 2026-10-12 (hiljem): energeetika Statistikaameti andmetest

Avalikus Statistikaameti PxWeb API-s (`andmed.stat.ee/api/v1/et/stat`) leiti energiabilanss Eurostati metoodikaga
(KE0240, TJ, 1990–2024), elektrijaamade toodang kütuse järgi (KE033) ja paigaldatud võimsus (KE032). Leht
„Energeetika“ näitab primaarenergia tootmist (põlevkivi osa 94% (1990) → 52% (2024)), taastuvate osakaalu
energiabilansi GAE-s (2% → 33%), energiasõltuvust (netoimport / GAE, 1–41%, 2024: 5,7%), lõpptarbimist sektorite
kaupa ja elektritootmist (taastuvate osakaal 8% (2010) → 62% (2025), viimane aasta võib olla esialgne). **Piirangud:**
osakaalud on arvutatud bilansist ega ole ametlik SHARES-osakaal; elektri- ja soojuskaubandus on netona sees;
ekspordi märk tuvastati samasusest (jääk 0,008%); litsents (Statistikaameti avaandmed) ja viitamise nõue on
kinnitamata. Taastuvenergia osakaal on nüüd „osaliselt“, elektrienergia hulk „olemas“; energiasektori KHG inventuur
jääb katmata.

## Täiendus 2026-10-28: ringmajandus, jäätmed vs SKP ja soojatootmine

**Allikad:** Statistikaameti materjalivoo arvepidamine (KK99), jäätmebilanss (KK610), jäätmeteke tegevusala järgi (KK068), SKP
(RAA0012) ja Eurostati ringleva materjali määr (`cei_srm030`; Statistikaameti tabelites seda ei ole, otsisin ka võtmesõnadega
„ringlus“ ja „ringmajandus“). **Tulemused:** jäätmeteke 2025: 16,7 Mt (eeldatud tonnid; PxWeb-tabelis ühikut ei ole, suurusjärk
sobib materjalivooga), millest 52% on mäetööstuse ja termiliste protsesside jäätmed (jäätmenimistu peatükid 01 ja 10);
2002 = 100 korral on 2024. aastal reaalne SKP 177, DMC 143, jäätmeteke kokku 101 ja jäätmeteke ilma peatükkideta 01 ja 10
173 (st ilma mäetööstuse ja energeetika jäätmeteta ei ole lahtisidumist). Ringleva materjali määr Eestis 20,5% (2024), EL27
12,2% (Eurostat). Jäätmete taaskasutuse osakaal arvutati väljaminekust (töödeldud + ladestatud); esimene versioon
(taaskasutus / töödeldud) oli ~99% ja ei kandnud infot, seega asendati. **Soojatootmine** (KE034, KE035, KE20): koostootmise
soojatoodang 3 792 GWh (2025), kütuse taastuvate osakaal 56% (2025); enne 2011 on koostootmise kütuse energia puudulik
(kasulik toodang ületab kütuse energia) ja need aastad on kütusegraafikult välja jäetud. Piirangud: ühik eeldatud, SKP
aheldatud hinnad, lahtisidumine kirjeldav; litsents (Statistikaamet, Eurostat) ja viitamise nõue kinnitamata.
