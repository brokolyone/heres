// Render the game's synthesised sound effects (the same Web Audio code as game.js) to WAV files.
// usage: node render_sfx.js <game.js> <outDir>
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
(async () => {
  const [gameJs, out] = process.argv.slice(2);
  const src = fs.readFileSync(gameJs, 'utf8');
  const cut = (a, b) => src.slice(src.indexOf(a), src.indexOf(b, src.indexOf(a)));
  const helpers = cut('function env(g, t, a, peak, d)', 'const SFX = {');
  const sfx = cut('const SFX = {', '// ---------------- discoveries');
  const JOBS = {
    step_out: "H.scene='out';SFX.step()", step_in: "H.scene='in';SFX.step()",
    boing_s: 'SFX.boing(0.7)', boing_m: 'SFX.boing(1.2)', boing_l: 'SFX.boing(2)',
    creak: 'SFX.creak()', snort: 'SFX.snort()', clock: 'SFX.chime([784, 659, 523], .5)', sparkle: 'SFX.sparkle()',
    musicbox: 'SFX.musicbox()', whistle: 'SFX.whistle()', whoosh: 'SFX.whoosh()', crackle: 'SFX.crackle()',
    ding: 'SFX.ding()', click: 'SFX.click()', bloop: 'SFX.bloop()', whirr: 'SFX.whirr()', buzz: 'SFX.buzz()',
    snore: 'SFX.snore()', yay: 'SFX.yay()',
    purr: "for (let i = 0; i < 3; i++) tone(70 + i * 4, .35, { type: 'sawtooth', vol: .05, when: i * .4, vib: 20 })",
  };
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.setContent('<html><body></body></html>');
  for (const [name, call] of Object.entries(JOBS)) {
    const wav = await page.evaluate(async ({ helpers, sfx, call }) => {
      const ac = new OfflineAudioContext(1, 44100 * 6, 44100);
      const master = ac.createGain(); master.gain.value = 0.9; master.connect(ac.destination);
      const muted = false, H = { scene: 'out' };
      eval(helpers + sfx + call);
      const buf = await ac.startRendering();
      const d = buf.getChannelData(0);
      let end = d.length; while (end > 0 && Math.abs(d[end - 1]) < 1e-4) end--;
      end = Math.min(d.length, end + 2205);
      const pcm = new Int16Array(end);
      for (let i = 0; i < end; i++) pcm[i] = Math.max(-1, Math.min(1, d[i])) * 32767;
      return Array.from(new Uint8Array(pcm.buffer));
    }, { helpers, sfx, call });
    const data = Buffer.from(wav);
    const hdr = Buffer.alloc(44);
    hdr.write('RIFF', 0); hdr.writeUInt32LE(36 + data.length, 4); hdr.write('WAVE', 8); hdr.write('fmt ', 12);
    hdr.writeUInt32LE(16, 16); hdr.writeUInt16LE(1, 20); hdr.writeUInt16LE(1, 22); hdr.writeUInt32LE(44100, 24);
    hdr.writeUInt32LE(88200, 28); hdr.writeUInt16LE(2, 32); hdr.writeUInt16LE(16, 34); hdr.write('data', 36); hdr.writeUInt32LE(data.length, 40);
    fs.writeFileSync(path.join(out, `${name}.wav`), Buffer.concat([hdr, data]));
  }
  await browser.close();
  console.log(`sfx: ${Object.keys(JOBS).length}`);
})();
