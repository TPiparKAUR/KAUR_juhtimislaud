/* Renders the hydrology analysis from data/hydro.json into [data-hydro] containers. */
(async () => {
  'use strict';
  const hosts = [...document.querySelectorAll('[data-hydro]')];
  if (!hosts.length) return;
  const C = window.KaurCharts, { fmt, sgn } = C;
  let d;
  try {
    const res = await fetch('data/hydro.json', { cache: 'no-cache' });
    if (!res.ok) throw new Error(res.status);
    d = await res.json();
  } catch (e) {
    for (const h of hosts) h.innerHTML = '<p class="viz-note">Hüdroloogia analüüsi andmed pole hetkel saadaval.</p>';
    return;
  }
  const unit = 'm³/s';
  const named = (s) => `${s.name} (${s.river ?? '–'})`;
  const N = d.national_runoff;
  const ranked = N.year.map((y, i) => [y, N.pct_of_mean[i], N.n[i]]).filter((r) => r[1] !== null).sort((a, b) => b[1] - a[1]);

  const builders = {
    findings(host) {
      const li = [];
      const yrs = d.stations.map((s) => [s.first.slice(0, 4), s.last.slice(0, 4)]);
      li.push(`<li><b>Andmed:</b> ${d.stations.length} jõejaama pikkade vooluhulga ridadega (${Math.min(...yrs.map((y) => +y[0]))}–${d.meta.current_year}), tunniväärtused koondatud UTC päevadeks. Vooluhulga ühik ${unit} on <b>eeldatud</b> (tabeli skeemis puudub); kontrollina on mediaanerivool ${fmt(d.plausibility.specific_runoff_ls_km2?.median, 1)} l/s/km² (vahemik ${fmt(d.plausibility.specific_runoff_ls_km2?.min, 1)} … ${fmt(d.plausibility.specific_runoff_ls_km2?.max, 1)}).</li>`);
      if (ranked.length >= 4) {
        li.push(`<li><b>Veerikkad ja kuivad aastad:</b> kõige veerikkamad ${ranked.slice(0, 3).map((r) => `${r[0]} (${fmt(r[1], 0)}%)`).join(', ')}; kõige väiksema äravooluga ${ranked.slice(-3).reverse().map((r) => `${r[0]} (${fmt(r[1], 0)}%)`).join(', ')} (% jaamade enda keskmisest).</li>`);
      }
      const L = d.climate_link;
      if (L) {
        const sp = L.spearman;
        li.push(`<li><b>Sademed ja äravool:</b> aastane riigi äravool ja sademete summa on seotud (ρ = ${fmt(sp.rho, 2)}, 95% vahemik ${fmt(sp.lo, 2)} … ${fmt(sp.hi, 2)}, n = ${sp.n}); ${sp.lo > 0 ? 'seos on positiivne ja vahemik ei sisalda nulli' : 'vahemik sisaldab nulli, seos pole selle valimiga kindlalt eristatav'}.</li>`);
      }
      let out = 0, total = 0, below = 0;
      for (const s of d.stations) {
        const r = d.regime[s.code];
        if (!r) continue;
        r.current_months.forEach((m) => { const i = r.months.indexOf(m); if (i < 0) return; total += 1; const v = r.current[r.current_months.indexOf(m)]; if (v > r.q90[i] || v < r.q10[i]) out += 1; if (v < r.q10[i]) below += 1; });
      }
      if (total) li.push(`<li><b>${d.meta.current_year}:</b> ${fmt(100 * out / total, 0)}% jaama-kuu väärtustest jääb väljapoole 10.–90. protsentiili (${out}/${total}; neist ${below} alla ja ${out - below} üle). Kui aasta oleks varasemate sarnane, oleks neid umbes 20%.</li>`);
      const means = d.stations.map((s) => ({ s, m: (d.annual[s.code]?.specific_ls_km2 || []).filter((v) => v !== null) })).filter((x) => x.m.length >= 5).map((x) => ({ name: x.s.name, v: x.m.reduce((a, b) => a + b, 0) / x.m.length }));
      const sorted = means.map((x) => x.v).sort((a, b) => a - b), med = sorted[sorted.length >> 1];
      const high = means.filter((x) => x.v > 1.3 * med).map((x) => `${x.name} (${fmt(x.v, 1)})`);
      if (high.length) li.push(`<li><b>Kontrolli vajav:</b> ${high.join(', ')} l/s/km² on jaamade mediaanist (${fmt(med, 1)}) üle 30% kõrgem – valgala pindala, mõõtekõver või maa-alune toide vajab kontrolli enne jaamade omavahelist võrdlust.</li>`);
      const sw = d.water_temperature, years = {};
      for (const [code, t] of Object.entries(sw)) {
        const vals = t.years.map((y, i) => [y, t.summer_mean[i]]).filter(([, v]) => v !== null);
        if (vals.length < 8) continue;
        const mean = vals.reduce((a, [, v]) => a + v, 0) / vals.length;
        for (const [y, v] of vals) (years[y] ||= []).push(v - mean);
      }
      const yr = Object.entries(years).filter(([, a]) => a.length >= 8).map(([y, a]) => [+y, a.reduce((x, z) => x + z, 0) / a.length]).sort((a, b) => b[1] - a[1]);
      if (yr.length >= 4) li.push(`<li><b>Veetemperatuur:</b> kõige soojemad suved ${yr.slice(0, 3).map((r) => `${r[0]} (${sgn(r[1], 1)} °C)`).join(', ')}, kõige jahedamad ${yr.slice(-3).reverse().map((r) => `${r[0]} (${sgn(r[1], 1)} °C)`).join(', ')} (jaamade keskmine kõrvalekalle oma keskmisest, juuni–august).</li>`);
      const dq = d.quality.dropped, nq = dq.reduce((acc, x) => acc + x.negative + x.spike + x.out_of_range, 0);
      if (nq) li.push(`<li><b>Andmekvaliteet:</b> lihtne reeglipõhine sõel jättis välja ${nq} päevaväärtust (${dq.map((x) => `${(d.stations.find((s) => s.code === x.jaam_kood) || {}).name ?? x.jaam_kood}: ${x.series}, ${x.negative + x.spike + x.out_of_range}`).join('; ')}) – negatiivne vooluhulk, ebareaalne hüpe (> ${d.quality.rules.discharge_spike.match(/\d+/)[0]}× jaama enda Q95) või füüsikaliselt võimatu veetemperatuur. Andmete omaniku kvaliteedikontrolli tase ei ole teada.</li>`);
      host.innerHTML = `<ul class="findings">${li.join('')}</ul>`;
    },
    regime(host) {
      const items = d.stations.filter((s) => d.regime[s.code]);
      const initial = String((items.find((s) => s.name === 'Tartu') ?? items[0]).code);
      C.selectable(host, items.map((s) => ({ value: String(s.code), text: named(s) })), initial, 'Jaam:', (holder, code) => {
        const s = items.find((x) => String(x.code) === code);
        C.regimeBands(holder, d.regime[code], named(s), { unit, refFrom: 2013, subtitle: `Kuude keskmine vooluhulk (${unit}, eeldatud) võrreldes varasemate aastatega; valgala ${fmt(s.area_km2, 0)} km².`, note: 'Kuu loetakse ainult vähemalt 25 kehtiva päevaga. Tavavahemik tuleneb ~12 aastast: servale jäävad väärtused ei ole haruldused pikas plaanis.' });
        const r = d.regime[code];
        let below = 0, above = 0;
        r.current_months.forEach((m, k) => { const i = r.months.indexOf(m); if (i < 0) return; if (r.current[k] < r.q10[i]) below += 1; else if (r.current[k] > r.q90[i]) above += 1; });
        C.punch(holder, `${s.name}: ${d.meta.current_year}. aasta ${r.current_months.length} kuust jääb ${below} alla ja ${above} üle varasemate aastate 10.–90. protsentiili (oodatav osa väljaspool on umbes 20%).`);
      });
    },
    specific(host) {
      C.specificHeat(host, d, { note: 'Erivool = kuu mediaanvooluhulk / valgala pindala. Ühik eeldatud m³/s → l/s/km². Reguleerimata ja reguleeritud jõgesid ei eristata.' });
      const m = d.stations.map((s) => ({ s, v: (d.annual[s.code]?.specific_ls_km2 || []).filter((x) => x !== null) })).filter((x) => x.v.length >= 5).map((x) => ({ name: x.s.name, v: x.v.reduce((a, b) => a + b, 0) / x.v.length })).sort((a, b) => b.v - a.v);
      if (m.length > 1) C.punch(host, `Keskmine erivool on suurim jaamas ${m[0].name} (${fmt(m[0].v, 1)} l/s/km²) ja väikseim jaamas ${m[m.length - 1].name} (${fmt(m[m.length - 1].v, 1)}); vahe ${fmt(m[0].v / m[m.length - 1].v, 1)}-kordne.`);
    },
    fdc(host) {
      C.flowDuration(host, d);
      const q = Object.entries(d.flow_duration).map(([code, f]) => { const i50 = f.p.indexOf(50), i95 = f.p.indexOf(95); return i50 < 0 || i95 < 0 ? null : { name: (d.stations.find((x) => String(x.code) === code) || {}).name ?? code, r: f.specific_ls_km2[i95] / f.specific_ls_km2[i50] }; }).filter(Boolean).sort((a, b) => b.r - a.r);
      if (q.length > 1) C.punch(host, `Madalvee (95. protsentiil) on ${fmt(100 * q[q.length - 1].r, 0)}–${fmt(100 * q[0].r, 0)}% mediaanvoolust: kõige ühtlasema režiimiga on ${q[0].name}, kõige muutlikum ${q[q.length - 1].name}.`);
    },
    runoff(host) {
      C.annualBars(host, { years: N.year, mean: N.pct_of_mean, p10: N.p10, p90: N.p90, n_stations: N.n, trend: null }, { title: 'Aastane äravool protsendina jaamade enda keskmisest', subtitle: 'Kõigi jaamade keskmine; kriipsud: jaamade vahe (10.–90. protsentiil).', unit: '%', valueHead: '% keskmisest', dec: 0, baseline: 100, posLabel: 'Keskmisest veerikkam', negLabel: 'Keskmisest vaesem', height: 280, labelTop: 2, note: 'Referents on jaama kõigi täisaastate keskmine, mitte 30-aastane norm. Aasta loetakse ainult vähemalt 350 kehtiva päevaga.' });
      if (ranked.length >= 2) C.punch(host, `Veerikkaim aasta oli ${ranked[0][0]} (${fmt(ranked[0][1], 0)}% keskmisest), kõige väiksema äravooluga ${ranked[ranked.length - 1][0]} (${fmt(ranked[ranked.length - 1][1], 0)}%).`);
    },
    link(host) {
      if (!d.climate_link) return;
      C.linkScatter(host, d.climate_link);
      const sp = d.climate_link.spearman;
      if (sp) C.punch(host, `Sademeterikkad aastad on ka veerikkad: Spearmani ρ = ${fmt(sp.rho, 2)} (95% vahemik ${fmt(sp.lo, 2)} … ${fmt(sp.hi, 2)}, n = ${sp.n}); korrelatsioon ei tõesta põhjuslikkust.`);
    },
    extremes(host) {
      C.extremesPanel(host, d);
      let pk = null;
      for (const [code, e] of Object.entries(d.extremes)) e.years.forEach((y, i) => { if (e.peak[i] !== null && (!pk || e.peak[i] > pk.v)) pk = { v: e.peak[i], y, name: (d.stations.find((x) => String(x.code) === code) || {}).name ?? code }; });
      if (pk) C.punch(host, `Suurim registreeritud aasta tipp on ${fmt(pk.v, 0)} m³/s (${pk.name}, ${pk.y}); read algavad ${Math.min(...Object.values(d.extremes).map((e) => e.years[0]))}. aastast, seega korduvusaegu ei hinnata.`);
    },
    temp(host) {
      C.tempHeat(host, d);
      const years = {};
      for (const t of Object.values(d.water_temperature)) {
        const v = t.years.map((y, i) => [y, t.summer_mean[i]]).filter(([, x]) => x !== null);
        if (v.length < 4) continue;
        const mean = v.reduce((a, [, x]) => a + x, 0) / v.length;
        for (const [y, x] of v) (years[y] ||= []).push(x - mean);
      }
      const yr = Object.entries(years).map(([y, a]) => [+y, a.reduce((x, z) => x + z, 0) / a.length]).sort((a, b) => b[1] - a[1]);
      if (yr.length >= 2) C.punch(host, `Soojim jõesuvi oli ${yr[0][0]} (${sgn(yr[0][1], 1)} °C jaama keskmisest) ja jahedaim ${yr[yr.length - 1][0]} (${sgn(yr[yr.length - 1][1], 1)} °C); suvi = juuni–august.`);
    },
    coverage(host) {
      C.coverageMatrix(host, d);
      const c = d.coverage.cells, good = c.filter((x) => x[2] >= 0.95).length;
      C.punch(host, `${fmt(100 * good / c.length, 0)}% jaama-aastatest on vähemalt 95% katvusega (${c.length} jaama-aastat); ${d.meta.current_year}. aasta on pooleli.`);
    },
    methods(host) {
      host.innerHTML = `<div class="methods"><b>Andmed ja meetod</b> <span class="review-flag">valdkonnaekspert ülevaatamata</span>
        <p><b>Allikas ja päritolu:</b> Keskkonnaagentuuri avaandmed (keskkonnaandmed.envir.ee, tabel f_hydroseire): avaldatud seireread, tunniväärtused koondatud UTC kalendripäevadeks (päev vajab ≥ 20 tundi). Tabeli skeem ei nimeta ühikuid ega kvaliteeditaset: vooluhulk on eeldatud m³/s ja veetemperatuur °C (toetab kontroll: 15 jaama mediaanerivool 4–7 l/s/km²), kvaliteeditaset ei eeldata. Lisaks on rakendatud meie enda lihtne sõel (negatiivsed väärtused, ebareaalsed hüpped, võimatu temperatuur).</p>
        <p><b>Meetod:</b> kuud ≥ 25 ja aastad ≥ 350 kehtiva päevaga; erivool = vooluhulk / valgala pindala; kestvuskõver kõigist kehtivatest päevadest; Q7min = aasta madalaim 7-päeva keskmine; seos sademetega Spearmani järgkorrelatsioon (bootstrap-vahemik) kliimaanalüüsi aastasete sademetega.</p>
        <p><b>Piirangud:</b> read algavad 2012, seega korduvusaegu ega pikaajalisi trende hinnata ei saa; jaamad on valitud rea pikkuse järgi, mitte kogu võrgu esindajana; jõgede reguleerimist (paisud, järved) ei ole eristatud; UTC päevad erinevad kohaliku aja päevadest kuni 3 tunni võrra.</p>
        <p>Genereeritud ${d.meta.generated_utc.slice(0, 10)} (UTC).</p></div>`;
    },
  };
  for (const h of hosts) {
    const fn = builders[h.dataset.hydro];
    if (fn) { try { fn(h); } catch (e) { h.innerHTML = '<p class="viz-note">Graafikut ei saanud joonistada.</p>'; console.error(e); } }
  }
})();
