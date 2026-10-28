/* Renders material flow, waste vs GDP and circular material use charts from data/circular.json. */
(async () => {
  'use strict';
  const hosts = [...document.querySelectorAll('[data-circular]')];
  if (!hosts.length) return;
  const C = window.KaurCharts, { fmt, SLOTS, GREY } = C;
  let d;
  try {
    const res = await fetch('data/circular.json', { cache: 'no-cache' });
    if (!res.ok) throw new Error(res.status);
    d = await res.json();
  } catch (e) {
    for (const h of hosts) h.innerHTML = '<p class="viz-note">Ringmajanduse analüüsi tulemused pole hetkel saadaval.</p>';
    return;
  }
  const first = (a) => a[0], last = (a) => a[a.length - 1];
  const Mt = (t) => `${fmt(t / 1e6, 1)} Mt`;
  const W = d.waste, DC = d.decoupling.years, MAT = d.materials.filter((r) => r.dmc != null), CMU = d.cmu.filter((r) => r.ee != null);
  const share = (a, b) => (b ? (100 * a) / b : null);

  const builders = {
    cfindings(host) {
      const li = [], w = last(W), c = last(CMU), x = last(DC), m = last(MAT);
      li.push(`<li><b>Mida see on:</b> Statistikaameti materjalivoo arvepidamine (DMC, ressursitootlikkus), jäätmebilanss ja SKP (aheldatud väärtus, 2020. aasta hindades) ning Eurostati ringleva materjali määr. Jäätmed on eeldatud tonnides (tabelis ühikut ei ole). Ametlik statistika, mitte Keskkonnaagentuuri mõõtmine; litsents ja viitamise nõue on kinnitamata.</li>`);
      li.push(`<li><b>Jäätmeteke ${w.year}:</b> ${Mt(w.generated)}, millest ${fmt(share(w.mining_energy, w.generated), 0)}% on mäetööstuse (jäätmenimistu peatükk 01) ja termiliste protsesside (peatükk 10) jäätmed; ilma nendeta ${Mt(w.generated_other)}.</li>`);
      li.push(`<li><b>Lahtisidumine (${DC[0].year} = 100, viimane ${x.year}):</b> reaalne SKP ${fmt(x.gdp, 0)}, kodumaine materjalitarbimine (DMC) ${fmt(x.dmc, 0)}, jäätmeteke kokku ${fmt(x.waste, 0)}, jäätmeteke ilma peatükkideta 01 ja 10 ${fmt(x.waste_other, 0)}. Indeksite võrdlus on kirjeldav, mitte põhjuslik.</li>`);
      li.push(`<li><b>Ringleva materjali määr (Eurostat):</b> Eesti ${fmt(c.ee, 1)}% (${c.year}), EL27 ${c.eu != null ? `${fmt(c.eu, 1)}%` : 'andmeid ei ole'}; Eesti ${fmt(first(CMU).ee, 1)}% (${first(CMU).year}) → ${fmt(c.ee, 1)}%. Määr on Eurostati arvutatud ega ole siin tuletatud.</li>`);
      li.push(`<li><b>Ressursitootlikkus:</b> ${fmt(first(MAT).resource_productivity, 2)} (${first(MAT).year}) → ${fmt(m.resource_productivity, 2)} € DMC kilogrammi kohta (${m.year}); DMC ${fmt(m.dmc / 1000, 1)} Mt.</li>`);
      host.innerHTML = `<ul class="findings">${li.join('')}</ul>`;
    },
    cdecouple(host) {
      const mk = (label, color, key) => ({ label, color, data: DC.filter((r) => r[key] != null).map((r) => ({ year: r.year, value: r[key], n: 0, extra: '' })) });
      C.lines(host, { title: 'Majandus, materjalitarbimine ja jäätmeteke', subtitle: `Indeks, ${d.decoupling.base_year} = 100: reaalne SKP, kodumaine materjalitarbimine (DMC), jäätmeteke kokku ning ilma mäetööstuse ja termiliste protsesside jäätmeteta.`, unit: '', dec: 0, axisDec: 0, nName: '–',
        series: [mk('Reaalne SKP', SLOTS[0], 'gdp'), mk('DMC', SLOTS[2], 'dmc'), mk('Jäätmeteke kokku', GREY, 'waste'), mk('Jäätmeteke ilma 01 ja 10', SLOTS[3], 'waste_other')], ref: { value: 100, label: `${d.decoupling.base_year} = 100` },
        note: 'Indeksite võrdlus on kirjeldav: SKP struktuuri muutus, kaubandus ja jäätmete klassifikatsiooni muutus mõjutavad indekseid. Jäätmeteke sõltub mäetööstuse ja põlevkivisektori mahust, mis ei järgi SKP-d.' });
      const x = last(DC);
      C.punch(host, `${last(DC).year}. aastaks (${d.decoupling.base_year} = 100) on reaalne SKP ${fmt(x.gdp, 0)}, DMC ${fmt(x.dmc, 0)} ja jäätmeteke ilma peatükkideta 01 ja 10 ${fmt(x.waste_other, 0)}; ${x.dmc < x.gdp ? 'materjalitarbimine on kasvanud aeglasemalt kui SKP (suhteline lahtisidumine)' : 'materjalitarbimine on kasvanud vähemalt SKP-ga võrdselt'}, ${x.waste_other >= x.gdp - 5 ? 'kuid mäetööstuse ja termiliste protsesside jäätmeteta jäätmeteke on kasvanud ligikaudu SKP-ga sama tempoga' : 'ning mäetööstuse ja termiliste protsesside jäätmeteta jäätmeteke on kasvanud SKP-st aeglasemalt'}.`);
    },
    cwaste(host) {
      C.stackedBars(host, { years: W.map((r) => String(r.year)), scale: 1e6, unit: 'Mt', dec: 1, height: 300, noLabels: true,
        series: [{ key: 'm', label: 'Mäetööstus ja termilised protsessid (01, 10)', color: GREY, values: new Map(W.map((r) => [String(r.year), r.mining_energy])) }, { key: 'o', label: 'Muud jäätmed', color: SLOTS[1], values: new Map(W.map((r) => [String(r.year), r.generated_other])) }],
        title: 'Jäätmeteke Eestis', subtitle: 'Jäätmeteke (sh kogutud) jäätmenimistu peatükkide järgi, Mt aastas (eeldatud tonnid).', note: 'Peatükk 01 on mäetööstuse jäätmed ja peatükk 10 termiliste protsesside jäätmed; ülejäänud peatükid on koondatud „Muud jäätmed“. Eeldatud ühik: tonn.' });
      const a = first(W), b = last(W);
      C.punch(host, `Jäätmeteke oli ${Mt(a.generated)} (${a.year}) ja ${Mt(b.generated)} (${b.year}); mäetööstuse ning termiliste protsesside osa ${fmt(share(a.mining_energy, a.generated), 0)}% → ${fmt(share(b.mining_energy, b.generated), 0)}%, ülejäänud jäätmeid ${Mt(a.generated_other)} → ${Mt(b.generated_other)}.`);
    },
    crecovery(host) {
      const all = W.filter((r) => r.treated > 0).map((r) => ({ year: r.year, value: (100 * r.recovery) / r.treated, n: 0, extra: `taaskasutatud ${Mt(r.recovery)} / töödeldud ${Mt(r.treated)}` }));
      const other = W.filter((r) => r.treated - r.treated_mining_energy > 0).map((r) => ({ year: r.year, value: (100 * (r.recovery - r.recovery_mining_energy)) / (r.treated - r.treated_mining_energy), n: 0, extra: `ilma 01 ja 10` }));
      const lf = W.filter((r) => r.generated_other > 0).map((r) => ({ year: r.year, value: (100 * (r.landfilled - r.landfilled_mining_energy)) / r.generated_other, n: 0, extra: `ladestatud ${Mt(r.landfilled - r.landfilled_mining_energy)} / teke ${Mt(r.generated_other)}` }));
      C.lines(host, { title: 'Jäätmete taaskasutus ja ladestamine', subtitle: 'Taaskasutatud osa töödeldud jäätmetest (kõik jäätmed; ilma peatükkideta 01 ja 10) ning ladestatud jäätmed ilma peatükkideta 01 ja 10 jäätmetekke suhtes, %.', unit: '%', dec: 0, axisDec: 0, nName: '–',
        series: [{ label: 'Taaskasutus, kõik jäätmed', color: SLOTS[1], data: all }, { label: 'Taaskasutus, ilma 01 ja 10', color: SLOTS[0], data: other }, { label: 'Ladestatud, ilma 01 ja 10 (jäätmetekke suhtes)', color: SLOTS[3], data: lf }],
        note: 'Taaskasutus hõlmab kõiki taaskasutustoiminguid (energiakasutus ei ole eraldatav); aastas töödeldud kogus võib sisaldada varasemate aastate varusid ning ladestatud kogus ei ole sama, mis aastas tekkinud jäätmete ladestamine. Osakaal ei ole ELi ringlusmäär.' });
      const o = last(other), p = first(other);
      C.punch(host, `Taaskasutatud osa töödeldud jäätmetest (ilma peatükkideta 01 ja 10) oli ${fmt(p.value, 0)}% (${p.year}) ja ${fmt(o.value, 0)}% (${o.year}); ladestatud kogus ilma nende peatükkideta on ${fmt(last(lf).value, 0)}% jäätmetekkest (${last(lf).year}); see on tabelist arvutatud osakaal, mitte ELi ringlusmäär.`);
    },
    cmat(host) {
      const rp = MAT.filter((r) => r.resource_productivity != null).map((r) => ({ year: r.year, value: r.resource_productivity, n: r.dmc / 1000, extra: `DMC ${fmt(r.dmc / 1000, 1)} Mt` }));
      if (!rp.length) return;
      C.lines(host, { title: 'Ressursitootlikkus', subtitle: 'SKP (€) kodumaise materjalitarbimise (DMC) kilogrammi kohta; tooltipis DMC.', unit: '€/kg', dec: 2, axisDec: 1, nName: 'DMC, Mt', series: [{ label: 'Ressursitootlikkus', color: SLOTS[0], data: rp }],
        note: 'Ressursitootlikkus = SKP / DMC (Statistikaamet; hinnabaas on tabeli sisene, kinnitamata). DMC sisaldab kodumaist toorme kasutust ja füüsilist väliskaubanduse tasakaalu; mäetööstus (põlevkivi, ehitusmaterjalid) domineerib.' });
      const a = first(rp), b = last(rp);
      C.punch(host, `Ressursitootlikkus on ${fmt(a.value, 2)} (${a.year}) → ${fmt(b.value, 2)} € kg kohta (${b.year}); DMC ${fmt(first(MAT).dmc / 1000, 1)} → ${fmt(last(MAT).dmc / 1000, 1)} Mt, tulemus sõltub tugevalt põlevkivi ja ehitusmaterjalide mahust.`);
    },
    ccmu(host) {
      const ee = CMU.map((r) => ({ year: r.year, value: r.ee, n: 0, extra: '' })), eu = d.cmu.filter((r) => r.eu != null).map((r) => ({ year: r.year, value: r.eu, n: 0, extra: '' }));
      C.lines(host, { title: 'Ringleva materjali määr', subtitle: 'Ringleva materjali osakaal kogu materjalikasutusest, % (Eurostat, cei_srm030).', unit: '%', dec: 1, axisDec: 0, nName: '–', series: [{ label: 'Eesti', color: SLOTS[1], data: ee }, { label: 'EL27', color: GREY, data: eu }],
        note: 'Eurostati arvutatud näitaja: ringlusse võetud materjal / (kodumaine materjalikasutus + ringlusse võetud materjal). Eesti määr on mõjutatud põlevkivituha ja ehitus- ning mäetööstusjäätmete taaskasutusest; näitaja ei ole otse võrreldav Statistikaameti taaskasutuse osakaaluga.' });
      const l = last(CMU), el = last(d.cmu.filter((r) => r.eu != null));
      C.punch(host, `Ringleva materjali määr oli Eestis ${fmt(l.ee, 1)}% (${l.year}), EL27 keskmine ${fmt(el.eu, 1)}% (${el.year}); Eesti määr on tõusnud ${fmt(first(CMU).ee, 1)}%-lt (${first(CMU).year}).`);
    },
    cactivity(host) {
      const a = last(d.activity), rows = [...a.activities].sort((x, y) => y.value - x.value).slice(0, 9).map((r) => ({ name: r.name.replace(/^\.+/, ''), value: r.value / 1e6, note: `${fmt(share(r.value, a.total), 0)}% jäätmetekkest` }));
      C.natureBars(host, { rows, unit: 'Mt', fmt: (v) => fmt(v, 2), title: `Jäätmeteke tegevusala järgi (${a.year})`, subtitle: 'Jäätmeteke tegevusalade kaupa, Mt (eeldatud tonnid); 9 suurimat tegevusala.', color: SLOTS[2],
        note: 'Tabel KK068 on kahe aasta sammuga; tegevusalad võivad kattuda (nt „jäätmekäitlus“ sisaldab sekundaarjäätmeid), summat ei kontrollitud.' });
      const t = rows[0];
      C.punch(host, `Suurim jäätmetekitaja ${a.year}. aastal on ${t.name.toLowerCase()} (${fmt(t.value, 1)} Mt, ${t.note}); kümme suurimat tegevusala annavad kokku ${fmt(share(rows.reduce((s, r) => s + r.value * 1e6, 0), a.total), 0)}% jäätmetekkest.`);
    },
    cmethods(host) {
      host.innerHTML = `<div class="methods"><b>Andmed ja meetod</b> <span class="review-flag">valdkonnaekspert ülevaatamata</span>
        <p><b>Allikas ja päritolu:</b> ${d.meta.source}; ametlik statistika (mitte Keskkonnaagentuuri mõõtmine).</p>
        <p><b>Tõlgendus (kinnitamata):</b> ${d.meta.interpretation.join(' ')}</p>
        <p><b>Piirangud:</b> ringlusmäära ega lahtisidumist ei ole siin ise arvutatud ametliku meetodiga; jäätmete ühik on eeldatud. Genereeritud ${d.meta.generated_utc.slice(0, 10)} (UTC).</p></div>`;
    },
  };
  for (const h of hosts) {
    const b = builders[h.dataset.circular];
    if (b) b(h);
  }
})();
