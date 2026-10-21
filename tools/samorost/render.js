// Render one or more stacked SVG files (bottom→top) to a PNG.
// usage: node render.js out.png layer1.svg [layer2.svg ...]
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
(async () => {
  const [out, ...svgs] = process.argv.slice(2);
  const imgs = svgs.map(f => `<div style="position:absolute;inset:0">${fs.readFileSync(path.resolve(f), 'utf8').replace(/<\?xml[^>]*>/, '')}</div>`).join('');
  const html = `<html><body style="margin:0;background:#888"><div style="position:relative;width:1600px;height:1000px">${imgs}</div></body></html>`;
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  await page.setContent(html);
  await page.screenshot({ path: out });
  await browser.close();
})();
