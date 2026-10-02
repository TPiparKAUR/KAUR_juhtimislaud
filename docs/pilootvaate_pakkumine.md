# Pilootvaate pakkumine

Seisuga 2026-10-02. Aluseks `data/kaur_viz_inventar.csv` (46 vaadet, käsitsi inventar; crawl pole
veel käivitatud, seega võib vaateid olla rohkem) ja Taavi vastused: **avalik GitHub Pages sait**,
sihtrühm avalikkus + sektori spetsialistid, sisu peab põhinema **avalikel andmetel ja teenustel**,
soovitud struktuur on **terviklik, teemasid seostav avaleht + iga valdkonna all eraldi analüüsid ja
graafikud**, teaduskirjanduse viited otsitakse eraldi.

## Inventari põhjal olemasolev struktuur

| Plokk | Vaateid | Töövihikud |
|---|---|---|
| Keskkonnaülevaade (9 teemat) | 34 | `Keskkonnalevaade-*`, `Rohemdikud-*` |
| Seire tulemused (7 valdkonda) | 7 | `RKSP-*` |
| Iseseisvad töölauad | 5 | erinevad (neist 1 `tableau.envir.ee`) |

Keskkonnaülevaate teemad (vaadete arv): vesi 6, ilm ja kliima 5, mets 4, liigid 4, jäätmed 4,
energeetika 3, välisõhk 3, muld ja maahõive 3, ökosüsteemid 2.

## Variandid

### A. Keskkonnaülevaade tervikuna (lai)
Avaleht seob kõik 9 teemat; iga teema saab oma alamlehe.
- Plussid: vastab otse soovile "terviklik + valdkonniti"; struktuur on juba olemas; avalik Tableau Public.
- Miinused: suurim maht (34 vaadet, 9 teemat, 9 kirjandusplokki); pilootina liiga lai, tuleks teha
  kõik korraga ja kvaliteet jääb pinnapealseks.

### B. Seire tulemused (spetsialistidele)
7 seirevaldkonda (meteo, hüdro, mets, välisõhk, kiirgus, komplekss, muld), igaüks üks vaade.
- Plussid: regulaarne uuendus, selge allikas, sobib spetsialistidele.
- Miinused: valdkonnad on omavahel nõrgemini seotud; vähe vaateid valdkonna kohta, "mitu analüüsi
  ja graafikut" ei täitu; avalikkusele raskemini loetav.

### C. Kliima–energia–õhk klaster (soovitus)
Avaleht "Keskkonnaülevaade" ühe seotud klastriga: **Ilm ja kliima (5) + Energeetika (3) +
Välisõhk (3) = 11 vaadet**, ühendavaks lõimeks kasvuhoonegaaside heitkogused (ilm ja kliima:
KHG heitkogused, KHG 2024; energeetika: sektori KHG heitkogused, taastuvenergia osakaal; välisõhk:
peamised heiteallikad, saasteainete heitkogused). Seos on sisuline ja ülaltoodud vaadete nimedest
nähtav. Lisaks saab seirevaate "Meteoroloogiline seire" siduda ilma ja kliima alamlehega.
- Plussid: näitab täpselt soovitud mustrit (hub + valdkonnalehed + teemadevahelised seosed) piisavalt
  väikesel mahul; kliima kohta on rikkalik avalik teaduskirjandus ja avalikud andmed; mõõdetav
  skaleerimine ülejäänud teemadele sama malliga.
- Miinused / riskid: kõigepealt tuleb kontrollida, kas alusandmed on avalikult kättesaadavad
  (Tableau Public töövihikute allalaaditavus, KAUR-i avaandmed, riiklikud allikad). Täpseid
  andmekogusid ja päringuid ei ole veel verifitseeritud; see on esimene ehituse-eelne samm.
  Päritolu (toor / QC-tud / tuletatud indeks) tuleb vaate kaupa märgistada.

## Soovitus
**C**, kasutades A struktuuri (hub + alamlehed) ja jättes B seirevaated hilisemaks laiendusfaasiks.
Esimene tulemus: avaleht + "Ilm ja kliima" täislehena (metoodika, andmeallikas, päritolu, ühikud,
ajavahemik, uuendussagedus, viited, ligipääsetav tabelivaade/CSV), seejärel Energeetika ja Välisõhk
sama mustriga.

## Enne ehitamist vaja otsustada / kontrollida
1. Variandi valik (A / B / C).
2. Käivitada crawl KAUR-i võrgust (`uv run python crawl_kaur_viz.py`), et inventar oleks täielik.
3. Vaatekaupa kontrollida avalike andmete allikad ja litsentsid (Tableau Public alusandmed,
   Copernicus/ECMWF piirangud enne taasavaldamist).
4. Teaduskirjanduse otsing eraldi sammuna; DOI-sid lisada ainult verifitseerituna.
