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
      const w = CAP.filter((r) => r.CAP_I_WIND != null), a = first(w), b = last(w);
      C.punch(host, `Tuuleelektrijaamade paigaldatud võimsus kasvas ${fmt(a.CAP_I_WIND, 0)} MW-lt (${a.year}) ${fmt(b.CAP_I_WIND, 0)} MW-ni (${b.year}); soojuselektrijaamade paigaldatud elektrivõimsus on ${fmt(last(CAP).ELCAP_I_THRM, 0)} MW (${last(CAP).year}).`);
    },
    enmethods(host) {
      host.innerHTML = `<div class="methods"><b>Andmed ja meetod</b> <span class="review-flag">valdkonnaekspert ülevaatamata</span>
        <p><b>Allikas ja päritolu:</b> ${d.meta.source}; ametlik energiastatistika (energiabilanss Eurostati metoodikaga), mitte Keskkonnaagentuuri mõõtmine.</p>
        <p><b>Tõlgendus (kinnitamata):</b> ${d.meta.interpretation.join(' ')}</p>
        <p><b>Piirangud:</b> osakaalud on arvutatud bilansitoodete põhjal (ekspordi märk tuvastati samasusest, jääk ${(100 * d.signs.residual_share).toFixed(3)}%); ei ole ametlik taastuvenergia osakaal ega kasvuhoonegaaside inventuur. Genereeritud ${d.meta.generated_utc.slice(0, 10)} (UTC).</p></div>`;
    },
  };
  for (const h of hosts) {
    const b = builders[h.dataset.energy];
    if (b) b(h);
  }
})();
