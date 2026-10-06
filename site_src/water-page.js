/* Renders the water-body status analysis from data/water.json into [data-water] hosts. */
(async () => {
  'use strict';
  const hosts = [...document.querySelectorAll('[data-water]')];
  if (!hosts.length) return;
  const C = window.KaurCharts, { fmt } = C;
  let d;
  try {
    const res = await fetch('data/water.json', { cache: 'no-cache' });
    if (!res.ok) throw new Error(res.status);
    d = await res.json();
  } catch (e) {
    for (const h of hosts) h.innerHTML = '<p class="viz-note">Veekogumite seisundi analüüsi tulemused pole hetkel saadaval.</p>';
    return;
  }
  const p = d.paired, base = d.meta.baseline_year, pr = d.pressures;
  const share = (a, b) => 100 * a / b;
  const big = Math.max(...d.by_year.map((r) => r.n)), full = d.by_year.filter((r) => r.n >= 0.7 * big), f0 = full[0], f1 = full[full.length - 1];
  const lastY = d.by_year[d.by_year.length - 1];
  const rng = p.later_years ? `${p.later_years.min}–${p.later_years.max}` : 'hilisem';
  const top = pr.by_sector[0], topImp = pr.by_impact[0];
  const gw = d.groundwater.years;

  const builders = {
    findings(host) {
      const li = [];
      li.push(`<li><b>Mida see on:</b> pinnaveekogumite (jõed, järved, rannikumeri) koondhinnang klassidena 1 (väga hea) – 5 (väga halb) Keskkonnaagentuuri avaandmetest; ${fmt(d.meta.status_bodies, 0)} veekogumit on vähemalt ühe hinnanguga. Koondhinnangu täpne koostis (ökoloogiline seisund või potentsiaal) on kinnitamata.</li>`);
      if (f0 && f1) li.push(`<li><b>Täielik hinnang (${f0.year}–${f1.year}):</b> hea või parem on ${fmt(100 * f0.share_good, 0)}% (${f0.year}) → ${fmt(100 * d.baseline_distribution.share_good, 0)}% (${base}) klassifitseeritud veekogumitest (n≈${fmt(d.baseline_distribution.classified, 0)}). Hilisemad aastad hindavad vaid osa veekogumeid, seega nende osakaalu ei saa riikliku aegreana võrrelda.</li>`);
      if (p.all.n) li.push(`<li><b>Samad veekogumid (paaritatud, n=${fmt(p.all.n, 0)}):</b> hea või parem ${fmt(share(p.all.good_before, p.all.n), 0)}% → ${fmt(share(p.all.good_after, p.all.n), 0)}% (${base} → viimane hinnang ${rng}); ${fmt(p.all.worsened, 0)} halvenes, ${fmt(p.all.improved, 0)} paranes. Järvedel on muutus järsem (${fmt(p.by_group['Järv'].good_before, 0)} → ${fmt(p.by_group['Järv'].good_after, 0)} hea hinnangut ${fmt(p.by_group['Järv'].n, 0)}-st); põhjus (meetod või tegelik seisund) on kinnitamata.</li>`);
      li.push(`<li><b>Eesmärgi saavutamine (${d.targets.year}):</b> ${fmt(d.targets.achieved, 0)} ${fmt(d.targets.flagged, 0)}-st märgitud eesmärgist on märgitud saavutatuks (${fmt(share(d.targets.achieved, d.targets.flagged), 0)}%).</li>`);
      if (top) li.push(`<li><b>Survetegurid:</b> ${fmt(pr.bodies_with_significant, 0)} ${fmt(pr.assessed_bodies, 0)}-st hinnatud kehtivast veekogumist on vähemalt üks oluline aktuaalne survetegur; sagedaseim põhjus on ${top.name.toLowerCase()} (${fmt(share(top.bodies, pr.assessed_bodies), 0)}%).</li>`);
      const y = Object.keys(gw);
      if (y.length) li.push(`<li><b>Põhjavesi:</b> ${y.map((k) => `${k}: ${fmt(100 * gw[k].counts[1] / gw[k].n, 0)}% heas seisundis (n=${gw[k].n})`).join('; ')}; kogumite hulgad ei kattu, seega muutust ei arvutata.</li>`);
      host.innerHTML = `<ul class="findings">${li.join('')}</ul>`;
    },
    status(host) {
      C.waterStatus(host, d);
      C.punch(host, f0 && f1 && f0 !== f1 ? `Täielikult hinnatud aastatel muutus hea või parema seisundi osakaal ${fmt(100 * f0.share_good, 0)}%-st (${f0.year}) ${fmt(100 * f1.share_good, 0)}%-ks (${f1.year}); hilisemad aastad hindavad vaid osa veekogumeid ja ${fmt(100 * lastY.share_good, 0)}% (${lastY.year}) ei ole sellega otse võrreldav.` : `Hinnatud veekogumite arv erineb aastati, seega osakaalud ei ole aegreana võrreldavad.`);
    },
    paired(host) {
      if (!p.all.n) return;
      C.waterPaired(host, d);
      C.punch(host, `Samadest ${fmt(p.all.n, 0)} veekogumist halvenes ${fmt(share(p.all.worsened, p.all.n), 0)}% ja paranes ${fmt(share(p.all.improved, p.all.n), 0)}%; järvedest halvenes ${fmt(share(p.by_group['Järv'].worsened, p.by_group['Järv'].n), 0)}%, mis viitab pigem hindamismeetodi muutusele kui tegelikule seisundile (põhjus kinnitamata).`);
    },
    sectors(host) {
      if (!top) return;
      C.waterBars(host, { rows: pr.by_sector, total: pr.assessed_bodies, title: 'Oluline survetegur sektori järgi', subtitle: `Osakaal ${fmt(pr.assessed_bodies, 0)}-st hinnatud kehtivast veekogumist, millel on vähemalt üks oluline aktuaalne survetegur selle sektori poolt.`, color: C.SLOTS[3],
        note: 'Veekogumil võib olla mitu survetegurit, seega osakaalud ei anna summaks 100%. „Teadmata“ tähendab, et põhjus on tabelis märkimata.' });
      const most = [...pr.by_sector].sort((a, b) => b.pressures - a.pressures)[0];
      C.punch(host, `Sagedaseim oluline survetegur on sektor „${top.name}“ (${fmt(share(top.bodies, pr.assessed_bodies), 0)}% hinnatud veekogumitest)${most.name !== top.name ? `; kõige rohkem üksikuid survetegureid annab „${most.name}“ (${fmt(most.pressures, 0)})` : ''}.`);
    },
    impacts(host) {
      if (!topImp) return;
      C.waterBars(host, { rows: pr.by_impact, total: pr.assessed_bodies, title: 'Oluline survetegur mõju liigi järgi', subtitle: 'Osakaal hinnatud kehtivatest veekogumitest.', color: C.SLOTS[1],
        note: 'Mõju liigid on tabeli hinnang_moju klassifikaator; veekogumil võib olla mitu mõju.' });
      const t = topImp;
      C.punch(host, `Kõige sagedasem oluline mõju on ${t.name.toLowerCase()} (${fmt(share(t.bodies, pr.assessed_bodies), 0)}% veekogumitest); toitainetega saastus puudutab ${fmt(share((pr.by_impact.find((x) => x.name === 'Saastus toitainetega') || { bodies: 0 }).bodies, pr.assessed_bodies), 0)}%.`);
    },
    groundwater(host) {
      if (!Object.keys(gw).length) return;
      C.waterGroundwater(host, d);
      const y = Object.keys(gw);
      C.punch(host, `${y.map((k) => `${k}. aastal oli ${fmt(100 * gw[k].counts[1] / gw[k].n, 0)}% põhjaveekogumitest heas seisundis (n=${gw[k].n})`).join(', ')}; kogumite hulgad ei kattu, seega ei ole see muutus.`);
    },
    methods(host) {
      const m = d.meta;
      host.innerHTML = `<div class="methods"><b>Andmed ja meetod</b> <span class="review-flag">valdkonnaekspert ülevaatamata</span>
        <p><b>Allikas ja päritolu:</b> Keskkonnaagentuuri avaandmed (keskkonnaandmed.envir.ee): veekogumite register, veekogumite seisundid, koormused (survetegurid) ja põhjaveekogumite seisundid. Andmed on hinnangud, mitte otsesed mõõtmised; kvaliteeditaset ei eeldata.</p>
        <p><b>Tõlgendus (kinnitamata):</b> ${m.interpretation.join(' ')}</p>
        <p><b>Meetod:</b> kasutati ainult kehtivaid ridu. Osakaalud on arvutatud klassifitseeritud veekogumite hulgast; paaritatud võrdlus võrdleb samu veekogumeid. Aggregeeritud tulemused; veekogumite nimesid ei avaldata. Üldlämmastiku ja -fosfori väärtusi ei kasutatud: andmeid on vähe (alla 8% ridadest) ja ühik on kinnitamata (üksikud väga suured väärtused).</p>
        <p><b>Piirangud:</b> hindamiskava ja piirväärtused muutuvad aja jooksul; hilisemate aastate valim ei ole juhuvalim; survetegurite olulisus on ekspertotsus. Genereeritud ${m.generated_utc.slice(0, 10)} (UTC).</p></div>`;
    },
  };
  for (const h of hosts) {
    const b = builders[h.dataset.water];
    if (b) b(h);
  }
})();
