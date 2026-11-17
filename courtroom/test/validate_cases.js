#!/usr/bin/env node
/* Валидатор сценариев G.Cases (src/cases.js) по CONTRACT.md.
   Запуск: node test/validate_cases.js            */
'use strict';
const path = require('path');
global.window = { G: {} };
require(path.join(__dirname, '..', 'src', 'cases.js'));
const G = window.G;

const errors = [], warns = [];
const err = (where, msg) => errors.push(where + ': ' + msg);
const warn = (where, msg) => warns.push(where + ': ' + msg);

/* ---------- разрешённые значения из контракта ---------- */
const range = (p, n) => Array.from({ length: n }, (_, i) => p + (i + 1));
const WITNESSES = ['hollis', 'crane', 'bell', 'morales', 'holloway'];
const DEFENDANTS = ['lomax', 'whitfield', 'park', 'doyle'];
const ISO_ONLY = [...range('juror', 6), ...range('spectator', 12), 'reporter'];
const CAST = ['player', 'judge', 'prosecutor', 'clerk', 'bailiff', 'foreperson', ...WITNESSES, ...DEFENDANTS, ...ISO_ONLY];
const EMO = {
  player: ['normal', 'think', 'confident', 'shocked', 'point', 'slam'],
  judge: ['normal', 'stern', 'surprised', 'smile'],
  prosecutor: ['normal', 'smirk', 'angry', 'shocked', 'point'],
  clerk: ['normal'], bailiff: ['normal'], foreperson: ['normal'],
};
WITNESSES.forEach(w => EMO[w] = ['normal', 'nervous', 'angry', 'shocked', 'breakdown']);
DEFENDANTS.forEach(d => EMO[d] = ['normal', 'worried', 'hopeful', 'relieved']);
const ANIMS = { judge: ['gavel'], prosecutor: ['slam'] };
WITNESSES.forEach(w => ANIMS[w] = ['breakdown']);
const SHOTS = ['judge', 'witness', 'defense', 'prosecution', 'jury', 'visit', 'defendant'];
const CAMS = ['wide', 'judge', 'witness', 'defense', 'prosecution', 'jury'];
const MUSIC = ['menu', 'court', 'cross', 'pressure', 'victory', 'defeat', 'suspense', 'silence'];
const SFX = ['gavel', 'gavel3', 'objection', 'stamp', 'paper', 'evidence', 'crowd', 'crowdHush', 'door', 'damage', 'shock',
  'slam', 'select', 'cancel', 'typewriter', 'heartbeat', 'jail', 'itemget'];
const SHOUTS = ['objection', 'contradiction', 'sustained', 'overruled', 'evidence'];
const MOODS = ['whisper', 'gasp', 'murmur', 'angry', 'cheer', 'clap', 'laugh', 'shout'];
const ICONS = ['logbook', 'photo', 'document', 'key', 'coat', 'ticket', 'report', 'canister', 'video', 'knife', 'policy', 'map',
  'phone', 'receipt', 'badge', 'letter', 'fingerprint', 'autopsy', 'watch', 'glass', 'laptop', 'bag', 'paint', 'violin', 'bread',
  'cctv', 'camera', 'money', 'pills', 'keycard'];
const SPOTS = ['judge', 'witness', 'defense', 'defendant', 'prosecution', 'clerk', 'bailiff', 'reporter', 'jury', 'gallery'];
const COMMANDS = ['say', 'think', 'narrate', 'shot', 'wide', 'cam', 'music', 'sfx', 'shout', 'anim', 'enter', 'leave', 'evidence',
  'doc', 'title', 'testimony', 'present', 'choice', 'objection', 'penalty', 'verdict', 'wait', 'crowd', 'emo'];
const LOUD = ['angry', 'cheer', 'clap', 'shout'];
const MAX_SAY = 260;   // символов в одной реплике (панель диалога ~4 строки)

const stats = [];

/* ---------- проверка одной команды ---------- */
function checkCmd(cs, c, where, ctx) {
  if (!c || typeof c !== 'object' || Array.isArray(c)) { err(where, 'команда не объект: ' + JSON.stringify(c)); return; }
  if (!COMMANDS.includes(c.c)) { err(where, 'неизвестная команда ' + c.c); return; }
  const has = id => !!cs.evidence[id];
  ctx.stat.cmds++;
  switch (c.c) {
    case 'say': {
      if (!CAST.includes(c.who)) err(where, 'say: неизвестный who ' + c.who);
      else if (ISO_ONLY.includes(c.who)) err(where, 'say: у ' + c.who + ' нет бюста');
      if (typeof c.text !== 'string' || !c.text) err(where, 'say: пустой текст');
      else {
        if (c.text.replace(/\{p\}|\*/g, '').length > MAX_SAY) warn(where, 'say: длинная реплика (' + c.text.length + ')');
        if ((c.text.match(/\*/g) || []).length % 2) err(where, 'say: непарные * в ' + c.text.slice(0, 40));
      }
      if (c.emo !== undefined && EMO[c.who] && !EMO[c.who].includes(c.emo)) err(where, 'say: эмоция ' + c.emo + ' недопустима для ' + c.who);
      if (c.shot !== undefined && !SHOTS.includes(c.shot)) err(where, 'say: неизвестный shot ' + c.shot);
      if (c.anim !== undefined && !(ANIMS[c.who] || []).includes(c.anim)) err(where, 'say: anim ' + c.anim + ' недопустим для ' + c.who);
      ctx.stat.lines++;
      break;
    }
    case 'think': case 'narrate':
      if (!c.text) err(where, c.c + ': пустой текст'); else if (c.text.length > MAX_SAY) warn(where, c.c + ': длинный текст');
      ctx.stat.lines++; break;
    case 'shot': if (!SHOTS.includes(c.id)) err(where, 'shot: ' + c.id); break;
    case 'cam': if (!CAMS.includes(c.id)) err(where, 'cam: ' + c.id); break;
    case 'music': if (!MUSIC.includes(c.id)) err(where, 'music: ' + c.id); break;
    case 'sfx': if (!SFX.includes(c.id)) err(where, 'sfx: ' + c.id); break;
    case 'shout':
      if (!SHOUTS.includes(c.kind)) err(where, 'shout kind: ' + c.kind);
      if (c.who && !CAST.includes(c.who)) err(where, 'shout who: ' + c.who);
      break;
    case 'anim':
      if (!(ANIMS[c.who] || []).includes(c.id)) err(where, 'anim ' + c.id + ' недопустим для ' + c.who);
      if (c.id === 'breakdown') ctx.breakdowns++;
      break;
    case 'emo': if (EMO[c.who] && !EMO[c.who].includes(c.emo)) err(where, 'emo ' + c.emo + ' для ' + c.who); break;
    case 'enter':
      if (!CAST.includes(c.who)) err(where, 'enter: неизвестный who ' + c.who);
      if (!SPOTS.includes(c.spot) && !/^(jury|gallery)\d+$/.test(c.spot)) err(where, 'enter: неизвестный spot ' + c.spot);
      break;
    case 'leave': if (!CAST.includes(c.who)) err(where, 'leave: ' + c.who); break;
    case 'evidence':
      if (!has(c.id)) err(where, 'evidence: нет улики ' + c.id);
      ctx.sure.add(c.id); break;
    case 'doc':
      if (!has(c.id)) err(where, 'doc: нет улики ' + c.id);
      else if (!cs.evidence[c.id].doc) err(where, 'doc: у улики ' + c.id + ' нет doc');
      break;
    case 'title': if (!c.text) err(where, 'title без текста'); break;
    case 'testimony': {
      const t = cs.testimonies[c.id];
      if (!t) { err(where, 'нет показаний ' + c.id); break; }
      ctx.usedT.add(c.id);
      checkTestimony(cs, c.id, t, ctx);
      break;
    }
    case 'present':
      if (!has(c.answer)) err(where, 'present: нет улики ' + c.answer);
      else if (!ctx.sure.has(c.answer)) err(where, 'present: улика ' + c.answer + ' может быть ещё не получена');
      walk(cs, c.ok, where + '.ok', ctx);
      walk(cs, c.fail, where + '.fail', ctx);
      ctx.stat.presents++;
      break;
    case 'choice': {
      const opts = c.options || [];
      if (opts.length < 2 || opts.length > 4) err(where, 'choice: нужно 2–4 варианта');
      if (opts.filter(o => o.ok).length !== 1) err(where, 'choice: ровно один верный вариант');
      opts.forEach((o, i) => walk(cs, o.then, where + '.opt' + i, ctx));
      ctx.stat.choices++;
      break;
    }
    case 'objection':
      if (c.by !== 'prosecutor') err(where, 'objection: by должен быть prosecutor');
      if (!['sustained', 'overruled'].includes(c.ruling)) err(where, 'objection: ruling ' + c.ruling);
      if (!/§|Пятая/.test(c.ground || '')) warn(where, 'objection без ссылки на статью');
      ctx.stat.objections++;
      break;
    case 'verdict': if (c.result !== 'not_guilty') err(where, 'verdict: ' + c.result); ctx.verdicts++; break;
    case 'crowd':
      if (!MOODS.includes(c.mood)) err(where, 'crowd mood: ' + c.mood);
      if (c.lines !== undefined && (!Array.isArray(c.lines) || c.lines.some(l => typeof l !== 'string' || l.length > 40)))
        err(where, 'crowd lines: массив коротких строк (≤40)');
      if (LOUD.includes(c.mood)) ctx.loud.push(where);
      ctx.stat.crowds++;
      break;
    case 'wait': if (!(c.s > 0)) err(where, 'wait без s'); break;
  }
}

function walk(cs, list, where, ctx) {
  if (list === undefined) return;
  if (!Array.isArray(list)) { err(where, 'ожидался массив команд'); return; }
  list.forEach((c, i) => checkCmd(cs, c, where + '[' + i + ']', ctx));
}

function checkTestimony(cs, id, t, ctx) {
  const where = cs.id + '.testimonies.' + id;
  if (!CAST.includes(t.witness)) err(where, 'witness ' + t.witness);
  if (!t.title) err(where, 'нет title');
  const st = t.statements || [];
  if (st.length < 4 || st.length > 6) err(where, 'нужно 4–6 показаний, есть ' + st.length);
  const hits = st.filter(s => s.hit);
  if (hits.length !== 1) err(where, 'должно быть ровно одно показание с hit, есть ' + hits.length);
  const local = new Set();
  st.forEach((s, i) => {
    if (!s.text) err(where + '.s' + i, 'нет текста');
    else if (s.text.length > 200) warn(where + '.s' + i, 'длинное показание');
    if (!s.press || !s.press.length) err(where + '.s' + i, 'нет press');
    if (s.add) { if (!cs.evidence[s.add]) err(where + '.s' + i, 'add: нет улики ' + s.add); else local.add(s.add); }
    walk(cs, s.press, where + '.s' + i + '.press', ctx);
  });
  hits.forEach(s => {
    const i = st.indexOf(s);
    if (!cs.evidence[s.hit]) err(where + '.s' + i, 'hit: нет улики ' + s.hit);
    else if (!ctx.sure.has(s.hit) && !local.has(s.hit)) err(where + '.s' + i, 'hit: улика ' + s.hit + ' недоступна к этому моменту');
    else if (!ctx.sure.has(s.hit)) warn(where + '.s' + i, 'hit ' + s.hit + ' добывается уточнением в этих же показаниях (честно, но требует press)');
    if (!s.hitScript || !s.hitScript.length) warn(where + '.s' + i, 'пустой hitScript');
    walk(cs, s.hitScript, where + '.s' + i + '.hitScript', ctx);
  });
  walk(cs, t.wrong, where + '.wrong', ctx);
  ctx.stat.statements += st.length;
  ctx.stat.testimonies++;
  // улики, добытые только через press, не считаются гарантированными для последующих шагов
  local.forEach(e => { if (!ctx.sure.has(e)) ctx.maybe.add(e); });
}

/* ---------- проход по делам ---------- */
if (!Array.isArray(G.Cases) || G.Cases.length !== 4) err('G.Cases', 'нужно 4 дела');
if (!G.CaseMeta || !G.CaseMeta.player || G.CaseMeta.player.name !== 'Дэниел Рид') err('G.CaseMeta', 'нет player');
const ids = new Set();
for (const cs of G.Cases || []) {
  const w = cs.id || '?';
  if (ids.has(cs.id)) err(w, 'повтор id'); ids.add(cs.id);
  for (const k of ['id', 'title', 'docket', 'caption', 'charges', 'defendant', 'witnesses', 'victim', 'date', 'summary', 'evidence', 'start', 'script', 'testimonies'])
    if (cs[k] === undefined) err(w, 'нет поля ' + k);
  if (!/^[A-Z]{2}-?\d{6}$/.test(cs.docket || '')) err(w, 'docket в формате ЛА: ' + cs.docket);
  if (!/2025/.test(cs.date || '')) err(w, 'дата не в 2025');
  if (!DEFENDANTS.includes(cs.defendant)) err(w, 'defendant ' + cs.defendant);
  (cs.witnesses || []).forEach(x => { if (!WITNESSES.includes(x)) err(w, 'witness ' + x); });
  (cs.charges || []).forEach((ch, i) => { if (!/^Cal\. Penal Code §/.test(ch.code) || !ch.title || !ch.text || !ch.max) err(w + '.charges' + i, 'неполная статья'); });
  for (const [eid, e] of Object.entries(cs.evidence || {})) {
    if (!e.name || !e.desc) err(w + '.evidence.' + eid, 'нет name/desc');
    if (!ICONS.includes(e.icon)) err(w + '.evidence.' + eid, 'icon ' + e.icon);
    if (e.doc) {
      if (!e.doc.title || !Array.isArray(e.doc.lines)) err(w + '.evidence.' + eid, 'doc без title/lines');
      if (e.doc.lines.length > 14) warn(w + '.evidence.' + eid, 'doc: больше 14 строк');
      e.doc.lines.forEach(l => { if (l.length > 56) warn(w + '.evidence.' + eid, 'doc: длинная строка «' + l + '»'); });
      (e.doc.stamps || []).forEach(s => { if (!['#b8262f', '#2d4478'].includes(s.color)) err(w + '.evidence.' + eid, 'цвет печати ' + s.color); });
    }
  }
  (cs.start || []).forEach(e => { if (!cs.evidence[e]) err(w + '.start', 'нет улики ' + e); });
  const ctx = {
    sure: new Set(cs.start || []), maybe: new Set(), usedT: new Set(), breakdowns: 0, verdicts: 0, loud: [],
    stat: { cmds: 0, lines: 0, statements: 0, testimonies: 0, presents: 0, choices: 0, objections: 0, crowds: 0 },
  };
  walk(cs, cs.script, w + '.script', ctx);
  for (const tid of Object.keys(cs.testimonies || {})) if (!ctx.usedT.has(tid)) err(w, 'показания ' + tid + ' не используются');
  if (ctx.breakdowns < 1) err(w, 'нет срыва (breakdown) настоящего виновника');
  if (ctx.verdicts !== 1) err(w, 'должен быть ровно один verdict');
  const last = (cs.script || []).map(c => c.c);
  if (last.indexOf('verdict') < last.lastIndexOf('testimony')) err(w, 'вердикт раньше последнего допроса');
  // после громкой реакции зала в основном сценарии должен быть молоток судьи
  cs.script.forEach((c, i) => {
    if (c.c === 'crowd' && LOUD.includes(c.mood)) {
      const next = cs.script.slice(i + 1, i + 4);
      if (!next.some(n => n.c === 'anim' && n.who === 'judge' && n.id === 'gavel') && !next.some(n => n.c === 'crowd'))
        warn(w + '.script[' + i + ']', 'громкая реакция без молотка судьи');
    }
  });
  stats.push({ id: cs.id, ...ctx.stat, evidence: Object.keys(cs.evidence).length });
}

/* ---------- отчёт ---------- */
console.log('Дело       команд  реплик  показ.  допр.  улик  предъяв.  выборов  протестов  реакций');
let tot = { cmds: 0, lines: 0, statements: 0 };
for (const s of stats) {
  console.log(s.id.padEnd(10), String(s.cmds).padStart(6), String(s.lines).padStart(7), String(s.statements).padStart(7),
    String(s.testimonies).padStart(6), String(s.evidence).padStart(5), String(s.presents).padStart(9), String(s.choices).padStart(8),
    String(s.objections).padStart(10), String(s.crowds).padStart(8));
  tot.cmds += s.cmds; tot.lines += s.lines; tot.statements += s.statements;
}
console.log('ИТОГО: команд ' + tot.cmds + ', реплик ' + tot.lines + ', показаний ' + tot.statements);
warns.forEach(x => console.log('WARN  ' + x));
errors.forEach(x => console.log('ERROR ' + x));
console.log(errors.length ? '\nОШИБОК: ' + errors.length : '\nOK: ошибок нет' + (warns.length ? ' (предупреждений: ' + warns.length + ')' : ''));
process.exit(errors.length ? 1 : 0);
