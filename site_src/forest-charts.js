/* Forest inventory (SMI) charts with relative-error intervals (extends window.KaurCharts). */
(() => {
  'use strict';
  const C = window.KaurCharts;
  const { fmt } = C;
  const { el, frame, responsive, niceTicks, hover, axisY } = C.kit;
  const COLORS = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#4a3aa7', '#008300', '#e34948'];
  const pct = (e) => (e == null ? '–' : `±${fmt(100 * e, 1)}%`);
  const lo = (r) => r.value * (1 - (r.err ?? 0));
  const hi = (r) => r.value * (1 + (r.err ?? 0));

  /* Time series with an error band. series: [{label, color, data:[{year,value,err}]}] */
  function errLines(host, o) {
    const years = [...new Set(o.series.flatMap((s) => s.data.map((r) => r.year)))].sort((a, b) => a - b);
    const rows = years.map((y) => [String(y), ...o.series.flatMap((s) => { const r = s.data.find((x) => x.year === y); return r ? [fmt(r.value, o.dec), pct(r.err)] : ['–', '–']; })]);
    const stage = frame(host, {
      title: o.title, subtitle: o.subtitle,
      legend: [...o.series.map((s) => ['dot', s.color, s.label]), ['band', '#8c8b86', 'suhteline viga (±, 95%, eeldatud)']],
      table: { head: ['Aasta', ...o.series.flatMap((s) => [`${s.label} (${o.unit})`, `${s.label}: viga`])], rows }, note: o.note,
    });
    responsive(stage, (box, w) => {
      const m = { l: 62, r: 14, t: 18, b: 28 }, h = o.height || 300;
      const svg = el('svg', { width: w, height: h, role: 'img', 'aria-label': o.title }, box);
      const all = o.series.flatMap((s) => s.data);
      const y0 = o.zero ? 0 : Math.min(...all.map(lo)) * 0.98, y1 = Math.max(...all.map(hi)) * 1.04;
      const { ticks } = niceTicks(y0, y1, 5);
      const x = (yr) => m.l + (w - m.l - m.r) * ((yr - years[0]) / (years[years.length - 1] - years[0] || 1));
      const y = (v) => m.t + (h - m.t - m.b) * (1 - (v - ticks[0]) / (ticks[ticks.length - 1] - ticks[0] || 1));
      axisY(el('g', {}, svg), y, ticks, w, m, o.unit, o.dec);
      for (const yr of years.filter((v, i) => i % Math.ceil(years.length / 8) === 0 || i === years.length - 1)) el('text', { x: x(yr), y: h - 8, 'text-anchor': 'middle', class: 'tick' }, svg, String(yr));
      o.series.forEach((s) => {
        const d = s.data;
        const band = `${d.map((r, i) => `${i ? 'L' : 'M'}${x(r.year)},${y(hi(r))}`).join('')}${[...d].reverse().map((r) => `L${x(r.year)},${y(lo(r))}`).join('')}Z`;
        el('path', { d: band, fill: s.color, opacity: 0.2 }, svg);
        el('path', { d: d.map((r, i) => `${i ? 'L' : 'M'}${x(r.year)},${y(r.value)}`).join(''), fill: 'none', stroke: s.color, 'stroke-width': 2.4 }, svg);
        d.forEach((r) => { const c = el('circle', { cx: x(r.year), cy: y(r.value), r: 3.2, fill: s.color, tabindex: 0 }, svg); hover(c, () => `<b>${r.year}</b><br>${s.label}: <b>${fmt(r.value, o.dec)} ${o.unit}</b> (${pct(r.err)})<br>${fmt(lo(r), o.dec)} … ${fmt(hi(r), o.dec)}`); });
      });
    });
  }

  /* Grouped bars for categories at two (or more) times, with error whiskers.
     o.cats: [{label, points:[{name,color,value,err}]}] */
  function errBars(host, o) {
    const names = o.cats[0]?.points.map((p) => ({ name: p.name, color: p.color })) ?? [];
    const rows = o.cats.map((c) => [c.label, ...c.points.flatMap((p) => [fmt(p.value, o.dec), pct(p.err)])]);
    const stage = frame(host, {
      title: o.title, subtitle: o.subtitle,
      legend: [...names.map((n) => ['box', n.color, n.name]), ['whisk', '#51605a', 'viga (±, 95%, eeldatud)']],
      table: { head: ['', ...names.flatMap((n) => [`${n.name} (${o.unit})`, `${n.name}: viga`])], rows }, note: o.note,
    });
    responsive(stage, (box, w) => {
      const m = { l: 58, r: 12, t: 16, b: o.rotate ? 64 : 34 }, h = o.height || 300;
      const svg = el('svg', { width: w, height: h, role: 'img', 'aria-label': o.title }, box);
      const y1 = Math.max(...o.cats.flatMap((c) => c.points.map(hi))) * 1.06;
      const { ticks } = niceTicks(0, y1, 5);
      const y = (v) => m.t + (h - m.t - m.b) * (1 - v / (ticks[ticks.length - 1] || 1));
      axisY(el('g', {}, svg), y, ticks, w, m, o.unit, o.dec);
      const band = (w - m.l - m.r) / o.cats.length, k = names.length, bw = Math.max(4, Math.min(28, (band * 0.8) / k));
      o.cats.forEach((c, i) => {
        const cx = m.l + band * (i + 0.5);
        c.points.forEach((p, j) => {
          const x = cx - (bw * k) / 2 + bw * j;
          const r = el('rect', { x, y: y(p.value), width: bw - 1, height: Math.max(0, y(0) - y(p.value)), fill: p.color, rx: 2, tabindex: 0 }, svg);
          hover(r, () => `<b>${c.label}</b><br>${p.name}: <b>${fmt(p.value, o.dec)} ${o.unit}</b> (${pct(p.err)})<br>${fmt(lo(p), o.dec)} … ${fmt(hi(p), o.dec)}`);
          if (p.err != null) { const xm = x + (bw - 1) / 2; el('line', { x1: xm, x2: xm, y1: y(lo(p)), y2: y(hi(p)), stroke: 'var(--ink-2)', 'stroke-width': 1.4 }, svg); }
        });
        const t = el('text', { x: cx, y: h - (o.rotate ? 48 : 12), 'text-anchor': o.rotate ? 'end' : 'middle', class: 'tick' }, svg, c.label);
        if (o.rotate) t.setAttribute('transform', `rotate(-40 ${cx} ${h - 48})`);
      });
    });
  }

  Object.assign(window.KaurCharts, { errLines, errBars, FOREST_COLORS: COLORS });
})();
