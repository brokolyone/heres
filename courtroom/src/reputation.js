/* =====================================================================
   REPUTATION — карьера адвоката.
   Каждое завершённое дело (победа или поражение) записывается в
   G.Save.data.career.cases. G.Rep.compute() раскладывает итог на слагаемые.
   Мнения (судья, присяжные, публика, пресса) — отдельные шкалы 0..100,
   они меняются от поступков в зале, а не только от исхода дела.
   ===================================================================== */
(function () {
'use strict';
const G = window.G;

const DIFF = { easy: 0.8, normal: 1.0, hard: 1.4 };
const OUTCOME_SHIFT = {
  win:  { judge: +4, jury: +5, public: +6, press: +8 },
  loss: { judge: -3, jury: -6, public: -8, press: -10 },
};
const TIERS = [
  [-Infinity, 'rep.tier0'], [0, 'rep.tier1'], [150, 'rep.tier2'], [350, 'rep.tier3'], [600, 'rep.tier4'], [900, 'rep.tier5'],
];
const clamp = v => Math.max(0, Math.min(100, Math.round(v)));

function scoreCase(c) {
  const k = DIFF[c.difficulty] || 1;
  const parts = [];
  const eff = c.effects || { judge: 0, jury: 0, public: 0, press: 0 };
  if (c.result === 'win') {
    parts.push({ label: 'rep.p.win', value: Math.round(100 * k), note: '100 × ' + k });
    parts.push({ label: 'rep.p.cred', value: c.cred * 12, note: c.cred + ' × 12' });
    if (c.alts) parts.push({ label: 'rep.p.routes', value: c.alts * 15, note: c.alts + ' × 15' });
    if (c.argues) parts.push({ label: 'rep.p.argue', value: c.argues * 10, note: c.argues + ' × 10' });
  } else {
    parts.push({ label: 'rep.p.loss', value: -Math.round(80 / k), note: '−80 ÷ ' + k });
  }
  if (c.mistakes) parts.push({ label: 'rep.p.mistakes', value: -c.mistakes * (c.result === 'win' ? 10 : 5), note: c.mistakes + ' × ' + (c.result === 'win' ? '−10' : '−5') });
  const crowd = (eff.public || 0) + (eff.press || 0);
  if (crowd) parts.push({ label: 'rep.p.crowd', value: crowd * 2, note: '(' + (eff.public || 0) + ' + ' + (eff.press || 0) + ') × 2' });
  const court = (eff.judge || 0) + (eff.jury || 0);
  if (court) parts.push({ label: 'rep.p.court', value: court, note: (eff.judge || 0) + ' + ' + (eff.jury || 0) });
  const score = parts.reduce((a, p) => a + p.value, 0);
  return { score, parts };
}

G.Rep = {
  /* записать итог дела */
  record(entry) {
    const car = G.Save.data.career;
    entry.at = Date.now();
    entry.difficulty = entry.difficulty || G.Save.data.settings.difficulty || 'normal';
    car.cases.push(entry);
    G.Save.save();
  },
  compute() {
    const car = G.Save.data.career || { cases: [] };
    const op = { judge: 50, jury: 50, public: 50, press: 50 };
    let total = 0;
    const history = [{ n: 0, total: 0 }];
    const cases = car.cases.map((c, i) => {
      const s = scoreCase(c);
      total += s.score;
      const sh = OUTCOME_SHIFT[c.result] || OUTCOME_SHIFT.loss;
      for (const k in op) op[k] = clamp(op[k] + sh[k] + 2 * ((c.effects && c.effects[k]) || 0));
      history.push({ n: i + 1, total, result: c.result });
      const cd = (G.Cases || []).find(x => x.id === c.id);
      return { id: c.id, title: cd ? cd.title : c.id, result: c.result, score: s.score, parts: s.parts, cred: c.cred, mistakes: c.mistakes || 0 };
    });
    let tier = TIERS[0][1];
    for (const [min, key] of TIERS) if (total >= min) tier = key;
    const wins = cases.filter(c => c.result === 'win').length;
    return { total, tier, wins, losses: cases.length - wins, cases, opinions: op, history };
  },
  reset() { G.Save.data.career = { cases: [], opinions: {} }; G.Save.save(); },
};
})();
