// Автопрохождение дела: node tools/autoplay.js <caseIndex> <outDir> [maxSeconds]
// Проходит дело «идеально» (правильные улики и ответы), делает снимки ключевых моментов, печатает ошибки.
const { chromium } = require('playwright');
const path = require('path'), fs = require('fs');
(async () => {
  const [ci = '0', out = '/tmp/auto', maxS = '400', wrong = '0'] = process.argv.slice(2);
  fs.mkdirSync(out, { recursive: true });
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1152, height: 648 } });
  const errs = [];
  p.on('pageerror', e => errs.push('pageerror: ' + e.message + '\n' + (e.stack || '').split('\n').slice(0, 3).join('\n')));
  p.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') errs.push(m.type() + ': ' + m.text()); });
  await p.goto(process.env.GAME_URL || 'http://localhost:8765/dist/play.html');
  await p.waitForTimeout(500);
  await p.evaluate(i => G.startCase(+i), ci);
  let shots = 0, lastType = '', t0 = Date.now(), lastShotKey = '';
  const snap = async (name) => {
    const data = await p.evaluate(() => G.buffer.toDataURL('image/png'));
    fs.writeFileSync(path.join(out, String(shots++).padStart(3, '0') + '_' + name + '.png'), Buffer.from(data.split(',')[1], 'base64'));
  };
  let wrongDone = +wrong ? false : true;
  while (Date.now() - t0 < +maxS * 1000) {
    const st = await p.evaluate(() => {
      const S = G._dbg.S(); if (!S) return null;
      const B = S.block || {};
      return { type: B.type || null, end: S.endT != null, shot: S.view.mode + ':' + S.view.shot, line: S.line && S.line.text, who: S.line && S.line.who,
        lineDone: !S.line || S.line.shown >= S.line.visible, cross: S.cross && { idx: S.cross.idx, phase: S.cross.phase, hit: S.cross.t.statements.findIndex(x => x.hit), n: S.cross.t.statements.length, hitId: (S.cross.t.statements.find(x => x.hit) || {}).hit, adds: S.cross.t.statements.map(x => x.add || null) },
        rec: S.record.open, cmd: B.cmd ? { answer: B.cmd.answer, ok: (B.cmd.options || []).findIndex(o => o.ok), route: (B.cmd.routes || [])[0] || null } : null, ev: S.evidence.slice(), cred: S.cred };
    });
    if (!st) break;
    if (st.cred !== global.__lastCred) { console.log('cred', st.cred, 'block', st.type, 'line', (st.line || '').slice(0, 70), 'cross', JSON.stringify(st.cross && { idx: st.cross.idx, hit: st.cross.hit })); global.__lastCred = st.cred; }
    if (st.end) { await p.waitForTimeout(1200); await snap('end'); break; }
    const key = st.type + '|' + st.shot;
    if (key !== lastShotKey && ['line', 'cross', 'choice', 'presentPrompt', 'evidence', 'doc', 'title', 'shout', 'bigstamp', 'gameover'].includes(st.type)) {
      await p.waitForTimeout(st.type === 'shout' ? 350 : 250);
      await snap(st.type + '_' + st.shot.replace(':', '-'));
      lastShotKey = key;
    }
    if (st.type === 'gameover') { console.log('GAME OVER'); break; }
    if (st.type === 'cross' && st.cross) {
      if (st.cross.phase === 'title') { await p.evaluate(() => G.input._kp.add('Enter')); await p.waitForTimeout(80); continue; }
      // сначала уточнить все показания с add, если улики ещё нет
      const needAdd = st.cross.adds.findIndex(a => a && !st.ev.includes(a));
      if (!st.ev.includes(st.cross.hitId) && needAdd >= 0) {
        await p.evaluate(i => { const S = G._dbg.S(); S.cross.idx = i; G._dbg.cross('press'); }, needAdd);
      } else if (!wrongDone) {
        wrongDone = true;
        await p.evaluate(() => { G._dbg.cross('present'); });
        await p.waitForTimeout(400); await snap('record_open');
        await p.evaluate(() => { const S = G._dbg.S(); const bad = S.evidence.find(e => e !== S.cross.t.statements[S.cross.idx].hit); G._dbg.force({ present: bad }); });
      } else {
        await p.evaluate(i => { const S = G._dbg.S(); S.cross.idx = i; G._dbg.cross('present'); }, st.cross.hit);
        await p.waitForTimeout(300);
        await p.evaluate(id => G._dbg.force({ present: id }), st.cross.hitId);
      }
      await p.waitForTimeout(150); continue;
    }
    if (st.type === 'argue') {
      if (!st.lineDone) { await p.evaluate(() => G.input._kp.add('Enter')); await p.waitForTimeout(100); continue; }
      await p.waitForTimeout(600); await snap('argue');
      const r = st.cmd.route; await p.evaluate(r => G._dbg.force({ argue: { claim: r.claim, ground: r.ground, ev: r.ev || null } }), r);
      await p.waitForTimeout(150); continue;
    }
    if (st.type === 'choice') { await p.waitForTimeout(400); await p.evaluate(i => G._dbg.force({ choice: i }), st.cmd.ok); await p.waitForTimeout(100); continue; }
    if (st.type === 'presentPrompt') {
      if (!st.rec) { await p.evaluate(() => G.input._kp.add('Enter')); await p.waitForTimeout(120); continue; }
      await p.waitForTimeout(300);
      await p.evaluate(id => G._dbg.force({ present: id }), st.cmd.answer); await p.waitForTimeout(100); continue;
    }
    await p.evaluate(() => G.input._kp.add('Enter'));
    await p.waitForTimeout(60);
  }
  const fin = await p.evaluate(() => { const S = G._dbg.S(); return { end: S.endT != null, cred: S.cred, block: S.block && S.block.type }; });
  console.log('result', JSON.stringify(fin), 'shots', shots, 'time', ((Date.now() - t0) / 1000).toFixed(0) + 's');
  console.log(errs.length ? [...new Set(errs)].slice(0, 30).join('\n') : 'no errors');
  await b.close();
})();
