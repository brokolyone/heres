/* =====================================================================
   UI — интерфейс «Слово защиты»: ореховое дерево, латунь, бумага, мастика.
   Компоненты: drawDialog, button, drawCredibility, courtRecord, drawDocument,
   drawStamp, drawShout, choice, crossHUD, drawWipe.
   Сцены: TitleScene, CaseSelectScene, SettingsScene, CreditsScene.
   ===================================================================== */
(function () {
'use strict';
const G = window.G;
const R = G.RAMP, P = G.PAL;
const W = G.W, H = G.H;
const inp = G.input;

const sfx = id => { if (G.Audio && G.Audio.sfx) G.Audio.sfx(id); };
const T = (c, s, x, y, col, o) => G.Font ? G.Font.draw(c, s, x, y, col, o) : 0;
const M = (s, o) => G.Font ? G.Font.measure(s, o) : String(s).length * 6;
const WRAP = (s, w, o) => G.Font ? G.Font.wrap(s, w, o) : [String(s)];
const STRIP = s => G.Font ? G.Font.strip(s) : String(s);
const kp = (...ks) => ks.some(k => inp.keyPressed(k));

/* ---------------------------------------------------------------------
   Общие примитивы
   --------------------------------------------------------------------- */
function bevel(c, x, y, w, h, face, light, dark) {
  G.rect(c, x, y, w, h, face);
  G.rect(c, x, y, w, 1, light); G.rect(c, x, y, 1, h, light);
  G.rect(c, x, y + h - 1, w, 1, dark); G.rect(c, x + w - 1, y + 1, 1, h - 1, dark);
}
/* Ореховая доска с волокнами */
function woodFill(c, x, y, w, h, seed, base) {
  base = base == null ? 2 : base;
  const rnd = G.rng(seed || 7);
  G.rect(c, x, y, w, h, R.wood[base]);
  for (let j = 0; j < h; j++) {
    let i = Math.floor(rnd() * 12) - 12;
    while (i < w) {
      const len = 4 + Math.floor(rnd() * 22);
      const r = rnd();
      const col = r < 0.45 ? R.wood[Math.max(0, base - 1)] : r < 0.6 ? R.wood[Math.min(6, base + 1)] : null;
      if (col) {
        const a = Math.max(0, i), b = Math.min(w, i + len);
        if (b > a) G.rect(c, x + a, y + j, b - a, 1, col);
      }
      i += len + Math.floor(rnd() * 10);
    }
  }
  // сучок
  if (w > 40 && h > 10) {
    const kx = x + 8 + Math.floor(rnd() * (w - 16)), ky = y + 3 + Math.floor(rnd() * (h - 6));
    G.rect(c, kx - 2, ky, 5, 1, R.wood[Math.max(0, base - 1)]);
    G.rect(c, kx - 1, ky - 1, 3, 1, R.wood[Math.max(0, base - 1)]);
    G.px(c, kx, ky, R.wood[0]);
  }
}
/* Латунная заклёпка 4×4 */
function rivet(c, x, y) {
  G.rect(c, x, y, 4, 4, P.outline);
  G.rect(c, x + 1, y, 2, 4, R.gold[2]); G.rect(c, x, y + 1, 4, 2, R.gold[2]);
  G.rect(c, x + 1, y + 1, 2, 2, R.gold[4]);
  G.px(c, x + 1, y + 1, R.gold[5]);
  G.px(c, x + 2, y + 2, R.gold[3]);
}
/* Латунная рамка (3 px) */
function brassFrame(c, x, y, w, h) {
  G.frame(c, x, y, w, h, P.outline);
  G.frame(c, x + 1, y + 1, w - 2, h - 2, R.gold[3]);
  G.rect(c, x + 1, y + 1, w - 2, 1, R.gold[5]);
  G.rect(c, x + 1, y + 1, 1, h - 2, R.gold[4]);
  G.rect(c, x + 1, y + h - 2, w - 2, 1, R.gold[1]);
  G.rect(c, x + w - 2, y + 2, 1, h - 3, R.gold[2]);
  G.frame(c, x + 2, y + 2, w - 4, h - 4, P.outline);
}
const dimCache = {};
function dim(c, lvl) {
  lvl = G.clamp(lvl | 0, 0, 16);
  if (!lvl) return;
  let s = dimCache[lvl];
  if (!s) { s = dimCache[lvl] = G.makeSprite(W, H, x => G.dither(x, 0, 0, W, H, P.black, lvl)); }
  c.drawImage(s, 0, 0);
}
function shadowRect(c, x, y, w, h, a) {
  c.globalAlpha = a || 0.35; G.rect(c, x, y, w, h, P.shadow); c.globalAlpha = 1;
}
/* value noise (для неровной мастики) */
function hash2(x, y, s) {
  let h = (x * 374761393 + y * 668265263 + s * 2246822519) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
}
function vnoise(x, y, s) {
  const xi = Math.floor(x), yi = Math.floor(y), fx = x - xi, fy = y - yi;
  const a = hash2(xi, yi, s), b = hash2(xi + 1, yi, s), c = hash2(xi, yi + 1, s), d = hash2(xi + 1, yi + 1, s);
  const u = fx * fx * (3 - 2 * fx), v = fy * fy * (3 - 2 * fy);
  return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
}
function strSeed(s) { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }

/* Попиксельный поворот и масштаб (ближайший сосед, сэмплирование вручную) */
function xform(src, deg, scale) {
  scale = scale || 1;
  const a = deg * Math.PI / 180, ca = Math.cos(a), sa = Math.sin(a);
  const sw = src.width, sh = src.height;
  const bw = Math.ceil((Math.abs(sw * ca) + Math.abs(sh * sa)) * scale) + 2;
  const bh = Math.ceil((Math.abs(sw * sa) + Math.abs(sh * ca)) * scale) + 2;
  const out = G.makeCanvas(bw, bh);
  const sd = new Uint32Array(src.getContext('2d').getImageData(0, 0, sw, sh).data.buffer);
  const oc = out.getContext('2d');
  const id = oc.createImageData(bw, bh);
  const od = new Uint32Array(id.data.buffer);
  const scx = sw / 2, scy = sh / 2, dcx = bw / 2, dcy = bh / 2;
  for (let y = 0; y < bh; y++) for (let x = 0; x < bw; x++) {
    const dx = (x + 0.5 - dcx) / scale, dy = (y + 0.5 - dcy) / scale;
    const sx = Math.floor(dx * ca + dy * sa + scx), sy = Math.floor(-dx * sa + dy * ca + scy);
    if (sx >= 0 && sy >= 0 && sx < sw && sy < sh) od[y * bw + x] = sd[sy * sw + sx];
  }
  oc.putImageData(id, 0, 0);
  return out;
}
/* Целочисленное увеличение (дублирование пикселей) */
function zoomInt(src, z) {
  if (z === 1) return src;
  const out = G.makeCanvas(src.width * z, src.height * z);
  const sd = new Uint32Array(src.getContext('2d').getImageData(0, 0, src.width, src.height).data.buffer);
  const oc = out.getContext('2d');
  const id = oc.createImageData(out.width, out.height);
  const od = new Uint32Array(id.data.buffer);
  for (let y = 0; y < out.height; y++) for (let x = 0; x < out.width; x++) od[y * out.width + x] = sd[((y / z) | 0) * src.width + ((x / z) | 0)];
  oc.putImageData(id, 0, 0);
  return out;
}
G.UI_xform = xform;

/* ---------------------------------------------------------------------
   СПРАЙТЫ
   --------------------------------------------------------------------- */
const GAVEL = G.fromMap([
  '..........ooo.',
  '.........oaabo',
  '.........oabco',
  'oooooooooghcco',
  'oaaaabbbbghcco',
  'occcddddeghdco',
  'oooooooooghdeo',
  '.........ocdeo',
  '.........odeeo',
  '..........ooo.',
], { o: P.outline, a: R.wood[6], b: R.wood[5], c: R.wood[4], d: R.wood[3], e: R.wood[2], g: R.gold[3], h: R.gold[5] });
const PADLOCK = G.fromMap([
  '..ooooo..',
  '.osSSSso.',
  '.os...so.',
  '.os...so.',
  'ooooooooo',
  'ohHHHHHgo',
  'oHGGGGGgo',
  'oGGGoGGdo',
  'oGGGoGGdo',
  'oggggggdo',
  'ooooooooo',
], { o: P.outline, s: R.neutral[6], S: R.neutral[8], h: R.gold[5], H: R.gold[4], G: R.gold[3], g: R.gold[2], d: R.gold[1] });
const ARROW_DN = G.fromMap([
  'ooooooooo',
  'ohhhhhhgo',
  '.ohhhhgo.',
  '..ohhgo..',
  '...ogo...',
  '....o....',
], { o: P.outline, h: R.gold[5], g: R.gold[3] });

/* ---------------------------------------------------------------------
   ДИАЛОГ
   --------------------------------------------------------------------- */
const DLG_Y = 150, DLG_H = 66;
let dlgFrame = null;
function buildDialogFrame() {
  return G.makeSprite(W, DLG_H, c => {
    // ореховая рама
    woodFill(c, 0, 0, W, DLG_H, 31, 2);
    G.rect(c, 0, 0, W, 1, P.outline);
    G.rect(c, 0, 1, W, 1, R.wood[4]);
    G.rect(c, 0, 2, W, 1, R.wood[3]);
    G.rect(c, 0, DLG_H - 1, W, 1, R.wood[0]);
    // латунная вставка
    const ix = 5, iy = 6, iw = W - 10, ih = DLG_H - 11;
    G.frame(c, ix - 2, iy - 2, iw + 4, ih + 4, R.wood[0]);
    G.rect(c, ix - 2, iy + ih + 1, iw + 4, 1, R.wood[4]);
    G.rect(c, ix + iw + 1, iy - 2, 1, ih + 4, R.wood[4]);
    G.frame(c, ix - 1, iy - 1, iw + 2, ih + 2, R.gold[2]);
    G.rect(c, ix - 1, iy - 1, iw + 2, 1, R.gold[4]);
    G.rect(c, ix - 1, iy - 1, 1, ih + 2, R.gold[3]);
    // тёмная панель
    G.rect(c, ix, iy, iw, ih, R.neutral[1]);
    G.rect(c, ix, iy, iw, 1, P.black);
    G.rect(c, ix, iy, 1, ih, P.black);
    G.dither(c, ix + 1, iy + 1, iw - 1, 3, P.black, 6);
    G.dither(c, ix + 1, iy + ih - 6, iw - 1, 6, R.neutral[2], 3);
    // заклёпки
    rivet(c, 1, 2); rivet(c, W - 5, 2); rivet(c, 1, DLG_H - 6); rivet(c, W - 5, DLG_H - 6);
    // гравировка на нижней планке
    for (let x = 40; x < W - 40; x += 2) G.px(c, x, DLG_H - 3, R.wood[1]);
  });
}
const plateCache = {};
function namePlate(name) {
  if (plateCache[name]) return plateCache[name];
  const tw = M(name, { font: 'small' });
  const w = tw + 20, h = 14;
  const s = G.makeSprite(w, h + 2, c => {
    shadowRect(c, 2, 2, w - 2, h, 0.45);
    G.rect(c, 0, 0, w - 1, h, P.outline);
    G.rect(c, 1, 1, w - 3, h - 2, R.gold[3]);
    G.rect(c, 1, 1, w - 3, 1, R.gold[5]);
    G.rect(c, 1, 2, 1, h - 3, R.gold[4]);
    G.rect(c, 1, h - 2, w - 3, 1, R.gold[1]);
    G.rect(c, w - 3, 2, 1, h - 3, R.gold[2]);
    G.dither(c, 2, 3, w - 6, h - 6, R.gold[4], 3);
    // винтики
    for (const sx of [4, w - 7]) {
      G.rect(c, sx, 5, 3, 3, R.gold[1]); G.px(c, sx + 1, 6, R.gold[5]); G.px(c, sx, 5, R.gold[2]);
    }
    // гравированный текст: тёмная прорезь + светлая кромка снизу
    T(c, name, 10, 3, R.wood[0], { shadow: R.gold[5], shadowX: 0, shadowY: 1 });
  });
  plateCache[name] = s;
  return s;
}

function drawDialog(c, o) {
  o = o || {};
  if (!dlgFrame) dlgFrame = buildDialogFrame();
  const t = o.t || G.time || 0;
  const y0 = o.y == null ? DLG_Y : o.y;
  c.drawImage(dlgFrame, 0, y0);
  if (o.name) {
    const pl = namePlate(o.name);
    const px = o.side === 'right' ? W - pl.width - 10 : 10;
    // латунный кронштейн под табличкой
    G.rect(c, px + 4, y0 - 1, pl.width - 10, 2, R.wood[0]);
    c.drawImage(pl, px, y0 - 10);
  }
  const col = o.color || R.paper[4];
  const emph = o.emph || R.red[4];
  const lines = WRAP(o.text || '', W - 30, { font: 'small' });
  let budget = o.shown == null ? Infinity : o.shown;
  const ty = y0 + (o.name ? 11 : 10);
  for (let i = 0; i < lines.length && i < 5; i++) {
    if (budget <= 0) break;
    T(c, lines[i], 14, ty + i * 10, col, { maxChars: budget, shadow: P.black, shadowX: 0, shadowY: 1, emph });
    budget -= STRIP(lines[i]).length + 1;
  }
  if (o.waiting) {
    const bob = Math.round(Math.sin(t * 7) * 1.5);
    if (((t * 2.2) | 0) % 3 !== 2) c.drawImage(ARROW_DN, W - 22, y0 + DLG_H - 15 + bob);
  }
}

/* ---------------------------------------------------------------------
   КНОПКА
   --------------------------------------------------------------------- */
const BTN_STYLES = {
  normal: { face: R.wood[3], hi: R.wood[4], light: R.wood[5], dark: R.wood[1], text: R.paper[4], shadow: R.wood[0], hiText: R.gold[5] },
  primary: { face: R.gold[3], hi: R.gold[4], light: R.gold[5], dark: R.gold[1], text: R.wood[0], shadow: R.gold[5], hiText: R.wood[0] },
  danger: { face: R.red[2], hi: R.red[3], light: R.red[4], dark: R.red[0], text: R.paper[4], shadow: R.red[0], hiText: R.gold[5] },
};
function hotkeyHit(hk) {
  if (!hk) return false;
  const arr = Array.isArray(hk) ? hk : [hk];
  return arr.some(k => inp.keyPressed(k) || (k.length === 1 && inp.keyPressed(k.toUpperCase())));
}
function button(c, r, label, o) {
  o = o || {};
  const st = BTN_STYLES[o.kind] || BTN_STYLES.normal;
  const hover = !o.disabled && (inp.inRect(r) || o.selected);
  const down = !o.disabled && inp.down && inp.inRect(r);
  const { x, y, w, h } = r;
  const oy = down ? 1 : 0;
  // тень под кнопкой
  shadowRect(c, x + 1, y + h, w, 1, 0.45);
  G.rect(c, x, y + oy, w, h - oy, P.outline);
  if (o.disabled) {
    bevel(c, x + 1, y + 1 + oy, w - 2, h - 2 - oy, R.neutral[3], R.neutral[4], R.neutral[2]);
  } else {
    bevel(c, x + 1, y + 1 + oy, w - 2, h - 2 - oy, hover ? st.hi : st.face, st.light, st.dark);
    if (!down) G.rect(c, x + 2, y + h - 3, w - 4, 1, hover ? st.face : st.dark);
    if (hover) {
      // латунные уголки-маркеры
      const g = R.gold[5];
      G.rect(c, x - 1, y - 1 + oy, 3, 1, g); G.rect(c, x - 1, y - 1 + oy, 1, 3, g);
      G.rect(c, x + w - 2, y - 1 + oy, 3, 1, g); G.rect(c, x + w, y - 1 + oy, 1, 3, g);
      G.rect(c, x - 1, y + h, 3, 1, g); G.rect(c, x - 1, y + h - 2, 1, 3, g);
      G.rect(c, x + w - 2, y + h, 3, 1, g); G.rect(c, x + w, y + h - 2, 1, 3, g);
    }
  }
  const txtCol = o.disabled ? R.neutral[6] : hover ? st.hiText : st.text;
  let lbl = String(label);
  let keyLbl = o.hotkeyLabel || null;
  const lw = M(lbl);
  const kw = keyLbl ? M(keyLbl) + 5 : 0;
  const tx = x + ((w - lw - kw) >> 1);
  const ty = y + ((h - 8) >> 1) + oy - 1;
  T(c, lbl, tx, ty, txtCol, { shadow: o.disabled ? null : st.shadow, shadowX: 0, shadowY: 1 });
  if (keyLbl) {
    const kx = tx + lw + 4;
    G.rect(c, kx - 1, ty, kw - 2, 9, o.disabled ? R.neutral[2] : st.dark);
    T(c, keyLbl, kx, ty, o.disabled ? R.neutral[5] : st.light);
  }
  if (o.disabled) return false;
  const hit = inp.clicked(r) || hotkeyHit(o.hotkey);
  if (hit && !o.silent) sfx(o.sound || 'select');
  return hit;
}

/* ---------------------------------------------------------------------
   ДОВЕРИЕ: латунные медальоны с сургучными печатями
   --------------------------------------------------------------------- */
let sealOk = null, sealLost = null, sealFlash = null;
function buildSeals() {
  const base = (c) => {
    // латунная оправа
    G.ellipse(c, 7, 7, 7, 7, P.outline);
    G.ellipse(c, 7, 7, 6, 6, R.gold[2]);
    G.ellipse(c, 6, 6, 5, 5, R.gold[4]);
    G.ellipse(c, 7, 7, 5, 5, R.gold[3]);
  };
  sealOk = G.makeSprite(15, 15, c => {
    base(c);
    G.ellipse(c, 7, 7, 4, 4, R.red[1]);
    G.ellipse(c, 7, 7, 4, 3, R.red[2]);
    G.ellipse(c, 6, 6, 3, 3, R.red[3]);
    // рельеф: весы правосудия
    G.rect(c, 5, 5, 5, 1, R.red[4]); G.rect(c, 7, 4, 1, 5, R.red[4]);
    G.px(c, 5, 6, R.red[1]); G.px(c, 9, 6, R.red[1]); G.rect(c, 6, 9, 3, 1, R.red[1]);
    G.px(c, 5, 4, R.red[5]);
  });
  sealLost = G.makeSprite(15, 15, c => {
    base(c);
    G.ellipse(c, 7, 7, 4, 4, R.neutral[1]);
    G.ellipse(c, 8, 8, 3, 3, R.neutral[2]);
    // обломки сургуча и трещина
    G.rect(c, 4, 9, 2, 2, R.red[1]); G.px(c, 5, 9, R.red[2]);
    G.rect(c, 9, 4, 2, 1, R.red[1]);
    G.line(c, 5, 4, 7, 7, P.black); G.line(c, 7, 7, 6, 10, P.black); G.line(c, 7, 7, 10, 8, P.black);
    G.px(c, 3, 5, R.gold[1]); G.px(c, 11, 10, R.gold[1]);
  });
  sealFlash = G.makeSprite(15, 15, c => {
    G.ellipse(c, 7, 7, 7, 7, P.outline);
    G.ellipse(c, 7, 7, 6, 6, R.gold[5]);
    G.ellipse(c, 7, 7, 4, 4, P.white);
    G.line(c, 5, 4, 7, 7, R.red[3]); G.line(c, 7, 7, 6, 10, R.red[3]); G.line(c, 7, 7, 10, 8, R.red[3]);
  });
}
function drawCredibility(c, x, y, value, max, t, o) {
  o = o || {};
  if (!sealOk) buildSeals();
  max = max || 5;
  t = t || 0;
  const pw = max * 15 + 7;
  // ореховая планка
  G.rect(c, x, y, pw, 21, P.outline);
  woodFill(c, x + 1, y + 1, pw - 2, 19, 77, 2);
  G.rect(c, x + 1, y + 1, pw - 2, 1, R.wood[4]);
  G.rect(c, x + 1, y + 19, pw - 2, 1, R.wood[0]);
  for (let i = 0; i < max; i++) {
    const sx = x + 4 + i * 15, sy = y + 3;
    let spr = i < value ? sealOk : sealLost;
    let dy = 0;
    if (o.flashLost && i === value) {
      const ph = (t * 10) | 0;
      if (ph % 2 === 0) spr = sealFlash;
      dy = ph % 2;
    }
    shadowRect(c, sx + 2, sy + 13, 12, 2, 0.35);
    c.drawImage(spr, sx, sy + dy);
  }
}

/* ---------------------------------------------------------------------
   ПЕЧАТИ (штампы)
   --------------------------------------------------------------------- */
const stampBaseCache = {}, stampVarCache = {};
function lighter(col) {
  if (col === P.stamp) return R.red[4];
  if (col === P.stampBlue) return R.blue[4];
  for (const k in R) { const i = R[k].indexOf(col); if (i >= 0) return R[k][Math.min(R[k].length - 1, i + 1)]; }
  return col;
}
/* Базовый штамп: двойная рамка, текст, неровная мастика. size: 'small'|'big'|'shout' */
function stampBase(text, color, size) {
  const key = text + '|' + color + '|' + size;
  if (stampBaseCache[key]) return stampBaseCache[key];
  const font = size === 'small' ? 'big' : 'title';
  const zoom = size === 'shout' ? 2 : 1;
  const fo = { font };
  const lines = String(text).split('\n');
  const capTop = G.Font ? G.Font.capTop(fo) : 1, capH = G.Font ? G.Font.capH(fo) : 7;
  const tw = Math.max(...lines.map(l => M(l, fo)));
  const pad = size === 'small' ? 4 : 6, b = 7;
  const lgap = size === 'small' ? 3 : 5;
  const w = tw + 2 * (b + pad) + 2, h = lines.length * capH + (lines.length - 1) * lgap + 2 * (b + pad - 2);
  let base = G.makeSprite(w, h, c => {
    // двойная рамка со скруглением
    const ring = (x, y, ww, hh, th) => {
      G.rect(c, x + 1, y, ww - 2, th, color); G.rect(c, x + 1, y + hh - th, ww - 2, th, color);
      G.rect(c, x, y + 1, th, hh - 2, color); G.rect(c, x + ww - th, y + 1, th, hh - 2, color);
    };
    ring(0, 0, w, h, 2);
    ring(4, 4, w - 8, h - 8, 1);
    lines.forEach((l, i) => {
      T(c, l, (w >> 1), b + pad - 2 - capTop + i * (capH + lgap), color, { font, align: 'center' });
    });
  });
  base = zoomInt(base, zoom);
  // мастика: пропуски, светлые кляксы, крапины
  const bw = base.width, bh = base.height;
  const cx = base.getContext('2d');
  const id = cx.getImageData(0, 0, bw, bh);
  const d = id.data;
  const seed = strSeed(key);
  const light = lighter(color);
  const lr = parseInt(light.slice(1, 3), 16), lg = parseInt(light.slice(3, 5), 16), lb = parseInt(light.slice(5, 7), 16);
  const sc = size === 'shout' ? 9 : 6;
  for (let y = 0; y < bh; y++) for (let x = 0; x < bw; x++) {
    const k = (y * bw + x) * 4;
    if (!d[k + 3]) continue;
    const n = vnoise(x / sc, y / sc, seed);
    const f = hash2(x, y, seed + 5);
    // край штампа (правая и нижняя стороны) пропечатан хуже
    const edge = (x / bw) * 0.18 + (y / bh) * 0.1;
    if ((n < (size === 'small' ? 0.12 : 0.2) + edge && f < 0.7) || f < 0.03) d[k + 3] = 0;
    else if (n > 0.72 && f < 0.6) { d[k] = lr; d[k + 1] = lg; d[k + 2] = lb; }
  }
  cx.putImageData(id, 0, 0);
  // крапины мастики вокруг
  const rnd = G.rng(seed);
  cx.fillStyle = color;
  for (let i = 0; i < (size === 'small' ? 6 : 14); i++) {
    const ex = Math.floor(rnd() * bw), ey = rnd() < 0.5 ? Math.floor(rnd() * 3) : bh - 1 - Math.floor(rnd() * 3);
    if (rnd() < 0.5) cx.fillRect(ex, ey, 1, 1); else cx.fillRect(Math.floor(rnd() * 3), Math.floor(rnd() * bh), 1, 1);
  }
  stampBaseCache[key] = base;
  return base;
}
function stampVariant(text, color, size, angle, scale) {
  const key = text + '|' + color + '|' + size + '|' + angle + '|' + scale;
  let v = stampVarCache[key];
  if (!v) v = stampVarCache[key] = xform(stampBase(text, color, size), angle, scale);
  return v;
}
const APPEAR_STEPS = [2.2, 1.8, 1.5, 1.25, 1.1, 1];
function drawStamp(c, x, y, text, color, o) {
  o = o || {};
  color = color || P.stamp;
  const size = o.size || 'small';
  const angle = Math.round(o.angle == null ? -8 : o.angle);
  let scale = 1;
  if (o.t != null && o.t < 1) {
    if (o.t <= 0) return;
    const i = Math.min(APPEAR_STEPS.length - 1, Math.floor(o.t * APPEAR_STEPS.length));
    scale = APPEAR_STEPS[i];
  }
  const v = stampVariant(text, color, size, angle, scale);
  c.drawImage(v, Math.round(x - v.width / 2), Math.round(y - v.height / 2));
}

/* ---------------------------------------------------------------------
   БОЛЬШОЙ УДАР ПЕЧАТЬЮ
   --------------------------------------------------------------------- */
const SHOUTS = {
  objection: { text: 'ПРОТЕСТ!', color: P.stamp, angle: -7 },
  contradiction: { text: 'ПРОТИВОРЕЧИЕ', color: P.stamp, angle: 5 },
  sustained: { text: 'ПРОТЕСТ\nПРИНЯТ', color: P.stampBlue, angle: -5 },
  overruled: { text: 'ПРОТЕСТ\nОТКЛОНЁН', color: P.stampBlue, angle: 6 },
  evidence: { text: 'ПРИОБЩЕНО\nК ДЕЛУ', color: P.stampBlue, angle: -6 },
};
const SHOUT_STEPS = [2.6, 2.1, 1.7, 1.4, 1.2, 1.08, 1];
const splatCache = {};
function splats(kind, w, h) {
  if (splatCache[kind]) return splatCache[kind];
  const rnd = G.rng(strSeed(kind) + 3);
  const arr = [];
  for (let i = 0; i < 26; i++) {
    const side = rnd();
    let px, py;
    if (side < 0.5) { px = (rnd() - 0.5) * w * 1.05; py = (rnd() < 0.5 ? -1 : 1) * (h / 2 + 2 + rnd() * 14); }
    else { px = (rnd() < 0.5 ? -1 : 1) * (w / 2 + 2 + rnd() * 18); py = (rnd() - 0.5) * h * 1.1; }
    arr.push({ x: px, y: py, r: rnd() < 0.25 ? 2 : rnd() < 0.6 ? 1 : 0, streak: rnd() < 0.3, a: rnd() * 6.28 });
  }
  return splatCache[kind] = arr;
}
function paperSheet(c, cx, cy, ang, flip, w, h) {
  const ca = Math.cos(ang), sa = Math.sin(ang);
  const hw = w / 2 * flip, hh = h / 2;
  const pts = [[-hw, -hh], [hw, -hh], [hw, hh], [-hw, hh]].map(([x, y]) => [Math.round(cx + x * ca - y * sa), Math.round(cy + x * sa + y * ca)]);
  c.globalAlpha = 0.35;
  G.poly(c, pts.map(p => [p[0] + 2, p[1] + 3]), P.shadow);
  c.globalAlpha = 1;
  G.poly(c, pts, flip > 0 ? R.paper[4] : R.paper[2]);
  // строчки
  if (Math.abs(flip) > 0.4) {
    for (let k = -2; k <= 2; k++) {
      const yy = k * 3;
      const a = [cx + (-hw * 0.7) * ca - yy * sa, cy + (-hw * 0.7) * sa + yy * ca];
      const b = [cx + (hw * 0.7) * ca - yy * sa, cy + (hw * 0.7) * sa + yy * ca];
      G.line(c, a[0], a[1], b[0], b[1], R.blue[5]);
    }
  }
}
function drawShout(c, kind, t) {
  const S = SHOUTS[kind] || SHOUTS.objection;
  t = G.clamp(t, 0, 1);
  const cx = W >> 1, cy = (H >> 1) - 14;
  const fall = 0.16;
  // затемнение
  const dl = t < 0.1 ? Math.round(t / 0.1 * 7) : t > 0.88 ? Math.round((1 - t) / 0.12 * 7) : 7;
  dim(c, dl);
  const base = stampBase(S.text, S.color, 'shout');
  if (t < fall) {
    const k = t / fall;
    const i = Math.min(SHOUT_STEPS.length - 2, Math.floor(k * (SHOUT_STEPS.length - 1)));
    const sc = SHOUT_STEPS[i];
    // тень штампа (сжимается к моменту удара)
    const sw = Math.round(base.width * (0.6 + 0.4 * k)), sh = Math.round(base.height * (0.6 + 0.4 * k));
    shadowRect(c, cx - (sw >> 1) + Math.round((1 - k) * 24), cy - (sh >> 1) + Math.round((1 - k) * 30), sw, sh, 0.25 + 0.2 * k);
    const v = stampVariant(S.text, S.color, 'shout', S.angle, sc);
    c.drawImage(v, cx - (v.width >> 1), cy - (v.height >> 1) - Math.round((1 - k) * 10));
    return;
  }
  const after = (t - fall) / (1 - fall); // 0..1
  const v = stampVariant(S.text, S.color, 'shout', S.angle, 1);
  // разлетающиеся листы
  const rnd = G.rng(strSeed(kind) + 11);
  for (let i = 0; i < 6; i++) {
    const dir = (i / 6) * 6.28 + rnd() * 0.6;
    const sp = 120 + rnd() * 90;
    const tt = after * 0.9;
    const px = cx + Math.cos(dir) * sp * tt;
    const py = cy + Math.sin(dir) * sp * tt * 0.6 + 140 * tt * tt;
    const ang = dir + tt * (4 + rnd() * 5) * (i % 2 ? 1 : -1);
    const flip = Math.cos(tt * (10 + rnd() * 8) + i);
    paperSheet(c, px, py, ang, flip, 14, 18);
  }
  // брызги мастики
  const sp = splats(kind, v.width, v.height);
  const grow = Math.min(1, after * 6);
  c.fillStyle = S.color;
  for (const s of sp) {
    const px = Math.round(cx + s.x * (0.85 + 0.15 * grow)), py = Math.round(cy + s.y * (0.85 + 0.15 * grow));
    if (s.streak) {
      const l = 2 + s.r * 2;
      G.line(c, px, py, px + Math.round(Math.sign(s.x) * l * grow), py + Math.round(Math.sign(s.y) * l * 0.5 * grow), S.color);
    } else if (s.r === 0) G.px(c, px, py, S.color);
    else G.ellipse(c, px, py, s.r, s.r, S.color);
  }
  // удар: штамп слегка вдавлен в первые кадры
  const squash = after < 0.06 ? 1 : 0;
  if (t > 0.88) {
    // мастика «уходит» дизерингом
    const lvl = Math.round((t - 0.88) / 0.12 * 16);
    const tmp = fadeTmp(v.width, v.height);
    const tc = tmp.getContext('2d');
    tc.clearRect(0, 0, tmp.width, tmp.height);
    tc.drawImage(v, 0, 0);
    tc.globalCompositeOperation = 'destination-out';
    G.dither(tc, 0, 0, v.width, v.height, '#000000', lvl);
    tc.globalCompositeOperation = 'source-over';
    c.drawImage(tmp, 0, 0, v.width, v.height, cx - (v.width >> 1), cy - (v.height >> 1), v.width, v.height);
  } else {
    c.drawImage(v, cx - (v.width >> 1), cy - (v.height >> 1) + squash);
  }
  // вспышка-кольцо удара
  if (after < 0.08) {
    const rr = Math.round(10 + after / 0.08 * 40);
    G.frame(c, cx - (v.width >> 1) - rr / 4 | 0, cy - (v.height >> 1) - rr / 4 | 0, v.width + (rr >> 1), v.height + (rr >> 1), P.white);
  }
}
let fadeCanvas = null;
function fadeTmp(w, h) {
  if (!fadeCanvas || fadeCanvas.width < w || fadeCanvas.height < h) fadeCanvas = G.makeCanvas(Math.max(w, fadeCanvas ? fadeCanvas.width : 0), Math.max(h, fadeCanvas ? fadeCanvas.height : 0));
  return fadeCanvas;
}

/* ---------------------------------------------------------------------
   ИКОНКИ УЛИК (обёртка)
   --------------------------------------------------------------------- */
const iconCache = {}, icon2Cache = {};
function placeholderIcon(c, x, y, id) {
  // конверт из манильской бумаги со скрепкой
  G.rect(c, x + 5, y + 6, 22, 21, P.outline);
  G.rect(c, x + 6, y + 7, 20, 19, R.paper[3]);
  G.rect(c, x + 6, y + 7, 20, 1, R.paper[4]);
  G.rect(c, x + 6, y + 25, 20, 1, R.paper[1]);
  for (let i = 0; i < 4; i++) G.rect(c, x + 9, y + 12 + i * 3, 14 - (i === 3 ? 6 : 0), 1, R.blue[5]);
  G.rect(c, x + 20, y + 4, 2, 8, R.neutral[6]); G.rect(c, x + 22, y + 4, 1, 6, R.neutral[7]);
  G.px(c, x + 21, y + 3, R.neutral[7]);
  T(c, (id || '?')[0].toUpperCase(), x + 9, y + 15, R.wood[1]);
}
function iconCanvas(id) {
  if (iconCache[id]) return iconCache[id];
  const cv = G.makeSprite(32, 32, c => {
    if (G.Icons && G.Icons.draw) { try { G.Icons.draw(c, id, 0, 0); } catch (e) { placeholderIcon(c, 0, 0, id); } }
    else placeholderIcon(c, 0, 0, id);
  });
  if (G.Icons) iconCache[id] = cv;
  return cv;
}
function icon2x(id) {
  if (icon2Cache[id]) return icon2Cache[id];
  const z = zoomInt(iconCanvas(id), 2);
  if (G.Icons) icon2Cache[id] = z;
  return z;
}

/* ---------------------------------------------------------------------
   ПАПКА ДЕЛА (court record)
   --------------------------------------------------------------------- */
let folderBg = null;
const FX = 10, FY = 10, FW = 364, FH = 198;
function buildFolder() {
  return G.makeSprite(W, H, c => {
    // задняя обложка + вкладка
    shadowRect(c, FX + 4, FY + 6, FW, FH - 2, 0.45);
    // вкладка «Улики»
    const tab = (x, w, active, label) => {
      G.rect(c, x, FY - 1, w, 12, P.outline);
      G.rect(c, x + 1, FY, w - 2, 11, active ? R.paper[2] : R.paper[1]);
      G.rect(c, x + 1, FY, w - 2, 1, active ? R.paper[3] : R.paper[2]);
      T(c, label, x + (w >> 1), FY + 1, active ? R.wood[1] : R.wood[2], { align: 'center' });
    };
    // раскрытая папка
    G.rect(c, FX, FY + 8, FW, FH - 8, P.outline);
    G.rect(c, FX + 1, FY + 9, FW - 2, FH - 10, R.paper[2]);
    G.rect(c, FX + 1, FY + 9, FW - 2, 1, R.paper[3]);
    G.rect(c, FX + 1, FY + FH - 3, FW - 2, 2, R.paper[1]);
    // волокно картона
    const rnd = G.rng(99);
    for (let i = 0; i < 500; i++) G.px(c, FX + 2 + Math.floor(rnd() * (FW - 4)), FY + 10 + Math.floor(rnd() * (FH - 14)), rnd() < 0.5 ? R.paper[1] : R.paper[3]);
    // сгиб посередине
    const mx = FX + 178;
    G.rect(c, mx - 3, FY + 9, 1, FH - 11, R.paper[1]);
    G.dither(c, mx - 6, FY + 9, 3, FH - 11, R.paper[1], 6);
    G.rect(c, mx - 2, FY + 9, 2, FH - 11, R.paper[0]);
    G.rect(c, mx, FY + 9, 1, FH - 11, R.paper[3]);
    // латунный зажим-скоба (fastener) на правой половине
    // лист бумаги справа
    const sx = mx + 8, sy = FY + 16, sw = FX + FW - 8 - sx, sh = FH - 46;
    shadowRect(c, sx + 2, sy + 2, sw, sh, 0.35);
    G.rect(c, sx, sy, sw, sh, R.paper[4]);
    G.rect(c, sx, sy, sw, 1, P.white);
    G.frame(c, sx - 1, sy - 1, sw + 2, sh + 2, R.paper[0]);
    for (let yy = sy + 76; yy < sy + sh - 3; yy += 10) G.rect(c, sx + 2, yy, sw - 4, 1, R.blue[6]);
    G.rect(c, sx + 13, sy + 1, 1, sh - 2, R.red[5]);
    // скоба сверху
    G.rect(c, sx + (sw >> 1) - 12, sy - 4, 24, 5, P.outline);
    G.rect(c, sx + (sw >> 1) - 11, sy - 3, 22, 3, R.gold[3]);
    G.rect(c, sx + (sw >> 1) - 11, sy - 3, 22, 1, R.gold[5]);
    // заголовок слева
    T(c, 'МАТЕРИАЛЫ ДЕЛА', FX + 12, FY + 13, R.wood[1], { font: 'small' });
    G.rect(c, FX + 12, FY + 23, 150, 1, R.paper[1]);
    tab(FX + 14, 54, true, 'Улики');
    tab(FX + 70, 60, false, 'Профили');
  });
}
const REC = { cols: 4, rows: 3, cell: 38, gx: FX + 12, gy: FY + 28 };
function courtRecord(c, state, evidence, t) {
  if (!folderBg) folderBg = buildFolder();
  state = state || {};
  evidence = evidence || [];
  t = t || 0;
  const per = REC.cols * REC.rows;
  const n = evidence.length;
  if (state.sel == null || state.sel >= n) state.sel = Math.max(0, Math.min(n - 1, state.sel || 0));
  let result = { action: null, id: null };
  const mode = state.mode || 'view';
  // клавиатура
  if (n) {
    let s = state.sel;
    if (kp('ArrowRight', 'd', 'в')) s = Math.min(n - 1, s + 1);
    if (kp('ArrowLeft', 'a', 'ф')) s = Math.max(0, s - 1);
    if (kp('ArrowDown', 's', 'ы')) s = Math.min(n - 1, s + REC.cols);
    if (kp('ArrowUp', 'w', 'ц')) s = Math.max(0, s - REC.cols);
    if (s !== state.sel) { state.sel = s; sfx('select'); }
  }
  state.page = Math.floor((state.sel || 0) / per);
  dim(c, 9);
  c.drawImage(folderBg, 0, 0);
  // заголовок режима
  if (mode === 'present') {
    const blink = ((t * 2) | 0) % 2 === 0;
    const lbl = 'ПРЕДЪЯВИТЕ УЛИКУ';
    const lw = M(lbl) + 12, lx = FX + FW - lw - 4;
    G.rect(c, lx, FY - 3, lw, 13, P.outline);
    G.rect(c, lx + 1, FY - 2, lw - 2, 11, blink ? R.red[3] : R.red[2]);
    G.rect(c, lx + 1, FY - 2, lw - 2, 1, R.red[4]);
    T(c, lbl, lx + 6, FY, R.paper[4], { shadow: R.red[0], shadowX: 0, shadowY: 1 });
  }
  // сетка
  const first = state.page * per;
  for (let i = 0; i < per; i++) {
    const gi = first + i;
    const cx = REC.gx + (i % REC.cols) * REC.cell, cy = REC.gy + Math.floor(i / REC.cols) * REC.cell;
    const r = { x: cx, y: cy, w: 36, h: 36 };
    if (gi >= n) {
      // пустой кармашек
      for (let k = 0; k < 36; k += 2) { G.px(c, cx + k, cy, R.paper[1]); G.px(c, cx + k, cy + 35, R.paper[1]); G.px(c, cx, cy + k, R.paper[1]); G.px(c, cx + 35, cy + k, R.paper[1]); }
      continue;
    }
    const ev = evidence[gi];
    const sel = gi === state.sel;
    const hov = inp.inRect(r);
    const lift = sel ? 1 : 0;
    shadowRect(c, cx + 2, cy + 2, 36, 36, 0.35);
    G.rect(c, cx, cy - lift, 36, 36, P.outline);
    G.rect(c, cx + 1, cy + 1 - lift, 34, 34, sel ? P.white : R.paper[4]);
    G.rect(c, cx + 1, cy + 34 - lift, 34, 1, R.paper[2]);
    c.drawImage(iconCanvas(ev.icon || ev.id), cx + 2, cy + 2 - lift);
    if (sel) {
      const pulse = ((t * 4) | 0) % 2;
      G.frame(c, cx - 2, cy - 2 - lift, 40, 40, pulse ? R.gold[5] : R.gold[4]);
      G.frame(c, cx - 1, cy - 1 - lift, 38, 38, R.gold[2]);
    } else if (hov) G.frame(c, cx - 1, cy - 1, 38, 38, R.gold[3]);
    if (inp.clicked(r) && !sel) { state.sel = gi; sfx('select'); }
  }
  // страницы
  const pages = Math.max(1, Math.ceil(n / per));
  if (pages > 1) {
    const py = REC.gy + REC.rows * REC.cell + 2;
    T(c, (state.page + 1) + ' / ' + pages, REC.gx + 76, py + 2, R.wood[1], { align: 'center' });
    if (button(c, { x: REC.gx, y: py, w: 22, h: 13 }, '◄', { disabled: state.page === 0 })) state.sel = (state.page - 1) * per;
    if (button(c, { x: REC.gx + 130, y: py, w: 22, h: 13 }, '►', { disabled: state.page >= pages - 1 })) state.sel = Math.min(n - 1, (state.page + 1) * per);
  }
  // правая страница: выбранная улика
  const sx = FX + 186, sy = FY + 16;
  const ev = evidence[state.sel];
  if (ev) {
    // фото-подложка с уголками
    const ix = sx + 18, iy = sy + 6;
    shadowRect(c, ix + 2, iy + 2, 68, 68, 0.35);
    G.rect(c, ix - 1, iy - 1, 70, 70, R.paper[1]);
    G.rect(c, ix, iy, 68, 68, P.white);
    c.drawImage(icon2x(ev.icon || ev.id), ix + 2, iy + 2);
    for (const [ux, uy, dx, dy] of [[ix - 2, iy - 2, 1, 1], [ix + 63, iy - 2, -1, 1], [ix - 2, iy + 63, 1, -1], [ix + 63, iy + 63, -1, -1]]) {
      const ox = dx > 0 ? 0 : 6, oy = dy > 0 ? 0 : 6;
      for (let k = 0; k < 7; k++) G.rect(c, ux + (dx > 0 ? 0 : 7 - (7 - k)) + (dx > 0 ? 0 : 0), uy + (dy > 0 ? k : 6 - k), dx > 0 ? 7 - k : 7 - k, 1, R.neutral[2]);
      void ox; void oy;
    }
    // номер улики
    const nx = ix + 76;
    T(c, 'Улика', nx, iy + 2, R.wood[2]);
    T(c, '№ ' + (state.sel + 1), nx, iy + 12, P.inkDark, { font: 'big' });
    if (ev.doc) { G.rect(c, nx, iy + 30, 64, 11, R.paper[2]); T(c, '+ документ', nx + 2, iy + 31, R.wood[1]); }
    // название и описание
    const tw = 150;
    const nameLines = WRAP(ev.name || ev.id, tw, { font: 'big' });
    let yy = iy + 72;
    nameLines.slice(0, 2).forEach((l, i) => T(c, l, sx + 18, yy + i * 13, P.inkDark, { font: 'big' }));
    yy += Math.min(2, nameLines.length) * 13 + 1;
    const dl = WRAP(ev.desc || '', tw - 2, { font: 'small' });
    const room = Math.max(1, Math.floor((FY + FH - 32 - yy) / 10));
    dl.slice(0, room).forEach((l, i) => T(c, l, sx + 18, yy + i * 10, P.ink, { emph: P.stamp }));
  } else {
    T(c, 'Папка пуста', sx + 90, sy + 60, R.wood[2], { align: 'center' });
  }
  // кнопки
  const by = FY + FH - 22;
  let bx = FX + FW - 10;
  const btns = [];
  btns.push({ label: 'Закрыть', act: 'close', w: 58, kind: 'normal' });
  if (ev && ev.doc) btns.push({ label: 'Документ', act: 'doc', w: 64, kind: 'normal' });
  if (mode === 'present' && ev) btns.push({ label: 'Предъявить', act: 'present', w: 76, kind: 'danger' });
  for (const b of btns) {
    bx -= b.w;
    if (button(c, { x: bx, y: by, w: b.w, h: 16 }, b.label, { kind: b.kind, silent: true })) result = { action: b.act, id: ev ? ev.id : null };
    bx -= 5;
  }
  if (kp('Escape', 'Backspace', 'x', 'ч')) result = { action: 'close', id: ev ? ev.id : null };
  if (ev && kp('Enter', ' ')) {
    if (mode === 'present') result = { action: 'present', id: ev.id };
    else if (ev.doc) result = { action: 'doc', id: ev.id };
  }
  if (ev && ev.doc && kp('r', 'к')) result = { action: 'doc', id: ev.id };
  if (result.action) sfx(result.action === 'close' ? 'cancel' : result.action === 'present' ? 'evidence' : 'paper');
  return result;
}

/* ---------------------------------------------------------------------
   ДОКУМЕНТ
   --------------------------------------------------------------------- */
const docCache = new WeakMap();
let deskBg = null;
function buildDesk() {
  return G.makeSprite(W, H, c => {
    // ореховый стол из досок
    for (let i = 0; i < 8; i++) {
      woodFill(c, 0, i * 27, W, 27, 200 + i, i % 2 ? 2 : 3);
      G.rect(c, 0, i * 27, W, 1, R.wood[0]);
      G.rect(c, 0, i * 27 + 1, W, 1, R.wood[4]);
    }
    // свет настольной лампы слева сверху: ступени тона дизерингом
    for (let k = 0; k < 4; k++) {
      const rx = 170 - k * 34, ry = 110 - k * 22;
      const cvs = G.makeSprite(W, H, x => G.ellipse(x, 110, 70, rx, ry, '#fff'));
      const tmp = G.makeCanvas(W, H), tc = tmp.getContext('2d');
      G.dither(tc, 0, 0, W, H, R.wood[5], 2 + k);
      tc.globalCompositeOperation = 'destination-in';
      tc.drawImage(cvs, 0, 0);
      c.drawImage(tmp, 0, 0);
    }
    // виньетка
    for (let k = 0; k < 6; k++) {
      G.dither(c, 0, k * 3, W, 3, P.black, 12 - k * 2);
      G.dither(c, 0, H - 3 - k * 3, W, 3, P.black, 12 - k * 2);
      G.dither(c, k * 3, 0, 3, H, P.black, 12 - k * 2);
      G.dither(c, W - 3 - k * 3, 0, 3, H, P.black, 12 - k * 2);
    }
  });
}
function scribble(c, x, y, w, seed, col) {
  // скоропись: вытянутая циклоида с петлями, неровный нажим
  const rnd = G.rng(seed);
  const loops = 5 + (seed % 3);
  const pts = [];
  const n = 90;
  let amp = 5;
  for (let i = 0; i <= n; i++) {
    const k = i / n;
    const ph = k * loops * Math.PI * 2;
    if (i % 15 === 0) amp = 3 + rnd() * 4;
    const dx = x + k * w - Math.sin(ph) * 3.2;
    const dy = y - (1 - Math.cos(ph)) * amp * (k < 0.2 ? 1.5 : 1) + Math.sin(k * 7) * 2;
    pts.push([Math.round(dx), Math.round(dy)]);
  }
  for (let i = 1; i < pts.length; i++) {
    G.line(c, pts[i - 1][0], pts[i - 1][1], pts[i][0], pts[i][1], col);
    if (i < pts.length * 0.3) G.px(c, pts[i][0] + 1, pts[i][1], col);
  }
  G.line(c, x - 3, y + 3, x + w + 8, y - 1, col);
  G.line(c, x + w + 8, y - 1, x + w + 12, y - 4, col);
  G.px(c, x + w + 16, y - 5, col);
}
function buildDoc(doc) {
  const pw = 236, ph = 206, px = (W - pw) >> 1, py = 5;
  return G.makeSprite(W, H, c => {
    c.drawImage(deskBg || (deskBg = buildDesk()), 0, 0);
    // тень листа
    shadowRect(c, px + 4, py + 4, pw, ph, 0.45);
    // бумага
    G.rect(c, px, py, pw, ph, R.paper[4]);
    const rnd = G.rng(strSeed(doc.title || 'doc'));
    // старение к краям
    G.dither(c, px, py, pw, 4, R.paper[3], 8);
    G.dither(c, px, py + ph - 5, pw, 5, R.paper[3], 9);
    G.dither(c, px + pw - 4, py, 4, ph, R.paper[3], 7);
    G.dither(c, px, py, 3, ph, R.paper[3], 6);
    for (let i = 0; i < 160; i++) G.px(c, px + Math.floor(rnd() * pw), py + Math.floor(rnd() * ph), R.paper[3]);
    G.frame(c, px - 1, py - 1, pw + 2, ph + 2, R.paper[0]);
    // шапка
    const head = doc.header || 'ВЫСШИЙ СУД КАЛИФОРНИИ • ОКРУГ ЛОС-АНДЖЕЛЕС';
    const hl = WRAP(head, pw - 44).slice(0, 2);
    let hy = py + 5;
    hl.forEach(l => { T(c, l, px + (pw >> 1) + 8, hy, R.neutral[3], { align: 'center' }); hy += 9; });
    const tl = WRAP(doc.title || '', pw - 44, { font: 'big' }).slice(0, 2);
    hy += 2;
    tl.forEach(l => { T(c, l, px + (pw >> 1) + 8, hy, P.inkDark, { font: 'big', align: 'center' }); hy += 13; });
    G.rect(c, px + 30, hy + 2, pw - 44, 1, P.inkDark);
    G.rect(c, px + 30, hy + 4, pw - 44, 1, P.inkDark);
    // линовка и поля
    const top = hy + 17;
    for (let yy = top; yy < py + ph - 6; yy += 10) G.rect(c, px + 2, yy, pw - 4, 1, R.blue[6]);
    G.rect(c, px + 22, py, 1, ph, R.red[5]);
    G.rect(c, px + 24, py, 1, ph, R.red[5]);
    // дырокол
    for (const hy2 of [py + 30, py + 103, py + 176]) {
      G.ellipse(c, px + 9, hy2, 3, 3, R.paper[0]);
      G.ellipse(c, px + 9, hy2, 2, 2, R.wood[1]);
      G.px(c, px + 8, hy2 - 1, R.wood[0]);
    }
    // загнутый уголок
    const fc = 14;
    for (let k = 0; k < fc; k++) G.rect(c, px + pw - fc + k, py + k - 1, fc - k, 1, R.wood[2]);
    G.poly(c, [[px + pw - fc, py], [px + pw - fc, py + fc], [px + pw, py + fc]], R.paper[2]);
    G.line(c, px + pw - fc, py, px + pw, py + fc, R.paper[1]);
    G.rect(c, px + pw - fc, py, 1, fc, R.paper[1]);
    G.rect(c, px + pw - fc, py + fc, fc, 1, R.paper[0]);
    // текст
    let ly = top - 9;
    const maxLy = py + ph - (doc.signature ? 36 : 12);
    const lines = [];
    for (const raw of (doc.lines || [])) for (const l of WRAP(raw, pw - 40)) lines.push(l);
    for (const l of lines) {
      if (ly > maxLy) break;
      // «машинопись»: тёмные чернила, местами пропуск ленты
      T(c, l, px + 29, ly, P.inkDark, { emph: P.stamp });
      ly += 10;
    }
    // кофейное кольцо
    const kx = px + pw - 48 + Math.floor(rnd() * 16), ky = py + ph - 64 + Math.floor(rnd() * 20);
    for (let a = 0; a < 64; a++) {
      const ang = a / 64 * Math.PI * 2;
      if (Math.sin(ang * 3 + 1) < -0.6) continue;
      const rx = Math.round(kx + Math.cos(ang) * 15), ry = Math.round(ky + Math.sin(ang) * 13);
      G.px(c, rx, ry, R.paper[1]);
      if (Math.sin(ang * 2) > 0.2) G.px(c, rx + 1, ry, R.paper[2]);
    }
    // подпись
    if (doc.signature) {
      const sy = py + ph - 14;
      G.rect(c, px + pw - 110, sy, 96, 1, P.inkDark);
      T(c, doc.signature, px + pw - 62, sy + 2, R.neutral[4], { align: 'center' });
      scribble(c, px + pw - 104, sy - 6, 70, strSeed(doc.signature), P.ink);
      T(c, 'Подпись', px + 30, sy - 8, R.neutral[4]);
    }
    // печати
    for (const s of (doc.stamps || [])) {
      drawStamp(c, px + (s.x == null ? pw - 60 : s.x), py + (s.y == null ? ph - 60 : s.y), s.text, s.color || P.stamp, { angle: s.angle == null ? -10 : s.angle, size: s.size || 'small' });
    }
  });
}
function drawDocument(c, doc, t) {
  if (!doc) return;
  let cv = docCache.get(doc);
  if (!cv) { cv = buildDoc(doc); docCache.set(doc, cv); }
  c.drawImage(cv, 0, 0);
  t = t || 0;
  if (((t * 2) | 0) % 2 === 0) {
    G.rect(c, W - 70, H - 13, 66, 11, P.black);
    T(c, 'Esc / клик', W - 37, H - 12, R.paper[3], { align: 'center' });
  }
}

/* ---------------------------------------------------------------------
   ВЫБОР
   --------------------------------------------------------------------- */
const choiceState = { key: '', sel: 0 };
function choice(c, prompt, options, t) {
  const key = (prompt || '') + '|' + options.join('|');
  if (choiceState.key !== key) { choiceState.key = key; choiceState.sel = 0; }
  t = t || 0;
  // подсказка-вопрос на бумажной полосе
  let top = 8;
  if (prompt) {
    const pl = WRAP(prompt, 300);
    const ph = pl.length * 10 + 8;
    shadowRect(c, 44, top + 3, 300, ph, 0.4);
    G.rect(c, 41, top, 302, ph, P.outline);
    G.rect(c, 42, top + 1, 300, ph - 2, R.paper[4]);
    G.rect(c, 50, top + 1, 1, ph - 2, R.red[5]);
    pl.forEach((l, i) => T(c, l, 192, top + 5 + i * 10, P.inkDark, { align: 'center', emph: P.stamp }));
    top += ph + 6;
  }
  const n = options.length;
  const bh = 18, gap = 6;
  const total = n * bh + (n - 1) * gap;
  let y = Math.max(top, ((DLG_Y - total) >> 1) + 6);
  if (kp('ArrowDown', 's', 'ы')) { choiceState.sel = (choiceState.sel + 1) % n; sfx('select'); }
  if (kp('ArrowUp', 'w', 'ц')) { choiceState.sel = (choiceState.sel + n - 1) % n; sfx('select'); }
  let res = -1;
  for (let i = 0; i < n; i++) {
    const r = { x: 62, y: y + i * (bh + gap), w: 260, h: bh };
    if (inp.inRect(r) && (inp.mx !== choiceState.lmx || inp.my !== choiceState.lmy)) choiceState.sel = i;
    const selected = choiceState.sel === i;
    if (button(c, r, options[i], { kind: selected ? 'primary' : 'normal', selected, hotkey: String(i + 1) })) res = i;
    if (selected) {
      const bob = ((t * 4) | 0) % 2;
      c.drawImage(GAVEL, r.x - 18 - bob, r.y + 4);
    }
  }
  choiceState.lmx = inp.mx; choiceState.lmy = inp.my;
  if (res < 0 && kp('Enter', ' ')) { res = choiceState.sel; sfx('select'); }
  if (res >= 0) choiceState.key = '';
  return res;
}

/* ---------------------------------------------------------------------
   HUD ПЕРЕКРЁСТНОГО ДОПРОСА
   --------------------------------------------------------------------- */
let hudBanner = null;
function buildBanner() {
  return G.makeSprite(W, 18, c => {
    woodFill(c, 0, 0, W, 15, 501, 1);
    G.rect(c, 0, 0, W, 1, R.wood[3]);
    G.rect(c, 0, 14, W, 1, R.gold[4]);
    G.rect(c, 0, 15, W, 1, R.gold[2]);
    G.rect(c, 0, 16, W, 1, P.outline);
    c.globalAlpha = 0.35; G.rect(c, 0, 17, W, 1, P.shadow); c.globalAlpha = 1;
  });
}
function crossHUD(c, o) {
  o = o || {};
  if (!hudBanner) hudBanner = buildBanner();
  const t = o.t || 0;
  c.drawImage(hudBanner, 0, 0);
  // мигающая красная лампочка «идёт допрос»
  const on = ((t * 1.5) | 0) % 2 === 0;
  G.rect(c, 4, 4, 7, 7, P.outline);
  G.rect(c, 5, 5, 5, 5, on ? R.red[4] : R.red[1]);
  if (on) G.px(c, 6, 6, R.red[5]);
  const ttl = 'ПЕРЕКРЁСТНЫЙ ДОПРОС' + (o.title ? ' — ' + o.title : '');
  T(c, ttl, 15, 3, R.gold[5], { shadow: R.wood[0], shadowX: 0, shadowY: 1 });
  // счётчик показаний: пометки-зарубки
  const total = o.total || 1, idx = o.index || 0;
  const cnt = 'Показание ' + (idx + 1) + '/' + total;
  const cw = M(cnt);
  const px0 = W - 6 - total * 6;
  T(c, cnt, px0 - 5 - cw, 3, R.paper[3]);
  for (let i = 0; i < total; i++) {
    const x = px0 + i * 6;
    G.rect(c, x, 4, 5, 7, P.outline);
    G.rect(c, x + 1, 5, 3, 5, i === idx ? R.gold[5] : i < idx ? R.gold[2] : R.wood[2]);
  }
  // кнопки
  let act = null;
  const y = 125, h = 16;
  if (button(c, { x: 4, y, w: 24, h }, '◄', { disabled: idx <= 0, hotkey: 'ArrowLeft', silent: true })) act = 'prev';
  let x = W - 4 - 24;
  if (button(c, { x, y, w: 24, h }, '►', { hotkey: 'ArrowRight', silent: true })) act = 'next';
  x -= 54;
  if (button(c, { x, y, w: 50, h }, 'Папка', { hotkey: ['r', 'к', 'Tab'], hotkeyLabel: 'R' })) act = 'record';
  x -= 84;
  if (button(c, { x, y, w: 80, h }, 'Предъявить', { kind: 'danger', hotkey: ['e', 'у'], hotkeyLabel: 'E' })) act = 'present';
  x -= 74;
  if (button(c, { x, y, w: 70, h }, 'Уточнить', { kind: 'primary', hotkey: ['q', 'й'], hotkeyLabel: 'Q' })) act = 'press';
  if (act === 'prev' || act === 'next') sfx('select');
  return { action: act };
}

/* ---------------------------------------------------------------------
   ПЕРЕХОДЫ
   --------------------------------------------------------------------- */
function drawWipe(c, p, kind) {
  p = G.clamp(p || 0, 0, 1);
  if (p <= 0) return;
  if (kind === 'iris') {
    const cx = W >> 1, cy = H >> 1;
    const R0 = Math.ceil(Math.sqrt(cx * cx + cy * cy)) + 2;
    const r = Math.round((1 - p) * R0);
    c.fillStyle = P.black;
    if (r <= 0) { c.fillRect(0, 0, W, H); return; }
    for (let y = 0; y < H; y++) {
      const dy = y - cy;
      if (Math.abs(dy) >= r) { c.fillRect(0, y, W, 1); continue; }
      const dx = Math.round(Math.sqrt(r * r - dy * dy));
      c.fillRect(0, y, Math.max(0, cx - dx), 1);
      c.fillRect(cx + dx, y, W - cx - dx, 1);
    }
    // латунная кромка
    for (let y = Math.max(0, cy - r); y < Math.min(H, cy + r); y++) {
      const dy = y - cy, dx = Math.round(Math.sqrt(Math.max(0, r * r - dy * dy)));
      G.px(c, cx - dx, y, R.gold[2]); G.px(c, cx + dx - 1, y, R.gold[2]);
    }
    return;
  }
  // жалюзи: ореховые ламели
  const sh = 12;
  const f = Math.round(p * sh);
  for (let y = 0; y < H; y += sh) {
    if (f <= 0) break;
    G.rect(c, 0, y, W, f, R.wood[1]);
    G.rect(c, 0, y, W, 1, R.wood[3]);
    if (f > 2) G.rect(c, 0, y + f - 1, W, 1, R.wood[0]);
    if (f > 4) G.dither(c, 0, y + 1, W, f - 2, R.wood[2], 4);
  }
}

/* ---------------------------------------------------------------------
   ОБЩИЕ ЭЛЕМЕНТЫ МЕНЮ
   --------------------------------------------------------------------- */
function goTitle() { G.setScene(UI.TitleScene); }
function firstUnsolved() {
  const cs = G.Cases || [];
  const solved = (G.Save && G.Save.data.solved) || {};
  for (let i = 0; i < cs.length; i++) if (!solved[cs[i].id] && !solved[i]) return i;
  return 0;
}
function isSolved(i) {
  const cs = G.Cases || [];
  const s = (G.Save && G.Save.data.solved) || {};
  return !!(s[i] || (cs[i] && s[cs[i].id]));
}
function startCase(i) {
  if (G.startCase) G.startCase(i);
}
/* Заглушка-фон: закат над Лос-Анджелесом */
let skyBg = null;
function buildSky() {
  return G.makeSprite(W, H, c => {
    const bands = [R.blue[3], R.blue[4], R.blue[5], P.sky, P.sky2, R.gold[5], R.red[5]];
    const bh = 22;
    bands.forEach((col, i) => {
      G.rect(c, 0, i * bh, W, bh, col);
      if (i > 0) G.dither(c, 0, i * bh, W, 6, bands[i - 1], 8);
    });
    G.rect(c, 0, bands.length * bh, W, H, R.red[5]);
    // солнце
    G.ellipse(c, 300, 148, 16, 16, R.gold[5]);
    G.ellipse(c, 300, 148, 12, 12, P.glow);
    // облака
    const cloud = (x, y, w) => { G.rect(c, x, y, w, 3, P.sky2); G.rect(c, x + 4, y - 2, w - 10, 2, P.white); G.rect(c, x + 2, y + 3, w - 4, 1, R.gold[5]); };
    cloud(30, 40, 50); cloud(220, 28, 70); cloud(120, 66, 40);
    // холмы
    G.poly(c, [[0, 160], [60, 140], [130, 152], [200, 136], [290, 150], [384, 138], [384, 216], [0, 216]], R.purple[3]);
    G.poly(c, [[0, 172], [90, 160], [170, 170], [260, 158], [384, 166], [384, 216], [0, 216]], R.purple[2]);
    // здание суда
    const bx = 112, by = 112, bw = 160;
    G.rect(c, bx, by, bw, 104, R.stone[3]);
    G.rect(c, bx, by, bw, 4, R.stone[5]);
    G.rect(c, bx - 6, by - 8, bw + 12, 8, R.stone[4]);
    G.rect(c, bx - 6, by - 9, bw + 12, 1, R.stone[5]);
    for (let i = 0; i < 9; i++) {
      const cx = bx + 6 + i * 19;
      G.rect(c, cx, by + 6, 6, 80, R.stone[4]);
      G.rect(c, cx, by + 6, 2, 80, R.stone[5]);
      G.rect(c, cx + 5, by + 6, 1, 80, R.stone[2]);
    }
    for (let i = 0; i < 8; i++) for (let j = 0; j < 3; j++) G.rect(c, bx + 14 + i * 19, by + 12 + j * 26, 8, 16, R.blue[1]);
    G.rect(c, bx - 10, by + 86, bw + 20, 4, R.stone[4]);
    G.rect(c, bx - 16, by + 90, bw + 32, 4, R.stone[3]);
    G.rect(c, 0, 200, W, 16, R.stone[1]);
    // пальмы
    const palm = (x, y, hgt) => {
      for (let k = 0; k < hgt; k++) G.rect(c, x + Math.round(Math.sin(k / hgt * 2) * 3), y - k, 2, 1, k % 3 ? R.wood[2] : R.wood[1]);
      const tx = x + Math.round(Math.sin(2) * 3), ty = y - hgt;
      for (const [dx, dy] of [[-12, 4], [12, 5], [-9, -3], [10, -3], [-4, 7], [5, 8]]) G.line(c, tx, ty, tx + dx, ty + dy, R.green[1]);
      G.ellipse(c, tx + 1, ty, 2, 2, R.green[2]);
    };
    palm(40, 210, 70); palm(70, 212, 54); palm(330, 210, 76); palm(356, 212, 50);
  });
}
/* Логотип: Scale2x дважды (сглаженные контуры), латунь с деревянной экструзией */
let logoCv = null;
function buildLogo(text) {
  const F = G.Font;
  const glyphs = [];
  let tw = 0;
  for (const ch of text) {
    if (ch === ' ') { glyphs.push(null); tw += 12; continue; }
    const m0 = F.mask(ch);
    if (!m0) continue;
    const g = F.scale2x(F.scale2x(m0));
    glyphs.push(g); tw += g.w + 4;
  }
  tw -= 4;
  const D = 5; // глубина экструзии
  const gw = tw + 4, gh = 40;
  // маска лица
  const mask = new Uint8Array(gw * gh);
  let x = 0;
  for (const g of glyphs) {
    if (!g) { x += 12; continue; }
    for (let j = 0; j < g.h; j++) for (let i = 0; i < g.w; i++) {
      if (!g.m[j * g.w + i]) continue;
      // жирность: +1 вправо
      for (let b = 0; b < 2; b++) { const X = x + i + b, Y = j; if (X < gw && Y < gh) mask[Y * gw + X] = 1; }
    }
    x += g.w + 4;
  }
  const at = (X, Y) => X >= 0 && Y >= 0 && X < gw && Y < gh && mask[Y * gw + X];
  const out = G.makeCanvas(gw + D + 4, gh + D + 4);
  const c = out.getContext('2d');
  const ox = 2, oy = 2;
  // контур + экструзия
  for (let d = D; d >= 1; d--) {
    for (let Y = 0; Y < gh; Y++) for (let X = 0; X < gw; X++) if (at(X, Y)) G.px(c, ox + X + d, oy + Y + d, d === D ? P.outline : R.wood[d > 3 ? 0 : d > 1 ? 1 : 2]);
  }
  // внешний контур
  for (let Y = -1; Y <= gh; Y++) for (let X = -1; X <= gw; X++) {
    if (at(X, Y)) continue;
    if (at(X - 1, Y) || at(X + 1, Y) || at(X, Y - 1) || at(X, Y + 1)) {
      // на экструзии не рисуем поверх, только вокруг лица
      G.px(c, ox + X, oy + Y, P.outline);
    }
  }
  // лицо: латунь с полосами света сверху
  for (let Y = 0; Y < gh; Y++) for (let X = 0; X < gw; X++) {
    if (!at(X, Y)) continue;
    const yy = Y - 8; // верх заглавной в маске (строки 0..7 — диакритика)
    let col = yy < 6 ? R.gold[5] : yy < 13 ? R.gold[4] : yy < 22 ? R.gold[3] : R.gold[2];
    if (yy >= 11 && yy < 13 && G.bayer(X, Y) < 8) col = R.gold[3];
    if (yy >= 20 && yy < 22 && G.bayer(X, Y) < 8) col = R.gold[2];
    // фаска: верхняя/левая кромка светлее, нижняя/правая темнее
    if (!at(X, Y - 1) || !at(X - 1, Y)) col = yy < 13 ? R.gold[5] : R.gold[4];
    if (!at(X, Y + 1) || !at(X + 1, Y)) col = R.gold[1];
    G.px(c, ox + X, oy + Y, col);
  }
  return { cv: out, mask, gw, gh, ox, oy };
}
function menuBackground(c) {
  if (!deskBg) deskBg = buildDesk();
  c.drawImage(deskBg, 0, 0);
}
function sceneHeader(c, text) {
  T(c, text, W >> 1, 8, R.gold[5], { font: 'title', align: 'center', shadow: R.wood[0], shadowX: 1, shadowY: 2 });
  G.rect(c, (W >> 1) - 70, 30, 140, 1, R.gold[3]);
  G.rect(c, (W >> 1) - 70, 31, 140, 1, R.wood[0]);
  G.rect(c, (W >> 1) - 2, 29, 5, 4, R.gold[4]);
}

/* ---------------------------------------------------------------------
   ТИТУЛЬНЫЙ ЭКРАН
   --------------------------------------------------------------------- */
const TITLE_ITEMS = ['Новая игра', 'Продолжить', 'Выбор дела', 'Настройки', 'Об игре'];
const TitleScene = {
  t: 0, sel: 0, lmx: -1, lmy: -1,
  enter() {
    this.t = 0; this.sel = 0;
    if (!logoCv) logoCv = buildLogo('СЛОВО ЗАЩИТЫ');
    if (G.Audio && G.Audio.music) G.Audio.music('menu');
  },
  exit() {},
  activate(i) {
    sfx('select');
    if (i === 0) startCase(0);
    else if (i === 1) {
      const pr = G.Save && G.Save.data.progress;
      let idx = pr && pr.case != null ? pr.case : firstUnsolved();
      if (typeof idx === 'string' && G.Cases) idx = Math.max(0, G.Cases.findIndex(cs => cs.id === idx));
      startCase(idx);
    } else if (i === 2) G.setScene(UI.CaseSelectScene);
    else if (i === 3) G.setScene(UI.SettingsScene);
    else if (i === 4) G.setScene(UI.CreditsScene);
  },
  rects() {
    return TITLE_ITEMS.map((_, i) => ({ x: 142, y: 128 + i * 15, w: 100, h: 14 }));
  },
  update(dt) {
    this.t += dt;
    const n = TITLE_ITEMS.length;
    if (kp('ArrowDown', 's', 'ы')) { this.sel = (this.sel + 1) % n; sfx('select'); }
    if (kp('ArrowUp', 'w', 'ц')) { this.sel = (this.sel + n - 1) % n; sfx('select'); }
    const rs = this.rects();
    const moved = inp.mx !== this.lmx || inp.my !== this.lmy;
    this.lmx = inp.mx; this.lmy = inp.my;
    rs.forEach((r, i) => {
      if (inp.inRect(r) && moved && this.sel !== i) this.sel = i;
      if (inp.clicked(r)) this.activate(i);
    });
    if (kp('Enter', ' ')) this.activate(this.sel);
  },
  draw(c) {
    const t = this.t;
    if (G.Env && G.Env.drawExterior) G.Env.drawExterior(c, t);
    else c.drawImage(skyBg || (skyBg = buildSky()), 0, 0);
    if (!logoCv) logoCv = buildLogo('СЛОВО ЗАЩИТЫ');
    // логотип с лёгким «дыханием» и бликом
    const L = logoCv;
    const lx = (W - L.cv.width) >> 1, ly = 6 + (((t * 1.2) | 0) % 8 === 0 ? 0 : 0);
    // плашка под логотипом
    c.globalAlpha = 0.35; G.rect(c, 0, ly + 4, W, 52, P.shadow); c.globalAlpha = 1;
    c.drawImage(L.cv, lx, ly);
    // блик проходит по латуни каждые 5 с
    const ph = (t % 5) / 5;
    if (ph < 0.35) {
      const sx = Math.round(-30 + ph / 0.35 * (L.gw + 60));
      for (let Y = 0; Y < L.gh; Y++) for (let k = 0; k < 4; k++) {
        const X = sx + k - Math.floor(Y / 2);
        if (X >= 0 && X < L.gw && L.mask[Y * L.gw + X]) G.px(c, lx + L.ox + X, ly + L.oy + Y, k === 0 || k === 3 ? R.gold[5] : P.white);
      }
    }
    // подзаголовок на ленте
    const sub = 'Высший суд Калифорнии • Округ Лос-Анджелес';
    const sw = M(sub) + 24;
    const sx = (W - sw) >> 1, sy = ly + L.cv.height + 2;
    G.rect(c, sx - 1, sy - 1, sw + 2, 14, P.outline);
    G.rect(c, sx, sy, sw, 12, R.red[2]);
    G.rect(c, sx, sy, sw, 1, R.red[3]);
    G.rect(c, sx, sy + 11, sw, 1, R.red[1]);
    // хвосты ленты
    for (const [tx, dir] of [[sx - 9, 1], [sx + sw + 1, -1]]) {
      G.rect(c, tx, sy + 3, 8, 12, P.outline);
      G.rect(c, tx + 1, sy + 4, 6, 10, R.red[1]);
      for (let k = 0; k < 3; k++) G.rect(c, dir > 0 ? tx + k : tx + 7 - k, sy + 7 + k - 1, 1, 6 - 2 * k + 2, P.outline);
    }
    T(c, sub, W >> 1, sy + 2, R.paper[4], { align: 'center', shadow: R.red[0], shadowX: 0, shadowY: 1 });
    // меню: ореховая доска с латунной рамкой
    const mx = 128, my = 122, mw = 128, mh = 84;
    shadowRect(c, mx + 3, my + 4, mw, mh, 0.45);
    woodFill(c, mx, my, mw, mh, 404, 2);
    brassFrame(c, mx, my, mw, mh);
    rivet(c, mx + 4, my + 4); rivet(c, mx + mw - 8, my + 4); rivet(c, mx + 4, my + mh - 8); rivet(c, mx + mw - 8, my + mh - 8);
    const hasProg = !!(G.Save && (G.Save.data.progress || Object.keys(G.Save.data.solved || {}).length));
    TITLE_ITEMS.forEach((it, i) => {
      const y = 128 + i * 15;
      const sel = i === this.sel;
      if (sel) {
        G.rect(c, mx + 6, y, mw - 12, 13, R.wood[1]);
        G.rect(c, mx + 6, y + 12, mw - 12, 1, R.wood[3]);
      }
      const col = sel ? R.gold[5] : (i === 1 && !hasProg) ? R.wood[5] : R.paper[3];
      T(c, it, W >> 1, y + 2, col, { align: 'center', shadow: R.wood[0], shadowX: 0, shadowY: 1 });
      if (sel) {
        // молоток стучит
        const tap = (t * 3) % 1 < 0.2 ? 2 : 0;
        const w2 = M(it) >> 1;
        c.drawImage(GAVEL, (W >> 1) - w2 - 19 + tap, y + 1);
        if (tap) { G.px(c, (W >> 1) - w2 - 3, y + 2, R.gold[5]); G.px(c, (W >> 1) - w2 - 3, y + 10, R.gold[5]); }
      }
    });
    // версия
    T(c, 'v1.0', W - 4, H - 11, R.paper[2], { align: 'right', shadow: P.black, shadowX: 0, shadowY: 1 });
  },
};

/* ---------------------------------------------------------------------
   ВЫБОР ДЕЛА
   --------------------------------------------------------------------- */
const FEM = { whitfield: 1, park: 1, bell: 1, prosecutor: 1, clerk: 1, foreperson: 1 };
const PLACEHOLDER_CASES = [
  { id: 'violin', title: 'Скрипка Гварнери', docket: 'BA-512874', caption: 'Народ штата Калифорния против Сэмюэла Ломакса', charges: [{ code: 'Cal. Penal Code § 487(a)' }], defendant: 'lomax' },
  { id: 'bakery', title: 'Горький хлеб', docket: 'BA-520113', caption: 'Народ против Анны Уитфилд', charges: [{ code: 'Cal. Penal Code § 451' }], defendant: 'whitfield' },
  { id: 'gallery', title: 'Подделка века', docket: 'BA-531902', caption: 'Народ против Лизы Пак', charges: [{ code: 'Cal. Penal Code § 470' }], defendant: 'park' },
  { id: 'kitchen', title: 'Последний ужин', docket: 'BA-544870', caption: 'Народ против Маркуса Дойла', charges: [{ code: 'Cal. Penal Code § 187(a)' }], defendant: 'doyle' },
];
const folderCache = {};
function buildCaseFolder(cs, i, solved, locked) {
  const key = i + '|' + solved + '|' + locked + '|' + cs.title;
  if (folderCache[key]) return folderCache[key];
  const fw = 86, fh = 126;
  const tabX = 6 + (i % 3) * 20;
  const cv = G.makeSprite(fw + 4, fh + 14, c => {
    const oy = 10;
    // вкладка
    G.rect(c, tabX, 0, 46, 12, P.outline);
    G.rect(c, tabX + 1, 1, 44, 11, R.paper[2]);
    G.rect(c, tabX + 1, 1, 44, 1, R.paper[3]);
    T(c, cs.docket || '', tabX + 23, 2, P.inkDark, { align: 'center' });
    // папка
    G.rect(c, 0, oy, fw, fh, P.outline);
    G.rect(c, 1, oy + 1, fw - 2, fh - 2, R.paper[2]);
    G.rect(c, 1, oy + 1, fw - 2, 1, R.paper[3]);
    G.rect(c, 1, oy + fh - 3, fw - 2, 2, R.paper[1]);
    G.rect(c, fw - 3, oy + 2, 2, fh - 4, R.paper[1]);
    const rnd = G.rng(31 + i);
    for (let k = 0; k < 120; k++) G.px(c, 2 + Math.floor(rnd() * (fw - 5)), oy + 3 + Math.floor(rnd() * (fh - 6)), rnd() < 0.5 ? R.paper[1] : R.paper[3]);
    // наклейка
    G.rect(c, 6, oy + 8, fw - 12, 42, R.paper[4]);
    G.frame(c, 6, oy + 8, fw - 12, 42, R.paper[1]);
    G.rect(c, 6, oy + 8, fw - 12, 9, R.red[2]);
    T(c, 'ДЕЛО № ' + (i + 1), fw >> 1, oy + 8, R.paper[4], { align: 'center' });
    const tl = WRAP(cs.title || '', fw - 18);
    tl.slice(0, 3).forEach((l, k) => T(c, l, fw >> 1, oy + 20 + k * 10, P.inkDark, { align: 'center' }));
    // подпись-подзаголовок
    const cap = WRAP(cs.caption || '', fw - 12);
    cap.slice(0, 4).forEach((l, k) => T(c, l, 6, oy + 54 + k * 10, R.wood[1]));
    // статья
    const code = (cs.charges && cs.charges[0] && cs.charges[0].code) || '';
    const cl = WRAP(code.replace('Cal. Penal Code', 'PC'), fw - 12);
    G.rect(c, 6, oy + fh - 26, fw - 12, 1, R.paper[1]);
    cl.slice(0, 2).forEach((l, k) => T(c, l, 6, oy + fh - 23 + k * 10, P.stamp));
    // скрепка
    G.rect(c, fw - 18, oy - 3, 3, 14, R.neutral[6]); G.rect(c, fw - 17, oy - 2, 1, 12, R.neutral[8]);
    G.rect(c, fw - 20, oy + 9, 7, 1, R.neutral[5]);
    if (solved && !locked) {
      const fem = FEM[cs.defendant];
      drawStamp(c, fw >> 1, oy + 82, fem ? 'ОПРАВДАНА' : 'ОПРАВДАН', P.stamp, { angle: -14, size: 'small' });
    }
    if (locked) {
      G.dither(c, 0, 0, fw + 4, fh + 14, R.neutral[3], 11);
      c.globalCompositeOperation = 'destination-over';
      c.globalCompositeOperation = 'source-over';
      const lx = (fw >> 1) - 9, ly = oy + 52;
      G.rect(c, lx - 4, ly - 3, 26, 28, P.outline);
      G.rect(c, lx - 3, ly - 2, 24, 26, R.neutral[2]);
      c.drawImage(zoomInt(PADLOCK, 2), lx, ly);
    }
  });
  folderCache[key] = cv;
  return cv;
}
const CaseSelectScene = {
  t: 0, sel: 0, lmx: -1, lmy: -1,
  cases() { return (G.Cases && G.Cases.length ? G.Cases : PLACEHOLDER_CASES).slice(0, 4); },
  locked(i) { return i > 0 && !isSolved(i - 1); },
  enter() { this.t = 0; this.sel = Math.min(firstUnsolved(), this.cases().length - 1); },
  exit() {},
  rect(i) { return { x: 8 + i * 94, y: 42, w: 90, h: 140 }; },
  pick(i) {
    if (this.locked(i)) { sfx('cancel'); G.fx && G.fx.shake && G.fx.shake(2, 0.2); return; }
    sfx('select'); startCase(i);
  },
  update(dt) {
    this.t += dt;
    const n = this.cases().length;
    if (kp('ArrowRight', 'd', 'в')) { this.sel = (this.sel + 1) % n; sfx('select'); }
    if (kp('ArrowLeft', 'a', 'ф')) { this.sel = (this.sel + n - 1) % n; sfx('select'); }
    const moved = inp.mx !== this.lmx || inp.my !== this.lmy;
    this.lmx = inp.mx; this.lmy = inp.my;
    for (let i = 0; i < n; i++) {
      const r = this.rect(i);
      if (moved && inp.inRect(r)) this.sel = i;
      if (inp.clicked(r)) this.pick(i);
    }
    if (kp('Enter', ' ')) this.pick(this.sel);
    if (kp('Escape', 'Backspace')) { sfx('cancel'); goTitle(); }
  },
  draw(c) {
    menuBackground(c);
    sceneHeader(c, 'ВЫБОР ДЕЛА');
    const cs = this.cases();
    cs.forEach((k, i) => {
      const solved = isSolved(i), locked = this.locked(i);
      const cv = buildCaseFolder(k, i, solved, locked);
      const r = this.rect(i);
      const sel = i === this.sel;
      const lift = sel ? 4 + (((this.t * 2) | 0) % 2) : 0;
      shadowRect(c, r.x + 4, r.y + 14 + 2, 86, 126, sel ? 0.5 : 0.35);
      c.drawImage(cv, r.x, r.y - lift);
      if (sel) {
        G.frame(c, r.x - 2, r.y + 8 - lift, 90, 130, R.gold[4]);
        G.frame(c, r.x - 3, r.y + 7 - lift, 92, 132, P.outline);
      }
    });
    const k = cs[this.sel];
    const info = this.locked(this.sel) ? 'Дело закрыто: сначала завершите предыдущее' : (isSolved(this.sel) ? 'Пройдено. ' : '') + (k ? k.title : '');
    G.rect(c, 0, H - 22, W, 22, R.wood[0]);
    G.rect(c, 0, H - 22, W, 1, R.gold[2]);
    T(c, info, W >> 1, H - 16, R.paper[3], { align: 'center' });
    if (button(c, { x: 4, y: H - 19, w: 50, h: 16 }, 'Назад', { silent: true, hotkey: null })) { sfx('cancel'); goTitle(); }
  },
};

/* ---------------------------------------------------------------------
   НАСТРОЙКИ: жёлтый блокнот, латунные ползунки
   --------------------------------------------------------------------- */
const SETTINGS = [
  { key: 'music', label: 'Музыка', min: 0, max: 1, step: 0.1, fmt: v => Math.round(v * 100) + '%' },
  { key: 'sfx', label: 'Звуки', min: 0, max: 1, step: 0.1, fmt: v => Math.round(v * 100) + '%' },
  { key: 'textSpeed', label: 'Скорость текста', min: 0.5, max: 3, step: 0.25, fmt: v => '×' + (Math.round(v * 100) / 100) },
];
let padBg = null;
function buildPad() {
  return G.makeSprite(W, H, c => {
    c.drawImage(deskBg || (deskBg = buildDesk()), 0, 0);
    const px = 62, py = 26, pw = 260, ph = 184;
    shadowRect(c, px + 5, py + 5, pw, ph, 0.45);
    G.rect(c, px, py, pw, ph, R.gold[5]);
    G.frame(c, px - 1, py - 1, pw + 2, ph + 2, R.gold[1]);
    for (let y = py + 28; y < py + ph - 4; y += 12) G.rect(c, px + 1, y, pw - 2, 1, R.blue[5]);
    G.rect(c, px + 26, py, 1, ph, R.red[4]); G.rect(c, px + 28, py, 1, ph, R.red[4]);
    // склейка сверху
    G.rect(c, px - 2, py - 8, pw + 4, 10, P.outline);
    G.rect(c, px - 1, py - 7, pw + 2, 8, R.red[2]);
    G.rect(c, px - 1, py - 7, pw + 2, 1, R.red[3]);
    // ручка рядом
    G.line(c, 344, 60, 360, 170, P.outline); G.line(c, 345, 60, 361, 170, R.blue[3]); G.line(c, 346, 60, 362, 170, R.blue[4]);
    G.line(c, 347, 60, 363, 170, P.outline);
    G.rect(c, 344, 56, 4, 6, R.gold[4]);
    T(c, 'НАСТРОЙКИ', px + pw / 2 + 12, py + 6, P.inkDark, { font: 'big', align: 'center' });
  });
}
const SettingsScene = {
  t: 0, sel: 0, drag: -1, lmx: -1, lmy: -1,
  st() { const s = G.Save.data.settings = G.Save.data.settings || {}; for (const d of SETTINGS) if (s[d.key] == null) s[d.key] = d.key === 'textSpeed' ? 1 : 0.7; return s; },
  enter() { this.t = 0; this.sel = 0; this.drag = -1; },
  exit() { G.Save.save(); },
  set(i, v) {
    const d = SETTINGS[i]; const s = this.st();
    v = G.clamp(Math.round((v - d.min) / d.step) * d.step + d.min, d.min, d.max);
    v = Math.round(v * 100) / 100;
    if (s[d.key] !== v) {
      s[d.key] = v; G.Save.save();
      if (G.Audio && G.Audio.applySettings) G.Audio.applySettings(s);
      if (d.key === 'sfx') sfx('select');
    }
  },
  track(i) { return { x: 170, y: 64 + i * 36, w: 120, h: 12 }; },
  update(dt) {
    this.t += dt;
    const n = SETTINGS.length + 1;
    if (kp('ArrowDown', 's', 'ы')) { this.sel = (this.sel + 1) % n; sfx('select'); }
    if (kp('ArrowUp', 'w', 'ц')) { this.sel = (this.sel + n - 1) % n; sfx('select'); }
    if (this.sel < SETTINGS.length) {
      const d = SETTINGS[this.sel], s = this.st();
      if (kp('ArrowRight', 'd', 'в')) this.set(this.sel, s[d.key] + d.step);
      if (kp('ArrowLeft', 'a', 'ф')) this.set(this.sel, s[d.key] - d.step);
    } else if (kp('Enter', ' ')) { sfx('cancel'); goTitle(); return; }
    // мышь / касание
    for (let i = 0; i < SETTINGS.length; i++) {
      const r = this.track(i);
      const hit = { x: r.x - 6, y: r.y - 4, w: r.w + 12, h: r.h + 8 };
      if (inp.pressed && inp.inRect(hit)) { this.drag = i; this.sel = i; }
    }
    if (this.drag >= 0) {
      const r = this.track(this.drag), d = SETTINGS[this.drag];
      const k = G.clamp((inp.mx - r.x) / r.w, 0, 1);
      this.set(this.drag, d.min + k * (d.max - d.min));
      if (!inp.down) this.drag = -1;
    }
    if (kp('Escape', 'Backspace')) { sfx('cancel'); goTitle(); }
  },
  draw(c) {
    if (!padBg) padBg = buildPad();
    c.drawImage(padBg, 0, 0);
    const s = this.st();
    SETTINGS.forEach((d, i) => {
      const r = this.track(i);
      const sel = this.sel === i;
      T(c, d.label, 98, r.y + 2, sel ? P.stamp : P.inkDark);
      if (sel) c.drawImage(GAVEL, 80, r.y + 1);
      // шкала: чернильная линия с делениями
      G.rect(c, r.x, r.y + 6, r.w, 1, P.inkDark);
      G.rect(c, r.x, r.y + 7, r.w, 1, P.ink);
      const steps = Math.round((d.max - d.min) / d.step);
      for (let k = 0; k <= steps; k++) {
        const tx = r.x + Math.round(k / steps * (r.w - 1));
        G.rect(c, tx, r.y + (k % 2 ? 4 : 3), 1, k % 2 ? 2 : 3, P.inkDark);
      }
      const v = s[d.key];
      const kx = r.x + Math.round((v - d.min) / (d.max - d.min) * (r.w - 1));
      // заполненная часть — красной ручкой
      G.rect(c, r.x, r.y + 8, kx - r.x, 1, P.stamp);
      // латунный бегунок
      G.rect(c, kx - 4, r.y - 1, 9, 14, P.outline);
      G.rect(c, kx - 3, r.y, 7, 12, R.gold[3]);
      G.rect(c, kx - 3, r.y, 7, 1, R.gold[5]);
      G.rect(c, kx - 3, r.y, 1, 12, R.gold[4]);
      G.rect(c, kx - 3, r.y + 11, 7, 1, R.gold[1]);
      G.rect(c, kx, r.y + 3, 1, 6, R.gold[1]);
      T(c, d.fmt(v), r.x + r.w + 10, r.y + 2, P.ink);
    });
    // предпросмотр скорости текста
    const demo = 'Протест принят. Продолжайте, советник.';
    const sp = 30 * (s.textSpeed || 1);
    const n = Math.floor((this.t * sp) % (demo.length + 20));
    T(c, demo, 98, 168, P.ink, { maxChars: n });
    if (button(c, { x: 98, y: 186, w: 70, h: 16 }, 'Назад', { selected: this.sel === SETTINGS.length, silent: true })) { sfx('cancel'); goTitle(); }
  },
};

/* ---------------------------------------------------------------------
   ОБ ИГРЕ
   --------------------------------------------------------------------- */
const CREDITS = [
  ['big', 'СЛОВО ЗАЩИТЫ'],
  ['small', 'Пиксельная судебная драма в четырёх делах'],
  ['gap'],
  ['small', 'Вы — Дэниел Рид, адвокат защиты.'],
  ['small', 'Высший суд Калифорнии, округ Лос-Анджелес.'],
  ['gap'],
  ['small', 'Код, пиксель-арт, шрифты, музыка и сценарий'],
  ['small', 'созданы с нуля командой агентов Claude Code.'],
  ['gap'],
  ['small', 'Все персонажи и события вымышлены.'],
  ['small', 'Статьи законов приводятся в пересказе;'],
  ['small', 'игра не является юридической консультацией.'],
];
const CreditsScene = {
  t: 0,
  enter() { this.t = 0; },
  exit() {},
  update(dt) {
    this.t += dt;
    if (this.t > 0.3 && (inp.released || kp('Escape', 'Enter', ' ', 'Backspace'))) { sfx('cancel'); goTitle(); }
  },
  draw(c) {
    menuBackground(c);
    const px = 52, py = 12, pw = 280, ph = 192;
    shadowRect(c, px + 4, py + 4, pw, ph, 0.45);
    G.rect(c, px, py, pw, ph, R.paper[4]);
    G.frame(c, px - 1, py - 1, pw + 2, ph + 2, R.paper[0]);
    G.dither(c, px, py + ph - 5, pw, 5, R.paper[3], 8);
    let y = py + 12;
    for (const [f, s] of CREDITS) {
      if (f === 'gap') { y += 6; continue; }
      T(c, s, W >> 1, y, P.inkDark, { font: f, align: 'center' });
      y += f === 'big' ? 18 : 11;
    }
    drawStamp(c, px + pw - 52, py + ph - 26, 'УТВЕРЖДЕНО', P.stampBlue, { angle: -9, size: 'small' });
    scribble(c, px + 24, py + ph - 16, 60, 4242, P.ink);
    if (((this.t * 2) | 0) % 2 === 0) T(c, 'Нажмите, чтобы вернуться', W >> 1, H - 10, R.paper[3], { align: 'center' });
  },
};

const UI = G.UI = {
  drawDialog, button, drawCredibility, courtRecord, drawDocument, drawStamp, drawShout,
  choice, crossHUD, drawWipe,
  TitleScene, CaseSelectScene, SettingsScene, CreditsScene,
  // вспомогательное для интегратора
  dialogY: DLG_Y, dialogH: DLG_H,
  iconCanvas, dim, woodFill, brassFrame, rivet, xform, zoomInt,
};
})();
