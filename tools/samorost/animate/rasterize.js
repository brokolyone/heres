// Render every SVG in <buildDir> (static_*.svg, parts/*.svg and iparts/*.svg) to a transparent PNG at 2x.
// usage: node rasterize.js <buildDir>
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
(async () => {
  const dir = process.argv[2];
  const sub = d => fs.existsSync(path.join(dir, d)) ? fs.readdirSync(path.join(dir, d)).filter(f => f.endsWith('.svg')).map(f => `${d}/${f}`) : [];
  const files = [...fs.readdirSync(dir).filter(f => /^static_.*\.svg$/.test(f)), ...sub('parts'), ...sub('iparts')];
  const browser = await chromium.launch();
  for (const f of files) {
    // a fresh page per file: heavy filter layers rendered one after another in the same page
    // can exhaust the renderer and get silently dropped from later screenshots
    const page = await browser.newPage({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 2 });
    const svg = fs.readFileSync(path.join(dir, f), 'utf8');
    await page.setContent(`<html><body style="margin:0;background:transparent">${svg}</body></html>`);
    await page.screenshot({ path: path.join(dir, f.replace(/\.svg$/, '.png')), omitBackground: true });
    await page.close();
  }
  await browser.close();
  console.log(`rendered ${files.length}`);
})();
