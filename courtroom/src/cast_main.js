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

/*BUSTS_V3_BEGIN*/
/* =====================================================================
   БЮСТЫ v3 — половинное разрешение.
   Родной кадр 80×72 px (якорь — нижняя середина: x=40, y=72), в кэш кладётся
   копия ×2 (160×144). Все части нарисованы картами-строками и попиксельно.
   Слои: тело (поза) → голова (эмоция) → веки / рот (оверлеи) → передняя рука.
   Ключи кэша: cast/<id>/bust/<часть>/<вариант>.
   ===================================================================== */
const BW = 80, BH = 72, BCX = 40, SC = 2;
const BUSTS = {};   // id -> spec

/* карта-строка с ключом: символ -> цвет ('' — пропуск, null — стереть) */
function bmap(pb, rows, key, ox, oy, flip) { pb.map(rows, key, ox | 0, oy | 0, flip); }
function bpoly(pb, pts, col) { pb.fill(mPoly(pb, pts), col); }
function bline(pb, pts, col) { pb.pl(pts, col); }
/* обвести только то, что нарисовано в pb, контуром OUT (без селективности) */
function boutline(pb, sel) { pb.outline({ selective: !!sel }); }
/* отдельный слой с собственным контуром поверх pb (руки, рукава, предметы) */
function blayer(pb, fn, sel) {
  const t = new PB(pb.w, pb.h); fn(t); t.outline({ selective: !!sel });
  for (let i = 0; i < t.d.length; i++) if (t.d[i]) pb.d[i] = t.d[i];
}

/* общий ключ для карт: o — контур, 1..5 — кожа, a..e — волосы, w — блик */
function K(skin, hair, extra) {
  const k = { o: OUT, O: P.black, w: P.white };
  if (skin) { k['1'] = skin[0]; k['2'] = skin[1]; k['3'] = skin[2]; k['4'] = skin[3]; k['5'] = skin[4]; }
  if (hair) { k.a = hair[0]; k.b = hair[1]; k.c = hair[2]; k.d = hair[3]; k.e = hair[4]; }
  return Object.assign(k, extra || {});
}

function partCanvas(id, path, w, h, paint) {
  return G.cacheCanvas('cast/' + id + '/bust/' + path, w * SC, h * SC, c => {
    const pb = new PB(w, h); paint(pb);
    c.imageSmoothingEnabled = false;
    c.drawImage(pb.toCanvas(), 0, 0, w * SC, h * SC);
  });
}
/* spec = { seed, parts:{path:[w,h,paint]}, compose(o, st) -> [[path, nx, ny], ...] } */
function defineBust(id, spec) {
  BUSTS[id] = spec;
  const get = p => { const d = spec.parts[p]; if (!d) return null; return partCanvas(id, p, d[0], d[1], d[2]); };
  spec.get = get;
  return {
    w: BW * SC, h: BH * SC,
    draw(ctx, x, y, o) {
      o = o || {};
      const st = bustState(o, spec.seed);
      const list = spec.compose(o, st);
      const left = x - BCX * SC, top = y - BH * SC - st.br * SC;
      ctx.save();
      if (o.flip) { ctx.translate(2 * x, 0); ctx.scale(-1, 1); }
      for (const it of list) {
        const c = get(it[0]); if (!c) continue;
        ctx.drawImage(c, left + it[1] * SC, top + it[2] * SC);
        // при вдохе нижний ряд тела дублируется, чтобы снизу не было щели
        if (st.br && it[2] + c.height / SC >= BH) ctx.drawImage(c, 0, c.height - SC, c.width, SC, left + it[1] * SC, top + (it[2] + c.height / SC) * SC, c.width, SC);
      }
      ctx.restore();
    },
  };
}
/* общее состояние: моргание, рот (8 к/с), дыхание, расписание фиджетов */
function bustState(o, seed) {
  const t = o.t || 0;
  const per = 3.3 + (seed % 7) * 0.19;
  const ph = ((t + seed * 0.613) % per + per) % per;
  const blink = ph < 0.05 ? 1 : ph < 0.12 ? 2 : ph < 0.17 ? 1 : 0;
  const mouth = o.talking ? [1, 2, 1, 0, 2, 1, 2, 0][Math.floor(t * 8) % 8] : 0;
  const bper = 3.1 + (seed % 5) * 0.23;
  const br = Math.sin((t + seed * 0.37) * Math.PI * 2 / bper) > 0.1 ? 1 : 0;
  return { t, blink, mouth, br };
}
/* окно фиджета: прогресс 0..1 каждые period сек на dur сек, иначе -1 */
function fidget(t, period, dur, seed) {
  const ph = (((t || 0) + seed * 1.37) % period + period) % period;
  return ph < dur ? ph / dur : -1;
}

/* ---------------------------------------------------------------------
   СУДЬЯ — Харольд Уитакер
   --------------------------------------------------------------------- */
(function () {
  const S = R.skinL, H = R.hairGrey, N = R.neutral;
  const k = K(S, H, { g: N[1], G: N[4], k: N[1], i: R.blue[3], r: R.red[2], m: S[0] });
  // голова 22×26, смотрит влево (3/4). Глаза: ряд 12. Рот: ряд 18.
  const HEAD = [
    '........oooooo........',
    '......ooeeeeedoo......',
    '.....oeeeeedddddoo....',
    '....oeeeeddddddcccoo..',
    '...oeeddddcccccbbbbbo.',
    '...o4ddddccccbbbbbcbo.',
    '..o4554dccbbbbcbbbbbbo',
    '..o45544dcbbbcbbbbbbbo',
    '..o455444dcbbbbbcbbbao',
    '..o4544444dcbbbbbbbbao',
    '..o44444444dcbbbbbbbao',
    '.o4444444444cbbbbbbabo',
    '.o44444444443oo3bbbabo',
    '.o44444444443o432bbaao',
    'o444444444433o332bbao.',
    'o544444444333o232bao..',
    'o2444444443332o22ao...',
    '.o244444433332oooo....',
    '..o44444433322223o....',
    '..o44444333222222o....',
    '...o4443332211112o....',
    '...o3443o1111111o.....',
    '....oooo21111111o.....',
    '.......o2111111o......',
    '.......o111111o.......',
    '.......oo1111o........',
  ];
  function face(pb, emo) {
    const fr = N[3], sk = S[3];
    // очки: тонкая оправа, дальнее стекло уже ближнего
    bline(pb, [[2, 11], [4, 11]], fr); bline(pb, [[2, 13], [4, 13]], fr);
    pb.set(5, 12, fr);                                 // перемычка
    bline(pb, [[6, 11], [10, 11]], fr); bline(pb, [[6, 14], [10, 14]], fr);
    bline(pb, [[6, 11], [6, 14]], fr); bline(pb, [[10, 11], [10, 14]], fr);
    bline(pb, [[11, 12], [13, 12]], N[2]);             // дужка к уху
    pb.set(1, 12, fr);
    // глаза
    if (emo === 'surprised') {
      bmap(pb, ['k'], k, 3, 12); bmap(pb, ['wkw'], k, 7, 12); bmap(pb, ['.k.'], k, 7, 13);
      pb.set(3, 11, S[4]);
    } else if (emo === 'smile') {
      bmap(pb, ['k'], k, 3, 13); bmap(pb, ['.kk.'], k, 6, 13);
      bmap(pb, ['222'], k, 7, 12);
    } else {
      bmap(pb, ['k'], k, 3, 12); bmap(pb, ['kk3'], k, 7, 12); bmap(pb, ['222'], k, 7, 13);
      if (emo === 'stern') bmap(pb, ['222'], k, 7, 12), pb.set(7, 13, N[1]), pb.set(8, 13, N[1]);
    }
    // блик на ближнем стекле
    pb.set(9, 12, P.white); pb.set(8, 11, N[6]);
    // брови (седые, кустистые)
    if (emo === 'stern') { bmap(pb, ['ccd', '..c'], k, 2, 9); bmap(pb, ['.dcc', 'cc..'], k, 7, 9); }
    else if (emo === 'surprised') { bmap(pb, ['ccd'], k, 2, 8); bmap(pb, ['dccc'], k, 7, 8); }
    else if (emo === 'smile') { bmap(pb, ['ccd'], k, 2, 10); bmap(pb, ['dccc'], k, 7, 10); }
    else { bmap(pb, ['ccd'], k, 2, 10); bmap(pb, ['dccc'], k, 7, 10); }
    // нос: переносица светлая, кончик выступает, ноздря
    pb.set(4, 13, S[4]); pb.set(3, 14, S[4]); pb.set(1, 15, S[3]); pb.set(2, 16, S[2]); pb.set(3, 16, S[1]);
    // носогубная складка и скула
    pb.set(6, 16, S[2]); pb.set(6, 17, S[2]); pb.set(7, 15, S[2]);
    // рот
    if (emo === 'smile') { bmap(pb, ['m...', '.mmm', '..44'], k, 2, 18); }
    else if (emo === 'stern') bmap(pb, ['mmmm', '.22.'], k, 2, 19);
    else if (emo === 'surprised') bmap(pb, ['.mm', 'mrrm', 'mrrm', '.mm'], k, 2, 18);
    else bmap(pb, ['mmm', '.44'], k, 2, 19);
    // уголок рта и подбородок
    pb.set(4, 22, S[2]);
  }
  const MOUTHS = { 1: ['.mm.', 'mrrm'], 2: ['.mmm', 'mrrm', 'mrrm', '.mm.'] };

  // --- тело: мантия ---
  const RB = N; // мантия: N[1] тень, N[2] база, N[3] свет, N[4] блик
  function robe(pb) {
    bpoly(pb, [[34, 25], [27, 27], [22, 30], [20, 35], [19, 72], [61, 72], [60, 37], [58, 30], [53, 27], [46, 25]], RB[2]);
    // свет по левому плечу и груди
    bpoly(pb, [[27, 27], [22, 30], [20, 35], [20, 50], [23, 38], [27, 31], [33, 27]], RB[3]);
    bline(pb, [[27, 28], [23, 30], [21, 34]], RB[4]);
    // тень справа
    bpoly(pb, [[57, 31], [59, 34], [60, 40], [60, 72], [56, 72], [57, 46], [57, 37]], RB[1]);
    // V-вырез: рубашка, воротник, галстук
    bpoly(pb, [[34, 25], [46, 25], [42, 40], [39, 42]], N[8]);
    bpoly(pb, [[42, 26], [46, 25], [43, 34]], N[6]);
    bpoly(pb, [[39, 30], [42, 30], [42, 39], [40, 42], [39, 39]], R.carpet[1]);
    bline(pb, [[39, 31], [39, 38]], R.carpet[3]);
    bpoly(pb, [[38, 27], [43, 27], [42, 30], [39, 30]], R.carpet[2]);
    bline(pb, [[35, 26], [38, 28]], N[9]); bline(pb, [[43, 28], [45, 26]], N[7]);
    // края мантии вдоль выреза
    bline(pb, [[34, 25], [39, 43], [39, 72]], RB[1]);
    bline(pb, [[33, 26], [37, 39]], RB[4]);
    bline(pb, [[46, 25], [42, 41], [41, 46]], RB[1]);
    bline(pb, [[47, 26], [44, 36]], RB[3]);
    // кокетка и складки
    bline(pb, [[21, 41], [28, 43], [36, 44]], RB[1]);
    bline(pb, [[44, 45], [52, 44], [59, 41]], RB[1]);
    bline(pb, [[22, 42], [28, 44]], RB[3]);
    [[25, 45], [31, 46]].forEach(([x, y]) => { bline(pb, [[x, y], [x - 1, 72]], RB[3]); bline(pb, [[x + 1, y], [x, 72]], RB[1]); });
    [[49, 46], [54, 45]].forEach(([x, y]) => { bline(pb, [[x, y], [x + 1, 72]], RB[1]); });
  }
  const HANDS_CLASP = [
    '...oooooooo...',
    '..o55444443o..',
    '.o5o44o44o32o.',
    '.o4o44o43o32o.',
    'o544o44o43o32o',
    'o44444444433o.',
    '.o3443433322o.',
    '..oo3333222oo.',
    '....oooooo....',
  ];
  function sleeveL(pb) {
    bpoly(pb, [[19, 46], [24, 48], [35, 57], [36, 67], [26, 68], [18, 63]], RB[2]);
    bline(pb, [[19, 46], [24, 48], [35, 57]], RB[3]);
    bline(pb, [[20, 47], [24, 49]], RB[4]);
    bline(pb, [[18, 63], [26, 68], [36, 67]], RB[1]);
    bline(pb, [[23, 55], [29, 60]], RB[1]);
    bline(pb, [[34, 57], [34, 67]], RB[1]); bline(pb, [[35, 57], [35, 67]], RB[0]);
  }
  function sleeveR(pb) {
    bpoly(pb, [[61, 46], [56, 48], [46, 57], [45, 67], [55, 69], [62, 64]], RB[2]);
    bline(pb, [[60, 47], [56, 49], [47, 57]], RB[3]);
    bline(pb, [[62, 64], [55, 69], [45, 67]], RB[1]);
    bline(pb, [[57, 56], [52, 61]], RB[1]);
    bline(pb, [[46, 58], [46, 67]], RB[0]);
  }
  // молоток: головка с кольцами + рукоять
  const WK = { o: OUT, 6: R.wood[6], 5: R.wood[5], 4: R.wood[4], 3: R.wood[3], 2: R.wood[2], 1: R.wood[1], g: R.gold[4], G: R.gold[2] };
  const GAV_H = [ // головка горизонтально 11×5
    '.ooooooooo.',
    'o5g655566go',
    'o4G444444Go',
    'o3G322332Go',
    '.ooooooooo.',
  ];
  const GAV_V = [ // головка вертикально 5×11 (удар)
    '.ooo.',
    'o5gGo',
    'o6GGo',
    'o544o',
    'o543o',
    'o543o',
    'o443o',
    'o433o',
    'o5GGo',
    'o4gGo',
    '.ooo.',
  ];
  function fistR(pb, x, y) { // кулак, обхват рукояти; смотрит влево
    bmap(pb, ['.oooo.', 'o5444o', 'o4o43o', 'o4o32o', 'o4332o', '.oooo.'], k, x, y);
  }
  function armRaised(pb) {
    blayer(pb, q => {
      // рукав-колокол свисает с поднятого предплечья
      bpoly(q, [[56, 31], [60, 18], [66, 16], [69, 27], [67, 40], [61, 43], [57, 38]], RB[2]);
      bline(q, [[56, 31], [60, 18]], RB[3]); bline(q, [[57, 31], [61, 19]], RB[3]);
      bline(q, [[66, 17], [69, 27], [67, 39]], RB[1]);
      bline(q, [[62, 24], [64, 36]], RB[1]);
      bpoly(q, [[60, 17], [66, 15], [67, 18], [61, 20]], RB[1]); // манжета
    });
    blayer(pb, q => {
      bpoly(q, [[60, 2], [62, 2], [62, 14], [60, 14]], R.wood[4]); bline(q, [[60, 2], [60, 14]], R.wood[5]);
    });
    bmap(pb, GAV_H, WK, 56, 0);
    fistR(pb, 58, 11);
  }
  function armStrike(pb) {
    blayer(pb, q => {
      bpoly(q, [[60, 44], [55, 47], [49, 57], [50, 64], [58, 66], [63, 60]], RB[2]);
      bline(q, [[60, 45], [55, 48], [50, 57]], RB[3]);
      bline(q, [[50, 64], [58, 66], [63, 60]], RB[1]);
      bline(q, [[51, 57], [51, 64]], RB[0]);
    });
    blayer(pb, q => { bpoly(q, [[42, 58], [50, 58], [50, 60], [42, 60]], R.wood[4]); bline(q, [[42, 58], [50, 58]], R.wood[5]); });
    bmap(pb, GAV_V, WK, 37, 54);
    fistR(pb, 46, 56);
  }
  function armRebound(pb) {
    blayer(pb, q => {
      bpoly(q, [[60, 42], [55, 45], [50, 50], [52, 58], [60, 58], [63, 52]], RB[2]);
      bline(q, [[60, 43], [55, 46], [51, 50]], RB[3]);
      bline(q, [[52, 58], [60, 58], [63, 52]], RB[1]);
    });
    blayer(pb, q => { bpoly(q, [[48, 46], [51, 46], [51, 54], [48, 54]], R.wood[4]); bline(q, [[48, 46], [48, 54]], R.wood[5]); });
    bmap(pb, GAV_H, WK, 44, 42);
    fistR(pb, 47, 49);
  }
  function body(pb, pose) {
    robe(pb);
    boutline(pb);
    blayer(pb, sleeveL);
    if (pose === 'normal') {
      blayer(pb, sleeveR);
      bmap(pb, HANDS_CLASP, k, 33, 56);
    } else {
      bmap(pb, ['.ooooo.', 'o55444o', 'o4o4o3o', 'o44433o', '.ooooo.'], k, 32, 60);
      if (pose === 'g1') armRaised(pb);
      else if (pose === 'g2') armStrike(pb);
      else armRebound(pb);
    }
  }
  function impact(pb) { // линии удара вокруг головки
    const w = P.white, y = R.gold[5];
    bline(pb, [[35, 55], [33, 53]], w); bline(pb, [[37, 52], [37, 50]], y);
    bline(pb, [[35, 62], [32, 62]], w); bline(pb, [[35, 59], [33, 58]], y);
    bline(pb, [[43, 52], [44, 50]], w); bline(pb, [[36, 66], [34, 68]], y);
  }
  const parts = {};
  ['normal', 'g1', 'g2', 'g3'].forEach(p => { parts['body/' + p] = [BW, BH, pb => { body(pb, p); if (p === 'g2') impact(pb); }]; });
  ['normal', 'stern', 'surprised', 'smile'].forEach(e => {
    parts['head/' + e] = [22, 26, pb => { bmap(pb, HEAD, k, 0, 0); face(pb, e); }];
  });
  parts['lids/1'] = [11, 2, pb => { bmap(pb, ['.3...333', '.2...222'], k, 0, 0); }];
  parts['lids/2'] = [11, 2, pb => { bmap(pb, ['.4...444', '.2...222'], k, 0, 0); }];
  parts['mouth/1'] = [6, 4, pb => bmap(pb, MOUTHS[1], k, 0, 0)];
  parts['mouth/2'] = [6, 4, pb => bmap(pb, MOUTHS[2], k, 0, 0)];

  const spec = {
    seed: 3, parts,
    compose(o, st) {
      const emo = ['stern', 'surprised', 'smile'].includes(o.emo) ? o.emo : 'normal';
      let pose = 'normal';
      if (o.anim === 'gavel') {
        const a = o.animT || 0;
        pose = a < 0.32 ? 'g1' : a < 0.45 ? 'g3' : a < 0.6 ? 'g2' : a < 0.9 ? 'g3' : 'normal';
      }
      const L = [['body/' + pose, 0, 0], ['head/' + emo, 29, 2]];
      if (st.blink && emo !== 'surprised') L.push(['lids/' + st.blink, 29 + 2, 2 + 12]);
      if (st.mouth) L.push(['mouth/' + st.mouth, 29 + 2, 2 + 18]);
      return L;
    },
  };
  G.Cast.register('judge', {
    name: 'Судья Уитакер', voice: 'low',
    emotions: ['normal', 'stern', 'surprised', 'smile'],
    anims: { gavel: 0.9 }, bust: defineBust('judge', spec), iso: null,
  });
})();

/* все ключи бюстов — для запекания */
G.prebuild(() => {
  for (const id in BUSTS) for (const p in BUSTS[id].parts) BUSTS[id].get(p);
});

/*BUSTS_V3_END*/

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

G.__castMainInternal = { PB, shade, mPoly };
})();
