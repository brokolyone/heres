/* =====================================================================
   DIRECTOR — исполняет сценарии дел: камера, реплики, допросы,
   предъявление улик, протесты, вердикт. Даёт G.startCase(i).
   ===================================================================== */
(function () {
'use strict';
const G = window.G;

const SHOT_OF = { judge: 'judge', prosecutor: 'prosecution', player: 'defense', foreperson: 'jury' };
let MAX_CRED = 5;
function maxCred() { const d = G.Save.data.settings.difficulty; return d === 'easy' ? 7 : d === 'hard' ? 3 : 5; }
const tr = t => G.tr ? G.tr(t) : t;
const trf = (tpl, ...a) => { let s = tr(tpl); a.forEach((v, i) => { s = s.split('{' + i + '}').join(v); }); return s; };

let S = null;          // состояние текущего дела

/* ------------------------------------------------------------------ */
function caseData() { return S.case; }
function isWitness(id) { return (S.case.witnesses || []).includes(id); }
function evObj(id) {
  const e = S.case.evidence[id];
  if (!e) return { id, name: id, icon: 'document', desc: '' };
  const o = Object.assign({ id }, e, { name: tr(e.name), desc: tr(e.desc) });
  if (e.doc) o.doc = Object.assign({}, e.doc, { title: tr(e.doc.title), header: tr(e.doc.header), lines: (e.doc.lines || []).map(tr), signature: tr(e.doc.signature),
    stamps: (e.doc.stamps || []).map(st => Object.assign({}, st, { text: tr(st.text) })) });
  return o;
}
function ch(id) {
  if (!S.chars[id]) S.chars[id] = { emo: 'normal', anim: null, animStart: 0 };
  return S.chars[id];
}
function setEmo(id, emo) { if (emo) ch(id).emo = emo; }
function startAnim(id, a) { const c = ch(id); c.anim = a; c.animStart = G.time; }

/* ---------------- исполнение сценария ----------------
   S.stack  — основной сценарий (кадры {list,i}).
   S.istack — «вставки» во время перекрёстного допроса (уточнения, ошибки).
   Когда вставки кончились, а допрос активен — возвращаемся к показанию.  */
const CROSS = { c: '__cross' };
function push(list) {
  if (!list || !list.length) return;
  (S.cross ? S.istack : S.stack).push({ list, i: 0 });
}
function popFrom(st) {
  while (st.length) {
    const top = st[st.length - 1];
    if (top.i < top.list.length) return top.list[top.i++];
    st.pop();
  }
  return null;
}
function nextCmd() {
  if (S.istack.length) { const c = popFrom(S.istack); if (c) return c; }
  if (S.cross) return CROSS;
  S.fromMain = true;
  return popFrom(S.stack);
}
function run() {
  S.needRun = false;
  let guard = 0;
  while (!S.block && guard++ < 500) {
    S.fromMain = false;
    const c = nextCmd();
    if (c === CROSS) { S.block = { type: 'cross' }; if (S.cross.phase !== 'title') showStatement(); return; }
    if (!c) { S.block = { type: 'end' }; finishCase(); return; }
    exec(c);
  }
}

function shotFor(who) {
  if (S.view.shot === 'visit' && S.view.mode === 'shot' && (who === 'player' || who === S.case.defendant)) return 'visit';
  if (SHOT_OF[who]) return SHOT_OF[who];
  if (who === S.case.defendant) return 'defendant';
  if (isWitness(who) || who === S.witness) return 'witness';
  return null;   // clerk, bailiff и др. — изометрия
}

function setShot(id) {
  if (S.view.mode === 'shot' && S.view.shot === id) return;
  snapshotForTransition();
  S.view.mode = 'shot'; S.view.shot = id;
}
function setWorld(camTarget, instant) {
  if (S.view.mode !== 'world') { snapshotForTransition(); instant = true; }
  S.view.mode = 'world';
  const tgt = Object.assign({}, camTarget);
  if (instant) { S.cam = Object.assign({}, tgt); S.camTween = null; }
  else S.camTween = { from: Object.assign({}, S.cam), to: tgt, t: 0, dur: 0.7 };
}
function camForSpot(spotName) {
  const sp = spotOf(spotName);
  if (!sp) return G.Env ? G.Env.cams.wide : { x: 192, y: 108, z: 1 };
  return { x: sp.x, y: sp.y - 14, z: 2 };
}
function spotOf(name) {
  if (!G.Env || !name) return null;
  const m = /^(jury|gallery)(\d+)$/.exec(name);
  if (m) return (G.Env.spots[m[1]] || [])[+m[2]];
  return G.Env.spots[name];
}

let transSnap = null, transT = 1;
function snapshotForTransition() {
  if (!S.started) return;
  if (!transSnap) transSnap = G.makeCanvas(G.W, G.H);
  transSnap.getContext('2d').drawImage(G.buffer, 0, 0);
  transT = 0;
}

function sayLine(who, text, kind) {
  text = tr(text);
  S.line = { who, text, kind: kind || 'say', shown: 0, acc: 0, pauses: parsePauses(text), visible: visLen(text), pauseLeft: 0 };
  S.block = { type: 'line' };
}
function parsePauses(text) {
  const p = []; let n = 0;
  for (let i = 0; i < text.length; i++) {
    if (text.startsWith('{p}', i)) { p.push(n); i += 2; continue; }
    if (text[i] === '*') continue;
    n++;
  }
  return p;
}
function visLen(text) { return text.replace(/\{p\}/g, '').replace(/\*/g, '').length; }

function exec(c) {
  switch (c.c) {
    case 'say': {
      const who = c.who;
      if (c.emo) setEmo(who, c.emo);
      if (c.anim) startAnim(who, c.anim);
      if (isWitness(who) && S.witness !== who) { S.witness = who; placeWitness(who); }
      const sh = c.shot || shotFor(who);
      if (sh === 'wide') setWorld(G.Env.cams.wide);
      else if (sh) setShot(sh);
      else setWorld(camForSpot(S.pos[who] || who));
      S.speaker = who;
      sayLine(who, c.text, 'say');
      break;
    }
    case 'think': S.speaker = 'player'; sayLine('player', c.text, 'think'); break;
    case 'narrate': S.speaker = null; sayLine(null, c.text, 'narrate'); break;
    case 'shot': {
      if (c.id === 'wide') { setWorld(G.Env.cams.wide); break; }
      setShot(c.id);
      if (c.id === 'witness' && c.who) S.witness = c.who;
      break;
    }
    case 'wide': setWorld(G.Env.cams.wide); break;
    case 'cam': setWorld((G.Env.cams && G.Env.cams[c.id]) || camForSpot(c.id)); S.block = { type: 'wait', until: G.time + 0.7 }; break;
    case 'music': G.Audio && G.Audio.music(c.id); break;
    case 'sfx': G.Audio && G.Audio.sfx(c.id); break;
    case 'shout': doShout(c.kind || 'objection', c.who); break;
    case 'anim': {
      startAnim(c.who, c.id);
      const sh = shotFor(c.who);
      if (S.view.mode === 'shot' && sh && sh !== S.view.shot) setShot(sh);
      if (c.id === 'gavel') { setTimeout(() => G.Audio && G.Audio.sfx('gavel'), 430); setTimeout(() => G.fx.shake(2, .2), 430); }
      if (c.id === 'slam') { G.Audio && G.Audio.sfx('slam'); G.fx.shake(3, .25); }
      if (c.id === 'breakdown') { G.Audio && G.Audio.sfx('shock'); G.fx.flash(G.PAL.white, .3); G.fx.shake(5, .6); }
      S.block = { type: 'wait', until: G.time + Math.max(0.3, G.Cast.animDuration(c.who, c.id) || 0.8) };
      break;
    }
    case 'enter': S.pos[c.who] = c.spot; if (c.spot === 'witness') S.witness = c.who; break;
    case 'leave': delete S.pos[c.who]; break;
    case 'evidence': {
      if (!S.evidence.includes(c.id)) S.evidence.push(c.id);
      G.Audio && G.Audio.sfx('itemget');
      S.block = { type: 'evidence', id: c.id, t0: G.time };
      break;
    }
    case 'doc': G.Audio && G.Audio.sfx('paper'); S.block = { type: 'doc', id: c.id, t0: G.time }; break;
    case 'title': S.block = { type: 'title', text: tr(c.text), sub: tr(c.sub), t0: G.time }; break;
    case 'wait': S.block = { type: 'wait', until: G.time + (c.s || 1) }; break;
    case 'penalty': penalty(); break;
    case 'testimony': startTestimony(c.id); break;
    case 'present': checkpoint(); S.block = { type: 'presentPrompt', cmd: c, phase: 'ask' }; sayPrompt(c.prompt); break;
    case 'choice': checkpoint(); S.block = { type: 'choice', cmd: c, t0: G.time }; break;
    case 'objection': {
      const by = c.by || 'prosecutor';
      const list = [
        { c: 'shout', kind: 'objection', who: by },
        { c: 'say', who: by, emo: 'point', text: trf('Протест, ваша честь! {0}', tr(c.ground || '')) },
        { c: 'anim', who: 'judge', id: 'gavel' },
        { c: 'shout', kind: c.ruling === 'sustained' ? 'sustained' : 'overruled', who: 'judge' },
        { c: 'say', who: 'judge', emo: 'stern', text: tr(c.ruling === 'sustained' ? 'Протест принят.' : 'Протест отклонён.') + (c.note ? ' ' + tr(c.note) : '') },
      ];
      push(list);
      break;
    }
    case 'verdict': verdictSequence(c); break;
    case 'emo': setEmo(c.who, c.emo); break;
    case 'crowd': startCrowd(c); break;
    case 'effect': addEffects(c); break;
    case 'remarks': spawnRemarks(c.pool, c.mood || 'whisper', c.n || 3); break;
    case 'silence': doSilence(); break;
    case 'argue': checkpoint(); S.block = { type: 'argue', cmd: c, t0: G.time, st: { step: 0 } }; sayPrompt(c.prompt || 'Сформулируйте позицию защиты.'); break;
    case '__gameover': gameOver(); break;
    case '__add':
      if (!S.evidence.includes(c.id)) { S.evidence.push(c.id); G.Audio && G.Audio.sfx('itemget'); S.block = { type: 'evidence', id: c.id, t0: G.time }; }
      break;
    case '__stamp': G.Audio && G.Audio.sfx('stamp'); G.fx.shake(4, .3); S.block = { type: 'bigstamp', text: c.text, t0: G.time }; break;
    default: console.warn('unknown cmd', c);
  }
}

function sayPrompt(text) {
  S.speaker = 'player';
  text = tr(text || 'Какая улика это доказывает?');
  S.line = { who: 'player', text, kind: 'think', shown: 0, acc: 0, pauses: [], visible: visLen(text || ''), pauseLeft: 0 };
}

function doShout(kind, who) {
  if (who) {
    const sh = shotFor(who);
    if (sh) setShot(sh);
    setEmo(who, 'point');
  }
  G.Audio && G.Audio.sfx(kind === 'sustained' || kind === 'overruled' || kind === 'evidence' ? 'stamp' : 'objection');
  G.fx.shake(kind === 'objection' || kind === 'contradiction' ? 5 : 3, .4);
  G.fx.flash(G.PAL.white, .15);
  S.block = { type: 'shout', kind, t0: G.time, dur: 1.0 };
}

function penalty() {
  S.mistakes = (S.mistakes || 0) + 1;
  addEffects({ judge: -1, jury: -1 });
  S.cred = Math.max(0, S.cred - 1);
  S.credFlash = G.time;
  G.Audio && G.Audio.sfx('damage');
  G.fx.shake(4, .4); G.fx.flash(G.RAMP.red[3], .25);
  if (S.cred <= 0) push([{ c: '__gameover' }]);
}

/* ---------------- толпа: присяжные и зрители ---------------- */
function crowdIds() {
  const ids = [];
  for (const id in S.pos) if (/^(juror|spectator|foreperson)/.test(id)) ids.push(id);
  return ids;
}
function startCrowd(c) {
  const mood = c.mood || 'whisper';
  const loud = mood !== 'whisper' && mood !== 'murmur';
  const ids = crowdIds();
  const share = mood === 'whisper' ? 0.45 : mood === 'murmur' ? 0.6 : 0.9;
  for (const id of ids) if (Math.random() < share) {
    S.react[id] = { mood: mood === 'murmur' && Math.random() < .5 ? 'whisper' : mood, t0: G.time + Math.random() * 0.5, dur: loud ? 2.6 : 2.2 };
  }
  // реплики-пузыри
  const lines = (c.lines && c.lines.length ? c.lines : remarkPool(c.pool, mood).sort(() => Math.random() - .5).slice(0, loud ? 4 : 2));
  lines.forEach((text, k) => S.remarkQueue.push({ text: tr(text), mood, at: G.time + 0.15 + k * 0.4 }));
  S.bubbles = [];
  const sfx = { whisper: 'crowd', murmur: 'crowd', gasp: 'crowdGasp', angry: 'crowdAngry', cheer: 'cheer', clap: 'clap', laugh: 'crowd', shout: 'crowdAngry' }[mood];
  G.Audio && G.Audio.sfx(sfx || 'crowd');
  if (loud) G.fx.shake(mood === 'gasp' ? 2 : 3, .5);
  setWorld(G.Env.cams.wide, S.view.mode !== 'world');
  S.block = { type: 'wait', until: G.time + (loud ? 2.4 : 2.0) + lines.length * 0.25 };
}
const CROWD_LINES = {
  whisper: ['Ты слышал?', 'Шшш…', 'Он врёт.', 'Интересно…', 'Вот это да.'],
  murmur: ['Хм…', 'Не верю.', 'Странно.'],
  gasp: ['Ах!', 'Не может быть!', 'Боже мой!'],
  angry: ['Позор!', 'Лжец!', 'Как он мог?!'],
  cheer: ['Да!', 'Браво!', 'Свободна!', 'Ура!'],
  clap: ['Браво!', 'Молодец!'],
  laugh: ['Ха-ха!', 'Ну и ну!'],
  shout: ['Эй!', 'Позор!', 'Справедливость!'],
};
/* фоновая жизнь: кто-то всегда перешёптывается */
function ambientCrowd() {
  if (!S.nextAmbient || G.time > S.nextAmbient) {
    S.nextAmbient = G.time + 1.2 + Math.random() * 2.5;
    const ids = crowdIds();
    if (!ids.length) return;
    const id = ids[Math.floor(Math.random() * ids.length)];
    if (!S.react[id] || G.time - S.react[id].t0 > S.react[id].dur) {
      const r = Math.random();
      S.react[id] = { mood: r < .75 ? 'whisper' : 'murmur', t0: G.time, dur: 1.4 + Math.random() * 1.5, ambient: true };
    }
  }
}

/* ---------------- мнения ---------------- */
function addEffects(e) {
  if (!S.effects) S.effects = { judge: 0, jury: 0, public: 0, press: 0 };
  for (const k of ['judge', 'jury', 'public', 'press']) if (e[k]) {
    S.effects[k] += e[k];
    S.effFlash = { k, v: e[k], t0: G.time };
  }
}

/* ---------------- реплики зала по краям экрана ----------------
   Внезапные, не диалог: всплывают слева и справа, не перекрываются,
   плавно проявляются и сжимаются в точку.                              */
const SLOT_Y = [30, 52, 74, 96, 118];
function remarkPool(pool, mood) {
  const R = G.Remarks || {};
  const adult = G.Save.data.settings.adult;
  let list = [];
  if (pool && R.pools && R.pools[pool]) list = list.concat(R.pools[pool]);
  if (R.generic && R.generic[mood]) list = list.concat(R.generic[mood]);
  if (adult && R.adult) { if (pool && R.adult[pool]) list = list.concat(R.adult[pool]); if (R.adult[mood]) list = list.concat(R.adult[mood]); }
  if (!list.length) list = CROWD_LINES[mood] || CROWD_LINES.whisper;
  return list;
}
function spawnRemarks(pool, mood, n) {
  const list = remarkPool(pool, mood);
  for (let i = 0; i < n; i++) {
    const text = tr(list[Math.floor(Math.random() * list.length)]);
    S.remarkQueue.push({ text, mood, at: G.time + i * (0.35 + Math.random() * 0.5) });
  }
  if (mood !== 'whisper' && mood !== 'murmur') G.Audio && G.Audio.sfx(mood === 'gasp' ? 'crowdGasp' : mood === 'cheer' ? 'cheer' : mood === 'angry' || mood === 'shout' ? 'crowdAngry' : 'crowd');
}
function placeRemark(r) {
  const used = S.side.map(b => b.side + b.slot);
  const opts = [];
  for (const side of ['l', 'r']) for (let k = 0; k < SLOT_Y.length; k++) if (!used.includes(side + k)) opts.push({ side, slot: k });
  if (!opts.length) return false;
  const o = opts[Math.floor(Math.random() * opts.length)];
  S.side.push({ text: r.text, side: o.side, slot: o.slot, x: o.side === 'l' ? 6 : G.W - 6, y: SLOT_Y[o.slot] + Math.floor(Math.random() * 6), age: 0, life: 2.6 + Math.min(2.5, r.text.length * 0.04), mood: r.mood });
  return true;
}
function updateRemarks(dt) {
  for (const b of S.side) b.age += dt;
  S.side = S.side.filter(b => b.age < b.life);
  S.remarkQueue = S.remarkQueue.filter(r => { if (G.time < r.at) return true; return !placeRemark(r) && G.time - r.at < 3; });
  // фоновые перешёптывания во время заседания
  if (S.view.mode !== 'black' && !S.paused && S.endT == null && S.block && S.block.type !== 'title' && S.block.type !== 'gameover') {
    if (!S.nextRemark) S.nextRemark = G.time + 8;
    if (G.time > S.nextRemark) { S.nextRemark = G.time + 9 + Math.random() * 14; if (S.view.shot !== 'visit') spawnRemarks(null, Math.random() < .85 ? 'whisper' : 'murmur', 1); }
  }
}
function doSilence() {
  const prev = G.Audio && G.Audio.current();
  G.Audio && G.Audio.music('silence');
  G.Audio && G.Audio.sfx('crowdHush');
  S.side = []; S.remarkQueue = [];
  S.react = {};
  setEmo('judge', 'stern');
  S.block = { type: 'wait', until: G.time + 1.6 };
  if (prev && prev !== 'silence') setTimeout(() => { if (G.Audio && G.Audio.current() === 'silence') G.Audio.music(prev); }, 2600);
}

/* ---------------- конструктор аргумента ---------------- */
function submitArgue(B, r) {
  const c = B.cmd;
  const eq = (a, b) => a == null || a === b;
  const m = (c.routes || []).find(x => x.claim === r.claim && x.ground === r.ground && (!c.proof || eq(x.ev, r.ev)));
  S.block = null;
  if (m) {
    S.argues = (S.argues || 0) + 1;
    if (m.effects) addEffects(m.effects);
    push([{ c: 'shout', kind: 'evidence', who: 'player' }].concat(m.then || []));
    S.needRun = true; return;
  }
  const w = (c.weak || []).find(x => x.claim === r.claim && x.ground === r.ground && (!c.proof || eq(x.ev, r.ev)));
  if (w) {
    addEffects(Object.assign({ judge: -1 }, w.effects || {}));
    push(w.then || [{ c: 'say', who: 'judge', emo: 'stern', text: 'Довод слабый, мистер Рид, но суд его учтёт.' }]);
    S.needRun = true; return;
  }
  push([].concat(c.fail || [{ c: 'say', who: 'judge', emo: 'stern', text: 'Это основание здесь не применимо, мистер Рид. Сформулируйте позицию заново.' }], [{ c: 'penalty' }, Object.assign({}, c)]));
  S.needRun = true;
}

/* ---------------- контрольные точки и проигрыш ---------------- */
function checkpoint() {
  S.cp = {
    stack: S.stack.map((f, k) => ({ list: f.list, i: k === S.stack.length - 1 && S.fromMain ? Math.max(0, f.i - 1) : f.i })),
    evidence: S.evidence.slice(), pos: Object.assign({}, S.pos), witness: S.witness,
  };
}
function restoreCheckpoint() {
  if (!S.cp) return G.startCase(S.idx);
  S.stack = S.cp.stack.map(f => ({ list: f.list, i: f.i }));
  S.evidence = S.cp.evidence.slice(); S.pos = Object.assign({}, S.cp.pos); S.witness = S.cp.witness;
  S.cred = MAX_CRED; S.block = null; S.cross = null; S.istack = []; S.record.open = false; S.line = null;
  G.Audio && G.Audio.music('court');
  run();
}

/* ---------------- перекрёстный допрос ---------------- */
function startTestimony(id) {
  const t = S.case.testimonies[id];
  if (!t) { console.warn('no testimony', id); return; }
  S.witness = t.witness; placeWitness(t.witness);
  checkpoint();
  S.cross = { id, t, idx: 0, intro: true, phase: 'title', t0: G.time };
  G.Audio && G.Audio.music('cross');
  S.block = { type: 'cross' };
  setShot('witness');
}
function placeWitness(w) { if (!Object.values(S.pos).includes('witness') || S.pos[w] !== 'witness') { for (const k in S.pos) if (S.pos[k] === 'witness') delete S.pos[k]; S.pos[w] = 'witness'; } }

function showStatement() {
  const st = S.cross.t.statements[S.cross.idx];
  S.speaker = S.cross.t.witness;
  setShot('witness');
  const stx = tr(st.text);
  S.line = { who: S.cross.t.witness, text: stx, kind: 'statement', shown: 0, acc: 0, pauses: parsePauses(stx), visible: visLen(stx), pauseLeft: 0 };
}

function crossAction(a) {
  const cr = S.cross, st = cr.t.statements[cr.idx], n = cr.t.statements.length;
  if (a === 'prev') { cr.idx = (cr.idx - 1 + n) % n; G.Audio && G.Audio.sfx('select'); showStatement(); }
  else if (a === 'next') {
    G.Audio && G.Audio.sfx('select');
    if (cr.idx === n - 1) {
      cr.idx = 0;
      S.block = null;
      push([{ c: 'say', who: 'judge', text: cr.t.loopLine || 'Свидетель закончил показания. Если видите противоречие с уликами — предъявите улику. Если нет — уточните показания.' }]);
      run(); return;
    }
    cr.idx++; showStatement();
  }
  else if (a === 'press') {
    const list = [{ c: 'say', who: 'player', emo: 'point', text: pick(['Подождите. Уточните, пожалуйста.', 'Минуту, свидетель. Повторите это.', 'Стоп. Что именно вы имеете в виду?']) }];
    for (const x of (st.press || [])) list.push(x);
    if (st.add) list.push({ c: '__add', id: st.add });
    S.block = null; push(list); run();
  }
  else if (a === 'present' || a === 'record') {
    S.record = { open: true, sel: 0, page: 0, mode: a === 'present' ? 'present' : 'view', purpose: 'cross', frame: G.frameNo };
    G.Audio && G.Audio.sfx('paper');
  }
}

function presentInCross(evId) {
  const cr = S.cross, st = cr.t.statements[cr.idx];
  S.record.open = false;
  const name = evObj(evId).name;
  S.block = null;
  const alt = (st.alts || []).find(a => a.ev === evId);
  if (alt) {
    S.altsUsed = (S.altsUsed || 0) + 1;
    if (alt.effects) addEffects(alt.effects);
    const list = [
      { c: 'shout', kind: 'contradiction', who: 'player' },
      { c: 'say', who: 'player', emo: 'point', text: trf('Ваша честь, это показание опровергается уликой: «{0}».', name) },
      { c: 'emo', who: cr.t.witness, emo: 'shocked' },
      { c: 'sfx', id: 'shock' },
    ].concat(alt.hitScript || st.hitScript || []);
    S.cross = null; S.istack = [];
    G.Audio && G.Audio.music('pressure');
    push(list); S.needRun = true;
    return;
  }
  if (st.hit && st.hit === evId) {
    const list = [
      { c: 'shout', kind: 'contradiction', who: 'player' },
      { c: 'say', who: 'player', emo: 'point', text: trf(pick(['Ваша честь, это показание опровергается уликой: «{0}».', 'Свидетель, взгляните на это. «{0}».']), name) },
      { c: 'emo', who: cr.t.witness, emo: 'shocked' },
      { c: 'sfx', id: 'shock' },
    ].concat(st.hitScript || []);
    S.cross = null; S.istack = [];
    G.Audio && G.Audio.music('pressure');
    push(list); S.needRun = true;
  } else {
    const list = [{ c: 'say', who: 'player', emo: 'point', text: trf('Ваша честь, это показание опровергается уликой: «{0}».', name) }].concat(cr.t.wrong || [
      { c: 'say', who: 'prosecutor', emo: 'smirk', text: pick(['Ваша честь, защита показывает присяжным случайные бумаги.', 'Я не вижу никакой связи. Как и все в этом зале.', 'Защита, кажется, перепутала папки.']) },
      { c: 'say', who: 'judge', emo: 'stern', text: 'Суд не видит противоречия, мистер Рид. Не тратьте время присяжных.' },
    ], [{ c: 'penalty' }]);
    push(list); S.needRun = true;
  }
}

/* ---------------- вердикт ---------------- */
function verdictSequence(c) {
  const d = S.case, def = d.defendant;
  const fem = /а$|я$/.test((G.Cast.name(def) || '').split(' ').pop()) || ['whitfield', 'park'].includes(def);
  const word = fem ? 'НЕВИНОВНОЙ' : 'НЕВИНОВНЫМ';
  const charge = (d.charges && d.charges[0]) || { code: '', title: '' };
  push([
    { c: 'music', id: 'silence' },
    { c: 'title', text: 'ПРИСЯЖНЫЕ ВЕРНУЛИСЬ', sub: trf('Совещание длилось {0} ч {1} мин', 2 + (S.idx * 37) % 5, 10 + (S.idx * 23) % 50) },
    { c: 'wide' },
    { c: 'sfx', id: 'crowdHush' },
    { c: 'say', who: 'judge', text: 'Старшина присяжных, вынесли ли присяжные единогласный вердикт?' },
    { c: 'say', who: 'foreperson', text: 'Да, ваша честь.' },
    { c: 'say', who: 'judge', text: 'Передайте вердикт секретарю. {p}Секретарь, огласите.' },
    { c: 'say', who: 'clerk', text: trf('{0}, дело № {1}.', tr(d.caption || 'Народ штата Калифорния против подсудимого'), d.docket || '') },
    { c: 'say', who: 'clerk', text: trf(fem ? 'По обвинению по статье {0} — {1} — мы, присяжные, признаём подсудимую{p}{p}' : 'По обвинению по статье {0} — {1} — мы, присяжные, признаём подсудимого{p}{p}', charge.code, tr(charge.title)) },
    { c: 'music', id: 'victory' },
    { c: 'shot', id: 'defendant' },
    { c: 'emo', who: def, emo: 'relieved' },
    { c: 'say', who: 'clerk', shot: 'defendant', text: '*' + tr(word) + '*.' },
    { c: 'sfx', id: 'verdict' },
    { c: 'crowd', mood: 'cheer', lines: c.cheer || ['Да!', 'Браво!', 'Справедливость!', 'Ура!'] },
    { c: 'crowd', mood: 'clap' },
    { c: 'anim', who: 'judge', id: 'gavel' },
    { c: 'say', who: 'judge', emo: 'stern', text: 'Тишина в зале! {p}Прошу тишины.' },
    { c: '__stamp', text: fem ? 'ОПРАВДАНА' : 'ОПРАВДАН' },
    { c: 'say', who: 'judge', emo: 'smile', text: fem ? 'Подсудимая освобождается из-под стражи. Залог возвращается. Заседание закрыто.' : 'Подсудимый освобождается из-под стражи. Залог возвращается. Заседание закрыто.' },
    { c: 'say', who: def, shot: 'defendant', emo: 'relieved', text: c.thanks || 'Спасибо вам. Я… я не знаю, что сказать. Спасибо.' },
  ]);
}

/* ---------------- завершение дела ---------------- */
function finishCase() {
  const d = S.case;
  if (G.Rep && !S.recorded) { S.recorded = true; G.Rep.record({ id: d.id, result: 'win', cred: S.cred, maxCred: MAX_CRED, mistakes: S.mistakes, alts: S.altsUsed, argues: S.argues, effects: S.effects }); }
  G.Save.data.solved[d.id] = Math.max(G.Save.data.solved[d.id] || 0, S.cred || 1);
  G.Save.data.progress = { case: Math.min(S.idx + 1, G.Cases.length - 1) };
  G.Save.save();
  S.endT = G.time;
}

function gameOver() {
  if (G.Rep && !S.recordedLoss) { S.recordedLoss = true; G.Rep.record({ id: S.case.id, result: 'loss', cred: 0, maxCred: MAX_CRED, mistakes: S.mistakes, alts: S.altsUsed, argues: S.argues, effects: S.effects }); }
  S.stack = []; S.istack = []; S.cross = null; S.record.open = false;
  G.Audio && G.Audio.music('defeat');
  S.block = { type: 'gameover', t0: G.time };
  S.view.mode = 'shot'; S.view.shot = 'judge'; setEmo('judge', 'stern');
  setTimeout(() => G.Audio && G.Audio.sfx('gavel3'), 600);
  startAnim('judge', 'gavel');
}

function pick(a) { return a[Math.floor(Math.random() * a.length)]; }

/* ================== ОБНОВЛЕНИЕ ================== */
function textSpeed() { return 42 * ((G.Save.data.settings && G.Save.data.settings.textSpeed) || 1); }

function updateLine(dt) {
  const L = S.line;
  if (!L || L.shown >= L.visible) return;
  if (L.pauseLeft > 0) { L.pauseLeft -= dt; return; }
  L.acc += dt * textSpeed();
  while (L.acc >= 1 && L.shown < L.visible) {
    L.acc -= 1; L.shown++;
    if (L.pauses.includes(L.shown)) { L.pauseLeft = 0.4; L.acc = 0; break; }
    if (L.shown % 2 === 0 && L.who && G.Audio) G.Audio.blip(G.Cast.voice(L.who));
  }
}
function lineDone() { return !S.line || S.line.shown >= S.line.visible; }
function advanceInput() {
  const i = G.input;
  return i.released && !S.uiConsumed || i.keyPressed('Enter') || i.keyPressed(' ') || i.keyPressed('z');
}

const Court = {
  enter(idx) {
    if (idx && idx.resume && S) { G.resize && G.resize(); return; }
    const d = G.Cases[idx];
    S = {
      idx, case: d, stack: [], istack: [], block: null, line: null, speaker: null,
      chars: {}, pos: {}, witness: (d.witnesses || [])[0] || null,
      evidence: (d.start || []).slice(), cred: (MAX_CRED = maxCred()), credFlash: -9,
      mistakes: 0, effects: { judge: 0, jury: 0, public: 0, press: 0 }, altsUsed: 0, argues: 0, side: [], remarkQueue: [],
      view: { mode: 'black', shot: null }, cam: { x: 0, y: 0, z: 1 }, camTween: null,
      record: { open: false, sel: 0, page: 0, mode: 'view' }, cross: null, pressed: {},
      paused: false, started: false, cp: null, endT: null, react: {}, bubbles: [],
    };
    // расстановка по местам
    S.pos.judge = 'judge'; S.pos.clerk = 'clerk'; S.pos.bailiff = 'bailiff';
    S.pos.player = 'defense'; S.pos.prosecutor = 'prosecution'; S.pos[d.defendant] = 'defendant';
    for (let k = 1; k <= 6; k++) S.pos['juror' + k] = 'jury' + (k - 1);
    S.pos.foreperson = 'jury6';
    const hasSpect = G.Cast.has('spectator1');
    const juryN = G.Env && G.Env.spots.jury ? G.Env.spots.jury.length : 7;
    for (let k = 7; k < juryN; k++) S.pos[hasSpect ? 'spectator' + (k - 6) : 'juror' + ((k % 6) + 1) + '_' + k] = 'jury' + k;
    const galN = G.Env && G.Env.spots.gallery ? G.Env.spots.gallery.length : 0;
    for (let k = 0; k < galN; k++) {
      const sid = hasSpect ? 'spectator' + (((k + 5 + idx * 3) % 12) + 1) : 'juror' + (((k * 5 + idx) % 6) + 1);
      if (S.pos[sid]) { S.pos[sid + '_g' + k] = 'gallery' + k; } else S.pos[sid] = 'gallery' + k;
    }
    if (G.Env && G.Env.spots.reporter) S.pos.reporter = 'reporter';
    if (G.Env) S.cam = Object.assign({}, G.Env.cams.wide);
    push(d.script);
    S.started = true;
    run();
  },
  update(dt) {
    if (!S) return;
    const inp = G.input;
    S.uiConsumed = false;
    if (S.camTween) {
      const tw = S.camTween; tw.t += dt;
      const k = G.ease.inOut(G.clamp(tw.t / tw.dur, 0, 1));
      S.cam = { x: G.lerp(tw.from.x, tw.to.x, k), y: G.lerp(tw.from.y, tw.to.y, k), z: G.lerp(tw.from.z || 1, tw.to.z || 1, k) };
      if (tw.t >= tw.dur) { S.cam = Object.assign({}, tw.to); S.camTween = null; }
    }
    if (transT < 1) transT = Math.min(1, transT + dt / 0.22);

    if (inp.keyPressed('Escape') && S.repOpen) { S.repOpen = false; return; }
    if (inp.keyPressed('Escape') && !S.record.open && S.endT == null) { S.paused = !S.paused; G.Audio && G.Audio.sfx(S.paused ? 'select' : 'cancel'); return; }
    if (S.paused) return;
    if (S.endT != null) return;

    // анимации заканчиваются
    for (const id in S.chars) { const c = S.chars[id]; if (c.anim && G.time - c.animStart > (G.Cast.animDuration(id, c.anim) || 1) + 0.05) { if (c.anim === 'breakdown') c.emo = 'breakdown'; c.anim = null; } }

    updateLine(dt);
    if (S.view.mode === 'world') ambientCrowd();
    updateRemarks(dt);
    S.bubbles = S.bubbles.filter(b => G.time - b.t0 < b.dur);
    if (S.needRun) { run(); }
    const B = S.block;
    if (!B) { run(); return; }

    if (S.record.open) return; // ввод обрабатывает draw (UI-кнопки)

    switch (B.type) {
      case 'line':
        if (advanceInput()) {
          if (!lineDone()) { S.line.shown = S.line.visible; }
          else { S.block = null; run(); }
        }
        break;
      case 'wait': if (G.time >= B.until) { S.block = null; run(); } break;
      case 'shout': if (G.time - B.t0 >= B.dur) { S.block = null; run(); } break;
      case 'bigstamp': if (G.time - B.t0 > 0.6 && advanceInput() || G.time - B.t0 > 2.4) { S.block = null; run(); } break;
      case 'title': if (G.time - B.t0 > 0.8 && advanceInput() || G.time - B.t0 > 4.5) { S.block = null; run(); } break;
      case 'evidence': if (G.time - B.t0 > (G.UI.drawItemGet ? 2.0 : 0.5) && advanceInput()) { S.block = null; G.Audio && G.Audio.sfx('select'); run(); } break;
      case 'doc': if (B.back) break; if (G.time - B.t0 > 0.4 && advanceInput()) { S.block = null; G.Audio && G.Audio.sfx('paper'); run(); } break;
      case 'cross': updateCross(); break;
      case 'presentPrompt':
        if (B.phase === 'ask' && lineDone() && advanceInput()) { B.phase = 'record'; S.record = { open: true, sel: 0, page: 0, mode: 'present', purpose: 'present', frame: G.frameNo }; G.Audio && G.Audio.sfx('paper'); }
        else if (B.phase === 'ask' && !lineDone() && advanceInput()) S.line.shown = S.line.visible;
        break;
      case 'argue': if (!lineDone() && advanceInput()) S.line.shown = S.line.visible; break;
      case 'gameover': break;
      case 'end': break;
    }
  },
  draw(ctx) { if (S) drawAll(ctx); },
  exit() {},
};

function updateCross() {
  const cr = S.cross;
  if (!cr) { S.block = null; run(); return; }
  if (cr.phase === 'title') {
    if (G.time - cr.t0 > 0.6 && advanceInput() || G.time - cr.t0 > 2.6) { cr.phase = 'statement'; showStatement(); }
    return;
  }
  // клавиатура
  const i = G.input;
  if (!lineDone() && advanceInput()) { S.line.shown = S.line.visible; return; }
  if (i.keyPressed('ArrowLeft')) return crossAction('prev');
  if (i.keyPressed('ArrowRight') || (lineDone() && (i.keyPressed('Enter') || i.keyPressed(' ')))) return crossAction('next');
  if (i.keyPressed('q') || i.keyPressed('Q') || i.keyPressed('й')) return crossAction('press');
  if (i.keyPressed('e') || i.keyPressed('E') || i.keyPressed('у')) return crossAction('present');
  if (S.hudAction) { const a = S.hudAction; S.hudAction = null; crossAction(a); }
}

/* ================== ОТРИСОВКА ================== */
function charOpts(id, extra) {
  const c = ch(id);
  const talking = S.line && S.line.who === id && S.line.kind !== 'think' && S.line.shown < S.line.visible && S.line.pauseLeft <= 0;
  return Object.assign({ emo: c.emo, talking, t: G.time, anim: c.anim, animT: c.anim ? G.time - c.animStart : 0 }, extra || {});
}

function bustForShot(shot) {
  switch (shot) {
    case 'judge': return 'judge';
    case 'prosecution': return 'prosecutor';
    case 'defense': return 'player';
    case 'witness': return S.witness;
    case 'defendant': case 'visit': return S.case.defendant;
    case 'jury': return S.line && S.line.who === 'foreperson' ? 'foreperson' : null;
  }
  return null;
}

function drawScene(ctx) {
  if (S.view.mode === 'world' && G.Env) {
    G.applyCam(ctx, S.cam);
    G.Env.drawWorld(ctx, 'back', G.time);
    const list = [];
    for (const id in S.pos) { const sp = spotOf(S.pos[id]); if (sp) list.push({ id, sp }); }
    list.sort((a, b) => a.sp.y - b.sp.y);
    for (const o of list) {
      const base = o.id.replace(/_.*$/, '');
      const r = S.react[o.id];
      const extra = { pose: o.sp.pose || 'stand', dir: o.sp.dir || 'l', t: G.time + (o.sp.x * 0.37) % 3 };
      if (r && G.time >= r.t0 && G.time - r.t0 < r.dur) { extra.react = r.mood; extra.reactT = G.time - r.t0; }
      G.Cast.drawIso(ctx, base, o.sp.x, o.sp.y, Object.assign(charOpts(base, extra), { t: extra.t }));
      o.screen = { x: o.sp.x, y: o.sp.y };
    }
    G.Env.drawWorld(ctx, 'front', G.time);
    // реплики толпы над головами (в мировых координатах -> экран)
    G.resetCam(ctx);
    for (const b of S.bubbles) {
      const age = G.time - b.t0; if (age < 0 || age > b.dur) continue;
      const sp = spotOf(S.pos[b.who]); if (!sp || !G.UI.drawSpeech) continue;
      const z = S.cam.z || 1;
      const sx = Math.round(G.W / 2 + (sp.x - S.cam.x) * z), sy = Math.round(G.H / 2 + (sp.y - 26 - S.cam.y) * z);
      G.UI.drawSpeech(ctx, sx, sy, b.text, age);
    }
    G.resetCam(ctx);
  } else if (S.view.mode === 'shot' && G.Env) {
    const sh = S.view.shot, info = G.Env.shots[sh] || { anchor: { x: 192, y: 180 }, flip: false };
    G.Env.drawShot(ctx, sh, 'back', G.time);
    const who = bustForShot(sh);
    if (who) {
      let ax = info.anchor.x, ay = info.anchor.y;
      // лёгкий «наезд» камеры при ударе/эмоции не делаем — пиксельная чистота
      G.Cast.drawBust(ctx, who, ax, ay, charOpts(who, { flip: !!info.flip }));
    }
    G.Env.drawShot(ctx, sh, 'front', G.time);
  }
}

function drawAll(ctx) {
  const B = S.block || {};
  if (B.type === 'title') { drawTitleCard(ctx, B); return; }

  drawScene(ctx);

  // переход между планами: старый кадр уезжает
  if (transT < 1 && transSnap) {
    const k = G.ease.in(transT);
    const dx = Math.round(-k * G.W);
    ctx.drawImage(transSnap, dx, 0);
    G.rect(ctx, dx + G.W, 0, 2, G.H, G.PAL.white);
  }

  // HUD: доверие суда
  if (S.view.mode !== 'black' && G.UI && G.UI.drawCredibility && B.type !== 'gameover') {
    G.UI.drawCredibility(ctx, G.W - 88, 3, S.cred, MAX_CRED, G.time, { flashLost: G.time - S.credFlash < 1.2 });
  }

  // диалог
  if (S.line && B.type !== 'evidence' && B.type !== 'doc' && B.type !== 'bigstamp' && B.type !== 'gameover') {
    const L = S.line;
    const color = L.kind === 'think' ? G.RAMP.blue[6] : L.kind === 'statement' ? G.RAMP.green[5] : null;
    const name = L.who ? (L.who === 'player' && L.kind === 'think' ? trf('{0} (мысленно)', G.Cast.name('player')) : G.Cast.name(L.who)) : null;
    G.UI.drawDialog(ctx, { name, text: L.kind === 'think' ? '(' + L.text + ')' : L.text, shown: L.shown + (L.kind === 'think' ? 1 : 0), waiting: lineDone() && B.type === 'line', t: G.time, side: L.who === 'player' ? 'left' : 'right', color });
  }

  // HUD допроса
  if (B.type === 'cross' && S.cross) {
    const cr = S.cross;
    if (cr.phase === 'title') drawCrossTitle(ctx, cr);
    else if (!S.record.open) {
      const r = G.UI.crossHUD(ctx, { title: tr(cr.t.title), index: cr.idx, total: cr.t.statements.length, statement: cr.t.statements[cr.idx].text, t: G.time });
      if (r && r.action) { S.hudAction = r.action; S.uiConsumed = true; }
    }
  }

  // выбор
  if (B.type === 'choice') {
    let idx = G.UI.choice(ctx, tr(B.cmd.prompt), B.cmd.options.map(o => tr(o.text)), G.time - B.t0);
    if (G.time - B.t0 < 0.3) idx = -1;   // то же нажатие, что пролистало реплику, не должно выбрать вариант
    if (S.force && S.force.choice != null) { idx = S.force.choice; S.force.choice = null; }
    if (idx >= 0) {
      const o = B.cmd.options[idx];
      G.Audio && G.Audio.sfx('select');
      S.block = null;
      if (o.ok) push(o.then || []);
      else { const back = { c: 'choice', prompt: B.cmd.prompt, options: B.cmd.options }; push([].concat(o.then || [{ c: 'say', who: 'judge', emo: 'stern', text: 'Это не выдерживает критики, мистер Рид.' }], [{ c: 'penalty' }, back])); }
      S.needRun = true;
    }
  }

  // папка дела
  if (S.record.open) {
    const list = S.evidence.map(evObj);
    let r = G.UI.courtRecord(ctx, S.record, list, G.time) || {};
    if (S.record.frame === G.frameNo) r = {};
    if (S.force && S.force.present) { r = { action: 'present', id: S.force.present }; S.force.present = null; }
    if (r.action === 'close') { S.record.open = false; G.Audio && G.Audio.sfx('cancel'); if (B.type === 'presentPrompt') { B.phase = 'ask'; S.line.shown = S.line.visible; } }
    else if (r.action === 'doc' && r.id) { S.record.open = false; S.block = { type: 'doc', id: r.id, t0: G.time, back: B }; }
    else if (r.action === 'present' && r.id) {
      G.Audio && G.Audio.sfx('select');
      if (S.record.purpose === 'cross' && S.cross) presentInCross(r.id);
      else if (B.type === 'presentPrompt') {
        S.record.open = false;
        const cmd = B.cmd; S.block = null;
        if (r.id === cmd.answer) push([{ c: 'shout', kind: 'evidence', who: 'player' }].concat(cmd.ok || []));
        else push([].concat(cmd.fail || [{ c: 'say', who: 'judge', emo: 'stern', text: 'Не понимаю, как это относится к вопросу, мистер Рид.' }], [{ c: 'penalty' }, { c: 'present', prompt: cmd.prompt, answer: cmd.answer, ok: cmd.ok, fail: cmd.fail }]));
        S.needRun = true;
      }
    }
  }

  // всплывающая улика
  if (B.type === 'evidence') { if (G.UI.drawItemGet) G.UI.drawItemGet(ctx, evObj(B.id), G.time - B.t0); else drawEvidencePopup(ctx, B); }
  if (B.type === 'doc') {
    const e = evObj(B.id);
    const doc = e.doc || { title: e.name, header: '', lines: [e.desc] };
    G.UI.drawDocument(ctx, doc, G.time - B.t0);
    if (B.back) { /* вернуться к папке */ if (G.input.released || G.input.keyPressed('Escape') || G.input.keyPressed('Enter')) { S.block = B.back; S.record.open = true; } }
  }
  if (B.type === 'shout') G.UI.drawShout(ctx, B.kind, G.clamp((G.time - B.t0) / B.dur, 0, 1));
  if (B.type === 'bigstamp') { G.UI.drawStamp(ctx, G.W / 2, G.H / 2 - 10, B.text, G.PAL.stamp, { angle: -8, size: 'big', t: G.clamp((G.time - B.t0) / 0.35, 0, 1) }); }
  if (B.type === 'gameover') drawGameOver(ctx, B);
  // реплики зала по краям
  if (G.UI.drawCrowdBubble) for (const b of S.side) G.UI.drawCrowdBubble(ctx, b);
  // конструктор аргумента
  if (B.type === 'argue') {
    if (lineDone() && G.UI.argueBuilder) {
      const c = B.cmd;
      const data = { prompt: tr(c.prompt), proof: !!c.proof,
        claims: (c.claims || []).map(x => ({ id: x.id, text: tr(x.text) })),
        grounds: (c.grounds || []).map(x => ({ id: x.id, text: tr(x.text), law: x.law })) };
      if (B.readyT == null) B.readyT = G.time;
      let r = G.UI.argueBuilder(ctx, B.st, data, S.evidence.map(evObj), G.time - B.t0);
      if (G.time - B.readyT < 0.3) r = null;
      if (S.force && S.force.argue) { r = Object.assign({ action: 'submit' }, S.force.argue); S.force.argue = null; }
      if (r && r.action === 'submit') submitArgue(B, r);
    }
  }
  // всплывающее изменение мнений
  if (S.effFlash && G.time - S.effFlash.t0 < 1.6) {
    const e = S.effFlash, k = G.clamp((G.time - e.t0) / 1.6, 0, 1);
    const label = tr({ judge: 'Судья', jury: 'Присяжные', public: 'Публика', press: 'Пресса' }[e.k]) + ' ' + (e.v > 0 ? '+' : '') + e.v;
    G.Font.draw(ctx, label, G.W - 8, 28 - Math.round(k * 6), e.v > 0 ? G.RAMP.green[5] : G.RAMP.red[4], { align: 'right', shadow: G.PAL.black });
  }
  if (S.endT != null) drawCaseEnd(ctx);
  if (S.paused) {
    if (S.repOpen && G.UI.ReputationScreen) { if (G.UI.ReputationScreen(ctx, G.Rep.compute(), G.time) === 'close') S.repOpen = false; }
    else if (G.UI.PauseMenu) {
      const a = G.UI.PauseMenu(ctx, G.time);
      if (a === 'resume') S.paused = false;
      else if (a === 'record') { S.paused = false; S.record = { open: true, sel: 0, page: 0, mode: 'view', purpose: 'view', frame: G.frameNo }; }
      else if (a === 'reputation') S.repOpen = true;
      else if (a === 'settings') { S.paused = false; G.setScene(G.UI.SettingsScene, { back: Court }); }
      else if (a === 'restart') { S.paused = false; G.startCase(S.idx); }
      else if (a === 'title') { S.paused = false; G.Audio && G.Audio.music('menu'); G.setScene(G.UI.TitleScene); }
    } else drawPause(ctx);
  }
}

function drawTitleCard(ctx, B) {
  const k = G.clamp((G.time - B.t0) / 0.6, 0, 1);
  G.rect(ctx, 0, 0, G.W, G.H, G.PAL.black);
  const F = G.Font;
  const lines = F.wrap(B.text, G.W - 40, { font: 'big' });
  let y = 84 - lines.length * 7;
  for (const l of lines) { F.draw(ctx, l, G.W / 2, y, G.RAMP.gold[4], { font: 'big', align: 'center', maxChars: Math.floor(k * 80) }); y += 16; }
  if (B.sub) {
    const sl = F.wrap(B.sub, G.W - 60);
    y += 6;
    for (const l of sl) { F.draw(ctx, l, G.W / 2, y, G.RAMP.neutral[7], { align: 'center', maxChars: Math.floor(G.clamp((G.time - B.t0 - 0.5) * 50, 0, 200)) }); y += 11; }
  }
  // тонкие линейки
  const w = Math.round(k * 120);
  G.rect(ctx, G.W / 2 - w, 60, w * 2, 1, G.RAMP.gold[2]);
  G.rect(ctx, G.W / 2 - w, y + 6, w * 2, 1, G.RAMP.gold[2]);
}

function drawCrossTitle(ctx, cr) {
  const k = G.clamp((G.time - cr.t0) / 0.4, 0, 1);
  const h = Math.round(k * 46);
  G.rect(ctx, 0, 70 - h / 2, G.W, h, G.RAMP.neutral[1]);
  G.rect(ctx, 0, 70 - h / 2, G.W, 1, G.RAMP.gold[3]);
  G.rect(ctx, 0, 70 + h / 2 - 1, G.W, 1, G.RAMP.gold[3]);
  if (k >= 1) {
    G.Font.draw(ctx, tr('ПЕРЕКРЁСТНЫЙ ДОПРОС'), G.W / 2, 56, G.RAMP.gold[4], { font: 'big', align: 'center', shadow: G.PAL.black });
    G.Font.draw(ctx, '«' + tr(cr.t.title) + '» — ' + G.Cast.name(cr.t.witness), G.W / 2, 74, G.RAMP.neutral[8], { align: 'center' });
  }
}

function drawEvidencePopup(ctx, B) {
  const e = evObj(B.id);
  const k = G.ease.back(G.clamp((G.time - B.t0) / 0.35, 0, 1));
  const w = 220, h = 92, x = (G.W - w) / 2, y = Math.round(40 + (1 - k) * 30);
  G.dither(ctx, 0, 0, G.W, G.H, G.PAL.black, 8);
  G.rect(ctx, x - 1, y - 1, w + 2, h + 2, G.PAL.outline);
  G.rect(ctx, x, y, w, h, G.RAMP.paper[3]);
  G.rect(ctx, x, y, w, 12, G.RAMP.wood[2]);
  G.Font.draw(ctx, 'УЛИКА ПРИОБЩЕНА К ДЕЛУ', x + 6, y + 2, G.RAMP.gold[4]);
  G.rect(ctx, x + 8, y + 20, 36, 36, G.RAMP.paper[1]);
  if (G.Icons) G.Icons.draw(ctx, e.icon || 'document', x + 10, y + 22);
  G.Font.draw(ctx, e.name, x + 52, y + 18, G.RAMP.neutral[1], { font: 'big' });
  const dl = G.Font.wrap(e.desc || '', w - 60);
  dl.slice(0, 5).forEach((l, i) => G.Font.draw(ctx, l, x + 52, y + 34 + i * 10, G.PAL.ink));
  if (G.time - B.t0 > 0.35 && G.UI.drawStamp) G.UI.drawStamp(ctx, x + w - 34, y + h - 14, 'ВЕЩДОК', G.PAL.stampBlue, { angle: -10, size: 'small', t: 1 });
}

function drawGameOver(ctx, B) {
  const k = G.clamp((G.time - B.t0) / 1.2, 0, 1);
  G.dither(ctx, 0, 0, G.W, G.H, G.PAL.black, Math.round(k * 12));
  if (G.time - B.t0 > 1.0) {
    G.UI.drawStamp(ctx, G.W / 2, 70, S.case.defendant && ['whitfield', 'park'].includes(S.case.defendant) ? 'ВИНОВНА' : 'ВИНОВЕН', G.PAL.stamp, { angle: -6, size: 'big', t: G.clamp((G.time - B.t0 - 1) / 0.3, 0, 1) });
    G.Font.draw(ctx, 'Доверие суда исчерпано. Присяжные вынесли обвинительный вердикт.', G.W / 2, 112, G.RAMP.neutral[8], { align: 'center' });
    if (G.time - B.t0 > 1.6) {
      if (G.UI.button(ctx, { x: G.W / 2 - 110, y: 136, w: 220, h: 18 }, 'Апелляция: продолжить с допроса', { kind: 'primary', hotkey: 'Enter' })) restoreCheckpoint();
      if (G.UI.button(ctx, { x: G.W / 2 - 110, y: 160, w: 105, h: 18 }, 'Заново', {})) G.startCase(S.idx);
      if (G.UI.button(ctx, { x: G.W / 2 + 5, y: 160, w: 105, h: 18 }, 'В меню', {})) { G.Audio && G.Audio.music('menu'); G.setScene(G.UI.TitleScene); }
    }
  }
}

function drawCaseEnd(ctx) {
  const k = G.clamp((G.time - S.endT) / 0.8, 0, 1);
  G.dither(ctx, 0, 0, G.W, G.H, G.PAL.black, Math.round(k * 13));
  if (k < 1) return;
  const d = S.case;
  const w = 260, h = 150, x = (G.W - w) / 2, y = 26;
  G.rect(ctx, x - 1, y - 1, w + 2, h + 2, G.PAL.outline);
  G.rect(ctx, x, y, w, h, G.RAMP.paper[3]);
  G.Font.draw(ctx, 'ДЕЛО ЗАКРЫТО', x + w / 2, y + 8, G.RAMP.neutral[1], { font: 'big', align: 'center' });
  G.Font.draw(ctx, d.caption || d.title, x + w / 2, y + 26, G.PAL.ink, { align: 'center' });
  G.Font.draw(ctx, '№ ' + (d.docket || '') + '   ' + ((d.charges && d.charges[0] && d.charges[0].code) || ''), x + w / 2, y + 38, G.RAMP.neutral[4], { align: 'center' });
  G.Font.draw(ctx, tr('Доверие суда') + ': ' + S.cred + ' / ' + MAX_CRED, x + 16, y + 58, G.RAMP.neutral[2]);
  G.Font.draw(ctx, trf('Улик в деле: {0}', S.evidence.length), x + 16, y + 70, G.RAMP.neutral[2]);
  G.UI.drawStamp(ctx, x + w - 64, y + 70, ['whitfield', 'park'].includes(d.defendant) ? 'ОПРАВДАНА' : 'ОПРАВДАН', G.PAL.stamp, { angle: -12, size: 'small', t: 1 });
  const next = G.Cases[S.idx + 1];
  if (next && G.UI.button(ctx, { x: x + 16, y: y + h - 28, w: 120, h: 18 }, 'Следующее дело', { kind: 'primary', hotkey: 'Enter' })) G.startCase(S.idx + 1);
  if (!next) G.Font.draw(ctx, 'Все дела выиграны. Спасибо за игру!', x + 16, y + 92, G.PAL.stamp);
  if (G.UI.button(ctx, { x: x + w - 116, y: y + h - 28, w: 100, h: 18 }, 'В меню', { hotkey: next ? null : 'Enter' })) { G.Audio && G.Audio.music('menu'); G.setScene(G.UI.CaseSelectScene || G.UI.TitleScene); }
}

function drawPause(ctx) {
  G.dither(ctx, 0, 0, G.W, G.H, G.PAL.black, 10);
  G.Font.draw(ctx, 'ПЕРЕРЫВ', G.W / 2, 50, G.RAMP.gold[4], { font: 'big', align: 'center' });
  const bx = G.W / 2 - 70;
  if (G.UI.button(ctx, { x: bx, y: 76, w: 140, h: 18 }, 'Продолжить', { kind: 'primary' })) S.paused = false;
  if (G.UI.button(ctx, { x: bx, y: 100, w: 140, h: 18 }, 'Папка дела', {})) { S.paused = false; S.record = { open: true, sel: 0, page: 0, mode: 'view', purpose: 'view' }; }
  if (G.UI.button(ctx, { x: bx, y: 124, w: 140, h: 18 }, 'Начать дело заново', {})) { S.paused = false; G.startCase(S.idx); }
  if (G.UI.button(ctx, { x: bx, y: 148, w: 140, h: 18 }, 'Выйти в меню', { kind: 'danger' })) { S.paused = false; G.Audio && G.Audio.music('menu'); G.setScene(G.UI.TitleScene); }
}

/* ================== API ================== */
G.CourtScene = Court;
G.startCase = function (i) {
  i = G.clamp(i | 0, 0, G.Cases.length - 1);
  G.Save.data.progress = { case: i }; G.Save.save();
  G.fx.fade = 0;
  G.setScene(Court, i);
};
/* отладка и автотест */
G._dbg = {
  S: () => S,
  cross: a => crossAction(a),
  force: o => { S.force = Object.assign(S.force || {}, o); },
};
})();
