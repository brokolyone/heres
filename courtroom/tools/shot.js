// Скриншот тестовой страницы: node tools/shot.js test/env.html out.png [scale=3] [waitMs=300]
// Страница должна выставить window.__ready = true, когда кадр нарисован в G.buffer.
// Сохраняется именно буфер 384x216 (или window.__shotCanvas, если задан), увеличенный без сглаживания.
const { chromium } = require('playwright');
const path = require('path'), fs = require('fs');
(async () => {
  const [page_, out, sc = '3', wait = '300'] = process.argv.slice(2);
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1280, height: 720 } });
  const errs = [];
  p.on('pageerror', e => errs.push('pageerror: ' + e.message));
  p.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text()); });
  await p.goto('file://' + path.resolve(page_));
  await p.waitForFunction(() => window.__ready === true, null, { timeout: 15000 }).catch(() => errs.push('timeout: __ready not set'));
  await p.waitForTimeout(+wait);
  const data = await p.evaluate((s) => {
    const src = window.__shotCanvas || (window.G && G.buffer);
    if (!src) return null;
    const c = document.createElement('canvas');
    c.width = src.width * s; c.height = src.height * s;
    const x = c.getContext('2d'); x.imageSmoothingEnabled = false;
    x.drawImage(src, 0, 0, c.width, c.height);
    return c.toDataURL('image/png');
  }, +sc);
  if (data) fs.writeFileSync(out, Buffer.from(data.split(',')[1], 'base64'));
  console.log(errs.length ? errs.join('\n') : 'ok, no errors');
  await b.close();
})();
