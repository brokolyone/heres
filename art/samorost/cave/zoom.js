// usage: node zoom.js out_prefix layer.svg ...   -> out_prefix_z6.png (dsf 6 crop) and out_prefix_1x.png (real-size crop, upscaled x4 nearest)
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const fs = require('fs'), path = require('path');
(async () => {
  const [out, ...svgs] = process.argv.slice(2);
  const imgs = svgs.map(f => `<div style="position:absolute;inset:0">${fs.readFileSync(path.resolve(f), 'utf8').replace(/<\?xml[^>]*>/, '')}</div>`).join('');
  const html = `<html><body style="margin:0;background:#888"><div style="position:relative;width:1600px;height:1000px">${imgs}</div></body></html>`;
  const browser = await chromium.launch();
  for (const [dsf, suf, clip] of [[6, 'z6', { x: 450, y: 680, width: 140, height: 130 }], [1, '1x', { x: 380, y: 620, width: 280, height: 240 }]]) {
    const page = await browser.newPage({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: dsf });
    await page.setContent(html);
    await page.screenshot({ path: `${out}_${suf}.png`, clip });
    await page.close();
  }
  await browser.close();
})();
