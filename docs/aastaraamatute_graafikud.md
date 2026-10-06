# Aastaraamatute graafikud: ülevaade, analüüs ja järeldused juhtimislaua parendamiseks

Seis: 2026-10-06. **Meetod ja piirang.** Aluseks on 12 allalaetud PDF-i joonise- ja tabelipealkirjad
(`yearbooks_summary.json`), mida klassifitseerib `analyse_yearbooks.py` märksõnade järgi. Pilte endid
ei ole analüüsitud ega täistekste loetud. Seetõttu saab öelda, **millest joonis räägib** (ajas muutus,
jaotus, lõige, teema), kuid **mitte**, kas see on joon-, tulp- või virnastatud diagramm, ega seda, kas
joonisel on veapiirid. Kõik allolevad arvud on pealkirjade põhjal hinnatud ja ligikaudsed; kahes keeles
trükitud pealkirjad (eesti/inglise) on loetud üks kord. Arvud on taastatavad (`yearbook_figures.json`
harul `yearbooks`, kui töövoog `yearbooks.yml` on uuesti käivitatud).

## 1. Ülevaade: mis graafikuid aastaraamatutes on

| Dokument | Lk | Jooniseid | Tabeleid | Joonist / 100 lk | Märkus |
|---|---|---|---|---|---|
| Eesti «Mets» 2021 | 337 | 93 | (ei tuvastatud) | 27,6 | tabelid pole tuvastatavate pealkirjadega |
| Eesti «Mets» 2020 | 322 | 92 | – | 28,6 | sama ülesehitus |
| Eesti «Mets» 2019 | 310 | 90 | – | 29,0 | sama ülesehitus |
| Eesti meteoroloogia 2025 | 114 | 10 | 1 | 8,8 | pealkirjad lühikesed, vorm ei tuvastu |
| Rootsi Naturvårdsverket 7071 | 82 | 8 | 7 | 9,8 | miljöömålide süvaanalüüs |
| Norra NIBIO 8/62 | 46 | 25 | 145 | 54,3 | tabelikeskne maakonnaraport |
| Norra Miljødirektoratet 2023 | 83 | 0 | 6 | 0 | asutuse töö aruanne |
| Taani Skovstatistik 2023 | 78 | 27 | 61 | 34,6 | |
| Taani Skovstatistik 2021 | 61 | 20 | 54 | 32,8 | |

Eesti RMK 2023 ja keskkonnaseire kokkuvõte 2022 ei andnud tuvastatavaid pealkirju. Soome allikatelt saadi
ainult veebilehed, Rootsi Skogsdata andis 404 (vt `aastaraamatute_oppetunnid.md`).

**Vormi järgi** (365 joonist kokku, pealkirja märksõnade põhjal; üks joonis võib kuuluda mitmesse):
ajas muutuvad (pealkirjas periood, «muutumine», «aastail», «utvikling») ≈ 55%; jaotus või osakaal
(«jagunemine», «fordeling», «andel») ≈ 43%; kaarte pealkirjade põhjal **ei tuvastatud ühtegi**.
Eesti «Mets» 2021: 55 ajas muutuvat ja 38 jaotust 93 joonisest; ligi 15 pealkirja ei sisalda
kumbagi märksõna (nt hinnad, üksikud ülevaated).

**Lõigete järgi** (Eesti «Mets» 2021, 93 joonist): puuliik 20, vanuseklass 14, omand 13, maakond/piirkond 11;
Norra NIBIO 25 joonisest 16 puuliigi ja 8 vanuse/raieküpsusklassi järgi; Taani joonised on vähem
lõikelised (mitu on üldised ajaread ja jaotused).

**Teemade järgi** (Eesti «Mets» 2021): raie 22, pindala 16, majandus/hinnad 8, jaht/tulekahju 8,
tagavara 7, tervislik seisund 3. Seega suurim kaal on raiel, hind ja pindala jaotusel, mitte tagavaral.

**Määramatus.** Ühegi tuvastatud joonise/tabeli pealkirjas ei mainita viga, usaldus- ega
konfidentsvahemikku, kuigi märksõna esineb 6–7 leheküljel igas Eesti «Metsa» köites, Rootsi
raportis 8 ja Norra aastaaruandes 10 leheküljel. Eesti käsiraamatus on viga kirjeldatud meetodi
märkuses ja tabelirea «Suhteline viga (±%)» kujul. **Pealkirjade põhjal ei saa öelda, kas jooniste
enda peal on veapiirid;** see tuleks kontrollida lehekülgi vaadates.

## 2. Analüüs: mida see tähendab

1. **Aegrida on põhivorm, aga alati selge perioodiga.** Üle poole joonistest on aegread ja pealkiri
   nimetab perioodi («aastail 1993–2022»). Hinnangulised seisud on eraldi tähistatud (nt «SMI, seisuga
   22.02.2023»).
2. **Samad lõiked kordusid.** Eesti raamatus korduvad puuliik, vanuseklass, omand ja maakond kõigis
   peatükkides; lugeja õpib neli telge korra ja leiab need alati samast kohast. Norra raport kasutab
   samuti kahte-kolme püsivat lõiget.
3. **Mahu juures on tabel, joonis on valik.** Norra (145 tabelit / 25 joonist) ja Taani (~60 / ~25)
   raamatud on tabelikesksed: joonis näitab mustrit, tabel annab täpse väärtuse ja vea.
4. **Ülevaade enne detaile.** Peatükid algavad ülevaatega; Taani raamat algab proovivõtu ülesehituse ja
   mõõdetud proovitükkide arvuga (tabel 1, joonis 1), enne tulemusi.
5. **Keskkonnaeesmärgid ja surveteguritega seotud osakaalud** (Rootsi: «andel rapporterade
   påverkansfaktorer och hot») on eraldi teema; seisund esitatakse koos eesmärgiga.
6. **Kakskeelsus.** Eesti raamatu pealkirjad on eesti ja inglise keeles.

## 3. Võrdlus meie juhtimislauaga

Meie saidil on kaheksa analüüsilehte (ilm ja kliima, vesi, välisõhk, energeetika, mets, jäätmed, liigid,
ökosüsteemid) ligikaudu 50 graafikuplokiga; igaühel on andmetest tuletatud puänt, tabelivaade ja märge
«valdkonnaekspert ülevaatamata». Vorm (ligikaudu, lehekoodist): aegread ja veatsoonid (mets, kliima,
õhuheited, hüdroloogia), osakaalu-virnad (jäätmed, vesi, loodus), horisontaalsed edetabelid
(jäätmeliigid, survetegurid, vääriselupaigad), paaritatud muutuse virn (vesi, Natura), maatriks/soojuskaart
(kliima, jäätmete kaubandus), hajuvusdiagramm (hüdroloogia, energeetika).

| Aspekt | Aastaraamatud (pealkirjade põhjal) | Meie juhtimislaud | Lünk |
|---|---|---|---|
| Pealkiri sisaldab perioodi, ühikut, allikat | jah (aasta/periood pealkirjas) | alapealkiri osaliselt; seisu kuupäev ainult metoodikaplokis | lisada igale graafikule «seisuga» ja periood |
| Püsivad lõiked | puuliik, vanus, omand, maakond kõigis peatükkides | metsal eraldi staatilised graafikud; teistel teemadel lõiked puuduvad | ühtne lõikevalija |
| Tabelid | arvukad, koos veaga | «Tabelivaade» iga graafiku all; allalaadimist ei ole | CSV allalaadimine |
| Määramatus | meetodimärkus ja vea rida tabelis | veatsoonid (mets), «n» alusel, paaritatud võrdlused | ühtne selgitus; usaldusnivoo kinnitamine |
| Metoodika | sissejuhatav ülesehituse osa | metoodikaplokk lehe lõpus | «Kuidas lugeda» lehe algusesse |
| Eesmärgid | eraldi teema (Rootsi) | enamasti puudub | eesmärgi/sihtväärtuse joon |
| Keel | eesti + inglise | ainult eesti | inglise sildid ELi aruandluseks |
| Teemade kaal | raie, pindala, hinnad kõrgel | mets: raie vs juurdekasv ühes graafikus | raie lõiked (liik, omand) |

## 4. Järeldused ja soovitused (tõendatud vs hinnang)

Märgis [tõend] = tuleneb ülaltoodud pealkirjade analüüsist; [hinnang] = minu soovitus, vajab ekspertide
kinnitust.

1. **Ühtne lõikevalija (puuliik, vanus, omand, maakond) igale näitajale** [tõend: neli lõiget
   kuuluvad kuni ~58 märgendiga 93 joonisest; hinnang: valija on parem kui staatilised graafikud]. Mets-lehel on
   need juba olemas, aga eraldi graafikutena; liita üheks valijaga.
2. **Iga graafiku alla kohustuslik rida: periood · ühik · allikas · seis (kuupäev) · määramatuse selgitus**
   [tõend: aastaraamatute pealkirjad kannavad perioodi ja seisu].
3. **CSV allalaadimine igale graafikule** (aggregeeritud väärtused veaga) [tõend: tabelikesksed Norra ja
   Taani raamatud; hinnang: eksperdid vajavad täpseid arve].
4. **«Kuidas lugeda» kast lehe algusse** (valim, hinnangu tüüp, perioodi kattuvus, mida ei saa järeldada)
   [tõend: Taani raamat alustab ülesehitusest; meie metoodika on lehe lõpus].
5. **Näita eesmärgi/sihttaseme vastu.** [tõend: Rootsi raport; hinnang: kõigepealt kasuta andmetes
   olemasolevat]. Veetabelis on seisundi ja eesmärgi read (tüüp S ja E; eesmärgid aastatele 2015, 2021 ja
   2027); seisundit saab kõrvutada kehtiva eesmärgiga. Teiste teemade eesmärgid (ELi, riiklikud) tuleb
   kinnitada ametlikust allikast enne lisamist; ma ei lisa neid mälu põhjal.
6. **Raie lõiked metsa teemas** [tõend: raie on suurim teema, 22 joonist/93; hinnang: SMI andmetes on
   raiehinnang olemas, riiklik raiestatistika on teine allikas ja nende võrdlus tasuks kontrollida].
7. **Kahekeelsed sildid** [tõend: Eesti raamatud; org-nõue: ELi/WMO aruandlus inglise keeles].
8. **Kaardid ei ole pealkirjade põhjal prioriteet** [tõend nõrk: pealkirjades kaarte ei tuvastatud; kuid
   kaardid võivad olla pealkirjata]. Enne kaardivaadete ehitamist kontrollida raamatuid lehekülgi
   vaadates.
9. **Hoia puänt ja veatsoonid.** Aastaraamatute pealkirjad on kirjeldavad («jagunemine»), meie omad
   järeldavad; see on lisaväärtus, aga iga puänt peab jääma andmetest tuletatuks ja ausaks (võrreldavus,
   n, meetodimuutus), nagu praegu.
10. **Kuupäevaline võrreldavus.** Kui näitaja ei ole aastate vahel võrreldav (nt vee seisund pärast 2015.
    aastat), tuleb seda graafikul näidata nagu praegu (n all), mitte aegreana.

## 5. Mida ei ole tehtud (ausalt)

- Joonisepilte ega täistekste ei ole analüüsitud; vormi ja veapiiride kohta ei ole tõendeid.
- Soome, Island, Rootsi Skogsdata, Statistikaamet ja Ilmateenistus puuduvad.
- PDF-id ei ole repos; neid hoiab ainult töövoo artefakt (30 päeva).
- Klassifikaatori märksõnad on minu valitud; viga võib olla (nt «maakonniti» lõikes loetud geograafiaks,
  «aastal 2022» ühe aasta seisuna ei loeta aegreaks).
