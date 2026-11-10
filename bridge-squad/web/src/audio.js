// Tiny synthesized sound kit: no audio files, everything generated with WebAudio.
let ctx = null, master = null, noiseBuf = null;
let enabled = true;
let lastShot = 0;

export function setSound(on) { enabled = on; if (master) master.gain.value = on ? 0.55 : 0; }
export function soundOn() { return enabled; }

export function unlock() {
  if (!ctx) {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    ctx = new AC();
    master = ctx.createGain();
    master.gain.value = enabled ? 0.55 : 0;
    const comp = ctx.createDynamicsCompressor();
    master.connect(comp).connect(ctx.destination);
    noiseBuf = ctx.createBuffer(1, ctx.sampleRate * 0.5, ctx.sampleRate);
    const d = noiseBuf.getChannelData(0);
    for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
  }
  if (ctx.state === 'suspended') ctx.resume();
}
export function suspend() { if (ctx && ctx.state === 'running') ctx.suspend(); }

function tone(freq, dur, { type = 'square', vol = 0.2, slide = 0, delay = 0, attack = 0.005 } = {}) {
  if (!ctx || !enabled) return;
  const t = ctx.currentTime + delay;
  const o = ctx.createOscillator(), g = ctx.createGain();
  o.type = type; o.frequency.setValueAtTime(freq, t);
  if (slide) o.frequency.exponentialRampToValueAtTime(Math.max(30, freq * slide), t + dur);
  g.gain.setValueAtTime(0.0001, t);
  g.gain.exponentialRampToValueAtTime(vol, t + attack);
  g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  o.connect(g).connect(master); o.start(t); o.stop(t + dur + 0.02);
}
function noise(dur, { vol = 0.2, freq = 2000, q = 1, type = 'bandpass', delay = 0, sweep = 0 } = {}) {
  if (!ctx || !enabled) return;
  const t = ctx.currentTime + delay;
  const s = ctx.createBufferSource(); s.buffer = noiseBuf;
  const f = ctx.createBiquadFilter(); f.type = type; f.frequency.setValueAtTime(freq, t); f.Q.value = q;
  if (sweep) f.frequency.exponentialRampToValueAtTime(freq * sweep, t + dur);
  const g = ctx.createGain();
  g.gain.setValueAtTime(vol, t); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  s.connect(f).connect(g).connect(master); s.start(t, Math.random() * 0.3); s.stop(t + dur + 0.02);
}

export const sfx = {
  shot() {
    if (!ctx) return;
    const now = ctx.currentTime;
    if (now - lastShot < 0.075) return;
    lastShot = now;
    noise(0.06, { vol: 0.09, freq: 3200 + Math.random() * 800, q: 0.8 });
    tone(180 + Math.random() * 40, 0.05, { type: 'triangle', vol: 0.05, slide: 0.5 });
  },
  hit() { noise(0.05, { vol: 0.06, freq: 1400, q: 2 }); },
  pop() { noise(0.12, { vol: 0.14, freq: 900, q: 1.2, sweep: 0.4 }); tone(320, 0.08, { type: 'square', vol: 0.04, slide: 0.5 }); },
  ouch() { tone(260, 0.12, { type: 'sawtooth', vol: 0.06, slide: 0.6 }); },
  gateGood() { [523, 659, 784, 1046].forEach((f, i) => tone(f, 0.14, { type: 'square', vol: 0.07, delay: i * 0.055 })); },
  gateBad() { [392, 311, 233].forEach((f, i) => tone(f, 0.18, { type: 'sawtooth', vol: 0.07, delay: i * 0.08 })); },
  gateTick() { tone(1200 + Math.random() * 200, 0.03, { type: 'sine', vol: 0.05 }); },
  smash() { noise(0.4, { vol: 0.35, freq: 600, q: 0.7, sweep: 0.25, type: 'lowpass' }); tone(110, 0.3, { type: 'sine', vol: 0.25, slide: 0.4 }); },
  coin() { tone(988, 0.07, { type: 'square', vol: 0.06 }); tone(1319, 0.16, { type: 'square', vol: 0.06, delay: 0.06 }); },
  buy() { [660, 880, 1320].forEach((f, i) => tone(f, 0.1, { type: 'triangle', vol: 0.12, delay: i * 0.05 })); },
  deny() { tone(150, 0.18, { type: 'square', vol: 0.08 }); },
  click() { tone(700, 0.04, { type: 'triangle', vol: 0.1 }); },
  bossRoar() { tone(90, 0.7, { type: 'sawtooth', vol: 0.18, slide: 0.6 }); noise(0.6, { vol: 0.12, freq: 400, q: 1, sweep: 0.5 }); },
  bossDown() { noise(0.9, { vol: 0.4, freq: 800, q: 0.6, sweep: 0.15, type: 'lowpass' }); tone(70, 0.9, { type: 'sine', vol: 0.35, slide: 0.5 }); },
  win() { [523, 659, 784, 659, 784, 1046].forEach((f, i) => tone(f, i === 5 ? 0.5 : 0.14, { type: 'square', vol: 0.08, delay: i * 0.11 })); },
  lose() { [392, 370, 349, 262].forEach((f, i) => tone(f, i === 3 ? 0.6 : 0.22, { type: 'triangle', vol: 0.14, delay: i * 0.2 })); },
};
