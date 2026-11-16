/* =====================================================================
   AUDIO — музыка и звуки, синтезируются в реальном времени (WebAudio).
   Свой маленький трекер: партитура записана нотами с длительностями
   в шестнадцатых, гармония — аккордами по тактам.
   G.Audio.music(id), G.Audio.sfx(id), G.Audio.blip(voice), G.Audio.unlock()
   ===================================================================== */
(function () {
'use strict';
const G = window.G;

let ac = null, master, musicBus, sfxBus, reverb, revSend, noiseBuf;
const waves = {};

function settings() { return (G.Save && G.Save.data && G.Save.data.settings) || { music: .7, sfx: .8 }; }

function init() {
  if (ac) return true;
  const AC = window.AudioContext || window.webkitAudioContext;
  if (!AC) return false;
  try { ac = new AC(); } catch (e) { return false; }
  master = ac.createGain(); master.gain.value = 0.9;
  const comp = ac.createDynamicsCompressor();
  comp.threshold.value = -14; comp.ratio.value = 3; comp.attack.value = 0.005; comp.release.value = 0.2;
  master.connect(comp).connect(ac.destination);
  musicBus = ac.createGain(); musicBus.connect(master);
  sfxBus = ac.createGain(); sfxBus.connect(master);
  // ревербератор зала суда: сгенерированный импульс
  reverb = ac.createConvolver();
  const len = Math.floor(ac.sampleRate * 2.2);
  const ir = ac.createBuffer(2, len, ac.sampleRate);
  for (let ch = 0; ch < 2; ch++) {
    const d = ir.getChannelData(ch);
    for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 3.2) * (i < 200 ? i / 200 : 1);
  }
  reverb.buffer = ir;
  revSend = ac.createGain(); revSend.gain.value = 0.28;
  revSend.connect(reverb).connect(master);
  // шум
  noiseBuf = ac.createBuffer(1, ac.sampleRate * 2, ac.sampleRate);
  const nd = noiseBuf.getChannelData(0);
  for (let i = 0; i < nd.length; i++) nd[i] = Math.random() * 2 - 1;
  // пульсовые волны
  for (const duty of [0.125, 0.25, 0.5]) {
    const n = 48, re = new Float32Array(n), im = new Float32Array(n);
    for (let k = 1; k < n; k++) re[k] = (2 / (k * Math.PI)) * Math.sin(Math.PI * k * duty);
    waves['p' + duty] = ac.createPeriodicWave(re, im);
  }
  applyVolumes();
  return true;
}
function applyVolumes() {
  if (!ac) return;
  const s = settings();
  musicBus.gain.value = (s.music ?? .7) * 0.9;
  sfxBus.gain.value = (s.sfx ?? .8) * 0.9;
}

/* ---------------- ноты ---------------- */
const NOTE = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
function midi(name) {
  const m = /^([A-G])(#|b)?(-?\d)$/.exec(name);
  if (!m) return null;
  return 12 * (+m[3] + 1) + NOTE[m[1]] + (m[2] === '#' ? 1 : m[2] === 'b' ? -1 : 0);
}
const freq = m => 440 * Math.pow(2, (m - 69) / 12);
const CHORD_Q = { '': [0, 4, 7], m: [0, 3, 7], '7': [0, 4, 7, 10], m7: [0, 3, 7, 10], maj7: [0, 4, 7, 11], dim: [0, 3, 6], sus4: [0, 5, 7], aug: [0, 4, 8], m6: [0, 3, 7, 9] };
function chord(name) {
  const m = /^([A-G])(#|b)?(.*)$/.exec(name);
  const root = NOTE[m[1]] + (m[2] === '#' ? 1 : m[2] === 'b' ? -1 : 0);
  return { root, iv: CHORD_Q[m[3]] || CHORD_Q[''] };
}

/* ---------------- инструменты ---------------- */
function env(g, t, a, peak, d, sus, rel, dur) {
  g.gain.setValueAtTime(0.0001, t);
  g.gain.linearRampToValueAtTime(peak, t + a);
  g.gain.linearRampToValueAtTime(peak * sus, t + a + d);
  const end = t + Math.max(dur, a + d);
  g.gain.setValueAtTime(peak * sus, end);
  g.gain.exponentialRampToValueAtTime(0.0001, end + rel);
  return end + rel;
}
function osc(type, f, t) {
  const o = ac.createOscillator();
  if (waves[type]) o.setPeriodicWave(waves[type]); else o.type = type;
  o.frequency.setValueAtTime(f, t);
  return o;
}
function noise(t) { const s = ac.createBufferSource(); s.buffer = noiseBuf; s.loop = true; return s; }

/* ---------------- СЭМПЛЕР: настоящие инструменты ----------------
   Банк FluidR3 GM (Frank Wen, CC BY 3.0), каждая нота записана отдельно.
   Файлы assets/sf/<инструмент>.json: { "C4": "<base64 mp3>", ... }        */
const SF_BASE = (window.G && G.ASSET_BASE || '') + 'assets/sf/';
const NAMES = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B'];
const noteName = m => NAMES[((m % 12) + 12) % 12] + (Math.floor(m / 12) - 1);
const SF = {};   // name -> { raw, bufs:{}, pending:{}, loading:Promise }
const RELEASE = { acoustic_grand_piano: .9, vibraphone: 1.2, celesta: 1.0, glockenspiel: 1.2, orchestral_harp: 1.5, pizzicato_strings: .4,
  tubular_bells: 2, timpani: 1.5, acoustic_bass: .25, contrabass: .3 };
function loadInst(name) {
  if (SF[name]) return SF[name].loading;
  const e = SF[name] = { raw: null, bufs: {}, pending: {} };
  e.loading = fetch(SF_BASE + name + '.json').then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(j => { e.raw = j; }).catch(() => { e.failed = true; });
  return e.loading;
}
function b64ToBuf(b64) {
  const bin = atob(b64), u = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);
  return u.buffer;
}
function decodeNote(name, m) {
  const e = SF[name]; if (!e || !e.raw) return Promise.resolve(null);
  const k = noteName(m);
  if (e.bufs[k]) return Promise.resolve(e.bufs[k]);
  if (e.pending[k]) return e.pending[k];
  if (!e.raw[k]) return Promise.resolve(null);
  return e.pending[k] = new Promise(res => {
    try { ac.decodeAudioData(b64ToBuf(e.raw[k]), b => { e.bufs[k] = b; res(b); }, () => res(null)); } catch (err) { res(null); }
  });
}
function sampleReady(name, m) { const e = SF[name]; return !!(e && e.bufs[noteName(m)]); }
function playSample(name, t, m, dur, vel, bus, rev) {
  const b = SF[name].bufs[noteName(m)];
  const src = ac.createBufferSource(); src.buffer = b;
  const g = ac.createGain();
  const peak = 1.6 * vel;
  g.gain.setValueAtTime(0.0001, t);
  g.gain.linearRampToValueAtTime(peak, t + 0.008);
  const rel = RELEASE[name] != null ? RELEASE[name] : 0.25;
  const end = Math.min(t + dur, t + b.duration);
  g.gain.setValueAtTime(peak, end);
  g.gain.exponentialRampToValueAtTime(0.0001, end + rel);
  src.connect(g); g.connect(bus); if (rev !== false) g.connect(revSend);
  src.start(t); src.stop(end + rel + 0.05);
}
/* подготовить все ноты песни заранее */
async function prepare(song, c) {
  const need = {};
  for (const e of c.ev) { const inst = song.parts && song.parts[e.inst]; if (inst && e.m != null) (need[inst] = need[inst] || new Set()).add(e.m); }
  await Promise.all(Object.keys(need).map(loadInst));
  const jobs = [];
  for (const [inst, set] of Object.entries(need)) for (const m of set) jobs.push(decodeNote(inst, m));
  await Promise.all(jobs);
}

const INST = {
  lead(t, m, dur, vel, bus) {           // пульс 25% с вибрато — главный голос
    const g = ac.createGain(), f = ac.createBiquadFilter();
    f.type = 'lowpass'; f.frequency.value = 3200; f.Q.value = 0.5;
    const o = osc('p0.25', freq(m), t);
    const lfo = ac.createOscillator(), lg = ac.createGain();
    lfo.frequency.value = 5.5; lg.gain.setValueAtTime(0, t); lg.gain.linearRampToValueAtTime(freq(m) * 0.012, t + Math.min(0.35, dur));
    lfo.connect(lg).connect(o.frequency);
    o.connect(f).connect(g); g.connect(bus); g.connect(revSend);
    const end = env(g, t, 0.01, 0.16 * vel, 0.08, 0.7, 0.12, dur);
    o.start(t); lfo.start(t); o.stop(end + 0.05); lfo.stop(end + 0.05);
  },
  flute(t, m, dur, vel, bus) {          // треугольник + октава синусом — мягкая тема меню
    const g = ac.createGain();
    const o = osc('triangle', freq(m), t), o2 = osc('sine', freq(m) * 2, t), g2 = ac.createGain();
    g2.gain.value = 0.25;
    const lfo = ac.createOscillator(), lg = ac.createGain();
    lfo.frequency.value = 4.8; lg.gain.setValueAtTime(0, t); lg.gain.linearRampToValueAtTime(freq(m) * 0.01, t + Math.min(0.4, dur));
    lfo.connect(lg); lg.connect(o.frequency); lg.connect(o2.frequency);
    o.connect(g); o2.connect(g2).connect(g); g.connect(bus); g.connect(revSend);
    const end = env(g, t, 0.04, 0.28 * vel, 0.1, 0.8, 0.25, dur);
    for (const x of [o, o2, lfo]) { x.start(t); x.stop(end + 0.05); }
  },
  brass(t, m, dur, vel, bus) {          // «медь»: пила через фильтр с раскрытием
    const g = ac.createGain(), f = ac.createBiquadFilter();
    f.type = 'lowpass'; f.Q.value = 2;
    f.frequency.setValueAtTime(400, t); f.frequency.linearRampToValueAtTime(2400, t + 0.06); f.frequency.linearRampToValueAtTime(1300, t + 0.3);
    const o = osc('sawtooth', freq(m), t), o2 = osc('sawtooth', freq(m) * 1.004, t);
    o.connect(f); o2.connect(f); f.connect(g); g.connect(bus); g.connect(revSend);
    const end = env(g, t, 0.03, 0.1 * vel, 0.15, 0.75, 0.18, dur);
    for (const x of [o, o2]) { x.start(t); x.stop(end + 0.05); }
  },
  bass(t, m, dur, vel, bus) {
    const g = ac.createGain(), f = ac.createBiquadFilter();
    f.type = 'lowpass'; f.frequency.value = 900;
    const o = osc('triangle', freq(m), t), o2 = osc('p0.5', freq(m), t), g2 = ac.createGain();
    g2.gain.value = 0.18;
    o.connect(g); o2.connect(g2).connect(f).connect(g); g.connect(bus);
    const end = env(g, t, 0.005, 0.42 * vel, 0.1, 0.6, 0.06, dur * 0.9);
    for (const x of [o, o2]) { x.start(t); x.stop(end + 0.05); }
  },
  arp(t, m, dur, vel, bus) {
    const g = ac.createGain(), f = ac.createBiquadFilter();
    f.type = 'lowpass'; f.frequency.value = 2600;
    const o = osc('p0.125', freq(m), t);
    o.connect(f).connect(g); g.connect(bus); g.connect(revSend);
    const end = env(g, t, 0.003, 0.07 * vel, 0.06, 0.3, 0.05, Math.min(dur, 0.1));
    o.start(t); o.stop(end + 0.05);
  },
  pad(t, m, dur, vel, bus) {
    const g = ac.createGain(), f = ac.createBiquadFilter();
    f.type = 'lowpass'; f.frequency.value = 1100; f.Q.value = 0.3;
    const os = [-7, 0, 7].map(c => { const o = osc('sawtooth', freq(m) * Math.pow(2, c / 1200), t); o.connect(f); return o; });
    f.connect(g); g.connect(bus); g.connect(revSend);
    const end = env(g, t, Math.min(0.5, dur * 0.4), 0.045 * vel, 0.3, 0.85, 0.6, dur);
    for (const o of os) { o.start(t); o.stop(end + 0.05); }
  },
  bell(t, m, dur, vel, bus) {           // колокольчик (FM)
    const g = ac.createGain();
    const car = osc('sine', freq(m), t), mod = osc('sine', freq(m) * 3.5, t), mg = ac.createGain();
    mg.gain.setValueAtTime(freq(m) * 2, t); mg.gain.exponentialRampToValueAtTime(1, t + 1.2);
    mod.connect(mg).connect(car.frequency); car.connect(g); g.connect(bus); g.connect(revSend);
    g.gain.setValueAtTime(0.0001, t); g.gain.linearRampToValueAtTime(0.14 * vel, t + 0.005); g.gain.exponentialRampToValueAtTime(0.0001, t + 1.6);
    car.start(t); mod.start(t); car.stop(t + 1.7); mod.stop(t + 1.7);
  },
  kick(t, m, dur, vel, bus) {
    const g = ac.createGain(), o = osc('sine', 150, t);
    o.frequency.exponentialRampToValueAtTime(42, t + 0.18);
    g.gain.setValueAtTime(0.7 * vel, t); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.3);
    o.connect(g).connect(bus); o.start(t); o.stop(t + 0.32);
  },
  snare(t, m, dur, vel, bus) {
    const n = noise(t), f = ac.createBiquadFilter(), g = ac.createGain();
    f.type = 'highpass'; f.frequency.value = 1400;
    g.gain.setValueAtTime(0.28 * vel, t); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.16);
    n.connect(f).connect(g); g.connect(bus); g.connect(revSend); n.start(t); n.stop(t + 0.18);
    const o = osc('triangle', 190, t), og = ac.createGain();
    o.frequency.exponentialRampToValueAtTime(120, t + 0.08);
    og.gain.setValueAtTime(0.25 * vel, t); og.gain.exponentialRampToValueAtTime(0.0001, t + 0.1);
    o.connect(og).connect(bus); o.start(t); o.stop(t + 0.12);
  },
  hat(t, m, dur, vel, bus) {
    const n = noise(t), f = ac.createBiquadFilter(), g = ac.createGain();
    f.type = 'highpass'; f.frequency.value = 7500;
    g.gain.setValueAtTime(0.09 * vel, t); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.045);
    n.connect(f).connect(g).connect(bus); n.start(t); n.stop(t + 0.06);
  },
  timp(t, m, dur, vel, bus) {           // литавры
    const g = ac.createGain(), o = osc('sine', freq(m), t), o2 = osc('sine', freq(m) * 1.5, t), g2 = ac.createGain();
    o.frequency.exponentialRampToValueAtTime(freq(m) * 0.96, t + 0.4);
    g2.gain.value = 0.3;
    const n = noise(t), nf = ac.createBiquadFilter(), ng = ac.createGain();
    nf.type = 'lowpass'; nf.frequency.value = 500;
    ng.gain.setValueAtTime(0.25 * vel, t); ng.gain.exponentialRampToValueAtTime(0.0001, t + 0.08);
    n.connect(nf).connect(ng).connect(bus); n.start(t); n.stop(t + 0.1);
    g.gain.setValueAtTime(0.5 * vel, t); g.gain.exponentialRampToValueAtTime(0.0001, t + 1.1);
    o.connect(g); o2.connect(g2).connect(g); g.connect(bus); g.connect(revSend);
    o.start(t); o2.start(t); o.stop(t + 1.2); o2.stop(t + 1.2);
  },
};

/* ---------------- партитуры ----------------
   mel: "A4:6 D5:2 r:4 ..." — нота:длительность в шестнадцатых
   chords: по одному аккорду на такт (или 'Gm A' — два на такт)
   bass/arp/pad/drums — генерируются стилями из гармонии
*/
const SONGS = {
  /* Главная тема: нуарная джазовая баллада — труба с сурдиной, рояль, контрабас щипком, струнные, щётки */
  menu: {
    bpm: 76,
    parts: { lead: 'muted_trumpet', counter: 'cello', bass: 'acoustic_bass', arp: 'acoustic_grand_piano', pad: 'string_ensemble_1', bell: 'vibraphone', timp: 'timpani' },
    chords: ['Dm7', 'Bbmaj7', 'Gm7', 'A7', 'Dm7', 'Fmaj7', 'Gm7 A7', 'Dm7'],
    mel: [
      'A4:6 D5:2 F5:4 E5:2 D5:2', 'D5:6 C5:2 Bb4:4 A4:4', 'G4:6 Bb4:2 D5:4 C5:2 Bb4:2', 'A4:12 r:4',
      'A4:6 D5:2 F5:4 G5:2 A5:2', 'C6:6 Bb5:2 A5:4 F5:4', 'G5:4 F5:2 E5:2 E5:4 C#5:4', 'D5:12 r:4',
    ],
    counter: ['r:16', 'r:16', 'r:16', 'r:8 E3:4 C#3:4', 'F3:8 A3:8', 'A3:8 C4:8', 'Bb3:8 A3:8', 'F3:12 r:4'],
    bass: 'walk', arp: 'comp', pad: true, drums: 'brush',
  },
  /* Заседание: размеренная тема — пиццикато, рояль, валторна, литавры */
  court: {
    bpm: 100,
    parts: { lead: 'french_horn', counter: 'cello', bass: 'contrabass', arp: 'pizzicato_strings', pad: 'string_ensemble_1', timp: 'timpani', bell: 'orchestral_harp' },
    chords: ['Am', 'G', 'F', 'E', 'Am', 'Dm', 'E7', 'Am'],
    mel: [
      'E4:2 A4:2 B4:2 C5:4 B4:2 A4:2 E4:2', 'D4:2 G4:2 A4:2 B4:4 A4:2 G4:2 D4:2',
      'C4:2 F4:2 G4:2 A4:4 G4:2 F4:2 C4:2', 'B3:4 E4:4 G#4:4 B4:4',
      'C5:4 B4:2 A4:2 E4:4 A4:4', 'D5:4 C5:2 B4:2 A4:4 F4:4',
      'E4:2 F4:2 G#4:2 A4:2 B4:4 G#4:4', 'A4:8 r:4 E4:4',
    ],
    counter: ['A2:8 C3:8', 'B2:8 D3:8', 'A2:8 C3:8', 'G#2:8 B2:8', 'E3:8 C3:8', 'F3:8 D3:8', 'E3:8 D3:8', 'C3:12 r:4'],
    bass: 'half', arp: 'eighths', pad: true, drums: 'timp',
  },
  /* Перекрёстный допрос: рояль-остинато, пиццикато шестнадцатыми, труба, контрабас, малый барабан */
  cross: {
    bpm: 128,
    parts: { lead: 'trumpet', counter: 'trombone', bass: 'acoustic_bass', arp: 'acoustic_grand_piano', pad: 'tremolo_strings', timp: 'timpani' },
    chords: ['Em', 'C', 'D', 'B', 'Em', 'C', 'Am', 'B7'],
    mel: [
      'B4:2 E5:2 G5:2 B5:4 A5:2 G5:2 F#5:2', 'E5:2 G5:2 C6:4 B5:2 A5:2 G5:4',
      'F#5:2 A5:2 D6:4 C6:2 B5:2 A5:4', 'B5:6 A5:2 G5:2 F#5:2 D#5:4',
      'E5:2 E5:1 F#5:1 G5:2 B5:2 E6:4 D6:2 B5:2', 'C6:4 B5:2 G5:2 E5:4 G5:4',
      'A5:2 C6:2 E6:4 D6:2 C6:2 B5:2 A5:2', 'B5:8 D#6:4 F#6:4',
    ],
    counter: ['G3:16', 'G3:16', 'A3:16', 'F#3:16', 'G3:8 B3:8', 'E3:8 G3:8', 'E3:8 A3:8', 'F#3:8 D#3:8'],
    bass: 'pump', arp: 'sixteenths', pad: true, drums: 'drive',
  },
  /* Давление: тремоло струнных, медь, литавры — свидетель загнан в угол */
  pressure: {
    bpm: 146,
    parts: { lead: 'trumpet', counter: 'french_horn', bass: 'contrabass', arp: 'pizzicato_strings', pad: 'tremolo_strings', timp: 'timpani' },
    chords: ['Gm', 'Eb', 'F', 'D', 'Gm', 'Eb', 'Cm', 'D7'],
    mel: [
      'G5:1 D5:1 G5:1 A5:1 Bb5:2 A5:2 G5:2 D5:2 Bb4:2 D5:2', 'G5:1 Eb5:1 G5:1 A5:1 Bb5:2 C6:2 Bb5:2 G5:2 Eb5:4',
      'A5:1 F5:1 A5:1 Bb5:1 C6:2 D6:2 C6:2 A5:2 F5:4', 'F#5:4 A5:4 D6:4 C6:2 A5:2',
      'Bb5:2 A5:2 G5:2 D5:2 G5:2 A5:2 Bb5:2 D6:2', 'Eb6:4 D6:2 C6:2 Bb5:4 G5:4',
      'C6:2 Eb6:2 G6:4 F6:2 Eb6:2 D6:2 C6:2', 'D6:4 C6:2 A5:2 F#5:4 D5:4',
    ],
    counter: ['D4:16', 'Eb4:16', 'F4:16', 'F#4:16', 'G4:16', 'G4:16', 'G4:16', 'F#4:16'],
    bass: 'sixteen', arp: 'sixteenths', pad: true, drums: 'hard',
  },
  /* Напряжение: челеста, арфа, струнные, тихий хор */
  suspense: {
    bpm: 64,
    parts: { lead: 'celesta', counter: 'choir_aahs', bass: 'contrabass', bell: 'orchestral_harp', pad: 'string_ensemble_1' },
    chords: ['Cm', 'Ab', 'Fm', 'G', 'Cm', 'Ab', 'Fm', 'G7'],
    mel: [
      'r:8 G5:4 Ab5:4', 'G5:12 r:4', 'F5:4 Eb5:4 D5:4 C5:4', 'B4:12 r:4',
      'r:8 Eb5:4 F5:4', 'G5:8 Ab5:4 C6:4', 'B5:4 Ab5:4 G5:4 F5:4', 'D5:12 r:4',
    ],
    counter: ['C4:16', 'C4:16', 'C4:16', 'B3:16', 'G4:16', 'Ab4:16', 'F4:16', 'G4:16'],
    bass: 'whole', arp: 'harp', pad: true, drums: 'heart',
  },
  /* Победа: фанфара меди, струнные, литавры, колокольчики */
  victory: {
    bpm: 120,
    parts: { lead: 'trumpet', counter: 'french_horn', bass: 'contrabass', arp: 'string_ensemble_1', pad: 'string_ensemble_1', bell: 'glockenspiel', timp: 'timpani' },
    chords: ['C', 'F', 'G', 'C', 'Am', 'F', 'G', 'C'],
    mel: [
      'G4:2 C5:2 E5:2 G5:6 E5:2 G5:2', 'A5:6 G5:2 F5:4 A5:4', 'G5:4 D5:2 E5:2 F5:4 B4:4', 'E5:2 G5:2 C6:8 r:4',
      'E5:2 A5:2 C6:4 B5:2 A5:2 E5:4', 'F5:2 A5:2 C6:4 D6:2 C6:2 A5:4', 'B5:4 C6:2 D6:2 G5:4 B5:4', 'C6:12 r:4',
    ],
    counter: ['E4:8 G4:8', 'F4:8 C5:8', 'D4:8 B4:8', 'C5:8 G4:8', 'C5:8 E4:8', 'A4:8 F4:8', 'G4:8 D5:8', 'E5:12 r:4'],
    bass: 'half', arp: 'none', pad: true, drums: 'timp', bells: true,
  },
  /* Поражение: рояль и виолончель */
  defeat: {
    bpm: 58,
    parts: { lead: 'cello', bass: 'contrabass', arp: 'acoustic_grand_piano', pad: 'string_ensemble_1' },
    chords: ['Am', 'F', 'Dm', 'E'],
    mel: ['E4:8 C4:8', 'C4:8 A3:8', 'D4:6 F4:2 E4:4 D4:4', 'B3:12 r:4'],
    bass: 'whole', arp: 'broken', pad: true, drums: 'none',
  },
  /* Комната свиданий: одинокий рояль и саксофон */
  visit: {
    bpm: 70,
    parts: { lead: 'tenor_sax', bass: 'acoustic_bass', arp: 'acoustic_grand_piano', pad: 'string_ensemble_1' },
    chords: ['Fmaj7', 'Em7', 'Dm7', 'Cmaj7', 'Fmaj7', 'Em7', 'Dm7 G7', 'Cmaj7'],
    mel: [
      'A4:4 C5:4 E5:6 D5:2', 'B4:8 r:4 G4:4', 'A4:4 F4:2 A4:2 C5:6 B4:2', 'G4:12 r:4',
      'A4:4 C5:4 F5:6 E5:2', 'D5:6 C5:2 B4:4 G4:4', 'F4:4 A4:4 B4:4 D5:4', 'C5:12 r:4',
    ],
    bass: 'walk', arp: 'comp', pad: false, drums: 'brush',
  },
};
/* компиляция песни в события */
function compile(song) {
  const ev = [];
  const bars = song.chords.length;
  const addLine = (lines, inst, vel, oct = 0) => {
    if (!lines) return;
    lines.forEach((bar, bi) => {
      let step = bi * 16;
      for (const tok of bar.trim().split(/\s+/)) {
        const [n, d] = tok.split(':'); const dur = +d || 1;
        if (n !== 'r') { const m = midi(n); if (m != null) ev.push({ step, dur, m: m + oct, inst, vel }); }
        step += dur;
      }
    });
  };
  addLine(song.mel, 'lead', 1);
  addLine(song.counter, 'counter', 0.6);
  song.chords.forEach((cname, bi) => {
    const parts = cname.split(' ');
    parts.forEach((cn, pi) => {
      const ch = chord(cn), len = 16 / parts.length, s0 = bi * 16 + pi * len;
      const root = 36 + ch.root, tones = ch.iv.map(i => 48 + ch.root + i);
      // бас
      if (song.bass === 'half') { for (let k = 0; k < len; k += 8) ev.push({ step: s0 + k, dur: 7, m: k ? root + 7 : root, inst: 'bass', vel: .9 }); }
      if (song.bass === 'whole') ev.push({ step: s0, dur: len, m: root, inst: 'bass', vel: .9 });
      if (song.bass === 'walk') { const w = [0, 0, 7, 0, 12, 7, 3 + (ch.iv[1] - 3), 7]; for (let k = 0; k < len; k += 2) ev.push({ step: s0 + k, dur: 2, m: root + w[(k / 2) % 8], inst: 'bass', vel: k % 4 ? .7 : 1 }); }
      if (song.bass === 'pump') { for (let k = 0; k < len; k += 2) ev.push({ step: s0 + k, dur: 1, m: root + (k % 4 ? 12 : 0), inst: 'bass', vel: k % 4 ? .7 : 1 }); }
      if (song.bass === 'sixteen') { for (let k = 0; k < len; k++) ev.push({ step: s0 + k, dur: 1, m: root + (k % 8 === 6 ? 7 : 0), inst: 'bass', vel: k % 4 ? .6 : 1 }); }
      // арпеджио
      const at = tones.concat(tones.map(x => x + 12));
      if (song.arp === 'broken') { const o = [0, 1, 2, 3, 2, 1]; for (let k = 0; k < len; k += 2) ev.push({ step: s0 + k, dur: 2, m: at[o[(k / 2) % o.length]] + 12, inst: 'arp', vel: .8 }); }
      if (song.arp === 'eighths') { for (let k = 0; k < len; k += 2) ev.push({ step: s0 + k, dur: 2, m: at[(k / 2) % at.length] + 12, inst: 'arp', vel: .7 }); }
      if (song.arp === 'sixteenths') { const o = [0, 1, 2, 1, 3, 2, 1, 2]; for (let k = 0; k < len; k++) ev.push({ step: s0 + k, dur: 1, m: at[o[k % 8]] + 12, inst: 'arp', vel: k % 4 ? .55 : .9 }); }
      if (song.arp === 'bells') { ev.push({ step: s0 + 4, dur: 4, m: at[2] + 24, inst: 'bell', vel: .5 }); }
      if (song.arp === 'comp') { for (const k of [0, 6, 10]) if (k < len) for (const tn of tones) ev.push({ step: s0 + k, dur: k ? 2 : 4, m: tn + 12, inst: 'arp', vel: k ? .45 : .6 }); }
      if (song.arp === 'harp') { at.concat(at.map(x => x + 12)).forEach((tn, q) => { if (q * 1 < len) ev.push({ step: s0 + q, dur: 4, m: tn, inst: 'bell', vel: .45 }); }); }
      if (song.bells && pi === 0) [0, 4, 8, 12].forEach(k => ev.push({ step: s0 + k, dur: 2, m: tones[(k / 4) % tones.length] + 24, inst: 'bell', vel: .35 }));
      // пэд
      if (song.pad) for (const tn of tones) ev.push({ step: s0, dur: len, m: tn, inst: 'pad', vel: .8 });
      // ударные
      for (let k = 0; k < len; k++) {
        const s = s0 + k, b = (bi * 16 + pi * len + k) % 16;
        if (song.drums === 'march') { if (b === 0 || b === 8) ev.push({ step: s, inst: 'kick', vel: 1 }); if (b === 4 || b === 12) ev.push({ step: s, inst: 'snare', vel: .8 }); if (b % 2 === 0) ev.push({ step: s, inst: 'hat', vel: b % 4 ? .5 : .9 }); }
        if (song.drums === 'drive') { if (b % 4 === 0) ev.push({ step: s, inst: 'kick', vel: 1 }); if (b === 4 || b === 12) ev.push({ step: s, inst: 'snare', vel: 1 }); ev.push({ step: s, inst: 'hat', vel: b % 2 ? .4 : .8 }); }
        if (song.drums === 'hard') { if (b % 4 === 0 || b === 10) ev.push({ step: s, inst: 'kick', vel: 1 }); if (b === 4 || b === 12 || b === 15) ev.push({ step: s, inst: 'snare', vel: b === 15 ? .5 : 1 }); ev.push({ step: s, inst: 'hat', vel: b % 2 ? .5 : .9 }); }
        if (song.drums === 'timp') { if (b === 0 && bi % 2 === 0) ev.push({ step: s, m: 38 + ch.root % 12, inst: 'timp', vel: .8 }); if (b === 0 && bi % 2 === 1) ev.push({ step: s, m: 45 + ch.root % 7, inst: 'timp', vel: .5 }); if (bi === bars - 2 && b >= 12) ev.push({ step: s, m: 45, inst: 'timp', vel: .4 + (b - 12) * .12 }); }
        if (song.drums === 'brush') { if (b === 4 || b === 12) ev.push({ step: s, inst: 'snare', vel: .25 }); if (b % 4 === 0 || b % 4 === 3) ev.push({ step: s, inst: 'hat', vel: b % 4 ? .35 : .55 }); if (b === 0) ev.push({ step: s, inst: 'kick', vel: .35 }); }
        if (song.drums === 'heart') { if (b === 0) ev.push({ step: s, inst: 'kick', vel: .9 }); if (b === 3) ev.push({ step: s, inst: 'kick', vel: .6 }); }
      }
    });
  });
  ev.sort((a, b) => a.step - b.step);
  return { ev, steps: bars * 16, stepDur: 60 / song.bpm / 4 };
}
const compiled = {};

/* ---------------- плеер ---------------- */
const FALLBACK = { lead: 'lead', counter: 'brass', bass: 'bass', arp: 'arp', pad: 'pad', bell: 'bell', timp: 'timp' };
const VOL = { lead: 1.0, counter: .7, bass: 1.1, arp: .55, pad: .32, bell: .6, timp: .9 };
let cur = null, curId = null, timer = null;
function schedule() {
  if (!cur || !ac) return;
  const ahead = ac.currentTime + 0.25;
  while (true) {
    const e = cur.c.ev[cur.i];
    const loopT = cur.t0 + cur.loop * cur.c.steps * cur.c.stepDur;
    if (!e) { cur.loop++; cur.i = 0; continue; }
    const t = loopT + e.step * cur.c.stepDur;
    if (t > ahead) break;
    if (t >= ac.currentTime - 0.05) {
      const dur = (e.dur || 1) * cur.c.stepDur;
      const smp = cur.song.parts && cur.song.parts[e.inst];
      try {
        if (smp && e.m != null && sampleReady(smp, e.m)) playSample(smp, t, e.m, dur, (e.vel || 1) * (VOL[e.inst] || 1), cur.bus);
        else if (!smp || !SF[smp] || SF[smp].failed) INST[FALLBACK[e.inst] || e.inst](t, e.m, dur, e.vel || 1, cur.bus);
      } catch (err) {}
    }
    cur.i++;
  }
}
function stopMusic(fade = 0.6) {
  if (!cur) return;
  const old = cur; cur = null;
  try {
    old.bus.gain.setValueAtTime(old.bus.gain.value, ac.currentTime);
    old.bus.gain.linearRampToValueAtTime(0.0001, ac.currentTime + fade);
    setTimeout(() => old.bus.disconnect(), fade * 1000 + 3000);
  } catch (e) {}
}

let pendingMusic = null;
const A = G.Audio = {
  current: () => curId,
  unlock() {
    if (!init()) return;
    if (ac.state === 'suspended') ac.resume();
    if (!A._pre) { A._pre = true; A.preload && A.preload(); }
    if (pendingMusic && !cur) { const p = pendingMusic; pendingMusic = null; curId = null; A.music(p); }
  },
  applyVolumes,
  music(id) {
    if (id === curId) return;
    curId = id;
    if (!ac || ac.state !== 'running') { pendingMusic = id; if (ac) ac.resume(); }
    if (!ac) return;
    stopMusic(id === 'victory' || id === 'defeat' ? 0.15 : 0.8);
    if (!id || id === 'silence' || !SONGS[id]) return;
    const song = SONGS[id];
    const c = compiled[id] || (compiled[id] = compile(song));
    const token = {};
    A._token = token;
    // ждём, пока нужные ноты загрузятся (не дольше 6 с), потом стартуем
    Promise.race([prepare(song, c), new Promise(r => setTimeout(r, 6000))]).then(() => {
      if (A._token !== token || curId !== id) return;
      const bus = ac.createGain(); bus.gain.value = 1; bus.connect(musicBus);
      cur = { c, song, i: 0, loop: 0, t0: ac.currentTime + 0.08, bus };
      if (!timer) timer = setInterval(schedule, 25);
      schedule();
    });
  },
  sfx(id) {
    if (!ac) init();
    if (!ac || ac.state !== 'running') return;
    const t = ac.currentTime + 0.01, f = SFX[id];
    if (f) try { f(t); } catch (e) {}
  },
  blip(voice) {
    if (!ac || ac.state !== 'running') return;
    const t = ac.currentTime;
    const base = voice === 'low' ? 150 : voice === 'high' ? 520 : 300;
    const o = osc('p0.5', base * (0.96 + Math.random() * 0.08), t), g = ac.createGain(), f = ac.createBiquadFilter();
    f.type = 'lowpass'; f.frequency.value = 1800;
    g.gain.setValueAtTime(0.05, t); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.04);
    o.connect(f).connect(g).connect(sfxBus); o.start(t); o.stop(t + 0.05);
  },
};

/* ---------------- звуковые эффекты ---------------- */
function nburst(t, dur, ftype, fq, gain, q = 1, dest) {
  const n = noise(t), f = ac.createBiquadFilter(), g = ac.createGain();
  f.type = ftype; f.frequency.value = fq; f.Q.value = q;
  g.gain.setValueAtTime(gain, t); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  n.connect(f).connect(g); g.connect(dest || sfxBus); g.connect(revSend);
  n.start(t); n.stop(t + dur + 0.02);
  return f;
}
function tone(t, type, f0, f1, dur, gain, dest) {
  const o = osc(type, f0, t), g = ac.createGain();
  if (f1 !== f0) o.frequency.exponentialRampToValueAtTime(f1, t + dur);
  g.gain.setValueAtTime(gain, t); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  o.connect(g); g.connect(dest || sfxBus); g.connect(revSend);
  o.start(t); o.stop(t + dur + 0.02);
}
function gavel(t, k = 1) {
  // удар деревянного молотка о подставку: щелчок + деревянный резонанс + низ
  nburst(t, 0.03, 'highpass', 2500, 0.6 * k);
  nburst(t, 0.18, 'bandpass', 420, 0.9 * k, 6);
  nburst(t, 0.12, 'bandpass', 950, 0.5 * k, 8);
  tone(t, 'sine', 180, 90, 0.22, 0.6 * k);
  tone(t, 'triangle', 620, 560, 0.08, 0.15 * k);
}
function smp(name, t, m, dur, vel, fb) {
  if (sampleReady(name, m)) playSample(name, t, m, dur, vel, sfxBus);
  else { loadInst(name).then(() => decodeNote(name, m)); if (fb) INST[fb](t, m, dur, vel, sfxBus); }
}
const SFX = {
  /* Получение улики: глиссандо арфы, мотив челесты, струнный аккорд, искры колокольчиков (свой мотив) */
  itemget: t => {
    [60, 62, 64, 67, 69, 72, 74, 76, 79, 81, 84].forEach((m, i) => smp('orchestral_harp', t + i * 0.035, m, 0.8, 0.6, 'bell'));
    const m0 = t + 0.42;
    [[76, 0], [79, 0.14], [84, 0.28], [83, 0.42], [88, 0.62]].forEach(([m, d], i) => smp('celesta', m0 + d, m, i === 4 ? 1.4 : 0.3, 0.9, 'bell'));
    [60, 64, 67, 71, 76].forEach(m => smp('string_ensemble_1', m0 + 0.6, m, 1.4, 0.35, 'pad'));
    [96, 91, 100].forEach((m, i) => smp('glockenspiel', m0 + 0.62 + i * 0.09, m, 0.6, 0.35, 'bell'));
  },
  /* Удар-откровение: колокол, литавры, медь */
  reveal: t => {
    smp('tubular_bells', t, 50, 2, 0.9, 'bell'); smp('timpani', t, 38, 1.5, 1, 'timp');
    [50, 57, 62, 65].forEach(m => smp('french_horn', t + 0.02, m, 1.2, 0.6, 'brass'));
  },
  /* Вердикт «невиновен»: струнные и хор раскрываются */
  verdict: t => {
    [48, 55, 60, 64, 67, 72].forEach(m => smp('string_ensemble_1', t, m, 2.5, 0.5, 'pad'));
    [60, 64, 67].forEach(m => smp('choir_aahs', t + 0.1, m, 2.4, 0.4, 'pad'));
    smp('timpani', t, 36, 2, 1, 'timp'); smp('glockenspiel', t + 0.3, 84, 1, .4, 'bell'); smp('glockenspiel', t + 0.45, 88, 1, .4, 'bell');
  },
  gavel: t => gavel(t),
  gavel3: t => { gavel(t, .9); gavel(t + 0.32, .95); gavel(t + 0.64, 1.1); },
  objection: t => { tone(t, 'sine', 120, 40, 0.5, 0.9); nburst(t, 0.25, 'lowpass', 900, 0.8); nburst(t, 0.05, 'highpass', 3000, 0.5);
    tone(t + 0.02, 'sawtooth', 220, 210, 0.35, 0.08); tone(t + 0.02, 'sawtooth', 277, 270, 0.35, 0.06); tone(t + 0.02, 'sawtooth', 330, 325, 0.35, 0.06); },
  stamp: t => { tone(t, 'sine', 140, 50, 0.25, 0.7); nburst(t, 0.12, 'lowpass', 1200, 0.6); nburst(t, 0.03, 'highpass', 4000, 0.3); },
  slam: t => { tone(t, 'sine', 90, 40, 0.3, 0.8); nburst(t, 0.2, 'bandpass', 300, 0.9, 2); nburst(t + 0.01, 0.15, 'bandpass', 1400, 0.3, 3); },
  paper: t => { const f = nburst(t, 0.28, 'bandpass', 3000, 0.25, 1.5); f.frequency.linearRampToValueAtTime(6000, t + 0.25); },
  evidence: t => { [72, 76, 79, 84].forEach((m, i) => INST.bell(t + i * 0.07, m, 0.3, 0.9, sfxBus)); },
  select: t => { tone(t, 'square', 880, 880, 0.05, 0.06); tone(t + 0.04, 'square', 1320, 1320, 0.06, 0.05); },
  cancel: t => { tone(t, 'square', 660, 440, 0.1, 0.06); },
  typewriter: t => { nburst(t, 0.025, 'highpass', 3500, 0.35); nburst(t + 0.005, 0.04, 'bandpass', 1200, 0.25, 4); },
  damage: t => { tone(t, 'sawtooth', 300, 60, 0.45, 0.18); nburst(t, 0.3, 'lowpass', 600, 0.5); tone(t, 'sine', 80, 40, 0.5, 0.6); },
  shock: t => { [48, 54, 59, 63].forEach(m => INST.brass(t, m, 0.6, 1.3, sfxBus)); tone(t, 'sine', 60, 35, 0.8, 0.6); },
  door: t => { nburst(t, 0.25, 'bandpass', 200, 0.9, 3); tone(t, 'sine', 100, 60, 0.25, 0.5); nburst(t + 0.18, 0.05, 'highpass', 2000, 0.2); },
  heartbeat: t => { tone(t, 'sine', 70, 40, 0.18, 0.9); tone(t + 0.22, 'sine', 65, 38, 0.2, 0.7); },
  jail: t => { [1, 2.76, 5.4, 8.93].forEach((r, i) => tone(t, 'sine', 220 * r, 220 * r * 0.995, 1.4 / (i + 1), 0.15 / (i + 1))); nburst(t, 0.05, 'highpass', 2500, 0.4); },
  crowd: t => {
    for (let i = 0; i < 9; i++) {
      const tt = t + Math.random() * 0.6, f = nburst(tt, 0.9 + Math.random() * 0.6, 'bandpass', 350 + Math.random() * 700, 0.18, 4);
      f.frequency.linearRampToValueAtTime(300 + Math.random() * 900, tt + 0.8);
    }
  },
  crowdGasp: t => {
    for (let i = 0; i < 14; i++) { const tt = t + Math.random() * 0.15, f = nburst(tt, 0.35 + Math.random() * 0.3, 'bandpass', 1500 + Math.random() * 1500, 0.12, 3); f.frequency.linearRampToValueAtTime(800, tt + 0.4); }
  },
  crowdAngry: t => {
    for (let i = 0; i < 16; i++) { const tt = t + Math.random() * 1.2, f = nburst(tt, 0.4 + Math.random() * 0.5, 'bandpass', 250 + Math.random() * 500, 0.22, 6); f.frequency.linearRampToValueAtTime(400 + Math.random() * 600, tt + 0.4); }
    smp('trombone', t + 0.1, 41, 0.8, 0.25, null);
  },
  clap: t => { for (let i = 0; i < 70; i++) { const tt = t + Math.random() * 2.4; nburst(tt, 0.03, 'bandpass', 1200 + Math.random() * 1600, 0.18 * (1 - (tt - t) / 3), 1.2); } },
  cheer: t => {
    SFX.clap(t + 0.3);
    for (let i = 0; i < 12; i++) { const tt = t + Math.random() * 0.8, f = nburst(tt, 0.8 + Math.random() * 0.8, 'bandpass', 600 + Math.random() * 900, 0.16, 5); f.frequency.linearRampToValueAtTime(900 + Math.random() * 1200, tt + 0.3); f.frequency.linearRampToValueAtTime(500, tt + 1.2); }
  },
  crowdHush: t => { const f = nburst(t, 0.9, 'bandpass', 2500, 0.3, 0.8); f.frequency.linearRampToValueAtTime(5000, t + 0.8); },
};

G.Audio.songs = SONGS;
G.Audio._tap = function () { init(); const d = ac.createMediaStreamDestination(); master.connect(d); return d.stream; };
/* заранее подгрузить инструменты для эффектов */
G.Audio.preload = function () { if (!init()) return; ['orchestral_harp', 'celesta', 'glockenspiel', 'string_ensemble_1', 'timpani', 'choir_aahs', 'tubular_bells', 'french_horn'].forEach(n => loadInst(n).then(() => {
  for (const m of [60, 64, 67, 72, 76, 79, 84, 88, 91, 96, 55, 59, 62, 48, 43, 36, 38, 45, 50, 52, 53, 57, 65, 69, 71, 74, 77, 81, 83]) decodeNote(n, m);
})); };
})();
