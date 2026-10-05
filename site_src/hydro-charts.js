/* Hydrology charts (extends window.KaurCharts). Data: data/hydro.json. */
(() => {
  'use strict';
  const C = window.KaurCharts;
  const { fmt, sgn } = C;
  const { el, frame, responsive, niceTicks, hover, axisY, diverging, sequential } = C.kit;
  const MONTHS = ['jaan', 'veebr', 'märts', 'apr', 'mai', 'juuni', 'juuli', 'aug', 'sept', 'okt', 'nov', 'dets'];

  /* A <select> above a chart; re-renders the chart into a holder on change. */
  function selectable(host, items, initial, label, render) {
    host.innerHTML = '';
    const bar = Object.assign(document.createElement('label'), { className: 'viz-select' });
    bar.append(`${label} `);
    const sel = document.createElement('select');
    for (const it of items) sel.appendChild(Object.assign(document.createElement('option'), { value: it.value, textContent: it.text, selected: it.value === initial }));
    bar.appendChild(sel);
    const holder = document.createElement('div');
    host.append(bar, holder);
    const go = () => render(holder, sel.value);
    sel.addEventListener('change', go);
    go();
  }

  /* ---- seasonal regime band with current year ---- */
  function regimeBands(host, r, name, opt) {
    const rows = r.months.map((m, i) => [MONTHS[m - 1], fmt(r.q10[i], 2), fmt(r.median[i], 2), fmt(r.q90[i], 2), String(r.n_years[i]), fmt(r.current[r.current_months.indexOf(m)] ?? null, 2)]);
    const cur = new Map(r.current_months.map((m, i) => [m, r.current[i]]));
    const outside = r.months.filter((m, i) => cur.has(m) && (cur.get(m) > r.q90[i] || cur.get(m) < r.q10[i]))
      .map((m) => `${MONTHS[m - 1]} (${cur.get(m) > r.q90[r.months.indexOf(m)] ? 'üle' : 'alla'} tavavahemiku)`);
    const stage = frame(host, {
      title: `${name}: kuu keskmine vooluhulk`, subtitle: opt.subtitle,
      legend: [['band', 'var(--neg)', `10.–90. protsentiil, ${opt.refFrom}–${r.current_year - 1}`], ['dash', 'var(--neg)', 'Mediaan'], ['dot', 'var(--pos)', `${r.current_year}`]],
      table: { head: ['Kuu', 'P10', 'Mediaan', 'P90', 'Aastaid', `${r.current_year}`], rows },
      note: opt.note,
    });
    stage.insertAdjacentHTML('beforebegin', `<p class="viz-verdict">${r.current_year}: ${outside.length ? outside.join(', ') : 'kõik täis kuud jäävad tavavahemikku'}.</p>`);
    responsive(stage, (box, w) => {
      const m = { l: 48, r: 12, t: 20, b: 26 }, h = 300;
      const svg = el('svg', { width: w, height: h, role: 'img', 'aria-label': `${name} vooluhulga režiim` }, box);
      const hi = Math.max(...r.q90, ...r.current) * 1.05;
      const { ticks } = niceTicks(0, hi, 5);
      const y = (v) => m.t + (h - m.t - m.b) * (1 - v / hi);
      const x = (mo) => m.l + (w - m.l - m.r) * ((mo - 1) / 11);
      axisY(el('g', {}, svg), y, ticks, w, m, opt.unit, 1);
      const top = r.months.map((mo, i) => `${i ? 'L' : 'M'}${x(mo)},${y(r.q90[i])}`).join('');
      const bot = r.months.map((mo, i) => `L${x(r.months[r.months.length - 1 - i])},${y(r.q10[r.months.length - 1 - i])}`).join('');
      el('path', { d: `${top}${bot}Z`, class: 'ribbon' }, svg);
      el('path', { d: r.months.map((mo, i) => `${i ? 'L' : 'M'}${x(mo)},${y(r.median[i])}`).join(''), class: 'line' }, svg);
      el('path', { d: r.current_months.map((mo, i) => `${i ? 'L' : 'M'}${x(mo)},${y(r.current[i])}`).join(''), class: 'line-cur' }, svg);
      r.current_months.forEach((mo, i) => {
        const k = r.months.indexOf(mo);
        const c = el('circle', { cx: x(mo), cy: y(r.current[i]), r: 4.5, class: 'dot-pos', tabindex: 0 }, svg);
        const tipf = () => `<b>${MONTHS[mo - 1]} ${r.current_year}</b><br>Vooluhulk: <b>${fmt(r.current[i], 2)} ${opt.unit}</b><br>Tavavahemik: ${fmt(r.q10[k], 2)} … ${fmt(r.q90[k], 2)}<br>Mediaan: ${fmt(r.median[k], 2)}`;
        hover(c, tipf);
      });
      r.months.forEach((mo, i) => {
        const hit = el('rect', { x: x(mo) - 14, width: 28, y: m.t, height: h - m.t - m.b, fill: 'transparent' }, svg);
        hover(hit, () => `<b>${MONTHS[mo - 1]}</b><br>Mediaan: ${fmt(r.median[i], 2)} ${opt.unit}<br>10.–90.: ${fmt(r.q10[i], 2)} … ${fmt(r.q90[i], 2)}<br>${r.n_years[i]} aastat`);
        el('text', { x: x(mo), y: h - 8, 'text-anchor': 'middle', class: 'tick' }, svg, MONTHS[mo - 1]);
      });
    });
  }

  /* ---- generic matrix heat (rows x columns) ---- */
  function matrix(host, o) {
    const stage = frame(host, { title: o.title, subtitle: o.subtitle, table: { head: [o.rowHead, ...o.cols.map(String)], rows: o.rows.map((r) => [r.label, ...o.cols.map((c) => o.fmtCell(r.cells.get(c)))]) }, note: o.note });
    if (o.ramp) { const legend = document.createElement('div'); legend.className = 'viz-ramp'; legend.innerHTML = o.ramp; host.insertBefore(legend, stage.nextSibling); }
    responsive(stage, (box, w) => {
      const m = { l: o.labelW || 150, r: 8, t: 6, b: 24 }, rh = o.rowH || 20, h = m.t + rh * o.rows.length + m.b;
      const cw = (w - m.l - m.r) / o.cols.length;
      const svg = el('svg', { width: w, height: h, role: 'img', 'aria-label': o.title }, box);
      o.rows.forEach((r, ri) => {
        el('text', { x: m.l - 6, y: m.t + rh * ri + rh - 6, 'text-anchor': 'end', class: 'tick' }, svg, r.label);
        o.cols.forEach((c, ci) => {
          const v = r.cells.get(c);
          const rect = el('rect', { x: m.l + cw * ci, y: m.t + rh * ri, width: Math.max(1, cw - 0.8), height: rh - 1, fill: v === undefined || v === null ? 'transparent' : o.color(v), class: v === undefined || v === null ? 'cell-empty' : 'cell' }, svg);
          if (v !== undefined && v !== null) hover(rect, () => `<b>${r.label}, ${o.colLabel(c)}</b><br>${o.tip(v)}`);
        });
      });
      o.cols.forEach((c, ci) => { if (o.showCol(c, ci)) el('text', { x: m.l + cw * ci + cw / 2, y: h - 8, 'text-anchor': 'middle', class: 'tick' }, svg, o.colLabel(c)); });
    });
  }

  function specificHeat(host, d, opt) {
    const rows = d.stations.filter((s) => d.regime[s.code] && s.area_km2).sort((a, b) => b.area_km2 - a.area_km2).map((s) => {
      const r = d.regime[s.code];
      return { label: `${s.name} (${s.river ?? '–'})`, cells: new Map(r.months.map((m, i) => [m, r.median[i] * 1000 / s.area_km2])) };
    });
    const max = Math.max(...rows.flatMap((r) => [...r.cells.values()])) * 0.9;
    matrix(host, { title: 'Erivool kuude kaupa: kus ja millal jõed vett annavad?', subtitle: 'Kuu mediaanvooluhulk valgala pindala kohta (l/s/km²), suurimast valgalast väikseima poole.', rowHead: 'Jaam', cols: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], rows,
      color: (v) => sequential(v, max), colLabel: (c) => MONTHS[c - 1], showCol: () => true, fmtCell: (v) => fmt(v, 1), tip: (v) => `Erivool: <b>${fmt(v, 1)} l/s/km²</b>`,
      ramp: `<span>0</span><i class="seq"></i><span>${fmt(max, 0)}+ l/s/km²</span>`, labelW: 190, note: opt.note });
  }

  function tempHeat(host, d) {
    const rows = d.stations.filter((s) => d.water_temperature[s.code]).map((s) => {
      const t = d.water_temperature[s.code];
      const vals = t.years.map((y, i) => [y, t.summer_mean[i]]).filter(([, v]) => v !== null);
      const mean = vals.reduce((a, [, v]) => a + v, 0) / (vals.length || 1);
      return { label: `${s.name} (${s.river ?? '–'})`, cells: new Map(vals.map(([y, v]) => [y, v - mean])), mean };
    }).filter((r) => r.cells.size >= 5);
    const years = [...new Set(rows.flatMap((r) => [...r.cells.keys()]))].sort();
    matrix(host, { title: 'Suvine veetemperatuur: millised suved olid soojad?', subtitle: 'Juuni–augusti ööpäevakeskmiste keskmine võrreldes jaama enda keskmisega (°C).', rowHead: 'Jaam', cols: years, rows,
      color: (v) => diverging(v, 3), colLabel: String, showCol: (c) => c % 2 === 1 || true, fmtCell: (v) => (v === undefined ? '–' : sgn(v, 1)), tip: (v) => `Kõrvalekalle: <b>${sgn(v, 1)} °C</b>`,
      ramp: `<span>${C.kit.MINUS}3 °C</span><i></i><span>+3 °C</span>`, labelW: 190, note: 'Ühik °C on eeldatud (tabeli skeemis puudub). Anduri asukoht ja jõe reguleerimine mõjutavad temperatuuri; võrdlus on jaama enda sees.' });
  }

  function coverageMatrix(host, d) {
    const names = Object.fromEntries(d.stations.map((s) => [s.code, `${s.name}`]));
    const by = new Map();
    for (const [c, y, share] of d.coverage.cells) { if (!by.has(c)) by.set(c, new Map()); by.get(c).set(y, share); }
    const years = [...new Set(d.coverage.cells.map((c) => c[1]))].sort();
    const rows = [...by.keys()].map((c) => ({ label: names[c] ?? String(c), cells: by.get(c) }));
    matrix(host, { title: 'Andmete katvus: kui suure osa aastast on kehtiv ööpäevakeskmine vooluhulk?', subtitle: 'Kehtiv päev = vähemalt 20 tunniväärtust.', rowHead: 'Jaam', cols: years, rows,
      color: (v) => sequential(2 + 7 * v, 9), colLabel: String, showCol: () => true, fmtCell: (v) => (v === undefined ? '–' : `${fmt(100 * v, 0)}%`), tip: (v) => `${fmt(100 * v, 0)}% päevi kehtivad`,
      ramp: '<span>0%</span><i class="seq"></i><span>100%</span>', labelW: 150, rowH: 17, note: `Puuduva või puudulikuga aastaid ei kasutata aasta keskmiste ja ekstreemide arvutamisel (alla 350 kehtiva päeva). ${d.meta.current_year} on pooleli, seega jääb selle aasta osakaal paratamatult alla 100%.` });
  }

  /* ---- flow-duration curves, one station highlighted, others as context ---- */
  function flowDuration(host, d) {
    const stations = d.stations.filter((s) => d.flow_duration[s.code]);
    const label = (s) => `${s.name} (${s.river ?? '–'})`;
    const initial = String((stations.find((s) => s.name === 'Tartu') ?? stations[0]).code);
    selectable(host, stations.map((s) => ({ value: String(s.code), text: label(s) })), initial, 'Rõhuta jaam:', (holder, code) => {
      const sel = stations.find((s) => String(s.code) === code);
      const rows = d.flow_duration[sel.code].p.map((p, i) => [`${p}%`, fmt(d.flow_duration[sel.code].specific_ls_km2[i], 2)]);
      const stage = frame(holder, { title: 'Vooluhulga kestvuskõver (erivool)', subtitle: 'Mitu protsenti ajast on erivool vähemalt nii suur; log-telg. Hall: teised jaamad, sinine: valitud jaam.', table: { head: ['Ületamise tõenäosus', 'Erivool l/s/km²'], rows }, note: 'Kõik kehtivad päevad. Vool on jagatud valgala pindalaga, seega jaamu saab omavahel võrrelda; kõvera järsus näitab vooluhulga ebaühtlust (P5 = suurvesi, P95 = madalvesi). Telg lõpeb 0,05 l/s/km² juures: sellest madalamad väärtused (kuivaperioodid, nullvool) on kärbitud.' });
      responsive(stage, (box, w) => {
        const m = { l: 50, r: 70, t: 14, b: 30 }, h = 320;
        const svg = el('svg', { width: w, height: h, role: 'img', 'aria-label': 'Vooluhulga kestvuskõver' }, box);
        const all = stations.flatMap((s) => d.flow_duration[s.code].specific_ls_km2).filter((v) => v > 0);
        const FLOOR = 0.05;  // l/s/km2: lower values (dry spells, zero flow) are clipped to the axis floor
        const lo = Math.log10(FLOOR), hi = Math.log10(Math.max(...all));
        const x = (p) => m.l + (w - m.l - m.r) * (p / 100);
        const y = (v) => m.t + (h - m.t - m.b) * (1 - (Math.log10(Math.max(v, FLOOR)) - lo) / (hi - lo));
        for (let e = Math.ceil(lo); e <= Math.floor(hi); e++) {
          el('line', { x1: m.l, x2: w - m.r, y1: y(10 ** e), y2: y(10 ** e), class: 'grid' }, svg);
          el('text', { x: m.l - 6, y: y(10 ** e) + 4, 'text-anchor': 'end', class: 'tick' }, svg, fmt(10 ** e, e < 0 ? -e : 0));
        }
        el('text', { x: m.l - 6, y: 8, 'text-anchor': 'end', class: 'unit' }, svg, 'l/s/km²');
        [0, 20, 40, 60, 80, 100].forEach((p) => el('text', { x: x(p), y: h - 10, 'text-anchor': 'middle', class: 'tick' }, svg, `${p}%`));
        const path = (s) => d.flow_duration[s.code].p.map((p, i) => `${i ? 'L' : 'M'}${x(p)},${y(d.flow_duration[s.code].specific_ls_km2[i])}`).join('');
        for (const s of stations) if (s.code !== sel.code) el('path', { d: path(s), class: 'ctx' }, svg);
        el('path', { d: path(sel), class: 'line thick' }, svg);
        const fd = d.flow_duration[sel.code];
        el('text', { x: w - m.r + 6, y: y(fd.specific_ls_km2[fd.specific_ls_km2.length - 1]) + 4, class: 'lbl' }, svg, sel.name);
        fd.p.forEach((p, i) => {
          const hit = el('rect', { x: x(p) - 8, width: 16, y: m.t, height: h - m.t - m.b, fill: 'transparent' }, svg);
          hover(hit, () => `<b>${sel.name}</b><br>Ületatud ${p}% ajast: <b>${fmt(fd.specific_ls_km2[i], 2)} l/s/km²</b>`);
        });
      });
    });
  }

  /* ---- simple one-colour bars per year ---- */
  function yearBars(host, years, values, opt) {
    const stage = frame(host, { title: opt.title, subtitle: opt.subtitle, table: { head: ['Aasta', opt.unit], rows: years.map((y, i) => [String(y), fmt(values[i], opt.dec)]) }, note: opt.note });
    responsive(stage, (box, w) => {
      const m = { l: 48, r: 10, t: 16, b: 26 }, h = opt.height || 220;
      const svg = el('svg', { width: w, height: h, role: 'img', 'aria-label': opt.title }, box);
      const vals = values.filter((v) => v !== null);
      const hi = Math.max(...vals) * 1.08;
      const { ticks } = niceTicks(0, hi, 4);
      const y = (v) => m.t + (h - m.t - m.b) * (1 - v / hi);
      axisY(el('g', {}, svg), y, ticks, w, m, opt.unit, opt.dec);
      const band = (w - m.l - m.r) / years.length, bw = Math.max(3, Math.min(26, band * 0.7));
      years.forEach((yr, i) => {
        if (values[i] === null) return;
        const cx = m.l + band * (i + 0.5);
        const r = el('rect', { x: cx - bw / 2, width: bw, y: y(values[i]), height: Math.max(1, y(0) - y(values[i])), rx: 2, class: 'bar-neg', tabindex: 0 }, svg);
        hover(r, () => `<b>${yr}</b><br>${fmt(values[i], opt.dec)} ${opt.unit}`);
        if (band >= 26 || i % 2 === 0) el('text', { x: cx, y: h - 8, 'text-anchor': 'middle', class: 'tick' }, svg, String(yr));
      });
    });
  }

  function extremesPanel(host, d) {
    const items = d.stations.filter((s) => d.extremes[s.code] && d.extremes[s.code].years.length >= 5);
    const initial = String((items.find((s) => s.name === 'Tartu') ?? items[0]).code);
    selectable(host, items.map((s) => ({ value: String(s.code), text: `${s.name} (${s.river ?? '–'})` })), initial, 'Jaam:', (holder, code) => {
      const e = d.extremes[code];
      holder.innerHTML = '<div class="panels"><div></div><div></div></div>';
      const [a, b] = holder.firstChild.children;
      yearBars(a, e.years, e.peak, { title: 'Aasta kõrgeim tunnimaksimum', subtitle: 'Suurim „Äravool max“ tunniväärtus aastas.', unit: 'm³/s', dec: 1, note: `Ühik eeldatud. ${e.years.length} aastat ei võimalda korduvusaegade hindamist.` });
      yearBars(b, e.years, e.q7min, { title: 'Madalvesi: väikseim 7 päeva keskmine', subtitle: 'Aasta madalaim 7 järjestikuse päeva keskmine vooluhulk (Q7min).', unit: 'm³/s', dec: 2, note: 'Madalvee 7-päeva keskmine eeldab järjestikuseid kehtivaid päevi; aasta peab olema vähemalt 350 päeva ulatuses kaetud.' });
    });
  }

  /* ---- annual precipitation vs runoff scatter ---- */
  function linkScatter(host, link) {
    const rows = link.years.map((y, i) => [String(y), fmt(link.precip_pct_of_normal[i], 0), fmt(link.runoff_pct_of_mean[i], 0)]);
    const sp = link.spearman;
    const stage = frame(host, { title: 'Sademed ja äravool: kuidas vihm jõgedesse jõuab?', subtitle: `Iga punkt on aasta. Spearmani järgkorrelatsioon ρ = ${fmt(sp.rho, 2)} (95% vahemik ${fmt(sp.lo, 2)} … ${fmt(sp.hi, 2)}, n = ${sp.n}).`, table: { head: ['Aasta', 'Sademed % normist', 'Äravool % keskmisest'], rows },
      note: 'Sademed: riigi jaamade keskmine aastasumma 1991–2020 normist; äravool: jaamade aastase äravoolusügavuse keskmine % jaama enda keskmisest. Lühike rida (n väike) teeb vahemiku laiaks; seos ei tõesta põhjuslikkust (aastane sademete jaotus, lumi, aurumine).' });
    responsive(stage, (box, w) => {
      const m = { l: 52, r: 16, t: 14, b: 40 }, h = 340;
      const svg = el('svg', { width: w, height: h, role: 'img', 'aria-label': 'Sademed ja äravool' }, box);
      const xs = link.precip_pct_of_normal, ys = link.runoff_pct_of_mean;
      const [x0, x1] = [Math.min(...xs, 100) - 4, Math.max(...xs, 100) + 4], [y0, y1] = [Math.min(...ys, 100) - 8, Math.max(...ys, 100) + 8];
      const x = (v) => m.l + (w - m.l - m.r) * ((v - x0) / (x1 - x0)), y = (v) => m.t + (h - m.t - m.b) * (1 - (v - y0) / (y1 - y0));
      for (const t of niceTicks(y0, y1, 5).ticks) { el('line', { x1: m.l, x2: w - m.r, y1: y(t), y2: y(t), class: 'grid' }, svg); el('text', { x: m.l - 6, y: y(t) + 4, 'text-anchor': 'end', class: 'tick' }, svg, fmt(t, 0)); }
      for (const t of niceTicks(x0, x1, 6).ticks) el('text', { x: x(t), y: h - 22, 'text-anchor': 'middle', class: 'tick' }, svg, fmt(t, 0));
      el('line', { x1: x(100), x2: x(100), y1: m.t, y2: h - m.b, class: 'ax-zero' }, svg);
      el('line', { x1: m.l, x2: w - m.r, y1: y(100), y2: y(100), class: 'ax-zero' }, svg);
      el('text', { x: w / 2, y: h - 4, 'text-anchor': 'middle', class: 'unit' }, svg, 'Aastased sademed, % 1991–2020 normist');
      el('text', { x: m.l, y: 8, 'text-anchor': 'start', class: 'unit' }, svg, 'Äravool, % jaamade keskmisest');
      link.years.forEach((yr, i) => {
        const c = el('circle', { cx: x(xs[i]), cy: y(ys[i]), r: 6, class: 'dot-pos', tabindex: 0 }, svg);
        el('text', { x: x(xs[i]) + 9, y: y(ys[i]) + 4, class: 'tick' }, svg, String(yr));
        hover(c, () => `<b>${yr}</b><br>Sademed: ${fmt(xs[i], 0)}% normist<br>Äravool: ${fmt(ys[i], 0)}% keskmisest`);
      });
    });
  }

  Object.assign(window.KaurCharts, { regimeBands, specificHeat, tempHeat, coverageMatrix, flowDuration, yearBars, extremesPanel, linkScatter, selectable });
})();
