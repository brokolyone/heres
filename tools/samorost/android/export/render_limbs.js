// Render each puppet limb SVG (full 1600x1000 canvas) at high resolution, clipped to its bounding box.
// usage: node render_limbs.js <limbs.json> <outDir> <scale>
// limbs.json: [{ id, svg }] -> <outDir>/<id>.png and <outDir>/limbs_box.json ({ id: [x, y, w, h] } in canvas px)
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
(async () => {
  const [list, out, scale] = process.argv.slice(2);
  const limbs = JSON.parse(fs.readFileSync(list, 'utf8'));
  const browser = await chromium.launch();
  const boxes = {};
  for (const { id, svg } of limbs) {
    const page = await browser.newPage({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: +scale });
    await page.setContent(`<html><body style="margin:0;background:transparent">${svg}</body></html>`);
    const b = await page.evaluate(() => { const r = document.querySelector('#limb').getBBox(); return [r.x, r.y, r.width, r.height]; });
    const m = 8, x = Math.max(0, Math.floor(b[0] - m)), y = Math.max(0, Math.floor(b[1] - m));
    const w = Math.min(1600 - x, Math.ceil(b[2] + 2 * m)), h = Math.min(1000 - y, Math.ceil(b[3] + 2 * m));
    await page.screenshot({ path: path.join(out, `${id}.png`), clip: { x, y, width: w, height: h }, omitBackground: true });
    boxes[id] = [x, y, w, h];
    await page.close();
  }
  fs.writeFileSync(path.join(out, 'limbs_box.json'), JSON.stringify(boxes));
  await browser.close();
})();
