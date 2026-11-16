const { chromium } = require('playwright'); const fs = require('fs');
(async () => {
  const [ids, out] = [process.argv[2].split(','), process.argv[3]];
  const b = await chromium.launch({ args: ['--autoplay-policy=no-user-gesture-required'] });
  const p = await b.newPage();
  await p.goto('http://localhost:8765/test/audio.html');
  for (const id of ids) {
    const data = await p.evaluate(async (id) => {
      G.Audio.unlock(); const st = G.Audio._tap();
      if (id.startsWith('sfx:')) { await new Promise(r => setTimeout(r, 1500)); }
      const rec = new MediaRecorder(st, { mimeType: 'audio/webm' }); const ch = [];
      rec.ondataavailable = e => ch.push(e.data);
      if (id.startsWith('sfx:')) { rec.start(); G.Audio.sfx(id.slice(4)); await new Promise(r => setTimeout(r, 3000)); }
      else { G.Audio.music(id); await new Promise(r => setTimeout(r, 2200)); rec.start(); await new Promise(r => setTimeout(r, 16000)); G.Audio.music('silence'); }
      rec.stop(); await new Promise(r => rec.onstop = r);
      const buf = await new Blob(ch).arrayBuffer(); let s = ''; const u = new Uint8Array(buf);
      for (let i = 0; i < u.length; i++) s += String.fromCharCode(u[i]); return btoa(s);
    }, id);
    fs.writeFileSync(out + '/' + id.replace(':', '_') + '.webm', Buffer.from(data, 'base64'));
  }
  await b.close();
})();
