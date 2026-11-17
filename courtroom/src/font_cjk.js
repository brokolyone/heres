/* =====================================================================
   FONT_CJK — китайские глифы. Пиксельный шрифт Fusion Pixel 12px
   (TakWolf, SIL OFL 1.1), растеризован tools/cjk_font.js в атлас
   assets/font/cjk.png + cjk.json. G.FontCJK.draw рисует глиф нужным цветом.
   ===================================================================== */
(function () {
'use strict';
const G = window.G;
let atlas = null, map = null, cell = 14;
const tinted = {};   // color -> canvas атласа нужного цвета

function tint(color) {
  if (tinted[color]) return tinted[color];
  const c = G.makeCanvas(atlas.width, atlas.height), x = c.getContext('2d');
  x.drawImage(atlas, 0, 0);
  x.globalCompositeOperation = 'source-in';
  x.fillStyle = color; x.fillRect(0, 0, c.width, c.height);
  return (tinted[color] = c);
}

G.FontCJK = {
  h: 12,
  ready: false,
  has(ch) { return !!(map && map[ch]); },
  isCJK(ch) { const u = ch.codePointAt(0); return (u >= 0x2E80 && u <= 0x9FFF) || (u >= 0xF900 && u <= 0xFAFF) || (u >= 0xFF00 && u <= 0xFFEF) || (u >= 0x3000 && u <= 0x303F); },
  advance(ch) { const g = map && map[ch]; return g ? g[2] + 1 : 12; },
  draw(ctx, ch, x, y, color) {
    const g = map && map[ch];
    if (!g) return 12;
    ctx.drawImage(tint(color || '#fbf7f0'), g[0], g[1], cell, cell, x | 0, (y | 0) - 2, cell, cell);
    return g[2] + 1;
  },
  async load(base) {
    try {
      const j = await (await fetch(base + 'assets/font/cjk.json')).json();
      map = j.map; cell = j.cell;
      atlas = await new Promise((res, rej) => { const i = new Image(); i.onload = () => res(i); i.onerror = rej; i.src = base + 'assets/font/cjk.png'; });
      this.ready = true;
    } catch (e) { this.ready = false; }
    return this.ready;
  },
};
})();
