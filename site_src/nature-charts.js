/* Nature-conservation charts (extends window.KaurCharts). Data: data/nature.json. Needs airenergy-charts.js. */
(() => {
  'use strict';
  const C = window.KaurCharts;
  const { fmt } = C;
  const { el, frame, responsive, hover } = C.kit;
  const { stackedBars, SLOTS } = C;
  const pct = (a, b) => (b ? (100 * a) / b : 0);
  const CONS = { 1: '#2e9e44', 2: '#8cc152', 3: '#ef8a2b' };
  const CONS_NAMES = { 1: 'Väga hästi säilinud', 2: 'Hästi säilinud', 3: 'Keskmiselt või vähe säilinud' };
  const SP_NAMES = { 1: 'Eeskujulik', 2: 'Hea', 3: 'Keskmine või vähenenud' };

  /* Horizontal bars: rows = [{ name, value, note? }]. */
  function hbars(host, o) {
    const rows = o.rows, max = Math.max(...rows.map((r) => r.value), 1);
    const f = o.fmt || ((v) => fmt(v, 0));
    const frm = frame(host, { title: o.title, subtitle: o.subtitle,
      table: { head: ['Nimetus', o.unit || 'Väärtus'], rows: rows.map((r) => [r.name, f(r.value)]) }, note: o.note });
    responsive(frm, (box, w) => {
      const rowH = 26, labelW = Math.min(300, w * 0.5), m = { t: 6, r: 70 }, h = m.t + rowH * rows.length + 8;
      const svg = el('svg', { width: w, height: h, role: 'img', 'aria-label': o.title }, box);
      rows.forEach((r, i) => {
        const y = m.t + i * rowH, bw = Math.max(1, (w - labelW - m.r) * (r.value / max));
        const cap = Math.max(12, Math.floor((labelW - 10) / 6.4));
        el('text', { x: labelW - 6, y: y + 16, 'text-anchor': 'end', class: 'tick' }, svg, r.name.length > cap ? `${r.name.slice(0, cap - 1)}…` : r.name);
        const rc = el('rect', { x: labelW, y: y + 3, width: bw, height: rowH - 9, rx: 2, fill: o.color || SLOTS[0], tabindex: 0 }, svg);
        hover(rc, () => `<b>${r.name}</b><br>${f(r.value)} ${o.unit || ''}${r.note ? `<br>${r.note}` : ''}`);
        el('text', { x: labelW + bw + 5, y: y + 16, class: 'lbl' }, svg, f(r.value));
      });
    });
  }

  /* 100% stacks of conservation classes; cats = [{ label, counts:{1,2,3}, n }]. */
  function classes(host, o) {
    const used = o.cats.filter((c) => c.n > 0);
    const names = o.names || CONS_NAMES, colors = o.colors || CONS;
    const series = ['1', '2', '3'].map((k) => ({ key: k, label: names[k], color: colors[k], values: new Map(used.map((c) => [c.label, pct(c.counts[k], c.n)])) }));
    stackedBars(host, { years: used.map((c) => c.label), scale: 1, unit: '%', dec: 0, height: o.height || 280, noLabels: true, series,
      coverage: new Map(used.map((c) => [c.label, c.n])), title: o.title, subtitle: o.subtitle, note: o.note });
  }

  function paired(host, o) {
    const p = o.paired, rows = [{ label: o.label, n: p.n, v: p }];
    const series = [['improved', 'Paranes', '#2e9e44'], ['same', 'Sama klass', '#a7b1ab'], ['worsened', 'Halvenes', '#c8312b']].map(([key, label, color]) => ({
      key, label, color, values: new Map(rows.map((r) => [r.label, pct(r.v[key], r.n)])) }));
    stackedBars(host, { years: rows.map((r) => r.label), scale: 1, unit: '%', dec: 0, height: 200, noLabels: true, series, coverage: new Map(rows.map((r) => [r.label, r.n])), title: o.title, subtitle: o.subtitle, note: o.note });
  }

  /* Count per year as bars. */
  function yearly(host, o) {
    const years = o.rows.map((r) => String(r.year));
    stackedBars(host, { years, scale: 1, unit: o.unit, dec: 0, height: 260, noLabels: true,
      series: [{ key: 'v', label: o.label, color: o.color || SLOTS[2], values: new Map(o.rows.map((r) => [String(r.year), r.value])) }], title: o.title, subtitle: o.subtitle, note: o.note });
  }

  Object.assign(window.KaurCharts, { natureBars: hbars, natureClasses: classes, naturePaired: paired, natureYearly: yearly, NATURE: { CONS_NAMES, SP_NAMES, CONS } });
})();
