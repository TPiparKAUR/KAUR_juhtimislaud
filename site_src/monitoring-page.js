/* Renders monitoring coverage and tree-crown condition from data/monitoring.json. */
(async () => {
  'use strict';
  const hosts = [...document.querySelectorAll('[data-monitoring]')];
  if (!hosts.length) return;
  const C = window.KaurCharts, { fmt, SLOTS } = C;
  const { el, frame, responsive, niceTicks, hover, axisY } = C.kit;
  let d;
  try {
    const res = await fetch('data/monitoring.json', { cache: 'no-cache' });
    if (!res.ok) throw new Error(res.status);
    d = await res.json();
  } catch (e) {
    for (const h of hosts) h.innerHTML = '<p class="viz-note">Keskkonnaseire analüüsi tulemused pole hetkel saadaval.</p>';
    return;
  }
  const cr = d.crown, cov = d.coverage;
  const NAMES = { 'harilik mänd': 'Harilik mänd', 'harilik kuusk': 'Harilik kuusk', arukask: 'Arukask' };
  const COLS = [SLOTS[1], SLOTS[2], SLOTS[0]];
  const pctv = (v) => `${fmt(100 * v, 0)}%`;
  const sgn = (v, n = 0) => `${v >= 0 ? '+' : '−'}${fmt(Math.abs(v), n)}`;
  const first = (a) => a[0], last = (a) => a[a.length - 1];

  /* Lines of several series on a common percent axis; series: [{label,color,data:[{year,value,n}]}] */
  function lines(host, o) {
    const series = o.series.filter((s) => s.data.length);
    const years = [...new Set(series.flatMap((s) => s.data.map((r) => r.year)))].sort((a, b) => a - b);
    const frm = frame(host, { title: o.title, subtitle: o.subtitle, legend: series.map((s) => ['dot', s.color, s.label]),
      table: { head: ['Aasta', ...series.flatMap((s) => [`${s.label} (%)`, `${s.label}: puid`])], rows: years.map((y) => [String(y), ...series.flatMap((s) => { const r = s.data.find((x) => x.year === y); return r ? [fmt(r.value, 1), fmt(r.n, 0)] : ['–', '–']; })]) }, note: o.note });
    responsive(frm, (box, w) => {
      const m = { l: 52, r: 14, t: 16, b: 28 }, h = o.height || 300;
      const svg = el('svg', { width: w, height: h, role: 'img', 'aria-label': o.title }, box);
      const top = Math.max(...series.flatMap((s) => s.data.map((r) => r.value)), 1) * 1.1;
      const { ticks } = niceTicks(0, top, 5);
      const x = (yr) => m.l + (w - m.l - m.r) * ((yr - years[0]) / (years[years.length - 1] - years[0] || 1));
      const y = (v) => m.t + (h - m.t - m.b) * (1 - (v - ticks[0]) / (ticks[ticks.length - 1] - ticks[0] || 1));
      axisY(el('g', {}, svg), y, ticks, w, m, '%', 0);
      for (const yr of years.filter((v, i) => i % Math.ceil(years.length / 8) === 0 || i === years.length - 1)) el('text', { x: x(yr), y: h - 8, 'text-anchor': 'middle', class: 'tick' }, svg, String(yr));
      for (const s of series) {
        el('path', { d: s.data.map((r, i) => `${i ? 'L' : 'M'}${x(r.year)},${y(r.value)}`).join(''), fill: 'none', stroke: s.color, 'stroke-width': 2.4 }, svg);
        for (const r of s.data) { const c = el('circle', { cx: x(r.year), cy: y(r.value), r: 3, fill: s.color, tabindex: 0 }, svg); hover(c, () => `<b>${r.year}</b><br>${s.label}: <b>${fmt(r.value, 1)}%</b><br>${fmt(r.n, 0)} puud, ${r.plots} prooviala`); }
      }
    });
  }

  const sp = (k) => cr.species[k] || [];
  const dmg = (rows) => rows.map((r) => ({ year: r.year, value: 100 * r.share_damaged, n: r.trees, plots: r.plots }));
  const extremes = (rows) => {
    const hi = rows.reduce((a, r) => (r.share_damaged > a.share_damaged ? r : a), rows[0]);
    const lo = rows.reduce((a, r) => (r.share_damaged < a.share_damaged ? r : a), rows[0]);
    return { hi, lo };
  };

  const builders = {
    mcfindings(host) {
      const all = cr.all, l = last(all), f = first(all), ex = extremes(all);
      const li = [];
      li.push(`<li><b>Mida see on:</b> riikliku metsaseire (KESE) puude võra okka-/lehekao hinnangud ${f.year}–${l.year}: ${fmt(cr.checks.rows, 0)} hinnangut, ${fmt(l.plots, 0)} prooviala (${l.year}). Hinnang on tabelis <b>klassina</b> (nt „>20-25%“), mitte arvuna; klassi esindab ülempiir. Kahjustusklassid on ICP Forests tavapärased (kinnitamata rakendus).</li>`);
      li.push(`<li><b>Kahjustunud puud (>25% okka-/lehekadu):</b> ${pctv(f.share_damaged)} (${f.year}) → ${pctv(l.share_damaged)} (${l.year}); kõrgeim ${pctv(ex.hi.share_damaged)} (${ex.hi.year}), madalaim ${pctv(ex.lo.share_damaged)} (${ex.lo.year}). Osakaal on puude, mitte proovialade lõikes.</li>`);
      for (const k of Object.keys(NAMES)) { const r = sp(k); if (r.length) li.push(`<li><b>${NAMES[k]}:</b> kahjustunud puid ${pctv(first(r).share_damaged)} → ${pctv(last(r).share_damaged)} (${first(r).year}–${last(r).year}), ${fmt(last(r).trees, 0)} puud ${last(r).year}.</li>`); }
      host.innerHTML = `<ul class="findings">${li.join('')}</ul>`;
    },
    mcrown(host) {
      const series = Object.keys(NAMES).map((k, i) => ({ label: NAMES[k], color: COLS[i], data: dmg(sp(k)) }));
      lines(host, { title: 'Kahjustunud puude osakaal (üle 25% okka-/lehekadu)', subtitle: 'Hinnatud puudest, % aastas; metsaseire proovialad (aastate lõikes ei pruugi proovialade koosseis olla sama).', series,
        note: 'Okka-/lehekadu on klassina; „kahjustunud“ = ülempiir üle 25%. Osakaal on puude lõikes; puude ja proovialade arv on tabelivaates. Esimeste aastate (1993–1996) kõrge mändide osakaal võib tuleneda hindamismeetodist või proovialade koosseisust (kinnitamata).' });
      const p = sp('harilik mänd'), k = sp('harilik kuusk');
      const al = last(cr.all);
      if (!(p.length && k.length)) C.punch(host, `Kahjustunud puude osakaal oli ${al.year}. aastal ${pctv(al.share_damaged)} (${fmt(al.trees, 0)} puud, ${al.plots} prooviala); liigipõhiseid võrdlusi ei ole piisavalt andmeid.`);
      else C.punch(host, `Kahjustunud puude osakaal ${last(p).year}. aastal: harilik mänd ${pctv(last(p).share_damaged)}, harilik kuusk ${pctv(last(k).share_damaged)}; aastate vaheline muutus võib kajastada ilmastikku, kuid ka proovialade koosseisu (puid ${fmt(last(p).trees, 0)} ja ${fmt(last(k).trees, 0)}).`);
    },
    mcrownclass(host) {
      C.selectable(host, Object.keys(NAMES).map((k) => ({ value: k, text: NAMES[k] })), 'harilik mänd', 'Puuliik:', (holder, key) => {
        const rows = sp(key);
        const series = ['none', 'slight', 'moderate', 'severe'].map((c, i) => ({ key: c, label: cr.meta.class_labels[c], color: ['#2e9e44', '#8cc152', '#ef8a2b', '#c8312b'][i], values: new Map(rows.map((r) => [String(r.year), r.trees ? (100 * r.counts[c]) / r.trees : 0])) }));
        C.stackedBars(holder, { years: rows.map((r) => String(r.year)), scale: 1, unit: '%', dec: 0, height: 300, noLabels: true, series, coverage: new Map(rows.map((r) => [String(r.year), r.trees])), title: `${NAMES[key]}: okka-/lehekao klassid`, subtitle: 'Osakaal hinnatud puudest, %; n = hinnatud puude arv.', note: 'Hindamata puud on välja jäetud; klassipiirid on ICP Forests tavapärased (kinnitamata).' });
        if (rows.length) { const a = first(rows), b = last(rows); C.punch(holder, `${NAMES[key]}: tugevalt kahjustunud või surnud puid ${fmt(100 * b.counts.severe / b.trees, 1)}% (${b.year}), mõõdukalt kahjustunud ${fmt(100 * b.counts.moderate / b.trees, 0)}%; ${a.year}. aastal vastavalt ${fmt(100 * a.counts.severe / a.trees, 1)}% ja ${fmt(100 * a.counts.moderate / a.trees, 0)}%.`); }
      });
    },
    mspecies(host) {
      const rows = cov.species_per_year, ys = rows.map((r) => String(r.year));
      C.stackedBars(host, { years: ys, scale: 1, unit: 'liiki', dec: 0, height: 280, noLabels: true, series: [{ key: 's', label: 'Registreeritud liike', color: SLOTS[2], values: new Map(rows.map((r) => [String(r.year), r.species])) }], coverage: new Map(rows.map((r) => [String(r.year), r.rows])), title: 'Seires registreeritud liikide arv aastas', subtitle: 'Liigid, mille kohta on aastas vähemalt üks seirerida; n = seireridade arv (liigiga read).',
        note: 'See on seire ulatuse, mitte liigirikkuse näitaja: liikide arv sõltub seirekavadest, rühmadest (nt metsaseire, linnud, selgrootud) ja määramisest.' });
      const a = rows.find((r) => r.year >= 1994), b = last(rows);
      C.punch(host, `Seires registreeritud liikide arv kasvas ${a.species} liigilt (${a.year}) ${b.species} liigini (${b.year}); see peegeldab seire laienemist (ridu ${fmt(a.rows, 0)} → ${fmt(b.rows, 0)}), mitte liigirikkuse muutust.`);
    },
    mgroups(host) {
      const rows = cov.groups.slice(0, 14).map((g) => ({ name: `${g.name} (${g.first_year}–${g.last_year})`, value: g.rows }));
      C.natureBars(host, { rows, unit: 'rida', title: 'Seireandmete maht näitajate rühma järgi', subtitle: 'Seiretabeli ridade arv rühmati; sulgudes esimene ja viimane aasta.', color: SLOTS[0],
        note: `Kokku ${fmt(cov.rows, 0)} rida. Rida on üks mõõdetud väärtus või vaatlus; maht ei näita keskkonnaseisundit.` });
      C.punch(host, `Suurimad rühmad on ${cov.groups[0].name.toLowerCase()} (${fmt(cov.groups[0].rows / 1e6, 1)} mln rida) ja ${cov.groups[1].name.toLowerCase()} (${fmt(cov.groups[1].rows / 1e6, 1)} mln); ${cov.groups.length} rühmast ainult ${cov.groups.filter((g) => g.last_year >= 2024).length} on andmeid aastast 2024 või hilisemast.`);
    },
    mmethods(host) {
      host.innerHTML = `<div class="methods"><b>Andmed ja meetod</b> <span class="review-flag">valdkonnaekspert ülevaatamata</span>
        <p><b>Allikas ja päritolu:</b> Keskkonnaagentuuri avaandmed (keskkonnaandmed.envir.ee), keskkonnaseire tabel (KESE), ${fmt(cov.rows, 0)} rida; metsaseire okka-/lehekadu ${fmt(cr.checks.rows, 0)} hinnangut. Tegu on seireandmetega, mitte arvukuse hinnangutega.</p>
        <p><b>Tõlgendus (kinnitamata):</b> ${d.meta.interpretation.join(' ')} ${cr.meta.interpretation.join(' ')}</p>
        <p><b>Piirangud:</b> okka-/lehekadu on visuaalne klassihinnang (hindajate erinevus ei ole andmetes); proovialade koosseis ei ole aastati tingimata sama; arvukuse ja asurkonna indekseid (nt lindude indeks, suurkiskjad) ei ole siin arvutatud, sest see nõuab seire kavaga arvestavat meetodit. Genereeritud ${d.meta.generated_utc.slice(0, 10)} (UTC).</p></div>`;
    },
  };
  for (const h of hosts) {
    const b = builders[h.dataset.monitoring];
    if (b) b(h);
  }
})();
