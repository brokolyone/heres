/* =====================================================================
   CORE — движок «Слово защиты».
   Низкое разрешение 384x216, всё рисуется попиксельно в буфер,
   буфер масштабируется на экран без сглаживания.
   Все модули — обычные скрипты, общий неймспейс window.G.
   ===================================================================== */
(function () {
'use strict';
const G = window.G = window.G || {};

G.W = 384;
G.H = 216;

/* ---------------------------------------------------------------------
   ПАЛИТРА. Использовать ТОЛЬКО эти цвета (плюс 'transparent').
   Рампы идут от тёмного к светлому.
   --------------------------------------------------------------------- */
const RAMP = G.RAMP = {
  neutral: ['#0d0b10', '#1b1621', '#25202b', '#3a3340', '#544b58', '#776c78', '#9e939c', '#c7bdc0', '#e8e0dc', '#fbf7f0'],
  wood:    ['#2a1810', '#43261a', '#5e3722', '#7d4c2c', '#a06839', '#c48d55', '#ddb27a'],
  stone:   ['#3f3c37', '#5d5a52', '#878276', '#aca596', '#cfc8b6', '#ebe5d3'],
  carpet:  ['#161e33', '#1f2a44', '#2c3b5e', '#3d5079', '#566c98'],
  red:     ['#2e0a10', '#4a1219', '#7a1e26', '#ad2f2f', '#d9503e', '#f08a5d'],
  gold:    ['#3a2709', '#5a3d14', '#8c6420', '#c1922e', '#e8c25a', '#fbe7a1'],
  blue:    ['#0b1122', '#121b33', '#1d2c52', '#2d4478', '#4a68a8', '#7d9bd6', '#b9cdf0'],
  green:   ['#0c1a13', '#14291f', '#21422f', '#346343', '#558a57', '#8dbb75', '#c4dea0'],
  skinL:   ['#5e3a2e', '#9c6450', '#d39a7c', '#f1c7a6', '#fde3cc'],
  skinM:   ['#3e2419', '#6b3f2a', '#a46a46', '#cf9468', '#e8b98b'],
  skinD:   ['#22130e', '#3d2216', '#64392a', '#8a553c', '#b07858'],
  hairBrown: ['#1c110b', '#2b1a12', '#4a2c1c', '#6e4428', '#946238'],
  hairBlack: ['#0b090d', '#121016', '#221d28', '#383145', '#544a63'],
  hairBlond: ['#4d3818', '#7a5a2a', '#b8913f', '#e2c46e', '#f6e6a6'],
  hairRed:   ['#3a140c', '#5a1f12', '#8f3518', '#c45a24', '#e8884a'],
  hairGrey:  ['#3c3a40', '#6d6a72', '#a19ea6', '#d2d0d6', '#f2f1f4'],
  paper:   ['#8f8468', '#b8ab8c', '#d8ccab', '#ece2c6', '#f8f1dc'],
  purple:  ['#1a0f24', '#2e1a40', '#4a2a63', '#6e4390', '#9a6cbc'],
  teal:    ['#0a1f22', '#123438', '#1d5056', '#2f7a7d', '#5aaaa6', '#9ad6c8'],
};
G.PAL = {
  outline: '#1b1621',    // основной контур (не чистый чёрный)
  black:   '#0d0b10',
  white:   '#fbf7f0',
  ink:     '#22305e',    // чернила, шариковая ручка
  inkDark: '#141c3a',
  stamp:   '#b8262f',    // красная мастика печати
  stampBlue: '#2d4478',  // синяя печать
  glow:    '#fff4c8',    // солнечный свет из окон
  sky:     '#9fc6e8',
  sky2:    '#cfe3f2',
  shadow:  '#0d0b10',    // для теней рисовать с globalAlpha ~0.35 ИЛИ дизерингом
};
/* Плоский список всех разрешённых цветов */
G.ALL_COLORS = Array.from(new Set([].concat(...Object.values(RAMP), Object.values(G.PAL))));

/* ---------------------------------------------------------------------
   CANVAS
   --------------------------------------------------------------------- */
const screen = document.createElement('canvas');
screen.id = 'screen';
const buf = document.createElement('canvas');
buf.width = G.W; buf.height = G.H;
const ctx = buf.getContext('2d');
ctx.imageSmoothingEnabled = false;
G.ctx = ctx;
G.buffer = buf;
G.screen = screen;

let scale = 1, offX = 0, offY = 0;
function resize() {
  const dpr = window.devicePixelRatio || 1;
  const cw = Math.max(1, Math.floor(window.innerWidth));
  const ch = Math.max(1, Math.floor(window.innerHeight));
  screen.width = Math.floor(cw * dpr);
  screen.height = Math.floor(ch * dpr);
  screen.style.width = cw + 'px';
  screen.style.height = ch + 'px';
  let s = Math.min(screen.width / G.W, screen.height / G.H);
  if (s >= 2) s = Math.floor(s);          // целочисленный масштаб, когда можем
  scale = s;
  offX = Math.floor((screen.width - G.W * s) / 2);
  offY = Math.floor((screen.height - G.H * s) / 2);
}
G.mountCanvas = function (parent) {
  (parent || document.body).appendChild(screen);
  resize();
  window.addEventListener('resize', resize);
};

/* ---------------------------------------------------------------------
   УТИЛИТЫ РИСОВАНИЯ (все координаты — целые пиксели буфера)
   --------------------------------------------------------------------- */
G.makeCanvas = function (w, h) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  const x = c.getContext('2d');
  x.imageSmoothingEnabled = false;
  return c;
};
/* Нарисовать спрайт через функцию: G.makeSprite(w,h,(ctx)=>{...}) -> canvas */
G.makeSprite = function (w, h, fn) {
  const c = G.makeCanvas(w, h);
  fn(c.getContext('2d'), w, h);
  return c;
};
/* Спрайт из текстовой карты: rows — массив строк одинаковой длины,
   key — {символ: '#hex'}; '.' и ' ' — прозрачно. */
G.fromMap = function (rows, key) {
  const h = rows.length, w = rows[0].length;
  const c = G.makeCanvas(w, h);
  const x = c.getContext('2d');
  for (let j = 0; j < h; j++) {
    const r = rows[j];
    for (let i = 0; i < w; i++) {
      const ch = r[i];
      if (ch === '.' || ch === ' ' || ch === undefined) continue;
      const col = key[ch];
      if (!col) continue;
      x.fillStyle = col;
      x.fillRect(i, j, 1, 1);
    }
  }
  return c;
};
/* Отзеркалить спрайт по горизонтали */
G.flipSprite = function (src) {
  const c = G.makeCanvas(src.width, src.height);
  const x = c.getContext('2d');
  x.translate(src.width, 0); x.scale(-1, 1);
  x.drawImage(src, 0, 0);
  return c;
};
G.px = function (c, x, y, col) { c.fillStyle = col; c.fillRect(x | 0, y | 0, 1, 1); };
G.rect = function (c, x, y, w, h, col) { c.fillStyle = col; c.fillRect(x | 0, y | 0, w | 0, h | 0); };
G.frame = function (c, x, y, w, h, col) {
  c.fillStyle = col;
  c.fillRect(x, y, w, 1); c.fillRect(x, y + h - 1, w, 1);
  c.fillRect(x, y, 1, h); c.fillRect(x + w - 1, y, 1, h);
};
/* Брезенхем */
G.line = function (c, x0, y0, x1, y1, col) {
  x0 |= 0; y0 |= 0; x1 |= 0; y1 |= 0;
  c.fillStyle = col;
  const dx = Math.abs(x1 - x0), dy = -Math.abs(y1 - y0);
  const sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1;
  let e = dx + dy;
  for (;;) {
    c.fillRect(x0, y0, 1, 1);
    if (x0 === x1 && y0 === y1) break;
    const e2 = 2 * e;
    if (e2 >= dy) { e += dy; x0 += sx; }
    if (e2 <= dx) { e += dx; y0 += sy; }
  }
};
/* Дизеринг Байера 4x4. level 0..16 — сколько пикселей из 16 закрасить цветом col */
const BAYER = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5];
G.dither = function (c, x, y, w, h, col, level) {
  c.fillStyle = col;
  for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) {
    if (BAYER[((y + j) & 3) * 4 + ((x + i) & 3)] < level) c.fillRect(x + i, y + j, 1, 1);
  }
};
G.bayer = function (x, y) { return BAYER[(y & 3) * 4 + (x & 3)]; };
/* Залитый эллипс/круг попиксельно */
G.ellipse = function (c, cx, cy, rx, ry, col) {
  c.fillStyle = col;
  for (let j = -ry; j <= ry; j++) {
    const w = Math.round(rx * Math.sqrt(Math.max(0, 1 - (j * j) / (ry * ry + 0.01))));
    c.fillRect(cx - w, cy + j, w * 2 + 1, 1);
  }
};
/* Залитый многоугольник (сканлайн) — для изометрических граней */
G.poly = function (c, pts, col) {
  c.fillStyle = col;
  let minY = Infinity, maxY = -Infinity;
  for (const p of pts) { minY = Math.min(minY, p[1]); maxY = Math.max(maxY, p[1]); }
  minY = Math.floor(minY); maxY = Math.ceil(maxY);
  for (let y = minY; y < maxY; y++) {
    const yc = y + 0.5, xs = [];
    for (let i = 0; i < pts.length; i++) {
      const a = pts[i], b = pts[(i + 1) % pts.length];
      if ((a[1] <= yc && b[1] > yc) || (b[1] <= yc && a[1] > yc)) {
        xs.push(a[0] + (yc - a[1]) / (b[1] - a[1]) * (b[0] - a[0]));
      }
    }
    xs.sort((p, q) => p - q);
    for (let k = 0; k + 1 < xs.length; k += 2) {
      const x0 = Math.round(xs[k]), x1 = Math.round(xs[k + 1]);
      if (x1 > x0) c.fillRect(x0, y, x1 - x0, 1);
    }
  }
};
/* Обвести непрозрачные пиксели спрайта контуром (возвращает новый canvas, +1px со всех сторон) */
G.outlineSprite = function (src, col) {
  const w = src.width, h = src.height;
  const out = G.makeCanvas(w + 2, h + 2);
  const o = out.getContext('2d');
  const d = src.getContext('2d').getImageData(0, 0, w, h).data;
  const a = (x, y) => (x >= 0 && y >= 0 && x < w && y < h) ? d[(y * w + x) * 4 + 3] > 0 : false;
  o.fillStyle = col || G.PAL.outline;
  for (let y = -1; y <= h; y++) for (let x = -1; x <= w; x++) {
    if (a(x, y)) continue;
    if (a(x - 1, y) || a(x + 1, y) || a(x, y - 1) || a(x, y + 1)) o.fillRect(x + 1, y + 1, 1, 1);
  }
  o.drawImage(src, 1, 1);
  return out;
};
/* Нарисовать canvas-спрайт в целых координатах */
G.blit = function (c, spr, x, y, flip) {
  if (!spr) return;
  if (flip) {
    c.save(); c.translate((x | 0) + spr.width, y | 0); c.scale(-1, 1);
    c.drawImage(spr, 0, 0); c.restore();
  } else c.drawImage(spr, x | 0, y | 0);
};

/* Детерминированный ГСЧ */
G.rng = function (seed) {
  let s = seed >>> 0 || 1;
  return function () { s ^= s << 13; s >>>= 0; s ^= s >>> 17; s ^= s << 5; s >>>= 0; return s / 4294967296; };
};
G.clamp = (v, a, b) => v < a ? a : v > b ? b : v;
G.lerp = (a, b, t) => a + (b - a) * t;
G.ease = {
  linear: t => t,
  inOut: t => t < .5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2,
  out: t => 1 - Math.pow(1 - t, 3),
  in: t => t * t * t,
  back: t => { const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2); },
};

/* ---------------------------------------------------------------------
   ВВОД. Координаты мыши — в пикселях буфера.
   --------------------------------------------------------------------- */
const input = G.input = {
  mx: -1, my: -1, down: false, pressed: false, released: false,
  keys: new Set(), _kp: new Set(),
  keyPressed(k) { return this._kp.has(k); },   // k — e.key ('Enter', ' ', 'ArrowLeft', 'x', 'Escape'…)
  wheel: 0,
  inRect(r) { return this.mx >= r.x && this.my >= r.y && this.mx < r.x + r.w && this.my < r.y + r.h; },
  clicked(r) { return this.released && this.inRect(r); },
  any() { return this.released || this._kp.has('Enter') || this._kp.has(' '); },
};
function toBuf(e) {
  const r = screen.getBoundingClientRect();
  const dpr = screen.width / r.width;
  input.mx = Math.floor(((e.clientX - r.left) * dpr - offX) / scale);
  input.my = Math.floor(((e.clientY - r.top) * dpr - offY) / scale);
}
window.addEventListener('pointermove', e => toBuf(e));
window.addEventListener('pointerdown', e => {
  toBuf(e); input.down = true; input.pressed = true;
  G.Audio && G.Audio.unlock && G.Audio.unlock();
});
window.addEventListener('pointerup', e => { toBuf(e); input.down = false; input.released = true; });
window.addEventListener('wheel', e => { input.wheel += Math.sign(e.deltaY); }, { passive: true });
window.addEventListener('keydown', e => {
  if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', ' '].includes(e.key)) e.preventDefault();
  if (!input.keys.has(e.key)) input._kp.add(e.key);
  input.keys.add(e.key);
  G.Audio && G.Audio.unlock && G.Audio.unlock();
});
window.addEventListener('keyup', e => input.keys.delete(e.key));
window.addEventListener('blur', () => input.keys.clear());

/* ---------------------------------------------------------------------
   СЦЕНЫ. scene = { enter(arg), update(dt), draw(ctx), exit() }
   --------------------------------------------------------------------- */
G.scene = null;
G.setScene = function (s, arg) {
  if (G.scene && G.scene.exit) G.scene.exit();
  G.scene = s;
  if (s && s.enter) s.enter(arg);
};

/* ---------------------------------------------------------------------
   ЭКРАННЫЕ ЭФФЕКТЫ: тряска, вспышка, затемнение
   --------------------------------------------------------------------- */
const fx = G.fx = {
  shakeT: 0, shakeDur: 0, shakeAmp: 0,
  flashT: 0, flashDur: 0, flashCol: '#fbf7f0',
  fade: 0,               // 0..1 — чёрное затемнение поверх всего (кроме оверлеев UI, если те рисуют после)
  shake(amp = 3, dur = 0.35) { this.shakeAmp = amp; this.shakeDur = dur; this.shakeT = dur; },
  flash(col = '#fbf7f0', dur = 0.25) { this.flashCol = col; this.flashDur = dur; this.flashT = dur; },
};

/* ---------------------------------------------------------------------
   КАМЕРА для изометрического мира: cam = {x, y, z} — центр в мировых
   пикселях и зум. G.applyCam(ctx, cam) ставит трансформацию.
   --------------------------------------------------------------------- */
G.applyCam = function (c, cam) {
  const z = cam.z || 1;
  const tx = Math.round(G.W / 2 - cam.x * z);
  const ty = Math.round(G.H / 2 - cam.y * z);
  c.setTransform(z, 0, 0, z, tx, ty);
};
G.resetCam = function (c) { c.setTransform(1, 0, 0, 1, 0, 0); };

/* ---------------------------------------------------------------------
   РЕЕСТР ПЕРСОНАЖЕЙ
   G.Cast.register(id, def)
   def = {
     name: 'Имя Фамилия',
     voice: 'low'|'mid'|'high',              // для звука печатания текста
     emotions: ['normal','talk',...],        // список поддерживаемых эмоций бюста
     anims: { gavel: 0.9, ... },             // одноразовые анимации и их длительность (сек)
     bust: { w, h, draw(ctx, x, y, o) },     // x,y = нижняя середина бюста
     iso:  { draw(ctx, x, y, o) }            // x,y = точка ступней в мировых координатах
   }
   o = { emo, talking:bool, t:сек, anim:имя|null, animT:сек, flip:bool, pose:'stand'|'sit', dir:'l'|'r' }
   --------------------------------------------------------------------- */
const cast = {};
G.Cast = {
  defs: cast,
  register(id, def) { cast[id] = def; },
  has(id) { return !!cast[id]; },
  name(id) { return cast[id] ? cast[id].name : id; },
  voice(id) { return cast[id] && cast[id].voice || 'mid'; },
  animDuration(id, a) { return (cast[id] && cast[id].anims && cast[id].anims[a]) || 0; },
  drawBust(c, id, x, y, o) {
    const d = cast[id];
    if (!d || !d.bust) { G.rect(c, x - 20, y - 60, 40, 60, G.RAMP.neutral[4]); return; }
    d.bust.draw(c, x | 0, y | 0, o || {});
  },
  drawIso(c, id, x, y, o) {
    const d = cast[id];
    if (!d || !d.iso) { G.rect(c, x - 3, y - 14, 6, 14, G.RAMP.neutral[5]); return; }
    d.iso.draw(c, x | 0, y | 0, o || {});
  },
};

/* ---------------------------------------------------------------------
   СОХРАНЕНИЯ
   --------------------------------------------------------------------- */
G.Save = {
  key: 'slovo-zashity-v1',
  data: { solved: {}, settings: { music: 0.7, sfx: 0.8, textSpeed: 1 }, progress: null },
  load() {
    try { const s = JSON.parse(localStorage.getItem(this.key)); if (s) this.data = Object.assign(this.data, s); } catch (e) {}
    return this.data;
  },
  save() { try { localStorage.setItem(this.key, JSON.stringify(this.data)); } catch (e) {} },
};

/* ---------------------------------------------------------------------
   ГЛАВНЫЙ ЦИКЛ
   --------------------------------------------------------------------- */
G.time = 0; G.dt = 0; G.frameNo = 0;
let last = 0;
const sctx = screen.getContext('2d');
function frame(ts) {
  const t = ts / 1000;
  let dt = last ? t - last : 1 / 60;
  last = t;
  if (dt > 0.1) dt = 0.1;
  G.dt = dt; G.time += dt; G.frameNo++;

  if (G.scene && G.scene.update) G.scene.update(dt);

  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.globalAlpha = 1;
  ctx.fillStyle = G.PAL.black;
  ctx.fillRect(0, 0, G.W, G.H);
  if (G.scene && G.scene.draw) G.scene.draw(ctx);
  ctx.setTransform(1, 0, 0, 1, 0, 0);

  if (fx.flashT > 0) {
    ctx.globalAlpha = G.clamp(fx.flashT / fx.flashDur, 0, 1);
    ctx.fillStyle = fx.flashCol; ctx.fillRect(0, 0, G.W, G.H);
    ctx.globalAlpha = 1; fx.flashT -= dt;
  }
  if (fx.fade > 0) {
    // ступенчатое затемнение дизерингом — по-пиксельному
    const lvl = Math.round(G.clamp(fx.fade, 0, 1) * 16);
    if (lvl >= 16) { ctx.fillStyle = G.PAL.black; ctx.fillRect(0, 0, G.W, G.H); }
    else if (lvl > 0) G.dither(ctx, 0, 0, G.W, G.H, G.PAL.black, lvl);
  }

  let sx = 0, sy = 0;
  if (fx.shakeT > 0) {
    const k = fx.shakeT / fx.shakeDur;
    sx = Math.round((Math.random() * 2 - 1) * fx.shakeAmp * k);
    sy = Math.round((Math.random() * 2 - 1) * fx.shakeAmp * k);
    fx.shakeT -= dt;
  }
  sctx.imageSmoothingEnabled = false;
  sctx.fillStyle = '#0d0b10';
  sctx.fillRect(0, 0, screen.width, screen.height);
  sctx.drawImage(buf, offX + sx * scale, offY + sy * scale, G.W * scale, G.H * scale);

  input.pressed = false; input.released = false; input._kp.clear(); input.wheel = 0;
  requestAnimationFrame(frame);
}
G.start = function (scene, arg) {
  G.Save.load();
  if (scene) G.setScene(scene, arg);
  requestAnimationFrame(frame);
};

/* Для тестовых страниц: нарисовать кадр вручную без цикла */
G.renderOnce = function (drawFn) {
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.fillStyle = G.PAL.black; ctx.fillRect(0, 0, G.W, G.H);
  drawFn(ctx);
  ctx.setTransform(1, 0, 0, 1, 0, 0);
};
})();
