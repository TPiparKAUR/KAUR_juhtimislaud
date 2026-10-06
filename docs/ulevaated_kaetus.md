# Keskkonnaülevaate vaated ja nende katvus (genereeritud)

Genereeritud `analyse_ulevaated.py` poolt failidest `data/ulevaate_kaetus.toml` ja `data/tableau_public_workbooks.csv`. Vaatamiste arv on eeldatud kogu perioodi näit.

| Teema | Vaateid | Vaatamisi | Olemas | Osaliselt | Puudub | Vaatamistest katmata, % |
|---|---|---|---|---|---|---|
| Jäätmed | 10 | 3509 | 4 | 2 | 4 | 38 |
| Liigid | 4 | 2627 | 0 | 0 | 4 | 100 |
| Ilm ja kliima | 6 | 2371 | 4 | 0 | 2 | 18 |
| Vesi | 7 | 2132 | 2 | 3 | 2 | 16 |
| Välisõhk | 7 | 1932 | 2 | 3 | 2 | 24 |
| Mets | 5 | 1849 | 2 | 2 | 1 | 21 |
| Seire (RKSP) | 7 | 1259 | 2 | 0 | 5 | 59 |
| Energeetika | 3 | 772 | 0 | 1 | 2 | 71 |
| Ökosüsteemid | 2 | 761 | 0 | 1 | 1 | 35 |
| Muld ja maahõive | 3 | 676 | 0 | 0 | 3 | 100 |

## Vaated

| Teema | Vaade | Vaatamisi | Meie | Andmed | Märkus |
|---|---|---|---|---|---|
| Energeetika | Keskkonnaülevaade - Energeetika - Taastuvenergia osakaal | 286 | puudub | väline | Taastuvenergia osakaal on ametlikult energiabilansist (nt Statistikaamet); API-s puudub. |
| Energeetika | Rohemõõdikud - Energeetika - detail- energeetika - Energeetikasektori kasvuhoonegaaside heitkogused | 259 | puudub | teadmata | Sektori KHG inventuur; API-s ei ole tuvastatud vastavat tabelit. |
| Energeetika | Keskkonnaülevaade - Energeetika - Elektrienergia hulk | 227 | osaliselt | API:t_soojatoodang_curr | Käitiste soojus- ja elektritoodang õhuaruandest; riiklik elektrienergia hulk puudub. |
| Ilm ja kliima | Keskkonnaülevaade - Ilm ja kliima - Ilm ja kliima anomaaliad | 667 | olemas | API:f_kliima_* | Anomaaliad ja aastakeskmised kliimalehel. |
| Ilm ja kliima | Keskkonnaülevaade - Ilm ja kliima - Ilm ja kliima Külm_kuum | 531 | olemas | API:f_kliima_* | Äärmusnäitajad (kuum/külm) kliimalehel. |
| Ilm ja kliima | Keskkonnaülevaade - Ilm ja kliima - Keskmine aasta õhutemperatuur | 518 | olemas | API:f_kliima_* | Aasta keskmine temperatuur. |
| Ilm ja kliima | Eesti keskmine sademete summa | 238 | olemas | API:f_kliima_* | Sademete summa kliimalehel. |
| Ilm ja kliima | Rohemõõdikud - Kliimamuutused - detail - kliimamuutused - Kasvuhoonegaaside heitkogused | 229 | puudub | teadmata | KHG heitkogused (inventuur). |
| Ilm ja kliima | Keskkonnaülevaade - Ilma ja kliima - Ilm ja kliima KHG 2024 | 188 | puudub | teadmata | KHG 2024. |
| Jäätmed | Jäätmearuandlus_KKP jäätmete teemalehtede valdkonnad_Olmejäätmed | 579 | osaliselt | API:f_jaatmeliikumine_fix_riik | Olmejäätmed (jäätmearuandlus). |
| Jäätmed | Jäätmearuandlus_KKP jäätmete teemalehtede valdkonnad_Üldine ülevaade | 478 | olemas | API:f_jaatmeliikumine_fix_riik | Üldine ülevaade. |
| Jäätmed | Jäätmearuandlus_KKP jäätmete teemalehtede valdkonnad_Pakendijäätmed | 359 | puudub | API:f_jaatmeliikumine_fix_riik | Pakendijäätmed: peatükk 15 01 tuletatav, kuid ei ole tehtud. |
| Jäätmed | Jäätmearuandlus_KKP jäätmete teemalehtede valdkonnad_Biojäätmed | 341 | puudub | API:f_jaatmeliikumine_fix_riik | Biojäätmed; tuletatavus kontrollimata. |
| Jäätmed | Keskkonnaülevaade - Jäätmed - Jäätmed ja SKP | 331 | puudub | väline | Nõuab SKP andmeid (Statistikaamet). |
| Jäätmed | Keskkonnaülevaade - Jäätmed - Ringleva materjali määr | 321 | puudub | väline | Ringleva materjali määr on Eurostati näitaja. |
| Jäätmed | Jäätmearuandlus_KKP jäätmete teemalehtede valdkonnad_Ohtlikud jäätmed | 304 | olemas | API:f_jaatmeliikumine_fix_riik | Ohtlikud jäätmed. |
| Jäätmed | Keskkonnaülevaade - Jäätmed - Olmejäätmed | 284 | osaliselt | API:f_jaatmeliikumine_fix_riik | Meil riigi voogude tabel; olmejäätmete eraldi lõige (peatükk 20) on tuletatav, kuid ei ole tehtud. |
| Jäätmed | Jäätmearuandlus_KKP jäätmete teemalehtede valdkonnad_Ehitus - lammutusjäätmed | 260 | olemas | API:f_jaatmeliikumine_fix_riik | Ehitus- ja lammutusjäätmed on peatükk 17 jäätmetekke graafikul. |
| Jäätmed | Keskkonnaülevaade - Jäätmed - Kogujäätme teke valdkonniti | 252 | olemas | API:f_jaatmeliikumine_fix_riik | Teke peatükkide kaupa. |
| Liigid | Keskkonnaülevaade - Liigid - Liikide seisund | 785 | puudub | teadmata | Liikide seisundi hinnang (nt ELi aruandlus); meil ainult leiukohtade register. |
| Liigid | Keskkonnaülevaade - Liigid - Lindude indeks | 649 | puudub | teadmata | Lindude indeks (seire). |
| Liigid | Keskkonnaülevaade - Liigid - Punase nimestiku liigid | 631 | puudub | teadmata | Punane nimestik; API-s ei ole tuvastatud. |
| Liigid | Keskkonnaülevaade - Liigid - Suurkiskjate arvukus | 562 | puudub | teadmata | Suurkiskjate arvukus (seire). |
| Mets | Keskkonnaülevaade - Mets - Metsamaa pindala | 429 | olemas | API:f_smi_tulemused | Metsamaa pindala (SMI). |
| Mets | Keskkonnaülevaade - Mets - Lehtpuu_Okaspuu | 400 | olemas | API:f_smi_tulemused | Puuliigid (tagavara enamuspuuliigi järgi). |
| Mets | Keskkonnaülevaade - Mets - Üraskid | 391 | puudub | teadmata | Kuuse-kooreüraskid (metsakaitse seire). |
| Mets | Keskkonnaülevaade - Mets - Raiemahud | 346 | osaliselt | API:f_smi_tulemused | Meil SMI raiehinnang; ametlik raiestatistika on teine allikas. |
| Mets | Keskkonnaülevaade - Mets - Kaitstav mets | 283 | osaliselt | API:f_alad | Kaitstav mets: meil kaitsealad ja vääriselupaigad, mitte metsamaa osakaal. |
| Muld ja maahõive | Keskkonnaülevaade - Maahõive - Maahõive | 296 | puudub | väline | Maahõive jaotus. |
| Muld ja maahõive | Keskkonnaülevaade - Maahõive - Põllumuldade Ph | 202 | puudub | teadmata | Põllumuldade pH kaart. |
| Muld ja maahõive | Keskkonnaülevaade - Maahõive - Mahepõllumajanduse osakaal | 178 | puudub | väline | Mahepõllumajandusmaa osakaal (PRIA/Statistikaamet). |
| Ökosüsteemid | Rohemõõdikud - Elurikkus - detail - elurikkus - Loodusdirektiivi elupaigatüüpide seisund Eestis ja Euroopa Liidus | 497 | osaliselt | API:f_rahvalad_elupaikstat | Meil Natura SDF ala-taseme hinnang; EL elupaigatüüpide aruande seisund puudub. |
| Ökosüsteemid | Keskkonnaülevaade - Ökosüsteemid - Öko hüved ja sidusus | 264 | puudub | teadmata | Ökosüsteemiteenused vs sidusus. |
| Seire (RKSP) | RKSP - meteoroloogiline seire | 439 | olemas | API:f_kliima_* | Meteoroloogiline seire. |
| Seire (RKSP) | RKSP - Mullaseire | 269 | puudub | teadmata | Raskmetallid mullas. |
| Seire (RKSP) | RKSP - Kiirgusseire | 155 | puudub | teadmata | Kiirgusseire. |
| Seire (RKSP) | RKSP - Välisõhu seire | 141 | puudub | teadmata | Välisõhu seire. |
| Seire (RKSP) | RKSP - Kompleksseire | 99 | puudub | teadmata | Kompleksseire. |
| Seire (RKSP) | RKSP - Metsaseire | 79 | puudub | teadmata | Okka- ja lehekadu. |
| Seire (RKSP) | RKSP - Hüdroloogiline seire | 77 | olemas | API:f_hydroseire | Hüdroloogiline seire. |
| Välisõhk | Välisõhk - Heitkogused - Heitkoguste inventuur | 336 | osaliselt | teadmata | Heitkoguste inventuur (riiklik); meil käitiste aruanded. |
| Välisõhk | Välisõhk - Heitkogused - Heitkoguste ülevaade | 333 | osaliselt | teadmata | Heitkoguste ülevaade. |
| Välisõhk | Välisõhk - Heitkogused - Tegevusalade heide mullid | 273 | osaliselt | API:t_heitkogus_allikas_curr | Tegevusalade heide. |
| Välisõhk | Keskkonnaülevaade - Õhk - Peamised heiteallikad | 267 | olemas | API:t_heitkogus_allikas_curr | Sektorid (käitiste aruanded, mitte riiklik inventuur). |
| Välisõhk | Keskkonnaülevaade - Õhk - Peamiste saasteainete heitkogused | 254 | olemas | API:t_heitkogus_allikas_curr | Saasteained käitiste aruannetes. |
| Välisõhk | Välisõhk - Heitkogused - NEC eesmärgid | 241 | puudub | väline | NEC eesmärgid (riiklik vähendamiskohustus). |
| Välisõhk | Keskkonnaülevaade - Õhk - Õhusaaste tervisemõju | 228 | puudub | väline | Tervisemõju (EEA hinnangud). |
| Vesi | Põhjaveebilanss | 1011 | osaliselt | API:f_pohjaveevarud | Meil kinnitatud varud lasundi järgi ja põhjaveevõtt; bilanssi (varu vs võtt) ei saa ehitada ilma seoseta. |
| Vesi | Keskkonnaülevaade - Vesi - Pinnaveekogumite koondseisund | 245 | olemas | API:f_veekogumi_seisundid | Pinnaveekogumite seisund (paaritatud võrdlus). |
| Vesi | Keskkonnaülevaade - Vesi - Põhjaveekogumite koondseisund | 223 | osaliselt | API:f_pohjaveekogumi_seisud | Põhjaveekogumid 2014 ja 2020, hulgad ei kattu. |
| Vesi | Keskkonnaülevaade - Vesi - NO3 põhjavees | 186 | puudub | teadmata | Nitraat põhjavees (seire). |
| Vesi | Keskkonnaülevaade - Vesi - Veekasutus | 173 | olemas | API:t_awtabel004_curr | Veekasutus sektori ja veeliigi järgi 2022-2025 (veearuanded); neli aastat. |
| Vesi | Keskkonnaülevaade - Vesi - Eutrofeerumine | 156 | puudub | API:f_veekogumi_seisundid | Tabelis on FÜKE üldlämmastik/-fosfor (alla 8% ridadest); ühik kinnitamata. |
| Vesi | Keskkonnaülevaade - Vesi - Reostuskoormused merre | 138 | osaliselt | API:f_reoveealad_koormus | Meil väljalaskmete heitvee koormus (N, P jt) kokku, mitte merre jõudev koormus. |
