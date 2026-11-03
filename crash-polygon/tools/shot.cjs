// Model review screenshots. Needs the static server: (cd crash-polygon && python3 -m http.server 8765)
// Usage: NODE_PATH=$(npm root -g) node tools/shot.cjs <out.png> <scenario> [speedSteps] [cam px,py,pz,lx,ly,lz] [xray]
//   scenario: idle | drive | wall | offset | pole | side   (crash tests run 12 s of sim time, i.e. after the impact)
//   speedSteps: Q/E steps from 64 km/h (e.g. 3 → 120 km/h, -2 → 50 km/h)
//   cam: world-space camera position and look-at; "car" in place of it means 4.5 m off the player's left-front.
//   Camera coordinates are relative to the player car's position when prefixed with "@" (e.g. @3,1.2,4,0,0.6,1).
const { chromium } = require('playwright');
(async () => {
  const [out = 'shot.png', sc = 'idle', sp = '0', cam = '', xray = ''] = process.argv.slice(2);
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader'] });
  const p = await b.newPage({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1 });
  p.on('pageerror', e => console.log('PAGEERROR', e.message));
  p.on('console', m => { if (m.type() === 'error') console.log('CONSOLE', m.text().slice(0, 300)); });
  await p.goto('http://localhost:8765/index.html', { waitUntil: 'load' });
  await p.waitForFunction(() => window.__k7, null, { timeout: 60000 });
  const info = await p.evaluate(({ sc, sp, cam, xray }) => {
    const k = window.__k7; const tests = { wall: 0, offset: 1, pole: 2, side: 3 };
    const s = +sp; for (let i = 0; i < Math.abs(s); i++) k.onKey(s > 0 ? 'KeyE' : 'KeyQ');
    if (sc === 'drive') { k.keys.add('KeyW'); k.simulate(3); k.keys.clear(); k.simulate(0.3); }
    else if (sc in tests) { for (let i = 0; i < tests[sc]; i++) k.onKey('KeyB'); k.onKey('KeyC'); k.simulate(12); }
    else k.simulate(0.5);
    if (cam) { let rel = cam.startsWith('@'); const v = cam.replace('@', '').split(',').map(Number); const P = k.player().body.position;
      if (rel) { v[0] += P.x; v[1] += P.y; v[2] += P.z; v[3] += P.x; v[4] += P.y; v[5] += P.z; } k.cam(...v); }
    if (xray) k.xray(true);
    return JSON.stringify(k.state());
  }, { sc, sp, cam, xray });
  console.log(info);
  await p.waitForTimeout(2500);
  await p.screenshot({ path: out });
  await b.close();
})();
