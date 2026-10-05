# Aastaraamatute õppetunnid juhtimislaua jaoks

Seis: 2026-10-05. **Mida loeti:** 12 avalikku dokumenti laaditi alla GitHub Actionsi käitusserveris
(analüüsi sandbox ei pääse neile saitidele ligi) ning sealt võeti ainult **ülesehitus**: lehekülgede arv,
järjehoidjad, joonise- ja tabelipealkirjad ning märksõnade (viga, usaldus, eesmärk, indikaator) ümbrused.
Täistekste ei ole loetud, seega alljärgnev tugineb pealkirjadele ja lühilõikudele. Kirjeldused on
minu sõnadega; see, mida **ei** tea, on märgitud. Kogu sisu on taastatav: `data/allikad.toml`,
`fetch_yearbooks.py`, töövoog `yearbooks.yml`.

## 1. Mida loeti ja mida mitte

| Dokument | Olek | Maht |
|---|---|---|
| KAUR Aastaraamat Mets 2019, 2020, 2021 | loetud (ülesehitus, pealkirjad) | 310–337 lk, ~90 joonist |
| KAUR Keskkonnaseire tulemuste kokkuvõte 2022 | loetud | 22 lk |
| KAUR Eesti meteoroloogia aastaraamat 2025 | loetud (pealkirjad osaliselt) | 114 lk |
| RMK aastaraamat 2023 | loetud (sisukord) | 80 lk |
| Taani Skovstatistik 2023, 2021 (IGN, Kopenhaageni Ülikool) | loetud | 78 ja 61 lk |
| Rootsi Naturvårdsverket, rapport 7071 (miljöömålide süvaanalüüs 2023, «Ett rikt växt- och djurliv») | loetud | 82 lk |
| Norra NIBIO rapport 8/62 (Møre og Romsdal, metsainventuur 2016–2020) | loetud | 46 lk |
| Norra Miljødirektoratet aastaaruanne 2023 | loetud (asutuse töö aruanne, mitte keskkonnaseis) | 83 lk |
| Soome Luke ja SYKE lehed | ainult HTML-pealkirjad | – |
| Rootsi Skogsdata 2025 | **ei saadud** (HTTP 404) | – |
| Island, Eesti Statistikaamet, Ilmateenistuse kliimaülevaated | **ei leitud/ei loetud** | – |

Soome Luke metsastatistika aastaraamatu kohta on lehe pealkiri «Publication of the Finnish Statistical
Yearbook of Forestry ends»; põhjust ei ole loetud.

## 2. Mida need raamatud teevad (kontrollitud tähelepanekud)

**Eesti «Mets» (KAUR).** Statistiline käsiraamat: peatükid Metsavarud, Metsaomand, Raied,
Metsauuendamine, Metsade tervislik seisund, Metsatulekahjud (lisaks õigusnormide eiramine, jahindus,
majandus). Iga peatükk algab ülevaatega ja jaguneb tabeliteks ja joonisteks; üle 90 numbreeritud joonise.
Standardlõiked: maakond, enamuspuuliik, vanuseklass, boniteediklass, kasvukohatüüp, omand. Pealkirjad on
kakskeelsed (eesti/inglise). Lk 17, 100 ja 124 märgivad, et SMI näitajate tegelik väärtus võib erineda
esitatust **vea ehk usaldusnivoo ulatuses**; tabelite iga aegrea all on rida «Suhteline viga / Relative
error (±%)» ja lk 124 nimetab usaldusnivoo 0,95. Andmed kannavad allikaviidet ja seisu kuupäeva
(«SMI, seisuga 22.02.2023»). Pikad read (1958–), LULUCF-i peatükk seob metsa kliimaaruandlusega.

**Taani Skovstatistik.** Peatükid järgivad üleeuroopalisi jätkusuutliku metsamajandamise kriteeriume ja
indikaatoreid: metsaressursid, tervis, tootmisfunktsioonid, elurikkus, kaitsefunktsioonid,
sotsiaal-majanduslikud funktsioonid. Algab peatükiga «Om Danmarks Skovstatistik» (kuidas valim on
kavandatud, ruudustik/proovitükid) ja tekstis rõhutatakse, et statistika on valimipõhine ning see mõjutab
tõlgendust. Iga peatüki lõpus on eraldi «Tabeller». Joonised on kakskeelsed (taani/inglise); näiteks
metsa pindala arengut 1881. aastast, pindala puuliikide ja vanuseklasside kaupa ning kasvava puistu
tagavara tulpadena koos hektaritagavaraga joonena.

**Rootsi Naturvårdsverket (miljöömålide süvaanalüüs).** Otsustusloogikaga struktuur:
kokkuvõte → 1 Nuläget (seis, vahendid, meetmed) → 2 Gapanalys (lünga analüüs; eraldi alapeatükk
«Osäkerheter» ehk ebakindlus ja kokkuvõttev tabel) → 3 «Når vi miljökvalitetsmålet?» (kas eesmärk
saavutatakse) → 4 Prognos → 5 Vajadus meetmete järele. Pealkirjad on osalt küsimused.

**Norra NIBIO.** Tabelikeskne: pindala maaliikide, valitseva puuliigi, raieklassi ja boniteedi
kaupa; muutus ajas vanuse, raieklassi, mahu, juurdekasvu ja diameetriklasside lõikes. Pealkirjas on
inventuuri periood (2016–2020). Aruande päises on tellija, märksõnad ja kättesaadavus; teksti
leidus ka süstemaatiliste mõõtmisvigade arutelu.

**RMK aastaraamat.** Organisatsiooni aruanne üldsusele: loodus, liikumine looduses, metsade
majandamine (maa ja varu ülevaade, metsatööd, puiduturustus), organisatsioon. Mõõdikud eesmärkide kaupa.

**KAUR keskkonnaseire kokkuvõte.** Struktuur seireprogrammide kaupa (meteoroloogia, välisõhk,
põhjavesi, siseveed, meri, elurikkus, mets, kompleksseire, kiirgus, seismoloogia, muld): sobib
juhtimislaua teemade ja andmeallikate kaardistamiseks.

## 3. Mida ei saa nendest raamatutest järeldada

* Graafikute **tüübid ja värvid** (ainult pealkirjad on loetud, mitte pildid).
* Kuidas veapiire joonisel kujutatakse (tabelites on viga eraldi reana; joonistest ei tea).
* Sihttasemete/eesmärkide joonistamine metsa peatükkides (märksõna «eesmärk» oli enamasti
  metoodika või õigusvaldkonna kontekstis).
* Rootsi, Soome, Islandi metsastatistika sisu (Skogsdata ja Luke ei olnud loetavad).

## 4. Rakendatavad põhimõtted (millest on tuletatud ja millest mitte)

Märgitud: **[allikas]** = otse loetud aastaraamatutest; **[üldpraktika]** = minu soovitus, mitte
nende raamatute järeldus.

1. **Iga tulemus koos veaga.** Aastaraamat Mets esitab viga iga aegrea all. [allikas] → Metsalehe iga
   SMI-graafik näitab ±-vahemikku ja arvu; erinevusi nimetame eristatavaks ainult siis, kui need ületavad
   ühendatud veapiiri.
2. **Metoodika ja valimi ülevaade enne tulemusi.** Taani raamat algab «Om statistikken». [allikas] →
   Metsaleht algab kasti «Kuidas see arvutati» (valim, periood, vea tõlgendus).
3. **Standardlõiked.** Maakond, omand, enamuspuuliik, vanus, boniteet, kasvukohatüüp. [allikas]
4. **Rahvusvaheline indikaatoripõhine struktuur.** Taani järgib üleeuroopalisi kriteeriume. [allikas] →
   Metsaleht rühmitatakse samade kriteeriumide järgi (ressurss, tervis, tootmine, elurikkus,
   kaitse, sotsiaalmajandus), kui andmed seda võimaldavad.
5. **Seis → lünk → hinnang → prognoos → vajadus.** Rootsi otsustusloogika. [allikas] → pikemas
   perspektiivis lisame teemadele «kas jõuame eesmärgini» plokid, kui eesmärgid on teada
   (eesmärke ei leiutata).
6. **Allikas ja seis iga graafiku all** («SMI, seisuga …»). [allikas]
7. **Kakskeelsus** (eesti/inglise pealkirjad). [allikas] → hilisem ülesanne.
8. **Puänt.** Iga graafik algab ühe lausega peamise sõnumiga, mis on **arvutatud andmetest** ja ütleb
   ka, mis on ebakindel. [üldpraktika; Rootsi küsimuspealkirjad toetavad mõtet] Lause ei tohi väita
   rohkemat, kui andmed lubavad (nt ei kirjuta «kasvab», kui muutus jääb veapiiri sisse).
9. **Eksperdile suunatud.** Täpsed arvud, ühikud, veapiirid, perioodid ja piirangud on nähtaval;
   üldsusele on kokkuvõtte plokk lehe alguses. [üldpraktika]
10. **Staatiliselt aastaraamatult elavale statistikale.** Soome Luke lõpetas aastaraamatu; selle põhjust
    ei ole loetud. [allikas: lehe pealkiri]
