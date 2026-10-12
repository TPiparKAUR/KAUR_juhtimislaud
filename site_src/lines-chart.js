/* Shared line chart: several series on a common axis. Loaded before the page scripts. */
(() => {
  'use strict';
  const C = window.KaurCharts, { fmt } = C;
  const { el, frame, responsive, niceTicks, hover, axisY } = C.kit;

  /* Lines of several series on a common percent axis; series: [{label,color,data:[{year,value,n}]}] */
  function lines(host, o) {
    const series = o.series.filter((s) => s.data.length);
    const years = [...new Set(series.flatMap((s) => s.data.map((r) => r.year)))].sort((a, b) => a - b);
    const frm = frame(host, { title: o.title, subtitle: o.subtitle, legend: series.map((s) => ['dot', s.color, s.label]),
      table: { head: ['Aasta', ...series.flatMap((s) => [`${s.label} (${o.unit ?? '%'})`, `${s.label}: ${o.nName || 'puid'}`])], rows: years.map((y) => [String(y), ...series.flatMap((s) => { const r = s.data.find((x) => x.year === y); return r ? [fmt(r.value, o.dec ?? 1), fmt(r.n, 0)] : ['–', '–']; })]) }, note: o.note });
    responsive(frm, (box, w) => {
      const m = { l: 52, r: 14, t: 16, b: 28 }, h = o.height || 300;
      const svg = el('svg', { width: w, height: h, role: 'img', 'aria-label': o.title }, box);
      const top = Math.max(...series.flatMap((s) => s.data.map((r) => r.value)), o.ref ? o.ref.value : 0, 1e-9) * 1.1;
      const { ticks } = niceTicks(0, top, 5);
      const x = (yr) => m.l + (w - m.l - m.r) * ((yr - years[0]) / (years[years.length - 1] - years[0] || 1));
      const y = (v) => m.t + (h - m.t - m.b) * (1 - (v - ticks[0]) / (ticks[ticks.length - 1] - ticks[0] || 1));
      axisY(el('g', {}, svg), y, ticks, w, m, o.unit ?? '%', o.axisDec ?? 0);
      if (o.ref) { el('line', { x1: m.l, x2: w - m.r, y1: y(o.ref.value), y2: y(o.ref.value), stroke: '#c8312b', 'stroke-dasharray': '5 4', 'stroke-width': 1.5 }, svg); el('text', { x: w - m.r - 4, y: y(o.ref.value) - 5, 'text-anchor': 'end', class: 'tick' }, svg, o.ref.label); }
      for (const yr of years.filter((v, i) => i % Math.ceil(years.length / 8) === 0 || i === years.length - 1)) el('text', { x: x(yr), y: h - 8, 'text-anchor': 'middle', class: 'tick' }, svg, String(yr));
      for (const s of series) {
        el('path', { d: s.data.map((r, i) => `${i ? 'L' : 'M'}${x(r.year)},${y(r.value)}`).join(''), fill: 'none', stroke: s.color, 'stroke-width': 2.4 }, svg);
        for (const r of s.data) { const c = el('circle', { cx: x(r.year), cy: y(r.value), r: 3, fill: s.color, tabindex: 0 }, svg); hover(c, () => `<b>${r.year}</b><br>${s.label}: <b>${fmt(r.value, o.dec ?? 1)} ${o.unit ?? '%'}</b><br>${r.extra || `${fmt(r.n, 0)} puud, ${r.plots} prooviala`}`); }
      }
    });
  }

  C.lines = lines;
})();
