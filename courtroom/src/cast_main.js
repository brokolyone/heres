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
    '..ssssss.',
    '..KKKKKKK',
    '.KiPPiWwK',
    '...llll..'],
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
    'sssss',
    'KKKKK',
    'PPiwK',
    '.ll..'],
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
function breath(t) { return Math.sin((t || 0) * Math.PI * 2 / 3.1) > 0.2 ? 1 : 0; }

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
    // шея
    const neck = mPoly(pb, P2(0, 0, [[63, 44], [79, 42], [80, 58], [64, 60]]));
    pb.fill(neck, sk[2]);
    dith(pb, neck, sk[1], 8, 63, 50, 80, 60);
    pb.line(64, 46, 64, 58, sk[3]);
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
    pb.line(96, 88, 106, 87, su[2]); pb.line(96, 89, 106, 88, su[4]);
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
  function paint(pb, emo, eyes, mouth, br) {
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
    const br = breath(o.t);
    const key = emo + '|' + eyes + '|' + mouth + '|' + br;
    const spr = bust.frame(key, pb => paint(pb, emo, eyes, mouth, br));
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

G.__castMainInternal = { PB, head, hairShape, shade, mPoly };
})();
