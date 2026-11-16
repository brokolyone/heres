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
  musicBus.gain.value = (s.music ?? .7) * 0.55;
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
  menu: {
    bpm: 80, lead: 'flute', swing: 0,
    chords: ['Dm', 'Bb', 'Gm', 'A', 'Dm', 'F', 'Gm A', 'Dm'],
    mel: [
      'A4:6 D5:2 F5:4 E5:2 D5:2', 'D5:6 C5:2 Bb4:4 A4:4', 'G4:6 Bb4:2 D5:4 C5:2 Bb4:2', 'A4:12 r:4',
      'A4:6 D5:2 F5:4 G5:2 A5:2', 'C6:6 Bb5:2 A5:4 F5:4', 'G5:4 F5:2 E5:2 E5:4 C#5:4', 'D5:12 r:4',
    ],
    counter: [   // второй голос (медь) во второй половине повтора
      'r:16', 'r:16', 'r:16', 'r:8 E4:4 C#4:4',
      'F4:8 A4:8', 'A4:8 C5:8', 'Bb4:8 A4:8', 'F4:12 r:4',
    ],
    bass: 'half', arp: 'broken', pad: true, drums: 'timp',
  },
  court: {
    bpm: 104, lead: 'lead',
    chords: ['Am', 'G', 'F', 'E', 'Am', 'Dm', 'E', 'Am'],
    mel: [
      'E5:2 A5:2 B5:2 C6:4 B5:2 A5:2 E5:2', 'D5:2 G5:2 A5:2 B5:4 A5:2 G5:2 D5:2',
      'C5:2 F5:2 G5:2 A5:4 G5:2 F5:2 C5:2', 'B4:4 E5:4 G#5:4 B5:4',
      'C6:4 B5:2 A5:2 E5:4 A5:4', 'D6:4 C6:2 B5:2 A5:4 F5:4',
      'E5:2 F5:2 G#5:2 A5:2 B5:4 G#5:4', 'A5:8 r:4 E5:4',
    ],
    counter: [
      'A3:8 C4:8', 'B3:8 D4:8', 'A3:8 C4:8', 'G#3:8 B3:8', 'E4:8 C4:8', 'F4:8 D4:8', 'E4:8 D4:8', 'C4:12 r:4',
    ],
    bass: 'walk', arp: 'eighths', pad: true, drums: 'march',
  },
  cross: {
    bpm: 132, lead: 'lead',
    chords: ['Em', 'C', 'D', 'B', 'Em', 'C', 'Am', 'B7'],
    mel: [
      'B4:2 E5:2 G5:2 B5:4 A5:2 G5:2 F#5:2', 'E5:2 G5:2 C6:4 B5:2 A5:2 G5:4',
      'F#5:2 A5:2 D6:4 C6:2 B5:2 A5:4', 'B5:6 A5:2 G5:2 F#5:2 D#5:4',
      'E5:2 E5:1 F#5:1 G5:2 B5:2 E6:4 D6:2 B5:2', 'C6:4 B5:2 G5:2 E5:4 G5:4',
      'A5:2 C6:2 E6:4 D6:2 C6:2 B5:2 A5:2', 'B5:8 D#6:4 F#6:4',
    ],
    counter: [
      'G4:16', 'G4:16', 'A4:16', 'F#4:16', 'G4:8 B4:8', 'E4:8 G4:8', 'E4:8 A4:8', 'F#4:8 D#4:8',
    ],
    bass: 'pump', arp: 'sixteenths', pad: false, drums: 'drive',
  },
  pressure: {
    bpm: 150, lead: 'lead',
    chords: ['Gm', 'Eb', 'F', 'D', 'Gm', 'Eb', 'Cm', 'D7'],
    mel: [
      'G5:1 D5:1 G5:1 A5:1 Bb5:2 A5:2 G5:2 D5:2 Bb4:2 D5:2', 'G5:1 Eb5:1 G5:1 A5:1 Bb5:2 C6:2 Bb5:2 G5:2 Eb5:4',
      'A5:1 F5:1 A5:1 Bb5:1 C6:2 D6:2 C6:2 A5:2 F5:4', 'F#5:4 A5:4 D6:4 C6:2 A5:2',
      'Bb5:2 A5:2 G5:2 D5:2 G5:2 A5:2 Bb5:2 D6:2', 'Eb6:4 D6:2 C6:2 Bb5:4 G5:4',
      'C6:2 Eb6:2 G6:4 F6:2 Eb6:2 D6:2 C6:2', 'D6:4 C6:2 A5:2 F#5:4 D5:4',
    ],
    counter: [
      'D4:16', 'Eb4:16', 'F4:16', 'F#4:16', 'G4:16', 'G4:16', 'G4:16', 'F#4:16',
    ],
    bass: 'sixteen', arp: 'sixteenths', pad: false, drums: 'hard',
  },
  suspense: {
    bpm: 66, lead: 'flute',
    chords: ['Cm', 'Ab', 'Fm', 'G', 'Cm', 'Ab', 'Fm', 'G7'],
    mel: [
      'r:8 G5:4 Ab5:4', 'G5:12 r:4', 'F5:4 Eb5:4 D5:4 C5:4', 'B4:12 r:4',
      'r:8 Eb5:4 F5:4', 'G5:8 Ab5:4 C6:4', 'B5:4 Ab5:4 G5:4 F5:4', 'D5:12 r:4',
    ],
    bass: 'whole', arp: 'bells', pad: true, drums: 'heart',
  },
  victory: {
    bpm: 124, lead: 'brass',
    chords: ['C', 'F', 'G', 'C', 'Am', 'F', 'G', 'C'],
    mel: [
      'G4:2 C5:2 E5:2 G5:6 E5:2 G5:2', 'A5:6 G5:2 F5:4 A5:4', 'G5:4 D5:2 E5:2 F5:4 B4:4', 'E5:2 G5:2 C6:8 r:4',
      'E5:2 A5:2 C6:4 B5:2 A5:2 E5:4', 'F5:2 A5:2 C6:4 D6:2 C6:2 A5:4', 'B5:4 C6:2 D6:2 G5:4 B5:4', 'C6:12 r:4',
    ],
    counter: [
      'E4:8 G4:8', 'F4:8 C5:8', 'D4:8 B4:8', 'C5:8 G4:8', 'C5:8 E4:8', 'A4:8 F4:8', 'G4:8 D5:8', 'E5:12 r:4',
    ],
    bass: 'walk', arp: 'eighths', pad: true, drums: 'march',
  },
  defeat: {
    bpm: 60, lead: 'flute',
    chords: ['Am', 'F', 'Dm', 'E'],
    mel: ['E5:8 C5:8', 'C5:8 A4:8', 'D5:6 F5:2 E5:4 D5:4', 'B4:12 r:4'],
    bass: 'whole', arp: 'bells', pad: true, drums: 'none',
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
  addLine(song.mel, song.lead, 1);
  addLine(song.counter, 'brass', 0.55);
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
      // пэд
      if (song.pad) for (const tn of tones) ev.push({ step: s0, dur: len, m: tn, inst: 'pad', vel: .8 });
      // ударные
      for (let k = 0; k < len; k++) {
        const s = s0 + k, b = (bi * 16 + pi * len + k) % 16;
        if (song.drums === 'march') { if (b === 0 || b === 8) ev.push({ step: s, inst: 'kick', vel: 1 }); if (b === 4 || b === 12) ev.push({ step: s, inst: 'snare', vel: .8 }); if (b % 2 === 0) ev.push({ step: s, inst: 'hat', vel: b % 4 ? .5 : .9 }); }
        if (song.drums === 'drive') { if (b % 4 === 0) ev.push({ step: s, inst: 'kick', vel: 1 }); if (b === 4 || b === 12) ev.push({ step: s, inst: 'snare', vel: 1 }); ev.push({ step: s, inst: 'hat', vel: b % 2 ? .4 : .8 }); }
        if (song.drums === 'hard') { if (b % 4 === 0 || b === 10) ev.push({ step: s, inst: 'kick', vel: 1 }); if (b === 4 || b === 12 || b === 15) ev.push({ step: s, inst: 'snare', vel: b === 15 ? .5 : 1 }); ev.push({ step: s, inst: 'hat', vel: b % 2 ? .5 : .9 }); }
        if (song.drums === 'timp') { if (b === 0 && bi % 2 === 0) ev.push({ step: s, m: 38 + ch.root % 12, inst: 'timp', vel: .8 }); if (bi === bars - 2 && b >= 12) ev.push({ step: s, m: 45, inst: 'timp', vel: .4 + (b - 12) * .12 }); }
        if (song.drums === 'heart') { if (b === 0) ev.push({ step: s, inst: 'kick', vel: .9 }); if (b === 3) ev.push({ step: s, inst: 'kick', vel: .6 }); }
      }
    });
  });
  ev.sort((a, b) => a.step - b.step);
  return { ev, steps: bars * 16, stepDur: 60 / song.bpm / 4 };
}
const compiled = {};

/* ---------------- плеер ---------------- */
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
      try { INST[e.inst](t, e.m, (e.dur || 1) * cur.c.stepDur, e.vel || 1, cur.bus); } catch (err) {}
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
    const c = compiled[id] || (compiled[id] = compile(SONGS[id]));
    const bus = ac.createGain(); bus.gain.value = 1; bus.connect(musicBus);
    cur = { c, i: 0, loop: 0, t0: ac.currentTime + 0.1, bus };
    if (!timer) timer = setInterval(schedule, 25);
    schedule();
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
const SFX = {
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
  crowdHush: t => { const f = nburst(t, 0.9, 'bandpass', 2500, 0.3, 0.8); f.frequency.linearRampToValueAtTime(5000, t + 0.8); },
};

G.Audio.songs = SONGS;
})();
