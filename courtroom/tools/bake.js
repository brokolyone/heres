// Запекание всех спрайтов в PNG: node tools/bake.js
//  1) открывает игру в режиме ?bake, вызывает все G.prebuild
//  2) сохраняет каждый ключ G.cacheCanvas как assets/png/<key>.png
//  3) пакует атласы assets/atlas/atlas_N.png + atlas.json (их грузит игра)
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
const root = path.resolve(__dirname, '..');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage();
  const errs = [];
  p.on('pageerror', e => errs.push(e.message));
  await p.goto('http://localhost:8765/index.html?bake=1&nobake_atlas=1');
  await p.waitForFunction(() => window.__bakeReady === true, null, { timeout: 30000 });
  const keys = await p.evaluate(() => {
    G.Assets.imgs = {};                       // запекаем из кода, не из старого атласа
    for (const k in G.Assets.registry) if (G.Assets.registry[k]._baked) delete G.Assets.registry[k];
    for (const f of G.Assets.prebuilders) { try { f(); } catch (e) { console.error('prebuild', e.message); } }
    return Object.keys(G.Assets.registry).sort();
  });
  console.log('keys', keys.length);
  const pngDir = path.join(root, 'assets/png');
  fs.rmSync(pngDir, { recursive: true, force: true });
  for (let i = 0; i < keys.length; i += 200) {
    const chunk = keys.slice(i, i + 200);
    const data = await p.evaluate(ks => ks.map(k => { const c = G.Assets.registry[k]; return c.width && c.height ? c.toDataURL('image/png') : null; }), chunk);
    chunk.forEach((k, j) => {
      if (!data[j]) return;
      const f = path.join(pngDir, k.replace(/[^a-zA-Z0-9_\/.-]/g, '_') + '.png');
      fs.mkdirSync(path.dirname(f), { recursive: true });
      fs.writeFileSync(f, Buffer.from(data[j].split(',')[1], 'base64'));
    });
  }
  // атласы: упаковка полками
  const sheets = await p.evaluate((keys) => {
    const S = 2048, items = keys.map(k => ({ k, c: G.Assets.registry[k] })).filter(o => o.c.width && o.c.height && o.c.width <= S && o.c.height <= S);
    items.sort((a, b) => b.c.height - a.c.height);
    const out = []; let cur = null, x = 0, y = 0, rowH = 0;
    const newSheet = () => { cur = document.createElement('canvas'); cur.width = S; cur.height = S; out.push({ cv: cur, frames: {} }); x = 0; y = 0; rowH = 0; };
    newSheet();
    for (const it of items) {
      const w = it.c.width, h = it.c.height;
      if (x + w > S) { x = 0; y += rowH + 1; rowH = 0; }
      if (y + h > S) { newSheet(); }
      cur.getContext('2d').drawImage(it.c, x, y);
      out[out.length - 1].frames[it.k] = [x, y, w, h];
      x += w + 1; rowH = Math.max(rowH, h);
    }
    return out.map((s, i) => ({ file: 'atlas_' + i + '.png', data: s.cv.toDataURL('image/png'), frames: s.frames }));
  }, keys);
  const atDir = path.join(root, 'assets/atlas');
  fs.rmSync(atDir, { recursive: true, force: true }); fs.mkdirSync(atDir, { recursive: true });
  for (const s of sheets) fs.writeFileSync(path.join(atDir, s.file), Buffer.from(s.data.split(',')[1], 'base64'));
  fs.writeFileSync(path.join(atDir, 'atlas.json'), JSON.stringify({ version: Date.now(), sheets: sheets.map(s => ({ file: s.file, frames: s.frames })) }));
  console.log('png files', keys.length, 'atlases', sheets.length);
  if (errs.length) console.log(errs.slice(0, 10).join('\n'));
  await b.close();
})();
