/* Renders nature-conservation analyses from data/nature.json into [data-nature] hosts. */
(async () => {
  'use strict';
  const hosts = [...document.querySelectorAll('[data-nature]')];
  if (!hosts.length) return;
  const C = window.KaurCharts, { fmt } = C;
  let d;
  try {
    const res = await fetch('data/nature.json', { cache: 'no-cache' });
    if (!res.ok) throw new Error(res.status);
    d = await res.json();
  } catch (e) {
    for (const h of hosts) h.innerHTML = '<p class="viz-note">Looduskaitse analüüsi tulemused pole hetkel saadaval.</p>';
    return;
  }
  const N = C.NATURE, pa = d.protected_areas, hb = d.habitats, sp = d.species_stats, ss = d.species_sites, kh = d.key_habitats;
  const lastV = hb.per_version[hb.per_version.length - 1], firstV = hb.per_version[0];
  const share = (a, b) => (b ? (100 * a) / b : 0);
  const ha = (v) => `${fmt(v, 0)} ha`;
  const topLand = [...pa.by_type].filter((r) => r.n_land_area > 0).sort((a, b) => b.land_ha - a.land_ha);
  const goodShare = (v) => share(v.counts['1'] + v.counts['2'], v.rated);

  const builders = {
    /* ---- Ökosüsteemid ---- */
    efindings(host) {
      const li = [];
      li.push(`<li><b>Mida see on:</b> kaitsealade, Natura alade, Natura elupaigatüüpide ja vääriselupaikade registrite koondid (Keskkonnaagentuuri avaandmed). Nimesid ja koordinaate ei laeta ega avaldata. Pindalad kattuvad (vööndid ja püsielupaigad kaitsealade sees), seepärast ei liideta neid tüüpide vahel; ühik (ha) on eeldatud.</li>`);
      li.push(`<li><b>Kaitsealad:</b> ${fmt(pa.designated, 0)} kehtivat kaitsealust ala või objekti ja ${fmt(pa.planned, 0)} kavandatavat; suurima maismaapindalaga tüüp on ${topLand[0].name} (${ha(topLand[0].land_ha)}), mereosa suurim on hoiualadel.</li>`);
      li.push(`<li><b>Natura elupaigad:</b> ${fmt(lastV.records, 0)} elupaigatüübi kirjet ${fmt(lastV.sites, 0)} alal (versioon ${lastV.version}); ${fmt(goodShare(lastV), 0)}% hinnatud kirjetest on „väga hästi“ või „hästi säilinud“. Sama ala ja elupaigatüübi võrdluses ${firstV.version} → ${lastV.version} on ${fmt(share(hb.paired.same, hb.paired.n), 0)}% klassist muutumata (${fmt(hb.paired.improved, 0)} paranes, ${fmt(hb.paired.worsened, 0)} halvenes, n=${fmt(hb.paired.n, 0)}).</li>`);
      li.push(`<li><b>Vääriselupaigad:</b> ${fmt(kh.n, 0)} registreeritud, kokku ${ha(kh.area_ha)}; ainult ${fmt(kh.with_contract, 0)} (${fmt(share(kh.with_contract, kh.n), 1)}%) on kehtiva lepinguga. Registreerimine toimus kampaaniatena (vt graafikut), seega registreeritud arvu kasv ei näita vääriselupaikade arvu muutust loodusesse.</li>`);
      host.innerHTML = `<ul class="findings">${li.join('')}</ul>`;
    },
    areas(host) {
      C.natureBars(host, { rows: topLand.map((r) => ({ name: `${r.name} (${fmt(r.n, 0)})`, value: r.land_ha })), unit: 'ha', title: 'Kaitsealade maismaapindala tüübi järgi', subtitle: 'Kehtivate kaitsealade ja objektide maismaapindala; sulgudes alade arv.', color: C.SLOTS[2],
        note: 'Tüüpide pindalad kattuvad ja neid ei liideta. Pindala puudub osal kirjetest (nt kudemis- ja elupaigad, mõned üksikobjektid). Ühik (ha) on eeldatud.' });
      C.punch(host, `Suurima maismaapindalaga tüüp on ${topLand[0].name} (${ha(topLand[0].land_ha)}), kuid arvult on kõige rohkem ${[...pa.by_type].sort((a, b) => b.n - a.n)[0].name} (${fmt([...pa.by_type].sort((a, b) => b.n - a.n)[0].n, 0)}); pindalasid ei liideta, sest tüübid kattuvad.`);
    },
    habgroups(host) {
      const g = hb.groups_latest;
      C.natureClasses(host, { cats: g.map((x) => ({ label: x.name, counts: x.counts, n: x.rated })), title: `Natura elupaigatüüpide säilimine rühmade kaupa (versioon ${lastV.version})`, subtitle: 'Osakaal hinnatud elupaigakirjetest, %; n = kirjete arv (ala × elupaigatüüp).', height: 330,
        note: 'Hinnang on Natura ala standardandmebaasi ala-taseme hinnang elupaiga säilimisele, mitte riiklik soodsa seisundi hinnang.' });
      const rs = [...g].filter((x) => x.rated >= 30).sort((a, b) => b.counts['3'] / b.rated - a.counts['3'] / a.rated);
      const worst = rs[0], best = rs[rs.length - 1];
      if (!(worst && best && worst !== best)) C.punch(host, `Hinnatud elupaigakirjeid on rühmades liiga vähe, et rühmi usaldusväärselt võrrelda (n=${g.reduce((a, x) => a + x.rated, 0)}).`);
      else C.punch(host, `Kõige suurema „keskmiselt või vähe säilinud“ osakaaluga rühm on ${worst.name.toLowerCase()} (${fmt(share(worst.counts['3'], worst.rated), 0)}% kirjetest, n=${worst.rated}), väikseima osakaaluga ${best.name.toLowerCase()} (${fmt(share(best.counts['3'], best.rated), 0)}%, n=${best.rated}).`);
    },
    habchange(host) {
      C.naturePaired(host, { paired: hb.paired, label: `${hb.paired.from} → ${hb.paired.to}`, title: 'Natura elupaiga säilimisklassi muutus samas alas', subtitle: 'Osakaal kirjetest, mis on hinnatud mõlemas versioonis; n = kirjete arv.', note: 'Hinnang on ekspertide ja andmete täiendamise tulemus; muutus ei pruugi kajastada tegelikku muutust looduses.' });
      C.punch(host, `Sama ala ja elupaigatüübi säilimisklass on ${hb.paired.from}. ja ${hb.paired.to}. versioonis ${fmt(share(hb.paired.same, hb.paired.n), 0)}% kirjetest sama (paranes ${fmt(hb.paired.improved, 0)}, halvenes ${fmt(hb.paired.worsened, 0)}); Natura hinnang ei näita seega mõõdetavat suunda.`);
    },
    keyhab(host) {
      const t = kh.by_type.slice(0, 12);
      C.natureBars(host, { rows: t.map((r) => ({ name: r.name, value: r.area_ha, note: `${fmt(r.n, 0)} vääriselupaika` })), unit: 'ha', title: 'Vääriselupaigad tüübi järgi', subtitle: `Registreeritud vääriselupaikade pindala (12 suurimat tüüpi ${kh.by_type.length}-st).`, color: C.SLOTS[2], fmt: (v) => fmt(v, 0),
        note: 'Vääriselupaigad on metsa tüübiti tuvastatud elupaigad; pindala ha (eeldatud).' });
      C.punch(host, `Kõige suurema pindalaga tüüp on „${t[0].name}“ (${ha(t[0].area_ha)}, ${fmt(share(t[0].area_ha, kh.area_ha), 0)}% koguala ${ha(kh.area_ha)}).`);
    },
    keyhabYear(host) {
      const rows = kh.by_year.map((r) => ({ year: r.year, value: r.n }));
      C.natureYearly(host, { rows, unit: 'tk', label: 'Esmakordselt registreeritud vääriselupaigad', title: 'Vääriselupaikade esmaregistreerimine aasta järgi', subtitle: 'Registreeritud vääriselupaikade arv esmase registreerimise aasta järgi.', note: `Esmase registreerimise kuupäev puudus või ei olnud tuvastatav ${fmt(kh.year_unparsed, 0)} kirjel.` });
      const top = [...kh.by_year].sort((a, b) => b.n - a.n).slice(0, 3).sort((a, b) => a.year - b.year);
      C.punch(host, `Registreerimine toimus kampaaniatena: ${top.map((r) => `${r.year} (${fmt(r.n, 0)})`).join(', ')}; registreeritud arvu kasv peegeldab inventeerimist, mitte vääriselupaikade tegelikku arvu.`);
    },
    /* ---- Liigid ---- */
    findings(host) {
      const li = [];
      li.push(`<li><b>Mida see on:</b> kaitsealuste liikide leiukohtade register ja Natura liikide statistika (Keskkonnaagentuuri avaandmed). Leiukohtade arv sõltub inventeerimise ulatusest ja registreerimise tavast, mitte liigi arvukusest. Koordinaate ja asukohakirjeldusi ei avaldata.</li>`);
      li.push(`<li><b>Leiukohad:</b> ${fmt(ss.total_sites, 0)} kehtivat leiukohta, neist ${fmt(ss.protected_species_sites, 0)} kaitsealuse liigi ja ${fmt(ss.alien_sites, 0)} võõrliigi leiukohta (neist ${fmt(ss.invasive_sites, 0)} invasiivset). Kaitsekategooriate järgi: I ${fmt(ss.by_category['I kategooria'], 0)}, II ${fmt(ss.by_category['II kategooria'], 0)}, III ${fmt(ss.by_category['III kategooria'], 0)}.</li>`);
      const a = ss.alien_by_group[0];
      li.push(`<li><b>Võõrliigid:</b> enamik registreeritud võõrliikide leiukohti on rühmas ${a.name.toLowerCase()} (${fmt(a.sites, 0)} leiukohta ${fmt(a.species, 0)} liigil).</li>`);
      const v = sp.per_version, f = v[0], l = v[v.length - 1];
      li.push(`<li><b>Natura liigid:</b> ${fmt(l.species, 0)} liiki ${fmt(l.sites, 0)} alal (versioon ${l.version}); hinnatud kirjetest on ${fmt(share(l.counts['1'] + l.counts['2'], l.rated), 0)}% heas või eeskujulikus kaitsestaatuses (versioon ${f.version}: ${fmt(share(f.counts['1'] + f.counts['2'], f.rated), 0)}%, kuid hinnatud kirjeid oli siis ${fmt(f.rated, 0)}, hiljem ${fmt(l.rated, 0)} – hindamisaluse muutus).</li>`);
      host.innerHTML = `<ul class="findings">${li.join('')}</ul>`;
    },
    spgroups(host) {
      const g = ss.by_group.slice(0, 10);
      const cats = g.map((x) => ({ label: x.name, counts: { 1: x.by_category['I kategooria'], 2: x.by_category['II kategooria'], 3: x.by_category['III kategooria'] }, n: x.by_category['I kategooria'] + x.by_category['II kategooria'] + x.by_category['III kategooria'] }));
      C.natureClasses(host, { cats, names: { 1: 'I kategooria', 2: 'II kategooria', 3: 'III kategooria' }, colors: { 1: '#c8312b', 2: '#ef8a2b', 3: '#e3c32b' }, title: 'Kaitsealuste liikide leiukohad rühmiti ja kaitsekategooriati', subtitle: 'Osakaal rühma kategooriaga leiukohtadest, %; n = leiukohtade arv.', height: 330,
        note: 'Kaitsekategooriata liigid (nt täpsustamata) on välja jäetud. Leiukohtade arv ei ole arvukuse mõõt.' });
      const top = g[0], mam = g.find((x) => x.name === 'Imetajad');
      C.punch(host, `Kõige rohkem leiukohti on rühmas ${top.name.toLowerCase()} (${fmt(top.sites, 0)} leiukohta ${fmt(top.species, 0)} liigil)${mam ? `; imetajatel on I kategooria osakaal ${fmt(share(mam.by_category['I kategooria'], mam.sites), 0)}%` : ''}, aga see kirjeldab registreerimist, mitte arvukust.`);
    },
    alien(host) {
      C.natureBars(host, { rows: ss.alien_by_group.slice(0, 8).map((r) => ({ name: r.name, value: r.sites, note: `${fmt(r.species, 0)} liiki` })), unit: 'leiukohta', title: 'Võõrliikide leiukohad rühmiti', subtitle: 'Registreeritud võõrliikide leiukohtade arv.', color: C.SLOTS[3],
        note: 'Võõrliikide registreerimine sõltub tähelepanust ja kampaaniatest (nt invasiivsete taimede kaardistus).' });
      const a = ss.alien_by_group[0];
      C.punch(host, `${fmt(share(a.sites, ss.alien_sites), 0)}% võõrliikide leiukohtadest on rühmas ${a.name.toLowerCase()} (${fmt(a.species, 0)} liiki); invasiivseks märgitud on ${fmt(share(ss.invasive_sites, ss.alien_sites), 0)}% võõrliikide leiukohtadest.`);
    },
    spstats(host) {
      const cats = sp.per_version.map((v) => ({ label: v.version, counts: v.counts, n: v.rated }));
      C.natureClasses(host, { cats, names: N.SP_NAMES, title: 'Natura liikide kaitsestaatus alal (standardandmebaasi versioonid)', subtitle: 'Osakaal hinnatud liigi × ala kirjetest, %; n = hinnatud kirjete arv.', height: 280,
        note: 'Kaitsestaatuse väli on suures osas täitmata (~40% kirjetest) ja versioonide vahel muutus hinnatud kirjete hulk; seetõttu ei ole versioonid otse võrreldavad.' });
      const v = sp.per_version, f = v[0], l = v[v.length - 1];
      C.punch(host, `Hinnatud Natura liigikirjetest on ${fmt(share(l.counts['1'] + l.counts['2'], l.rated), 0)}% heas või eeskujulikus kaitsestaatuses (versioon ${l.version}); versioonide vahel hinnatud kirjete arv muutus (${fmt(f.rated, 0)} → ${fmt(l.rated, 0)}), seega osakaalude muutust ei tõlgendata.`);
    },
    methods(host) {
      host.innerHTML = `<div class="methods"><b>Andmed ja meetod</b> <span class="review-flag">valdkonnaekspert ülevaatamata</span>
        <p><b>Allikas ja päritolu:</b> Keskkonnaagentuuri avaandmed (keskkonnaandmed.envir.ee): kaitsealad, Natura (rahvusvahelised) alad, Natura elupaigatüüpide ja liikide statistika, liikide leiukohad, vääriselupaigad. Tegu on registriandmetega, mitte süstemaatilise seirega.</p>
        <p><b>Tõlgendus (kinnitamata):</b> ${d.meta.interpretation.join(' ')}</p>
        <p><b>Piirangud:</b> registrite sisu sõltub inventeerimisest ja registreerimispraktikast; liikide arvukust ega elupaikade tegelikku seisundi muutust nende põhjal hinnata ei saa. Soovitatav on täiendada riikliku seire (nt EL elupaigatüüpide aruandluse) andmetega. Genereeritud ${d.meta.generated_utc.slice(0, 10)} (UTC).</p></div>`;
    },
  };
  for (const h of hosts) {
    const b = builders[h.dataset.nature];
    if (b) b(h);
  }
})();
