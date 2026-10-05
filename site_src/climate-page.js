/* Renders the climate analysis from data/climate.json into [data-climate] containers. */
(async () => {
  'use strict';
  const hosts = [...document.querySelectorAll('[data-climate]')];
  if (!hosts.length) return;
  const C = window.KaurCharts, { fmt, sgn } = C;
  let d;
  try {
    const res = await fetch('data/climate.json', { cache: 'no-cache' });
    if (!res.ok) throw new Error(res.status);
    d = await res.json();
  } catch (e) {
    for (const h of hosts) h.innerHTML = '<p class="viz-note">Kliimaanalüüsi andmed pole hetkel saadaval.</p>';
    return;
  }
  const T = d.temperature, P = d.precipitation, A = T.annual, stName = Object.fromEntries(d.stations.map((s) => [s.code, s.name]));
  const excl0 = (t) => t && t.lo !== null && (t.lo > 0 || t.hi < 0);
  const tr = (t, dec = 2, unit = '') => `${sgn(t.slope_per_decade, dec)}${unit ? ' ' + unit : ''} kümnendi kohta (95% vahemik ${fmt(t.lo, dec)} … ${fmt(t.hi, dec)}${unit ? ' ' + unit : ''})`;
  const last = (a) => a[a.length - 1];
  const seasonNames = { DJF: 'Talv (dets–veebr)', MAM: 'Kevad (märts–mai)', JJA: 'Suvi (juuni–aug)', SON: 'Sügis (sept–nov)' };
  const stationTrends = T.station_trends.map((s) => ({ ...s, name: stName[s.code] })).filter((s) => s.slope_per_decade !== null).sort((a, b) => a.slope_per_decade - b.slope_per_decade);
  const allPositive = stationTrends.every((s) => s.lo > 0);
  const nPos = stationTrends.filter((s) => s.lo > 0).length;
  const pm = A.period_means;
  const top = A.top_years.slice(0, 3);
  const rob = T.robustness;

  const MONTHS = ['jaanuar', 'veebruar', 'märts', 'aprill', 'mai', 'juuni', 'juuli', 'august', 'september', 'oktoober', 'november', 'detsember'];
  const sigWord = (t) => (excl0(t) ? 'eristatav' : 'ei ole eristatav looduslikust kõikumisest');
  const forestItems = [{ label: 'Aasta', t: A.trend, strong: true }, ...Object.entries(T.seasonal).map(([k, b]) => ({ label: seasonNames[k].split(' ')[0], t: b.trend }))];

  const builders = {
    kpis(host) {
      const fd = d.extremes.FD;
      host.innerHTML = `<div class="kpis">
        <div class="kpi"><b>${sgn(A.trend.slope_per_decade, 2)} °C</b><span>aastakeskmine temperatuur kümnendi kohta, ${A.years[0]}–${last(A.years)}<br>95% vahemik ${fmt(A.trend.lo, 2)} … ${fmt(A.trend.hi, 2)}</span></div>
        <div class="kpi"><b>${top.map((t) => t[0]).join(', ')}</b><span>soojemad aastad (anomaalia ${top.map((t) => sgn(t[1], 1)).join(', ')} °C vs 1991–2020)</span></div>
        <div class="kpi"><b>${nPos}/${stationTrends.length}</b><span>jaama, kus trend on positiivne ja vahemik ei sisalda nulli</span></div>
        ${fd && fd.trend && fd.trend.slope_per_decade !== null ? `<div class="kpi"><b>${sgn(fd.trend.slope_per_decade, 1)} päeva</b><span>külmapäevi (Tmin &lt; 0 °C) kümnendi kohta<br>95% vahemik ${fmt(fd.trend.lo, 1)} … ${fmt(fd.trend.hi, 1)}</span></div>` : ''}
      </div>`;
    },
    annual(host) {
      C.annualBars(host, A, { title: 'Aastakeskmise õhutemperatuuri kõrvalekalle 1991–2020 normist', subtitle: `Eesti jaamade keskmine, ${A.years[0]}–${last(A.years)}. Iga tulp on aasta; kriips näitab, kuidas jaamad omavahel erinevad.`, unit: '°C', valueHead: 'Anomaalia °C', dec: 1, posLabel: 'Soojem kui norm', negLabel: 'Külmem kui norm', note: `Allikas: Keskkonnaagentuur / Ilmateenistus, avaandmed (f_kliima_kuu, õhutemperatuur ööpäeva keskmine), ${d.temperature.n_stations_with_normal} jaama normiga. Aeg UTC kuudes. Jaamade vahe ≠ mõõtemääramatus.` });
      C.punch(host, `Eesti aastakeskmine õhutemperatuur on ${A.years[0]}–${last(A.years)} soojenenud ${tr(A.trend, 2, '°C')}; kolm soojemat aastat on ${top.map((t) => t[0]).join(', ')}.`);
    },
    forest(host) {
      C.forest(host, forestItems, { title: 'Temperatuuri trend aastaajati', subtitle: 'Soojenemine kümnendi kohta (Theil–Sen), 95% vahemik 3-aastaste plokkide bootstrapist.', unit: '°C / 10 a', dec: 2, note: 'Lühike rida (35 aastat) ja suur aastatevaheline kõikumine, eriti talvel, teevad vahemikud laiaks. Vahemik, mis sisaldab nulli, ei tähenda trendi puudumist, vaid et seda pole selle rea põhjal eristatav.' });
    
      const seas = Object.entries(T.seasonal).map(([k, bl]) => ({ k, t: bl.trend }));
      const sig = seas.filter((x) => excl0(x.t)).map((x) => seasonNames[x.k].split(' ')[0].toLowerCase());
      C.punch(host, `Eristatav soojenemine on ${sig.length ? sig.join(' ja ') : 'ühelgi aastaajal'}; ülejäänud aastaajad jäävad lühikese rea ja suure kõikumise tõttu veapiiri sisse.`);
    },
    grid(host) {
      C.heatGrid(host, T.monthly_grid, { title: 'Kuude kaupa: millal soojenemine toimus?', subtitle: 'Riigi keskmine kuu anomaalia võrreldes sama kuu 1991–2020 normiga.', limit: 5, note: 'Iga lahter on riigi jaamade keskmine anomaalia (vähemalt 5 jaama). Skaala on sümmeetriline ±5 °C ja kärbitud.' });
    
      const cells = T.monthly_grid.cells, yrs = T.monthly_grid.years, y0 = yrs[0], y1 = last(yrs);
      const avg = (m, a, z) => { const v = cells.filter((c) => c[1] === m && c[0] >= a && c[0] <= z).map((c) => c[2]); return v.length ? v.reduce((x, y) => x + y, 0) / v.length : null; };
      const diffs = MONTHS.map((nm, i) => ({ nm, v: avg(i + 1, y1 - 14, y1) - avg(i + 1, y0, y0 + 14) })).filter((x) => Number.isFinite(x.v)).sort((a, b) => b.v - a.v);
      if (diffs.length) C.punch(host, `Kõige rohkem on soojenenud ${diffs[0].nm} (${sgn(diffs[0].v, 1)} °C: ${y1 - 14}–${y1} keskmine miinus ${y0}–${y0 + 14} keskmine), kõige vähem ${diffs[diffs.length - 1].nm} (${sgn(diffs[diffs.length - 1].v, 1)} °C). Kirjeldav võrdlus, ilma veahinnanguta.`);
    },
    stations(host) {
      C.stationDots(host, stationTrends, A.trend, { title: 'Kas soojenemine on ühtlane üle Eesti?', subtitle: 'Iga jaama aastakeskmise temperatuuri trend, aeglasemast kiiremani.', note: `${nPos} jaama ${stationTrends.length}-st näitab statistiliselt eristatavat soojenemist. Kasutatud on jaamad, millel on 1991–2020 normi jaoks vähemalt 25 aastat andmeid ja trendi jaoks vähemalt 10 täisaastat.` });
    
      C.punch(host, `${nPos} jaama ${stationTrends.length}-st näitab eristatavat soojenemist (kiirus ${fmt(stationTrends[0].slope_per_decade, 2)} … ${fmt(last(stationTrends).slope_per_decade, 2)} °C / 10 a); kiireim on ${last(stationTrends).name}, aeglaseim ${stationTrends[0].name}.`);
    },
    precip(host) {
      if (!P) return;
      C.annualBars(host, P.annual, { title: 'Aastane sademete summa protsendina 1991–2020 normist', subtitle: 'Riigi jaamade keskmine; 100% = norm.', unit: '%', valueHead: '% normist', dec: 0, baseline: 100, tipOffset: 0, posLabel: 'Märjem kui norm', negLabel: 'Kuivem kui norm', height: 260, note: 'Sademete mõõtmisel on teadaolev süstemaatiline alamõõtmine (tuul, lumi), seetõttu on usaldusväärsem aastate võrdlus, mitte absoluutne summa. Kriipsud: jaamade vahe.' });
    
      C.punch(host, `Aastased sademed muutuvad ${tr(P.annual.trend, 1, '%-punkti')}; trend ${sigWord(P.annual.trend)}.`);
    },
    precipForest(host) {
      if (!P) return;
      const items = [{ label: 'Aasta', t: P.annual.trend, strong: true }, ...Object.entries(P.seasonal).map(([k, b]) => ({ label: seasonNames[k].split(' ')[0], t: b.trend }))];
      C.forest(host, items, { title: 'Sademete trend: protsendipunkti kümnendi kohta', subtitle: 'Muutus normi %-des 10 aasta kohta.', unit: '%-punkti / 10 a', dec: 1, note: 'Vahemikud sisaldavad nulli: sademete trendi pole selle rea põhjal võimalik eristada looduslikust kõikumisest.' });
    
      const seasP = Object.entries(P.seasonal).filter(([, bl]) => excl0(bl.trend)).map(([k]) => seasonNames[k].split(' ')[0].toLowerCase());
      C.punch(host, seasP.length ? `Eristatav sademete trend on ainult aastaajal: ${seasP.join(', ')}.` : 'Ühelgi aastaajal ei ole sademete trend looduslikust kõikumisest eristatav.');
    },
    extremes(host) {
      const E = d.extremes, defs = [
        ['FD', 'Külmapäevad (Tmin < 0 °C)', 'päeva/a', 1, 'Mitu päeva aastas on päevane miinimum alla 0 °C.'],
        ['ID', 'Jäävad päevad (Tmax < 0 °C)', 'päeva/a', 1, 'Päevad, mil temperatuur ei tõuse üle 0 °C.'],
        ['SU25', 'Suvepäevad (Tmax ≥ 25 °C)', 'päeva/a', 1, 'Päevad, mil maksimum on vähemalt 25 °C.'],
        ['HD30', 'Kuumapäevad (Tmax ≥ 30 °C)', 'päeva/a', 2, 'Harv sündmus: paljudes jaamades 0 päeva, seetõttu on keskmine väike ja kõikuv.'],
        ['TR20', 'Troopilised ööd (Tmin ≥ 20 °C)', 'ööd/a', 2, 'Väga harv sündmus Eestis; vaata jaamade vahet.'],
        ['Rx1day', 'Aasta suurim ööpäevane sademe hulk', 'mm', 1, 'Aasta tugevaim sadu jaamas; järsult ebaühtlane.'],
      ];
      host.innerHTML = '<div class="panels"></div>';
      const grid = host.firstChild;
      for (const [k, title, unit, dec, sub] of defs) {
        if (!E[k] || !E[k].aasta) continue;
        const div = document.createElement('div');
        grid.appendChild(div);
        C.indexPanel(div, E[k], { title, unit, dec, subtitle: sub });
        const tt = E[k].trend;
        if (tt && tt.slope_per_decade !== null) C.punch(div, `${title.split(' (')[0]}: ${sgn(tt.slope_per_decade, dec)} ${unit} kümnendi kohta, ${sigWord(tt)}.`);
      }
    },
    coverage(host) {
      C.coverage(host, d.completeness, d.stations, { title: 'Andmete katvus: millised jaamad mõõtsid millal?', subtitle: 'Kuude arv aastas, millal jaamal on õhutemperatuuri väärtus.', note: 'Jaamavõrk ei ole stabiilne: osa jaamu alustas hiljem (Ruhnu 2003, Heltermaa 2007, Roomassaare 2008, Tooma 2009). Nende normi ei arvutata, kui baasperioodil on alla 25 aasta. Lüngad vähendavad riigi keskmise jaamade arvu konkreetsetel aastatel.' });
    
      const firstYear = {};
      for (const [code, yr] of d.completeness.cells) firstYear[code] = Math.min(firstYear[code] ?? 9999, yr);
      const late = Object.values(firstYear).filter((y) => y > d.completeness.years[0]).length;
      C.punch(host, `${late} jaama ${Object.keys(firstYear).length}-st alustas pärast ${d.completeness.years[0]}. aastat, seega jaamavõrk ei ole kogu perioodi jooksul konstantne.`);
    },
    findings(host) {
      const li = [];
      li.push(`<li><b>Soojenemine:</b> aastakeskmine õhutemperatuur on ${A.years[0]}–${last(A.years)} muutunud ${tr(A.trend, 2, '°C')}; ${excl0(A.trend) ? 'vahemik ei sisalda nulli' : 'vahemik sisaldab nulli'}. Kümnendite keskmised anomaaliad võrreldes 1991–2020 normiga: ${pm.map((q) => `${q.from}–${q.to}: ${sgn(q.mean, 2)} °C`).join('; ')}.</li>`);
      li.push(`<li><b>Ühtlus:</b> ${nPos} jaama ${stationTrends.length}-st annab statistiliselt eristatava soojenemise (trendid ${fmt(stationTrends[0].slope_per_decade, 2)} … ${fmt(last(stationTrends).slope_per_decade, 2)} °C / 10 a), ${allPositive ? 'seega signaal on ruumiliselt ühtlane' : 'kuid mitte kõigil'}.</li>`);
      const seas = Object.entries(T.seasonal).map(([k, b]) => ({ k, t: b.trend }));
      const sig = seas.filter((s) => excl0(s.t)).map((s) => seasonNames[s.k].split(' ')[0].toLowerCase());
      const non = seas.filter((s) => !excl0(s.t)).map((s) => seasonNames[s.k].split(' ')[0].toLowerCase());
      li.push(`<li><b>Aastaajad:</b> eristatav soojenemine: ${sig.join(', ') || 'ükski'}; ${non.length ? `vahemik sisaldab nulli: ${non.join(', ')} (lühike rida ja suur kõikumine)` : ''}.</li>`);
      if (rob) {
        const core = rob.core_stations_only, l20 = rob.last_20_years, b1 = rob.block_1, b5 = rob.block_5;
        li.push(`<li><b>Robustsus:</b> ainult täispikkade ridadega jaamadega (${core.n_stations}) on trend ${sgn(core.slope_per_decade, 2)} °C / 10 a (${fmt(core.lo, 2)} … ${fmt(core.hi, 2)}); vahemiku laius sõltub plokkide pikkusest (1–5 a) vähe (alumine piir ${fmt(Math.min(b1.lo, b5.lo), 2)}, ülemine ${fmt(Math.max(b1.hi, b5.hi), 2)}). Viimase 20 aasta trend on ${sgn(l20.slope_per_decade, 2)} °C / 10 a, kuid vahemik ${fmt(l20.lo, 2)} … ${fmt(l20.hi, 2)} on lai: kiirenemist selle põhjal väita ei saa.</li>`);
      }
      if (P) li.push(`<li><b>Sademed:</b> aastase summa trend ${tr(P.annual.trend, 1, '%-punkti')} – ${excl0(P.annual.trend) ? 'eristatav' : 'ei ole eristatav looduslikust kõikumisest'}.</li>`);
      const fd = d.extremes.FD;
      if (fd && fd.trend) li.push(`<li><b>Külmapäevad (Tmin &lt; 0 °C):</b> ${tr(fd.trend, 1, 'päeva aastas')} – ${excl0(fd.trend) ? 'külmapäevi on märgatavalt vähem' : 'muutus pole eristatav'}.</li>`);
      host.innerHTML = `<ul class="findings">${li.join('')}</ul>`;
    },
    methods(host) {
      const ch = d.checks.monthly_vs_daily_mean_temperature;
      host.innerHTML = `<div class="methods"><b>Andmed ja meetod</b> <span class="review-flag">valdkonnaekspert ülevaatamata</span>
        <p><b>Allikas ja päritolu:</b> Keskkonnaagentuuri avaandmed (keskkonnaandmed.envir.ee, tabelid f_kliima_kuu, f_kliima_paev, f_kliima_jaam_vaatlus): avaldatud vaatlused, kuu- ja ööpäevaagregaadid. Andmetabeli kirjeldus ei nimeta kvaliteedikontrolli ega homogeniseerimise taset, seega seda ei eeldata. Aasta, kuu ja päev on avaldatud kujul UTC-s, kohalikku aega ei ole teisendatud.</p>
        <p><b>Meetod:</b> norm WMO 1991–2020; jaama kuunorm nõuab vähemalt 25 aastat. Anomaaliad arvutatakse jaama kaupa ja keskmistatakse alles seejärel (jaamavõrgu muutus ei kalluta tulemust). Aasta ja aastaaeg loetakse ainult täis kuudega. Riiklik väärtus on jaamade lihtkeskmine (ilma pindala kaaluta). Hajuvuse kriipsud on jaamade vahe (10.–90. protsentiil), mitte mõõtemääramatus. Trend: Theil–Sen, 95% vahemik 3-aastaste plokkide bootstrapist. Äärmusnäitajad on loetud ainult aastatel, kus jaamal oli vähemalt 355 kehtivat päeva.</p>
        <p><b>Piirangud:</b> rida algab 1991, seega sajandipikkust muutust siit hinnata ei saa; ~35 aastat on lühike rida, mistõttu aastaaegade trendide vahemikud on laiad; jaamade valik ja asukohad on ebaühtlased; mõõtmise ja jaamade nihkeid ei ole korrigeeritud.</p>
        <p><b>Kontroll:</b> kuu keskmine temperatuur ühtib ööpäevaväärtuste keskmisega (${ch.station}, ${ch.months_compared} kuud, suurim vahe ${fmt(ch.max_abs_diff_degC, 2)} °C). Genereeritud ${d.meta.generated_utc.slice(0, 10)} (UTC).</p></div>`;
    },
  };
  for (const h of hosts) {
    const fn = builders[h.dataset.climate];
    if (fn) { try { fn(h); } catch (e) { h.innerHTML = '<p class="viz-note">Graafikut ei saanud joonistada.</p>'; console.error(e); } }
  }
})();
