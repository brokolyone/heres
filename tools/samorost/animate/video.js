// Capture the animated page frame by frame (deterministic, via the Web Animations API).
// usage: node video.js <page.html> <framesDir> [seconds=12] [fps=30]
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
(async () => {
  const [src, dir, secs = '12', fps = '30'] = process.argv.slice(2);
  fs.mkdirSync(dir, { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  await page.goto('file://' + path.resolve(src));
  await page.waitForTimeout(800);
  await page.evaluate(() => document.getAnimations().forEach(a => a.pause()));
  const n = Math.round(+secs * +fps);
  for (let i = 0; i < n; i++) {
    await page.evaluate(t => document.getAnimations().forEach(a => { a.currentTime = t; }), (i * 1000) / +fps);
    await page.screenshot({ path: path.join(dir, `f${String(i).padStart(4, '0')}.png`) });
  }
  await browser.close();
  console.log(`${n} frames`);
})();
