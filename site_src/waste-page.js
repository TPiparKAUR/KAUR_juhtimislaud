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
    generation(host) {
      C.wasteGeneration(host, d);
      const g = flow('Jäätmeteke', last), ch = d.generation_by_chapter.filter((r) => r.aasta === last).sort((a, b) => b.tonnes - a.tonnes)[0];
      if (g && ch) C.punch(host, `Jäätmeteke on ${last}. aastal ${mt(g.tonnes)}; suurim peatükk on ${ch.pohigrupp} (${d.meta.chapter_labels_short[ch.pohigrupp] || ''}) ${fmt(100 * ch.tonnes / g.tonnes, 0)}% osakaaluga.`);
    },
    generationRest(host) {
      C.wasteGenerationRest(host, d);
      const rows = d.generation_by_chapter.filter((r) => r.aasta === last && r.pohigrupp !== '10').sort((a, b) => b.tonnes - a.tonnes), all = rows.reduce((a, r) => a + r.tonnes, 0);
      if (rows[0]) C.punch(host, `Ilma peatükita 10 on jäätmeteke ${mt(all)}; suurim on peatükk ${rows[0].pohigrupp} (${d.meta.chapter_labels_short[rows[0].pohigrupp] || ''}), ${fmt(100 * rows[0].tonnes / all, 0)}%.`);
    },
    flows(host) {
      C.wasteFlows(host, d);
      const a = flow('Taaskasutamine', last), l = flow('Ladestatud prügilasse', last);
      C.punch(host, a && l ? `${last}. aastal: taaskasutamine ${mt(a.tonnes)}, prügilasse ladestatud ${mt(l.tonnes)}. Voogusid ei liideta ega suhestata, sest nende kattuvus on teadmata.` : 'Iga vool on eraldi graafikul; voogusid ei liideta, sest nende kattuvus on teadmata.');
    },
    hazardous(host) {
      C.wasteHazardous(host, d);
      const h = d.hazardous_generation.find((r) => r.aasta === last);
      if (h && h.share != null) {
        const hs = d.hazardous_generation.filter((r) => r.share != null).sort((a, b) => a.aasta - b.aasta);
        const jump = hs.slice(1).map((r, i) => ({ y: r.aasta, dv: r.share - hs[i].share })).sort((a, b) => a.dv - b.dv)[0];
        C.punch(host, `Ohtlikuks märgitud osa on ${fmt(100 * h.share, 1)}% jäätmetekkest (${last})${jump && jump.dv < -0.15 ? `; suurim hüpe on ${jump.y}. aastal (${fmt(100 * jump.dv, 0)} protsendipunkti), mis viitab pigem märkimise või klassifikatsiooni muutusele kui ohu tegelikule vähenemisele (põhjus kinnitamata)` : ''}.`);
      }
    },
    top(host) {
      C.wasteTopTypes(host, d);
      const t = d.top_generation, all = flow('Jäätmeteke', last);
      if (t[0] && all) C.punch(host, `Suurim jäätmeliik on ${t[0].jaatmeliik_nimi} (${t[0].jaatmeliik}) ${fmt(100 * t[0].tonnes / all.tonnes, 0)}% jäätmetekkest (${last}).`);
    },
    trade(host) {
      C.wasteTrade(host, d, (key, by, keys) => {
        const tot = keys.map((k) => ({ k, v: [...by.get(k).values()].reduce((a, b) => a + b, 0) })).sort((a, b) => b.v - a.v);
        return tot[0] ? `${key === 'export_partners' ? 'Eksporti' : 'Importi'} on perioodil kokku kõige rohkem partneriga ${tot[0].k} (${fmt(tot[0].v / 1e3, 0)} kt kümne partneri hulgas).` : '';
      });
    },
    stocks(host) {
      C.wasteStocks(host, d);
      const r = d.stock_continuity.filter((x) => x.ratio != null);
      if (r.length) { const dev = r.map((x) => Math.abs(x.ratio - 1)).sort((a, b) => a - b); C.punch(host, `Lõpu- ja järgmise aasta algusladu lahknevus on mediaanis ${fmt(100 * dev[dev.length >> 1], 0)}% (suurim ${fmt(100 * dev[dev.length - 1], 0)}%): jäätmeandmete järjepidevus on piiratud.`); }
    },
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
