/* Renders the energy balance, electricity and capacity charts from data/energy.json. */
(async () => {
  'use strict';
  const hosts = [...document.querySelectorAll('[data-energy]')];
  if (!hosts.length) return;
  const C = window.KaurCharts, { fmt, SLOTS, GREY } = C;
  let d;
  try {
    const res = await fetch('data/energy.json', { cache: 'no-cache' });
    if (!res.ok) throw new Error(res.status);
    d = await res.json();
  } catch (e) {
    for (const h of hosts) h.innerHTML = '<p class="viz-note">Energiastatistika tulemused pole hetkel saadaval.</p>';
    return;
  }
  const first = (a) => a[0], last = (a) => a[a.length - 1];
  const sgn = (v, n = 0) => `${v >= 0 ? '+' : '−'}${fmt(Math.abs(v), n)}`;
  const pj = (tj) => `${fmt(tj / 1000, 0)} PJ`;
  const B = d.balance.filter((r) => r.gae), P = d.production, R = d.renewable_gae, F = d.final, E = d.electricity, CAP = d.capacity;
  const at = (rows, y) => rows.find((r) => r.year === y);
  const yrs = (rows) => rows.map((r) => String(r.year));
  const PCOL = { 'Põlevkivi': SLOTS[3], Turvas: GREY, 'Biomass ja biogaas': SLOTS[1], 'Tuul, päike, hüdro': SLOTS[0], Muu: '#c9ced4' };

  const stack = (host, rows, keys, o) => C.stackedBars(host, { years: yrs(rows), scale: o.scale, unit: o.unit, dec: o.dec ?? 0, height: o.height || 300, noLabels: true,
    series: keys.map((k, i) => ({ key: k, label: k, color: (o.colors && o.colors[k]) || SLOTS[i % SLOTS.length], values: new Map(rows.map((r) => [String(r.year), r[k] || 0])) })), title: o.title, subtitle: o.subtitle, note: o.note });

  const builders = {
    enfindings(host) {
      const li = [], l = last(B), f = first(B), r = last(R), lp = last(P), fe = last(E);
      li.push(`<li><b>Mida see on:</b> Statistikaameti energiabilanss (Eurostati metoodika, TJ) ${f.year}–${l.year}, elektrijaamade toodang ja võimsused. Need on ametlikud statistilised andmed, mitte Keskkonnaagentuuri mõõtmised; osakaalud on siin <b>bilansist arvutatud</b> ega ole ametlikud SHARES-osakaalud. Litsents ja viitamise nõue on kinnitamata.</li>`);
      li.push(`<li><b>Taastuvate osakaal energiabilansi kogu energiaressursis (GAE):</b> ${fmt(first(R).share_pct, 0)}% (${first(R).year}) → ${fmt(r.share_pct, 0)}% (${r.year}); primaarenergia tootmises ${fmt(100 * lp.renewable / lp.total, 0)}% (${lp.year}).</li>`);
      li.push(`<li><b>Energiasõltuvus (netoimport / GAE):</b> ${fmt(l.dependency_pct, 1)}% (${l.year}); ${fmt(Math.min(...B.filter((x) => x.year >= l.year - 9).map((x) => x.dependency_pct)), 1)}–${fmt(Math.max(...B.filter((x) => x.year >= l.year - 9).map((x) => x.dependency_pct)), 1)}% viimase kümne aasta jooksul; elektri- ja soojuskaubandus on netona sees.</li>`);
      li.push(`<li><b>Elektritootmine (${fe.year}):</b> ${fmt(fe.total / 1000, 1)} TWh, taastuvate osakaal ${fmt(fe.renewable_share_pct, 0)}%; põlevkivi ${fmt(100 * fe['Põlevkivi ja põlevkiviproduktid'] / fe.total, 0)}%. Viimane aasta võib olla esialgne.</li>`);
      host.innerHTML = `<ul class="findings">${li.join('')}</ul>`;
    },
    enprod(host) {
      const keys = ['Põlevkivi', 'Turvas', 'Biomass ja biogaas', 'Tuul, päike, hüdro', 'Muu'];
      stack(host, P, keys, { scale: 1000, unit: 'PJ', colors: PCOL, title: 'Primaarenergia tootmine Eestis', subtitle: 'Energiabilansi primaarenergia tootmine toodete rühmade kaupa, PJ aastas (1 PJ = 1000 TJ).', note: 'Põlevkivi, turvas, biomass (sh biogaas, taastuvast toorainest olmejäätmed ja vedelad biokütused), tuul-päike-hüdro; „Muu“ on jääk kogu tootmisest. Primaarenergia ei ole lõpptarbimine.' });
      const a = first(P), b = last(P), pk = (r) => 100 * r['Põlevkivi'] / r.total;
      C.punch(host, `Põlevkivi osa primaarenergia tootmises langes ${fmt(pk(a), 0)}%-lt (${a.year}) ${fmt(pk(b), 0)}%-ni (${b.year}), biomass ja biogaas on ${fmt(100 * b['Biomass ja biogaas'] / b.total, 0)}% ja tuul-päike-hüdro ${fmt(100 * b['Tuul, päike, hüdro'] / b.total, 0)}% (${b.year}); kogutootmine ${pj(a.total)} → ${pj(b.total)}.`);
    },
    endep(host) {
      const dep = { label: 'Energiasõltuvus (netoimport / GAE)', color: SLOTS[2], data: B.filter((r) => r.dependency_pct != null).map((r) => ({ year: r.year, value: r.dependency_pct, n: r.gae / 1000, extra: `netoimport ${pj(r.net_imports)}, GAE ${pj(r.gae)}` })) };
      const ren = { label: 'Taastuvate osakaal GAE-s', color: SLOTS[1], data: R.map((r) => ({ year: r.year, value: r.share_pct, n: r.total_tj / 1000, extra: `taastuvad ${pj(r.renewable_tj)}, GAE ${pj(r.total_tj)}` })) };
      C.lines(host, { title: 'Energiasõltuvus ja taastuvate osakaal', subtitle: 'Energiabilansist arvutatud, % kogu energiaressursist (GAE).', unit: '%', dec: 1, axisDec: 0, nName: 'GAE, PJ', series: [dep, ren],
        note: 'Energiasõltuvus = (import − eksport) / GAE, negatiivne väärtus tähendab netoeksporti. Taastuvate osakaal on arvutatud bilansitoodetest (hüdro, tuul, päike, biokütused, biogaas, taastuvast toorainest olmejäätmed) ja ei ole ametlik SHARES-osakaal; elektri- ja soojuskaubanduse saldo on GAE-s sees.' });
      const l = last(B), r = last(R), a = first(R);
      C.punch(host, `Taastuvate osakaal energiabilansi GAE-s tõusis ${fmt(a.share_pct, 0)}%-lt (${a.year}) ${fmt(r.share_pct, 0)}%-ni (${r.year}); energiasõltuvus oli ${fmt(l.dependency_pct, 1)}% (${l.year}) ja kõikus aastati ${fmt(Math.min(...B.map((x) => x.dependency_pct)), 0)}–${fmt(Math.max(...B.map((x) => x.dependency_pct)), 0)}% (kogu periood), osalt elektrikaubanduse tõttu.`);
    },
    enfinal(host) {
      const keys = ['Tööstus', 'Transport', 'Kodumajapidamised', 'Äri- ja avalik sektor'];
      stack(host, F, keys, { scale: 1000, unit: 'PJ', title: 'Energia lõpptarbimine sektorite kaupa', subtitle: 'Tegelik lõpptarbimine (Eurostati bilanss), PJ aastas; põllumajandus, kalandus ja muud sektorid ei ole eraldi näidatud.', note: 'Sektorite summa ei pruugi võrduda kogu lõpptarbimisega (põllumajandus-, kalandus- ja liigitamata sektorid puuduvad); tööstus ei sisalda tooraineks tarbitut.' });
      const a = first(F), b = last(F), sh = (r, k) => 100 * r[k] / r.total;
      C.punch(host, `Transpordi osa lõpptarbimises on ${fmt(sh(b, 'Transport'), 0)}% (${b.year}; ${fmt(sh(a, 'Transport'), 0)}% aastal ${a.year}), kodumajapidamiste osa ${fmt(sh(b, 'Kodumajapidamised'), 0)}% (${fmt(sh(a, 'Kodumajapidamised'), 0)}%); lõpptarbimine ${pj(a.total)} → ${pj(b.total)}.`);
    },
    enelec(host) {
      const keys = ['Põlevkivi ja põlevkiviproduktid', 'Maagaas', 'Biomass, biogaas, muu taastuv', 'Hüdro', 'Tuul', 'Päike', 'Muu'];
      const colors = { 'Põlevkivi ja põlevkiviproduktid': SLOTS[3], Maagaas: GREY, 'Biomass, biogaas, muu taastuv': SLOTS[1], 'Hüdro': SLOTS[4] || SLOTS[0], Tuul: SLOTS[0], 'Päike': SLOTS[2], Muu: '#c9ced4' };
      stack(host, E, keys, { scale: 1000, unit: 'TWh', dec: 1, colors, title: 'Elektritootmine kütuse ja allika järgi', subtitle: 'Kõikide elektrijaamade toodetud elektrienergia, TWh aastas (Statistikaamet, KE033).', note: 'Elektri tootmine, mitte tarbimine: import ja eksport ei ole sees. Jäätmekütus ei ole taastuvaks arvatud (taastuv osa pole tabelis eraldatud) ja kuulub „Muu“ alla; viimane aasta võib olla esialgne.' });
      const a = at(E, 2010) || first(E), b = last(E);
      C.punch(host, `Taastuvate osakaal elektritootmises oli ${fmt(a.renewable_share_pct, 0)}% (${a.year}) ja ${fmt(b.renewable_share_pct, 0)}% (${b.year}), samal ajal kui põlevkivi osa langes ${fmt(100 * a['Põlevkivi ja põlevkiviproduktid'] / a.total, 0)}%-lt ${fmt(100 * b['Põlevkivi ja põlevkiviproduktid'] / b.total, 0)}%-ni ja kogutoodang ${fmt(a.total / 1000, 1)} → ${fmt(b.total / 1000, 1)} TWh; tuule ja päikese osa elektritootmises on ${fmt(100 * (b.Tuul + b['Päike']) / b.total, 0)}% (${b.year}).`);
    },
    encap(host) {
      const mk = (code, label, color) => ({ label, color, data: CAP.filter((r) => r[code] != null).map((r) => ({ year: r.year, value: r[code], n: 0, extra: '' })) });
      C.lines(host, { title: 'Elektrijaamade paigaldatud võimsus', subtitle: 'Paigaldatud elektrivõimsus, MW (kõik elektrijaamad); soojuselektrijaamad, tuule- ja hüdroelektrijaamad.', unit: 'MW', dec: 0, axisDec: 0, nName: '–', series: [mk('ELCAP_I_THRM', 'Soojuselektrijaamad', SLOTS[3]), mk('CAP_I_WIND', 'Tuuleelektrijaamad', SLOTS[0]), mk('CAP_I_HYDR', 'Hüdroelektrijaamad', SLOTS[4] || SLOTS[2])],
        note: 'Päikeseelektrijaamade võimsust tabelis KE032 ei ole. Paigaldatud võimsus ei ole tootmisvõime kättesaadavus; tuule võimsus on tootmisvõime nimivõimsus, mitte keskmine toodang.' });
      const w = CAP.filter((r) => r.CAP_I_WIND > 0), a = first(w), b = last(w);
      C.punch(host, `Tuuleelektrijaamade paigaldatud võimsus kasvas ${fmt(a.CAP_I_WIND, 0)} MW-lt (${a.year}, esimene aasta, mil võimsust on) ${fmt(b.CAP_I_WIND, 0)} MW-ni (${b.year}); soojuselektrijaamade paigaldatud elektrivõimsus on ${fmt(last(CAP).ELCAP_I_THRM, 0)} MW (${last(CAP).year}).`);
    },
    hchp(host) {
      const H = d.heat; if (!H) return;
      const mk = (code, label, color) => ({ label, color, data: H.chp.filter((r) => r[code] != null).map((r) => ({ year: r.year, value: r[code], n: 0, extra: '' })) });
      C.lines(host, { title: 'Koostootmisjaamade toodang', subtitle: 'Koostootmisjaamade toodetud soojus- ja elektrienergia, GWh aastas (Statistikaamet, KE034).', unit: 'GWh', dec: 0, axisDec: 0, nName: '–', series: [mk('PROD_H_CHP', 'Soojusenergia', SLOTS[3]), mk('PROD_E_CHP', 'Elektrienergia', SLOTS[0])],
        note: 'Koostootmisjaamade genereerimisseadmed kokku; aastad on tabelis puudu (nt 2003). Viimane aasta võib olla esialgne.' });
      const h = H.chp.filter((r) => r.PROD_H_CHP != null), a = at(h, 2010) || first(h), b = last(h);
      const t = last(H.chp), bt = Object.entries(t.heat_by_generator || {}).sort((x, y) => y[1] - x[1])[0];
      C.punch(host, `Koostootmisjaamade soojatoodang oli ${fmt(a.PROD_H_CHP, 0)} GWh (${a.year}) ja ${fmt(b.PROD_H_CHP, 0)} GWh (${b.year}); elektritoodang ${fmt(a.PROD_E_CHP, 0)} → ${fmt(b.PROD_E_CHP, 0)} GWh${bt ? `; ${t.year}. aastal toodab enim soojust seadmetüüp „${{ BP_TURB: 'vasturõhuauruturbiinid', SC_TURB: 'vaheltvõtuauru-kondensatsiooniturbiinid', INT_COMB: 'sisepõlemismootorid' }[bt[0]] || bt[0]}“ (${fmt(100 * bt[1] / t.PROD_H_CHP, 0)}%)` : ''}.`);
    },
    hfuel(host) {
      const H = d.heat; if (!H) return;
      const keys = ['Põlevkivi ja põlevkiviproduktid', 'Maagaas', 'Biomass ja biogaas', 'Kivisüsi ja turvas', 'Jäätmekütus', 'Muud taastuvad'];
      const colors = { 'Põlevkivi ja põlevkiviproduktid': SLOTS[3], Maagaas: GREY, 'Biomass ja biogaas': SLOTS[1], 'Kivisüsi ja turvas': '#6b7280', 'Jäätmekütus': SLOTS[2], 'Muud taastuvad': SLOTS[0] };
      const FU = H.fuels.filter((r) => r.output_to_fuel == null || r.output_to_fuel <= 1.2);
      if (!FU.length) { host.innerHTML = '<p class="viz-note">Koostootmisjaamade kütuse andmed on kõigil aastatel puudulikud.</p>'; return; }
      stack(host, FU, keys, { scale: 1000, unit: 'PJ', dec: 1, colors, title: 'Koostootmisjaamade kütus', subtitle: 'Koostootmisjaamades tarbitud kütuse energia kütuseliigi järgi, PJ aastas (Statistikaamet, KE035).', note: 'Taastuvaks on loetud biomass, biogaas ja muud taastuvad allikad; jäätmekütust ei loeta taastuvaks (taastuv osa ei ole tabelis eraldatud). Aastad, mil koostootmise kasulik toodang ületab kütuse energia (puudulikud kütuseandmed, nt enne 2011), on välja jäetud. Viimane aasta võib olla esialgne.' });
      const a = first(FU), b = last(FU);
      C.punch(host, `Taastuvate (biomass, biogaas, muud) osa koostootmisjaamade kütuses oli ${fmt(a.renewable_share_pct, 0)}% (${a.year}) ja ${fmt(b.renewable_share_pct, 0)}% (${b.year}); põlevkivi ja põlevkiviproduktide osa ${fmt(100 * a['Põlevkivi ja põlevkiviproduktid'] / a.total_tj, 0)}% → ${fmt(100 * b['Põlevkivi ja põlevkiviproduktid'] / b.total_tj, 0)}%, maagaasi osa ${b.year}. aastal ${fmt(100 * b['Maagaas'] / b.total_tj, 0)}% (${fmt(b.total_tj / 1000, 1)} PJ kokku).`);
    },
    hyear(host) {
      const H = d.heat; if (!H) return;
      const A = H.monthly.annual;
      const mk = (key, label, color) => ({ label, color, data: A.filter((r) => r[key] != null).map((r) => ({ year: r.year, value: r[key], n: 0, extra: '' })) });
      C.lines(host, { title: 'Soojus- ja elektrienergia toodang', subtitle: 'Kuise toodangu aastasumma (ainult täisaastad), GWh (Statistikaamet, KE20).', unit: 'GWh', dec: 0, axisDec: 0, nName: '–', series: [mk('heat_gwh', 'Soojusenergia', SLOTS[3]), mk('electricity_gwh', 'Elektrienergia', SLOTS[0])],
        note: 'KE20 on toodanguindeksi aluseks olev tootmine; ei ole jaotatud tootja tüübi järgi, seega ei ole võrreldav koostootmise tabeliga täpselt. Soojatoodang sõltub talvede külmusest (kütteperiood) ning ei ole kliimakorrigeeritud.' });
      const h = A.filter((r) => r.heat_gwh != null), a = first(h), b = last(h);
      const mn = h.reduce((x, r) => (r.heat_gwh < x.heat_gwh ? r : x), h[0]), mx = h.reduce((x, r) => (r.heat_gwh > x.heat_gwh ? r : x), h[0]);
      C.punch(host, `Soojatoodang oli ${fmt(a.heat_gwh, 0)} GWh (${a.year}) ja ${fmt(b.heat_gwh, 0)} GWh (${b.year}); vahemik ${fmt(mn.heat_gwh, 0)} (${mn.year}) kuni ${fmt(mx.heat_gwh, 0)} GWh (${mx.year}); elektritoodang ${fmt(a.electricity_gwh, 0)} → ${fmt(b.electricity_gwh, 0)} GWh, aastate muutus sõltub talvede külmusest ja elektrituru muutustest.`);
    },
    hmonth(host) {
      const H = d.heat; if (!H || !H.monthly.profile.length) return;
      const cols = [SLOTS[2], SLOTS[1], SLOTS[0]];
      const series = H.monthly.profile.map((p, i) => ({ label: String(p.year), color: cols[i % cols.length], data: p.months.map((v, m) => ({ year: m + 1, value: v, n: 0, extra: '' })) }));
      C.lines(host, { title: 'Soojatoodang kuude kaupa', subtitle: 'Kuine soojatoodang, GWh; kolm viimast täisaastat (x-telg: kuu number, 1 = jaanuar).', unit: 'GWh', dec: 0, axisDec: 0, nName: '–', series,
        note: 'Soojatoodang on tugevalt hooajaline (kütteperiood); kuude erinevus aastate vahel peegeldab ilma. Viimane kuu tabelis: ' + H.monthly.last_month + '.' });
      const p = last(H.monthly.profile), mx = Math.max(...p.months), mn = Math.min(...p.months);
      C.punch(host, `${p.year}. aastal oli soojatoodang suurim ${fmt(mx, 0)} GWh (kuu ${p.months.indexOf(mx) + 1}) ja väikseim ${fmt(mn, 0)} GWh (kuu ${p.months.indexOf(mn) + 1}); suurima ja väikseima kuu suhe ${fmt(mx / mn, 1)} korda.`);
    },
    enmethods(host) {
      host.innerHTML = `<div class="methods"><b>Andmed ja meetod</b> <span class="review-flag">valdkonnaekspert ülevaatamata</span>
        <p><b>Allikas ja päritolu:</b> ${d.meta.source}; ametlik energiastatistika (energiabilanss Eurostati metoodikaga), mitte Keskkonnaagentuuri mõõtmine.</p>
        <p><b>Tõlgendus (kinnitamata):</b> ${d.meta.interpretation.concat(d.heat ? d.heat.meta.interpretation : []).join(' ')}</p>
        <p><b>Piirangud:</b> osakaalud on arvutatud bilansitoodete põhjal (ekspordi märk tuvastati samasusest, jääk ${(100 * d.signs.residual_share).toFixed(3)}%); ei ole ametlik taastuvenergia osakaal ega kasvuhoonegaaside inventuur. Genereeritud ${d.meta.generated_utc.slice(0, 10)} (UTC).</p></div>`;
    },
  };
  for (const h of hosts) {
    const b = builders[h.dataset.energy];
    if (b) b(h);
  }
})();
