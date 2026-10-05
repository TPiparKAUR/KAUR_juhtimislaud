/* Renders the forest-inventory (SMI) analysis from data/forest.json into [data-forest] hosts. */
(async () => {
  'use strict';
  const hosts = [...document.querySelectorAll('[data-forest]')];
  if (!hosts.length) return;
  const C = window.KaurCharts, { fmt, sgn } = C;
  const COL = C.FOREST_COLORS;
  let d;
  try {
    const res = await fetch('data/forest.json', { cache: 'no-cache' });
    if (!res.ok) throw new Error(res.status);
    d = await res.json();
  } catch (e) {
    for (const h of hosts) h.innerHTML = '<p class="viz-note">Metsainventuuri analüüsi andmed pole hetkel saadaval.</p>';
    return;
  }
  const N = d.national, last = (s) => s[s.length - 1], first = (s) => s[0];
  const pe = (e) => (e == null ? 'viga teadmata' : `±${fmt(100 * e, 1)}%`);
  const verdict = (c) => (c == null || c.distinguishable == null ? 'eristatavus teadmata' : c.distinguishable ? 'muutus ületab veapiiri' : 'muutus jääb veapiiri sisse');
  const chg = (c) => (c ? `${sgn(100 * c.pct, 1)}% aastatel ${c.from}–${c.to} (${verdict(c)})` : '');
  const mln = (v) => fmt(v / 1000, 1);
  const L = d.meta.latest_year;

  /* Largest change between first and last year across categories of a {name: series} object. */
  function changes(obj) {
    return Object.entries(obj).map(([k, s]) => {
      if (s.length < 2) return null;
      const a = first(s), b = last(s), diff = b.value - a.value;
      const half = a.err == null || b.err == null ? null : Math.hypot(a.value * a.err, b.value * b.err);
      return { name: k, a, b, diff, pct: a.value ? diff / a.value : null, ok: half == null ? null : Math.abs(diff) > half };
    }).filter(Boolean);
  }
  const catBars = (obj, names, pairColors) => Object.keys(obj).filter((k) => !names || names.includes(k)).map((k) => ({
    label: k,
    points: [first(obj[k]), last(obj[k])].map((r, i) => ({ name: String(r.year), color: pairColors[i], value: r.value, err: r.err })),
  }));
  const PAIR = [COL[2], COL[0]];
  /* True (and an explanatory note) when a breakdown has no data, instead of a broken chart. */
  const none = (host, obj, what) => {
    const ok = obj && (Array.isArray(obj) ? obj.length : Object.keys(obj).length);
    if (!ok) host.innerHTML = `<p class="viz-note">${what}: andmed puuduvad.</p>`;
    return !ok;
  };

  const builders = {
    findings(host) {
      const li = [];
      li.push(`<li><b>Mis see on:</b> riikliku statistilise metsainventuuri (SMI) valimipõhised <b>hinnangud</b> aastatest ${d.meta.years[0]}–${L}, igaüks koos suhtelise veaga. Näitajad on 5-aastase inventeerimisperioodi (raiel 3- ja 5-aastase) hinnangud, seega järjestikused aastad <b>kattuvad</b> ega ole sõltumatud.</li>`);
      const A = last(N.area), S = last(N.stock), I = last(N.increment);
      li.push(`<li><b>Pindala ja tagavara (${L}):</b> metsamaad ${fmt(A.value, 0)} tuhat ha (${pe(A.err)}), kasvavate puude tagavara ${mln(S.value)} mln m³ (${pe(S.err)}), ${fmt(last(N.stock_per_ha).value, 0)} m³/ha. Tagavara ${chg(d.changes.stock?.since_start)}.</li>`);
      const R = last(N.felling_to_increment_5y);
      li.push(`<li><b>Juurdekasv ja raie:</b> juurdekasv ${mln(I.value)} mln m³ aastas (${pe(I.err)}); SMI raiehinnang (5-a periood) ${mln(last(N.felling_5y).value)} mln m³ aastas, ehk ${fmt(100 * R.value, 0)}% juurdekasvust (${pe(R.err)}). SMI hinnang erineb raiedokumentide põhisest raiestatistikast ning neid ei tohi segada.</li>`);
      const D = last(N.deadwood_per_ha);
      li.push(`<li><b>Surnud puit:</b> kuivanud ja lamapuitu kokku ${fmt(D.value, 1)} m³/ha (${pe(D.err)}); muutus ${chg(d.changes.deadwood_per_ha?.since_start)}.</li>`);
      li.push(`<li><b>Usaldusväärsus:</b> kõigi ${fmt(d.errors.rows, 0)} avaldatud hinnangu suhtelise vea mediaan on ${fmt(100 * d.errors.quantiles.p50, 1)}%, ülemine kümnendik üle ${fmt(100 * d.errors.quantiles.p90, 0)}% ja ${fmt(100 * d.errors.share_over_50pct, 0)}% hinnangutest on ebatäpsemad kui ±50%. Väikeste rühmade (nt maakond × puuliik) hinnangutesse tuleb suhtuda ettevaatlikult.</li>`);
      host.innerHTML = `<ul class="findings">${li.join('')}</ul>`;
    },
    area(host) {
      const c = d.changes.area?.since_start;
      C.errLines(host, { title: 'Metsamaa pindala', subtitle: 'SMI hinnang koos veaga.', unit: 'tuhat ha', dec: 0, series: [{ label: 'Metsamaa', color: COL[2], data: N.area }], note: 'Metsamaa sisaldab ajutiselt metsata alasid. Vea vahemik on eeldatud 95% usaldusnivool (vt metoodikat).' });
      C.punch(host, `Metsamaad on ${L}. aastal ${fmt(last(N.area).value, 0)} tuhat ha (${pe(last(N.area).err)}); ${c ? `${sgn(100 * c.pct, 1)}% aastast ${c.from} – ${verdict(c)}` : ''}.`);
    },
    stock(host) {
      const c = d.changes.stock?.since_start, c10 = d.changes.stock?.last_10_years;
      C.errLines(host, { title: 'Kasvavate puude tagavara', subtitle: 'Kogutagavara koos veaga.', unit: 'tuhat m³', dec: 0, series: [{ label: 'Tagavara', color: COL[0], data: N.stock }], note: 'Tagavara on kogu metsamaa kasvavate puude maht. Hinnangud kattuvad 5-aastaste perioodidena.' });
      const peak = N.stock.reduce((a, r) => (r.value > a.value ? r : a), N.stock[0]), now = last(N.stock);
      const fromPeak = peak.year < now.year - 2 && peak.err != null && now.err != null ? { diff: now.value - peak.value, ok: Math.abs(now.value - peak.value) > Math.hypot(peak.value * peak.err, now.value * now.err) } : null;
      C.punch(host, `Tagavara on ${mln(now.value)} mln m³ (${pe(now.err)}); ${c ? `${sgn(100 * c.pct, 0)}% aastast ${c.from} (${verdict(c)})` : ''}${fromPeak ? `. Kõrgeim hinnang oli ${peak.year}. aastal (${mln(peak.value)} mln m³); sellest on ${sgn(100 * fromPeak.diff / peak.value, 1)}% (${fromPeak.ok ? 'ületab veapiiri' : 'jääb veapiiri sisse'})` : ''}.`);
    },
    perha(host) {
      C.errLines(host, { title: 'Hektaritagavara', subtitle: 'Keskmine kasvavate puude maht hektari kohta.', unit: 'm³/ha', dec: 0, series: [{ label: 'Hektaritagavara', color: COL[3], data: N.stock_per_ha }], height: 260 });
      const c = d.changes.stock_per_ha?.since_start;
      C.punch(host, `Keskmine hektaritagavara on ${fmt(last(N.stock_per_ha).value, 0)} m³/ha (${pe(last(N.stock_per_ha).err)})${c ? `, ${sgn(100 * c.pct, 0)}% aastast ${c.from} (${verdict(c)})` : ''}.`);
    },
    balance(host) {
      if (none(host, N.felling_to_increment_5y, 'Juurdekasv ja raie')) return;
      C.errLines(host, { title: 'Juurdekasv ja raie', subtitle: 'Aastane juurdekasv ja SMI raiehinnang (5-aastane periood).', unit: 'tuhat m³/a', dec: 0, zero: true, series: [{ label: 'Juurdekasv', color: COL[2], data: N.increment }, { label: 'Raie (SMI hinnang)', color: COL[1], data: N.felling_5y }], note: 'Raie on SMI hinnang proovitükkidelt ja erineb raiedokumentide põhisest statistikast. Juurdekasvu täpne definitsioon (kogu- või puhasjuurdekasv) on kinnitamata. Suhte vea arvutus eeldab sõltumatuid hinnanguid (ligikaudne).' });
      const R = N.felling_to_increment_5y, r = last(R);
      const under = R.filter((x) => x.err != null && x.value * (1 + x.err) < 1).length, over = R.filter((x) => x.err != null && x.value * (1 - x.err) > 1).length;
      C.punch(host, `Raie moodustab ${L}. aastal ${fmt(100 * r.value, 0)}% juurdekasvust (${pe(r.err)}); ${over ? `${over} aastal oli raie eristatavalt juurdekasvust suurem` : 'ükski aasta ei ole raie eristatavalt juurdekasvust suurem'}, ${under} aastal eristatavalt väiksem.`);
    },
    species(host) {
      if (none(host, d.species, 'Tagavara puuliigi järgi')) return;
      const ch = changes(d.species).filter((x) => x.name !== 'Teised puuliigid');
      C.errBars(host, { title: 'Tagavara enamuspuuliigi järgi', subtitle: `Kasvavate puude tagavara puistu enamuspuuliigi järgi: ${first(Object.values(d.species)[0]).year} ja ${L}.`, unit: 'tuhat m³', dec: 0, cats: catBars(d.species, null, PAIR), note: 'Enamuspuuliik on puistu, mitte üksikpuu liik.' });
      const big = ch.slice().sort((a, b) => Math.abs(b.diff) - Math.abs(a.diff))[0];
      const total = Object.values(d.species).reduce((a, s) => a + last(s).value, 0);
      const top = ch.slice().sort((a, b) => b.b.value - a.b.value)[0];
      C.punch(host, `${top.name} annab ${fmt(100 * top.b.value / total, 0)}% tagavarast; suurim absoluutne muutus on liigil ${big.name} (${sgn(100 * big.pct, 0)}%, ${big.ok == null ? 'eristatavus teadmata' : big.ok ? 'ületab veapiiri' : 'jääb veapiiri sisse'}).`);
    },
    owners(host) {
      if (none(host, d.owners, 'Metsamaa omand')) return;
      const t = Object.values(d.owners).reduce((a, s) => a + last(s).value, 0);
      const st = d.owners['Riigimetsamaa'] ? last(d.owners['Riigimetsamaa']) : null;
      C.errBars(host, { title: 'Metsamaa omand', subtitle: 'Metsamaa pindala omandi järgi.', unit: 'tuhat ha', dec: 0, height: 240, cats: catBars(d.owners, null, PAIR) });
      C.punch(host, st ? `Riigimetsamaa on ${L}. aastal ${fmt(100 * st.value / t, 0)}% metsamaast (${fmt(st.value, 0)} tuhat ha, ${pe(st.err)}).` : 'Metsamaa omandi jaotus.');
    },
    management(host) {
      if (none(host, d.management, 'Majanduskategooriad')) return;
      const parts = d.management_parts || ['Majandusmets', 'Majanduspiiranguga mets', 'Rangelt kaitstav mets'];
      const obj = Object.fromEntries(parts.filter((k) => d.management[k]).map((k) => [k, d.management[k]]));
      C.errBars(host, { title: 'Metsa majanduskategooria', subtitle: 'Metsamaa pindala majanduskategooria järgi.', unit: 'tuhat ha', dec: 0, height: 260, cats: catBars(obj, null, PAIR), note: 'Kolm üksteist välistavat kategooriat (summa = kogu metsamaa); SMI klassifikaator, mitte õiguslik kaitsestaatus.' });
      const total = d.management['Kokku mets'] ? last(d.management['Kokku mets']).value : null;
      const strict = obj['Rangelt kaitstav mets'] ? last(obj['Rangelt kaitstav mets']) : null;
      C.punch(host, strict && total ? `Rangelt kaitstavat metsa on ${fmt(100 * strict.value / total, 0)}% metsamaast (${fmt(strict.value, 0)} tuhat ha, ${pe(strict.err)}).` : 'Metsa jaotus majanduskategooriate järgi.');
    },
    counties(host) {
      if (none(host, d.counties, 'Maakonnad')) return;
      const rows = Object.entries(d.counties).map(([name, v]) => ({ name, r: last(v.stock_per_ha) })).filter((x) => x.r).sort((a, b) => b.r.value - a.r.value);
      C.errBars(host, { title: 'Hektaritagavara maakonniti', subtitle: `Keskmine tagavara m³/ha, ${L}. Maakondade hinnangud on ebatäpsemad kui riiklikud.`, unit: 'm³/ha', dec: 0, rotate: true, height: 330, cats: rows.map((x) => ({ label: x.name, points: [{ name: String(L), color: COL[0], value: x.r.value, err: x.r.err }] })) });
      const a = rows[0], b = rows[rows.length - 1];
      const dh = Math.hypot(a.r.value * a.r.err, b.r.value * b.r.err);
      C.punch(host, `Hektaritagavara on suurim maakonnas ${a.name} (${fmt(a.r.value, 0)} m³/ha) ja väikseim maakonnas ${b.name} (${fmt(b.r.value, 0)}); vahe ${Math.abs(a.r.value - b.r.value) > dh ? 'ületab' : 'ei ületa'} ühendatud veapiiri.`);
    },
    age(host) {
      if (none(host, d.age, 'Vanuseline jaotus')) return;
      const keys = Object.keys(d.age); // already ordered by lower bound
      const obj = Object.fromEntries(keys.map((k) => [k, d.age[k]]));
      C.errBars(host, { title: 'Puistute vanuseline jaotus', subtitle: 'Metsamaa pindala 20-aastaste vanuseklasside järgi (omandirühmad liidetud).', unit: 'tuhat ha', dec: 0, rotate: true, height: 320, cats: catBars(obj, null, PAIR), note: 'Vea arvutus liidab omandirühmade vead ruutude summana (ligikaudne).' });
      const ch = changes(obj), big = ch.slice().sort((a, b) => Math.abs(b.diff) - Math.abs(a.diff))[0], top = ch.slice().sort((a, b) => b.b.value - a.b.value)[0];
      C.punch(host, `Kõige suurem on vanuseklass ${top.name} (${fmt(top.b.value, 0)} tuhat ha); suurim muutus on klassis ${big.name} (${sgn(100 * big.pct, 0)}%, ${big.ok == null ? 'eristatavus teadmata' : big.ok ? 'ületab veapiiri' : 'jääb veapiiri sisse'}).`);
    },
    deadwood(host) {
      if (none(host, N.deadwood_per_ha, 'Surnud puit')) return;
      C.errLines(host, { title: 'Surnud puit', subtitle: 'Kuivanud (püsti) ja lamapuit kokku, m³ hektari kohta.', unit: 'm³/ha', dec: 1, zero: true, height: 260, series: [{ label: 'Surnud puit kokku', color: COL[5], data: N.deadwood_per_ha }], note: 'Summa liidab kaks eraldi hinnangut; viga on ligikaudne.' });
      const c = d.changes.deadwood_per_ha?.since_start;
      C.punch(host, `Surnud puitu on ${fmt(last(N.deadwood_per_ha).value, 1)} m³/ha (${pe(last(N.deadwood_per_ha).err)})${c ? `; ${sgn(100 * c.pct, 0)}% aastast ${c.from} (${verdict(c)})` : ''}.`);
    },
    methods(host) {
      const m = d.meta, q = d.errors;
      host.innerHTML = `<div class="methods"><b>Andmed ja meetod</b> <span class="review-flag">valdkonnaekspert ülevaatamata</span>
        <p><b>Allikas ja päritolu:</b> Keskkonnaagentuuri avaandmed (keskkonnaandmed.envir.ee, tabel f_smi_tulemused, SMI arvutustulemused). Hinnangud põhinevad riikliku statistilise metsainventuuri proovitükkidel; need on <b>valimipõhised hinnangud</b>, mitte täisloendus, ja kannavad suhtelist viga.</p>
        <p><b>Tõlgendus (kinnitamata):</b> ${m.interpretation.join(' ')}</p>
        <p><b>Meetod:</b> read valiti tabeli, näitaja, arvutustüübi ja täidetud klassifikaatorite täpse kombinatsiooni järgi, et kogusummasid ja osasummasid ei segataks. Muutust nimetatakse eristatavaks ainult siis, kui see ületab ühendatud veapiiri (ruutude summa ruutjuur). Hinnangute vea mediaan ${fmt(100 * q.quantiles.p50, 1)}%.</p>
        <p><b>Kontrollid:</b> ${Object.entries(d.checks || {}).map(([k, v]) => `${({ species_vs_stock: 'puuliikide tagavara summa', owners_vs_area: 'omandirühmade pindala summa', management_vs_total: 'majanduskategooriate summa', age_vs_area: 'vanuseklasside summa' })[k] || k} = ${fmt(100 * v, 1)}% kogusummast`).join('; ') || 'puuduvad'}. Väärtus ~100% tähendab, et klassid katavad kogusumma üks kord.</p>
        <p><b>Piirangud:</b> kattuvad perioodid, seega aastate vahelisi muutusi ei tohi tõlgendada aasta-aasta trendina; raie on SMI hinnang, mitte raiedokumentide statistika; väikeste rühmade hinnangud on ebatäpsed; pika perioodi võrdlusel võib inventuuri meetod muutuda. Genereeritud ${m.generated_utc.slice(0, 10)} (UTC).</p></div>`;
    },
  };
  for (const h of hosts) {
    const fn = builders[h.dataset.forest];
    if (fn) { try { fn(h); } catch (e) { h.innerHTML = '<p class="viz-note">Graafikut ei saanud joonistada.</p>'; console.error(e); } }
  }
})();
