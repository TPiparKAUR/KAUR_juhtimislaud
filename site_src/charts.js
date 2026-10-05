/* Dependency-free SVG charts for the KAUR climate analysis.
 * Every chart: SVG drawn at container width, hover tooltip, text/table view, light+dark via CSS vars.
 * Data come from data/climate.json (aggregated results only). */
(() => {
  'use strict';
  const NS = 'http://www.w3.org/2000/svg';
  const MINUS = '−';
  const nf = (d) => new Intl.NumberFormat('et-EE', { minimumFractionDigits: d, maximumFractionDigits: d });
  const fmt = (v, d = 1) => {
    if (v === null || v === undefined || Number.isNaN(v)) return '–';
    const r = Number(v.toFixed(d));
    return nf(d).format(Object.is(r, -0) ? 0 : r).replace('-', MINUS);
  };
  const sgn = (v, d = 1) => (v > 0 ? '+' : '') + fmt(v, d);

  const el = (tag, attrs = {}, parent = null, text = null) => {
    const e = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
    if (text !== null) e.textContent = text;
    if (parent) parent.appendChild(e);
    return e;
  };

  function niceTicks(min, max, n = 5) {
    const span = max - min || 1;
    const raw = span / n;
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) || raw;
    const out = [];
    for (let v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) out.push(Math.round(v / step) * step);
    return { ticks: out, step };
  }

  function median(a) {
    const s = a.filter((v) => v !== null && !Number.isNaN(v)).sort((x, y) => x - y);
    if (!s.length) return NaN;
    const m = s.length >> 1;
    return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
  }

  /* ---- tooltip ---- */
  let tip;
  function tooltip() {
    if (!tip) {
      tip = document.createElement('div');
      tip.className = 'viz-tip';
      tip.setAttribute('role', 'status');
      document.body.appendChild(tip);
    }
    return tip;
  }
  function showTip(evt, html) {
    const t = tooltip();
    t.innerHTML = html;
    t.style.display = 'block';
    const pad = 12;
    let x = evt.clientX + pad, y = evt.clientY + pad;
    const r = t.getBoundingClientRect();
    if (x + r.width > window.innerWidth - 4) x = evt.clientX - r.width - pad;
    if (y + r.height > window.innerHeight - 4) y = evt.clientY - r.height - pad;
    t.style.left = `${Math.max(4, x)}px`;
    t.style.top = `${Math.max(4, y)}px`;
  }
  const hideTip = () => { if (tip) tip.style.display = 'none'; };
  function hover(node, htmlFn, { mouse = true } = {}) {
    if (mouse) {
      node.addEventListener('mousemove', (e) => showTip(e, htmlFn()));
      node.addEventListener('mouseleave', hideTip);
    }
    node.addEventListener('focus', () => {
      const r = node.getBoundingClientRect();
      showTip({ clientX: r.left + r.width / 2, clientY: r.top }, htmlFn());
    });
    node.addEventListener('blur', hideTip);
  }

  /* ---- colour helpers (palette tokens are CSS variables) ---- */
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  function mix(a, b, t) {
    const A = hex(a), B = hex(b);
    return `rgb(${A.map((v, i) => Math.round(v + (B[i] - v) * t)).join(',')})`;
  }
  function diverging(v, lim) {
    const t = Math.max(-1, Math.min(1, v / lim));
    const mid = css('--div-mid');
    return t >= 0 ? mix(mid, css('--div-pos'), t) : mix(mid, css('--div-neg'), -t);
  }
  function sequential(v, max) {
    const t = Math.max(0, Math.min(1, v / max));
    return mix(css('--seq-lo'), css('--seq-hi'), t);
  }

  /* ---- scaffolding: figure with title, svg host, legend, table view ---- */
  function frame(host, { title, subtitle, legend, table, note }) {
    host.innerHTML = '';
    host.classList.add('viz');
    if (title) host.appendChild(Object.assign(document.createElement('h3'), { textContent: title, className: 'viz-title' }));
    if (subtitle) host.appendChild(Object.assign(document.createElement('p'), { textContent: subtitle, className: 'viz-sub' }));
    const stage = Object.assign(document.createElement('div'), { className: 'viz-stage' });
    host.appendChild(stage);
    if (legend) {
      const lg = Object.assign(document.createElement('ul'), { className: 'viz-legend' });
      for (const [kind, color, label] of legend) {
        const li = document.createElement('li');
        const sw = Object.assign(document.createElement('span'), { className: `sw sw-${kind}` });
        sw.style.setProperty('--c', color);
        li.append(sw, label);
        lg.appendChild(li);
      }
      host.appendChild(lg);
    }
    if (note) host.appendChild(Object.assign(document.createElement('p'), { className: 'viz-note', textContent: note }));
    if (table) {
      const d = document.createElement('details');
      d.className = 'viz-table';
      d.appendChild(Object.assign(document.createElement('summary'), { textContent: 'Tabelivaade' }));
      const t = document.createElement('table');
      const head = document.createElement('tr');
      for (const h of table.head) head.appendChild(Object.assign(document.createElement('th'), { textContent: h, scope: 'col' }));
      t.appendChild(Object.assign(document.createElement('thead'))).appendChild(head);
      const tb = document.createElement('tbody');
      for (const row of table.rows) {
        const tr = document.createElement('tr');
        row.forEach((c, i) => tr.appendChild(Object.assign(document.createElement(i ? 'td' : 'th'), { textContent: c, scope: i ? '' : 'row' })));
        tb.appendChild(tr);
      }
      t.appendChild(tb);
      d.appendChild(t);
      host.appendChild(d);
    }
    return stage;
  }

  function responsive(stage, draw) {
    let last = 0;
    const run = () => {
      const w = Math.floor(stage.clientWidth);
      if (w < 120 || w === last) return;
      last = w;
      stage.innerHTML = '';
      draw(stage, w);
    };
    new ResizeObserver(run).observe(stage);
    run();
    matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => { last = 0; run(); });
    new MutationObserver(() => { last = 0; run(); }).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  }

  function axisY(g, y, ticks, w, m, unit, dec = 1) {
    for (const t of ticks) {
      el('line', { x1: m.l, x2: w - m.r, y1: y(t), y2: y(t), class: t === 0 ? 'ax-zero' : 'grid' }, g);
      el('text', { x: m.l - 6, y: y(t) + 4, 'text-anchor': 'end', class: 'tick' }, g, fmt(t, dec));
    }
    if (unit) el('text', { x: m.l - 6, y: 10, 'text-anchor': 'end', class: 'unit' }, g, unit);
  }

  /* ---- 1. annual anomaly bars with between-station spread and trend ---- */
  function annualBars(host, block, opt) {
    const { years, mean, p10, p90, n_stations: ns } = block;
    const tr = block.trend;
    const base = opt.baseline || 0;
    const rows = years.map((y, i) => [String(y), fmt(mean[i], opt.dec), `${fmt(p10 && p10[i], opt.dec)} … ${fmt(p90 && p90[i], opt.dec)}`, String(ns[i])]);
    const stage = frame(host, {
      title: opt.title, subtitle: opt.subtitle,
      legend: [['box', 'var(--pos)', opt.posLabel], ['box', 'var(--neg)', opt.negLabel],
        ['whisk', 'var(--ink-2)', 'Jaamade vahe: 10.–90. protsentiil'], ['dash', 'var(--ink)', 'Theil–Sen trend']],
      table: { head: ['Aasta', opt.valueHead, 'Jaamade 10.–90. pct', 'Jaamu'], rows },
      note: opt.note,
    });
    responsive(stage, (box, w) => {
      const m = { l: 46, r: 10, t: 22, b: 26 }, h = opt.height || 300;
      const svg = el('svg', { width: w, height: h, role: 'img', 'aria-label': opt.title }, box);
      const vals = [...mean, ...(p10 || []), ...(p90 || [])].filter((v) => v !== null);
      const lo = Math.min(base, ...vals), hi = Math.max(base, ...vals);
      const pad = (hi - lo) * 0.06;
      const { ticks } = niceTicks(lo - pad, hi + pad, 6);
      const y = (v) => m.t + (h - m.t - m.b) * (1 - (v - (lo - pad)) / (hi - lo + 2 * pad));
      const band = (w - m.l - m.r) / years.length;
      const x = (i) => m.l + band * (i + 0.5);
      axisY(el('g', {}, svg), (t) => y(t), ticks.map((t) => t), w, m, opt.unit, opt.dec);
      const bw = Math.max(2, Math.min(18, band * 0.68));
      years.forEach((yr, i) => {
        if (mean[i] === null) return;
        const above = mean[i] >= base;
        const g = el('g', { tabindex: 0, 'aria-label': `${yr}: ${fmt(mean[i], opt.dec)} ${opt.unit}` }, svg);
        if (p10 && p10[i] !== null) el('line', { x1: x(i), x2: x(i), y1: y(p10[i]), y2: y(p90[i]), class: 'whisk' }, g);
        el('rect', { x: x(i) - bw / 2, width: bw, y: Math.min(y(mean[i]), y(base)), height: Math.max(1, Math.abs(y(mean[i]) - y(base))), rx: 2, class: above ? 'bar-pos' : 'bar-neg' }, g);
        const hit = el('rect', { x: x(i) - band / 2, width: band, y: m.t, height: h - m.t - m.b, fill: 'transparent' }, g);
        hover(hit, () => `<b>${yr}</b><br>${opt.valueHead}: <b>${sgn(mean[i] - (opt.tipOffset || 0), opt.dec)} ${opt.unit}</b><br>Jaamade vahe: ${fmt(p10 && p10[i], opt.dec)} … ${fmt(p90 && p90[i], opt.dec)}<br>${ns[i]} jaama`);
        hover(g, () => `<b>${yr}</b>: ${fmt(mean[i], opt.dec)} ${opt.unit}`, { mouse: false });
      });
      // trend line
      if (tr && tr.slope_per_decade !== null) {
        const s = tr.slope_per_decade / 10;
        const b0 = median(years.map((yr, i) => (mean[i] === null ? NaN : mean[i] - s * yr)));
        const [a, z] = [years[0], years[years.length - 1]];
        el('line', { x1: x(0), x2: x(years.length - 1), y1: y(b0 + s * a), y2: y(b0 + s * z), class: 'trend' }, svg);
      }
      // direct labels for the extremes
      const order = mean.map((v, i) => [v, i]).filter(([v]) => v !== null).sort((p, q) => q[0] - p[0]);
      for (const [v, i] of order.slice(0, opt.labelTop || 3)) el('text', { x: x(i), y: y(Math.max(v, p90 ? p90[i] : v)) - 4, 'text-anchor': 'middle', class: 'lbl' }, svg, String(years[i]));
      const tickEvery = band < 14 ? 5 : 2;
      years.forEach((yr, i) => { if (yr % tickEvery === 0) el('text', { x: x(i), y: h - 8, 'text-anchor': 'middle', class: 'tick' }, svg, String(yr)); });
    });
  }

  /* ---- 2. month x year heat grid ---- */
  function heatGrid(host, grid, opt) {
    const years = grid.years;
    const cell = new Map(grid.cells.map(([a, k, v, n]) => [`${a}-${k}`, [v, n]]));
    const monthNames = ['jaan', 'veebr', 'märts', 'apr', 'mai', 'juuni', 'juuli', 'aug', 'sept', 'okt', 'nov', 'dets'];
    const rows = [];
    for (const yr of years) for (let k = 1; k <= 12; k++) { const c = cell.get(`${yr}-${k}`); if (c) rows.push([String(yr), monthNames[k - 1], fmt(c[0], 1), String(c[1])]); }
    const lim = opt.limit || 5;
    const stage = frame(host, {
      title: opt.title, subtitle: opt.subtitle, table: { head: ['Aasta', 'Kuu', 'Anomaalia °C', 'Jaamu'], rows }, note: opt.note,
    });
    const legend = document.createElement('div');
    legend.className = 'viz-ramp';
    legend.innerHTML = `<span>${MINUS}${lim} °C</span><i></i><span>+${lim} °C</span>`;
    host.insertBefore(legend, stage.nextSibling);
    responsive(stage, (box, w) => {
      const m = { l: 44, r: 8, t: 8, b: 24 };
      const cw = (w - m.l - m.r) / years.length, ch = Math.max(16, Math.min(24, cw * 1.9));
      const h = m.t + ch * 12 + m.b;
      const svg = el('svg', { width: w, height: h, role: 'img', 'aria-label': opt.title }, box);
      monthNames.forEach((mn, k) => el('text', { x: m.l - 6, y: m.t + ch * k + ch / 2 + 4, 'text-anchor': 'end', class: 'tick' }, svg, mn));
      years.forEach((yr, i) => {
        for (let k = 1; k <= 12; k++) {
          const c = cell.get(`${yr}-${k}`);
          const r = el('rect', { x: m.l + cw * i, y: m.t + ch * (k - 1), width: Math.max(1, cw - 0.6), height: ch - 0.6, fill: c ? diverging(c[0], lim) : 'transparent', class: c ? 'cell' : 'cell-empty' }, svg);
          if (c) hover(r, () => `<b>${monthNames[k - 1]} ${yr}</b><br>Anomaalia: <b>${sgn(c[0], 1)} °C</b><br>${c[1]} jaama`);
        }
        if (yr % 5 === 0 || i === 0) el('text', { x: m.l + cw * i + cw / 2, y: h - 8, 'text-anchor': 'middle', class: 'tick' }, svg, String(yr));
      });
    });
  }

  /* ---- 3. forest plot of trends with intervals ---- */
  function forest(host, items, opt) {
    const rows = items.map((it) => [it.label, `${sgn(it.t.slope_per_decade, opt.dec)} [${fmt(it.t.lo, opt.dec)}; ${fmt(it.t.hi, opt.dec)}]`, String(it.t.n)]);
    const stage = frame(host, {
      title: opt.title, subtitle: opt.subtitle,
      legend: [['dot', 'var(--pos)', 'Vahemik ei sisalda nulli'], ['hollow', 'var(--ink-2)', 'Vahemik sisaldab nulli (trend pole eristatav)']],
      table: { head: ['Näitaja', `Trend (${opt.unit}) [95% vahemik]`, 'Aastaid'], rows }, note: opt.note,
    });
    responsive(stage, (box, w) => {
      const m = { l: 92, r: 14, t: 22, b: 32 }, rh = 34, h = m.t + rh * items.length + m.b;
      const svg = el('svg', { width: w, height: h, role: 'img', 'aria-label': opt.title }, box);
      const all = items.flatMap((i) => [i.t.lo, i.t.hi]).filter((v) => v !== null);
      const lo = Math.min(0, ...all), hi = Math.max(0, ...all), pad = (hi - lo) * 0.08;
      const { ticks } = niceTicks(lo - pad, hi + pad, 5);
      const x = (v) => m.l + (w - m.l - m.r) * ((v - (lo - pad)) / (hi - lo + 2 * pad));
      for (const t of ticks) {
        el('line', { x1: x(t), x2: x(t), y1: m.t - 4, y2: h - m.b, class: t === 0 ? 'ax-zero' : 'grid' }, svg);
        el('text', { x: x(t), y: h - m.b + 16, 'text-anchor': 'middle', class: 'tick' }, svg, fmt(t, opt.dec));
      }
      el('text', { x: w - m.r, y: h - 4, 'text-anchor': 'end', class: 'unit' }, svg, opt.unit);
      items.forEach((it, i) => {
        const cy = m.t + rh * i + rh / 2, t = it.t;
        if (t.slope_per_decade === null) return;
        const sig = t.lo > 0 || t.hi < 0;
        const g = el('g', { tabindex: 0 }, svg);
        el('text', { x: m.l - 10, y: cy + 4, 'text-anchor': 'end', class: it.strong ? 'lbl-strong' : 'tick' }, g, it.label);
        el('line', { x1: x(t.lo), x2: x(t.hi), y1: cy, y2: cy, class: 'ci' }, g);
        el('circle', { cx: x(t.slope_per_decade), cy, r: 6, class: sig ? 'dot-pos' : 'dot-hollow' }, g);
        el('text', { x: x(t.slope_per_decade), y: cy - 11, 'text-anchor': 'middle', class: 'lbl' }, g, sgn(t.slope_per_decade, opt.dec));
        const hit = el('rect', { x: m.l, y: cy - rh / 2, width: w - m.l - m.r, height: rh, fill: 'transparent' }, g);
        hover(hit, () => `<b>${it.label}</b><br>Trend: <b>${sgn(t.slope_per_decade, opt.dec)} ${opt.unit}</b><br>95% vahemik: ${fmt(t.lo, opt.dec)} … ${fmt(t.hi, opt.dec)}<br>${t.n} aastat`);
      });
    });
  }

  /* ---- 4. station trends ranked ---- */
  function stationDots(host, stations, national, opt) {
    const rows = stations.map((s) => [s.name, `${sgn(s.slope_per_decade, 2)} [${fmt(s.lo, 2)}; ${fmt(s.hi, 2)}]`, String(s.n)]);
    const stage = frame(host, {
      title: opt.title, subtitle: opt.subtitle,
      legend: [['band', 'var(--ink-2)', 'Riigi keskmise trendi 95% vahemik']],
      table: { head: ['Jaam', 'Trend °C/10 a [95% vahemik]', 'Aastaid'], rows }, note: opt.note,
    });
    responsive(stage, (box, w) => {
      const m = { l: 110, r: 14, t: 14, b: 30 }, rh = 20, h = m.t + rh * stations.length + m.b;
      const svg = el('svg', { width: w, height: h, role: 'img', 'aria-label': opt.title }, box);
      const all = stations.flatMap((s) => [s.lo, s.hi]);
      const lo = Math.min(0, ...all), hi = Math.max(...all), pad = (hi - lo) * 0.05;
      const lo0 = lo < 0 ? lo - pad : 0;
      const { ticks } = niceTicks(lo0, hi + pad, 6);
      const x = (v) => m.l + (w - m.l - m.r) * ((v - lo0) / (hi + pad - lo0));
      el('rect', { x: x(national.lo), width: x(national.hi) - x(national.lo), y: m.t - 4, height: rh * stations.length + 4, class: 'natband' }, svg);
      for (const t of ticks) {
        el('line', { x1: x(t), x2: x(t), y1: m.t - 4, y2: h - m.b, class: t === 0 ? 'ax-zero' : 'grid' }, svg);
        el('text', { x: x(t), y: h - m.b + 16, 'text-anchor': 'middle', class: 'tick' }, svg, fmt(t, 1));
      }
      el('text', { x: w - m.r, y: h - 4, 'text-anchor': 'end', class: 'unit' }, svg, '°C / 10 a');
      stations.forEach((s, i) => {
        const cy = m.t + rh * i + rh / 2;
        const g = el('g', { tabindex: 0 }, svg);
        el('text', { x: m.l - 8, y: cy + 4, 'text-anchor': 'end', class: 'tick' }, g, s.name);
        el('line', { x1: x(s.lo), x2: x(s.hi), y1: cy, y2: cy, class: 'ci' }, g);
        el('circle', { cx: x(s.slope_per_decade), cy, r: 4.5, class: 'dot-pos' }, g);
        const hit = el('rect', { x: m.l, y: cy - rh / 2, width: w - m.l - m.r, height: rh, fill: 'transparent' }, g);
        hover(hit, () => `<b>${s.name}</b><br>Trend: <b>${sgn(s.slope_per_decade, 2)} °C/10 a</b><br>95% vahemik: ${fmt(s.lo, 2)} … ${fmt(s.hi, 2)}<br>${s.n} aastat`);
      });
    });
  }

  /* ---- 5. small-multiple index lines ---- */
  function indexPanel(host, block, opt) {
    const yrs = block.aasta;
    const tr = block.trend;
    const rows = yrs.map((y, i) => [String(y), fmt(block.mean[i], 1), `${fmt(block.q10[i], 1)} … ${fmt(block.q90[i], 1)}`, fmt(100 * block.share_any[i], 0), String(block.n[i])]);
    const stage = frame(host, {
      title: opt.title, subtitle: opt.subtitle,
      table: { head: ['Aasta', `Keskmine (${opt.unit})`, '10.–90. pct', 'Jaamu ≥1 sündmusega, %', 'Jaamu'], rows }, note: opt.note,
    });
    const verdict = tr && tr.slope_per_decade !== null
      ? ((tr.lo > 0 || tr.hi < 0) ? `Trend ${sgn(tr.slope_per_decade, opt.dec ?? 1)} ${opt.unit} kümnendi kohta (95% ${fmt(tr.lo, opt.dec ?? 1)} … ${fmt(tr.hi, opt.dec ?? 1)}): eristub nullist` : `Trend ${sgn(tr.slope_per_decade, opt.dec ?? 1)} ${opt.unit} kümnendi kohta (95% ${fmt(tr.lo, opt.dec ?? 1)} … ${fmt(tr.hi, opt.dec ?? 1)}): ei erine nullist`) : '';
    stage.insertAdjacentHTML('beforebegin', `<p class="viz-verdict">${verdict}</p>`);
    responsive(stage, (box, w) => {
      const m = { l: 40, r: 8, t: 10, b: 24 }, h = opt.height || 190;
      const svg = el('svg', { width: w, height: h, role: 'img', 'aria-label': opt.title }, box);
      const hi = Math.max(...block.q90, ...block.mean, 1), lo = Math.min(0, ...block.q10);
      const { ticks } = niceTicks(lo, hi * 1.05, 4);
      const y = (v) => m.t + (h - m.t - m.b) * (1 - (v - lo) / (hi * 1.05 - lo));
      const x = (yr) => m.l + (w - m.l - m.r) * ((yr - yrs[0]) / (yrs[yrs.length - 1] - yrs[0]));
      axisY(el('g', {}, svg), y, ticks, w, m, '', 0);
      const area = block.q90.map((v, i) => `${i ? 'L' : 'M'}${x(yrs[i])},${y(v)}`).join('') + block.q10.map((v, i) => `L${x(yrs[block.q10.length - 1 - i])},${y(block.q10[block.q10.length - 1 - i])}`).join('') + 'Z';
      el('path', { d: area, class: 'ribbon' }, svg);
      el('path', { d: block.mean.map((v, i) => `${i ? 'L' : 'M'}${x(yrs[i])},${y(v)}`).join(''), class: 'line' }, svg);
      yrs.forEach((yr, i) => {
        const c = el('circle', { cx: x(yr), cy: y(block.mean[i]), r: 3, class: 'pt', tabindex: 0 }, svg);
        const hit = el('rect', { x: x(yr) - 6, width: 12, y: m.t, height: h - m.t - m.b, fill: 'transparent' }, svg);
        const tipf = () => `<b>${yr}</b><br>Keskmine: <b>${fmt(block.mean[i], 1)} ${opt.unit}</b><br>Jaamade vahe: ${fmt(block.q10[i], 1)} … ${fmt(block.q90[i], 1)}<br>${fmt(100 * block.share_any[i], 0)}% jaamadest ≥1 sündmus`;
        hover(hit, tipf); hover(c, tipf, { mouse: false });
      });
      [yrs[0], 2000, 2010, 2020, yrs[yrs.length - 1]].filter((v, i, a) => a.indexOf(v) === i).forEach((yr) => el('text', { x: x(yr), y: h - 6, 'text-anchor': 'middle', class: 'tick' }, svg, String(yr)));
    });
  }

  /* ---- 6. coverage matrix ---- */
  function coverage(host, comp, stations, opt) {
    const names = Object.fromEntries(stations.map((s) => [s.code, s.name]));
    const by = new Map();
    for (const [st, yr, mo] of comp.cells) { if (!by.has(st)) by.set(st, new Map()); by.get(st).set(yr, mo); }
    const order = [...by.keys()].sort((a, b) => Math.min(...by.get(a).keys()) - Math.min(...by.get(b).keys()) || names[a].localeCompare(names[b], 'et'));
    const years = comp.years;
    const rows = order.map((st) => [names[st], String(Math.min(...by.get(st).keys())), String([...by.get(st).values()].filter((v) => v === 12).length)]);
    const stage = frame(host, { title: opt.title, subtitle: opt.subtitle, table: { head: ['Jaam', 'Esimene aasta', 'Täis-aastaid (12 kuud)'], rows }, note: opt.note });
    const legend = document.createElement('div');
    legend.className = 'viz-ramp';
    legend.innerHTML = '<span>1 kuu</span><i class="seq"></i><span>12 kuud</span>';
    host.insertBefore(legend, stage.nextSibling);
    responsive(stage, (box, w) => {
      const m = { l: 110, r: 8, t: 6, b: 24 }, rh = 15, h = m.t + rh * order.length + m.b;
      const cw = (w - m.l - m.r) / years.length;
      const svg = el('svg', { width: w, height: h, role: 'img', 'aria-label': opt.title }, box);
      order.forEach((st, r) => {
        el('text', { x: m.l - 6, y: m.t + rh * r + rh - 4, 'text-anchor': 'end', class: 'tick' }, svg, names[st]);
        years.forEach((yr, i) => {
          const mo = by.get(st).get(yr);
          if (mo === undefined) { el('rect', { x: m.l + cw * i, y: m.t + rh * r, width: Math.max(1, cw - 0.6), height: rh - 1, class: 'cell-empty' }, svg); return; }
          const rect = el('rect', { x: m.l + cw * i, y: m.t + rh * r, width: Math.max(1, cw - 0.6), height: rh - 1, fill: mo === 12 ? sequential(12, 12) : sequential(2 + 7 * (mo / 12), 12), class: 'cell' }, svg);
          hover(rect, () => `<b>${names[st]} ${yr}</b><br>${mo} kuud andmetega${mo < 12 ? ' – <b>puudulik aasta</b>' : ''}`);
        });
      });
      years.forEach((yr, i) => { if (yr % 5 === 0 || i === 0) el('text', { x: m.l + cw * i + cw / 2, y: h - 8, 'text-anchor': 'middle', class: 'tick' }, svg, String(yr)); });
    });
  }

  window.KaurCharts = { annualBars, heatGrid, forest, stationDots, indexPanel, coverage, fmt, sgn };
})();
