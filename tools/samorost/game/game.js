(function () {
'use strict';
const $ = s => document.querySelector(s);
const stage = $('#stage'), outside = $('#outside'), inside = $('#inside'), curtain = $('#curtain');
const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;

// ---------------- layout ----------------
function fit() {
  const s = Math.min(innerWidth / 1600, innerHeight / 1000);
  stage.style.transform = 'scale(' + s + ')';
}
addEventListener('resize', fit); fit();
function toStage(e) {
  const r = stage.getBoundingClientRect();
  return { x: (e.clientX - r.left) / r.width * 1600, y: (e.clientY - r.top) / r.height * 1000 };
}

// ---------------- ground under the gnome ----------------
const SEGS = [[380, 610, 470, 560, 600, 545, 720, 548], [720, 548, 850, 550, 980, 555, 1080, 570], [1080, 570, 1150, 580, 1200, 595, 1230, 615]];
const GT = [];
for (const s of SEGS) for (let t = 0; t <= 1; t += 0.01) {
  const u = 1 - t, b = [u * u * u, 3 * u * u * t, 3 * u * t * t, t * t * t];
  GT.push([b[0] * s[0] + b[1] * s[2] + b[2] * s[4] + b[3] * s[6], b[0] * s[1] + b[1] * s[3] + b[2] * s[5] + b[3] * s[7]]);
}
GT.sort((a, b) => a[0] - b[0]);
function groundY(x) {
  for (let i = 1; i < GT.length; i++) if (GT[i][0] >= x) {
    const [x0, y0] = GT[i - 1], [x1, y1] = GT[i];
    return y0 + (y1 - y0) * (x - x0) / Math.max(1e-6, x1 - x0);
  }
  return GT[GT.length - 1][1];
}
const SCN = {
  out: { min: 430, max: 1085, feet: x => groundY(x) - 0.5, scale: 1, speed: 105, stride: 3.6 },
  in: { min: 175, max: 1430, feet: () => 905, scale: 2.3, speed: 230, stride: 8.4 },
};

// ---------------- the puppet ----------------
document.getElementById('slot-out').appendChild(document.getElementById('hero-tpl').content.cloneNode(true));
const hero = $('#hero');
const P = {}; for (const id of ['root', 'shadow', 'legL', 'legR', 'upper', 'armL', 'armR', 'head', 'eyes', 'beam']) P[id] = $('#h-' + id);
const H = { scene: 'out', x: 780, dir: 1, target: null, walk: 0, phase: 0, arm: 0, armL: 0, look: 0, blink: 1, beam: 1,
  busy: false, action: null, pose: null, fade: 1, nextBlink: 2, nextLook: 5, lookTo: 0, keys: 0, lastStep: 0 };

function draw(t) {
  const S = SCN[H.scene], sc = S.scale, w = H.walk, s = Math.sin(H.phase);
  if (H.pose === 'sleep') {
    P.root.setAttribute('transform', `translate(560,752) scale(${sc}) rotate(-90) translate(-781,-512)`);
  } else {
    P.root.setAttribute('transform', `translate(${H.x.toFixed(1)},${S.feet(H.x).toFixed(1)}) scale(${(sc * H.dir).toFixed(3)},${sc}) translate(-781,-548)`);
  }
  hero.style.opacity = H.fade;
  const breathe = (1 - w) * Math.sin(t * 1.8) * 0.45;
  P.legL.setAttribute('transform', `rotate(${(s * 30 * w).toFixed(2)} 775 532)`);
  P.legR.setAttribute('transform', `rotate(${(-s * 30 * w).toFixed(2)} 786 532)`);
  P.upper.setAttribute('transform', `translate(0,${(-Math.abs(Math.cos(H.phase)) * 2.4 * w + breathe).toFixed(2)})`);
  P.armL.setAttribute('transform', `rotate(${(-s * 22 * w + H.armL).toFixed(2)} 770 517)`);
  P.armR.setAttribute('transform', `rotate(${(s * 9 * w + H.arm).toFixed(2)} 791 517)`);
  P.head.setAttribute('transform', `rotate(${(H.look + s * 2.5 * w).toFixed(2)} 781 512)`);
  P.eyes.setAttribute('transform', `translate(0,${(496 * (1 - H.blink)).toFixed(2)}) scale(1,${H.blink.toFixed(3)})`);
  P.beam.style.opacity = (H.scene === 'out' && H.pose !== 'sleep') ? H.beam : 0;
  P.shadow.setAttribute('transform', `translate(781,549) scale(${(1 - 0.12 * Math.abs(Math.cos(H.phase)) * w).toFixed(3)},1) translate(-781,-549)`);
}

// ---------------- tiny animation helpers ----------------
const wait = ms => new Promise(r => setTimeout(r, ms));
function tween(ms, fn) {
  return new Promise(res => {
    const t0 = performance.now();
    (function step(now) {
      const k = Math.min(1, (now - t0) / ms);
      fn(k < .5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2);
      if (k < 1) requestAnimationFrame(step); else res();
    })(t0);
  });
}
const fxLayer = () => $(H.scene === 'out' ? '#fx-out' : '#fx-in');
function fx(cls, x, y, frames, ms, opts = {}) {
  const el = document.createElement('i');
  el.className = cls; if (opts.text) el.textContent = opts.text;
  el.style.left = x + 'px'; el.style.top = y + 'px';
  fxLayer().appendChild(el);
  const a = el.animate(frames, { duration: reduce ? 1 : ms, easing: opts.easing || 'ease-out', delay: opts.delay || 0, fill: 'both' });
  a.onfinish = () => el.remove();
  return a;
}
const part = id => document.querySelector(`[data-id="${id}"]`);
function img(id) { const p = part(id); return p && p.querySelector(':scope > img'); }
function box(el) { return { x: parseFloat(el.style.left), y: parseFloat(el.style.top), w: parseFloat(el.style.width), h: parseFloat(el.style.height) }; }
function poke(el, frames, ms, origin) {
  if (!el || reduce) return;
  if (origin) el.style.transformOrigin = origin;
  el.animate(frames, { duration: ms, easing: 'ease-out' });
}
function speed(ids, rate, ms) {
  for (const id of ids) { const p = part(id); if (!p) continue; p.getAnimations().forEach(a => { a.playbackRate = rate; }); }
  setTimeout(() => { for (const id of ids) { const p = part(id); if (p) p.getAnimations().forEach(a => { a.playbackRate = 1; }); } }, ms);
}
async function reach(up = -70, ms = 260, hold = 300) {
  await tween(ms, k => { H.arm = up * k; });
  await wait(hold);
  tween(ms, k => { H.arm = up * (1 - k); });
}

// ---------------- sound ----------------
const AUDIO = [%%AUDIO%%];
let ac = null, master, music, musicFilter, musicGain, crackleGain, muted = false;
function initAudio() {
  if (ac) return;
  try { ac = new (window.AudioContext || window.webkitAudioContext)(); } catch (e) { return; }
  master = ac.createGain(); master.gain.value = 0.9; master.connect(ac.destination);
  musicFilter = ac.createBiquadFilter(); musicFilter.type = 'lowpass'; musicFilter.frequency.value = 18000;
  musicGain = ac.createGain(); musicGain.gain.value = 0;
  musicFilter.connect(musicGain); musicGain.connect(master);
  // stove crackle bed, only heard inside
  const n = ac.sampleRate * 4, nb = ac.createBuffer(1, n, ac.sampleRate), d = nb.getChannelData(0);
  for (let i = 0; i < 90; i++) { const p = Math.floor(Math.random() * (n - 800)), L = 80 + Math.random() * 500, a = Math.random() * .8; for (let k = 0; k < L; k++) d[p + k] += (Math.random() * 2 - 1) * a * Math.exp(-k / (L / 4)); }
  for (let k = 0; k < n; k++) d[k] += (Math.random() * 2 - 1) * 0.02;
  const cs = ac.createBufferSource(); cs.buffer = nb; cs.loop = true;
  const cf = ac.createBiquadFilter(); cf.type = 'bandpass'; cf.frequency.value = 2400; cf.Q.value = 0.7;
  crackleGain = ac.createGain(); crackleGain.gain.value = 0;
  cs.connect(cf); cf.connect(crackleGain); crackleGain.connect(master); cs.start();
  (async () => {
    for (const [, url] of AUDIO) {
      try {
        const ab = await (await fetch(url)).arrayBuffer();
        const buf = await new Promise((ok, no) => ac.decodeAudioData(ab, ok, no));
        music = ac.createBufferSource(); music.buffer = buf; music.loop = true; music.connect(musicFilter); music.start();
        musicGain.gain.setTargetAtTime(0.75, ac.currentTime, 1.2);
        return;
      } catch (e) { /* try the next format */ }
    }
  })();
}
function env(g, t, a, peak, d) { g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(peak, t + a); g.gain.exponentialRampToValueAtTime(0.0001, t + a + d); }
function tone(f, d, { type = 'sine', vol = 0.2, a = 0.005, when = 0, glide = null, vib = 0, pan = 0 } = {}) {
  if (!ac || muted) return;
  const t = ac.currentTime + when, o = ac.createOscillator(), g = ac.createGain(), p = ac.createStereoPanner ? ac.createStereoPanner() : null;
  o.type = type; o.frequency.setValueAtTime(f, t);
  if (glide) o.frequency.exponentialRampToValueAtTime(glide, t + d);
  if (vib) { const l = ac.createOscillator(), lg = ac.createGain(); l.frequency.value = 6; lg.gain.value = vib; l.connect(lg); lg.connect(o.frequency); l.start(t); l.stop(t + a + d + .05); }
  env(g, t, a, vol, d);
  o.connect(g); if (p) { p.pan.value = pan; g.connect(p); p.connect(master); } else g.connect(master);
  o.start(t); o.stop(t + a + d + 0.05);
}
function noise(d, { f = 1000, q = 1, type = 'bandpass', vol = 0.2, a = 0.005, when = 0, sweep = null } = {}) {
  if (!ac || muted) return;
  const t = ac.currentTime + when, n = Math.ceil(ac.sampleRate * (a + d + .05)), b = ac.createBuffer(1, n, ac.sampleRate), c = b.getChannelData(0);
  for (let i = 0; i < n; i++) c[i] = Math.random() * 2 - 1;
  const s = ac.createBufferSource(), fl = ac.createBiquadFilter(), g = ac.createGain();
  s.buffer = b; fl.type = type; fl.frequency.setValueAtTime(f, t); fl.Q.value = q;
  if (sweep) fl.frequency.exponentialRampToValueAtTime(sweep, t + d);
  env(g, t, a, vol, d); s.connect(fl); fl.connect(g); g.connect(master); s.start(t);
}
const SFX = {
  step() { if (H.scene === 'out') noise(.06, { f: 500, type: 'lowpass', vol: .12 }); else { tone(150 + Math.random() * 30, .07, { vol: .18 }); noise(.03, { f: 2500, vol: .05 }); } },
  boing(size) { const f = 520 / Math.max(.5, size); tone(f * 1.6, .45, { glide: f * .6, vib: 18, vol: .22 }); },
  creak() { if (!ac || muted) return; for (let i = 0; i < 14; i++) noise(.025, { f: 900 + Math.random() * 500, q: 8, vol: .25, when: i * .045 + Math.random() * .02 }); tone(110, .6, { type: 'sawtooth', vol: .04, glide: 140 }); },
  snort() { noise(.5, { f: 300, type: 'lowpass', vol: .5, a: .05 }); tone(70, .5, { vib: 12, vol: .3, a: .05 }); },
  chime(fs, gap = .12) { fs.forEach((f, i) => { tone(f, 1.2, { vol: .12, when: i * gap }); tone(f * 2.01, .6, { vol: .04, when: i * gap }); }); },
  sparkle() { [1568, 1976, 2349, 3136].forEach((f, i) => tone(f, .35, { vol: .06, when: i * .05 })); },
  musicbox() { const N = [587, 698, 880, 784, 698, 659, 587, 440, 523, 587, 659, 698, 659, 523, 587]; N.forEach((f, i) => { tone(f, .9, { vol: .13, when: i * .32 }); tone(f * 2, .3, { vol: .04, when: i * .32 }); }); return N.length * 320; },
  whistle() { tone(1700, 1.8, { glide: 2100, vib: 40, vol: .1, a: .3 }); noise(1.8, { f: 3000, vol: .05, a: .3 }); },
  whoosh() { noise(.7, { f: 300, sweep: 3000, q: 1.5, vol: .3, a: .1 }); },
  crackle() { for (let i = 0; i < 20; i++) noise(.03, { f: 2000 + Math.random() * 2000, vol: .25 * Math.random(), when: Math.random() * .9 }); },
  ding() { tone(1320, 1.4, { vol: .12 }); tone(2640, .5, { vol: .04 }); },
  click() { noise(.02, { f: 3000, vol: .2 }); tone(800, .04, { vol: .08 }); },
  bloop() { tone(300, .2, { glide: 900, vol: .18 }); },
  whirr() { tone(90, 2.2, { type: 'sawtooth', vol: .05, glide: 160, vib: 20 }); noise(2.2, { f: 700, q: 2, vol: .06 }); },
  buzz() { tone(180, .8, { type: 'square', vol: .03, vib: 30 }); },
  snore() { noise(1.2, { f: 400, q: 2, vol: .2, a: .5 }); tone(60, 1.2, { vol: .1, a: .5, vib: 8 }); },
  yay() { [523, 659, 784, 1047, 1319].forEach((f, i) => tone(f, .8, { vol: .12, when: i * .11 })); },
};

// ---------------- discoveries ----------------
const found = new Set();
let total = 0;
const toastEl = $('#toast');
let toastTimer;
function toast(msg, ms = 4500) { toastEl.textContent = msg; toastEl.style.opacity = 1; clearTimeout(toastTimer); toastTimer = setTimeout(() => { toastEl.style.opacity = 0; }, ms); }
function discover(id) {
  if (found.has(id)) return;
  found.add(id);
  $('#nfound').textContent = found.size;
  if (found.size === total) {
    toast('Ты нашёл всё на острове и в доме. Гномик доволен!', 7000);
    SFX.yay();
    for (let i = 0; i < 40; i++) fx('dot', 200 + Math.random() * 1200, 900, [{ transform: 'translate(0,0)', opacity: 0 }, { opacity: 1, offset: .2 }, { transform: `translate(${(Math.random() - .5) * 200}px,${-300 - Math.random() * 500}px)`, opacity: 0 }], 3000 + Math.random() * 2000, { delay: Math.random() * 1500 });
  }
}

// ---------------- hotspots ----------------
const R = (x, y, w, h) => ({ x, y, w, h });
function partRect(id, pad = 4) { const i = img(id); if (!i) return null; const b = box(i); return R(b.x - pad, b.y - pad, b.w + 2 * pad, b.h + 2 * pad); }
function shroomSpots() {
  return [...document.querySelectorAll('#outside [data-id^="shroom-"]')].map(p => {
    const id = p.dataset.id, b = box(p.querySelector(':scope > img')), cx = b.x + b.w / 2;
    return { scene: 'out', key: 'mushrooms', rect: R(b.x - 4, b.y - 4, b.w + 8, b.h + 8), walk: cx < 760 ? cx + 22 : cx - 22, act: async () => {
      await reach(-40, 180, 120);
      const size = Math.min(2.2, b.h / 60);
      SFX.boing(size);
      poke(p.querySelector(':scope > img'), [{ transform: 'scale(1,1)' }, { transform: 'scale(1.18,.78)' }, { transform: 'scale(.9,1.15)' }, { transform: 'scale(1.04,.97)' }, { transform: 'scale(1,1)' }], 700, '50% 100%');
      for (let i = 0; i < 10; i++) fx('dot', cx + (Math.random() - .5) * b.w * .6, b.y + 6, [{ transform: 'translate(0,0) scale(1)', opacity: 1 }, { transform: `translate(${(Math.random() - .5) * 70}px,${-30 - Math.random() * 60}px) scale(.4)`, opacity: 0 }], 1400 + Math.random() * 600);
    } };
  });
}
const SPOTS = [
  // ---- island ----
  { scene: 'out', key: 'door', rect: R(498, 484, 80, 86), walk: 538, act: enterHouse },
  { scene: 'out', key: 'beast', rect: R(1095, 520, 190, 140), walk: 1078, face: 1, act: async () => {
    await reach(-30);
    SFX.snort();
    poke(img('beast'), [{ transform: 'scale(1,1)' }, { transform: 'scale(1.05,.93) translateY(3px)' }, { transform: 'scale(.97,1.06)' }, { transform: 'scale(1,1)' }], 900, '50% 100%');
    for (let i = 0; i < 6; i++) fx('zz', 1250 + i * 6, 540, [{ transform: 'translate(0,0) scale(.6)', opacity: 0 }, { opacity: 1, offset: .2 }, { transform: `translate(${20 + i * 8}px,${-60 - i * 18}px) scale(1.2)`, opacity: 0 }], 1800, { text: 'z', delay: 500 + i * 220 });
    toast('Хррр… Зверь всхрапнул и снова уснул.');
  } },
  { scene: 'out', key: 'glowshrooms', rect: R(810, 524, 32, 34), walk: 806, act: async () => {
    await reach(-30); SFX.sparkle();
    const p = part('glowshrooms'); if (p) p.animate([{ filter: 'brightness(1)' }, { filter: 'brightness(2.6)' }, { filter: 'brightness(1)' }], { duration: 1600 });
  } },
  { scene: 'out', key: 'machine', rect: R(975, 330, 160, 230), walk: 985, face: 1, act: async () => {
    await reach(-60); SFX.whirr(); speed(['propeller', 'gear-a', 'gear-b', 'gear-c', 'gauge', 'flag'], 5, 3200);
    await wait(600); const ms = SFX.musicbox();
    for (let i = 0; i < 9; i++) fx('note', 1000 + Math.random() * 20, 290, [{ transform: 'translate(0,0) rotate(0)', opacity: 0 }, { opacity: 1, offset: .15 }, { transform: `translate(${-40 - Math.random() * 120}px,${-80 - Math.random() * 120}px) rotate(${(Math.random() - .5) * 60}deg)`, opacity: 0 }], 2200, { text: Math.random() < .5 ? '♪' : '♫', delay: i * (ms / 9) });
    toast('Граммофон на башне заиграл.');
  } },
  { scene: 'out', key: 'lantern', rect: R(1146, 398, 40, 60), walk: 1110, face: 1, act: async () => {
    await reach(-80); SFX.ding();
    poke(img('lantern'), [{ transform: 'rotate(0)' }, { transform: 'rotate(16deg)' }, { transform: 'rotate(-12deg)' }, { transform: 'rotate(7deg)' }, { transform: 'rotate(0)' }], 2200, '50% 0%');
  } },
  { scene: 'out', key: 'chimney', rect: R(598, 298, 84, 72), walk: 612, act: async () => {
    await reach(-75); SFX.whoosh();
    for (let i = 0; i < 9; i++) fx('puffx', 640, 320, [{ transform: 'translate(0,0) scale(.5)', opacity: 0 }, { opacity: 1, offset: .1 }, { transform: `translate(${40 + Math.random() * 90}px,${-120 - Math.random() * 120}px) scale(${3 + Math.random() * 2})`, opacity: 0 }], 2400, { delay: i * 90 });
  } },
  { scene: 'out', key: 'window', rect: R(552, 432, 42, 40), walk: 575, act: async () => {
    await reach(-60); SFX.click();
    const g = document.getElementById('glow-window'); if (g) g.animate([{ opacity: 1 }, { opacity: .1 }, { opacity: 1 }, { opacity: .2 }, { opacity: 1 }], { duration: 900 });
  } },
  { scene: 'out', key: 'moth', rect: () => partRect('moth', 10), walk: 880, act: async () => {
    SFX.buzz(); const p = part('moth'); if (p) flyOff(p, [[0, 0], [-140, -90], [-60, -200], [120, -150], [60, -40], [0, 0]], 3200);
  } },
  { scene: 'out', key: 'beetle', rect: () => partRect('beetle', 10), walk: 700, act: async () => {
    SFX.buzz(); const p = part('beetle'); if (p) flyOff(p, [[0, 0], [60, -40], [120, 0], [60, 40], [0, 0], [-60, -40], [0, 0]], 2600, true);
  } },
  { scene: 'out', key: 'jelly', rect: () => partRect('jelly', 8), walk: 470, act: async () => {
    SFX.sparkle(); const p = part('jelly'); if (p) p.animate([{ filter: 'brightness(1)' }, { filter: 'brightness(2.2) drop-shadow(0 0 12px #f3d27a)' }, { filter: 'brightness(1)' }], { duration: 2000 });
  } },
  { scene: 'out', key: 'snail', rect: () => partRect('snail-1', 10), walk: 975, act: async () => {
    SFX.bloop(); poke(img('snail-1'), [{ transform: 'scale(1)' }, { transform: 'scale(.6,.7)' }, { transform: 'scale(.6,.7)', offset: .7 }, { transform: 'scale(1)' }], 2200, '50% 70%');
    toast('Улитка спряталась… и снова выглянула.');
  } },
  { scene: 'out', key: 'spider', rect: R(1050, 450, 40, 40), walk: 1060, act: async () => {
    await reach(-50); SFX.bloop(); poke(img('spider-1'), [{ transform: 'translateY(0)' }, { transform: 'translateY(40px)' }, { transform: 'translateY(34px)', offset: .6 }, { transform: 'translateY(0)' }], 2400);
  } },
  { scene: 'out', key: 'sky', rect: R(-9999, -9999, 1, 1), walk: 780, act: async () => {} },
  { scene: 'out', key: 'ladder', rect: () => partRect('ladder', 10), walk: 905, act: async () => {
    SFX.creak(); poke(img('ladder'), [{ transform: 'rotate(0)' }, { transform: 'rotate(14deg)' }, { transform: 'rotate(-10deg)' }, { transform: 'rotate(5deg)' }, { transform: 'rotate(0)' }], 2400, '50% 0%');
  } },
  // ---- inside the house ----
  { scene: 'in', key: 'exit', rect: R(90, 580, 200, 330), walk: 195, act: leaveHouse },
  { scene: 'in', key: 'bed', rect: R(410, 630, 360, 240), walk: 600, act: sleep },
  { scene: 'in', key: 'lamp', rect: R(764, 405, 72, 95), walk: 800, act: async () => {
    await reach(-95); SFX.ding();
    poke(img('lamp'), [{ transform: 'rotate(0)' }, { transform: 'rotate(10deg)' }, { transform: 'rotate(-8deg)' }, { transform: 'rotate(4deg)' }, { transform: 'rotate(0)' }], 2000, '50% 0%');
  } },
  { scene: 'in', key: 'stove', rect: R(1215, 640, 180, 215), walk: 1175, face: 1, act: async () => {
    await reach(-30); SFX.whoosh(); SFX.crackle();
    const f = part('stovefire'); if (f) f.animate([{ filter: 'brightness(1)' }, { filter: 'brightness(2)' }, { filter: 'brightness(1)' }], { duration: 1500 });
    const g = $('.stoveglow'); if (g) g.animate([{ transform: 'scale(1)' }, { transform: 'scale(1.5)' }, { transform: 'scale(1)' }], { duration: 1500 });
    for (let i = 0; i < 18; i++) fx('spark', 1300 + (Math.random() - .5) * 60, 760, [{ transform: 'translate(0,0)', opacity: 1 }, { transform: `translate(${(Math.random() - .5) * 220}px,${-60 - Math.random() * 160}px)`, opacity: 0 }], 900 + Math.random() * 700, { delay: Math.random() * 300 });
  } },
  { scene: 'in', key: 'kettle', rect: R(1255, 540, 120, 62), walk: 1190, face: 1, act: async () => {
    await reach(-90); SFX.whistle();
    poke(img('kettle'), [{ transform: 'rotate(0)' }, { transform: 'rotate(-3deg)' }, { transform: 'rotate(3deg)' }, { transform: 'rotate(-2deg)' }, { transform: 'rotate(2deg)' }, { transform: 'rotate(0)' }], 1600, '50% 100%');
    for (let i = 0; i < 14; i++) fx('puffx', 1362, 556, [{ transform: 'translate(0,0) scale(.5)', opacity: 0 }, { opacity: 1, offset: .1 }, { transform: `translate(${30 + Math.random() * 80}px,${-140 - Math.random() * 100}px) scale(4)`, opacity: 0 }], 1800, { delay: i * 100 });
  } },
  { scene: 'in', key: 'clock', rect: R(810, 336, 80, 225), walk: 850, act: async () => {
    await reach(-90); SFX.chime([784, 659, 523], .5); speed(['pendulum'], 3, 2000);
  } },
  { scene: 'in', key: 'jar', rect: R(445, 408, 48, 66), walk: 470, act: async () => {
    await reach(-95); SFX.sparkle();
    const j = part('jar'); if (j) j.animate([{ filter: 'brightness(1)' }, { filter: 'brightness(2.4)' }, { filter: 'brightness(1)' }], { duration: 1800 });
    for (let i = 0; i < 12; i++) fx('dot', 469, 445, [{ transform: 'translate(0,0)', opacity: 1 }, { transform: `translate(${(Math.random() - .5) * 160}px,${(Math.random() - .5) * 140}px)`, opacity: 0 }], 1500);
  } },
  { scene: 'in', key: 'musicbox', rect: R(846, 730, 72, 50), walk: 860, act: async () => {
    await reach(-20); const ms = SFX.musicbox();
    const c = img('crank'); if (c && !reduce) { c.style.transformOrigin = '0% 100%'; c.animate([{ transform: 'rotate(0)' }, { transform: 'rotate(-720deg)' }], { duration: ms }); }
    for (let i = 0; i < 12; i++) fx('note', 875, 720, [{ transform: 'translate(0,0)', opacity: 0 }, { opacity: 1, offset: .15 }, { transform: `translate(${(Math.random() - .5) * 200}px,${-140 - Math.random() * 120}px) rotate(${(Math.random() - .5) * 50}deg)`, opacity: 0 }], 2400, { text: Math.random() < .5 ? '♪' : '♫', delay: i * (ms / 12) });
  } },
  { scene: 'in', key: 'candle', rect: R(926, 705, 34, 75), walk: 930, act: async () => {
    await reach(-15); SFX.click(); const c = part('candle'); if (c) c.animate([{ filter: 'brightness(1)', transform: 'scale(1)' }, { filter: 'brightness(1.8)', transform: 'scale(1.3)' }, { filter: 'brightness(1)', transform: 'scale(1)' }], { duration: 1200 });
  } },
  { scene: 'in', key: 'window-in', rect: R(1034, 286, 150, 160), walk: 1100, act: async () => {
    H.look = -12; SFX.sparkle(); fx('streak', 1060, 320, [{ transform: 'translate(0,0) rotate(20deg)', opacity: 0 }, { opacity: 1, offset: .2 }, { transform: 'translate(90px,40px) rotate(20deg)', opacity: 0 }], 900);
    await wait(1600); H.look = 0;
  } },
  { scene: 'in', key: 'hook', rect: R(296, 570, 110, 190), walk: 330, act: async () => {
    await reach(-70); SFX.click(); toast('Запасная шапка и любимый шарф.', 2500);
  } },
  { scene: 'in', key: 'pet', rect: R(1122, 846, 108, 60), walk: 1100, face: 1, act: async () => {
    await reach(10, 300, 500);
    for (let i = 0; i < 3; i++) tone(70 + i * 4, .35, { type: 'sawtooth', vol: .05, when: i * .4, vib: 20 });
    poke(img('pet'), [{ transform: 'scale(1,1)' }, { transform: 'scale(1.06,.92)' }, { transform: 'scale(.98,1.05)' }, { transform: 'scale(1,1)' }], 1100, '50% 100%');
    for (let i = 0; i < 4; i++) fx('note', 1180, 840, [{ transform: 'translate(0,0) scale(.6)', opacity: 0 }, { opacity: 1, offset: .2 }, { transform: `translate(${(i - 1.5) * 18}px,-70px) scale(1)`, opacity: 0 }], 1400, { text: '♥', delay: i * 200 });
    toast('Моховой зверёк мурчит у тёплой печки.', 3000);
  } },
  { scene: 'in', key: 'front-shrooms', rect: R(0, 880, 130, 120), walk: 180, act: async () => { SFX.boing(1.4); poke(img('front-left'), [{ transform: 'scale(1)' }, { transform: 'scale(1.1,.85)' }, { transform: 'scale(.95,1.08)' }, { transform: 'scale(1)' }], 700, '50% 100%'); } },
];
function flyOff(p, path, ms, spin) {
  if (reduce) return;
  const frames = path.map(([x, y], i) => ({ transform: `translate(${x}px,${y}px)${spin ? ` rotate(${(i / (path.length - 1)) * 360}deg)` : ''}` }));
  p.querySelectorAll(':scope > img').forEach(el => { el.style.transformOrigin = '50% 50%'; el.animate(frames, { duration: ms, easing: 'ease-in-out' }); });
  p.querySelectorAll(':scope > .p').forEach(el => el.animate(frames, { duration: ms, easing: 'ease-in-out', composite: 'add' }));
}
const allSpots = () => SPOTS.concat(shroomSpots());
const keysTotal = new Set(allSpots().map(s => s.key)).size;
total = keysTotal; $('#ntotal').textContent = total;
function rectOf(s) { return typeof s.rect === 'function' ? s.rect() : s.rect; }
function hit(p) {
  let best = null, area = 1e9;
  for (const s of allSpots()) {
    if (s.scene !== H.scene) continue;
    const r = rectOf(s); if (!r) continue;
    if (p.x >= r.x && p.x <= r.x + r.w && p.y >= r.y && p.y <= r.y + r.h && r.w * r.h < area) { best = s; area = r.w * r.h; }
  }
  return best;
}

// ---------------- moving between the island and the house ----------------
// the door opens in painted frames: closed, ~40°, ~80°, with the lit room behind it
const DOOR = ['door-0', 'door-1', 'door-2'].map(part);
const doorway = part('doorway');
function doorFrame(k) {
  DOOR.forEach((d, i) => { if (d) d.style.opacity = i === k ? 1 : 0; });
  if (doorway) doorway.style.opacity = k > 0 ? 1 : 0;
}
doorFrame(0);
async function doorOut(open, ms = 360) {
  const seq = open ? [1, 2] : [1, 0];
  for (const k of seq) { await wait(ms / seq.length); doorFrame(k); }
}
async function swapScene(to, x, dir) {
  curtain.style.opacity = 1; await wait(380);
  H.scene = to; H.x = x; H.dir = dir; H.target = null; H.pose = null;
  outside.hidden = to !== 'out'; inside.hidden = to !== 'in';
  $(to === 'out' ? '#slot-out' : '#slot-in').appendChild(hero);
  if (musicFilter) { musicFilter.frequency.setTargetAtTime(to === 'in' ? 900 : 18000, ac.currentTime, .4); crackleGain.gain.setTargetAtTime(to === 'in' ? .22 : 0, ac.currentTime, .4); }
  curtain.style.opacity = 0; await wait(380);
}
async function enterHouse() {
  await reach(-40, 200, 100); SFX.creak(); await doorOut(true);
  await tween(450, k => { H.fade = 1 - k; });
  await swapScene('in', 200, 1); H.fade = 1;
  doorFrame(0);
  if (!found.has('door')) toast('Внутри тепло. Тапни по двери, чтобы выйти обратно.');
}
async function leaveHouse() {
  SFX.creak();
  doorFrame(2);
  await swapScene('out', 538, 1); H.fade = 0;
  await tween(400, k => { H.fade = k; });
  H.target = 590; await waitArrive();
  await doorOut(false); SFX.click();
}
function waitArrive() { return new Promise(res => { const c = () => (H.target == null ? res() : requestAnimationFrame(c)); c(); }); }
async function sleep() {
  H.pose = 'sleep'; H.blink = .08;
  SFX.snore(); const zz = setInterval(() => {
    SFX.snore();
    fx('zz', 540, 700, [{ transform: 'translate(0,0) scale(.6)', opacity: 0 }, { opacity: 1, offset: .2 }, { transform: 'translate(40px,-140px) scale(1.4)', opacity: 0 }], 2200, { text: 'z' });
  }, 1300);
  toast('Тсс… гномик спит.', 3000);
  await wait(5200); clearInterval(zz);
  H.pose = null; H.blink = 1; H.x = 600;
}

// ---------------- input ----------------
async function goTo(x, spot) {
  const S = SCN[H.scene];
  H.action = spot || null;
  H.target = Math.max(S.min, Math.min(S.max, x));
}
stage.addEventListener('pointerdown', e => {
  if (!started || H.busy || H.pose === 'sleep') return;
  const p = toStage(e), s = hit(p);
  if (s) { goTo(typeof s.walk === 'function' ? s.walk() : s.walk, s); return; }
  if (H.scene === 'out') {
    const gy = groundY(Math.max(380, Math.min(1230, p.x)));
    if (p.x > 360 && p.x < 1250 && p.y > gy - 140 && p.y < 990) goTo(p.x);
    else { SFX.sparkle(); fx('streak', p.x - 60, p.y, [{ transform: 'translate(0,0) rotate(18deg) scaleX(.2)', opacity: 0 }, { opacity: 1, offset: .2 }, { transform: 'translate(160px,52px) rotate(18deg) scaleX(1)', opacity: 0 }], 900); discover('sky'); }
  } else goTo(p.x);
});
stage.addEventListener('pointermove', e => { if (!started) return; stage.classList.toggle('hot', !!hit(toStage(e))); });
const held = new Set();
addEventListener('keydown', e => {
  if (!started) return;
  const k = e.key.toLowerCase();
  if (['arrowleft', 'a', 'ф'].includes(k)) held.add(-1);
  else if (['arrowright', 'd', 'в'].includes(k)) held.add(1);
  else if ([' ', 'e', 'enter', 'у'].includes(k)) {
    e.preventDefault();
    let best = null, dist = 140;
    for (const s of allSpots()) { if (s.scene !== H.scene) continue; const w = typeof s.walk === 'function' ? s.walk() : s.walk; const d = Math.abs(w - H.x); if (d < dist) { dist = d; best = s; } }
    if (best && !H.busy && H.pose !== 'sleep') goTo(typeof best.walk === 'function' ? best.walk() : best.walk, best);
  }
});
addEventListener('keyup', e => { const k = e.key.toLowerCase(); if (['arrowleft', 'a', 'ф'].includes(k)) held.delete(-1); if (['arrowright', 'd', 'в'].includes(k)) held.delete(1); });

// ---------------- main loop ----------------
let last = performance.now(), started = false;
async function arrive() {
  const s = H.action; H.action = null;
  if (!s) return;
  if (s.face) H.dir = s.face;
  else { const r = rectOf(s); if (r) H.dir = (r.x + r.w / 2) >= H.x ? 1 : -1; }
  H.busy = true;
  try { await s.act(); discover(s.key); } finally { H.busy = false; }
}
// ---------------- 25 frames a second, on purpose ----------------
// Every animation on the page (CSS loops, effects, transitions) is paused and stepped by hand once
// per frame, and the puppet only moves on the same ticks: a stop-motion feel like the original game.
const FRAME = 40;
const clocks = new WeakMap();
function stepAnimations() {
  for (const a of document.getAnimations()) {
    let c = clocks.get(a);
    if (!c) {
      if (a.playState === 'finished' || a.playState === 'idle') continue;
      c = { t: a.currentTime || 0 }; clocks.set(a, c); a.pause();
    } else c.t += FRAME * a.playbackRate;
    a.currentTime = c.t;
    const end = a.effect ? a.effect.getComputedTiming().endTime : Infinity;
    if (isFinite(end) && c.t >= end) { clocks.delete(a); a.finish(); }
  }
}
let acc = 0, frameT = performance.now() / 1000;
function loop(now) {
  acc += now - last; last = now;
  if (acc >= FRAME) {
    const steps = Math.min(3, Math.floor(acc / FRAME));
    acc = Math.min(acc - steps * FRAME, FRAME);
    for (let i = 0; i < steps; i++) { frameT += FRAME / 1000; update(FRAME / 1000, frameT); stepAnimations(); }
    draw(frameT);
  }
  requestAnimationFrame(loop);
}
function update(dt, t) {
  const S = SCN[H.scene];
  if (started && !H.busy && H.pose !== 'sleep' && held.size) {
    const d = [...held].reduce((a, b) => a + b, 0);
    if (d) { H.action = null; H.target = Math.max(S.min, Math.min(S.max, H.x + d * 30)); }
  }
  let moving = false;
  if (H.target != null && H.pose !== 'sleep') {
    const dx = H.target - H.x;
    if (Math.abs(dx) < 1.5) { H.x = H.target; H.target = null; arrive(); }
    else {
      H.dir = Math.sign(dx);
      const step = Math.min(Math.abs(dx), S.speed * dt);
      H.x += H.dir * step; H.phase += step / S.stride; moving = true;
      const st = Math.sign(Math.sin(H.phase));
      if (st !== H.lastStep) { H.lastStep = st; SFX.step(); }
    }
  }
  H.walk += ((moving ? 1 : 0) - H.walk) * Math.min(1, dt * 10);
  if (!moving && H.walk < .02) H.phase = 0;
  H.beam += ((moving || H.busy ? 0 : 0.95) - H.beam) * Math.min(1, dt * 3);
  if (H.pose !== 'sleep') {
    if (t > H.nextBlink) { H.blink = .1; if (t > H.nextBlink + .12) { H.blink = 1; H.nextBlink = t + 2.5 + Math.random() * 3; } }
    if (!moving && !H.busy && t > H.nextLook) { H.lookTo = [-8, 6, -4, 0][Math.floor(Math.random() * 4)]; H.nextLook = t + 3 + Math.random() * 4; }
    if (moving) H.lookTo = 0;
    H.look += (H.lookTo - H.look) * Math.min(1, dt * 3);
  }
}
requestAnimationFrame(loop);

// ---------------- start screen and sound toggle ----------------
const startEl = $('#start');
$('#play').addEventListener('click', () => {
  initAudio(); if (ac && ac.state === 'suspended') ac.resume();
  started = true; startEl.style.opacity = 0; setTimeout(() => { startEl.hidden = true; }, 800);
  $('#found').style.opacity = 1;
  toast('Тапни по земле — гномик пойдёт. Тапни по чему-нибудь — он с этим поиграет. На клавиатуре: стрелки и пробел.', 7000);
});
// the Android wrapper pauses and resumes the sound when the app goes to the background
window.appPause = p => { if (ac) (p ? ac.suspend() : ac.resume()); };
document.addEventListener('visibilitychange', () => { if (ac && !muted) (document.hidden ? ac.suspend() : ac.resume()); });
const snd = $('#snd');
snd.addEventListener('click', () => {
  initAudio(); muted = !muted;
  if (master) master.gain.setTargetAtTime(muted ? 0 : .9, ac.currentTime, .1);
  snd.classList.toggle('playing', !muted); snd.setAttribute('aria-label', muted ? 'Включить звук' : 'Выключить звук');
});
})();
