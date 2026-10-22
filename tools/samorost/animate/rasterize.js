// Render every SVG in <buildDir> (static_*.svg and parts/*.svg) to a transparent PNG at 2x.
// usage: node rasterize.js <buildDir>
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
(async () => {
  const dir = process.argv[2];
  const files = ['static_bg.svg', 'static_mid.svg', ...fs.readdirSync(path.join(dir, 'parts')).filter(f => f.endsWith('.svg')).map(f => `parts/${f}`)];
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 2 });
  for (const f of files) {
    const svg = fs.readFileSync(path.join(dir, f), 'utf8');
    await page.setContent(`<html><body style="margin:0;background:transparent">${svg}</body></html>`);
    await page.screenshot({ path: path.join(dir, f.replace(/\.svg$/, '.png')), omitBackground: true });
  }
  await browser.close();
  console.log(`rendered ${files.length}`);
})();
