/* Renders the waste analysis from data/waste.json into [data-waste] hosts. */
(async () => {
  'use strict';
  const hosts = [...document.querySelectorAll('[data-waste]')];
  if (!hosts.length) return;
  const C = window.KaurCharts, { fmt } = C;
  let d;
  try {
    const res = await fetch('data/waste.json', { cache: 'no-cache' });
    if (!res.ok) throw new Error(res.status);
    d = await res.json();
  } catch (e) {
    for (const h of hosts) h.innerHTML = '<p class="viz-note">Jäätmeandmete analüüsi tulemused pole hetkel saadaval.</p>';
    return;
  }
  const years = d.meta.years, last = d.meta.latest_year, first = years[0];
  const flow = (f, y) => d.flows.find((r) => r.maht_liik === f && r.aasta === y);
  const mt = (t) => `${fmt(t / 1e6, 1)} Mt`;

  const builders = {
    findings(host) {
      const li = [];
      const f = d.meta.fetch || {};
      li.push(`<li><b>Mida see on:</b> riigi jäätmestatistika tabel (${first}–${last}), ${f.rows_read ? `${fmt(f.rows_read, 0)} rida loetud ja koondatud` : 'koondatud'}. Ühik on skeemis nimetamata ja <b>eeldatud tonnid</b>. Voogusid (teke, taaskasutus, ladestamine, eksport, laoseis jt) ei liideta, sest tabel ei ütle, kas need kattuvad.${f.count_mismatches && f.count_mismatches.length ? ` Märkus: ${f.count_mismatches.length} lõigu ridade arv ei kattunud serveri arvuga.` : ''}</li>`);
      const g0 = flow('Jäätmeteke', last - 1), g1 = flow('Jäätmeteke', last);
      if (g0 && g1) {
        const ch10 = (y) => d.generation_by_chapter.filter((r) => r.aasta === y && r.pohigrupp === '10').reduce((a, r) => a + r.tonnes, 0);
        li.push(`<li><b>Jäätmeteke:</b> ${mt(g0.tonnes)} (${last - 1}) → ${mt(g1.tonnes)} (${last}); peatükk 10 (termilised protsessid, sh põlevkivituhk) moodustab ${fmt(100 * ch10(last) / g1.tonnes, 0)}% ${last}. aasta kogusest, seega koguse muutust juhib suuresti energeetika. Ilma selleta: ${mt(g0.tonnes - ch10(last - 1))} → ${mt(g1.tonnes - ch10(last))}.</li>`);
        if (g1.negative_tonnes < 0) li.push(`<li><b>Negatiivsed väärtused:</b> jäätmetekke ridades on ${fmt(g1.negative_rows, 0)} negatiivset rida kokku ${fmt(g1.negative_tonnes / 1e3, 1)} kt (${last}). Põhjus on andmetest nähtamatu (parandused, ümberklassifitseerimine?); tulemused on netokogused.</li>`);
      }
      const r1 = flow('Taaskasutamine', last), l1 = flow('Ladestatud prügilasse', last);
      if (r1 && l1) li.push(`<li><b>Käitlus (${last}):</b> taaskasutamine ${mt(r1.tonnes)}, prügilasse ladestatud ${mt(l1.tonnes)}. Need on eraldi voogude kogused; nende suhet tekkega ei arvutata, sest kattuvus ja aruandjate koosseis on teadmata.</li>`);
      const h = d.hazardous_generation.find((r) => r.aasta === last);
      if (h && h.share != null) li.push(`<li><b>Ohtlikud jäätmed:</b> ${fmt(100 * h.share, 1)}% jäätmetekkest (${last}).</li>`);
      const sc = d.stock_continuity.filter((r) => r.ratio != null);
      if (sc.length) {
        const dev = sc.map((r) => Math.abs(r.ratio - 1)).sort((a, b) => a - b);
        li.push(`<li><b>Andmekvaliteet:</b> lõpu- ja järgmise aasta algusladu ühtivad mediaanis ${fmt(100 * dev[dev.length >> 1], 0)}% täpsusega (suurim kõrvalekalle ${fmt(100 * dev[dev.length - 1], 0)}%); lahknevus viitab aruandjate koosseisu muutusele või parandustele.</li>`);
      }
      host.innerHTML = `<ul class="findings">${li.join('')}</ul>`;
    },
    generation(host) { C.wasteGeneration(host, d); },
    generationRest(host) { C.wasteGenerationRest(host, d); },
    flows(host) { C.wasteFlows(host, d); },
    hazardous(host) { C.wasteHazardous(host, d); },
    top(host) { C.wasteTopTypes(host, d); },
    trade(host) { C.wasteTrade(host, d); },
    stocks(host) { C.wasteStocks(host, d); },
    methods(host) {
      const m = d.meta;
      host.innerHTML = `<div class="methods"><b>Andmed ja meetod</b> <span class="review-flag">valdkonnaekspert ülevaatamata</span>
        <p><b>Allikas ja päritolu:</b> Keskkonnaagentuuri avaandmed (keskkonnaandmed.envir.ee, tabel f_jaatmeliikumine_fix_riik, riigi jäätmearuandluse statistika). Tabel on aruandjate esitatud andmete põhjal koostatud statistika; kvaliteeditaset ei eeldata.</p>
        <p><b>Meetod:</b> tabeli read loeti serverist aasta, voo tüübi ja peatüki kaupa ning summeeriti; iga lõigu ridade arvu võrreldi serveri täpse arvuga. Summad on netokogused (negatiivsed väärtused on sees ja eraldi näidatud). Voo tüüpe ei liideta. Peatükkide lühendatud nimetused on kirjutatud selle lehe jaoks ja kontrollimata; koodid ja jäätmeliikide nimetused on andmetest.</p>
        <p><b>Piirangud:</b> ühik (eeldatud t) tuleb andmeomanikuga kinnitada; voogude seos (kattuvus) on kirjeldamata; viimase aasta andmed võivad olla täienemas; aruandjate koosseis ja klassifikatsioon on aja jooksul muutunud, seega pikad võrdlused on orienteerivad. Ettevõtteid ega käitisi ei nimetata, ainult koondid.</p>
        <p>Genereeritud ${m.generated_utc.slice(0, 10)} (UTC).</p></div>`;
    },
  };
  for (const h of hosts) {
    const fn = builders[h.dataset.waste];
    if (fn) { try { fn(h); } catch (e) { h.innerHTML = '<p class="viz-note">Graafikut ei saanud joonistada.</p>'; console.error(e); } }
  }
})();
