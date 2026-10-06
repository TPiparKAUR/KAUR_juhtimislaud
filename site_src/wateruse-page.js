/* Renders water use / discharge analyses from data/wateruse.json into [data-wateruse] hosts. */
(async () => {
  'use strict';
  const hosts = [...document.querySelectorAll('[data-wateruse]')];
  if (!hosts.length) return;
  const C = window.KaurCharts, { fmt, SLOTS, GREY } = C;
  let d;
  try {
    const res = await fetch('data/wateruse.json', { cache: 'no-cache' });
    if (!res.ok) throw new Error(res.status);
    d = await res.json();
  } catch (e) {
    for (const h of hosts) h.innerHTML = '<p class="viz-note">Veekasutuse analüüsi tulemused pole hetkel saadaval.</p>';
    return;
  }
  const M = 1e6, mm = (v) => `${fmt(v / M, 0)} Mm³`;
  const S = d.use_by_sector, first = S[0], last = S[S.length - 1];
  const years = S.map((r) => String(r.year));
  const SECT = { olme: 'Olme', toostus: 'Tööstus', jahutus: 'Jahutus', energeetika: 'Energeetika', pollumajandus: 'Põllumajandus', niisutus: 'Niisutus', muu: 'Muu' };
  const pctChange = (a, b) => (a ? (100 * (b - a)) / a : 0);
  const sgn = (v, n = 0) => `${v >= 0 ? '+' : '−'}${fmt(Math.abs(v), n)}`;
  const ds = d.discharge.years, dl = ds[ds.length - 1], df = ds[0];
  const cmp = d.discharge.compliance;
  const comp = (key, yr) => cmp.find((r) => r.key === key && r.year === yr);
  const absTot = (y) => d.abstraction.groundwater.filter((r) => r.year === y).concat(d.abstraction.surface.filter((r) => r.year === y)).reduce((a, r) => a + r.m3, 0);
  const matchPct = (y) => 100 * (absTot(y) / S.find((r) => r.year === y).kokku - 1);
  const ag = d.agglomerations, big = ag.by_size.find((r) => r.tyyp_selg.startsWith('Üle'));

  const sectorSeries = (skip = []) => {
    const base = Object.keys(SECT).filter((k) => !skip.includes(k)).map((k, i) => ({ key: k, label: SECT[k], color: SLOTS[i], values: new Map(S.map((r) => [String(r.year), (r[k] || 0)])) }));
    const rest = new Map(S.map((r) => [String(r.year), Math.max(0, (r.kokku || 0) - (r.sectors_sum || 0))]));
    base.push({ key: 'rest', label: 'Jaotamata (kokku − sektorite summa)', color: GREY, values: rest });
    if (skip.includes('jahutus')) for (const s of base) if (s.key === 'rest') for (const r of S) s.values.set(String(r.year), Math.max(0, (r.kokku || 0) - (r.sectors_sum || 0)));
    return base;
  };

  const builders = {
    wfindings(host) {
      const li = [];
      li.push(`<li><b>Mida see on:</b> veekasutajate aastaaruannete (veearuanne) koondid ${d.meta.years[0]}–${d.meta.years[d.meta.years.length - 1]}: veekasutus sektorite kaupa, veevõtt, heitvesi ja reostuskoormus, reoveekogumisalad. API-s on ainult viimased aruandeaastad (${d.meta.years.length}), seega ei ole see pikk aegrida ja aastate muutus võib kajastada aruandlust. Ühikud (m³, t, mg/l) on tabeli kirjeldusest eeldatud. Käitiste ega väljalaskmete nimesid ei avaldata.</li>`);
      li.push(`<li><b>Veekasutus:</b> deklareeritud kokku ${mm(first.kokku)} (${first.year}) → ${mm(last.kokku)} (${last.year}); jahutusvesi langes ${mm(first.jahutus)} → ${mm(last.jahutus)} (${mm(first.jahutus - last.jahutus)}), mis on suurem kui kogulangus (${mm(first.kokku - last.kokku)}); ilma jahutuseta veekasutus pigem ei vähenenud. Põhjus on andmetest nähtamatu (aruandlus või tegelik muutus).</li>`);
      li.push(`<li><b>Veevõtt:</b> põhjaveevõtt ${mm(d.abstraction.groundwater.at(-1).m3)} (${last.year}; ${sgn(pctChange(d.abstraction.groundwater.at(-2).m3, d.abstraction.groundwater.at(-1).m3), 0)}% eelmise aastaga), pinnaveevõtt ${mm(d.abstraction.surface.at(-1).m3)}. Põhja- ja pinnaveevõtu summa ühtib deklareeritud veekasutuse kogusummaga (erinevus ${sgn(matchPct(last.year), 1)}%, ${last.year}), kuid veeliigi järgi on põhjavett veekasutuses ainult ${mm((d.use_by_type.find((r) => r.aruandeaasta === last.year && r.veeliik === 'Põhjavesi') || { m3: 0 }).m3)}. Tõenäoline põhjus (kinnitamata): kaevandus- ja karjäärivesi on veevõtus põhjavesi, veekasutuses eraldi veeliik.</li>`);
      li.push(`<li><b>Heitvesi:</b> reostuskoormus ${last.year}: üldlämmastik ${fmt(dl.nyldkogus, 0)} t, üldfosfor ${fmt(dl.pkogus, 0)} t; ${fmt(100 * dl.calculated_share, 0)}% väljalaskmetest on arvutusliku, mitte mõõdetud kogusega.</li>`);
      li.push(`<li><b>Reoveekogumisalad:</b> ${fmt(ag.valid, 0)} kehtivat ala; ${fmt(big.n, 0)} üle 2000 ie ala annavad ${fmt(100 * big.load_pe / ag.load_pe_total, 0)}% koormusest (ie).</li>`);
      host.innerHTML = `<ul class="findings">${li.join('')}</ul>`;
    },
    wsector(host) {
      C.stackedBars(host, { years, scale: M, unit: 'Mm³', dec: 0, height: 320, series: sectorSeries(), title: 'Deklareeritud veekasutus sektori järgi', subtitle: 'Veearuandes deklareeritud veekasutus, Mm³ aastas (m³ eeldatud).', coverage: new Map(S.map((r) => [String(r.year), r.reports])),
        note: `n = aruannete arv. Sektorite veerud ei summeeru igal real kogusummani (ridadest ${fmt(100 * d.checks.sector_tiling.share, 0)}% sobib 1% täpsusega), seetõttu on „Jaotamata“ eraldi.` });
      C.punch(host, `Deklareeritud veekasutus langes ${mm(first.kokku)}-lt (${first.year}) ${mm(last.kokku)}-le (${last.year}); jahutusvee langus (${mm(first.jahutus)} → ${mm(last.jahutus)}) on suurem kui kogulangus; aruannete arv muutus vähe (${first.reports} → ${last.reports}).`);
    },
    wsectorRest(host) {
      const ex = S.map((r) => ({ y: String(r.year), v: (r.kokku || 0) - (r.jahutus || 0) }));
      C.stackedBars(host, { years, scale: M, unit: 'Mm³', dec: 0, height: 300, series: sectorSeries(['jahutus']), title: 'Veekasutus ilma jahutusveeta', subtitle: 'Sama, jahutus välja jäetud, et teised sektorid oleksid nähtavad; Mm³ aastas.', note: 'Jahutuse väljajätmine on esituse valik, mitte andmete parandus.' });
      const a = ex[0], b = ex[ex.length - 1];
      C.punch(host, `Ilma jahutusveeta oli deklareeritud veekasutus ${fmt(a.v / M, 0)} Mm³ (${a.y}) ja ${fmt(b.v / M, 0)} Mm³ (${b.y}); suurim osa on tööstus ja „muu“ (${fmt(((last.toostus || 0) + (last.muu || 0)) / M, 0)} Mm³, ${last.year}).`);
    },
    wtype(host) {
      const types = [...new Set(d.use_by_type.map((r) => r.veeliik))].map((t) => ({ t, tot: d.use_by_type.filter((r) => r.veeliik === t).reduce((a, r) => a + r.m3, 0) })).sort((a, b) => b.tot - a.tot);
      const top = types.slice(0, 5).map((x) => x.t), rest = types.slice(5).map((x) => x.t);
      const val = (t, y) => (d.use_by_type.find((r) => r.veeliik === t && r.aruandeaasta === y) || { m3: 0 }).m3;
      const series = top.map((t, i) => ({ key: t, label: t, color: SLOTS[i], values: new Map(S.map((r) => [String(r.year), val(t, r.year)])) }));
      if (rest.length) series.push({ key: 'rest', label: `Muud veeliigid (${rest.length})`, color: GREY, values: new Map(S.map((r) => [String(r.year), rest.reduce((a, t) => a + val(t, r.year), 0)])) });
      C.stackedBars(host, { years, scale: M, unit: 'Mm³', dec: 0, height: 300, series, title: 'Deklareeritud veekasutus veeliigi järgi', subtitle: 'Mm³ aastas; veeliik on aruande vee päritolu.', coverage: new Map(S.map((r) => [String(r.year), r.reports])) });
      const sw = val('Pinnavesi (jõed, järved)', last.year), gwv = val('Põhjavesi', last.year);
      const nrep = (pred) => d.use_by_type.filter((r) => r.aruandeaasta === last.year && pred(r.veeliik)).reduce((a, r) => a + r.reports, 0);
      C.punch(host, `${last.year}. aastal pärines ${fmt(100 * sw / last.kokku, 0)}% deklareeritud veest pinnaveest (jõed, järved) ja ${fmt(100 * gwv / last.kokku, 0)}% põhjaveest; aruandeid on põhjavee kohta ${fmt(nrep((t) => t === 'Põhjavesi'), 0)} ja pinnavee kohta ${fmt(nrep((t) => t.startsWith('Pinnavesi')), 0)}.`);
    },
    wabstraction(host) {
      const ab = d.abstraction, ys = ab.groundwater.map((r) => String(r.year));
      const series = [{ key: 'gw', label: 'Põhjavesi', color: SLOTS[0], values: new Map(ab.groundwater.map((r) => [String(r.year), r.m3])) }, { key: 'sw', label: 'Pinnavesi', color: SLOTS[2], values: new Map(ab.surface.map((r) => [String(r.year), r.m3])) }];
      C.stackedBars(host, { years: ys, scale: M, unit: 'Mm³', dec: 0, height: 280, series, title: 'Veevõtt aastas', subtitle: 'Veevõtt põhja- ja pinnaveest aruannete järgi, Mm³ aastas.', coverage: new Map(ab.groundwater.map((r) => [String(r.year), r.reports])),
        note: `n = põhjaveevõtu aruannete arv. Põhja- ja pinnaveevõtu summa ühtib deklareeritud veekasutuse kogusummaga (erinevus ${sgn(matchPct(last.year), 1)}% aastal ${last.year}), kuid veeliikide jaotus erineb: veevõtu „põhjavesi“ ja veekasutuse „Põhjavesi“ ei ole sama (tõenäoliselt kaevandus- ja karjäärivesi; kinnitamata).` });
      const g = ab.groundwater, a = g[g.length - 2], b = g[g.length - 1];
      C.punch(host, `Põhjaveevõtt oli ${mm(b.m3)} (${b.year}), ${sgn(pctChange(a.m3, b.m3), 0)}% võrreldes aastaga ${a.year}, aruannete arv peaaegu sama (${a.reports} → ${b.reports}); aastate muutuse põhjus (aruandlus või tegelik) on andmetest nähtamatu.`);
    },
    wloads(host) {
      const ys = ds.map((r) => String(r.year));
      host.innerHTML = '<div class="panels"></div>';
      const grid = host.firstChild;
      for (const [col, label, unit] of [['nyldkogus', 'Üldlämmastik', 't'], ['pkogus', 'Üldfosfor', 't'], ['bht7kogus', 'BHT7', 't'], ['helkogus', 'Heljum', 't'], ['khtkogus', 'KHT', 't']]) {
        const div = document.createElement('div'); grid.appendChild(div);
        C.stackedBars(div, { years: ys, scale: 1, unit, dec: 0, height: 200, noLabels: true, series: [{ key: col, label, color: SLOTS[1], values: new Map(ds.map((r) => [String(r.year), r[col]])) }], title: label, subtitle: `${fmt(dl[col], 0)} t (${dl.year})`, note: '' });
      }
      const dn = pctChange(ds[ds.length - 2].nyldkogus, dl.nyldkogus), dp = pctChange(ds[ds.length - 2].pkogus, dl.pkogus);
      C.punch(host, `Heitveega väljuv üldlämmastik oli ${fmt(dl.nyldkogus, 0)} t (${sgn(dn, 0)}% eelmise aastaga) ja üldfosfor ${fmt(dl.pkogus, 0)} t (${sgn(dp, 0)}%); ${fmt(100 * dl.calculated_share, 0)}% väljalaskmetest on arvutuslikud, seega aastate muutus võib olla arvutusmeetodi mõju.`);
    },
    wcompliance(host) {
      const keys = ['helj', 'kht', 'bht7', 'p', 'n'];
      const rows = keys.map((k) => ({ r: comp(k, dl.year), l: comp(k, df.year) })).filter((x) => x.r).map((x) => ({ name: x.r.pollutant, value: 100 * x.r.over_limit / x.r.with_limit, note: `${x.r.over_limit} / ${x.r.with_limit} väljalaskmest (${x.r.year}); ${x.l ? `${x.l.year}: ${fmt(100 * x.l.over_limit / x.l.with_limit, 1)}%` : ''}` })).sort((a, b) => b.value - a.value);
      C.natureBars(host, { rows, unit: '%', fmt: (v) => fmt(v, 1), title: `Väljalaskmed, mille kvartali kontsentratsioon ületab lubatud piirmäära (${dl.year})`, subtitle: 'Osakaal väljalaskmetest, millel on piirmäär märgitud; vähemalt üks kvartal üle piirmäära.', color: C.SLOTS[3],
        note: 'Kontsentratsioonid on suures osas arvutuslikud; ületamine ei tähenda automaatselt rikkumist (kvartali- vs aasta­keskmine piirmäär, lubatud erandid on andmetest nähtamatud).' });
      const t = rows[0], p = rows.find((x) => x.name === 'Üldfosfor');
      C.punch(host, `${t.name} piirmäära ületab ${fmt(t.value, 0)}% piirmääraga väljalaskmetest (${dl.year})${p ? `; üldfosfori puhul ${fmt(p.value, 0)}% (${df.year}: ${fmt(100 * comp('p', df.year).over_limit / comp('p', df.year).with_limit, 0)}%)` : ''}; arvutuslike väärtuste tõttu on need ülempiiri hinnangud.`);
    },
    wagglo(host) {
      const rows = ag.by_size.map((r) => ({ name: `${r.tyyp_selg} (${fmt(r.n, 0)} ala)`, value: r.load_pe, note: `${fmt(r.residents, 0)} elanikku` }));
      C.natureBars(host, { rows, unit: 'ie', title: 'Reoveekogumisalade reostuskoormus suurusklassi järgi', subtitle: 'Kehtivate reoveekogumisalade koormus (ie = inimekvivalent), sulgudes alade arv.', color: C.SLOTS[1],
        note: 'ie = inimekvivalent; koormus on registris märgitud väärtus (arvutuslik).' });
      C.punch(host, `${fmt(big.n, 0)} üle 2000 ie reoveekogumisala annavad ${fmt(100 * big.load_pe / ag.load_pe_total, 0)}% registreeritud koormusest (${fmt(ag.load_pe_total, 0)} ie) ja ${fmt(100 * big.residents / ag.residents_total, 0)}% elanikest.`);
    },
    wreserves(host) {
      const r = d.reserves, rows = r.by_aquifer.map((x) => ({ name: `${x.geol_indeks} (${fmt(x.deposits, 0)} varu)`, value: x.t1_olme }));
      C.natureBars(host, { rows, unit: 'T1 olme', title: 'Kinnitatud põhjaveevarud lasundi järgi (kehtivad kirjed)', subtitle: 'Varu kategooria T1 „olme“ summa lasundiindeksi (geoloogiline indeks) järgi; ühik eeldatud m³/ööpäevas.', color: C.SLOTS[0],
        note: `Kehtivaid kirjeid ${fmt(r.valid_records, 0)} / ${fmt(r.all_records, 0)}; kategooria T1 on täidetud ainult osal kirjetest. Varu ei ole võrreldav veevõtuga (veevõtu tabelil puudub seos varuga), seega see ei ole põhjaveebilanss.` });
      C.punch(host, `Suurim kinnitatud T1 olmevaru on lasundil ${r.by_aquifer[0].geol_indeks} (${fmt(r.by_aquifer[0].t1_olme, 0)}, ${fmt(100 * r.by_aquifer[0].t1_olme / r.t1_olme_total, 0)}% kogusummast); see ei ole veevõtuga võrreldav põhjaveebilanss.`);
    },
    wmethods(host) {
      host.innerHTML = `<div class="methods"><b>Andmed ja meetod</b> <span class="review-flag">valdkonnaekspert ülevaatamata</span>
        <p><b>Allikas ja päritolu:</b> Keskkonnaagentuuri avaandmed (keskkonnaandmed.envir.ee): veearuannete tabelid (veekasutus, veevõtt, heitvesi) aruandeaastatel ${d.meta.years[0]}–${d.meta.years[d.meta.years.length - 1]}, põhjaveevarude ja reoveekogumisalade registrid. Veearuanded on käitajate endi deklareeritud andmed.</p>
        <p><b>Tõlgendus (kinnitamata):</b> ${d.meta.interpretation.join(' ')}</p>
        <p><b>Piirangud:</b> neli aruandeaastat ei võimalda trendi hinnata; osa väärtustest on arvutuslikud; kontrollikontsentratsioonide tõlgendus (kvartal vs aasta) on kinnitamata; põhjaveebilanssi ei ole võimalik ehitada ilma veevõtu ja varu sidumiseta. Genereeritud ${d.meta.generated_utc.slice(0, 10)} (UTC).</p></div>`;
    },
  };
  for (const h of hosts) {
    const b = builders[h.dataset.wateruse];
    if (b) b(h);
  }
})();
