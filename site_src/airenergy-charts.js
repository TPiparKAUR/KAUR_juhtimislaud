/* Air-emission and energy charts (extends window.KaurCharts). Data: data/airenergy.json. */
(() => {
  'use strict';
  const C = window.KaurCharts;
  const { fmt, sgn } = C;
  const { el, frame, responsive, niceTicks, hover, axisY, sequential } = C.kit;
  // Fixed categorical order (validated palette slots); entity -> colour never changes with filtering.
  const SLOTS = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#4a3aa7', '#e34948'];
  const GREY = '#8c8b86';
  const FUEL_COLOR = { 'Põlevkivi': SLOTS[3], 'Põlevkiviõli': SLOTS[5], 'Maagaas': SLOTS[1], 'Puit ja biomass': SLOTS[0], 'Tööstus- ja muud gaasid': SLOTS[2], 'Jäätmed': SLOTS[4], 'Turvas': SLOTS[7], 'Nafta- ja veeldatud gaasid': SLOTS[6] };

  /* Stacked bars by year. series: [{key,label,color,values:Map(year->value)}] */
  function stackedBars(host, o) {
    const years = o.years;
    const totals = years.map((y) => o.series.reduce((a, s) => a + (s.values.get(y) || 0), 0));
    if (!(Math.max(...totals) > 0)) { host.insertAdjacentHTML('beforeend', `<p class="viz-note">${o.title}: andmeid ei ole.</p>`); return; }
    const rows = years.map((y, i) => [String(y), ...o.series.map((s) => fmt((s.values.get(y) || 0) / o.scale, o.dec)), fmt(totals[i] / o.scale, o.dec)]);
    const stage = frame(host, {
      title: o.title, subtitle: o.subtitle,
      legend: o.series.map((s) => ['box', s.color, s.label]),
      table: { head: ['Aasta', ...o.series.map((s) => s.label), 'Kokku'], rows }, note: o.note,
    });
    responsive(stage, (box, w) => {
      const m = { l: 52, r: 12, t: 24, b: 40 }, h = o.height || 300;
      const svg = el('svg', { width: w, height: h, role: 'img', 'aria-label': o.title }, box);
      const hi = Math.max(...totals) * 1.08 / o.scale;
      const { ticks } = niceTicks(0, hi, 5);
      const y = (v) => m.t + (h - m.t - m.b) * (1 - v / hi);
      axisY(el('g', {}, svg), y, ticks, w, m, o.unit, o.dec);
      const band = (w - m.l - m.r) / years.length, bw = Math.max(6, Math.min(64, band * 0.7));
      years.forEach((yr, i) => {
        const cx = m.l + band * (i + 0.5);
        let acc = 0;
        o.series.forEach((s, k) => {
          const v = (s.values.get(yr) || 0) / o.scale;
          if (v <= 0) return;
          const r = el('rect', { x: cx - bw / 2, width: bw, y: y(acc + v), height: Math.max(1, y(acc) - y(acc + v) - 2), rx: 2, fill: s.color, tabindex: 0 }, svg);
          hover(r, () => `<b>${yr}</b><br>${s.label}: <b>${fmt(v, o.dec)} ${o.unit}</b><br>Kokku: ${fmt(totals[i] / o.scale, o.dec)} ${o.unit}${o.coverage ? `<br>${o.coverage.get(yr)} aruannet` : ''}`);
          acc += v;
        });
        el('text', { x: cx, y: y(acc) - 5, 'text-anchor': 'middle', class: 'lbl' }, svg, fmt(acc, o.dec));
        el('text', { x: cx, y: h - 22, 'text-anchor': 'middle', class: 'tick' }, svg, String(yr));
        if (o.coverage) el('text', { x: cx, y: h - 8, 'text-anchor': 'middle', class: 'unit' }, svg, `n=${o.coverage.get(yr)}`);
      });
    });
  }

  function seriesOf(rows, key, valKey, filter) {
    const map = new Map();
    for (const r of rows) { if (filter && !filter(r)) continue; if (!map.has(r[key])) map.set(r[key], new Map()); map.get(r[key]).set(r.aruanne_aasta, (map.get(r[key]).get(r.aruanne_aasta) || 0) + r[valKey]); }
    return map;
  }

  function co2Ets(host, d) {
    const cov = new Map(d.coverage.map((r) => [r.aruanne_aasta, r.reports]));
    const by = seriesOf(d.ets, 'ets', 'tonnes');
    const order = [['Jah', 'ETS-kohuslane', SLOTS[0]], ['Ei', 'Mitte-ETS', SLOTS[1]], ['teadmata', 'ETS-staatus teadmata', GREY]];
    stackedBars(host, { years: d.meta.years, scale: 1e6, unit: 'Mt', dec: 2, height: 320, coverage: cov,
      title: 'Fossiilne CO₂ aruannetes aastas', subtitle: 'Kütuste põletamisel deklareeritud CO₂ (biomassi CO₂ eraldi allpool); jaotus ETS-kohustuse järgi.',
      series: order.filter(([k]) => by.has(k)).map(([k, label, color]) => ({ key: k, label, color, values: by.get(k) })),
      note: 'Allikas: KOTKAS õhuaruanded (asutuste deklaratsioonid), mitte riigi inventuur. n = aasta aruannete arv; aruannete koosseis muutub, seega aastate vahe ei ole puhas heite muutus.' });
  }

  function co2Bio(host, d) {
    const by = seriesOf(d.co2, 'aine_stat_grupp', 'tonnes');
    const bio = by.get('CO2 bio') || new Map();
    stackedBars(host, { years: d.meta.years, scale: 1e6, unit: 'Mt', dec: 2, height: 220,
      title: 'Biogeenne CO₂ (biomassi põletamisel)', subtitle: 'Deklareeritud eraldi fossiilsest CO₂-st; ei liideta fossiilsega.',
      series: [{ key: 'bio', label: 'Biogeenne CO₂', color: SLOTS[2], values: bio }],
      note: 'Biogeenne CO₂ arvestatakse riiklikus aruandluses teisiti kui fossiilne; siin on see vaid asutuste deklareeritud kogus.' });
  }

  function sectors(host, d) {
    const names = d.meta.nfr_names;
    const groups = [['CO2', 'Fossiilne CO₂', 'Mt', 1e6, 2], ['NO2', 'NOx (NO₂-na)', 'kt', 1e3, 2], ['NH3', 'NH₃', 'kt', 1e3, 2]];
    C.selectable(host, groups.map(([v, t]) => ({ value: v, text: t })), 'CO2', 'Aine:', (holder, g) => {
      const [, label, unit, scale, dec] = groups.find((x) => x[0] === g);
      const rows = d.sectors[g];
      const by = seriesOf(rows, 'sector', 'tonnes');
      const total = (k) => [...by.get(k).values()].reduce((a, b) => a + b, 0);
      const keys = [...by.keys()].filter((k) => k !== 'Muu').sort((a, b) => total(b) - total(a));
      const series = keys.map((k, i) => ({ key: k, label: names[k] ? `${k} ${names[k]}` : k, color: SLOTS[i % SLOTS.length], values: by.get(k) }));
      if (by.has('Muu')) series.push({ key: 'Muu', label: 'Muu', color: GREY, values: by.get('Muu') });
      stackedBars(holder, { years: d.meta.years, scale, unit, dec, height: 320, title: `${label} sektorite kaupa (NFR)`, subtitle: 'EMEP/EEA NFR sektor aruandes; suurimad sektorid eraldi, ülejäänud kokku.', series,
        note: 'NFR-kood tuleb aruandest; sektorinimed on lühendatud EMEP/EEA klassifikaatori põhjal ja kontrollimata (koodi näeb alati kõrval).' });
    });
  }

  function pollutants(host, d) {
    const names = d.meta.pollutants;
    host.innerHTML = '<div class="panels"></div>';
    const grid = host.firstChild;
    const by = seriesOf(d.pollutants, 'aine_stat_grupp', 'tonnes');
    for (const [k, label] of Object.entries(names)) {
      if (!by.has(k)) continue;
      const div = document.createElement('div'); grid.appendChild(div);
      const sc = Math.max(...by.get(k).values()) >= 2000 ? ['kt', 1e3, 1] : ['t', 1, 0];
      stackedBars(div, { years: d.meta.years, scale: sc[1], unit: sc[0], dec: sc[2], height: 200, title: label, subtitle: '', series: [{ key: k, label, color: SLOTS[0], values: by.get(k) }] });
    }
  }

  function counties(host, d) {
    const groups = [['CO2', 'Fossiilne CO₂'], ['NO2', 'NOx (NO₂-na)']];
    C.selectable(host, groups.map(([v, t]) => ({ value: v, text: t })), 'CO2', 'Aine:', (holder, g) => {
      const by = seriesOf(d.counties[g], 'county', 'tonnes');
      const years = d.meta.years;
      const keys = [...by.keys()].filter((k) => k !== 'teadmata').sort((a, b) => Math.max(...by.get(b).values()) - Math.max(...by.get(a).values()));
      const max = Math.max(...keys.flatMap((k) => [...by.get(k).values()]));
      const rows = keys.map((k) => ({ label: k.replace(' maakond', ''), cells: by.get(k) }));
      const unit = g === 'CO2' ? ['kt', 1e3] : ['t', 1];
      C.matrix(holder, { title: `${g === 'CO2' ? 'Fossiilne CO₂' : 'NOx'} maakonniti`, subtitle: 'Aruandes märgitud tegevuskoha maakonna järgi; värv = kogus ruutjuure skaalal.', rowHead: 'Maakond', cols: years, rows,
        color: (v) => sequential(Math.sqrt(v), Math.sqrt(max)), colLabel: String, showCol: () => true, fmtCell: (v) => (v === undefined ? '–' : fmt(v / unit[1], 1)), tip: (v) => `${fmt(v / unit[1], 1)} ${unit[0]}`, labelW: 130, rowH: 22,
        ramp: `<span>0</span><i class="seq"></i><span>${fmt(max / unit[1], 0)} ${unit[0]}</span>`, note: 'Suurimad kogused koonduvad üksikutesse suurkäitistesse (vt kontsentratsioon): maakonna värv näitab seal asuvaid asutusi, mitte maakonna elanike heidet.' });
    });
  }

  function concentration(host, d) {
    const groups = [['CO2', 'Fossiilne CO₂'], ['NO2', 'NOx'], ['SO2', 'SO₂']];
    C.selectable(host, groups.map(([v, t]) => ({ value: v, text: t })), 'CO2', 'Aine:', (holder, g) => {
      const rows = d.concentration[g];
      const stage = frame(holder, { title: 'Kui suur osa heitest tuleb üksikutelt suurematelt aruannetelt?', subtitle: 'Suurima 1, 5 ja 10 aruande osakaal aasta kogusest (identiteete ei salvestata).',
        legend: [['box', SLOTS[0], 'Suurim 1'], ['box', SLOTS[1], 'Suurim 5'], ['box', SLOTS[2], 'Suurim 10']],
        table: { head: ['Aasta', 'Aruandeid', 'Top 1 %', 'Top 5 %', 'Top 10 %'], rows: rows.map((r) => [String(r.aruanne_aasta), String(r.reports), fmt(100 * r.top1_share, 0), fmt(100 * r.top5_share, 0), fmt(100 * r.top10_share, 0)]) },
        note: 'Kõrge osakaal tähendab, et aastate muutust määravad mõne üksiku asutuse otsused (nt tootmise sulgemine), mitte sektori üldine areng.' });
      responsive(stage, (box, w) => {
        const m = { l: 44, r: 12, t: 14, b: 26 }, h = 240;
        const svg = el('svg', { width: w, height: h, role: 'img', 'aria-label': 'Kontsentratsioon' }, box);
        const y = (v) => m.t + (h - m.t - m.b) * (1 - v);
        for (const t of [0, 0.25, 0.5, 0.75, 1]) { el('line', { x1: m.l, x2: w - m.r, y1: y(t), y2: y(t), class: 'grid' }, svg); el('text', { x: m.l - 6, y: y(t) + 4, 'text-anchor': 'end', class: 'tick' }, svg, `${100 * t}%`); }
        const x = (i) => m.l + (w - m.l - m.r) * (rows.length === 1 ? 0.5 : i / (rows.length - 1));
        [['top1_share', SLOTS[0]], ['top5_share', SLOTS[1]], ['top10_share', SLOTS[2]]].forEach(([k, col]) => {
          el('path', { d: rows.map((r, i) => `${i ? 'L' : 'M'}${x(i)},${y(r[k])}`).join(''), fill: 'none', stroke: col, 'stroke-width': 2.5 }, svg);
          rows.forEach((r, i) => { const c = el('circle', { cx: x(i), cy: y(r[k]), r: 4, fill: col, stroke: 'var(--surface)', 'stroke-width': 2, tabindex: 0 }, svg); hover(c, () => `<b>${r.aruanne_aasta}</b><br>${k.replace('top', 'Suurim ').replace('_share', '')}: <b>${fmt(100 * r[k], 0)}%</b><br>${r.reports} aruannet`); });
        });
        rows.forEach((r, i) => el('text', { x: x(i), y: h - 8, 'text-anchor': 'middle', class: 'tick' }, svg, String(r.aruanne_aasta)));
      });
    });
  }

  function sensitivity(host, d) {
    const years = d.meta.years;
    const by = seriesOf(d.sensitivity.map((r) => ({ ...r, tonnes: r.gap_share ?? 0 })), 'aine_stat_grupp', 'tonnes');
    const keys = [...by.keys()];
    const rows = keys.map((k) => ({ label: d.meta.pollutants[k] || (k === 'CO2' ? 'Fossiilne CO₂' : k === 'CO2 bio' ? 'Biogeenne CO₂' : k), cells: by.get(k) }));
    C.matrix(host, { title: 'Tundlikkus: kui palju summa muutuks, kui samasuguse võtmega ridadest jääks alles ainult esimene?', subtitle: 'Osakaal aasta kogusest (%). Võti = aruanne, allikas, aine, kütus.', rowHead: 'Aine', cols: years, rows,
      color: (v) => sequential(Math.sqrt(v), Math.sqrt(0.2)), colLabel: String, showCol: () => true, fmtCell: (v) => (v === undefined ? '–' : `${fmt(100 * v, 1)}%`), tip: (v) => `Vahe: <b>${fmt(100 * v, 1)}%</b>`, labelW: 150, rowH: 22,
      ramp: '<span>0%</span><i class="seq"></i><span>20%+</span>', note: 'Kui vahe on väike, ei mõjuta ridade kordumine tulemust. Suurem vahe tähendab, et sama võtmega ridu (nt eri arvutusmeetodid) võib olla topelt; kasutaja peab selle arvesse võtma.' });
  }

  function energyFuel(host, d) {
    const rows = d.energy.by_fuel;
    const by = seriesOf(rows.map((r) => ({ ...r, fuel: r.fuel ?? 'Muu' })), 'fuel', 'heat');
    const total = (k) => [...by.get(k).values()].reduce((a, b) => a + b, 0);
    const keys = [...by.keys()].filter((k) => k !== 'Muu').sort((a, b) => total(b) - total(a));
    const series = keys.map((k, i) => ({ key: k, label: k, color: FUEL_COLOR[k] || GREY, values: by.get(k) }));
    if (by.has('Muu')) series.push({ key: 'Muu', label: 'Muu', color: GREY, values: by.get('Muu') });
    stackedBars(host, { years: d.meta.years, scale: 1e6, unit: 'TWh', dec: 1, height: 320, title: 'Deklareeritud soojatoodang kütuse järgi', subtitle: 'Aruannetes deklareeritud soojus, ühik eeldatud MWh (tabeli skeemis puudub). Ebareaalse soojus/kütus suhtega read on välja jäetud; «Muu» sisaldab ka kütuseta ridu.',
      series, note: `Väljajäetud read: ${d.meta.data_quality.heat.flagged_rows} (ühiku- või sisestusvea tunnused). Aruannete arv muutub aastati; see on kõigi aruandvate käitiste, mitte kogu Eesti soojatoodang.` });
  }

  function energyElectricity(host, d) {
    const rows = d.energy.by_fuel;
    const by = seriesOf(rows.map((r) => ({ ...r, fuel: r.fuel ?? 'Muu' })), 'fuel', 'electricity');
    const total = (k) => [...by.get(k).values()].reduce((a, b) => a + b, 0);
    const keys = [...by.keys()].filter((k) => total(k) > 0).sort((a, b) => total(b) - total(a));
    const series = keys.map((k, i) => ({ key: k, label: k, color: FUEL_COLOR[k] || GREY, values: by.get(k) }));
    stackedBars(host, { years: d.meta.years, scale: 1e6, unit: 'TWh', dec: 2, height: 260, title: 'Deklareeritud elektritoodang kütuse järgi', subtitle: 'Soojus- ja elektrijaamade aruannetest; ühik eeldatud MWh.', series, note: 'Aruandjate koosseis muutub, seega ei ole see riigi elektritoodangu statistika.' });
  }

  function heatClimate(host, d) {
    const L = d.energy.climate_link;
    if (!L) return;
    const stage = frame(host, { title: 'Külm talv ja soojatoodang', subtitle: 'Iga punkt on aasta: talve (dets–veebr) õhutemperatuuri kõrvalekalle normist ja deklareeritud soojatoodang.',
      table: { head: ['Aasta', 'Talve anomaalia °C', 'Soojus (MWh)'], rows: L.years.map((y, i) => [String(y), fmt(L.djf_anomaly_degC[i], 1), fmt(L.heat_mwh[i], 0)]) },
      note: 'Vaid orientiirina: punkte on vähe, aruannete koosseis muutub ja ühik on eeldatud. Statistikut ei arvutata.' });
    responsive(stage, (box, w) => {
      const m = { l: 60, r: 16, t: 14, b: 40 }, h = 300;
      const svg = el('svg', { width: w, height: h, role: 'img', 'aria-label': 'Soojatoodang ja talv' }, box);
      const xs = L.djf_anomaly_degC, ys = L.heat_mwh.map((v) => v / 1e6);
      const x0 = Math.min(...xs) - 0.4, x1 = Math.max(...xs) + 0.4, y0 = 0, y1 = Math.max(...ys) * 1.1;
      const x = (v) => m.l + (w - m.l - m.r) * ((v - x0) / (x1 - x0)), y = (v) => m.t + (h - m.t - m.b) * (1 - (v - y0) / (y1 - y0));
      for (const t of niceTicks(y0, y1, 4).ticks) { el('line', { x1: m.l, x2: w - m.r, y1: y(t), y2: y(t), class: 'grid' }, svg); el('text', { x: m.l - 6, y: y(t) + 4, 'text-anchor': 'end', class: 'tick' }, svg, fmt(t, 1)); }
      for (const t of niceTicks(x0, x1, 6).ticks) el('text', { x: x(t), y: h - 22, 'text-anchor': 'middle', class: 'tick' }, svg, fmt(t, 1));
      el('text', { x: w / 2, y: h - 4, 'text-anchor': 'middle', class: 'unit' }, svg, 'Talve temperatuuri kõrvalekalle normist, °C');
      el('text', { x: m.l, y: 8, 'text-anchor': 'start', class: 'unit' }, svg, 'Soojus, TWh');
      L.years.forEach((yr, i) => { const c = el('circle', { cx: x(xs[i]), cy: y(ys[i]), r: 6, class: 'dot-pos', tabindex: 0 }, svg); el('text', { x: x(xs[i]) + 9, y: y(ys[i]) + 4, class: 'tick' }, svg, String(yr)); hover(c, () => `<b>${yr}</b><br>Talv: ${sgn(xs[i], 1)} °C<br>Soojus: ${fmt(ys[i], 1)} TWh`); });
    });
  }

  Object.assign(window.KaurCharts, { co2Ets, co2Bio, aeSectors: sectors, aePollutants: pollutants, aeCounties: counties, aeConcentration: concentration, aeSensitivity: sensitivity, aeFuel: energyFuel, aeElectricity: energyElectricity, aeHeatClimate: heatClimate });
})();
