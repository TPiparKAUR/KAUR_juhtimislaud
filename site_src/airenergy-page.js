/* Renders the air-emission and energy analysis from data/airenergy.json into [data-airenergy] hosts. */
(async () => {
  'use strict';
  const hosts = [...document.querySelectorAll('[data-airenergy]')];
  if (!hosts.length) return;
  const C = window.KaurCharts, { fmt } = C;
  let d;
  try {
    const res = await fetch('data/airenergy.json', { cache: 'no-cache' });
    if (!res.ok) throw new Error(res.status);
    d = await res.json();
  } catch (e) {
    for (const h of hosts) h.innerHTML = '<p class="viz-note">Õhuheite ja energia analüüsi andmed pole hetkel saadaval.</p>';
    return;
  }
  const years = d.meta.years, first = years[0], last = years[years.length - 1];
  const tot = (rows, grp, y) => rows.filter((r) => r.aine_stat_grupp === grp && r.aruanne_aasta === y).reduce((a, r) => a + r.tonnes, 0);
  const reports = (y) => (d.coverage.find((r) => r.aruanne_aasta === y) || {}).reports;
  const gap = (grp, y) => (d.sensitivity.find((r) => r.aine_stat_grupp === grp && r.aruanne_aasta === y) || {}).gap_share;

  const builders = {
    findings(host) {
      const li = [];
      li.push(`<li><b>Mida see on:</b> asutuste endi deklareeritud aastaaruanded (${first}–${last}); <b>mitte</b> riiklik heitkoguste inventuur ega kogu riigi heide. Aruannete arv on ${reports(first)} → ${reports(last)}, seega koosseis muutub.</li>`);
      const c0 = tot(d.co2, 'CO2', first), c1 = tot(d.co2, 'CO2', last);
      const peak = years.map((y) => [y, tot(d.co2, 'CO2', y)]).sort((a, b) => b[1] - a[1])[0];
      li.push(`<li><b>Fossiilne CO₂:</b> ${fmt(c0 / 1e6, 1)} Mt (${first}) → ${fmt(c1 / 1e6, 1)} Mt (${last}); maksimum ${peak[0]} (${fmt(peak[1] / 1e6, 1)} Mt). Langus on osaliselt aruandjate koosseisu muutus, mitte ainult heite vähenemine – seda ei saa eraldada ilma käitise tasandi võrdlusrühmata.</li>`);
      const unk = years.map((y) => { const t = d.ets.filter((r) => r.aruanne_aasta === y); const all = t.reduce((x, r) => x + r.tonnes, 0); return [y, all ? t.filter((r) => r.ets === 'teadmata').reduce((x, r) => x + r.tonnes, 0) / all : 0]; });
      const bad = unk.filter(([, v]) => v > 0.2);
      if (bad.length) li.push(`<li><b>ETS-jaotus:</b> ETS-staatus puudub aastatel ${bad.map(([y, v]) => `${y} (${fmt(100 * v, 0)}% CO₂-st)`).join(', ')}; ETS ja mitte-ETS osa ei ole nende aastate vahel võrreldav.</li>`);
      const b0 = tot(d.co2, 'CO2 bio', first), b1 = tot(d.co2, 'CO2 bio', last);
      li.push(`<li><b>Biogeenne CO₂</b> (eraldi, ei liideta): ${fmt(b0 / 1e6, 1)} Mt → ${fmt(b1 / 1e6, 1)} Mt, muutus on fossiilsest oluliselt väiksem.</li>`);
      const k = d.concentration.CO2.find((r) => r.aruanne_aasta === last);
      if (k) li.push(`<li><b>Kontsentratsioon:</b> ${last}. aastal tuleb suurimalt 5 aruandelt ${fmt(100 * k.top5_share, 0)}% ja suurimalt 10-lt ${fmt(100 * k.top10_share, 0)}% fossiilsest CO₂-st (${k.reports} aruandest); aastate muutust juhivad seega üksikute suurkäitiste otsused.</li>`);
      const g = ['CO2', 'NO2', 'SO2'].map((a) => [a, Math.max(...years.map((y) => gap(a, y) ?? 0))]);
      const worst = g.filter(([, v]) => v > 0.1).map(([a, v]) => `${d.meta.pollutants[a] || a} kuni ${fmt(100 * v, 0)}%`);
      li.push(`<li><b>Andmete kordused:</b> kui samasuguse võtmega ridadest (aruanne, allikas, aine, kütus) loetakse ainult esimene, väheneb CO₂ summa ${fmt(100 * Math.min(...years.map((y) => gap('CO2', y) ?? 0)), 1)}–${fmt(100 * Math.max(...years.map((y) => gap('CO2', y) ?? 0)), 1)}%${worst.length ? `; suurem tundlikkus: ${worst.join(', ')}` : ''}. Tavatulemuses on read jäetud nii, nagu on esitatud.</li>`);
      const hq = d.meta.data_quality.heat;
      const big = [...hq.flagged_heat_by_year].sort((a, b) => b.heat - a.heat)[0];
      if (hq.flagged_rows && big) li.push(`<li><b>Soojatoodang:</b> ${hq.flagged_rows} rida (${fmt(100 * hq.flagged_rows / hq.rows, 1)}%) jäeti välja ebareaalse soojus/kütus suhte tõttu, suurima koguga ${big.aruanne_aasta}. aastal (${big.rows} rida) – tõenäoliselt ühiku- või sisestusviga. Ühik (MWh) on <b>eeldatud</b>, tuletatud kütuse energiasisalduse suhtest.</li>`);
      host.innerHTML = `<ul class="findings">${li.join('')}</ul>`;
    },
    efindings(host) {
      const li = [];
      const ht = d.energy.heat_total_mwh;
      if (!ht.length) { host.innerHTML = '<p class="viz-note">Soojatoodangu andmeid ei ole.</p>'; return; }
      const h0 = ht[0], h1 = ht[ht.length - 1];
      li.push(`<li><b>Mida see on:</b> käitajate deklareeritud soojus- ja elektritoodang (${first}–${last}), ühik <b>eeldatud</b> MWh; mitte riiklik energiabilanss. Deklareeritud soojus ${fmt(h0.heat / 1e6, 1)} TWh (${h0.year}) → ${fmt(h1.heat / 1e6, 1)} TWh (${h1.year}), aruannete arv ${reports(first)} → ${reports(last)}.</li>`);
      const fuel = (f, y) => d.energy.by_fuel.filter((r) => r.fuel === f && r.aruanne_aasta === y).reduce((a, r) => a + r.heat, 0);
      const names = [...new Set(d.energy.by_fuel.map((r) => r.fuel).filter(Boolean))];
      const jumps = names.map((f) => [f, fuel(f, first), fuel(f, years[1])]).filter(([, a, b]) => a > 5e5 && b > 0).map(([f, a, b]) => [f, b / a - 1, a, b]).sort((x, y) => x[1] - y[1]);
      if (jumps.length && jumps[0][1] < -0.5) li.push(`<li><b>Kontrolli vajav:</b> ${jumps[0][0].toLowerCase()} soojus ${fmt(jumps[0][2] / 1e6, 1)} → ${fmt(jumps[0][3] / 1e6, 1)} TWh aastate ${first} ja ${years[1]} vahel (${fmt(100 * jumps[0][1], 0)}%). Põhjust (sisestusviga, ühik, aruandjate koosseis) ei tea; enne järelduste tegemist tuleb andmeomanikuga üle kontrollida.</li>`);
      const L = d.energy.climate_link;
      if (L) li.push(`<li><b>Talv ja soojatoodang:</b> ${L.years.length} punkti, aruannete koosseis muutub – ainult orientiir, statistikut ei arvutata.</li>`);
      host.innerHTML = `<ul class="findings">${li.join('')}</ul>`;
    },
    co2(host) {
      C.co2Ets(host, d);
      const c0 = tot(d.co2, 'CO2', first), c1 = tot(d.co2, 'CO2', last);
      C.punch(host, `Fossiilne CO₂ aruannetes: ${fmt(c0 / 1e6, 1)} Mt (${first}) → ${fmt(c1 / 1e6, 1)} Mt (${last}); aruandeid ${reports(first)} → ${reports(last)}, seega osa langusest on koosseisu muutus.`);
    },
    bio(host) {
      C.co2Bio(host, d);
      const b0 = tot(d.co2, 'CO2 bio', first), b1 = tot(d.co2, 'CO2 bio', last);
      C.punch(host, `Biogeenne CO₂ püsib ${fmt(b1 / 1e6, 1)} Mt tasemel (${fmt(b0 / 1e6, 1)} Mt aastal ${first}); see on eraldi fossiilsest ega liitu sellega.`);
    },
    sectors(host) {
      const label = { CO2: 'fossiilsest CO₂-st', NO2: 'NOx-ist', NH3: 'NH₃-st' };
      C.aeSectors(host, d, (g) => {
        const rows = d.sectors[g].filter((r) => r.aruanne_aasta === last), all = rows.reduce((a, r) => a + r.tonnes, 0);
        const top = rows.slice().sort((a, b) => b.tonnes - a.tonnes)[0];
        return top ? `${d.meta.nfr_names[top.sector] || top.sector} (${top.sector}) annab ${fmt(100 * top.tonnes / all, 0)}% aruannete ${label[g] || g} aastal ${last}.` : '';
      });
    },
    pollutants(host) {
      C.aePollutants(host, d);
      const parts = Object.entries(d.meta.pollutants).map(([k, name]) => { const a = tot(d.pollutants, k, first), b = tot(d.pollutants, k, last); return a ? `${name.split(' ')[0]} ${fmt(100 * (b / a - 1), 0)}%` : null; }).filter(Boolean);
      C.punch(host, `Muutus ${first} → ${last}: ${parts.join(', ')}. Aruandjate koosseis muutub, seega need ei ole riigi heite muutused.`);
    },
    counties(host) {
      C.aeCounties(host, d, (g) => {
        const rows = d.counties[g].filter((r) => r.aruanne_aasta === last && r.county !== 'teadmata'), all = rows.reduce((a, r) => a + r.tonnes, 0);
        const top = rows.slice().sort((a, b) => b.tonnes - a.tonnes)[0];
        return top ? `${top.county.replace(' maakond', '')} annab ${fmt(100 * top.tonnes / all, 0)}% ${g === 'CO2' ? 'fossiilsest CO₂-st' : 'NOx-ist'} (${last}); suurkäitiste tõttu kajastab see asutuste, mitte elanike heidet.` : '';
      });
    },
    concentration(host) {
      C.aeConcentration(host, d, (g) => {
        const r = d.concentration[g].find((x) => x.aruanne_aasta === last);
        return r ? `${last}. aastal annavad 5 suurimat aruannet ${fmt(100 * r.top5_share, 0)}% ja 10 suurimat ${fmt(100 * r.top10_share, 0)}% summast (${r.reports} aruandest).` : '';
      });
    },
    sensitivity(host) {
      C.aeSensitivity(host, d);
      const worst = d.sensitivity.slice().sort((a, b) => (b.gap_share ?? 0) - (a.gap_share ?? 0))[0];
      if (worst) C.punch(host, `Sama võtmega ridade kordumine võib summat mõjutada kuni ${fmt(100 * worst.gap_share, 0)}% (${d.meta.pollutants[worst.aine_stat_grupp] || worst.aine_stat_grupp}, ${worst.aruanne_aasta}); CO₂ puhul kuni ${fmt(100 * Math.max(...d.sensitivity.filter((r) => r.aine_stat_grupp === 'CO2').map((r) => r.gap_share ?? 0)), 1)}%.`);
    },
    fuel(host) {
      C.aeFuel(host, d);
      const ht = d.energy.heat_total_mwh;
      if (ht.length) C.punch(host, ht.length > 1 ? `Deklareeritud soojatoodang on ${fmt(ht[0].heat / 1e6, 1)} TWh (${ht[0].year}) → ${fmt(ht[ht.length - 1].heat / 1e6, 1)} TWh (${ht[ht.length - 1].year}); ühik eeldatud MWh, aruandjate koosseis muutub.` : `Deklareeritud soojatoodang on ${fmt(ht[0].heat / 1e6, 1)} TWh (${ht[0].year}); ühik eeldatud MWh.`);
    },
    electricity(host) {
      C.aeElectricity(host, d);
      const byYear = {};
      for (const r of d.energy.by_fuel) byYear[r.aruanne_aasta] = (byYear[r.aruanne_aasta] || 0) + r.electricity;
      const ys = Object.keys(byYear).map(Number).sort((a, b) => a - b);
      if (ys.length) C.punch(host, ys.length > 1 ? `Deklareeritud elektritoodang on ${fmt(byYear[ys[0]] / 1e6, 1)} TWh (${ys[0]}) → ${fmt(byYear[ys[ys.length - 1]] / 1e6, 1)} TWh (${ys[ys.length - 1]}); see ei ole riigi elektritoodangu statistika.` : `Deklareeritud elektritoodang on ${fmt(byYear[ys[0]] / 1e6, 1)} TWh (${ys[0]}); see ei ole riigi elektritoodangu statistika.`);
    },
    heatclimate(host) {
      C.aeHeatClimate(host, d);
      const L = d.energy.climate_link;
      if (L) C.punch(host, `${L.years.length} punkti ei võimalda talve ja soojatoodangu seost hinnata; graafik on ainult orientiiriks.`);
    },
    methods(host) {
      const m = d.meta, hq = m.data_quality.heat;
      host.innerHTML = `<div class="methods"><b>Andmed ja meetod</b> <span class="review-flag">valdkonnaekspert ülevaatamata</span>
        <p><b>Allikas ja päritolu:</b> Keskkonnaagentuuri avaandmed (keskkonnaandmed.envir.ee, tabelid stat_t_heitkogus_allikas_curr ja t_soojatoodang_curr, KOTKAS). Tegu on käitajate deklareeritud aastaaruannetega; arvutusmeetodid on segatud (süsteemi arvutatud, arvutatud, mõõdetud). Kvaliteeditaset andmetes ei ole ja seda ei eeldata.</p>
        <p><b>Meetod:</b> kogused teisendatud tonnideks (allikas t/kg/mg); fossiilne ja biogeenne CO₂ on eraldi ainegrupid ning neid ei liideta; kütuse kogust heitetabelist ei summeerita (kordub aine ridades). ${m.data_quality.emissions.rows_unknown_unit} tundmatu ühikuga rida jäeti välja. Soojus ja elekter liidetakse ridade kaupa, ühik on <b>eeldatud</b> MWh (tabeli skeemis puudub; tuletatud soojus/kütus suhtest). Välja jäetud read: soojus/kütus suhe väljaspool 0,1–10× kütuse mediaanist või soojus kütuseta (${hq.flagged_rows} rida).</p>
        <p><b>Piirangud:</b> aruandjate koosseis muutub aastati, seega kogused ei ole konstantse populatsiooni aegrida; ainult 2019–2025, seega pikaajalist trendi ega olulisust ei hinnata; sama võtmega ridu on jäetud nii, nagu need esitati (tundlikkus on näidatud eraldi); ETS-staatus puudub osal aruannetest; käitisi ega ettevõtteid ei nimetata ega salvestata, ainult koondid; sektorinimed on NFR-klassifikaatori lühendid ja kontrollimata.</p>
        <p>Genereeritud ${m.generated_utc.slice(0, 10)} (UTC).</p></div>`;
    },
  };
  for (const h of hosts) {
    const fn = builders[h.dataset.airenergy];
    if (fn) { try { fn(h); } catch (e) { h.innerHTML = '<p class="viz-note">Graafikut ei saanud joonistada.</p>'; console.error(e); } }
  }
})();
