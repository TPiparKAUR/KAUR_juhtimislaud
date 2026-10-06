/* Water-body status charts (extends window.KaurCharts). Data: data/water.json. Needs airenergy-charts.js. */
(() => {
  'use strict';
  const C = window.KaurCharts;
  const { fmt } = C;
  const { el, frame, responsive, hover } = C.kit;
  const { stackedBars, SLOTS } = C;
  // Water Framework Directive class colours: very good ... very bad.
  const CLS = { 1: '#2166ac', 2: '#2e9e44', 3: '#e3c32b', 4: '#ef8a2b', 5: '#c8312b' };
  const pct = (a, b) => (b ? (100 * a) / b : 0);

  /* Class shares per assessment year (100% stacks); n under each bar. */
  function status(host, d) {
    const rows = d.by_year;
    const years = rows.map((r) => String(r.year));
    const series = ['1', '2', '3', '4', '5'].map((c) => ({
      key: c, label: `${c}. ${d.meta.class_names[c]}`, color: CLS[c],
      values: new Map(rows.map((r) => [String(r.year), pct(r.counts[c], r.classified)])),
    }));
    stackedBars(host, { years, scale: 1, unit: '%', dec: 0, height: 330, noLabels: true, series,
      coverage: new Map(rows.map((r) => [String(r.year), r.n])),
      title: 'Veekogumite seisundiklassid hindamisaasta järgi', subtitle: 'Osakaal klassifitseeritud veekogumitest, %; aluse all hinnatud veekogumite arv (n).',
      note: 'Aastatel 2010 ja 2012–2015 hinnati iga aasta ligikaudu 730 veekogumit, pärast 2015. aastat vaid osa (n≈130–200 aastas) ja aastate 2007–2009 ning 2011 hinnangud on veel vähem. Seetõttu ei ole hilisemad aastad riikliku aegreana võrreldavad.' });
  }

  /* Paired comparison: same water bodies, baseline year vs latest later assessment. */
  function paired(host, d) {
    const p = d.paired;
    const keys = ['Vooluveekogu', 'Järv', 'Meri', 'Kokku'];
    const get = (k) => (k === 'Kokku' ? p.all : p.by_group[k]);
    const used = keys.filter((k) => get(k).n > 0);
    const series = [['improved', 'Paranes', '#2e9e44'], ['same', 'Sama klass', '#a7b1ab'], ['worsened', 'Halvenes', '#c8312b']].map(([key, label, color]) => ({
      key, label, color, values: new Map(used.map((k) => [k, pct(get(k)[key], get(k).n)])),
    }));
    stackedBars(host, { years: used, scale: 1, unit: '%', dec: 0, height: 260, noLabels: true, series,
      coverage: new Map(used.map((k) => [k, get(k).n])),
      title: `Samade veekogumite klassi muutus: ${p.baseline_year} → viimane hilisem hinnang`, subtitle: `Osakaal veekogumitest, mis klassifitseeriti nii ${p.baseline_year}. aastal kui hiljem (${p.later_years ? `${p.later_years.min}–${p.later_years.max}` : ''}); n = veekogumite arv.`,
      note: 'Hilisemalt hinnatud veekogumid ei ole juhuvalim (seirevalik), ja hindamismeetod või piirväärtused võivad olla muutunud; muutuse põhjus (tegelik seisund või meetod) on andmetest nähtamatu.' });
  }

  /* Horizontal bars: share of assessed water bodies with a significant pressure. */
  function bars(host, o) {
    const rows = o.rows;
    const frm = frame(host, { title: o.title, subtitle: o.subtitle,
      table: { head: ['Nimetus', 'Veekogumeid', 'Osakaal, %'], rows: rows.map((r) => [r.name, fmt(r.bodies, 0), fmt(pct(r.bodies, o.total), 0)]) }, note: o.note });
    responsive(frm, (box, w) => {
      const rowH = 26, labelW = Math.min(300, w * 0.5), m = { t: 6, r: 56 }, h = m.t + rowH * rows.length + 8;
      const svg = el('svg', { width: w, height: h, role: 'img', 'aria-label': o.title }, box);
      rows.forEach((r, i) => {
        const y = m.t + i * rowH, bw = Math.max(1, (w - labelW - m.r) * (r.bodies / o.total));
        const cap = Math.max(12, Math.floor((labelW - 10) / 6.4));
        el('text', { x: labelW - 6, y: y + 16, 'text-anchor': 'end', class: 'tick' }, svg, r.name.length > cap ? `${r.name.slice(0, cap - 1)}…` : r.name);
        const rc = el('rect', { x: labelW, y: y + 3, width: bw, height: rowH - 9, rx: 2, fill: o.color || SLOTS[0], tabindex: 0 }, svg);
        hover(rc, () => `<b>${r.name}</b><br>${fmt(r.bodies, 0)} veekogumit (${fmt(pct(r.bodies, o.total), 0)}%)<br>${fmt(r.pressures, 0)} survetegurit`);
        el('text', { x: labelW + bw + 5, y: y + 16, class: 'lbl' }, svg, `${fmt(pct(r.bodies, o.total), 0)}%`);
      });
    });
  }

  function groundwater(host, d) {
    const ys = Object.keys(d.groundwater.years);
    const names = { 1: 'Hea', 2: 'Ohustatud', 3: 'Halb' }, colors = { 1: CLS[2], 2: CLS[4], 3: CLS[5] };
    const series = ['1', '2', '3'].map((k) => ({ key: k, label: names[k], color: colors[k], values: new Map(ys.map((y) => [y, pct(d.groundwater.years[y].counts[k], d.groundwater.years[y].n)])) }));
    stackedBars(host, { years: ys, scale: 1, unit: '%', dec: 0, height: 240, noLabels: true, series,
      coverage: new Map(ys.map((y) => [y, d.groundwater.years[y].n])),
      title: 'Põhjaveekogumite seisund', subtitle: 'Koondseisund hindamisaasta järgi, % põhjaveekogumitest; n = põhjaveekogumite arv.',
      note: 'Kahe aasta põhjaveekogumite hulgad ei kattu (kogumite id-d ei ühti), seega muutust ei arvutata; hinnang kirjeldab iga aasta kogumeid eraldi.' });
  }

  Object.assign(window.KaurCharts, { waterStatus: status, waterPaired: paired, waterBars: bars, waterGroundwater: groundwater });
})();
