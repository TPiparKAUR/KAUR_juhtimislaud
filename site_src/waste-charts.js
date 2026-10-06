/* Waste-statistics charts (extends window.KaurCharts). Data: data/waste.json. Needs airenergy-charts.js. */
(() => {
  'use strict';
  const C = window.KaurCharts;
  const { fmt } = C;
  const { el, frame, responsive, hover } = C.kit;
  const { stackedBars, seriesOf, SLOTS, GREY } = C;

  const unitFor = (max) => (max >= 2e6 ? ['Mt', 1e6, 1] : max >= 2e3 ? ['kt', 1e3, 0] : ['t', 1, 0]);
  const yearSum = (rows, years) => years.map((y) => rows.filter((r) => r.aasta === y).reduce((a, r) => a + r.tonnes, 0));

  /* Stacked bars by catalogue chapter; top chapters get colours, the rest are grouped as 'Muu'. */
  function chapters(host, d, o) {
    const rows = d[o.key].filter((r) => !(o.exclude || []).includes(r.pohigrupp));
    const by = seriesOf(rows.map((r) => ({ ...r, aruanne_aasta: r.aasta })), 'pohigrupp', 'tonnes');
    const tot = (k) => [...by.get(k).values()].reduce((a, b) => a + b, 0);
    const keys = [...by.keys()].filter((k) => tot(k) > 0).sort((a, b) => tot(b) - tot(a));
    const top = keys.slice(0, 7), rest = keys.slice(7);
    const label = (k) => `${k} ${d.meta.chapter_labels_short[k] || ''}`.trim();
    const series = top.map((k, i) => ({ key: k, label: label(k), color: SLOTS[i], values: by.get(k) }));
    if (rest.length) {
      const m = new Map();
      for (const k of rest) for (const [y, v] of by.get(k)) m.set(y, (m.get(y) || 0) + v);
      series.push({ key: 'Muu', label: `Muud peatükid (${rest.length})`, color: GREY, values: m });
    }
    const years = d.meta.years;
    const [unit, scale, dec] = unitFor(Math.max(...yearSum(rows, years)));
    stackedBars(host, { years, scale, unit, dec, height: 320, title: o.title, subtitle: o.subtitle, series, note: o.note });
  }

  function generation(host, d) {
    chapters(host, d, { key: 'generation_by_chapter', title: 'Jäätmeteke peatükkide kaupa', subtitle: 'Netokogus (sh negatiivsed parandused), eeldatud ühik t; jäätmekataloogi peatükk andmetest.', note: 'Peatükk 10 (termilised protsessid, sh põlevkivituhk) domineerib; allpool on sama ilma selleta. Peatükkide nimed on lühendatud ja kontrollimata.' });
  }
  function generationRest(host, d) {
    chapters(host, d, { key: 'generation_by_chapter', exclude: ['10'], title: 'Jäätmeteke ilma peatükita 10', subtitle: 'Netokogus, eeldatud ühik t; peatükk 10 (termilised protsessid) on välja jäetud, et teised peatükid oleksid nähtavad.', note: 'Peatüki 10 väljajätmine on esituse valik, mitte andmete parandus.' });
  }

  /* Small multiples: each flow type on its own axis; never added together. */
  function flows(host, d) {
    const order = d.meta.flow_order;
    host.innerHTML = '<div class="panels"></div>';
    const grid = host.firstChild;
    const years = d.meta.years;
    for (const f of order) {
      const rows = d.flows.filter((r) => r.maht_liik === f);
      const m = new Map(rows.map((r) => [r.aasta, r.tonnes]));
      const mx = Math.max(...m.values(), 0);
      if (!(mx > 0)) continue;
      const [unit, scale, dec] = unitFor(mx);
      const div = document.createElement('div'); grid.appendChild(div);
      const negYears = rows.filter((r) => r.negative_tonnes < 0).length;
      const short = f.length > 52 ? `${f.slice(0, 50).trim()}…` : f;
      const note = [f.length > 52 ? f : '', negYears ? `Negatiivseid väärtusi on ${negYears} aastal (netokogus).` : ''].filter(Boolean).join(' ');
      stackedBars(div, { years, scale, unit, dec, height: 200, noLabels: true, title: short, subtitle: `Suurim: ${fmt(mx / scale, dec)} ${unit} (${[...m].find(([, v]) => v === mx)[0]})`, series: [{ key: f, label: short, color: SLOTS[0], values: m }], note });
    }
  }

  function hazardous(host, d) {
    const years = d.meta.years;
    const haz = new Map(d.hazardous_generation.map((r) => [r.aasta, r.hazardous]));
    const oth = new Map(d.hazardous_generation.map((r) => [r.aasta, r.total - r.hazardous]));
    const share = new Map(d.hazardous_generation.map((r) => [r.aasta, r.share]));
    const mx = Math.max(...d.hazardous_generation.map((r) => r.total));
    const [unit, scale, dec] = unitFor(mx);
    stackedBars(host, { years, scale, unit, dec, height: 280, title: 'Ohtlike jäätmete teke', subtitle: 'Jäätmeteke, ohtlikuks märgitud osa eraldi; eeldatud ühik t.', series: [{ key: 'haz', label: 'Ohtlik', color: SLOTS[7], values: haz }, { key: 'oth', label: 'Muu', color: SLOTS[0], values: oth }],
      note: `Ohtlike osakaal: ${years.filter((y) => share.get(y) != null).map((y) => `${y} ${fmt(100 * share.get(y), 1)}%`).join(', ')}. Osakaal sõltub väga peatükist 10 (põlevkivituhk) ja selle ohtlikkuse märkimisest.` });
  }

  function trade(host, d, punchFn) {
    const groups = [['export_partners', 'Eksport partnerriigi järgi'], ['import_partners', 'Import partnerriigi järgi']];
    C.selectable(host, groups.map(([v, t]) => ({ value: v, text: t })), 'export_partners', 'Suund:', (holder, key) => {
      const rows = d[key];
      const by = seriesOf(rows.map((r) => ({ ...r, aruanne_aasta: r.aasta })), 'partner_riik_nimi', 'tonnes');
      const keys = [...by.keys()].sort((a, b) => Math.max(...by.get(b).values()) - Math.max(...by.get(a).values()));
      const max = Math.max(...keys.flatMap((k) => [...by.get(k).values()]), 1);
      const [unit, scale] = unitFor(max);
      C.matrix(holder, { title: groups.find((g) => g[0] === key)[1], subtitle: 'Kümme suurimat partnerit kogu perioodi summa järgi; värv = kogus ruutjuure skaalal.', rowHead: 'Riik', cols: d.meta.years,
        rows: keys.map((k) => ({ label: k, cells: by.get(k) })), color: (v) => C.kit.sequential(Math.sqrt(Math.max(v, 0)), Math.sqrt(max)), colLabel: String, showCol: () => true,
        fmtCell: (v) => (v === undefined ? '–' : fmt(v / scale, scale === 1 ? 0 : 1)), tip: (v) => `${fmt(v / scale, scale === 1 ? 0 : 1)} ${unit}`, labelW: 130, rowH: 22,
        ramp: `<span>0</span><i class="seq"></i><span>${fmt(max / scale, 0)} ${unit}</span>`, note: 'Partnerriik on märgitud ainult piiriülese liikumise ridadel; "Määramata" tähendab, et riiki ei ole teada.' });
      if (punchFn) C.punch(holder, punchFn(key, by, keys));
    });
  }

  function stocks(host, d) {
    const rows = d.stock_continuity;
    if (!rows.length) return;
    const frm = frame(host, { title: 'Laoseisu järjepidevus', subtitle: 'Aasta Y lõpu laoseis ja aasta Y+1 alguse laoseis peaksid ühtima, kui aruandjad ja andmed on täielikud.',
      table: { head: ['Aasta', 'Lõpu laoseis', 'Järgmise aasta algus', 'Suhe'], rows: rows.map((r) => [String(r.aasta), fmt(r.closing, 0), fmt(r.next_opening, 0), r.ratio == null ? '–' : fmt(r.ratio, 2)]) },
      note: 'Suhe 1,00 = täielik kooskõla. Kõrvalekalle viitab aruandjate koosseisu muutusele või parandustele; see on andmekvaliteedi näitaja, mitte jäätmevoog.' });
    responsive(frm, (box, w) => {
      const m = { l: 44, r: 12, t: 14, b: 26 }, h = 200;
      const svg = el('svg', { width: w, height: h, role: 'img', 'aria-label': 'Laoseisu suhe' }, box);
      const vals = rows.map((r) => r.ratio ?? 1);
      const lo = Math.min(0.5, ...vals) - 0.05, hi = Math.max(1.5, ...vals) + 0.05;
      const y = (v) => m.t + (h - m.t - m.b) * (1 - (v - lo) / (hi - lo));
      el('line', { x1: m.l, x2: w - m.r, y1: y(1), y2: y(1), class: 'grid' }, svg);
      el('text', { x: m.l - 6, y: y(1) + 4, 'text-anchor': 'end', class: 'tick' }, svg, '1,00');
      const band = (w - m.l - m.r) / rows.length;
      rows.forEach((r, i) => {
        const cx = m.l + band * (i + 0.5);
        if (r.ratio != null) { const c = el('circle', { cx, cy: y(r.ratio), r: 5, fill: SLOTS[0], tabindex: 0 }, svg); hover(c, () => `<b>${r.aasta} → ${r.aasta + 1}</b><br>Suhe: ${fmt(r.ratio, 2)}`); }
        el('text', { x: cx, y: h - 8, 'text-anchor': 'middle', class: 'tick' }, svg, String(r.aasta));
      });
    });
  }

  function topTypes(host, d) {
    const rows = d.top_generation;
    const max = Math.max(...rows.map((r) => r.tonnes), 1);
    const [unit, scale, dec] = unitFor(max);
    const frm = frame(host, { title: `Suurimad jäätmeliigid ${d.meta.latest_year}`, subtitle: 'Jäätmeteke, jäätmeliigi kood ja nimetus andmetest; eeldatud ühik t.',
      table: { head: ['Kood', 'Nimetus', `Kogus, ${unit}`], rows: rows.map((r) => [r.jaatmeliik, r.jaatmeliik_nimi, fmt(r.tonnes / scale, dec)]) },
      note: `Aasta ${d.meta.latest_year} andmed võivad olla täienemas.` });
    responsive(frm, (box, w) => {
      const rowH = 24, labelW = Math.min(340, w * 0.55), m = { t: 8, r: 70 }, h = m.t + rowH * rows.length + 8;
      const svg = el('svg', { width: w, height: h, role: 'img', 'aria-label': 'Suurimad jäätmeliigid' }, box);
      rows.forEach((r, i) => {
        const y = m.t + i * rowH, bw = Math.max(1, (w - labelW - m.r) * Math.max(r.tonnes, 0) / max);
        const full = `${r.jaatmeliik} ${r.jaatmeliik_nimi}`, cap = Math.max(12, Math.floor((labelW - 10) / 6.4));
        el('text', { x: labelW - 6, y: y + 15, 'text-anchor': 'end', class: 'tick' }, svg, full.length > cap ? `${full.slice(0, cap - 1)}…` : full);
        const rc = el('rect', { x: labelW, y: y + 3, width: bw, height: rowH - 8, rx: 2, fill: SLOTS[0], tabindex: 0 }, svg);
        hover(rc, () => `<b>${r.jaatmeliik}</b><br>${r.jaatmeliik_nimi}<br>${fmt(r.tonnes / scale, dec)} ${unit}`);
        el('text', { x: labelW + bw + 5, y: y + 15, class: 'lbl' }, svg, fmt(r.tonnes / scale, dec));
      });
    });
  }

  /* Several flows of one stream as lines on one axis (side by side, never summed). */
  function streamLines(host, o) {
    const series = o.series.filter((s) => s.data.length);
    const years = [...new Set(series.flatMap((s) => s.data.map((r) => r.aasta)))].sort((a, b) => a - b);
    const all = series.flatMap((s) => s.data.map((r) => r.tonnes));
    const [unit, scale, dec] = unitFor(Math.max(...all, 0));
    const frm = frame(host, { title: o.title, subtitle: o.subtitle, legend: series.map((s) => ['dot', s.color, s.label]),
      table: { head: ['Aasta', ...series.map((s) => `${s.label} (${unit})`)], rows: years.map((y) => [String(y), ...series.map((s) => { const r = s.data.find((x) => x.aasta === y); return r ? fmt(r.tonnes / scale, dec) : '–'; })]) }, note: o.note });
    responsive(frm, (box, w) => {
      const m = { l: 56, r: 14, t: 16, b: 28 }, h = o.height || 280;
      const svg = el('svg', { width: w, height: h, role: 'img', 'aria-label': o.title }, box);
      const { ticks } = C.kit.niceTicks(0, Math.max(...all, 1) / scale * 1.05, 5);
      const x = (yr) => m.l + (w - m.l - m.r) * ((yr - years[0]) / (years[years.length - 1] - years[0] || 1));
      const y = (v) => m.t + (h - m.t - m.b) * (1 - (v - ticks[0]) / (ticks[ticks.length - 1] - ticks[0] || 1));
      C.kit.axisY(el('g', {}, svg), y, ticks, w, m, unit, dec);
      for (const yr of years.filter((v, i) => i % Math.ceil(years.length / 8) === 0 || i === years.length - 1)) el('text', { x: x(yr), y: h - 8, 'text-anchor': 'middle', class: 'tick' }, svg, String(yr));
      for (const s of series) {
        el('path', { d: s.data.map((r, i) => `${i ? 'L' : 'M'}${x(r.aasta)},${y(r.tonnes / scale)}`).join(''), fill: 'none', stroke: s.color, 'stroke-width': 2.4 }, svg);
        for (const r of s.data) { const c = el('circle', { cx: x(r.aasta), cy: y(r.tonnes / scale), r: 3, fill: s.color, tabindex: 0 }, svg); hover(c, () => `<b>${r.aasta}</b><br>${s.label}: <b>${fmt(r.tonnes / scale, dec)} ${unit}</b>${r.negative_tonnes < 0 ? `<br>sh negatiivseid ${fmt(r.negative_tonnes / scale, dec)} ${unit}` : ''}`); }
      }
    });
  }

  Object.assign(window.KaurCharts, { wasteStreamLines: streamLines, wasteGeneration: generation, wasteGenerationRest: generationRest, wasteFlows: flows, wasteHazardous: hazardous, wasteTrade: trade, wasteStocks: stocks, wasteTopTypes: topTypes });
})();
