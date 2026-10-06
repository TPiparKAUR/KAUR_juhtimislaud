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
  const maxY = +d.meta.generated_utc.slice(0, 4) - 1; // the running year is incomplete
  const MINN = 30; // fewer samples per year are not shown
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
      table: { head: ['Aasta', ...series.flatMap((s) => [`${s.label} (${o.unit || '%'})`, `${s.label}: ${o.nName || 'puid'}`])], rows: years.map((y) => [String(y), ...series.flatMap((s) => { const r = s.data.find((x) => x.year === y); return r ? [fmt(r.value, o.dec ?? 1), fmt(r.n, 0)] : ['–', '–']; })]) }, note: o.note });
    responsive(frm, (box, w) => {
      const m = { l: 52, r: 14, t: 16, b: 28 }, h = o.height || 300;
      const svg = el('svg', { width: w, height: h, role: 'img', 'aria-label': o.title }, box);
      const top = Math.max(...series.flatMap((s) => s.data.map((r) => r.value)), o.ref ? o.ref.value : 0, 1e-9) * 1.1;
      const { ticks } = niceTicks(0, top, 5);
      const x = (yr) => m.l + (w - m.l - m.r) * ((yr - years[0]) / (years[years.length - 1] - years[0] || 1));
      const y = (v) => m.t + (h - m.t - m.b) * (1 - (v - ticks[0]) / (ticks[ticks.length - 1] - ticks[0] || 1));
      axisY(el('g', {}, svg), y, ticks, w, m, o.unit || '%', o.axisDec ?? 0);
      if (o.ref) { el('line', { x1: m.l, x2: w - m.r, y1: y(o.ref.value), y2: y(o.ref.value), stroke: '#c8312b', 'stroke-dasharray': '5 4', 'stroke-width': 1.5 }, svg); el('text', { x: w - m.r - 4, y: y(o.ref.value) - 5, 'text-anchor': 'end', class: 'tick' }, svg, o.ref.label); }
      for (const yr of years.filter((v, i) => i % Math.ceil(years.length / 8) === 0 || i === years.length - 1)) el('text', { x: x(yr), y: h - 8, 'text-anchor': 'middle', class: 'tick' }, svg, String(yr));
      for (const s of series) {
        el('path', { d: s.data.map((r, i) => `${i ? 'L' : 'M'}${x(r.year)},${y(r.value)}`).join(''), fill: 'none', stroke: s.color, 'stroke-width': 2.4 }, svg);
        for (const r of s.data) { const c = el('circle', { cx: x(r.year), cy: y(r.value), r: 3, fill: s.color, tabindex: 0 }, svg); hover(c, () => `<b>${r.year}</b><br>${s.label}: <b>${fmt(r.value, o.dec ?? 1)} ${o.unit || '%'}</b><br>${r.extra || `${fmt(r.n, 0)} puud, ${r.plots} prooviala`}`); }
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
    sfindings(host) {
      const so = d.soil; if (!so) { host.innerHTML = '<p class="viz-note">Mullaseire andmeid ei ole.</p>'; return; }
      const I = so.indicators, li = [];
      li.push(`<li><b>Mida see on:</b> riikliku mullaseire (KESE) mulla (A-horisont ja muud proovid) mõõtmised alates 2002: ${fmt(so.checks.rows, 0)} väärtust ${fmt(so.checks.plots, 0)} proovialalt. Perioodid on 5-aastased ja proovialad ei ole perioodide vahel samad, seega perioodide mediaane ei tõlgendata trendina; muutust hinnatakse ainult proovialadel, mida on mõõdetud nii esimeses kui viimases perioodis (paaritatud). Normide ja sihttasemetega võrdlust ei ole tehtud.</li>`);
      const pr = (n) => I[n] && I[n].paired;
      for (const [n, u, dec] of [['pH', '', 2], ['Orgaaniline süsinik', '% KA', 2]]) {
        const p = pr(n); if (p) li.push(`<li><b>${n}:</b> samal ${fmt(p.plots, 0)} proovialal ${p.from} → ${p.to}: mediaan ${fmt(p.median_first, dec)} → ${fmt(p.median_last, dec)} ${u}; mediaanmuutus ${sgn(p.median_change, dec)}, kasvas ${fmt(100 * p.share_increased, 0)}% proovialadest.</li>`);
      }
      const metals = ['Vask', 'Tsink', 'Plii', 'Kaadmium', 'Kroom', 'Nikkel', 'Elavhõbe', 'Arseen'].filter((m) => I[m]);
      if (metals.length) li.push(`<li><b>Metallid (mg/kg kuivaines):</b> ${metals.map((m) => `${m.toLowerCase()} mediaan ${fmt(last(I[m].periods).median, 2)} (${last(I[m].periods).period})`).join('; ')}.</li>`);
      host.innerHTML = `<ul class="findings">${li.join('')}</ul>`;
    },
    sph(host) {
      const so = d.soil; if (!so || !so.indicators.pH) return;
      const pl = so.indicators.pH.periods.filter((r) => r.plots >= 20);
      const mk = (label, color, f) => ({ label, color, data: pl.map((r) => ({ year: +r.period.slice(0, 4) + 2, value: f(r), n: r.samples, extra: `${r.period}: ${fmt(r.samples, 0)} proovi, ${fmt(r.plots, 0)} prooviala` })) });
      lines(host, { title: 'Mulla pH (mullaseire)', subtitle: 'Perioodi mediaan ning 10. ja 90. protsentiil (pH ühikuta); iga punkt on 5-aastane periood.', unit: '', dec: 2, axisDec: 1, nName: 'proove', series: [mk('Mediaan', SLOTS[0], (r) => r.median), mk('10. protsentiil', SLOTS[2], (r) => r.p10), mk('90. protsentiil', SLOTS[1], (r) => r.p90)], note: 'Proovialad ei ole perioodide vahel samad; pH väärtused väljaspool 2-10 on välja jäetud (andmevead). Paaritatud muutus on kokkuvõttes ja lehe tekstis.' });
      const a = first(pl), b = last(pl), p = so.indicators.pH.paired;
      C.punch(host, `Mulla pH mediaan on ${fmt(a.median, 1)} (${a.period}) ja ${fmt(b.median, 1)} (${b.period}); ${p ? `samadel ${fmt(p.plots, 0)} proovialadel on mediaanmuutus ${sgn(p.median_change, 2)} ja ${fmt(100 * p.share_increased, 0)}% proovialadel pH kasvas` : 'paaritatud võrdlust ei saa teha'}; perioodide erinevus võib tuleneda proovialade koosseisust.`);
    },
    sorg(host) {
      const so = d.soil; if (!so || !so.indicators['Orgaaniline süsinik']) return;
      const I = so.indicators['Orgaaniline süsinik'], pl = I.periods.filter((r) => r.plots >= 20);
      const mk = (label, color, f) => ({ label, color, data: pl.map((r) => ({ year: +r.period.slice(0, 4) + 2, value: f(r), n: r.samples, extra: `${r.period}: ${fmt(r.samples, 0)} proovi, ${fmt(r.plots, 0)} prooviala` })) });
      lines(host, { title: 'Mulla orgaaniline süsinik (mullaseire)', subtitle: '% kuivaines; perioodi mediaan ning 10. ja 90. protsentiil.', unit: '%', dec: 2, axisDec: 1, nName: 'proove', series: [mk('Mediaan', SLOTS[0], (r) => r.median), mk('10. protsentiil', SLOTS[2], (r) => r.p10), mk('90. protsentiil', SLOTS[1], (r) => r.p90)], note: 'Proovialad ei ole perioodide vahel samad; huumus ja orgaaniline süsinik on eri näitajad.' });
      const a = first(pl), b = last(pl), p = I.paired;
      C.punch(host, `Orgaanilise süsiniku mediaan on ${fmt(a.median, 2)}% (${a.period}) ja ${fmt(b.median, 2)}% (${b.period}); ${p ? `samadel ${fmt(p.plots, 0)} proovialadel on mediaanmuutus ${sgn(p.median_change, 2)} protsendipunkti` : 'paaritatud võrdlust ei saa teha'}; erinevus perioodide vahel võib tuleneda proovialade koosseisust.`);
    },
    smetals(host) {
      const so = d.soil; if (!so) return;
      const names = ['Vask', 'Tsink', 'Plii', 'Kaadmium', 'Kroom', 'Nikkel', 'Elavhõbe', 'Arseen'].filter((m) => so.indicators[m]);
      if (!names.length) return;
      C.selectable(host, names.map((n) => ({ value: n, text: n })), names[0], 'Element:', (holder, key) => {
        const I = so.indicators[key], pl = I.periods.filter((r) => r.plots >= 20);
        if (!pl.length) { holder.innerHTML = `<p class="viz-note">${key}: ühelgi perioodil ei ole vähemalt 20 prooviala.</p>`; return; }
        const mk = (label, color, f) => ({ label, color, data: pl.map((r) => ({ year: +r.period.slice(0, 4) + 2, value: f(r), n: r.samples, extra: `${r.period}: ${fmt(r.samples, 0)} proovi, ${fmt(r.plots, 0)} prooviala, alla määramispiiri ${r.below_loq_mark}` })) });
        lines(holder, { title: `${key} mullas (mullaseire)`, subtitle: 'mg/kg kuivaines; perioodi mediaan ja 90. protsentiil.', unit: 'mg/kg', dec: 2, axisDec: 1, nName: 'proove', series: [mk('Mediaan', SLOTS[0], (r) => r.median), mk('90. protsentiil', SLOTS[1], (r) => r.p90)], note: 'Ühikud on teisendatud mg/kg kuivaines (ppm = mg/kg; µg/kg ja ppb ÷ 1000). Piirväärtustega võrdlust ei ole tehtud. Proovialad ei ole perioodide vahel samad.' });
        if (pl.length) { const a = first(pl), b = last(pl), p = I.paired; C.punch(holder, `${key}: mediaan ${fmt(a.median, 2)} mg/kg (${a.period}) ja ${fmt(b.median, 2)} (${b.period}); 90. protsentiil ${fmt(b.p90, 1)}; ${p ? `samadel ${fmt(p.plots, 0)} proovialadel on mediaanmuutus ${sgn(p.median_change, 2)} mg/kg` : 'paaritatud võrdlust ei saa teha'}; piirväärtustega ei ole võrreldud.`); }
      });
    },
    smethods(host) {
      const so = d.soil; if (!so) return;
      host.innerHTML = `<div class="methods"><b>Andmed ja meetod</b> <span class="review-flag">valdkonnaekspert ülevaatamata</span>
        <p><b>Allikas ja päritolu:</b> Keskkonnaagentuuri avaandmed (keskkonnaandmed.envir.ee), keskkonnaseire tabel (KESE), mullaseire programm; mõõdetud või laboris määratud väärtused (mitte hinnangud ega mudelid).</p>
        <p><b>Tõlgendus (kinnitamata):</b> ${so.meta.interpretation.join(' ')}</p>
        <p><b>Piirangud:</b> proovialad ei ole perioodide vahel samad, proovivõtusügavus ja horisont erinevad (andmeväljad on enamasti täitmata); põllumuld ja muud mullaseire alad pole siin eristatud; metaboolsed näitajad, normid ja tõlgendus vajavad pedoloogi kinnitust. Genereeritud ${d.meta.generated_utc.slice(0, 10)} (UTC).</p></div>`;
    },
    wqfindings(host) {
      const w = d.water_quality;
      if (!w) { host.innerHTML = '<p class="viz-note">Veekvaliteedi andmeid ei ole.</p>'; return; }
      const g = w.groundwater_nitrate.years.filter((r) => r.samples >= MINN && r.year <= maxY), gl = last(g), gf = first(g), li = [];
      li.push(`<li><b>Mida see on:</b> keskkonnaseire (KESE) veeproovide kontsentratsioonid: põhjavee nitraat (${fmt(w.groundwater_nitrate.rows_used, 0)} proovi) ning üldlämmastik ja üldfosfor pinna- ja rannikuvees. Ühikud on teisendatud ühtseks (aatommassidega; tundmatu ühikuga read välja jäetud). Statistikud on proovide mediaanid, mitte vooluhulgaga kaalutud koormus; seirekohad ja proovivõtt erinevad aastati.</li>`);
      li.push(`<li><b>Põhjavee nitraat:</b> 90. protsentiil ${fmt(gf.p90, 1)} mg NO₃/l (${gf.year}) → ${fmt(gl.p90, 1)} (${gl.year}); mediaani ei esitata, sest kuni ${fmt(100 * Math.max(...g.map((r) => r.share_below_loq_mark)), 0)}% proovidest on märgitud „<“ (alla määramispiiri). Proovidest ületab EL põhjavee normi (${w.groundwater_nitrate.limit_mg_no3_l} mg NO₃/l) ${fmt(100 * gl.share_over_limit, 1)}% (${gl.year}, ${fmt(gl.samples, 0)} proovi, ${fmt(gl.sites, 0)} seirekohta).</li>`);
      for (const [k, name, unit] of [['tn', 'Üldlämmastik', 'mg N/l'], ['tp', 'Üldfosfor', 'mg P/l']]) {
        const sf = w.surface[k].filter((r) => r.year <= maxY);
        const cats = [...new Set(sf.map((r) => r.category))];
        const bits = cats.map((c) => { const r = sf.filter((x) => x.category === c); return `${c.toLowerCase()} ${fmt(first(r).median, 2)} (${first(r).year}) → ${fmt(last(r).median, 2)} (${last(r).year})`; });
        if (bits.length) li.push(`<li><b>${name}</b> (mediaan, ${unit}): ${bits.join('; ')}.</li>`);
      }
      host.innerHTML = `<ul class="findings">${li.join('')}</ul>`;
    },
    wqnitrate(host) {
      const w = d.water_quality; if (!w) return;
      const g = w.groundwater_nitrate.years.filter((r) => r.samples >= MINN && r.year <= maxY);
      const mk = (label, color, f) => ({ label, color, data: g.map((r) => ({ year: r.year, value: f(r), n: r.samples, extra: `${fmt(r.samples, 0)} proovi, ${fmt(r.sites, 0)} seirekohta` })) });
      lines(host, { title: 'Nitraat põhjavees', subtitle: `90. protsentiil proovide kaupa, mg NO₃/l (aastad vähemalt ${MINN} prooviga); punane joon = EL põhjavee norm.`, unit: 'mg/l', dec: 1, nName: 'proove', series: [mk('90. protsentiil', SLOTS[1], (r) => r.p90)], ref: { value: w.groundwater_nitrate.limit_mg_no3_l, label: `${w.groundwater_nitrate.limit_mg_no3_l} mg/l (norm)` },
        note: 'Nitraatlämmastik on teisendatud nitraadiks (korrutatud 4,427-ga). Osa väärtustest on märgitud „<“ (alla määramispiiri), seega mediaan oleks määramispiiri valiku mõju all; kasutatakse 90. protsentiili. Seirekohtade arv ja koosseis muutub aastati; see ei ole riiklik keskmine.' });
      const gl = last(g), hi = g.filter((r) => r.samples >= 100).reduce((a, r) => (r.share_over_limit > a.share_over_limit ? r : a), g[0]);
      C.punch(host, `Põhjavee nitraadi 90. protsentiil oli ${fmt(gl.p90, 1)} mg/l (${gl.year}); proovidest ületas normi ${fmt(100 * gl.share_over_limit, 1)}% (suurim osakaal ${fmt(100 * hi.share_over_limit, 1)}% aastal ${hi.year}); ${fmt(100 * gl.share_below_loq_mark, 0)}% väärtustest on märgitud „<“ ning seirekohad erinevad aastati (${fmt(gl.sites, 0)} kohta ${gl.year}).`);
    },
    wqnutrients(host) {
      const w = d.water_quality; if (!w) return;
      C.selectable(host, [{ value: 'tn', text: 'Üldlämmastik (mg N/l)' }, { value: 'tp', text: 'Üldfosfor (mg P/l)' }], 'tn', 'Näitaja:', (holder, key) => {
        const rows = w.surface[key].filter((r) => r.year <= maxY), cats = [...new Set(rows.map((r) => r.category))];
        const unit = key === 'tn' ? 'mg N/l' : 'mg P/l', name = key === 'tn' ? 'Üldlämmastik' : 'Üldfosfor';
        const series = cats.map((c, i) => ({ label: c, color: [SLOTS[0], SLOTS[2], SLOTS[1]][i % 3], data: rows.filter((r) => r.category === c).map((r) => ({ year: r.year, value: r.median, n: r.samples, extra: `${fmt(r.samples, 0)} proovi, ${fmt(r.sites, 0)} seirekohta` })) }));
        lines(holder, { title: `${name} pinna- ja rannikuvees`, subtitle: `Proovide mediaan aastas, ${unit}; üle 5 proovi grupis.`, unit, dec: 2, axisDec: 2, nName: 'proove', series, note: 'Proovide mediaan, mitte vooluhulgaga kaalutud; seirekohtade koosseis muutub aastati; ühikud on teisendatud (µmol/l, µg/l ja mg/m³ → mg/l).' });
        const parts = cats.map((c) => { const r = rows.filter((x) => x.category === c); return r.length > 1 ? `${c.toLowerCase()} ${fmt(first(r).median, 2)} → ${fmt(last(r).median, 2)} ${unit} (${first(r).year}–${last(r).year})` : null; }).filter(Boolean);
        C.punch(holder, parts.length ? `${name}: ${parts.join('; ')}; muutus võib kajastada seirekohtade koosseisu, mitte tegelikku seisundit.` : `${name}: aegrida ei ole piisavalt andmeid.`);
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
    wqmethods(host) {
      const w = d.water_quality; if (!w) return;
      host.innerHTML = `<div class="methods"><b>Andmed ja meetod</b> <span class="review-flag">valdkonnaekspert ülevaatamata</span>
        <p><b>Allikas ja päritolu:</b> Keskkonnaagentuuri avaandmed (keskkonnaandmed.envir.ee), keskkonnaseire tabel (KESE); vee kvaliteedi näitajad (nitraat, üldlämmastik, üldfosfor). Tegu on seireandmetega, mitte veekogumi seisundi hinnanguga.</p>
        <p><b>Tõlgendus (kinnitamata):</b> ${w.meta.interpretation.join(' ')}</p>
        <p><b>Piirangud:</b> seirekohtade arv ja koosseis muutub aastati (aastate muutus võib kajastada valimit); osa väärtustest on märgitud „<“ (alla määramispiiri) ja mediaanid sõltuksid määramispiirist; mitte-täieliku käesoleva aasta andmed on välja jäetud; veekogumi seisundi hinnang nõuab ametlikku klassifitseerimismetoodikat, mida siin ei rakendatud. Genereeritud ${d.meta.generated_utc.slice(0, 10)} (UTC).</p></div>`;
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
