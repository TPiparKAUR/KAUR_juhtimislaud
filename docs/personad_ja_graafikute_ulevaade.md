# Personad, nende küsimused ja graafikute kriitiline ülevaade

Töödokument analüüsi ja graafikute kvaliteedi hindamiseks. Seis: 2026-10-05. Seda dokumenti ei
ole valdkonnaeksperdid üle vaadanud; kõik hinnangud "kinnitatud" tähendavad **kontrollitud
andmetest ja testidest**, mitte ekspertide nõusolekut.

## 1. Personad ja küsimused

Iga persoon: mida ta otsustab, mida ta tahab teada, kus leht seda praegu vastab ja kus **mitte**.

| Persoon | Otsus / ülesanne | Põhiküsimused | Praegu vastab | Puudub |
|---|---|---|---|---|
| **Klimatoloog** (Ilmateenistus / KAUR) | hindab aasta ja hooaja klimaatilist erilisust, kirjutab ülevaateid | Kui erakordne on 2025/2026 normi suhtes? Kas trend on robustne jaama- ja meetodivalikust sõltumata? Kas äärmusindeksid (ETCCDI) muutuvad? | kliimaleht: aastaanomaaliad, hooajatrendid, robustsus, äärmusindeksid, katvus | jaamade homogeniseerimine, **võrdlus ametliku rahvusliku keskmise reaga**, pikem rida kui 1991 |
| **Hüdroloog** (KAUR) | jälgib veeolukorda, hoiatab põua ja üleujutuse eest | Kas jooksev kuu on tavavahemikus? Kui madal on madalvesi? Kas jaama andmed on usaldatavad? | hüdroloogialeht: kuuregiim koos jooksva aastaga, kestvuskõver, Q7min, tipud, katvus, kvaliteedisõel | veetase (WL), jääperiood, mõõtekõvera/ühiku kinnitus, ülejäänud 61 jaama |
| **Keskkonnapoliitika nõunik** (ministeerium) | seob andmed eesmärkidega ja aruandlusega | Kuhu on heited liikunud? Mida annab sektor/kütus? Kas muutus tuleb ETS-ist? | õhk ja energia (käitiste aruanded) | võrdlus riikliku inventuuriga, eesmärgid; **ainult asutuse aruanded, mitte kogu riigi heide** |
| **Omavalitsuse planeerija** | kohalik riskihinnang, loaotsused | Mis on minu piirkonnas: lähim jaam, kohalikud heited, põuariski signaalid? | jaamade trendid (üldiselt) | maakonna-/valla lõige, kaart |
| **Ajakirjanik / huviline** | kirjutab loo, kontrollib väiteid | Mis on peamine sõnum? Kui kindel see on? Kust allikas? | peamised tulemused tekstina, hoiatused, tabelivaated | lihtne "mida see ei tähenda" plokk, allalaetav CSV |
| **Teadlane / analüütik** | kasutab andmeid ja meetodit uuesti | Kuidas arvutati? Kas kood ja andmed on kättesaadavad? | meetodiplokk, avatud kood GitHubis | andmete versioonimine, DOI, viidatav väljalase |
| **Ettevõtte keskkonnajuht** | võrdleb end sektoriga | Kus ma asun sektori jaotuses? | (planeeritud) sektori jaotused | ainult koond: üksikettevõtteid ei näidata (privaatsus/konkurents) |

Põhimõte: leht ei anna soovitusi ega hinnanguid üksikettevõtetele; ainult koond ja ebakindlus.

## 2. Graafikute kontroll

Skaala: **Kindel** = kontrollitud andmete või testidega; **Eeldus** = lehel märgitud, kuid kinnitamata;
**Lahtine** = ei ole kontrollitud.

### Kliima (`ilm-ja-kliima`)

| Graafik | Küsimus | Faktikontroll | Tihedus | Teadaolevad nõrkused |
|---|---|---|---|---|
| Aastaanomaalia (tulbad, trend) | kui soe on aasta võrreldes 1991–2020 normiga? | **Kindel:** normi- ja anomaaliaarvutus testitud sünteetilise teadaoleva trendiga; kuu keskmine ühtib ööpäevaandmete keskmisega (suurim vahe 0,05 °C). **Lahtine:** ei ole võrreldud Ilmateenistuse ametliku rahvusliku keskmisega | kõrge (aasta, hajuvus jaamade vahel, trend, 3 rekordit) | jaamade lihtkeskmine (ilma pindala kaaluta); kriipsud ≠ mõõtemääramatus (märgitud) |
| Trend aastaajati (forest) | kus soojenemine on eristatav? | **Kindel:** Theil–Sen ja ploki-bootstrap testitud. Kokkuvõte ütleb: kevad ja sügis eristatavad, talv ja suvi mitte | keskmine | 35 aastat; talve suur kõikumine; vahemik laiem kui lugeja intuitsioon |
| Kuu × aasta soojuskaart | millal toimus soojenemine? | **Kindel:** riigi keskmine ≥ 5 jaamaga | kõrge | skaala ±5 °C kärbitud |
| Jaamade trendid | kas ühtlane? | **Kindel:** 20/20 jaama positiivne ja eristatav; vahemikud jaama kaupa | keskmine | ruumiline paiknemine puudub (pole kaarti) |
| Sademed % normist (tulbad, forest) | muutub sademete hulk? | **Kindel:** summade suhe, mitte kuusuhete keskmine; trend ei ole eristatav | keskmine | gabariidi alamõõtmine (märgitud); jaamad ≠ ühtlane võrk |
| Äärmusnäitajad (6 paneeli) | kas külmapäevad/kuumapäevad/sademed muutuvad? | **Kindel:** FD eristatav; HD30, TR20 ei ole eristatavad; medianist keskmiseks parandatud | keskmine | harvad sündmused on diskreetsed; lühike rida |
| Andmete katvus | kus on lüngad? | **Kindel:** kuude arv jaama-aasta kohta | keskmine | puuduvad jaamade nihked/ümberpaigutused (andmetes ei ole) |

### Hüdroloogia (`vesi`)

| Graafik | Küsimus | Faktikontroll | Tihedus | Teadaolevad nõrkused |
|---|---|---|---|---|
| Kuuregiim + jooksev aasta | kas jooksev aasta on tavavahemikus? | **Kindel:** P10/mediaan/P90 testitud; 2026 kokkuvõte loeb alla/üle. **Eeldus:** ühik m³/s | kõrge | 12–13 aasta "tavavahemik"; kuu vajab ≥ 25 kehtivat päeva |
| Erivoolu soojuskaart | millised jõed annavad vett millal? | **Eeldus:** ühik; mediaan 4–7 l/s/km² 15 jaamal; **Valgu 11,4** on tähelepanek | kõrge | reguleeritud jõgesid ei eristata; valgalade piirid kontrollimata |
| Kestvuskõver | kui sageli on erivool kindlast tasemest suurem? | **Kindel:** protsentiilid kehtivatest päevadest; telg 0,05 l/s/km² juures lõigatud | keskmine | UTC päevad; jääperiood ei ole eristatud |
| Aastane äravool, % jaama keskmisest | kas veerikkad/-vaesed aastad? | **Kindel:** aasta ≥ 350 päeva; keskmine jaamade lõikes | keskmine | jaamade arv muutub (13→15); 2012 on esimene täisaasta |
| Sademed vs äravool | kuidas sademed jõuavad jõgedesse? | **Kindel:** Spearmani ρ = 0,90 (0,61…1,00, n = 14). **Märkus:** sademed 1991–2020 normi suhtes, äravool 2012–2025 keskmise suhtes: võrreldud on järjestusi, mitte absoluutväärtusi | keskmine | n väike; ei tõesta põhjuslikkust (lumi, aurumine, sademete jaotus) |
| Tipp ja Q7min (jaam valitav) | kui suur on tipp / madalvesi? | **Kindel:** testitud; Tori min/max read lühikesed ja jäetakse välja | madal-keskmine | 13 aastat: korduvusaegu ei hinnata |
| Veetemperatuur | millised suved olid soojad? | **Eeldus:** ühik °C; vahemik 0…27,6 | keskmine | anduri asukoht; Narva linn alates 2017 |
| Katvus | kus on lüngad? | **Kindel** | madal | 2026 on pooleli (märgitud) |

### Välisõhk (`valisohk`) ja energeetika (`energeetika`)

Allikas: käitajate deklareeritud aastaaruanded 2019–2025 (KOTKAS); **mitte** riiklik inventuur.

| Graafik | Küsimus | Faktikontroll | Tihedus | Teadaolevad nõrkused |
|---|---|---|---|---|
| Fossiilne CO₂ (ETS-jaotus) | kuhu on heide liikunud? | **Kindel:** ühikud t/kg/mg → t; fossiilne ja biogeenne eraldi. **Lahtine:** langus 9,1 → 4,6 Mt on osalt aruandjate koosseisu muutus (1663 → 1353 aruannet) | kõrge | ETS-staatus puudub 2019–2022 suures osas → ETS-jaotus pole aastate vahel võrreldav (leht ütleb seda) |
| Biogeenne CO₂ | kui suur on biomassi osa? | **Kindel** (eraldi grupp) | madal | riiklikus aruandluses teine arvestus |
| Sektorid (NFR), ained, maakonnad | kus heide tekib? | **Kindel:** summad; **Lahtine:** NFR-nimed lühendatud, kontrollimata | kõrge | maakond = tegevuskoht; suurkäitised domineerivad |
| Kontsentratsioon (top 1/5/10) | kui haavatav on muutus üksikutele? | **Kindel** | keskmine | identiteete ei salvestata |
| Tundlikkus (kordused) | kui palju mõjutavad sama võtmega read? | **Kindel:** CO₂ 2,4–4,9%, SO₂ kuni 31% | keskmine | põhjus (meetodid/versioonid) selgitamata |
| Soojus ja elekter kütuse järgi | millest toodetakse? | **Eeldus:** ühik MWh (tuletatud soojus/kütus suhtest); 233 rida (2019: 170) välja jäetud | kõrge | **gaasi soojus 2019 → 2020 −62%: kontrollimata, andmeomanikult üle küsida** |
| Talv vs soojatoodang | kas külm talv tõstab? | **Lahtine:** 7 punkti, orientiir | madal | ei arvutata statistikut |

### Mets (`mets`): statistiline metsainventuur (SMI)

Allikas: SMI arvutustulemused (`f_smi_tulemused`, 332 433 rida, 1999–2024), iga hinnang koos suhtelise veaga.
Üksikasjad ja piirangud lehel endal; siin vaid ülevaatuse jaoks.

| Graafik | Küsimus | Faktikontroll | Tihedus | Teadaolevad nõrkused |
|---|---|---|---|---|
| Metsamaa pindala, tagavara, hektaritagavara (veavahemikuga) | kui palju mets on ja kas see muutub? | **Kindel:** read valitakse tabeli, näitaja ja täpse klassifikaatorikombinatsiooni järgi; puuliikide, omandirühmade ja majanduskategooriate summa = 100,0% kogusummast. **Eeldus:** ühikud (tuhat ha, tuhat m³) tuletatud suurusjärgust; viga = 95% poolvahemik (Mets 2021, lk 17, 124), andmebaasi `usaldusnivoo` on 0 | kõrge | periood 5 a: järjestikused aastad ei ole sõltumatud |
| Juurdekasv ja raie | kas raiutakse rohkem kui kasvab? | **Eeldus:** SMI raie, mitte raiedokumentide statistika; juurdekasvu definitsioon kinnitamata; suhte viga ligikaudne | keskmine | ei võrdu ametliku raiestatistikaga |
| Struktuur (puuliik, omand, majanduskategooria, vanus) | kuidas on mets jaotunud? | **Kindel:** summad tiilivad kogusumma; **Lahtine:** vanuseklassid (vaata allpool) | keskmine | vanuseklassid kahes skeemis (10 ja 20 a) samas klassifikaatoris |
| Maakonnad | kus on tagavara suurem? | **Kindel:** ±-vahemikud kuvatud | keskmine | väikeste rühmade viga suur (hinnangute 11% on ebatäpsemad kui ±50%) |
| Surnud puit | kui palju on kõdupuitu? | **Eeldus:** püsti + lamapuit liidetud ligikaudse veaga | madal | viga suur |

**Puänt (peamine sõnum) kõigil graafikutel.** Iga graafik algab lausega, mille arvud on arvutatud andmetest
ja mis ütleb ka ebakindluse. Test kontrollib, et ükski graafik ei jää ilma. Lause ei kasuta sõna «kasvab»
või «väheneb», kui muutus jääb veapiiri sisse.

## 3. Kui tihedad ja õiged need graafikud on?

**Tugevused:** kõigil graafikutel on allikas, ühik, periood, hajuvuse või ebakindluse märge ja
tabelivaade; tekstikokkuvõtted arvutatakse andmetest, mitte ei kirjutata käsitsi; piirangud on
nimetatud; kõik testid kontrollivad nii arvutust kui joonistamist.

**Nõrkused, mis ekspertidele paistavad kõigepealt:**
1. Kliima: puudub **sõltumatu kontroll** ametliku rahvusliku keskmisega (ilma selleta ei saa
   väita, et meie riigi keskmine ühtib ametlikuga). Samuti jaamade ruumilise kaalumise puudumine.
2. Hüdroloogia: **ühik ja mõõtekõver** pole andmeomaniku poolt kinnitatud; jäämõju talvel; Valgu.
3. Mõlemal: **lühikesed read** (35 ja 13 aastat) piiravad järeldusi; leht ütleb seda, aga
   mõned kokkuvõtted ("2026: 50% väljaspool tavavahemikku") on meie enda tavavahemiku suhtes
   ja sõltuvad 12 aasta valimist.
4. Puudub **kaardivaade** (jaamad, valgalad, maakonnad), mida planeerijad ootavad.
5. Praegu on kaetud 4 teemat 9-st (kliima, vesi osaliselt, välisõhk, energeetika); avaleht ei ole veel terviklik "seostatud" ülevaade.

## 4. Mida võib ja mida ei või lehel väita

| Võib | Ei või |
|---|---|
| "Aastakeskmine temperatuur on 1991–2025 kasvanud ~0,5 °C kümnendi kohta (95% vahemik 0,24…0,79)" | "Eesti on soojenenud X °C alates tööstusrevolutsioonist" (rida algab 1991) |
| "Viimase 20 aasta trend on kiirem, kuid vahemik on lai" | "Soojenemine kiireneb" |
| "2026. aasta kuu keskmised jäävad paljudes jaamades alla tavavahemiku" | "2026 on põuaaasta" (ei ole defineeritud põuaindeksit) |
| "Sademed ja äravool on seotud (ρ = 0,90)" | "Sademed põhjustavad X% äravoolust" |
| "Vooluhulga ühik on eeldatud m³/s" | "Vooluhulk on m³/s" ilma märketa |

## 5. Ülevaatuse protokoll

Iga eksperdi jaoks 5–8 küsimust, vastused repo issues'isse (silt `ekspert-ülevaatus`):

- **Klimatoloog:** Kas 1991–2020 jaamade lihtkeskmine on aktsepteeritav riigi keskmise lähend? Kas
  mõni jaam vajab homogeniseerimist? Kas ETCCDI valik (FD, ID, SU25, HD30, TR20, R10, R20, Rx1day) on piisav?
- **Hüdroloog:** Kas `Äravool` on m³/s ja `WL` cm? Kas jäämõju tuleks eraldi märkida? Kas
  Valgu pindala/kõver vajab parandust? Millised jaamad on reguleeritud?
- **Poliitikanõunik:** Millised aruanded seovad heitmed eesmärkidega? Kas ETS/non-ETS jaotus on
  õige lähenemine?
- **Kõik:** Kas järeldused on õiged, kas midagi olulist puudub, kas midagi on eksitav?

Staatus: kõik graafikud kannavad märget "valdkonnaekspert ülevaatamata", kuni vastav isik on
kinnitanud (või parandanud) iga graafiku iseseisvalt.

## Jäätmed ja ringmajandus (päris andmetega, 2004–2025)

Allikas: f_jaatmeliikumine_fix_riik, 20 139 963 rida loetud ja koondatud (kõik 22 aastat, ridade arv
võrdub serveri arvuga). Puänt-sõnumid tulevad andmetest; ühik (t) on eeldatud.

- Jäätmeteke: peatükk 10 (termilised protsessid, sh põlevkivituhk) on ~26% ja juhib aastatevahelist muutust;
  graafik näitab ka kogumit ilma selleta.
- Netokogused sisaldavad negatiivseid ridu (2025: −12,5 Mt); põhjus andmetest nähtamatu.
- Voogusid (teke, taaskasutus, ladestus, eksport jt) ei liideta ega suhestata: kattuvus teadmata
  (nt taaskasutus 2024 on suurem kui teke 2024).
- Ohtlike jäätmete osakaal langeb 2019 → 2020 u 40%-lt 10%-le; see viitab märkimise või klassifikatsiooni
  muutusele (põhjus kinnitamata), mitte tegelikule vähenemisele.
- Laoseisu lõpp vs. järgmise aasta algus erineb mediaanis suurelt: aruandjate koosseis/parandused piiravad
  järepidevust.

## Vesi: veekogumite seisund (päris andmetega)

Allikas: f_veekogumid, f_veekogumi_seisundid, f_veekogumid_koormus, f_pohjaveekogumi_seisud (1969 veekogumit
registris, 7041 seisundirida). Puänt-sõnumid tulevad andmetest; koondhinnangu koostis on kinnitamata.

- Täielikult hinnati ~730 veekogumit aastatel 2010 ja 2012-2015; 2016-2024 hinnatakse aastas vaid ~150, seega
  aastaid ei saa riikliku aegreana võrrelda. Hea või parema osakaal: 69% (2010) -> 57% (2015).
- Paaritatud võrdlus (sama veekogum, 2015 vs viimane hilisem hinnang): hea või parem 43% -> 29% (n=434);
  järvedel 39 -> 7 hea hinnangut 78-st. Selline järsk muutus viitab pigem meetodi muutusele; põhjus kinnitamata.
- Survetegurid: 745 hinnatud veekogumist 85%-l on oluline põllumajanduse survetegur; kõige sagedasem mõju on
  keemiline saastus (81%).
- Põhjavesi: 2014 ja 2020 kogumite hulgad ei kattu, muutust ei arvutata.
- Lämmastiku/fosfori kontsentratsioone ei kasutatud (<8% ridadest, ühik kinnitamata).

## Liigid ja ökosüsteemid (looduskaitse registrid, päris andmetega)

Allikas: f_alad, f_rahvalad, f_rahvalad_elupaikstat, f_rahvalad_lkohtstat, f_lkohad, f_vepid (ilma
koordinaatide ja vabatekstita). Tegu on registritega, mitte seirega.

- Kaitsealade pindalad kattuvad (vööndid, püsielupaigad), seega tüüpide vahel ei liideta.
- Natura elupaikade säilimisklass 2010 -> 2026 samas alas: 90% muutumata (138 paranes, 141 halvenes, n=2851);
  hinnang ei näita suunda.
- Vääriselupaikade registreerimine toimus kampaaniatena (2000-2001, 2018-2022); registreeritud arv ei ole
  tegelik arv. Kehtiva lepinguga 463 / 17 471 (2,7%).
- Liikide leiukohtade arv sõltub inventeerimisest; võõrliikide leiukohtadest 99% on katteseemnetaimed.
- Natura liikide kaitsestaatuse väli on ~40% ulatuses täitmata ja hinnatud kirjete hulk muutus versioonide
  vahel (2988 -> 2261); osakaalude muutust ei tõlgendata.

## Muld (seiretabel, päris andmetega)

Graafikud: pH, orgaaniline süsinik/huumus, toitained, raskmetallid perioodide kaupa (mediaan, p10–p90) ning
meetodite loetelu. Puänt on andmetest tuletatud ja märgib meetodimuutust; paarisvõrdlus puudub, kui korduvaid
proovialasid on alla 20. Ülevaatamata valdkonnaekspertide poolt.

## Välisõhu kvaliteet (seiretabel, päris andmetega)

Graafikud: jaamade aastakeskmiste mediaan ning vähim ja suurim jaam näitajate kaupa (valik), PM10
ületuspäevad aastas, meetodite plokk. Puänt võrdleb viimast aastat esimese aastaga, EL tasemega ja samade
jaamade muutust; ülevaatamata valdkonnaekspertide poolt, jaamatüüp teadmata.
