/* =====================================================================
   CAST_MAIN — постоянный каст «Слово защиты»: игрок, судья, прокурор,
   секретарь, пристав, присяжные, старшина + иконки улик (G.Icons).
   Всё рисуется попиксельно в буфер PB и кэшируется в offscreen-canvas.
   ===================================================================== */
(function () {
'use strict';
const G = window.G;
const R = G.RAMP, P = G.PAL;
const OUT = P.outline;

/* ---------------------------------------------------------------------
   Пиксельный буфер: массив цветов, маски, затенение плоскостями, контур
   --------------------------------------------------------------------- */
const RGB = {};
function rgb(hex) {
  let v = RGB[hex];
  if (!v) { v = RGB[hex] = [parseInt(hex.substr(1, 2), 16), parseInt(hex.substr(3, 2), 16), parseInt(hex.substr(5, 2), 16)]; }
  return v;
}
/* цвет -> на N ступеней темнее в своей рампе */
const DARK = {}, LIGHT = {};
for (const k in R) {
  const r = R[k];
  r.forEach((c, i) => {
    if (!DARK[c]) DARK[c] = r[Math.max(0, i - 2)];
    if (!LIGHT[c]) LIGHT[c] = r[Math.min(r.length - 1, i + 1)];
  });
}

function PB(w, h) { this.w = w; this.h = h; this.d = new Array(w * h).fill(0); }
PB.prototype.set = function (x, y, c) {
  x = Math.round(x); y = Math.round(y);
  if (x < 0 || y < 0 || x >= this.w || y >= this.h || !c) return;
  this.d[y * this.w + x] = c;
};
PB.prototype.get = function (x, y) {
  if (x < 0 || y < 0 || x >= this.w || y >= this.h) return 0;
  return this.d[y * this.w + x];
};
PB.prototype.clear = function (x, y) { if (x >= 0 && y >= 0 && x < this.w && y < this.h) this.d[y * this.w + x] = 0; };
PB.prototype.rect = function (x, y, w, h, c) { for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) this.set(x + i, y + j, c); };
PB.prototype.line = function (x0, y0, x1, y1, c) {
  x0 = Math.round(x0); y0 = Math.round(y0); x1 = Math.round(x1); y1 = Math.round(y1);
  const dx = Math.abs(x1 - x0), dy = -Math.abs(y1 - y0), sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1;
  let e = dx + dy;
  for (;;) {
    this.set(x0, y0, c);
    if (x0 === x1 && y0 === y1) break;
    const e2 = 2 * e;
    if (e2 >= dy) { e += dy; x0 += sx; }
    if (e2 <= dx) { e += dx; y0 += sy; }
  }
};
/* полилиния */
PB.prototype.pl = function (pts, c) { for (let i = 0; i + 1 < pts.length; i++) this.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], c); };
/* текстовая карта */
PB.prototype.map = function (rows, key, ox, oy, flip) {
  for (let j = 0; j < rows.length; j++) {
    const r = rows[j];
    for (let i = 0; i < r.length; i++) {
      const ch = r[i];
      if (ch === '.' || ch === ' ') continue;
      const col = key[ch];
      if (col === undefined) continue;
      const xx = flip ? ox + r.length - 1 - i : ox + i;
      if (col === null) this.clear(xx, oy + j); else this.set(xx, oy + j, col);
    }
  }
};
PB.prototype.fill = function (m, c) { const d = this.d; for (let i = 0; i < d.length; i++) if (m[i]) d[i] = c; };
PB.prototype.mask = function () { const m = new Uint8Array(this.w * this.h); for (let i = 0; i < m.length; i++) m[i] = this.d[i] ? 1 : 0; return m; };
/* селективный контур: снаружи силуэта. Сверху-слева (освещённая сторона) — темнее соседнего тона */
PB.prototype.outline = function (opt) {
  opt = opt || {};
  const w = this.w, h = this.h, src = this.d.slice();
  const g = (x, y) => (x < 0 || y < 0 || x >= w || y >= h) ? 0 : src[y * w + x];
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    if (src[y * w + x]) continue;
    const r = g(x + 1, y), b = g(x, y + 1), l = g(x - 1, y), t = g(x, y - 1);
    if (!(r || b || l || t)) continue;
    if (opt.noBottom && y >= h - 1) continue;
    let c = OUT;
    if (opt.selective !== false && (r || b) && !(l || t)) {
      const n = r || b;
      if (DARK[n] && n !== OUT) c = DARK[DARK[n]] === DARK[n] ? DARK[n] : DARK[n];
    }
    this.d[y * w + x] = c;
  }
};
PB.prototype.toCanvas = function () {
  const c = G.makeCanvas(this.w, this.h);
  const x = c.getContext('2d');
  const im = x.createImageData(this.w, this.h);
  const a = im.data;
  for (let i = 0; i < this.d.length; i++) {
    const col = this.d[i];
    if (!col) continue;
    const v = rgb(col);
    a[i * 4] = v[0]; a[i * 4 + 1] = v[1]; a[i * 4 + 2] = v[2]; a[i * 4 + 3] = 255;
  }
  x.putImageData(im, 0, 0);
  return c;
};
/* маски */
function mNew(pb) { return new Uint8Array(pb.w * pb.h); }
function mPoly(pb, pts) {
  const m = mNew(pb);
  let minY = Infinity, maxY = -Infinity;
  for (const p of pts) { minY = Math.min(minY, p[1]); maxY = Math.max(maxY, p[1]); }
  minY = Math.max(0, Math.floor(minY)); maxY = Math.min(pb.h, Math.ceil(maxY));
  for (let y = minY; y < maxY; y++) {
    const yc = y + 0.5, xs = [];
    for (let i = 0; i < pts.length; i++) {
      const a = pts[i], b = pts[(i + 1) % pts.length];
      if ((a[1] <= yc && b[1] > yc) || (b[1] <= yc && a[1] > yc)) xs.push(a[0] + (yc - a[1]) / (b[1] - a[1]) * (b[0] - a[0]));
    }
    xs.sort((p, q) => p - q);
    for (let k = 0; k + 1 < xs.length; k += 2) {
      const x0 = Math.max(0, Math.round(xs[k])), x1 = Math.min(pb.w, Math.round(xs[k + 1]));
      for (let x = x0; x < x1; x++) m[y * pb.w + x] = 1;
    }
  }
  return m;
}
function mEll(pb, cx, cy, rx, ry) {
  const m = mNew(pb);
  for (let j = -ry; j <= ry; j++) {
    const w = Math.round(rx * Math.sqrt(Math.max(0, 1 - (j * j) / (ry * ry + 0.01))));
    for (let i = -w; i <= w; i++) { const x = cx + i, y = cy + j; if (x >= 0 && y >= 0 && x < pb.w && y < pb.h) m[y * pb.w + x] = 1; }
  }
  return m;
}
function mAnd(a, b) { const m = new Uint8Array(a.length); for (let i = 0; i < a.length; i++) m[i] = a[i] && b[i] ? 1 : 0; return m; }
function mSub(a, b) { const m = new Uint8Array(a.length); for (let i = 0; i < a.length; i++) m[i] = a[i] && !b[i] ? 1 : 0; return m; }
function mOr(a, b) { const m = new Uint8Array(a.length); for (let i = 0; i < a.length; i++) m[i] = a[i] || b[i] ? 1 : 0; return m; }
/* Плоскостное затенение маски: базовый тон, светлая кромка сверху-слева, тень снизу-справа.
   o: {hi:ширина светлой кромки, lo:ширина тени справа, bot:ширина тени снизу, split:x-граница боковой плоскости, splitFn:(y)=>x} */
function shade(pb, m, ramp, base, o) {
  o = o || {};
  const w = pb.w, h = pb.h;
  const in_ = (x, y) => x >= 0 && y >= 0 && x < w && y < h && m[y * w + x];
  const hiW = o.hi === undefined ? 1 : o.hi, loW = o.lo === undefined ? 2 : o.lo, botW = o.bot || 0;
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    if (!m[y * w + x]) continue;
    let t = base;
    const sx = o.splitFn ? o.splitFn(y) : o.split;
    if (sx !== undefined && x >= sx) t = base - 1;
    let edgeR = false;
    for (let k = 1; k <= loW; k++) if (!in_(x + k, y)) { edgeR = true; break; }
    let edgeB = false;
    for (let k = 1; k <= botW; k++) if (!in_(x, y + k)) { edgeB = true; break; }
    if (edgeR || edgeB) t = Math.min(t, base - 1);
    if (hiW > 0) {
      let edgeL = false;
      for (let k = 1; k <= hiW; k++) if (!in_(x - k, y) || !in_(x, y - k)) { edgeL = true; break; }
      if (edgeL && !edgeR && (sx === undefined || x < sx)) t = base + 1;
    }
    pb.d[y * w + x] = ramp[G.clamp(t, 0, ramp.length - 1)];
  }
}
function interp(pts, y) {
  if (y <= pts[0][0]) return pts[0][1];
  for (let i = 0; i + 1 < pts.length; i++) {
    const a = pts[i], b = pts[i + 1];
    if (y >= a[0] && y <= b[0]) return a[1] + (b[1] - a[1]) * (y - a[0]) / Math.max(1, b[0] - a[0]);
  }
  return pts[pts.length - 1][1];
}

/* =====================================================================
   ГОЛОВА (3/4, смотрит влево). Локальная система: 34×42, (0,0) — верх-лево.
   S — внешность, st — состояние лица.
   ===================================================================== */
const PROF = {
  m: {
    L: [[0, 14], [1, 10], [3, 7], [6, 5], [10, 4], [16, 4], [18, 3], [20, 4], [22, 4], [24, 3], [26, 3], [27, 4], [29, 5], [32, 6], [35, 8], [37, 10], [38, 12], [39, 15]],
    R: [[0, 20], [1, 24], [3, 27], [6, 29], [10, 30], [16, 30], [20, 30], [24, 29], [27, 28], [30, 26], [33, 23], [36, 20], [38, 18], [39, 16]],
  },
  f: {
    L: [[0, 14], [1, 10], [3, 7], [6, 5], [10, 4], [16, 4], [18, 4], [20, 4], [22, 4], [24, 3], [26, 4], [28, 5], [30, 6], [33, 7], [35, 9], [37, 11], [38, 13]],
    R: [[0, 20], [1, 24], [3, 27], [6, 29], [10, 30], [16, 30], [20, 29], [24, 28], [27, 26], [30, 24], [33, 21], [36, 18], [38, 15]],
  },
  o: { // пожилой мужчина: тяжелее челюсть, брыли
    L: [[0, 14], [1, 10], [3, 7], [6, 5], [10, 4], [16, 4], [18, 3], [20, 4], [22, 4], [24, 3], [26, 3], [27, 4], [29, 5], [32, 6], [35, 8], [37, 10], [38, 12], [39, 15]],
    R: [[0, 20], [1, 24], [3, 27], [6, 29], [10, 30], [16, 31], [20, 31], [24, 30], [27, 29], [30, 28], [33, 25], [36, 21], [38, 18], [39, 16]],
  },
};
PROF.b = PROF.m; // пристав: как мужской

const EYE_N = {
  open: [
    '..sssss..',
    '..KKKKKKK',
    '.KiPPiWwK',
    '..IHIiw..',
    '...llll..'],
  wide: [
    '.KKKKKKK.',
    'KWiPPiWwK',
    'KWiPHIWw.',
    '.WIIIIw..',
    '..lllll..'],
  small: [
    '.KKKKKKK.',
    'KWWWPWWwK',
    '.WWWWWw..',
    '..lllll..',
    '.........'],
  half: [
    '.........',
    '..sssss..',
    '..KKKKKKK',
    '.KiPPiWwK',
    '..IIIiw..'],
  closed: [
    '.........',
    '.........',
    '.ssssss..',
    '.KKKKKKKK',
    '..lllll..'],
};
const EYE_F = {
  open: [
    '.sss.',
    'KKKKK',
    'PPiWK',
    'IHiw.',
    '.ll..'],
  wide: [
    'KKKKK',
    'iPPWK',
    'iHIw.',
    'IIw..',
    '.ll..'],
  small: [
    'KKKKK',
    'WPWwK',
    'WWw..',
    '.ll..',
    '.....'],
  half: [
    '.....',
    'ssss.',
    'KKKKK',
    'PPiwK',
    'IIw..'],
  closed: [
    '.....',
    '.....',
    'ssss.',
    'KKKKK',
    '.ll..'],
};
const MOUTH = {
  closed: ['.........', '..kKKKKk.', '...lll...', '.........'],
  half:   ['.........', '..KKKKKk.', '...KrrK..', '....ll...'],
  open:   ['...KKKK..', '..KTTTTK.', '..KrrrrK.', '...KttK..', '....ll...'],
  smile:  ['.k.....k.', '..KKKKK..', '...lll...', '.........'],
  smileO: ['.k.....k.', '..KTTTTK.', '...KrrK..', '....ll...'],
  smirk:  ['........k', '.kKKKKKk.', '...lll...', '.........'],
  frown:  ['...KKKK..', '..k....k.', '...lll...', '.........'],
  o:      ['...KKK...', '..KrrrK..', '..KrrrK..', '...KKK...', '....l....'],
  grit:   ['..KKKKKK.', '.KTKTKTK.', '..KKKKKK.', '...lll...'],
  tight:  ['.........', '.kKKKKKKk', '.........', '.........'],
};

function head(pb, ox, oy, S, st) {
  const sk = S.skin;
  const pr = PROF[S.prof || 'm'];
  const W = 34, H = 42;
  const m = mNew(pb);
  const hm = new Uint8Array(W * H);
  for (let y = 0; y < 40; y++) {
    const l = Math.round(interp(pr.L, y)), r = Math.round(interp(pr.R, y));
    for (let x = l; x <= r; x++) {
      hm[y * W + x] = 1;
      const X = ox + x, Y = oy + y;
      if (X >= 0 && Y >= 0 && X < pb.w && Y < pb.h) m[Y * pb.w + X] = 1;
    }
  }
  const inH = (x, y) => x >= 0 && y >= 0 && x < W && y < H && hm[y * W + x];
  const side = [[4, 21], [12, 22], [20, 22], [26, 21], [31, 19], [36, 16], [40, 14]];
  const fem = S.prof === 'f';
  for (let y = 0; y < 40; y++) for (let x = 0; x < W; x++) {
    if (!hm[y * W + x]) continue;
    let t = 3;
    const sx = interp(side, y);
    if (x > sx) t = 2;
    if (!inH(x + 1, y)) t = 1;
    // челюсть снизу
    if (!inH(x, y + 1) || (!inH(x, y + 2) && x > 9)) t = Math.min(t, 2);
    if (!inH(x, y + 1) && x > 12) t = 1;
    // свет на лбу и скуле
    const l = interp(pr.L, y);
    if (y >= 5 && y <= 12 && x >= l + 2 && x <= l + 8 && (y > 6 || x > l + 3)) t = 4;
    if (y >= 23 && y <= 25 && x >= 15 && x <= 18 && x - 15 <= (25 - y) + 1) t = 4;
    if (y >= 22 && y <= 27 && x === l + 1 && x < 6) t = 4;
    // тень скулы (боковая плоскость под скулой)
    if (y >= 27 && y <= 33 && x >= sx - 3 - (y - 27) * 0.3 && x <= sx && t === 3) t = (S.age >= 1 || !fem) ? 2 : 3;
    pb.set(ox + x, oy + y, sk[t]);
  }
  // румянец (дизеринг)
  if (S.blush) for (let y = 27; y <= 28; y++) for (let x = 14; x <= 18; x++) if (G.bayer(x, y) < 6) pb.set(ox + x, oy + y, S.blush);
  // ухо
  if (!S.noEar) {
    const ex = ox + 22, ey = oy + 18;
    pb.map([
      '.oooo.',
      'o3332o',
      'o2112o',
      'o21.2o',
      'o2122o',
      'o2132o',
      '.o222o',
      '.o23o.',
      '..oo..'], { o: sk[1], 1: sk[1], 2: sk[2], 3: sk[3], '.': undefined }, ex, ey);
  }
  // морщины возраста
  if (S.age >= 2) {
    pb.line(ox + 7, oy + 9, ox + 12, oy + 9, sk[2]);
    pb.line(ox + 15, oy + 10, ox + 19, oy + 10, sk[2]);
    pb.line(ox + 5, oy + 7, ox + 9, oy + 7, sk[2]);
    pb.set(ox + 21, oy + 22, sk[2]); pb.set(ox + 22, oy + 23, sk[2]);
    pb.set(ox + 14, oy + 28, sk[2]); pb.set(ox + 15, oy + 29, sk[2]); pb.set(ox + 15, oy + 30, sk[2]);
  }
  // нос: переносица, кончик, ноздря, падающая тень
  const nk = sk;
  pb.set(ox + 11, oy + 19, nk[2]); pb.set(ox + 11, oy + 20, nk[2]);
  pb.set(ox + 12, oy + 21, nk[2]); pb.set(ox + 12, oy + 22, nk[2]); pb.set(ox + 12, oy + 23, nk[2]);
  pb.set(ox + 12, oy + 24, nk[2]); pb.set(ox + 13, oy + 25, nk[2]);
  pb.set(ox + 10, oy + 21, nk[4]); pb.set(ox + 10, oy + 22, nk[4]); pb.set(ox + 9, oy + 23, nk[4]); pb.set(ox + 9, oy + 24, nk[4]);
  pb.set(ox + 8, oy + 26, nk[1]); pb.set(ox + 9, oy + 27, nk[1]); pb.set(ox + 10, oy + 27, nk[1]);
  pb.set(ox + 11, oy + 27, nk[2]); pb.set(ox + 12, oy + 26, nk[1]); pb.set(ox + 13, oy + 26, nk[2]);
  pb.set(ox + 12, oy + 27, nk[2]); pb.set(ox + 13, oy + 27, nk[2]); pb.set(ox + 14, oy + 26, nk[2]);
  pb.set(ox + 7, oy + 25, nk[2]);
  if (!fem) { pb.set(ox + 11, oy + 28, nk[2]); }
  // глаза
  const ek = S.eyeKey || {};
  const eyeKey = {
    K: S.lash || R.neutral[1], W: R.neutral[8], w: R.neutral[6], I: S.iris[1], i: S.iris[0], P: R.neutral[0],
    H: P.white, s: sk[2], l: sk[2],
  };
  Object.assign(eyeKey, ek);
  const es = st.eyes || 'open';
  pb.map(EYE_N[es], eyeKey, ox + 14, oy + 18);
  pb.map(EYE_F[es], eyeKey, ox + 4, oy + 18);
  // брови
  const bc = S.brow, bc2 = S.brow2 || bc;
  const b = st.brows || 'n';
  // [внутр. y, внеш. y] для ближней и дальней брови; смещение
  const BR = { n: [16, 15, 16, 15], stern: [18, 14, 18, 15], up: [13, 12, 13, 13], worried: [14, 16, 14, 16], smug: [16, 13, 17, 16], angry: [18, 13, 19, 15], sad: [14, 17, 15, 17] }[b];
  // ближняя: x 15..22
  for (let x = 15; x <= 22; x++) {
    const k = (x - 15) / 7;
    let y = Math.round(BR[0] + (BR[1] - BR[0]) * k + (b === 'up' || b === 'n' ? -Math.round(Math.sin(k * Math.PI) * 1) : 0));
    pb.set(ox + x, oy + y, bc);
    if (x < 21) pb.set(ox + x, oy + y + 1, x < 17 ? bc : bc2);
  }
  for (let x = 4; x <= 8; x++) {
    const k = (8 - x) / 4;
    const y = Math.round(BR[2] + (BR[3] - BR[2]) * k);
    pb.set(ox + x, oy + y, bc);
    if (x > 4) pb.set(ox + x, oy + y + 1, bc2);
  }
  if (b === 'stern' || b === 'angry') { pb.set(ox + 13, oy + 17, sk[2]); pb.set(ox + 13, oy + 16, sk[2]); }
  if (b === 'worried' || b === 'sad') { pb.set(ox + 12, oy + 13, sk[2]); pb.set(ox + 13, oy + 14, sk[2]); }
  // рот
  const mk = {
    K: S.lipLine || sk[0], k: sk[1], l: S.lipLow || sk[2], r: R.red[1], T: R.neutral[8], t: R.red[3],
  };
  pb.map(MOUTH[st.mouth || 'closed'], mk, ox + 6, oy + 30);
  if (S.lips && (st.mouth === 'closed' || st.mouth === 'smirk' || st.mouth === 'tight')) {
    // накрашенные губы
    const sm = st.mouth === 'smirk';
    pb.line(ox + 9, oy + 30, ox + 13, oy + 30, S.lips[1]);
    pb.line(ox + 10, oy + 32, ox + 13, oy + 32, S.lips[1]);
    pb.set(ox + 11, oy + 32, S.lips[2]); pb.set(ox + 10, oy + 32, S.lips[2]);
    if (sm) pb.set(ox + 15, oy + 30, S.lips[0]);
  }
  // пот
  if (st.sweat) {
    pb.map(['.b.', 'bBb', 'bWb', '.b.'], { b: R.blue[5], B: R.blue[6], W: P.white }, ox + 1, oy + 7);
    pb.map(['.b.', 'bBb', 'bWb', '.b.'], { b: R.blue[5], B: R.blue[6], W: P.white }, ox + 27, oy + 12);
  }
  return m;
}

/* Волосы: список полигонов-прядей (локальные координаты головы), тон по рампе */
function hairShape(pb, ox, oy, polys, ramp, o) {
  o = o || {};
  let all = mNew(pb);
  for (const pts of polys) all = mOr(all, mPoly(pb, pts.map(p => [p[0] + ox, p[1] + oy])));
  const base = o.base === undefined ? 2 : o.base;
  shade(pb, all, ramp, base, { hi: 1, lo: 2, bot: 1 });
  return all;
}

/* =====================================================================
   КЭШ КАДРОВ БЮСТА
   ===================================================================== */
const FW = 150, FH = 136;
function makeBust(def) {
  const cache = {};
  return {
    w: 110, h: 130,
    frame(key, paint) {
      let c = cache[key];
      if (!c) {
        const pb = new PB(FW, FH);
        paint(pb);
        c = cache[key] = pb.toCanvas();
      }
      return c;
    },
  };
}
function blinkState(t, seed) {
  const per = 3.4 + (seed % 5) * 0.17;
  const ph = ((t + seed * 0.71) % per + per) % per;
  if (ph < 0.06) return 'half';
  if (ph < 0.12) return 'closed';
  if (ph < 0.16) return 'half';
  return null;
}
function mouthFrame(o) {
  if (!o.talking) return 0;
  const f = Math.floor((o.t || 0) * 8) % 4;
  return [1, 2, 1, 0][f];
}
function breath(t, seed) {
  seed = seed || 0;
  const per = 2.8 + (seed % 5) * 0.25;
  const v = Math.sin(((t || 0) + seed * 0.91) * Math.PI * 2 / per);
  return v > 0.55 ? 2 : v > -0.35 ? 1 : 0;
}
/* расписание мелких движений: прогресс 0..1 внутри окна dur каждые period сек, иначе -1 */
function sched(t, period, dur, seed) {
  const ph = ((t || 0) + seed * 1.37) % period;
  return ph < dur ? ph / dur : -1;
}
/* поправить очки: рука к переносице (hx,hy — голова) */
function glassesPush(pb, hx, hy, sk, ramp, base) {
  sleeve(pb, ramp, base, 104, 136, hx + 14, hy + 40, 16);
  fist(pb, hx + 9, hy + 31, sk, false);
  pb.rect(hx + 11, hy + 19, 2, 12, sk[3]);
  pb.line(hx + 10, hy + 19, hx + 10, hy + 30, OUT); pb.line(hx + 13, hy + 19, hx + 13, hy + 30, sk[1]);
  pb.set(hx + 11, hy + 18, OUT); pb.set(hx + 12, hy + 18, OUT);
}

/* Общая отрисовка бюста: blit кадра с учётом flip */
function blitBust(ctx, spr, x, y, flip) {
  G.blit(ctx, spr, x - (FW >> 1), y - FH, flip);
}

/* хелперы-утилиты для тел */
function P2(ox, oy, pts) { return pts.map(p => [p[0] + ox, p[1] + oy]); }
function dith(pb, m, col, level, x0, y0, x1, y1) {
  for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) {
    if (m && !m[y * pb.w + x]) continue;
    if (G.bayer(x, y) < level) pb.set(x, y, col);
  }
}
/* кисть: прямоугольная ладонь с пальцами — карты */
const HANDS = {
  // указательный палец влево (рука вытянута влево). 21x12
  point: [
    '...........kkkkk.....',
    'kkkkkkkkkkk44443k....',
    'k444444444444333kk...',
    'kk22222222k4333322k..',
    '.kkkkkkkkkk4kk33222k.',
    '..........k4333k3222k',
    '..........k4kkk32222k',
    '..........k43333k222k',
    '...........k3kk32221k',
    '...........k3332211k.',
    '............kkk1111k.',
    '...............kkkk..'],
  // ладонь плашмя на столе, 16x8
  flat: [
    '.kkkkkkkkkkkk...',
    'k4443333333322k.',
    'k4433333333222k.',
    'k4333333332222kk',
    'k3k33k33k32k221k',
    'k3k33k33k32k21k.',
    'k3kk3kk3kk2kk1k.',
    '.k..k..k..kk.k..'],
  // кулак у подбородка с вытянутым указательным, 12x13
  chin: [
    '.kkkkkkkk...',
    'k44443333k..',
    'k4333333322k',
    'kkkkkk33322k',
    'k4443k33222k',
    'kkkkkk3322k.',
    'k4433k3222k.',
    'kkkkk32221k.',
    '.k4333222k..',
    '.k3332221k..',
    '..k332211k..',
    '..k32221k...',
    '..k3221k....'],
};
function hand(pb, kind, x, y, sk, flip) {
  pb.map(HANDS[kind], { k: OUT, 1: sk[1], 2: sk[2], 3: sk[3], 4: sk[4] }, x, y, flip);
}
/* линии удара */
function impact(pb, cx, cy, col) {
  const L = [[-14, -4, -9, -2], [-12, -10, -8, -6], [-5, -14, -4, -9], [14, -4, 9, -2], [12, -10, 8, -6], [5, -14, 4, -9]];
  for (const l of L) pb.line(cx + l[0], cy + l[1], cx + l[2], cy + l[3], col);
}

/* =====================================================================
   PLAYER — Дэниел Рид
   ===================================================================== */
(function () {
  const sk = R.skinL, hb = R.hairBrown, su = R.blue;
  const S = { skin: sk, iris: [R.hairBrown[2], R.hairBrown[3]], brow: hb[1], brow2: hb[2], prof: 'm', age: 0 };
  const HX = 58, HY = 12;
  const EMO = {
    normal:    { eyes: 'open', brows: 'n', mouth: 'closed' },
    think:     { eyes: 'half', brows: 'worried', mouth: 'tight' },
    confident: { eyes: 'half', brows: 'smug', mouth: 'smirk' },
    shocked:   { eyes: 'small', brows: 'up', mouth: 'o', sweat: true },
    point:     { eyes: 'open', brows: 'stern', mouth: 'closed' },
    slam:      { eyes: 'open', brows: 'angry', mouth: 'grit' },
  };
  const TALK = { closed: ['closed', 'half', 'open'], tight: ['tight', 'half', 'open'], smirk: ['smirk', 'half', 'smileO'], o: ['o', 'o', 'open'], grit: ['grit', 'half', 'open'] };

  function body(pb, emo, br) {
    const by = -br; // дыхание: плечи вверх
    neck(pb, sk, br);
    // торс (пиджак)
    let torsoPts;
    if (emo === 'slam') torsoPts = [[20, 136], [22, 92], [30, 66], [50, 56 + by], [66, 54 + by], [84, 52 + by], [106, 54 + by], [122, 64], [130, 92], [132, 136]];
    else torsoPts = [[28, 136], [30, 100], [32, 76], [36, 64 + by], [46, 58 + by], [62, 54 + by], [84, 52 + by], [104, 55 + by], [114, 60 + by], [118, 72], [120, 100], [122, 136]];
    const torso = mPoly(pb, torsoPts);
    shade(pb, torso, su, 3, { hi: 1, lo: 3, splitFn: y => 96 + (y - 60) * 0.1 });
    // плоскость груди светлее слева (свет)
    // рубашка V
    const shirt = mPoly(pb, [[60, 54 + by], [82, 51 + by], [74, 70], [66, 86]]);
    pb.fill(shirt, R.neutral[8]);
    pb.line(72, 66, 67, 84, R.neutral[7]);
    // воротник рубашки
    pb.map([
      'kkk..........kkk',
      'k99k........k98k',
      '.k998......k998k',
      '..k9987..k8877k.',
      '...k9987k8877k..',
      '....kk97877kk...',
      '......kk7kk.....'], { k: R.neutral[6], 9: R.neutral[9], 8: R.neutral[8], 7: R.neutral[7] }, 61, 50 + by);
    // галстук
    const tie = mPoly(pb, [[68, 60 + by], [75, 59 + by], [74, 64 + by], [77, 90], [71, 98], [66, 90], [69, 64 + by]]);
    shade(pb, tie, R.red, 2, { hi: 1, lo: 1 });
    pb.rect(69, 60 + by, 6, 4, R.red[3]); pb.set(70, 60 + by, R.red[4]); pb.line(69, 64 + by, 74, 64 + by, R.red[1]);
    for (let y = 68; y < 94; y += 5) pb.line(68, y + 2, 76, y - 2, R.red[1]);
    // лацканы
    const lapL = mPoly(pb, [[58, 53 + by], [64, 56 + by], [66, 88], [63, 98], [54, 78], [52, 66]]);
    shade(pb, lapL, su, 4, { hi: 1, lo: 1 });
    pb.pl([[58, 53 + by], [52, 66], [54, 78], [63, 98]], su[1]);
    const lapR = mPoly(pb, [[84, 50 + by], [88, 54 + by], [92, 66], [88, 70], [92, 74], [80, 92], [67, 100], [74, 74], [80, 62]]);
    shade(pb, lapR, su, 3, { hi: 1, lo: 2 });
    pb.pl([[88, 70], [92, 74], [80, 92], [67, 100]], su[1]);
    pb.pl([[92, 66], [88, 70]], su[1]);
    pb.pl([[80, 62], [74, 74], [67, 100]], su[2]);
    // значок коллегии
    pb.map(['.g.', 'gGg', '.g.'], { g: R.gold[3], G: R.gold[5] }, 85, 76);
    pb.set(86, 79, R.gold[1]);
    // нагрудный карман
    pb.line(90, 90, 100, 89, su[2]); pb.line(90, 91, 100, 90, su[4]);
    // пуговицы
    pb.map(['.k.', 'kbk', '.k.'], { k: su[0], b: su[1] }, 64, 108);
    pb.map(['.k.', 'kbk', '.k.'], { k: su[0], b: su[1] }, 63, 124);
    // складки
    pb.pl([[40, 80], [44, 96], [42, 120]], su[2]);
    pb.pl([[110, 76], [108, 100], [112, 130]], su[1]);
    pb.pl([[100, 100], [104, 112]], su[2]);
    pb.pl([[34, 104], [38, 114]], su[2]);
    // рукав ближней руки: граница
    pb.pl([[104, 62 + by], [106, 80], [104, 110], [106, 136]], su[1]);
    pb.pl([[103, 82], [102, 108], [101, 134]], su[4]);
    // дальняя рука
    pb.pl([[36, 72], [34, 96], [34, 136]], su[2]);
  }

  function armPoint(pb) {
    // рука вытянута влево с указательным пальцем
    const sl = mPoly(pb, [[58, 60], [44, 56], [24, 50], [22, 51], [22, 64], [40, 70], [56, 80]]);
    shade(pb, sl, su, 3, { hi: 1, lo: 0, bot: 2 });
    pb.pl([[46, 66], [26, 60]], su[2]);
    pb.pl([[44, 58], [28, 53]], su[4]);
    pb.pl([[52, 74], [46, 70]], su[1]);
    // манжета
    const cf = mPoly(pb, [[23, 50], [19, 50], [19, 63], [23, 64]]);
    pb.fill(cf, R.neutral[8]); pb.line(19, 62, 22, 63, R.neutral[6]); pb.line(19, 50, 19, 62, R.neutral[9]);
    hand(pb, 'point', 0, 49, sk, false);
  }
  function armsSlam(pb) {
    // обе руки вниз к столу
    const a1 = mPoly(pb, [[32, 70], [24, 90], [18, 118], [34, 120], [38, 96], [44, 76]]);
    shade(pb, a1, su, 3, { hi: 1, lo: 2 });
    pb.pl([[36, 80], [32, 112]], su[2]);
    const a2 = mPoly(pb, [[112, 64], [124, 80], [132, 116], [116, 120], [110, 96], [104, 80]]);
    shade(pb, a2, su, 2, { hi: 1, lo: 2 });
    pb.pl([[114, 86], [120, 112]], su[1]);
    pb.rect(18, 117, 16, 3, R.neutral[8]); pb.rect(116, 117, 16, 3, R.neutral[7]);
    hand(pb, 'flat', 18, 120, sk, false);
    hand(pb, 'flat', 116, 120, sk, true);
    impact(pb, 26, 128, R.neutral[8]);
    impact(pb, 124, 128, R.neutral[8]);
  }
  function armThink(pb, hx, hy) {
    const wx = hx + 14, wy = hy + 46;
    const a = mPoly(pb, [[wx - 4, wy - 2], [wx + 8, wy - 2], [wx + 22, wy + 30], [wx + 30, 136], [wx + 10, 136], [wx + 4, wy + 30]]);
    shade(pb, a, su, 3, { hi: 1, lo: 2 });
    pb.pl([[wx + 2, wy + 4], [wx + 10, wy + 34], [wx + 14, 136]], su[2]);
    pb.pl([[wx - 4, wy - 2], [wx + 4, wy + 30], [wx + 10, 136]], OUT);
    pb.rect(wx - 3, wy - 3, 10, 3, R.neutral[8]);
    pb.line(wx - 3, wy - 1, wx + 6, wy - 1, R.neutral[6]);
  }

  function hair(pb, ox, oy, emo) {
    // задняя масса + чёлка набок
    const back = [
      [[8, 6], [12, 0], [20, -3], [28, -1], [33, 5], [34, 14], [33, 22], [31, 28], [27, 30], [26, 18], [24, 14], [20, 11]],
    ];
    hairShape(pb, ox, oy, back, hb, { base: 2 });
    const fr = [
      [[2, 12], [3, 6], [7, 1], [13, -2], [21, -3], [27, 0], [24, 4], [18, 6], [13, 9], [9, 13], [5, 16]],
      [[14, 8], [19, 4], [26, 3], [30, 8], [25, 10], [21, 12]],
      [[22, 12], [28, 8], [32, 12], [31, 18], [27, 16]],
    ];
    hairShape(pb, ox, oy, fr, hb, { base: 3 });
    // пряди и блики
    const hl = hb[4];
    pb.pl([[ox + 6, oy + 6], [ox + 11, oy + 2], [ox + 16, oy]], hl);
    pb.pl([[ox + 10, oy + 6], [ox + 15, oy + 3]], hl);
    pb.pl([[ox + 19, oy + 1], [ox + 23, oy]], hl);
    pb.pl([[ox + 5, oy + 13], [ox + 10, oy + 9], [ox + 16, oy + 6], [ox + 22, oy + 4]], hb[1]);
    pb.pl([[ox + 18, oy + 9], [ox + 24, oy + 6], [ox + 28, oy + 5]], hb[1]);
    pb.pl([[ox + 26, oy + 12], [ox + 29, oy + 9]], hb[1]);
    pb.pl([[ox + 29, oy + 16], [ox + 32, oy + 12]], hb[1]);
    pb.pl([[ox + 28, oy + 22], [ox + 31, oy + 18]], hb[2]);
    // бакенбарды
    pb.rect(ox + 22, oy + 15, 2, 4, hb[2]);
  }

  const bust = makeBust();
  function paint(pb, emo, eyes, mouth, br, fid) {
    const e = EMO[emo] || EMO.normal;
    if (emo === 'slam') { /* голова ниже, наклон вперёд */ }
    const hy = HY + (emo === 'slam' ? 6 : 0) - br, hx = HX - (emo === 'slam' ? 2 : 0) - (emo === 'point' ? 2 : 0);
    body(pb, emo, br);
    if (emo === 'think') armThink(pb, hx, hy);
    head(pb, hx, hy, S, { eyes: eyes, brows: e.brows, mouth: mouth, sweat: e.sweat });
    hair(pb, hx, hy, emo);
    if (emo === 'think') hand(pb, 'chin', hx + 8, hy + 33, sk, false);
    if (emo === 'point') armPoint(pb);
    if (emo === 'slam') armsSlam(pb);
    if (fid) { // поправляет узел галстука
      sleeve(pb, su, 3, 112, 136, 84, 72 - br, 16);
      pb.rect(80, 66 - br, 8, 3, R.neutral[8]);
      fist(pb, 72, 60 - br, sk, false);
    }
    pb.outline();
  }
  bust.draw = function (ctx, x, y, o) {
    const emo = EMO[o.emo] ? o.emo : 'normal';
    const e = EMO[emo];
    const bl = blinkState(o.t || 0, 1);
    let eyes = e.eyes;
    if (bl && eyes !== 'small') eyes = (bl === 'closed' || eyes === 'half') ? 'closed' : 'half';
    const mf = mouthFrame(o);
    const tm = TALK[e.mouth] || TALK.closed;
    const mouth = tm[mf] || e.mouth;
    const br = breath(o.t, 1);
    const tieP = emo === 'normal' && !o.talking ? sched(o.t, 11, 1.1, 1) : -1;
    const fid = tieP >= 0 ? 1 : 0;
    const key = emo + '|' + eyes + '|' + mouth + '|' + br + '|' + fid;
    const spr = bust.frame(key, pb => paint(pb, emo, eyes, mouth, br, fid));
    blitBust(ctx, spr, x, y, o.flip);
  };
  G.Cast.register('player', {
    name: 'Дэниел Рид', voice: 'mid',
    emotions: ['normal', 'think', 'confident', 'shocked', 'point', 'slam'],
    anims: {},
    bust: bust,
    iso: null,
  });
})();

/* =====================================================================
   ОБЩИЙ КОНСТРУКТОР БЮСТА С АНИМАЦИЯМИ
   cfg = { EMO, TALK, seed, paint(pb, emo, e, eyes, mouth, br, af), animFrame(anim, t)->{id,...}|null }
   ===================================================================== */
const TALK_STD = { closed: ['closed', 'half', 'open'], tight: ['tight', 'half', 'open'], smirk: ['smirk', 'half', 'smileO'],
  o: ['o', 'o', 'open'], grit: ['grit', 'half', 'open'], smile: ['smile', 'smileO', 'open'], frown: ['frown', 'half', 'open'] };
function buildBust(cfg) {
  const bust = makeBust();
  bust.draw = function (ctx, x, y, o) {
    const emo = cfg.EMO[o.emo] ? o.emo : 'normal';
    const e = cfg.EMO[emo];
    const af = (o.anim && cfg.animFrame) ? cfg.animFrame(o.anim, o.animT || 0) : null;
    let eyes = (af && af.eyes) || e.eyes;
    const bl = blinkState(o.t || 0, cfg.seed || 2);
    if (bl && eyes !== 'small' && eyes !== 'wide') eyes = (bl === 'closed' || eyes === 'half') ? 'closed' : 'half';
    const baseM = (af && af.mouth) || e.mouth;
    const tm = (cfg.TALK || TALK_STD)[baseM] || TALK_STD.closed;
    const mouth = o.talking ? tm[mouthFrame(o)] : baseM;
    const br = af ? 0 : breath(o.t, cfg.seed || 2);
    const fd = (!af && cfg.fidget && emo === 'normal') ? cfg.fidget(o.t || 0) : null;
    const key = emo + '|' + eyes + '|' + mouth + '|' + br + '|' + (af ? af.id : '') + '|' + (fd ? fd.id : '');
    const spr = bust.frame(key, pb => { cfg.paint(pb, emo, e, eyes, mouth, br, af, fd); pb.outline(); });
    blitBust(ctx, spr, x, y, o.flip);
  };
  return bust;
}
function glasses(pb, hx, hy, col, hi, o) {
  o = o || {};
  const y0 = hy + 17 + (o.dy || 0);
  // ближняя линза
  pb.pl([[hx + 13, y0], [hx + 22, y0], [hx + 22, y0 + 5], [hx + 21, y0 + 6], [hx + 14, y0 + 6], [hx + 13, y0 + 5], [hx + 13, y0]], col);
  // дальняя
  pb.pl([[hx + 3, y0], [hx + 9, y0], [hx + 9, y0 + 5], [hx + 8, y0 + 6], [hx + 4, y0 + 6], [hx + 3, y0 + 5]], col);
  pb.line(hx + 10, y0 + 1, hx + 12, y0 + 1, col);
  pb.line(hx + 23, y0 + 1, hx + 25, y0 + 2, col);
  if (hi) { pb.set(hx + 20, y0 + 1, hi); pb.set(hx + 19, y0 + 2, hi); pb.set(hx + 21, y0 + 2, hi); pb.set(hx + 8, y0 + 1, hi); }
}
/* универсальный торс-пиджак: ramp, базовый тон; возвращает маску */
function torso(pb, ramp, base, br, wide) {
  const by = -br, k = wide ? 4 : 0;
  const m = mPoly(pb, [[28 - k, 136], [30 - k, 100], [32 - k, 76], [36 - k, 64 + by], [46 - k, 58 + by], [62, 54 + by], [84, 52 + by], [104 + k, 55 + by], [114 + k, 60 + by], [118 + k, 72], [120 + k, 100], [122 + k, 136]]);
  shade(pb, m, ramp, base, { hi: 1, lo: 3, splitFn: y => 98 + k + (y - 60) * 0.1 });
  pb.pl([[104 + k, 62 + by], [106 + k, 80], [104 + k, 110], [106 + k, 136]], ramp[Math.max(0, base - 2)]);
  pb.pl([[36 - k, 72], [34 - k, 96], [34 - k, 136]], ramp[Math.max(0, base - 1)]);
  pb.pl([[40, 84], [44, 98], [42, 120]], ramp[Math.max(0, base - 1)]);
  pb.pl([[110 + k, 76], [108 + k, 100], [112 + k, 130]], ramp[Math.max(0, base - 2)]);
  return m;
}
function neck(pb, sk, br, thin) {
  const a = thin ? 66 : 63, b = thin ? 78 : 80;
  const n = mPoly(pb, [[a, 40], [b, 40], [b, 58 - br], [a + 1, 60 - br]]);
  pb.fill(n, sk[2]);
  for (let y = 40; y < 54 - br; y++) for (let x = a; x <= b; x++) if (n[y * pb.w + x] && (y < 50 - br || x > a + 6 + (y - 50))) pb.set(x, y, sk[1]);
  pb.line(a + 1, 52 - br, a + 1, 57 - br, sk[3]);
}
/* рука в рукаве: от плеча (sx,sy) к кисти (hx,hy), толщина w */
function sleeve(pb, ramp, base, sx, sy, ex, ey, w) {
  const dx = ex - sx, dy = ey - sy, L = Math.hypot(dx, dy) || 1;
  const nx = -dy / L * w / 2, ny = dx / L * w / 2;
  const m = mPoly(pb, [[sx + nx, sy + ny], [ex + nx * 0.8, ey + ny * 0.8], [ex - nx * 0.8, ey - ny * 0.8], [sx - nx, sy - ny]]);
  shade(pb, m, ramp, base, { hi: 1, lo: 2, bot: 1 });
  return m;
}
/* кулак с рукоятью 9x8 */
function fist(pb, x, y, sk, flip) {
  pb.map([
    '.kkkkkk..',
    'k443333k.',
    'k4k3k32kk',
    'k3k3k322k',
    'k3333222k',
    '.k322211k',
    '..kkkkkk.'], { k: OUT, 1: sk[1], 2: sk[2], 3: sk[3], 4: sk[4] }, x, y, flip);
}
/* молоток: рукоять из (x0,y0) под углом a (рад), длина L */
function gavel(pb, x0, y0, a, L) {
  const w = R.wood;
  const ex = x0 + Math.cos(a) * L, ey = y0 + Math.sin(a) * L;
  // рукоять
  pb.line(x0, y0, ex, ey, w[4]);
  pb.line(x0 + 1, y0 + 1, ex + 1, ey + 1, w[2]);
  // головка — перпендикулярно рукояти
  const px = -Math.sin(a), py = Math.cos(a), hx = Math.cos(a), hy = Math.sin(a);
  const hl = 9, hw = 4;
  const c = [[ex + px * hl - hx * hw, ey + py * hl - hy * hw], [ex + px * hl + hx * hw, ey + py * hl + hy * hw], [ex - px * hl + hx * hw, ey - py * hl + hy * hw], [ex - px * hl - hx * hw, ey - py * hl - hy * hw]];
  const m = mPoly(pb, c);
  shade(pb, m, w, 3, { hi: 1, lo: 2, bot: 1 });
  // золотые кольца
  for (const s of [-6, 6]) pb.line(ex + px * s - hx * 3, ey + py * s - hy * 3, ex + px * s + hx * 3, ey + py * s + hy * 3, R.gold[3]);
  for (const p of c) pb.set(p[0], p[1], 0);
}

/* =====================================================================
   JUDGE — судья Гарольд Уитакер
   ===================================================================== */
(function () {
  const sk = R.skinL, hg = R.hairGrey, rb = R.neutral;
  const S = { skin: sk, iris: [R.blue[2], R.blue[4]], brow: hg[2], brow2: hg[3], prof: 'o', age: 2 };
  const HX = 58, HY = 12;
  const EMO = {
    normal:    { eyes: 'open', brows: 'n', mouth: 'closed' },
    stern:     { eyes: 'half', brows: 'stern', mouth: 'frown' },
    surprised: { eyes: 'wide', brows: 'up', mouth: 'o' },
    smile:     { eyes: 'half', brows: 'n', mouth: 'smile' },
  };
  function body(pb, br, af) {
    neck(pb, sk, br);
    const m = torso(pb, rb, 2, br, true);
    // складки мантии (вертикальные)
    for (const x of [44, 52, 90, 98]) pb.pl([[x, 80], [x - 1, 110], [x + 1, 136]], rb[1]);
    for (const x of [46, 54]) pb.pl([[x, 90], [x, 136]], rb[3]);
    // кокетка мантии
    pb.pl([[36, 76], [60, 84], [76, 88], [100, 82], [116, 74]], rb[1]);
    pb.pl([[36, 77], [60, 85]], rb[3]);
    // рубашка и галстук в вырезе
    const sh = mPoly(pb, [[60, 54 - br], [84, 51 - br], [76, 76], [70, 78]]);
    pb.fill(sh, rb[8]);
    pb.map([
      'kkk.........kkk',
      'k99k.......k98k',
      '.k998.....k997k',
      '..k998k.k8877k.',
      '...kk97k877kk..',
      '.....kk7kk.....'], { k: rb[6], 9: rb[9], 8: rb[8], 7: rb[7] }, 62, 50 - br);
    const tie = mPoly(pb, [[70, 58 - br], [75, 58 - br], [76, 76], [73, 80], [70, 76]]);
    shade(pb, tie, R.carpet, 2, { hi: 1, lo: 1 });
    // отвороты мантии
    pb.pl([[58, 54 - br], [62, 70], [70, 80]], rb[3]);
    pb.pl([[86, 52 - br], [82, 70], [76, 80]], rb[0]);
  }
  function hair(pb, hx, hy) {
    // седые волосы: зачёс назад, залысины
    hairShape(pb, hx, hy, [
      [[10, 3], [16, -2], [24, -2], [31, 3], [34, 12], [33, 22], [30, 28], [27, 26], [27, 16], [24, 10], [18, 6], [12, 6]],
    ], hg, { base: 2 });
    pb.pl([[hx + 13, hy + 1], [hx + 19, hy - 1], [hx + 25, hy]], hg[4]);
    pb.pl([[hx + 15, hy + 4], [hx + 22, hy + 2], [hx + 28, hy + 5]], hg[1]);
    pb.pl([[hx + 26, hy + 10], [hx + 31, hy + 12]], hg[1]);
    pb.pl([[hx + 28, hy + 18], [hx + 32, hy + 19]], hg[1]);
    pb.pl([[hx + 22, hy + 6], [hx + 29, hy + 8]], hg[3]);
    pb.rect(hx + 22, hy + 14, 2, 5, hg[2]);
  }
  function arm(pb, af) {
    // плечо ближней руки ~ (104,64); кисть по кадру
    const F = af.f;
    const pos = [[118, 22, -1.9], [116, 34, -1.3], [106, 70, -0.4], [94, 104, 0.15], [100, 96, 0.0], [108, 82, -0.3]][F];
    const [hx, hy, ang] = pos;
    sleeve(pb, rb, 2, 108, 68, hx + 5, hy + 8, 20);
    sleeve(pb, rb, 3, 106, 66, hx + 4, hy + 6, 10);
    // манжета
    pb.rect(hx - 1, hy + 6, 11, 3, rb[8]);
    gavel(pb, hx + 3, hy + 3, ang + Math.PI, 16);
    fist(pb, hx, hy, sk, false);
    if (F === 3) {
      impact(pb, hx - 14, hy + 22, P.white);
      pb.line(hx - 30, hy + 20, hx - 22, hy + 20, R.gold[4]);
      pb.line(hx + 12, hy + 20, hx + 20, hy + 20, R.gold[4]);
    }
  }
  const bust = buildBust({
    EMO, seed: 3,
    animFrame(a, t) {
      if (a !== 'gavel' || t >= 0.9) return null;
      const f = t < 0.18 ? 1 : t < 0.36 ? 0 : t < 0.45 ? 2 : t < 0.6 ? 3 : t < 0.75 ? 4 : 5;
      return { id: 'g' + f, f: f, eyes: f === 3 ? 'closed' : 'half', mouth: 'tight' };
    },
    fidget(t) {
      const g = sched(t, 9.5, 1.2, 3);
      if (g >= 0) return { id: 'gl', k: 'gl' };
      const l = sched(t, 14, 2.2, 5);
      if (l >= 0) return { id: 'ln', k: 'ln' };
      return null;
    },
    paint(pb, emo, e, eyes, mouth, br, af, fd) {
      body(pb, br, af);
      let HX = 58;
      let hy = HY - br;
      if (fd && fd.k === 'ln') { HX -= 2; hy += 2; }
      head(pb, HX, hy, S, { eyes: eyes, brows: af ? 'stern' : e.brows, mouth: mouth });
      hair(pb, HX, hy);
      // кустистые седые брови над оправой
      const bw = af ? 'stern' : e.brows;
      const by0 = { n: 14, stern: 15, up: 11, smile: 14 }[bw] || 14;
      pb.line(HX + 15, hy + by0, HX + 21, hy + by0 - (bw === 'stern' ? 1 : 0), hg[3]);
      pb.line(HX + 16, hy + by0 - 1, HX + 20, hy + by0 - 1, hg[4]);
      pb.line(HX + 4, hy + by0, HX + 8, hy + by0, hg[3]);
      glasses(pb, HX, hy, hg[0], P.white, { dy: 1 });
      if (af) arm(pb, af);
      if (fd && fd.k === 'gl') glassesPush(pb, HX, hy, sk, rb, 2);
    },
  });
  G.Cast.register('judge', {
    name: 'Судья Уитакер', voice: 'low',
    emotions: ['normal', 'stern', 'surprised', 'smile'],
    anims: { gavel: 0.9 }, bust: bust, iso: null,
  });
})();

/* =====================================================================
   PROSECUTOR — Виктория Лейн
   ===================================================================== */
(function () {
  const sk = R.skinL, hk = R.hairBlack, gs = R.neutral;
  const S = { skin: sk, iris: [R.green[1], R.green[3]], brow: hk[0], brow2: hk[1], prof: 'f', age: 1,
    lipLine: R.red[2], lipLow: R.red[3], lips: [R.red[2], R.red[3], R.red[4]], lash: R.neutral[0] };
  const HX = 58, HY = 12;
  const EMO = {
    normal:  { eyes: 'open', brows: 'n', mouth: 'closed' },
    smirk:   { eyes: 'half', brows: 'smug', mouth: 'smirk' },
    angry:   { eyes: 'open', brows: 'angry', mouth: 'grit' },
    shocked: { eyes: 'small', brows: 'up', mouth: 'o', sweat: true },
    point:   { eyes: 'open', brows: 'stern', mouth: 'closed' },
  };
  function body(pb, br, slam) {
    neck(pb, sk, br, true);
    const by = -br;
    const m = slam
      ? mPoly(pb, [[26, 136], [28, 96], [34, 70], [50, 60], [66, 56], [84, 54], [102, 56], [116, 66], [124, 96], [126, 136]])
      : mPoly(pb, [[38, 136], [38, 100], [39, 76], [42, 66 + by], [50, 60 + by], [64, 56 + by], [84, 54 + by], [100, 57 + by], [107, 62 + by], [110, 74], [111, 100], [112, 136]]);
    shade(pb, m, gs, 5, { hi: 1, lo: 3, splitFn: y => 96 + (y - 60) * 0.1 });
    // блузка (тёмная шёлковая)
    const bl = mPoly(pb, [[62, 55 + by], [82, 53 + by], [76, 74], [70, 82]]);
    shade(pb, bl, R.neutral, 8, { hi: 0, lo: 1 });
    pb.pl([[66, 56 + by], [70, 66], [72, 80]], gs[7]);
    // лацканы — острые
    const lL = mPoly(pb, [[60, 56 + by], [64, 58 + by], [70, 84], [66, 96], [56, 76], [54, 64]]);
    shade(pb, lL, gs, 6, { hi: 1, lo: 1 });
    const lR = mPoly(pb, [[84, 53 + by], [88, 56 + by], [94, 66], [89, 69], [94, 72], [80, 90], [70, 100], [76, 74]]);
    shade(pb, lR, gs, 5, { hi: 1, lo: 2 });
    pb.pl([[89, 69], [94, 72], [80, 90], [70, 100]], gs[3]);
    pb.pl([[76, 74], [70, 100]], gs[4]);
    // талия, пуговица
    pb.pl([[40, 104], [52, 110]], gs[4]); pb.pl([[100, 110], [110, 104]], gs[3]);
    pb.map(['.k.', 'kbk', '.k.'], { k: gs[2], b: gs[7] }, 68, 108);
    // складки
    pb.pl([[100, 66 + by], [102, 84], [100, 112], [102, 136]], gs[3]);
    pb.pl([[42, 78], [44, 92]], gs[4]);
    // брошь
    pb.map(['.r.', 'rRr', '.r.'], { r: R.red[2], R: R.red[4] }, 88, 78);
  }
  function hair(pb, hx, hy, back) {
    if (back) {
      // задняя часть каре (за шеей)
      hairShape(pb, hx, hy, [[[18, 4], [30, 2], [36, 12], [36, 30], [34, 38], [24, 40], [22, 30]]], hk, { base: 2 });
      return;
    }
    hairShape(pb, hx, hy, [
      // верх и чёлка с пробором: острый угол к лицу
      [[1, 15], [3, 6], [8, 0], [16, -3], [26, -2], [33, 4], [35, 14], [36, 30], [35, 38], [30, 40], [24, 39], [27, 30], [27, 18], [23, 10], [16, 7], [10, 9], [6, 13]],
    ], hk, { base: 2 });
    // острая прядь у щеки
    hairShape(pb, hx, hy, [[[20, 14], [24, 10], [28, 18], [28, 32], [24, 41], [21, 36], [23, 26]]], hk, { base: 3 });
    // блики (холодные)
    pb.pl([[hx + 5, hy + 7], [hx + 10, hy + 2], [hx + 17, hy - 1]], hk[4]);
    pb.pl([[hx + 9, hy + 6], [hx + 14, hy + 3]], hk[4]);
    pb.pl([[hx + 30, hy + 6], [hx + 33, hy + 14]], hk[4]);
    pb.pl([[hx + 7, hy + 11], [hx + 14, hy + 7], [hx + 22, hy + 6]], hk[0]);
    pb.pl([[hx + 30, hy + 18], [hx + 31, hy + 36]], hk[1]);
    pb.pl([[hx + 33, hy + 16], [hx + 34, hy + 34]], hk[3]);
    pb.pl([[hx + 25, hy + 20], [hx + 25, hy + 34]], hk[1]);
    // жемчужная серьга (ниже пряди)
    pb.map(['.w.', 'wWw', '.v.'], { w: R.neutral[7], W: P.white, v: R.neutral[6] }, hx + 22, hy + 30);
  }
  function armPoint(pb) {
    const sl = mPoly(pb, [[58, 62], [44, 58], [24, 52], [22, 53], [22, 64], [40, 70], [56, 80]]);
    shade(pb, sl, gs, 5, { hi: 1, lo: 0, bot: 2 });
    pb.pl([[46, 66], [26, 60]], gs[4]);
    pb.pl([[44, 60], [28, 55]], gs[6]);
    hand(pb, 'point', 1, 50, sk, false);
    // красный маникюр
    pb.set(1, 52, R.red[3]);
  }
  function armsSlam(pb, f) {
    // f: 0 — руки подняты, 1 — удар, 2 — держит
    const hy = f === 0 ? 96 : 120;
    sleeve(pb, gs, 5, 40, 74, 26, hy, 14);
    sleeve(pb, gs, 4, 110, 70, 124, hy, 14);
    hand(pb, 'flat', 18, hy, sk, false);
    hand(pb, 'flat', 116, hy, sk, true);
    if (f === 1) { impact(pb, 26, hy + 8, P.white); impact(pb, 124, hy + 8, P.white); }
  }
  const bust = buildBust({
    EMO, seed: 5,
    animFrame(a, t) {
      if (a !== 'slam' || t >= 0.6) return null;
      const f = t < 0.18 ? 0 : t < 0.36 ? 1 : 2;
      return { id: 's' + f, f: f, eyes: 'open', mouth: f === 0 ? 'tight' : 'grit' };
    },
    fidget(t) {
      const p = sched(t, 6.5, 1.6, 5);
      if (p < 0) return null;
      return { id: 'pen' + (Math.floor(p * 10) % 2), f: Math.floor(p * 10) % 2 };
    },
    paint(pb, emo, e, eyes, mouth, br, af, fd) {
      const slam = !!af;
      let hx = HX, hy = HY - br;
      if (slam && af.f > 0) { hy += 5; hx -= 2; }
      hair(pb, hx, hy, true);
      body(pb, br, slam && af.f > 0);
      head(pb, hx, hy, S, { eyes: eyes, brows: slam ? 'angry' : e.brows, mouth: mouth, sweat: e.sweat });
      hair(pb, hx, hy, false);
      if (emo === 'point' && !slam) armPoint(pb);
      if (slam) armsSlam(pb, af.f);
      if (fd) { // постукивает ручкой
        sleeve(pb, gs, 5, 44, 84, 34, 122, 14);
        fist(pb, 28, 118, sk, false);
        const ty = fd.f ? 112 : 108;
        pb.line(31, ty, 34, 119, R.neutral[1]); pb.line(32, ty, 35, 119, R.gold[4]);
        if (fd.f) { pb.set(29, 110, P.white); pb.set(27, 112, P.white); }
      }
    },
  });
  G.Cast.register('prosecutor', {
    name: 'Виктория Лейн', voice: 'high',
    emotions: ['normal', 'smirk', 'angry', 'shocked', 'point'],
    anims: { slam: 0.6 }, bust: bust, iso: null,
  });
})();

/* =====================================================================
   CLERK — Нора Пак
   ===================================================================== */
(function () {
  const sk = R.skinL, hk = R.hairBlack, tl = R.teal;
  const S = { skin: sk, iris: [R.hairBrown[1], R.hairBrown[2]], brow: hk[1], brow2: hk[2], prof: 'f', age: 0,
    lipLow: R.red[4], blush: R.red[5] };
  const HX = 58, HY = 13;
  const EMO = { normal: { eyes: 'open', brows: 'n', mouth: 'closed' } };
  function body(pb, br) {
    neck(pb, sk, br, true);
    const by = -br;
    const m = mPoly(pb, [[32, 136], [34, 100], [36, 76], [40, 66 + by], [50, 60 + by], [62, 56 + by], [84, 54 + by], [100, 57 + by], [108, 62 + by], [112, 74], [114, 100], [116, 136]]);
    shade(pb, m, tl, 3, { hi: 1, lo: 3, splitFn: y => 94 + (y - 60) * 0.1 });
    // вязка: рёбра по вертикали
    for (let y = 70; y < 136; y++) for (let x = 36; x < 114; x++) if (m[y * pb.w + x] && (x % 4 === 0) && pb.get(x, y) === tl[3]) pb.set(x, y, tl[2]);
    // блузка белая
    const bl = mPoly(pb, [[62, 56 + by], [82, 54 + by], [80, 136], [64, 136]]);
    shade(pb, bl, R.neutral, 8, { hi: 1, lo: 2 });
    pb.map(['kk.......kk', 'k99k...k98k', '.k998k899k.', '..kk9k8kk..'], { k: R.neutral[6], 9: R.neutral[9], 8: R.neutral[8] }, 66, 53 + by);
    for (let y = 72; y < 136; y += 12) pb.map(['k'], { k: R.neutral[5] }, 72, y);
    // кромка кардигана с пуговицами
    pb.pl([[62, 56 + by], [64, 136]], tl[1]); pb.pl([[82, 54 + by], [80, 136]], tl[1]);
    pb.pl([[63, 58], [65, 136]], tl[4]);
    for (let y = 84; y < 136; y += 14) pb.map(['.k.', 'kWk', '.k.'], { k: tl[1], W: R.neutral[7] }, 83, y);
    // цепочка очков
    pb.pl([[67, 54], [69, 64], [74, 70], [79, 64], [82, 54]], R.gold[3]);
    for (let i = 0; i < 6; i++) pb.set(68 + i * 2, 60 + (i % 3), R.gold[5]);
    // папка в руках внизу
    const f = mPoly(pb, [[44, 118], [96, 112], [100, 136], [46, 136]]);
    shade(pb, f, R.paper, 2, { hi: 1, lo: 1 });
    pb.line(46, 121, 98, 115, R.paper[4]);
    hand(pb, 'flat', 52, 120, sk, false);
  }
  function hair(pb, hx, hy, back) {
    if (back) { // пучок
      hairShape(pb, hx, hy, [[[26, 2], [34, -2], [40, 4], [40, 12], [34, 16], [28, 12]]], hk, { base: 2 });
      pb.pl([[hx + 30, hy + 2], [hx + 36, hy + 0]], hk[4]);
      pb.pl([[hx + 30, hy + 8], [hx + 37, hy + 10]], hk[1]);
      return;
    }
    hairShape(pb, hx, hy, [[[2, 14], [3, 7], [8, 1], [16, -2], [25, -1], [32, 4], [34, 12], [33, 22], [30, 26], [27, 18], [24, 12], [18, 7], [11, 7], [6, 10]]], hk, { base: 2 });
    pb.pl([[hx + 4, hy + 9], [hx + 9, hy + 3], [hx + 16, hy]], hk[4]);
    pb.pl([[hx + 18, hy + 1], [hx + 26, hy + 2], [hx + 30, hy + 6]], hk[3]);
    pb.pl([[hx + 8, hy + 7], [hx + 17, hy + 4], [hx + 27, hy + 8]], hk[1]);
    // выбившаяся прядь
    pb.pl([[hx + 3, hy + 14], [hx + 2, hy + 20], [hx + 3, hy + 24]], hk[2]);
  }
  const bust = buildBust({
    EMO, seed: 7,
    fidget(t) { return sched(t, 8, 1.1, 7) >= 0 ? { id: 'gl' } : null; },
    paint(pb, emo, e, eyes, mouth, br, af, fd) {
      const hy = HY - br;
      hair(pb, HX, hy, true);
      body(pb, br);
      head(pb, HX, hy, S, { eyes: eyes, brows: e.brows, mouth: mouth });
      hair(pb, HX, hy, false);
      glasses(pb, HX, hy, R.gold[2], P.white, { dy: 1 });
      if (fd) glassesPush(pb, HX, hy, sk, tl, 3);
    },
  });
  G.Cast.register('clerk', { name: 'Нора Пак', voice: 'high', emotions: ['normal'], anims: {}, bust: bust, iso: null });
})();

/* =====================================================================
   BAILIFF — Джо Бэнкс, помощник шерифа округа Лос-Анджелес
   ===================================================================== */
(function () {
  const sk = R.skinD, st = R.stone, gr = R.green;
  const S = { skin: sk, iris: [R.hairBrown[0], R.hairBrown[2]], brow: R.hairBlack[0], brow2: R.hairBlack[1], prof: 'o', age: 1,
    eyeKey: { W: R.neutral[7], w: R.neutral[5], H: R.neutral[8] } };
  const HX = 58, HY = 12;
  const EMO = { normal: { eyes: 'open', brows: 'stern', mouth: 'closed' } };
  function body(pb, br) {
    neck(pb, sk, br);
    const by = -br;
    const m = mPoly(pb, [[22, 136], [24, 100], [26, 74], [32, 64 + by], [46, 58 + by], [62, 54 + by], [84, 52 + by], [106, 56 + by], [118, 62 + by], [124, 74], [126, 100], [128, 136]]);
    shade(pb, m, st, 3, { hi: 1, lo: 3, splitFn: y => 104 + (y - 60) * 0.1 });
    // рукава: границы
    pb.pl([[108, 62 + by], [110, 84], [108, 136]], st[1]);
    pb.pl([[34, 70], [32, 100], [32, 136]], st[2]);
    // воротник + тёмно-зелёный галстук
    pb.map([
      'kkkk.........kkkk',
      'k5544.......k4443',
      '.k5443.....k4433k',
      '..k4433...k4332k.',
      '...kk43k.k332kk..',
      '.....kk...kk.....'], { k: st[1], 5: st[5], 4: st[4], 3: st[3], 2: st[2] }, 62, 50 + by);
    const tie = mPoly(pb, [[69, 55 + by], [76, 55 + by], [75, 60 + by], [77, 96], [73, 101], [69, 96], [71, 60 + by]]);
    shade(pb, tie, gr, 2, { hi: 1, lo: 1 });
    pb.rect(70, 55 + by, 6, 4, gr[3]);
    pb.rect(70, 78, 6, 2, R.gold[3]); // зажим
    // планка с пуговицами
    pb.pl([[80, 60], [81, 136]], st[2]);
    for (let y = 106; y < 136; y += 12) pb.map(['.k.', 'kbk', '.k.'], { k: st[1], b: st[4] }, 80, y);
    // карманы с клапанами
    const pk = (x) => {
      const f = mPoly(pb, [[x, 78], [x + 18, 77], [x + 18, 84], [x + 9, 86], [x, 84]]);
      shade(pb, f, st, 3, { hi: 1, lo: 1, bot: 1 });
      pb.pl([[x, 85], [x + 9, 87], [x + 18, 85]], st[1]);
      pb.pl([[x + 1, 88], [x + 1, 100], [x + 17, 100], [x + 17, 88]], st[2]);
      pb.map(['.k.', 'kbk', '.k.'], { k: st[1], b: st[4] }, x + 8, 82);
    };
    pk(44); pk(86);
    // звезда шерифа на левой груди (у нас — справа на экране)
    pb.map([
      '....k....',
      '...kGk...',
      'kkkGHGkkk',
      '.kGGHGGk.',
      '..kGgGk..',
      '.kGgkgGk.',
      '.kgk.kgk.',
      '.kk...kk.'], { k: R.gold[1], G: R.gold[3], H: R.gold[5], g: R.gold[2] }, 90, 66);
    // табличка с именем
    pb.rect(48, 73, 12, 3, R.gold[3]); pb.line(48, 75, 59, 75, R.gold[1]); pb.line(49, 74, 57, 74, R.gold[2]);
    // нашивка на рукаве (ближнем)
    pb.map([
      '.kkkkkk.',
      'kggGGggk',
      'kgYYYYgk',
      'kgYggYgk',
      'kgYYYYgk',
      'kggggggk',
      '.kggggk.',
      '..kkkk..'], { k: gr[0], g: gr[2], G: gr[4], Y: R.gold[4] }, 112, 70);
    // эполеты
    pb.pl([[90, 54 + by], [106, 57 + by]], st[1]);
    pb.pl([[48, 58 + by], [36, 64 + by]], st[1]);
    // ремень внизу
    pb.rect(24, 130, 104, 6, R.neutral[1]);
    pb.line(24, 130, 127, 130, R.neutral[3]);
    pb.rect(70, 130, 8, 6, R.gold[3]);
  }
  const bust = buildBust({
    EMO, seed: 9,
    fidget(t) { return sched(t, 7.5, 2.4, 9) >= 0 ? { id: 'sh' } : null; },
    paint(pb, emo, e, eyes, mouth, br, af, fd) {
      const hy = HY - br + (fd ? 1 : 0);
      body(pb, br);
      head(pb, HX, hy, S, { eyes: eyes, brows: e.brows, mouth: mouth });
      // бритая голова: щетина-дизеринг и блик на макушке
      for (let y = 0; y < 14; y++) for (let x = 4; x < 32; x++) {
        const c = pb.get(HX + x, hy + y);
        if (c && c !== sk[4] && x > 18 && G.bayer(x * 3 + y, y * 5 + x) < 2) pb.set(HX + x, hy + y, sk[2]);
      }
      pb.pl([[HX + 9, hy + 3], [HX + 13, hy + 1], [HX + 18, hy]], sk[4]);
      pb.pl([[HX + 8, hy + 5], [HX + 11, hy + 3]], sk[4]);
      // усы-щетина
      pb.line(HX + 8, hy + 29, HX + 14, hy + 29, sk[1]);
    },
  });
  G.Cast.register('bailiff', { name: 'Пристав Бэнкс', voice: 'low', emotions: ['normal'], anims: {}, bust: bust, iso: null });
})();

/* =====================================================================
   FOREPERSON — старшина присяжных
   ===================================================================== */
(function () {
  const sk = R.skinL, hg = R.hairGrey, cd = R.stone;
  const S = { skin: sk, iris: [R.blue[2], R.blue[3]], brow: hg[1], brow2: hg[2], prof: 'f', age: 2, lipLow: R.red[4] };
  const HX = 58, HY = 13;
  const EMO = { normal: { eyes: 'open', brows: 'n', mouth: 'closed' } };
  function body(pb, br) {
    neck(pb, sk, br, true);
    const by = -br;
    const m = mPoly(pb, [[30, 136], [32, 100], [34, 78], [40, 68 + by], [50, 60 + by], [62, 56 + by], [84, 54 + by], [102, 58 + by], [110, 64 + by], [114, 76], [116, 100], [118, 136]]);
    shade(pb, m, cd, 4, { hi: 1, lo: 3, splitFn: y => 96 + (y - 60) * 0.1 });
    for (let y = 70; y < 136; y++) for (let x = 34; x < 116; x++) if (m[y * pb.w + x] && ((x + y) % 5 === 0) && pb.get(x, y) === cd[4]) pb.set(x, y, cd[3]);
    // блузка в мелкий цветочек
    const bl = mPoly(pb, [[62, 56 + by], [82, 54 + by], [78, 136], [64, 136]]);
    shade(pb, bl, R.blue, 5, { hi: 1, lo: 1 });
    for (let y = 60; y < 136; y += 4) for (let x = 64; x < 80; x += 4) if (bl[y * pb.w + x + ((y >> 2) & 1) * 2]) pb.set(x + ((y >> 2) & 1) * 2, y, R.blue[6]);
    pb.pl([[62, 56 + by], [65, 136]], cd[2]); pb.pl([[82, 54 + by], [78, 136]], cd[2]);
    for (let y = 80; y < 136; y += 13) pb.map(['.k.', 'kbk', '.k.'], { k: R.wood[2], b: R.wood[4] }, 79, y);
    // листок с вердиктом
    const f = mPoly(pb, [[40, 112], [80, 108], [82, 136], [42, 136]]);
    shade(pb, f, R.paper, 3, { hi: 1, lo: 1 });
    for (let y = 116; y < 134; y += 3) pb.line(46, y, 74, y - 2, R.paper[1]);
    hand(pb, 'flat', 36, 118, sk, false);
    hand(pb, 'flat', 74, 116, sk, true);
  }
  function hair(pb, hx, hy) {
    // короткие седые кудри
    const polys = [[[0, 14], [2, 5], [8, -1], [18, -3], [28, -1], [35, 6], [37, 16], [35, 26], [30, 30], [27, 20], [24, 13], [16, 9], [8, 10], [4, 14]]];
    const m = hairShape(pb, hx, hy, polys, hg, { base: 3 });
    // кудри — колечки
    const rnd = G.rng(77);
    for (let i = 0; i < 46; i++) {
      const X = hx + Math.floor(rnd() * 38), Y = hy - 3 + Math.floor(rnd() * 32);
      if (!m[Y * pb.w + X]) continue;
      pb.map(['.44.', '4332', '3..2', '.21.'], { 4: hg[4], 3: hg[3], 2: hg[2], 1: hg[1] }, X - 1, Y - 1);
    }
    // контур кудрей по краю — неровный

  }
  const bust = buildBust({
    EMO, seed: 11,
    fidget(t) { return sched(t, 10, 1.2, 11) >= 0 ? { id: 'gl' } : null; },
    paint(pb, emo, e, eyes, mouth, br, af, fd) {
      const hy = HY - br;
      body(pb, br);
      head(pb, HX, hy, S, { eyes: eyes, brows: e.brows, mouth: mouth });
      hair(pb, HX, hy);
      glasses(pb, HX, hy, R.red[2], P.white);
      pb.pl([[HX + 25, hy + 19], [HX + 27, hy + 30], [HX + 26, hy + 40]], R.gold[3]);
      if (fd) glassesPush(pb, HX, hy, sk, cd, 4);
    },
  });
  G.Cast.register('foreperson', { name: 'Старшина присяжных', voice: 'mid', emotions: ['normal'], anims: {}, bust: bust, iso: null });
})();

/* =====================================================================
   ИЗОМЕТРИЯ: параметрические фигурки ~14×28 (стоя), сидя ~16 px верха.
   Реакции толпы o.react / o.reactT, жесты, анимации судьи.
   ===================================================================== */
function hashStr(s) { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return (h >>> 0); }
const IW = 32, IH = 44, IFX = 16, IFY = 42; // буфер и точка ступней
const ISO_DEF = {};
/* описание: skin, hair (рампа), hs (стиль), coat [ramp, base], shirt, tie, pants, shoes, extra{} */
function isoDef(id, d) { ISO_DEF[id] = d; }

function isoPaint(pb, d, st) {
  // st: {sit, dy(подпрыгивание), hx(смещение головы), arms:[far,near] точки кистей или null, eyes:'n'|'wide'|'closed'|'side', mouth:0|1|2, red, prop}
  const sk = st.red ? [R.red[2], R.red[3], R.red[4], R.red[5], R.red[5]] : d.skin;
  const cr = d.coat[0], cb = d.coat[1];
  const sit = st.sit;
  const by = (sit ? 8 : 0) + (st.dy || 0); // смещение верха вниз при сидении
  const bob = st.bob || 0;
  const T = by + bob; // для верха тела
  const hx = st.hx || 0;
  // --- ноги ---
  if (!sit) {
    const pc = d.pants;
    if (d.skirt) {
      const sm = mPoly(pb, [[11, 29 + T - bob], [21, 29 + T - bob], [22, 35], [10, 35]]);
      shade(pb, sm, d.skirt[0], d.skirt[1], { hi: 1, lo: 1 });
      pb.rect(12, 35, 2, 1, sk[2]); pb.rect(18, 35, 2, 1, sk[2]);
    } else if (!d.robe) {
      pb.rect(12, 29, 4, 7, pc[2]); pb.rect(17, 29, 4, 7, pc[1]);
      pb.rect(12, 29, 1, 7, pc[3]); pb.rect(16, 30, 1, 6, pc[0]);
    }
    const sh = d.shoes || R.neutral[1];
    pb.rect(11, 36, 5, 2, sh); pb.rect(17, 36, 4, 2, sh); pb.set(11, 36, R.neutral[3]);
  } else {
    // колени/бёдра вперёд-влево
    const pc = d.skirt ? d.skirt[0] : d.pants;
    pb.rect(9, 36, 11, 3, pc[d.skirt ? d.skirt[1] : 2]); pb.rect(9, 36, 11, 1, pc[d.skirt ? d.skirt[1] + 1 : 3]);
    pb.rect(16, 39, 5, 2, pc[1]);
  }
  // --- корпус ---
  const ty = 19 + T;
  const len = sit ? 10 : 10;
  const tm = mPoly(pb, [[11, ty + 1], [13, ty], [19, ty], [21, ty + 1], [21, ty + len], [11, ty + len]]);
  shade(pb, tm, cr, cb, { hi: 1, lo: 2, split: 18 });
  if (d.robe && !sit) { const rm = mPoly(pb, [[11, ty + 6], [21, ty + 6], [22, 37], [10, 37]]); shade(pb, rm, cr, cb, { hi: 1, lo: 2, split: 18 }); pb.line(14, ty + 10, 14, 36, cr[cb - 1]); }
  if (d.shirt) { pb.rect(14, ty, 3, 4, d.shirt); pb.set(15, ty + 4, d.shirt); }
  if (d.tie) { pb.set(15, ty + 1, d.tie); pb.set(15, ty + 2, d.tie); pb.set(15, ty + 3, d.tie); }
  if (d.badge) pb.set(18, ty + 3, R.gold[4]);
  if (d.belt) pb.rect(11, ty + 8, 10, 1, d.belt);
  if (d.stripe) for (let y = ty + 2; y < ty + len; y += 2) pb.line(11, y, 20, y, d.stripe);
  // шея
  pb.rect(14, ty - 1, 3, 1, sk[1]);
  // --- голова ---
  const hy = 11 + T, hX = 13 + hx;
  const hm = mPoly(pb, [[hX, hy + 1], [hX + 1, hy], [hX + 6, hy], [hX + 7, hy + 1], [hX + 7, hy + 5], [hX + 5, hy + 7], [hX + 2, hy + 7], [hX, hy + 5]]);
  pb.fill(hm, sk[3]);
  pb.rect(hX + 5, hy + 1, 2, 5, sk[2]); pb.set(hX + 4, hy + 6, sk[2]); pb.set(hX + 1, hy + 2, sk[4]); pb.set(hX + 2, hy + 1, sk[4]);
  pb.set(hX + 6, hy + 3, sk[1]); // ухо
  // глаза
  const ec = R.neutral[0];
  const ex = hX + 1 + (st.look || 0);
  if (st.eyes === 'closed') { pb.set(ex, hy + 4, sk[1]); pb.set(ex + 3, hy + 4, sk[1]); }
  else if (st.eyes === 'wide') { pb.set(ex, hy + 3, P.white); pb.set(ex, hy + 4, ec); pb.set(ex + 3, hy + 3, P.white); pb.set(ex + 3, hy + 4, ec); }
  else { pb.set(ex, hy + 4, ec); pb.set(ex + 3, hy + 4, ec); }
  // рот
  if (st.mouth === 2) { pb.set(hX + 2, hy + 6, R.red[1]); pb.set(hX + 2, hy + 5, R.red[1]); }
  else if (st.mouth === 1) pb.set(hX + 2, hy + 6, R.red[1]);
  else if (d.lips) pb.set(hX + 2, hy + 6, d.lips);
  if (d.beard) { pb.rect(hX + 1, hy + 6, 5, 2, d.beard); pb.set(hX + 2, hy + 6, st.mouth ? R.red[1] : d.beard); pb.rect(hX + 4, hy + 5, 2, 1, d.beard); }
  if (d.mustache) pb.line(hX + 1, hy + 5, hX + 3, hy + 5, d.mustache);
  // волосы
  const hr = d.hair, hs = d.hs;
  if (hr) {
    if (hs === 'short' || hs === 'side' || hs === 'curly' || hs === 'bun' || hs === 'bob' || hs === 'long' || hs === 'grey' || hs === 'pony') {
      pb.rect(hX, hy - 1, 8, 2, hr[2]); pb.rect(hX + 4, hy + 1, 4, 2, hr[2]); pb.rect(hX + 6, hy + 3, 2, 2, hr[1]);
      pb.line(hX + 1, hy - 1, hX + 4, hy - 1, hr[3]);
      if (hs === 'side') { pb.rect(hX, hy + 1, 3, 1, hr[2]); pb.set(hX, hy + 2, hr[2]); }
      if (hs === 'curly') { pb.set(hX - 1, hy, hr[2]); pb.set(hX + 8, hy + 1, hr[2]); pb.set(hX + 2, hy - 2, hr[2]); pb.set(hX + 5, hy - 2, hr[2]); pb.set(hX + 3, hy, hr[1]); pb.set(hX + 6, hy, hr[1]); }
      if (hs === 'bun') { pb.rect(hX + 6, hy - 2, 3, 3, hr[2]); pb.set(hX + 7, hy - 2, hr[3]); }
      if (hs === 'bob') { pb.rect(hX + 5, hy + 1, 3, 6, hr[2]); pb.rect(hX, hy + 1, 1, 4, hr[2]); pb.set(hX + 7, hy + 6, hr[1]); }
      if (hs === 'long') { pb.rect(hX + 5, hy + 1, 3, 9, hr[2]); pb.rect(hX + 7, hy + 4, 1, 6, hr[1]); pb.rect(hX, hy + 1, 1, 5, hr[2]); }
      if (hs === 'pony') { pb.rect(hX + 7, hy + 1, 2, 2, hr[2]); pb.rect(hX + 8, hy + 3, 1, 4, hr[2]); }
    } else if (hs === 'bald') {
      pb.rect(hX + 4, hy + 2, 3, 2, hr[2]); pb.set(hX + 6, hy + 4, hr[1]);
    } else if (hs === 'shaved') {
      pb.set(hX + 2, hy, sk[4]);
    }
  }
  if (d.cap) { pb.rect(hX, hy - 2, 8, 3, d.cap[2]); pb.rect(hX - 2, hy + 1, 4, 1, d.cap[1]); pb.line(hX + 1, hy - 2, hX + 4, hy - 2, d.cap[3]); }
  if (d.hat) { pb.rect(hX - 1, hy - 1, 10, 1, d.hat[1]); pb.rect(hX + 1, hy - 4, 6, 3, d.hat[2]); pb.line(hX + 1, hy - 2, hX + 6, hy - 2, d.hat[0]); }
  if (d.veil) { pb.rect(hX - 1, hy - 1, 9, 2, d.veil); pb.rect(hX + 6, hy + 1, 2, 7, d.veil); }
  if (d.glasses) { pb.set(ex, hy + 4, d.glasses); pb.set(ex + 1, hy + 4, d.glasses); pb.set(ex + 3, hy + 4, d.glasses); pb.set(ex + 2, hy + 4, d.glasses); pb.set(ex + 3, hy + 3, P.white); }
  // --- руки ---
  const sh = [[11, ty + 1], [20, ty + 1]];
  const arms = st.arms || [[10, ty + 8], [21, ty + 8]];
  for (let i = 0; i < 2; i++) {
    const a = arms[i]; if (!a) continue;
    const s0 = sh[i];
    const col = cr[i === 0 ? cb : cb - 1];
    pb.line(s0[0], s0[1], a[0], a[1] - 1, col);
    pb.line(s0[0] + (i ? 1 : -1), s0[1] + 1, a[0] + (i ? 1 : -1), a[1] - 1, col);
    pb.rect(a[0], a[1] - 1, 2, 2, d.skin[3]);
    pb.set(a[0] + 1, a[1], d.skin[2]);
  }
  // реквизит
  if (st.prop === 'notepad') { pb.rect(12, ty + 6, 4, 3, R.paper[4]); pb.line(12, ty + 7, 15, ty + 7, R.paper[1]); }
  if (st.prop === 'sketch') { pb.rect(10, ty + 4, 6, 5, R.wood[4]); pb.rect(11, ty + 5, 4, 3, R.paper[4]); pb.set(12, ty + 6, R.neutral[3]); }
  if (st.prop === 'steno') { pb.rect(10, ty + 8, 8, 3, R.neutral[2]); pb.line(10, ty + 8, 17, ty + 8, R.neutral[4]); pb.rect(11, ty + 11, 1, 3, R.neutral[1]); pb.rect(11, ty + 7, 5, 1, R.paper[4]); }
  if (st.gavel) {
    const g = st.gavel; // [x,y,'up'|'down']
    if (g[2] === 'up') { pb.line(g[0], g[1], g[0] + 2, g[1] - 4, R.wood[4]); pb.rect(g[0] + 1, g[1] - 7, 4, 2, R.wood[3]); }
    else { pb.line(g[0], g[1], g[0] - 4, g[1], R.wood[4]); pb.rect(g[0] - 6, g[1] - 2, 2, 4, R.wood[3]); pb.line(g[0] - 9, g[1] + 3, g[0] - 7, g[1] + 2, P.white); pb.line(g[0] - 3, g[1] + 3, g[0] - 1, g[1] + 2, P.white); }
  }
}

function isoState(id, d, o) {
  const t = o.t || 0, h = hashStr(id), ph = (h % 1000) / 1000;
  const sit = o.pose === 'sit';
  const st = { sit: sit, eyes: 'n', mouth: 0, bob: 0, look: 0 };
  // дыхание/покачивание (2 кадра), своя фаза
  const per = 2.6 + (h % 7) * 0.2;
  st.bob = ((t / per + ph) % 1) < 0.5 ? 0 : 1;
  // моргание
  const bp = 3.3 + (h % 5) * 0.3;
  if (((t + ph * 7) % bp) < 0.14) st.eyes = 'closed';
  // изредка поворот головы / взгляд
  const lp = 7 + (h % 9);
  const lph = ((t + ph * 13) % lp);
  if (lph < 1.4) st.look = (h & 1) ? 1 : 0;
  const ty = 19 + (sit ? 8 : 0);
  const R2 = (n) => Math.floor((o.reactT !== undefined ? o.reactT : t) * n);
  let key = '';
  if (o.react) {
    const rt = o.reactT !== undefined ? o.reactT : t;
    switch (o.react) {
      case 'whisper': st.hx = -1; st.arms = [[10, ty + 8], [13, ty - 3]]; st.mouth = R2(6) % 2; st.bob = 1; break;
      case 'gasp': st.arms = [[12, ty - 3], [19, ty - 3]]; st.eyes = 'wide'; st.mouth = 2; st.dy = (rt < 0.25) ? -1 : 0; break;
      case 'murmur': st.hx = (R2(4) % 2) ? -1 : 0; st.mouth = R2(5) % 2; break;
      case 'angry': st.red = true; st.arms = [[10, ty + 8], [22, ty - 8]]; st.mouth = 2; st.dy = R2(10) % 2 ? 0 : -1; st.hx = R2(10) % 2; break;
      case 'cheer': st.arms = [[8, ty - 9], [23, ty - 9]]; st.mouth = 2; st.dy = R2(4) % 2 ? -2 : 0; st.eyes = 'closed'; break;
      case 'clap': st.arms = R2(8) % 2 ? [[14, ty + 3], [16, ty + 3]] : [[12, ty + 3], [19, ty + 3]]; st.mouth = 1; break;
      case 'laugh': st.eyes = 'closed'; st.mouth = 2; st.dy = R2(10) % 2 ? -1 : 0; st.arms = [[13, ty + 7], [19, ty + 7]]; break;
      case 'shout': st.mouth = 2; st.arms = [[10, ty + 8], [12, ty - 2]]; st.dy = R2(6) % 2 ? -1 : 0; st.eyes = 'wide'; break;
    }
    key = o.react + '|' + st.mouth + st.hx + st.dy + st.eyes + (st.arms ? st.arms.join() : '');
  } else if (o.anim === 'gavel' && id === 'judge') {
    const a = o.animT || 0;
    if (a < 0.9) {
      if (a < 0.4) st.gavel = [21, ty - 6, 'up'], st.arms = [[10, ty + 8], [21, ty - 6]];
      else if (a < 0.65) { st.gavel = [16, ty + 6, 'down']; st.arms = [[10, ty + 8], [16, ty + 6]]; }
      else st.gavel = [20, ty + 2, 'up'], st.arms = [[10, ty + 8], [20, ty + 2]];
      key = 'gv' + st.gavel.join();
    }
  } else if (o.talking) {
    const f = Math.floor(t * 4 + ph * 4) % 4;
    st.mouth = Math.floor(t * 8) % 2 ? 1 : 0;
    st.arms = f < 2 ? [[10, ty + 8], [22, ty + 3]] : [[10, ty + 8], [20, ty + 5]];
    key = 'tk' + f;
  } else if (d.idle) {
    const r = d.idle(t, ph, ty, st); if (r) key = r;
  }
  return { st, key: key + '|' + st.bob + st.eyes + st.look + st.mouth };
}
function isoDraw(id) {
  const cache = {};
  return function (ctx, x, y, o) {
    const d = ISO_DEF[id];
    const { st, key } = isoState(id, d, o);
    const k = (o.pose === 'sit' ? 's' : 'S') + key;
    let spr = cache[k];
    if (!spr) {
      const pb = new PB(IW, IH);
      isoPaint(pb, d, st);
      pb.outline();
      spr = cache[k] = pb.toCanvas();
    }
    G.blit(ctx, spr, x - IFX, y - IFY, o.dir === 'r');
  };
}
/* у кого есть привычное занятие на холостом ходу */
function writeIdle(prop) {
  return function (t, ph, ty, st) {
    const p = (t * 0.13 + ph) % 1;
    if (p < 0.35) { st.prop = prop; const f = Math.floor(t * 5) % 2; st.arms = [[12, ty + 7], [15 + f, ty + 6]]; st.look = 0; return 'wr' + f; }
    return null;
  };
}
const SK = [R.skinL, R.skinM, R.skinD];
isoDef('player', { skin: R.skinL, hair: R.hairBrown, hs: 'side', coat: [R.blue, 3], shirt: R.neutral[8], tie: R.red[3], pants: R.blue, badge: 1 });
isoDef('judge', { skin: R.skinL, hair: R.hairGrey, hs: 'bald', coat: [R.neutral, 2], shirt: R.neutral[8], tie: R.carpet[2], pants: R.neutral, robe: 1, glasses: R.neutral[5] });
isoDef('prosecutor', { skin: R.skinL, hair: R.hairBlack, hs: 'bob', coat: [R.neutral, 5], shirt: R.neutral[8], pants: R.neutral, skirt: [R.neutral, 4], lips: R.red[3], shoes: R.neutral[0] });
isoDef('clerk', { skin: R.skinL, hair: R.hairBlack, hs: 'bun', coat: [R.teal, 3], shirt: R.neutral[8], pants: R.neutral, skirt: [R.neutral, 3], glasses: R.gold[3], idle: writeIdle('notepad') });
isoDef('bailiff', { skin: R.skinD, hair: R.skinD, hs: 'shaved', coat: [R.stone, 3], tie: R.green[2], pants: R.green, badge: 1, belt: R.neutral[1] });
isoDef('juror1', { skin: R.skinL, hair: R.hairBlond, hs: 'long', coat: [R.red, 3], shirt: R.neutral[8], pants: R.carpet, skirt: [R.carpet, 2], lips: R.red[3] });
isoDef('juror2', { skin: R.skinD, hair: R.hairBlack, hs: 'short', coat: [R.green, 3], shirt: R.neutral[7], pants: R.stone, beard: R.hairBlack[1] });
isoDef('juror3', { skin: R.skinM, hair: R.hairBlack, hs: 'pony', coat: [R.purple, 3], shirt: R.neutral[8], pants: R.neutral, skirt: [R.neutral, 3] });
isoDef('juror4', { skin: R.skinL, hair: R.hairGrey, hs: 'bald', coat: [R.wood, 3], shirt: R.neutral[8], tie: R.blue[3], pants: R.wood, glasses: R.neutral[2], mustache: R.hairGrey[2] });
isoDef('juror5', { skin: R.skinL, hair: R.hairRed, hs: 'curly', coat: [R.blue, 4], shirt: R.paper[4], pants: R.blue, stripe: R.blue[3] });
isoDef('juror6', { skin: R.skinM, hair: R.hairBrown, hs: 'short', coat: [R.gold, 3], shirt: R.neutral[8], pants: R.carpet, cap: null, glasses: R.neutral[1] });
isoDef('foreperson', { skin: R.skinL, hair: R.hairGrey, hs: 'curly', coat: [R.stone, 4], shirt: R.blue[5], pants: R.wood, skirt: [R.wood, 3], glasses: R.red[2], idle: writeIdle('notepad') });
isoDef('reporter', { skin: R.skinM, hair: R.hairBrown, hs: 'bun', coat: [R.carpet, 3], shirt: R.neutral[8], pants: R.neutral, skirt: [R.neutral, 2], glasses: R.neutral[1],
  idle(t, ph, ty, st) { st.prop = 'steno'; const f = Math.floor(t * 9) % 3; st.arms = [[11 + (f === 1 ? 1 : 0), ty + 7], [15 + (f === 2 ? 1 : 0), ty + 7]]; st.look = 0; return 'ty' + f; } });
// зрители
isoDef('spectator1', { skin: R.skinL, hair: R.hairBrown, hs: 'short', coat: [R.stone, 2], shirt: R.neutral[8], pants: R.neutral, hat: R.wood, idle: writeIdle('notepad') }); // репортёр
isoDef('spectator2', { skin: R.skinM, hair: R.hairBlack, hs: 'long', coat: [R.neutral, 3], shirt: R.red[3], pants: R.neutral, idle: writeIdle('sketch') }); // художник
isoDef('spectator3', { skin: R.skinL, hair: R.hairGrey, hs: 'bald', coat: [R.wood, 2], shirt: R.neutral[8], tie: R.green[3], pants: R.wood, glasses: R.neutral[2], mustache: R.hairGrey[3] }); // пожилой муж
isoDef('spectator4', { skin: R.skinL, hair: R.hairGrey, hs: 'curly', coat: [R.purple, 4], shirt: R.neutral[8], pants: R.neutral, skirt: [R.purple, 2], glasses: R.gold[3] }); // пожилая жена
isoDef('spectator5', { skin: R.skinD, hair: R.hairBlack, hs: 'curly', coat: [R.red, 4], shirt: R.neutral[8], pants: R.carpet, stripe: R.red[3] }); // студент
isoDef('spectator6', { skin: R.skinL, hair: R.hairBlond, hs: 'pony', coat: [R.teal, 4], shirt: R.neutral[8], pants: R.carpet, glasses: R.neutral[1] }); // студентка
isoDef('spectator7', { skin: R.skinL, hair: R.hairBlack, hs: 'bob', coat: [R.neutral, 1], shirt: R.neutral[2], pants: R.neutral, skirt: [R.neutral, 1], veil: R.neutral[1] }); // родственница в трауре
isoDef('spectator8', { skin: R.skinM, hair: R.hairBlack, hs: 'short', coat: [R.neutral, 1], shirt: R.neutral[8], tie: R.neutral[0], pants: R.neutral }); // родственник в трауре
isoDef('spectator9', { skin: R.skinL, hair: R.hairBrown, hs: 'short', coat: [R.green, 2], shirt: R.neutral[7], pants: R.blue, cap: R.red, beard: R.hairBrown[2] }); // мужчина в кепке
isoDef('spectator10', { skin: R.skinD, hair: R.hairBlack, hs: 'long', coat: [R.gold, 4], shirt: R.neutral[8], pants: R.neutral, skirt: [R.carpet, 3], lips: R.red[3] });
isoDef('spectator11', { skin: R.skinL, hair: R.hairRed, hs: 'side', coat: [R.blue, 2], shirt: R.neutral[8], tie: R.gold[3], pants: R.neutral }); // юрист-стажёр
isoDef('spectator12', { skin: R.skinM, hair: R.hairGrey, hs: 'short', coat: [R.stone, 3], shirt: R.neutral[7], pants: R.stone, hat: R.neutral, beard: R.hairGrey[3] });
for (const id in ISO_DEF) {
  const iso = { draw: isoDraw(id) };
  if (G.Cast.defs[id]) G.Cast.defs[id].iso = iso;
  else G.Cast.register(id, {
    name: { reporter: 'Стенографистка' }[id] || (id.startsWith('juror') ? 'Присяжный №' + id.slice(5) : 'Зритель'),
    voice: 'mid', emotions: [], anims: id === 'judge' ? { gavel: 0.9 } : {}, iso: iso,
  });
}
/* =====================================================================
   ИКОНКИ УЛИК: G.Icons.draw (32×32) и G.Icons.drawBig (64×64).
   Каждая иконка рисуется функцией f(pb, k, big): координаты в 32-сетке × k,
   линии и детали — 1 px, у большой версии дополнительные детали (текстуры, текст-полоски).
   ===================================================================== */
const IC = {};
function icon(id, f) { IC[id] = f; }
function mk(k) {
  const u = v => Math.round(v * k);
  return {
    u,
    box(pb, x, y, w, h, ramp, base, o) { const m = mPoly(pb, [[u(x), u(y)], [u(x + w), u(y)], [u(x + w), u(y + h)], [u(x), u(y + h)]]); shade(pb, m, ramp, base, o || { hi: 1, lo: 1, bot: 1 }); return m; },
    poly(pb, pts, ramp, base, o) { const m = mPoly(pb, pts.map(p => [u(p[0]), u(p[1])])); shade(pb, m, ramp, base, o || { hi: 1, lo: 1, bot: 1 }); return m; },
    ell(pb, cx, cy, rx, ry, ramp, base, o) { const m = mEll(pb, u(cx), u(cy), Math.max(1, u(rx)), Math.max(1, u(ry))); shade(pb, m, ramp, base, o || { hi: 1, lo: 1, bot: 1 }); return m; },
    line(pb, x0, y0, x1, y1, c) { pb.line(u(x0), u(y0), u(x1), u(y1), c); },
    px(pb, x, y, c) { pb.set(u(x), u(y), c); },
    rect(pb, x, y, w, h, c) { pb.rect(u(x), u(y), Math.max(1, u(w)), Math.max(1, u(h)), c); },
  };
}
/* строки "текста" на бумаге */
function textLines(pb, k, x, y, w, n, step, col, seed) {
  const rnd = G.rng(seed || 7);
  for (let i = 0; i < n; i++) {
    const yy = Math.round((y + i * step) * k);
    let xx = Math.round(x * k); const end = Math.round((x + w) * k) - (i === n - 1 ? Math.round(w * k * 0.4) : 0);
    while (xx < end) { const wl = 1 + Math.floor(rnd() * (k > 1 ? 6 : 3)); pb.line(xx, yy, Math.min(end, xx + wl - 1), yy, col); xx += wl + 1; }
  }
}
const PA = R.paper, NE = R.neutral, WO = R.wood, GO = R.gold;

icon('logbook', (pb, k, big) => {
  const g = mk(k);
  g.box(pb, 5, 4, 22, 25, R.green, 2);
  g.box(pb, 7, 4, 20, 24, PA, 4, { hi: 0, lo: 1 });
  g.box(pb, 5, 4, 4, 25, R.green, 1);
  for (let y = 7; y < 28; y += 4) g.line(pb, 5, y, 8, y, R.green[3]);
  g.box(pb, 12, 8, 12, 5, R.green, 3);
  g.line(pb, 13, 10, 22, 10, GO[4]);
  if (big) { textLines(pb, k, 11, 16, 14, 5, 2, PA[1], 3); g.line(pb, 10, 28, 26, 28, PA[2]); }
  else { g.line(pb, 11, 17, 24, 17, PA[1]); g.line(pb, 11, 20, 22, 20, PA[1]); g.line(pb, 11, 23, 24, 23, PA[1]); }
  g.box(pb, 22, 2, 3, 9, R.red, 3); // закладка
});
icon('photo', (pb, k, big) => {
  const g = mk(k);
  g.poly(pb, [[4, 8], [26, 4], [29, 24], [7, 28]], NE, 9, { hi: 0, lo: 1, bot: 1 });
  g.poly(pb, [[6, 10], [25, 7], [27, 21], [8, 24]], R.blue, 2, { hi: 0, lo: 0 });
  // силуэт фигуры и окна
  g.poly(pb, [[6, 10], [25, 7], [26, 13], [7, 16]], R.blue, 3, { hi: 0, lo: 0 });
  g.ell(pb, 14, 16, 2, 2, NE, 2, { hi: 0, lo: 0 });
  g.poly(pb, [[11, 23], [12, 18], [16, 18], [18, 22]], NE, 2, { hi: 0, lo: 0 });
  g.box(pb, 20, 10, 3, 4, GO, 4, { hi: 0, lo: 0 });
  if (big) { g.line(pb, 8, 24, 27, 21, NE[7]); for (let i = 0; i < 6; i++) g.px(pb, 9 + i * 3, 12 + (i % 2), R.blue[4]); g.box(pb, 12, 2, 7, 3, PA, 2, { hi: 0, lo: 0 }); }
});
icon('document', (pb, k, big) => {
  const g = mk(k);
  g.poly(pb, [[6, 3], [21, 3], [27, 9], [27, 29], [6, 29]], PA, 4, { hi: 0, lo: 1, bot: 1 });
  g.poly(pb, [[21, 3], [27, 9], [21, 9]], PA, 2, { hi: 0, lo: 0 });
  g.line(pb, 9, 7, 18, 7, NE[3]);
  textLines(pb, k, 9, 11, 15, big ? 7 : 5, big ? 2 : 3, PA[1], 11);
  g.ell(pb, 21, 25, 3, 2, R.red, 3, { hi: 0, lo: 0 });
  g.line(pb, 9, 26, 15, 25, P.ink);
});
icon('key', (pb, k, big) => {
  const g = mk(k);
  g.ell(pb, 9, 10, 6, 6, GO, 3);
  g.ell(pb, 9, 10, 2, 2, NE, 3, { hi: 0, lo: 0 });
  pb.set(g.u(9), g.u(10), 0);
  if (big) for (let y = 0; y < 4; y++) for (let x = 0; x < 4; x++) pb.clear(g.u(8) + x, g.u(9) + y);
  g.poly(pb, [[13, 13], [15, 11], [28, 24], [26, 26]], GO, 3);
  g.poly(pb, [[22, 22], [24, 20], [27, 23], [25, 25]], GO, 2);
  g.poly(pb, [[19, 19], [21, 17], [23, 19], [21, 21]], GO, 2);
  g.line(pb, 6, 6, 9, 5, GO[5]);
  g.box(pb, 4, 19, 8, 7, R.paper, 4); g.line(pb, 8, 15, 8, 19, NE[5]);
  if (big) { g.line(pb, 5, 22, 10, 22, P.ink); g.line(pb, 5, 24, 9, 24, P.ink); }
});
icon('coat', (pb, k, big) => {
  const g = mk(k);
  g.poly(pb, [[10, 4], [22, 4], [28, 10], [28, 29], [4, 29], [4, 10]], R.stone, 3);
  g.poly(pb, [[12, 4], [16, 14], [20, 4]], NE, 8, { hi: 0, lo: 0 });
  g.poly(pb, [[10, 4], [16, 18], [13, 20], [8, 9]], R.stone, 4);
  g.poly(pb, [[22, 4], [16, 18], [19, 20], [24, 9]], R.stone, 2);
  g.line(pb, 16, 18, 16, 29, R.stone[1]);
  for (const y of [21, 25]) { g.px(pb, 14, y, WO[2]); g.px(pb, 18, y, WO[2]); }
  g.line(pb, 6, 18, 11, 18, R.stone[1]); g.line(pb, 21, 18, 26, 18, R.stone[1]);
  g.rect(pb, 4, 22, 24, 1, R.stone[1]);
  if (big) { g.line(pb, 7, 12, 6, 28, R.stone[4]); g.line(pb, 25, 12, 26, 28, R.stone[1]); g.ell(pb, 23, 26, 2, 1, R.red, 2, { hi: 0, lo: 0 }); }
});
icon('ticket', (pb, k, big) => {
  const g = mk(k);
  const m = g.poly(pb, [[3, 9], [29, 7], [30, 23], [4, 25]], R.gold, 4, { hi: 1, lo: 1, bot: 1 });
  g.line(pb, 21, 8, 22, 24, R.gold[2]);
  for (let y = 9; y < 24; y += 2) g.px(pb, 21.5, y, 0);
  g.ell(pb, 4, 17, 1, 2, NE, 3, { hi: 0, lo: 0 }); 
  g.line(pb, 6, 12, 18, 11, R.red[2]); g.line(pb, 6, 13, 18, 12, R.red[2]);
  textLines(pb, k, 6, 16, 13, big ? 4 : 2, 3, R.gold[1], 5);
  g.line(pb, 24, 11, 25, 21, R.gold[1]);
});
icon('report', (pb, k, big) => {
  const g = mk(k);
  g.box(pb, 5, 5, 22, 25, R.blue, 4);
  g.box(pb, 7, 3, 21, 25, PA, 4, { hi: 0, lo: 1, bot: 1 });
  g.box(pb, 7, 3, 21, 5, R.blue, 3, { hi: 0, lo: 0 });
  g.ell(pb, 11, 5, 1, 1, GO, 4, { hi: 0, lo: 0 });
  textLines(pb, k, 10, 11, 15, big ? 7 : 4, big ? 2 : 3, PA[1], 13);
  g.box(pb, 18, 21, 8, 5, R.red, 3, { hi: 0, lo: 0 }); // штамп
  if (big) g.line(pb, 19, 23, 24, 23, R.red[5]);
  g.rect(pb, 14, 1, 6, 3, NE[5]);
});
icon('canister', (pb, k, big) => {
  const g = mk(k);
  g.box(pb, 9, 7, 14, 22, R.red, 3, { hi: 2, lo: 2, bot: 1 });
  g.box(pb, 11, 3, 10, 4, NE, 6);
  g.box(pb, 14, 1, 4, 2, NE, 5);
  g.box(pb, 9, 12, 14, 9, NE, 8, { hi: 0, lo: 2 });
  g.line(pb, 11, 15, 20, 15, R.red[2]); g.line(pb, 11, 17, 18, 17, NE[4]);
  g.line(pb, 10, 8, 10, 27, R.red[5]);
  if (big) { textLines(pb, k, 11, 19, 9, 1, 2, NE[4], 2); g.ell(pb, 15.5, 2, 1, 0.5, NE, 3, { hi: 0, lo: 0 }); }
});
icon('video', (pb, k, big) => {
  const g = mk(k);
  g.box(pb, 3, 8, 26, 16, NE, 2);
  g.box(pb, 6, 11, 20, 8, NE, 1, { hi: 0, lo: 0 });
  g.ell(pb, 10, 15, 3, 3, NE, 7); g.ell(pb, 22, 15, 3, 3, NE, 7);
  g.ell(pb, 10, 15, 1, 1, NE, 2, { hi: 0, lo: 0 }); g.ell(pb, 22, 15, 1, 1, NE, 2, { hi: 0, lo: 0 });
  g.box(pb, 13, 13, 6, 4, WO, 1, { hi: 0, lo: 0 });
  g.box(pb, 6, 20, 20, 3, PA, 4, { hi: 0, lo: 0 });
  g.line(pb, 8, 21, 18, 21, P.ink);
});
icon('knife', (pb, k, big) => {
  const g = mk(k);
  g.poly(pb, [[4, 27], [18, 12], [22, 12], [22, 15], [7, 29]], NE, 7, { hi: 1, lo: 1, bot: 1 });
  g.line(pb, 6, 27, 19, 14, NE[9]);
  g.poly(pb, [[19, 10], [24, 15], [23, 16], [18, 11]], NE, 4);
  g.poly(pb, [[22, 13], [27, 6], [30, 9], [24, 15]], WO, 2);
  for (let i = 0; i < 3; i++) g.px(pb, 24 + i * 1.5, 11 - i * 1.5, NE[7]);
  if (big) { g.px(pb, 10, 22, R.red[2]); g.px(pb, 11, 22, R.red[2]); g.px(pb, 9, 24, R.red[2]); g.line(pb, 26, 7, 29, 9, WO[4]); }
});
icon('policy', (pb, k, big) => {
  const g = mk(k);
  g.poly(pb, [[5, 3], [27, 3], [27, 29], [5, 29]], PA, 4, { hi: 0, lo: 1, bot: 1 });
  g.box(pb, 5, 3, 22, 6, R.carpet, 3, { hi: 0, lo: 0 });
  g.poly(pb, [[9, 4], [13, 4], [13, 7], [11, 8], [9, 7]], GO, 4, { hi: 0, lo: 0 });
  g.line(pb, 15, 6, 24, 6, NE[9]);
  textLines(pb, k, 8, 12, 17, big ? 7 : 4, big ? 2 : 3, PA[1], 21);
  g.line(pb, 16, 26, 25, 25, P.ink); g.line(pb, 17, 25, 19, 27, P.ink);
  g.box(pb, 7, 23, 6, 5, GO, 3);
});
icon('map', (pb, k, big) => {
  const g = mk(k);
  const xs = [3, 11, 20, 29];
  for (let i = 0; i < 3; i++) g.poly(pb, [[xs[i], i % 2 ? 5 : 7], [xs[i + 1], i % 2 ? 7 : 5], [xs[i + 1], i % 2 ? 27 : 25], [xs[i], i % 2 ? 25 : 27]], i % 2 ? R.green : R.green, i % 2 ? 4 : 5, { hi: 0, lo: 0 });
  g.line(pb, 4, 20, 13, 14, R.blue[4]); g.line(pb, 13, 14, 28, 18, R.blue[4]);
  g.line(pb, 6, 10, 26, 24, R.stone[5]); g.line(pb, 15, 6, 13, 26, R.stone[5]);
  g.line(pb, 20, 12, 24, 16, R.red[3]); g.line(pb, 24, 12, 20, 16, R.red[3]);
  if (big) { for (let i = 0; i < 8; i++) g.px(pb, 7 + i * 2, 22 - (i % 3), R.red[4]); g.box(pb, 5, 7, 4, 3, NE, 7, { hi: 0, lo: 0 }); }
});
icon('phone', (pb, k, big) => {
  const g = mk(k);
  g.box(pb, 9, 3, 15, 27, NE, 2, { hi: 1, lo: 1, bot: 1 });
  g.box(pb, 10, 6, 13, 20, R.blue, 3, { hi: 0, lo: 0 });
  g.poly(pb, [[10, 6], [16, 6], [10, 14]], R.blue, 4, { hi: 0, lo: 0 });
  g.line(pb, 14, 4, 18, 4, NE[4]);
  g.ell(pb, 16.5, 28, 1, 1, NE, 4, { hi: 0, lo: 0 });
  g.line(pb, 12, 12, 21, 21, NE[8]); g.line(pb, 12, 13, 18, 19, NE[6]); // трещина
  if (big) { g.box(pb, 11, 8, 10, 3, R.green, 4, { hi: 0, lo: 0 }); textLines(pb, k, 12, 13, 9, 3, 2, R.blue[5], 4); }
});
icon('receipt', (pb, k, big) => {
  const g = mk(k);
  const m = g.poly(pb, [[9, 2], [23, 2], [23, 30], [9, 30]], NE, 9, { hi: 0, lo: 1 });
  for (let x = 9; x < 23; x += 2) { g.px(pb, x, 30, 0); g.px(pb, x + 1, 29.6, 0); }
  g.line(pb, 11, 5, 21, 5, NE[3]);
  textLines(pb, k, 11, 9, 10, big ? 8 : 5, big ? 2 : 3, NE[5], 31);
  g.line(pb, 11, 24, 21, 24, NE[5]);
  g.line(pb, 16, 26, 21, 26, NE[2]);
});
icon('badge', (pb, k, big) => {
  const g = mk(k);
  g.box(pb, 4, 6, 24, 20, WO, 1);
  const pts = []; for (let i = 0; i < 12; i++) { const a = -Math.PI / 2 + i * Math.PI / 6, r = i % 2 ? 4.5 : 9; pts.push([16 + Math.cos(a) * r, 16 + Math.sin(a) * r]); }
  g.poly(pb, pts, GO, 3, { hi: 1, lo: 1, bot: 1 });
  g.ell(pb, 16, 16, 3, 3, GO, 4);
  g.px(pb, 16, 16, GO[2]);
  for (const p of pts.filter((_, i) => !(i % 2))) g.px(pb, p[0], p[1], GO[5]);
  if (big) { g.line(pb, 13, 13, 19, 13, GO[2]); g.line(pb, 13, 19, 19, 19, GO[2]); }
});
icon('letter', (pb, k, big) => {
  const g = mk(k);
  g.box(pb, 3, 8, 26, 18, PA, 4, { hi: 0, lo: 1, bot: 1 });
  g.line(pb, 3, 8, 16, 18, PA[1]); g.line(pb, 29, 8, 16, 18, PA[1]);
  g.line(pb, 3, 26, 13, 17, PA[2]); g.line(pb, 29, 26, 19, 17, PA[2]);
  g.ell(pb, 16, 18, 3, 3, R.red, 3);
  g.box(pb, 22, 10, 5, 5, R.blue, 4, { hi: 0, lo: 0 });
  if (big) { g.line(pb, 6, 22, 12, 22, P.ink); g.line(pb, 6, 24, 10, 24, P.ink); g.px(pb, 16, 18, R.red[5]); }
});
icon('fingerprint', (pb, k, big) => {
  const g = mk(k);
  g.box(pb, 4, 3, 24, 27, PA, 4, { hi: 0, lo: 1, bot: 1 });
  const cx = g.u(16), cy = g.u(15);
  for (let r = 2; r < 10; r += big ? 1 : 2) {
    for (let a = 0; a < Math.PI * 2; a += 0.05) {
      if (a > 1.2 && a < 1.9 && r > 4) continue;
      const x = cx + Math.cos(a) * r * k * 0.8, y = cy + Math.sin(a) * r * k;
      if (big ? (Math.round(r) % 2 === 0) : true) pb.set(x, y, NE[2]);
    }
  }
  g.line(pb, 7, 27, 20, 27, P.ink);
});
icon('autopsy', (pb, k, big) => {
  const g = mk(k);
  g.box(pb, 4, 2, 24, 28, NE, 9, { hi: 0, lo: 1, bot: 1 });
  g.box(pb, 4, 2, 24, 4, R.teal, 3, { hi: 0, lo: 0 });
  // силуэт тела
  g.ell(pb, 12, 11, 2, 2, NE, 6, { hi: 0, lo: 0 });
  g.poly(pb, [[10, 13], [14, 13], [15, 21], [13, 27], [11, 27], [9, 21]], NE, 6, { hi: 0, lo: 0 });
  g.px(pb, 13, 17, R.red[3]); g.px(pb, 11, 15, R.red[3]);
  textLines(pb, k, 18, 9, 7, big ? 9 : 5, big ? 2 : 3, NE[5], 41);
});
icon('watch', (pb, k, big) => {
  const g = mk(k);
  g.box(pb, 12, 2, 8, 28, WO, 2);
  if (big) for (let y = 3; y < 30; y += 2) g.line(pb, 12, y, 19, y, WO[1]);
  g.ell(pb, 16, 16, 8, 8, GO, 3);
  g.ell(pb, 16, 16, 6, 6, NE, 9, { hi: 0, lo: 1 });
  for (let i = 0; i < 12; i++) { const a = i * Math.PI / 6; g.px(pb, 16 + Math.cos(a) * 5, 16 + Math.sin(a) * 5, NE[4]); }
  g.line(pb, 16, 16, 16, 12, NE[1]); g.line(pb, 16, 16, 19, 17, NE[1]);
  g.px(pb, 25, 16, GO[4]);
  g.line(pb, 12, 12, 13, 11, P.white);
});
icon('glass', (pb, k, big) => {
  const g = mk(k);
  g.poly(pb, [[8, 3], [24, 3], [22, 29], [10, 29]], R.blue, 6, { hi: 1, lo: 1, bot: 1 });
  g.poly(pb, [[9, 13], [23, 13], [22, 28], [10, 28]], R.blue, 5, { hi: 0, lo: 1 });
  g.line(pb, 9, 13, 23, 13, R.blue[6]);
  g.line(pb, 11, 5, 12, 26, NE[9]);
  g.line(pb, 10, 28, 22, 28, R.blue[4]);
  g.ell(pb, 19, 6, 2, 1, R.red, 3, { hi: 0, lo: 0 }); // след помады
  if (big) { g.px(pb, 16, 20, NE[9]); g.px(pb, 18, 23, NE[9]); g.px(pb, 14, 17, R.blue[6]); }
});
icon('laptop', (pb, k, big) => {
  const g = mk(k);
  g.box(pb, 6, 5, 20, 15, NE, 3);
  g.box(pb, 8, 7, 16, 11, R.blue, 2, { hi: 0, lo: 0 });
  g.line(pb, 9, 9, 18, 9, R.teal[5]); g.line(pb, 9, 11, 15, 11, R.teal[4]); g.line(pb, 9, 13, 20, 13, R.teal[4]);
  g.poly(pb, [[6, 20], [26, 20], [30, 27], [2, 27]], NE, 5);
  for (let y = 21; y < 26; y += 2) g.line(pb, 7 + (y - 21) * 0.3, y, 25 - (y - 21) * 0.3, y, NE[4]);
  g.box(pb, 13, 25, 6, 1, NE, 4, { hi: 0, lo: 0 });
});
icon('bag', (pb, k, big) => {
  const g = mk(k);
  g.poly(pb, [[10, 6], [22, 6], [22, 10], [20, 10], [20, 8], [12, 8], [12, 10], [10, 10]], WO, 2);
  g.poly(pb, [[5, 10], [27, 10], [29, 28], [3, 28]], WO, 3, { hi: 1, lo: 2, bot: 1 });
  g.poly(pb, [[5, 10], [27, 10], [27, 16], [5, 16]], WO, 4);
  g.box(pb, 14, 14, 4, 4, GO, 4);
  g.line(pb, 5, 16, 27, 16, WO[1]);
  if (big) { for (let x = 6; x < 27; x += 2) { g.px(pb, x, 11, WO[2]); g.px(pb, x, 27, WO[1]); } }
});
icon('paint', (pb, k, big) => {
  const g = mk(k);
  g.poly(pb, [[3, 15], [8, 8], [20, 6], [29, 12], [28, 22], [18, 27], [7, 25]], WO, 5);
  g.ell(pb, 20, 20, 2, 2, NE, 3, { hi: 0, lo: 0 }); pb.set(g.u(20), g.u(20), 0);
  const cs = [R.red[3], R.blue[4], R.gold[4], R.green[4], R.purple[4], NE[9]];
  [[9, 13], [13, 9], [19, 9], [24, 12], [9, 20], [25, 18]].forEach((p, i) => g.ell(pb, p[0], p[1], 1.6, 1.4, [cs[i], cs[i], cs[i]], 1, { hi: 0, lo: 0 }));
  g.line(pb, 14, 30, 27, 3, WO[3]); g.line(pb, 26, 4, 28, 2, NE[2]); g.ell(pb, 28, 2, 1, 1, R.red, 3, { hi: 0, lo: 0 });
});
icon('violin', (pb, k, big) => {
  const g = mk(k);
  // корпус под углом
  g.ell(pb, 12, 21, 7, 6, R.hairRed, 3);
  g.ell(pb, 18, 13, 6, 5, R.hairRed, 3);
  g.poly(pb, [[11, 16], [16, 18], [13, 21]], R.hairRed, 3, { hi: 0, lo: 0 });
  g.line(pb, 9, 26, 26, 6, NE[1]);
  g.line(pb, 22, 10, 29, 3, NE[1]); g.line(pb, 23, 10, 30, 3, NE[2]);
  g.ell(pb, 29, 2, 1, 1, WO, 1, { hi: 0, lo: 0 });
  g.line(pb, 10, 22, 12, 17, NE[0]); g.line(pb, 16, 20, 18, 15, NE[0]); // эфы
  g.line(pb, 10, 25, 25, 7, NE[8]);
  g.line(pb, 7, 19, 9, 17, R.hairRed[4]);
  g.line(pb, 2, 10, 20, 30, WO[5]); // смычок
});
icon('bread', (pb, k, big) => {
  const g = mk(k);
  g.poly(pb, [[3, 20], [6, 12], [14, 8], [24, 9], [29, 15], [28, 23], [6, 25]], WO, 4, { hi: 1, lo: 2, bot: 2 });
  for (let i = 0; i < 4; i++) { g.line(pb, 8 + i * 5, 17, 11 + i * 5, 11, WO[6]); g.line(pb, 9 + i * 5, 17, 12 + i * 5, 11, WO[3]); }
  g.box(pb, 2, 25, 28, 3, PA, 3);
  if (big) for (let i = 0; i < 10; i++) g.px(pb, 6 + i * 2.2, 20 + (i % 3), WO[5]);
});
icon('cctv', (pb, k, big) => {
  const g = mk(k);
  g.box(pb, 20, 3, 8, 3, NE, 4);
  g.line(pb, 23, 6, 21, 11, NE[3]); g.line(pb, 24, 6, 22, 11, NE[3]);
  g.poly(pb, [[4, 12], [24, 9], [26, 18], [6, 21]], NE, 8);
  g.poly(pb, [[2, 13], [6, 12], [7, 21], [3, 21]], NE, 2);
  g.ell(pb, 5, 17, 1, 2, R.blue, 4, { hi: 0, lo: 0 });
  g.ell(pb, 21, 15, 1, 1, R.red, 4, { hi: 0, lo: 0 });
  g.line(pb, 8, 20, 25, 17, NE[6]);
  if (big) { g.line(pb, 9, 13, 22, 11, NE[9]); textLines(pb, k, 10, 15, 8, 1, 2, NE[5], 5); }
  g.line(pb, 3, 25, 10, 27, R.red[3]);
});
icon('camera', (pb, k, big) => {
  const g = mk(k);
  g.box(pb, 3, 10, 26, 17, NE, 2);
  g.box(pb, 9, 6, 9, 4, NE, 3);
  g.box(pb, 3, 14, 26, 9, WO, 2, { hi: 0, lo: 0 });
  g.ell(pb, 16, 18, 6, 6, NE, 4);
  g.ell(pb, 16, 18, 4, 4, NE, 1, { hi: 0, lo: 0 });
  g.ell(pb, 16, 18, 2, 2, R.blue, 3, { hi: 0, lo: 0 });
  g.px(pb, 15, 17, NE[9]);
  g.box(pb, 23, 11, 4, 2, NE, 8, { hi: 0, lo: 0 });
  g.box(pb, 5, 11, 3, 2, NE, 6, { hi: 0, lo: 0 });
});
icon('money', (pb, k, big) => {
  const g = mk(k);
  for (let i = 2; i >= 0; i--) {
    const o = i * 2;
    g.poly(pb, [[3 + o, 10 - o], [27 + o, 8 - o], [28 + o, 22 - o], [4 + o, 24 - o]], R.green, i ? 4 : 5);
  }
  g.ell(pb, 16, 15, 3, 4, R.green, 3, { hi: 0, lo: 0 });
  g.line(pb, 6, 11, 9, 11, R.green[2]); g.line(pb, 23, 20, 26, 20, R.green[2]);
  g.box(pb, 12, 9, 2, 16, PA, 4, { hi: 0, lo: 0 }); // бандероль
  if (big) { g.px(pb, 16, 14, R.green[6]); g.line(pb, 6, 21, 9, 21, R.green[3]); }
});
icon('pills', (pb, k, big) => {
  const g = mk(k);
  g.box(pb, 9, 3, 13, 5, NE, 9);
  g.box(pb, 8, 8, 15, 21, R.gold, 3, { hi: 1, lo: 2, bot: 1 });
  g.box(pb, 8, 13, 15, 10, NE, 9, { hi: 0, lo: 1 });
  textLines(pb, k, 10, 16, 10, big ? 3 : 2, 2, NE[4], 9);
  g.line(pb, 9, 9, 9, 27, R.gold[5]);
  g.ell(pb, 27, 26, 2, 1, NE, 8); g.ell(pb, 4, 27, 2, 1, R.red, 4);
});
icon('keycard', (pb, k, big) => {
  const g = mk(k);
  g.poly(pb, [[4, 9], [27, 6], [29, 23], [6, 26]], NE, 8);
  g.box(pb, 7, 10, 6, 7, NE, 5, { hi: 0, lo: 0 });
  g.ell(pb, 10, 12, 1.5, 1.5, R.hairBrown, 3, { hi: 0, lo: 0 });
  g.line(pb, 15, 11, 25, 10, NE[3]); g.line(pb, 15, 14, 22, 13, NE[5]);
  g.box(pb, 7, 19, 20, 2, R.blue, 3, { hi: 0, lo: 0 });
  g.box(pb, 20, 14, 5, 4, GO, 4, { hi: 0, lo: 0 });
  g.line(pb, 14, 1, 16, 7, R.red[3]); g.line(pb, 18, 1, 16, 7, R.red[3]);
});
function iconCanvas(id, S) {
  const pb = new PB(S, S);
  const f = IC[id];
  if (f) {
    const inner = new PB(S, S);
    f(inner, (S - 2) / 32, S > 32);
    // контур поверх: сдвиг на 1 px внутрь кадра
    for (let y = 0; y < S - 1; y++) for (let x = 0; x < S - 1; x++) { const c = inner.get(x, y); if (c) pb.set(x + 1, y + 1, c); }
    pb.outline();
  } else pb.rect(4, 4, S - 8, S - 8, R.neutral[5]);
  return pb.toCanvas();
}
const ICON_CACHE = {}, ICON_BIG = {};
G.Icons = {
  ids: Object.keys(IC),
  draw(ctx, id, x, y) { const c = ICON_CACHE[id] || (ICON_CACHE[id] = iconCanvas(id, 32)); ctx.drawImage(c, x | 0, y | 0); },
  drawBig(ctx, id, x, y) { const c = ICON_BIG[id] || (ICON_BIG[id] = iconCanvas(id, 64)); ctx.drawImage(c, x | 0, y | 0); },
};

G.__castMainInternal = { PB, head, hairShape, shade, mPoly };
})();
