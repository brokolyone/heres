// Растеризация пиксельного шрифта Fusion Pixel 12px (OFL) в атлас глифов.
// node tools/cjk_font.js  — собирает все CJK-символы из src/locale/*.js и пишет assets/font/cjk.png + cjk.json
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
(async () => {
  const root = path.resolve(__dirname, '..');
  let text = '';
  const ldir = path.join(root, 'src/locale');
  if (fs.existsSync(ldir)) for (const f of fs.readdirSync(ldir)) text += fs.readFileSync(path.join(ldir, f), 'utf8');
  text += process.argv.slice(2).join('');
  const chars = [...new Set([...text].filter(c => { const u = c.codePointAt(0); return (u >= 0x2E80 && u <= 0x9FFF) || (u >= 0xF900 && u <= 0xFAFF) || (u >= 0xFF00 && u <= 0xFFEF) || (u >= 0x3000 && u <= 0x303F); }))].sort();
  console.log('chars', chars.length);
  const b = await chromium.launch(); const p = await b.newPage();
  await p.goto('http://localhost:8765/test/core_demo.html');
  const font = fs.readFileSync(path.join(root, 'assets/font/fusion-pixel-12px-sc.woff2')).toString('base64');
  const res = await p.evaluate(async ({ font, chars }) => {
    const ff = new FontFace('FP12', 'url(data:font/woff2;base64,' + font + ')');
    await ff.load(); document.fonts.add(ff);
    const cell = 14, cols = 64, rows = Math.ceil(chars.length / cols) || 1;
    const out = document.createElement('canvas'); out.width = cols * cell; out.height = rows * cell;
    const o = out.getContext('2d');
    const tmp = document.createElement('canvas'); tmp.width = 32; tmp.height = 32;
    const t = tmp.getContext('2d', { willReadFrequently: true });
    const map = {};
    chars.forEach((ch, i) => {
      t.clearRect(0, 0, 32, 32); t.font = '12px FP12'; t.textBaseline = 'top'; t.fillStyle = '#fff';
      t.fillText(ch, 2, 2);
      const w = Math.round(t.measureText(ch).width);
      const d = t.getImageData(0, 0, 32, 32).data;
      const cx = (i % cols) * cell, cy = Math.floor(i / cols) * cell;
      o.fillStyle = '#fff';
      for (let y = 0; y < 14; y++) for (let x = 0; x < 14; x++) if (d[((y + 2) * 32 + x + 2) * 4 + 3] > 110) o.fillRect(cx + x, cy + y, 1, 1);
      map[ch] = [cx, cy, Math.min(13, Math.max(w, 4))];
    });
    return { png: out.toDataURL('image/png'), map };
  }, { font, chars });
  fs.writeFileSync(path.join(root, 'assets/font/cjk.png'), Buffer.from(res.png.split(',')[1], 'base64'));
  fs.writeFileSync(path.join(root, 'assets/font/cjk.json'), JSON.stringify({ cell: 14, h: 12, map: res.map }));
  await b.close();
})();
