/* =====================================================================
   CAST_CASE — персонажи дел: lomax, hollis, whitfield, crane, park,
   bell, doyle, morales, holloway.
   Бюсты (КОНТРАКТ v3): рисуются в половинном разрешении 64x72,
   в кэш кладётся копия x2 (каждый пиксель -> 2x2). Слои: тело (поза),
   лицо, глаза, брови, рот, экстра — каждый слой отдельный ключ
   cast/<id>/bust/<part>, в рантайме только blit.
   Лицо 3/4, смотрит ВЛЕВО; свет сверху слева; селективный контур.
   Изометрия ~12x26 (её переопределяет src/iso.js).
   ===================================================================== */
(function () {
'use strict';
const G = window.G;
const R = G.RAMP, PAL = G.PAL;
const NW = 64, NH = 72;       // родной размер бюста
const SC = 2;                 // масштаб кэша
const BW = NW * SC, BH = NH * SC;
const OUT = PAL.outline;

/* ---------- палитра: цвет -> [рампа, индекс] (для селективного контура) ---------- */
const COLIDX = {};
for (const [name, r] of Object.entries(R)) r.forEach((c, i) => { if (!COLIDX[c]) COLIDX[c] = [r, i]; });
function darker(col, n) {
  const e = COLIDX[col];
  if (!e) return OUT;
  return e[0][Math.max(0, e[1] - n)];
}
function hex(r, g, b) { return '#' + [r, g, b].map(v => v.toString(16).padStart(2, '0')).join(''); }

/* ---------- примитивы родного разрешения ---------- */
function px(c, x, y, col) { if (!col) return; c.fillStyle = col; c.fillRect(x | 0, y | 0, 1, 1); }
function hl(c, x0, x1, y, col) { if (x1 < x0) return; c.fillStyle = col; c.fillRect(x0 | 0, y | 0, (x1 - x0 + 1) | 0, 1); }
function vl(c, x, y0, y1, col) { if (y1 < y0) return; c.fillStyle = col; c.fillRect(x | 0, y0 | 0, 1, (y1 - y0 + 1) | 0); }
function rect(c, x, y, w, h, col) { c.fillStyle = col; c.fillRect(x, y, w, h); }
function poly(c, pts, col) { G.poly(c, pts, col); }
function line(c, a, b, col) { G.line(c, a[0], a[1], b[0], b[1], col); }
/* карта-строка: key {символ: цвет}; '.' и ' ' прозрачно */
function map(c, x, y, rows, key, mirror) {
  for (let j = 0; j < rows.length; j++) {
    const r = rows[j];
    for (let i = 0; i < r.length; i++) {
      const ch = r[i];
      if (ch === '.' || ch === ' ') continue;
      const col = key[ch];
      if (!col) continue;
      c.fillStyle = col;
      c.fillRect(mirror ? x + r.length - 1 - i : x + i, y + j, 1, 1);
    }
  }
}
/* по строкам: spans = [[y, x0, x1], ...] */
function spans(c, list, col) { for (const s of list) hl(c, s[1], s[2], s[0], col); }

/* Нарисовать на временном canvas и обвести селективным контуром:
   снаружи справа/снизу — тёмный контур, сверху/слева — тёмный тон рампы самого цвета. */
const tmpA = G.makeCanvas(NW + 4, NH + 4);
function outlined(fn, opt) {
  opt = opt || {};
  const w = NW, h = NH + 2;
  const c = G.makeCanvas(w, h);
  const x = c.getContext('2d');
  fn(x);
  const img = x.getImageData(0, 0, w, h);
  const d = img.data;
  const op = (i, j) => i >= 0 && j >= 0 && i < w && j < h && d[(j * w + i) * 4 + 3] > 0;
  const colAt = (i, j) => { const k = (j * w + i) * 4; return hex(d[k], d[k + 1], d[k + 2]); };
  const add = [];
  for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) {
    if (op(i, j)) continue;
    // сосед-источник
    let src = null, lit = false;
    if (op(i + 1, j)) { src = [i + 1, j]; lit = true; }
    else if (op(i, j + 1)) { src = [i, j + 1]; lit = true; }
    else if (op(i - 1, j)) { src = [i - 1, j]; }
    else if (op(i, j - 1)) { src = [i, j - 1]; }
    if (!src) continue;
    if (opt.noBottom && !op(i, j - 1) === false && j >= (opt.noBottom)) continue;
    let col = OUT;
    if (lit && !opt.hard) {
      const sc = colAt(src[0], src[1]);
      col = darker(sc, opt.litDark || 3);
      if (col === sc) col = OUT;
    }
    add.push([i, j, col]);
  }
  for (const a of add) px(x, a[0], a[1], a[2]);
  if (opt.cut !== undefined) x.clearRect(0, opt.cut, w, h - opt.cut);
  return c;
}

/* Кэш частей. Каждая часть — ключ cast/<id>/bust/<name>, полный кадр NW x (NH+2) в x2. */
function upscale(src, c) {
  c.imageSmoothingEnabled = false;
  c.drawImage(src, 0, 0, src.width * SC, src.height * SC);
}
function Parts(id) {
  const defs = {};
  return {
    defs,
    add(name, fn, opt) { defs[name] = { fn, opt }; },
    get(name) {
      const d = defs[name];
      if (!d) return null;
      return G.cacheCanvas('cast/' + id + '/bust/' + name, NW * SC, (NH + 2) * SC, (c) => {
        const n = d.opt && d.opt.raw ? (() => { const cc = G.makeCanvas(NW, NH + 2); d.fn(cc.getContext('2d')); return cc; })()
          : outlined(d.fn, d.opt);
        upscale(n, c);
      });
    },
    all() { for (const k in defs) this.get(k); },
  };
}

/* ---------- моргание ---------- */
function blinkState(t, seed) {
  const per = 3.1 + (seed % 5) * 0.37;
  const ph = (t + seed * 0.731) % per;
  if (ph < 0.05) return 'half';
  if (ph < 0.14) return 'closed';
  if (ph < 0.19) return 'half';
  if ((Math.floor((t + seed * 0.731) / per) % 3 === 1) && ph > 0.3 && ph < 0.36) return 'closed';
  return 'open';
}

/* =====================================================================
   ГОЛОВА: шаблоны лица 3/4 влево. Координаты относительно (hx, hy).
   Тона: 1..5 -> skin[0..4].
   ===================================================================== */
const FACE = {
  // [l, r] по строкам; нос выступает влево
  M: [[8, 13], [6, 15], [5, 16], [4, 17], [3, 18], [3, 18], [3, 19], [2, 19], [2, 19], [2, 19], [3, 19], [3, 19],
      [2, 18], [1, 18], [0, 18], [1, 17], [3, 16], [3, 16], [3, 15], [3, 14], [3, 13], [4, 11], [5, 9]],
  F: [[8, 13], [6, 15], [5, 16], [4, 17], [3, 18], [3, 18], [3, 18], [2, 18], [2, 18], [2, 18], [3, 18], [3, 18],
      [2, 17], [1, 17], [1, 17], [2, 16], [3, 15], [3, 15], [3, 14], [4, 13], [4, 11], [5, 9]],
  B: [[8, 13], [6, 15], [5, 16], [4, 17], [3, 18], [3, 18], [3, 19], [2, 19], [2, 19], [2, 19], [3, 19], [3, 19],
      [2, 19], [1, 19], [0, 19], [1, 18], [3, 18], [3, 18], [3, 17], [3, 17], [3, 16], [3, 15], [4, 13], [5, 11]],
};
/* tone(x,y) по плоскостям */
function faceTone(type, x, y, l, r) {
  const n = FACE[type].length;
  // боковая плоскость (справа от скулы)
  const side = y <= 8 ? 15 : y <= 15 ? 13 : y <= 18 ? 12 : 10;
  let t = x >= side ? 3 : 4;
  if (x >= side + 3 && y >= 9) t = 3;
  // блики: лоб, переносица, скула, подбородок
  if (y >= 2 && y <= 7 && x >= l && x <= l + 3 && x < 10) t = 5;
  if (y === 1 && x < 10) t = 5;
  if ((y === 12 || y === 13) && x === l) t = 5;
  if (y === 13 && (x === 6 || x === 7)) t = 5;
  if (y === 12 && x === 6) t = 5;
  if (type !== 'B' && y === n - 3 && x === l) t = 5;
  // тень под бровью
  if (y === 10 && x >= 3 && x <= 11) t = Math.min(t, 4);
  // нос: тень справа от спинки и снизу
  if ((y === 13 || y === 14) && x === 4) t = 3;
  if (y === 15 && x >= l && x <= 4) t = 3;
  if (y === 15 && x === 2) t = 2;
  // под нижней губой
  if (y === 19 && x >= 4 && x <= 6) t = 3;
  // челюсть: нижний край
  if (y >= 16 && x >= r - 1) t = 2;
  if (y === n - 1) t = 3;
  if (y >= n - 2 && x >= r - 1) t = 2;
  return t;
}
function drawFace(c, hx, hy, type, sk, extra) {
  const rows = FACE[type];
  for (let y = 0; y < rows.length; y++) {
    const [l, r] = rows[y];
    for (let x = l; x <= r; x++) px(c, hx + x, hy + y, sk[faceTone(type, x, y, l, r) - 1]);
  }
  // ухо
  const E = ['.3445', '25443', '2433.', '2443.', '.333.', '..2..'];
  map(c, hx + 13, hy + 10, E, { 2: sk[1], 3: sk[2], 4: sk[3], 5: sk[4] });
  if (extra) extra(c, hx, hy);
}
/* шея: от-до */
function drawNeck(c, x0, x1, y0, y1, sk) {
  for (let y = y0; y <= y1; y++) {
    hl(c, x0, x1, y, sk[2]);
    px(c, x0, y, sk[3]);
    px(c, x1, y, sk[1]);
  }
  hl(c, x0, x1, y0, sk[1]); hl(c, x0, x1, y0 + 1, sk[1]);
  px(c, x0 + 1, y0 + 2, sk[3]);
}

/* ---------- глаза (накладка), позиции: дальний глаз x 3..5, ближний 8..11, y 10..11 ---------- */
/* L — ресницы/веко, w — белок, P — зрачок, I — радужка, g — блик, s/S — кожа тень/тон */
const EYE = {
  open:   { n: ['LLLL', 'wIPw'], f: ['LLL', 'wP.'] },
  look:   { n: ['LLLL', 'IPww'], f: ['LLL', 'Pw.'] },
  side:   { n: ['LLLL', 'wwIP'], f: ['LLL', 'wwP'] },
  half:   { n: ['ssss', 'LIPL'], f: ['sss', 'LPL'] },
  closed: { n: ['SSSS', 'LLLL'], f: ['SSS', 'LLL'] },
  down:   { n: ['ssss', 'LPPL'], f: ['sss', 'LPL'] },
  angry:  { n: ['LLLL', 'wPPL'], f: ['LLL', 'wPL'] },
  tiny:   { n: ['wwww', 'wwPw'], f: ['www', 'wPw'], up: { n: 'LLLL', f: 'LLL' } },
  happy:  { n: ['.LL.', 'L..L'], f: ['.L.', 'L.L'] },
  shut:   { n: ['SSSS', 'LLLL'], f: ['SSS', 'LLL'] },
  wide:   { n: ['wIPw', 'wwww'], f: ['wPw', 'www'], up: { n: 'LLLL', f: 'LLL' } },
};
function drawEyes(c, hx, hy, type, pal, o) {
  o = o || {};
  const e = EYE[type] || EYE.open;
  const key = { L: pal.lash, w: PAL.white, P: pal.pupil || R.neutral[0], I: pal.iris, s: pal.sk[2], S: pal.sk[3], g: PAL.white };
  const ny = hy + 10 + (o.dy || 0);
  if (e.up) { map(c, hx + 8, ny - 1, [e.up.n], key); map(c, hx + 3, ny - 1, [e.up.f], key); }
  map(c, hx + 8, ny, e.n, key);
  map(c, hx + 3, ny, e.f, key);
  // нижнее веко — тень
  if (type !== 'happy' && type !== 'closed' && type !== 'shut') { hl(c, hx + 8, hx + 11, ny + 2, pal.sk[2]); px(c, hx + 3, ny + 2, pal.sk[2]); }
}
/* брови: тип -> смещения [ближняя (внутр. конец слева), дальняя] */
function drawBrows(c, hx, hy, type, col, col2) {
  const by = hy + 8;
  col2 = col2 || col;
  const B = {
    normal:  { n: [[0, 0], [1, 0], [2, 0], [3, 0], [4, 0], [1, 1, 2], [2, 1, 2], [3, 1, 2]], f: [[0, 0], [1, 0], [2, 0]] },
    raised:  { n: [[0, -1], [1, -2], [2, -2], [3, -2], [4, -1], [2, -1, 2], [3, -1, 2]], f: [[0, -1], [1, -2], [2, -2]] },
    worried: { n: [[0, -2], [1, -2], [2, -1], [3, -1], [4, 0], [1, -1, 2], [2, 0, 2]], f: [[0, 0], [1, -1], [2, -2]] },
    angry:   { n: [[0, 1], [1, 1], [2, 0], [3, 0], [4, -1], [1, 2, 2], [2, 1, 2], [0, 2, 2]], f: [[0, -1], [1, 0], [2, 1]] },
    shocked: { n: [[0, -3], [1, -3], [2, -3], [3, -3], [4, -2], [1, -2, 2], [2, -2, 2]], f: [[0, -3], [1, -3], [2, -3]] },
    sad:     { n: [[0, -1], [1, -1], [2, 0], [3, 0], [4, 1]], f: [[0, 1], [1, 0], [2, -1]] },
  }[type] || null;
  if (!B) return;
  for (const p of B.n) px(c, hx + 7 + p[0], by + p[1], p[2] ? col2 : col);
  for (const p of B.f) px(c, hx + 2 + p[0], by + p[1], col);
}
/* рты: x 3..8, y 16..20 (относительно головы) */
const MOUTH = {
  closed: ['.....', '.DDD.', '..h..'],
  smile:  ['....D', 'DDDD.', '.hh..'],
  bigsmile: ['D...D', '.DDD.', '.....'],
  frown:  ['.....', '.DDD.', 'D...D'],
  flat:   ['.....', 'DDDDD', '.....'],
  wobble: ['.....', 'D.D.D', '.D.D.'],
  half:   ['.....', '.DDD.', '.DMD.'],
  open:   ['.DDD.', 'DMMMD', '.DrD.'],
  halfS:  ['....D', 'DDDD.', '.MM..'],
  openS:  ['D...D', 'DwwwD', '.DrD.'],
  grit:   ['.....', 'DwwwD', '.DDD.'],
  gritO:  ['DDDDD', 'wwwww', 'DMMMD'],
  O:      ['.DD..', 'DMMD.', '.DD..'],
  Obig:   ['.DDD.', 'DMMMD', 'DMrMD', '.DDD.'],
  grin:   ['D...D', 'Dwwwd', '.DDD.'],
  smirk:  ['....D', '.DDD.', '.....'],
};
function drawMouth(c, hx, hy, type, pal, dy) {
  const m = MOUTH[type] || MOUTH.closed;
  const key = { D: pal.lip || pal.sk[0], M: R.red[0], r: R.red[2], w: PAL.white, h: pal.sk[4], d: pal.sk[1] };
  map(c, hx + 3, hy + 16 + (dy || 0), m, key);
}

/* ---------- руки (кисти) ---------- */
/* кисть, лежащая на перилах/столе, пальцы вниз-влево. key: 1..5 кожа */
const HAND = {
  rest:  ['.4443.', '544443', '444443', '4.4.43', '3.3.3.'],
  restR: ['.3444.', '344445', '344444', '34.4.4', '.3.3.3'],
  clasp: ['..444..', '.54443.', '5444443', '4434443', '.3.3.3.'],
  fist:  ['.444.', '54443', '44443', '4.4.3', '.333.'],
  grip:  ['.5444.', '544443', '4.4.43', '3.3.3.'],
};
function drawHand(c, x, y, type, sk, mirror) {
  map(c, x, y, HAND[type], { 1: sk[0], 2: sk[1], 3: sk[2], 4: sk[3], 5: sk[4] }, mirror);
}

/* ---------- торс: универсальный пиджак/рубашка 3/4 влево ----------
   o: { ramp:[0..n], neck:[x0,x1], sh:[xl, xr], top:y, slope, waist:[xl,xr], seam: x (граница боковой плоскости) } */
function torso(c, o) {
  const r = o.ramp, top = o.top, sl = o.slope || 4;
  const [nl, nr] = o.neck, [sl0, sr0] = o.sh, [wl, wr] = o.waist;
  const pts = [[nl - 2, top], [nr + 2, top], [sr0 - 2, top + sl - 1], [sr0, top + sl + 2], [sr0 + 1, top + sl + 8],
    [wr, NH + 2], [wl, NH + 2], [sl0 - 1, top + sl + 8], [sl0, top + sl + 2], [sl0 + 2, top + sl - 1]];
  poly(c, pts, r[o.base || 3]);
  const seam = o.seam;
  // боковая плоскость (справа) — тень
  poly(c, [[seam, top + 2], [sr0 + 2, top + sl + 1], [sr0 + 2, NH + 2], [seam + 2, NH + 2]], r[(o.base || 3) - 1]);
  // светлые верха плеч
  poly(c, [[nl - 2, top], [sl0 + 2, top + sl - 1], [sl0, top + sl + 2], [sl0 + 2, top + sl + 2], [nl - 1, top + 2]], r[(o.base || 3) + 1]);
  return pts;
}
/* рука: плечо S -> локоть E -> запястье W, толщина w; рампа, тон */
function limb(c, a, b, w0, w1, col) {
  const dx = b[0] - a[0], dy = b[1] - a[1];
  const len = Math.hypot(dx, dy) || 1;
  const nx = -dy / len, ny = dx / len;
  poly(c, [[a[0] + nx * w0 / 2, a[1] + ny * w0 / 2], [b[0] + nx * w1 / 2, b[1] + ny * w1 / 2],
    [b[0] - nx * w1 / 2, b[1] - ny * w1 / 2], [a[0] - nx * w0 / 2, a[1] - ny * w0 / 2]], col);
}

/* =====================================================================
   СБОРКА БЮСТА ИЗ СЛОЁВ
   cfg = { id, seed, emos, parts(P), layers(st) -> [[part, dx, dy, fixed], ...],
           bkDur, fidDur, fidPer, fidEmos, breathPer }
   st  = { emo, t, bk (0..1 | -1), blink, mouth 0|1|2, fid (0..1 | -1), talking }
   ===================================================================== */
const BUST_IDS = [];
function makeBust(cfg) {
  const P = Parts(cfg.id);
  cfg.parts(P);
  BUST_IDS.push(P);
  const BKD = cfg.bkDur || 1.2;
  const FDUR = cfg.fidDur || 1.6, FPER = cfg.fidPer || 7.5;
  return {
    w: BW, h: BH, parts: P,
    state(o) {
      const t = o.t || 0;
      let emo = o.emo && cfg.emos.indexOf(o.emo) >= 0 ? o.emo : 'normal';
      let bk = -1;
      if (o.anim === 'breakdown' && cfg.emos.indexOf('breakdown') >= 0) {
        bk = G.clamp((o.animT || 0) / BKD, 0, 1); emo = 'breakdown';
      } else if (emo === 'breakdown') bk = 1;
      let fid = -1;
      if (bk < 0 && (cfg.fidEmos || ['normal']).indexOf(emo) >= 0) {
        if (o.fidget !== undefined) fid = o.fidget;
        else if (!o.talking && t > 1.2) {
          const per = FPER + (cfg.seed % 3) * 1.1;
          const ph = (t + cfg.seed * 2.37) % per;
          if (ph < FDUR) fid = ph / FDUR;
        }
      }
      let blink = blinkState(t, cfg.seed);
      let mouth = 0;
      if (o.talking) mouth = [0, 1, 2, 1][Math.floor(t * 8) % 4];
      const sv = Math.sin(t * Math.PI * 2 / (cfg.breathPer || 3.1) + cfg.seed * 1.7);
      const breath = sv > 0.1 ? 1 : 0;
      return { emo, t, bk, blink, mouth, fid, talking: !!o.talking, breath };
    },
    draw(ctx, x, y, o) {
      o = o || {};
      const st = this.state(o);
      const L = cfg.layers(st);
      const shake = cfg.shake ? cfg.shake(st) : 0;
      x = x | 0; y = y | 0;
      ctx.save();
      // обрезка по нижнему краю (якорь)
      ctx.beginPath(); ctx.rect(x - BW / 2 - 40, y - BH - 60, BW + 80, BH + 60); ctx.clip();
      if (o.flip) { ctx.translate(x * 2, 0); ctx.scale(-1, 1); }
      const ox = x - BW / 2 + shake * SC, oy = y - BH;
      for (const l of L) {
        if (!l) continue;
        const spr = P.get(l[0]);
        if (!spr) continue;
        const by = l[3] ? 0 : -st.breath;
        ctx.drawImage(spr, ox + (l[1] || 0) * SC, oy + ((l[2] || 0) + by) * SC);
      }
      ctx.restore();
    },
  };
}
/* смена фаз (0..1) на кадры */
const seg = (k, a, b) => G.clamp((k - a) / (b - a), 0, 1);
/* фиджет: подъём 0..0.25, удержание, опускание 0.75..1 -> 0|1|2 (2 = у лица) */
function fidStage(f) { if (f < 0) return 0; if (f < 0.14 || f > 0.86) return 1; return 2; }

/* стандартная мимика */
const DEF_EMOS = ['normal', 'worried', 'hopeful', 'relieved'];
const WIT_EMOS = ['normal', 'nervous', 'angry', 'shocked', 'breakdown'];
const FACESPEC = {
  normal:   { eyes: 'open', brows: 'normal', m: ['closed', 'half', 'open'] },
  worried:  { eyes: 'down', brows: 'worried', m: ['frown', 'half', 'open'] },
  hopeful:  { eyes: 'look', brows: 'raised', m: ['smile', 'halfS', 'openS'] },
  relieved: { eyes: 'happy', brows: 'worried', m: ['bigsmile', 'halfS', 'openS'], noBlink: true },
  nervous:  { eyes: 'side', brows: 'worried', m: ['wobble', 'half', 'open'] },
  angry:    { eyes: 'angry', brows: 'angry', m: ['grit', 'gritO', 'gritO'] },
  shocked:  { eyes: 'tiny', brows: 'shocked', m: ['O', 'Obig', 'Obig'], noBlink: true },
  breakdown:{ eyes: 'shut', brows: 'sad', m: ['Obig', 'Obig', 'Obig'], noBlink: true },
};
/* зарегистрировать все накладки лица для персонажа */
function faceParts(P, hx, hy, pal, extraTypes) {
  const eyes = new Set(['open', 'half', 'closed']), brows = new Set(), mouths = new Set();
  for (const k in FACESPEC) { const f = FACESPEC[k]; eyes.add(f.eyes); brows.add(f.brows); f.m.forEach(m => mouths.add(m)); }
  if (extraTypes) { (extraTypes.eyes || []).forEach(e => eyes.add(e)); (extraTypes.brows || []).forEach(e => brows.add(e)); (extraTypes.mouths || []).forEach(e => mouths.add(e)); }
  for (const e of eyes) P.add('eyes/' + e, c => drawEyes(c, hx, hy, e, pal), { raw: true });
  for (const b of brows) P.add('brows/' + b, c => drawBrows(c, hx, hy, b, pal.brow, pal.brow2), { raw: true });
  for (const m of mouths) P.add('mouth/' + m, c => drawMouth(c, hx, hy, m, pal), { raw: true });
}
/* слои лица по эмоции; spec можно переопределить */
function faceLayers(st, spec, dx, dy) {
  dx = dx || 0; dy = dy || 0;
  let eyes = spec.eyes;
  if (!spec.noBlink && st.blink !== 'open') eyes = st.blink;
  const L = [['eyes/' + eyes, dx, dy], ['brows/' + spec.brows, dx, dy], ['mouth/' + spec.m[st.mouth] , dx, dy]];
  return L;
}

/* капля пота (родные px) */
function sweat(c, x, y) {
  px(c, x, y, R.blue[6]); px(c, x, y + 1, PAL.white); px(c, x - 1, y + 2, R.blue[5]); px(c, x, y + 2, R.blue[6]); px(c, x + 1, y + 2, R.blue[5]);
  px(c, x, y + 3, R.blue[4]);
}
function makeChar(cfg) {
  const bust = makeBust(cfg);
  G.Cast.register(cfg.id, {
    name: cfg.name, voice: cfg.voice, emotions: cfg.emos,
    anims: cfg.emos.indexOf('breakdown') >= 0 ? { breakdown: cfg.bkDur || 1.2 } : {},
    bust,
    iso: makeIso(cfg.iso),
  });
}
/* ---------------------------------------------------------------------
   ИЗОМЕТРИЯ: фигурка ~12x26
   cfg = {skin, hair, hairStyle, top, top2?, pants, shoes, build:'thin'|'mid'|'big', extra(c, f)}
   --------------------------------------------------------------------- */
function makeIso(cfg) {
  const cache = {};
  /* pose: stand|sit; frame: 0/1 (дыхание), mode: idle|talk|whisper|gasp|murmur|angry|cheer|clap|laugh|shout|bk; ph: 0/1 под-кадр */
  function build(pose, frame, mode, ph) {
    const W = 22, H = 36;
    const c = G.makeCanvas(W, H);
    const x = c.getContext('2d');
    const big = cfg.build === 'big' ? 1 : 0, thin = cfg.build === 'thin' ? 1 : 0;
    const sit = pose === 'sit';
    const top = cfg.top, pants = cfg.pants || R.neutral, skin0 = cfg.skin;
    const angry = mode === 'angry' || mode === 'bk';
    const skin = angry ? [skin0[0], R.red[2], R.red[3], R.red[4], skin0[4]] : skin0;
    // смещения тела
    let jump = 0, lean = 0, hShake = 0;
    if (frame === 1) jump = 1; // дыхание/покачивание
    if (mode === 'gasp') jump = ph ? 1 : -1;
    if (mode === 'cheer') jump = ph ? -2 : 0;
    if (mode === 'laugh') jump = ph ? 1 : 0;
    if (mode === 'angry' || mode === 'bk') hShake = ph ? 1 : -1;
    if (mode === 'murmur') hShake = ph ? 1 : -1;
    if (mode === 'whisper') lean = -1;
    const fx = 5 + (mode === 'angry' || mode === 'bk' ? hShake : 0);
    const tw = 10 + big * 2 - thin;
    const legTop = 22, baseY = H - 2;
    const fill = (xx, yy, w, h, col) => { x.fillStyle = col; x.fillRect(xx, yy, w, h); };
    if (!sit) {
      const lx = fx + 1;
      for (let y = legTop; y < baseY - 1; y++) {
        fill(lx, y, 3, 1, pants[2]); fill(lx + 4, y, 3, 1, pants[1]); fill(lx, y, 1, 1, pants[3] || pants[2]);
      }
      fill(lx - 1, baseY - 1, 4, 2, cfg.shoes || R.neutral[1]); fill(lx + 4, baseY - 1, 4, 2, cfg.shoes || R.neutral[1]);
      fill(lx - 1, baseY - 1, 1, 1, R.neutral[4]);
    }
    const ty = (sit ? 18 : 13) + jump;
    const tH = sit ? 10 : legTop - 13 + (cfg.long ? 5 : 1);
    const bx = fx - big + lean;
    for (let y = 0; y < tH; y++) {
      const inset = y === 0 ? 1 : 0;
      for (let i = inset; i < tw - inset; i++) {
        const u = i / (tw - 1);
        let col = top[3];
        if (u < 0.3) col = top[4] || top[3];
        if (u > 0.65) col = top[2];
        if (y === tH - 1) col = top[1];
        fill(bx + i + (y < 3 ? lean : 0), ty + y, 1, 1, col);
      }
    }
    if (cfg.shirt) { fill(bx + 2 + lean, ty, 3, 2, cfg.shirt); fill(bx + 3 + lean, ty + 2, 1, 2, cfg.shirt); }
    if (cfg.tie) fill(bx + 3 + lean, ty + 1, 1, 5, cfg.tie);
    if (cfg.extraBody) cfg.extraBody(x, { fx: bx, ty, tw, sit, frame });
    // голова
    const hx = bx + Math.floor(tw / 2) - 4 + lean * 2 + (mode === 'murmur' ? hShake : 0), hy = ty - 8 + (mode === 'laugh' && ph ? 0 : 0);
    for (let j = 0; j < 8; j++) for (let i = 0; i < 7; i++) {
      if ((j === 0 || j === 7) && (i === 0 || i === 6)) continue;
      let col = skin[3];
      if (i >= 5) col = skin[2];
      if (j === 7) col = skin[2];
      fill(hx + i, hy + j, 1, 1, col);
    }
    fill(hx + 1, hy + 2, 1, 2, skin[4]);
    // глаза
    const eyeCol = PAL.outline;
    if (mode === 'laugh' || mode === 'cheer') { fill(hx + 1, hy + 4, 1, 1, eyeCol); fill(hx + 4, hy + 4, 1, 1, eyeCol); fill(hx + 1, hy + 3, 1, 1, skin[2]); }
    else if (mode === 'gasp' || mode === 'bk') { fill(hx + 1, hy + 3, 1, 2, eyeCol); fill(hx + 4, hy + 3, 1, 2, eyeCol); }
    else { fill(hx + 1, hy + 4, 1, 1, eyeCol); fill(hx + 4, hy + 4, 1, 1, eyeCol); }
    if (angry) { fill(hx + 1, hy + 3, 2, 1, PAL.outline); fill(hx + 4, hy + 3, 1, 1, PAL.outline); }
    // рот
    const open = mode === 'talk' ? ph : (mode === 'shout' || mode === 'cheer' || mode === 'laugh' || mode === 'gasp' || mode === 'bk') ? 1 : 0;
    if (open) { fill(hx + 2, hy + 6, 2, 1, R.red[0]); if (mode === 'shout' || mode === 'laugh' || mode === 'cheer') fill(hx + 2, hy + 5, 2, 1, R.red[1]); }
    else fill(hx + 2, hy + 6, 2, 1, skin[1]);
    if (cfg.hairDraw) cfg.hairDraw(x, hx, hy, frame, pose, mode);
    // руки
    const armY = ty + 1, aL = bx - 1, aR = bx + tw - 1;
    const sleeve = (xx, yy, w, h, lit) => fill(xx, yy, w, h, lit ? top[3] : top[2]);
    const handAt = (xx, yy, lit) => { fill(xx, yy, 2, 2, lit ? skin[3] : skin[2]); fill(xx, yy, 1, 1, lit ? skin[4] : skin[3]); };
    const down = (side) => {
      const ax = side ? aR : aL, h = sit ? 7 : 8;
      sleeve(ax, armY, 2, h, !side); handAt(ax, armY + h, !side);
    };
    const upTo = (side, hx2, hy2) => { // рука от плеча к точке (кисть)
      const ax = side ? aR : aL;
      const sx = ax, sy = armY + 1;
      const n = Math.max(Math.abs(hx2 - sx), Math.abs(hy2 - sy));
      for (let k = 0; k <= n; k++) {
        const xx = Math.round(sx + (hx2 - sx) * k / (n || 1)), yy = Math.round(sy + (hy2 - sy) * k / (n || 1));
        sleeve(xx, yy, 2, 2, !side);
      }
      handAt(hx2, hy2, !side);
    };
    switch (mode) {
      case 'talk':
        down(0);
        if (ph) upTo(1, hx - 2, ty + 3); else upTo(1, hx - 1, ty + 5);
        break;
      case 'whisper': down(1); upTo(0, hx - 1, hy + 5); break;
      case 'gasp': upTo(0, hx - 1, hy + 5); upTo(1, hx + 5, hy + 5); break;
      case 'murmur': down(0); down(1); break;
      case 'angry': down(0); upTo(1, aR + 1, hy - 4 + (ph ? 0 : 1)); break;
      case 'bk': upTo(0, hx - 1, hy + 2); upTo(1, hx + 6, hy + 2); break;
      case 'cheer': upTo(0, aL - 2, hy - 4); upTo(1, aR + 2, hy - 4); break;
      case 'clap':
        if (ph) { upTo(0, hx + 1, ty + 3); upTo(1, hx + 3, ty + 3); }
        else { upTo(0, hx - 1, ty + 2); upTo(1, hx + 5, ty + 2); }
        break;
      case 'laugh': upTo(0, hx + 1, ty + 6); down(1); break;
      case 'shout': down(1); upTo(0, hx - 2, hy + 5); fill(hx - 1, hy + 4, 1, 3, skin[3]); break;
      default: down(0); down(1);
    }
    if (cfg.extra) cfg.extra(x, { fx: bx, ty, tw, hx, hy, sit, talk: mode === 'talk', frame, armY, mode, ph });
    return G.outlineSprite(c, PAL.outline);
  }
  return {
    draw(ctx, x, y, o) {
      o = o || {};
      const pose = o.pose === 'sit' ? 'sit' : 'stand';
      const t = o.t || 0;
      let frame = (Math.floor(t * 0.7 + (cfg.seed || 0) * 2) % 2);
      let mode = 'idle', ph = 0;
      if (o.react) {
        mode = o.react; const rt = o.reactT === undefined ? t : o.reactT;
        const sp = { whisper: 2, gasp: 7, murmur: 5, angry: 9, cheer: 5, clap: 7, laugh: 8, shout: 3 }[mode] || 4;
        ph = Math.floor(rt * sp) % 2;
        if (mode === 'gasp' && rt > 0.6) ph = 1;
        frame = 0;
      } else if (o.anim === 'breakdown' || o.emo === 'breakdown') { mode = 'bk'; ph = Math.floor(t * 10) % 2; frame = 0; }
      else if (o.talking) { mode = 'talk'; ph = Math.floor(t * 4) % 2; }
      const k = pose + frame + mode + ph;
      const spr = cache[k] || (cache[k] = build(pose, frame, mode, ph));
      const flip = o.dir === 'r';
      G.blit(ctx, spr, x - 12, y - (pose === 'sit' ? 33 : 37), flip);
    },
  };
}
/* причёски для изометрии */
function isoHair(ramp, style) {
  return function (x, hx, hy) {
    const H = ramp;
    const f = (i, j, col) => { x.fillStyle = col; x.fillRect(hx + i, hy + j, 1, 1); };
    if (style === 'bald') {
      for (let i = 3; i < 7; i++) f(i, 3, H[2]); f(6, 4, H[2]); f(6, 5, H[1]);
      return;
    }
    if (style === 'short' || style === 'curly' || style === 'slick' || style === 'messy') {
      for (let i = 0; i < 7; i++) f(i, 0, H[3]);
      for (let i = 1; i < 7; i++) f(i, 1, H[2]);
      for (let i = 4; i < 7; i++) { f(i, 2, H[2]); f(i, 3, H[1]); }
      f(-1, 1, H[2]); f(7, 1, H[1]); f(7, 2, H[1]);
      if (style === 'curly') { f(1, -1, H[2]); f(3, -1, H[3]); f(5, -1, H[2]); f(0, 2, H[2]); }
      if (style === 'messy') { f(0, -1, H[3]); f(3, -1, H[2]); f(6, -1, H[3]); f(-1, 0, H[2]); f(7, 0, H[2]); }
      if (style === 'slick') { f(1, 0, H[4] || H[3]); f(2, 0, H[4] || H[3]); }
      return;
    }
    if (style === 'bob' || style === 'long') {
      for (let i = -1; i < 8; i++) f(i, 0, H[3]);
      for (let i = -1; i < 8; i++) f(i, 1, H[2]);
      for (let j = 2; j < (style === 'long' ? 10 : 7); j++) { f(-1, j, H[2]); f(5, j, H[2]); f(6, j, H[1]); f(7, j, H[1]); }
      f(0, 2, H[2]); f(1, 2, H[3]);
      return;
    }
    if (style === 'bun') {
      for (let i = 0; i < 7; i++) f(i, 0, H[3]);
      for (let i = 0; i < 7; i++) f(i, 1, H[2]);
      for (let i = 4; i < 7; i++) f(i, 2, H[2]);
      f(5, -2, H[3]); f(6, -2, H[2]); f(4, -1, H[3]); f(5, -1, H[3]); f(6, -1, H[2]); f(7, -1, H[1]);
      return;
    }
  };
}

/* ====================== СЭМЮЭЛ ЛОМАКС ====================== */
(function () {
  const sk = R.skinL, hb = R.hairBrown;
  const cd = [R.wood[1], R.wood[3], R.stone[2], R.stone[3], R.stone[4], R.stone[5]]; // кардиган (беж)
  const sh = R.blue;
  const HX = 21, HY = 7;
  const pal = { sk, lash: hb[0], iris: hb[3], pupil: R.neutral[0], brow: hb[1], brow2: hb[2] };
  const HAIR = [
    '..........c..d',
    '.......cd.cdd.dc..c',
    '.....cddcdeedddddccb',
    '....cdeedddeeddddddcccb',
    '...cdeeddddeddddddddccbb',
    '..cdeedddddddddddddcccbb',
    '.cddeddcdddcddddddccccbbb',
    '.cdcddcdcddcdcdddcccccbbb',
    '..cdc.dcdcdcdccdcccccbbbb',
    '..c.c..dc.cdc.cccccccbbbb',
    '...c...c...c...ccccccbbbb',
    '...............cccccbbbbb',
    '................ccccbbbb',
    '..............c..cccbbbb',
    '..............b.....cbbb',
    '..............b.....cbbb',
    '....................bbbb',
    '....................bbb',
    '...................bbb',
    '..................bbb',
  ];
  const hk = { a: hb[0], b: hb[1], c: hb[2], d: hb[3], e: hb[4] };
  function head(c) {
    drawFace(c, HX, HY, 'M', sk, (c, hx, hy) => {
      // худые щёки: впадина под скулой
      px(c, hx + 11, hy + 15, sk[2]); px(c, hx + 12, hy + 16, sk[2]);
    });
    map(c, HX - 2, HY - 4, HAIR, hk);
  }
  function glasses(c) {
    const g = R.gold[1], g2 = R.gold[2];
    const x = HX, y = HY;
    // ближнее стекло
    hl(c, x + 8, x + 11, y + 9, g2); hl(c, x + 8, x + 11, y + 13, g);
    vl(c, x + 7, y + 10, y + 12, g); vl(c, x + 12, y + 10, y + 12, g);
    // дальнее
    hl(c, x + 2, x + 4, y + 9, g2); hl(c, x + 2, x + 4, y + 13, g);
    vl(c, x + 1, y + 10, y + 12, g); vl(c, x + 5, y + 10, y + 12, g);
    px(c, x + 6, y + 10, g2); // перемычка
    hl(c, x + 13, x + 14, y + 10, g); // дужка
    px(c, x + 8, y + 10, PAL.white); px(c, x + 2, y + 10, R.blue[6]);
  }
  function body(c, pose) {
    c.drawImage(outlined(x => {
      drawNeck(x, 30, 36, 25, 33, sk);
      // рубашка под горлом + воротник
      poly(x, [[28, 31], [38, 31], [36, 40], [31, 40]], sh[5]);
      poly(x, [[27, 30], [32, 31], [30, 35]], sh[6]); poly(x, [[33, 31], [38, 30], [36, 35]], sh[4]);
      // кардиган
      const pts = [[25, 31], [41, 31], [52, 35], [55, 38], [56, 46], [53, 74], [15, 74], [11, 46], [12, 38], [15, 35]];
      poly(x, pts, cd[3]);
      poly(x, [[44, 33], [52, 35], [55, 38], [56, 46], [53, 74], [46, 74], [45, 50]], cd[2]);
      poly(x, [[25, 31], [15, 35], [12, 38], [14, 38], [17, 36], [26, 33]], cd[4]);
      hl(x, 15, 22, 35, cd[5]);
      // V-вырез и планка
      poly(x, [[28, 31], [37, 31], [33, 46], [32, 46]], sh[5]);
      line(x, [28, 31], [32, 47], cd[4]); line(x, [27, 31], [31, 47], cd[4]);
      line(x, [37, 31], [33, 47], cd[2]); line(x, [38, 31], [34, 47], cd[1]);
      vl(x, 32, 47, 74, cd[2]); vl(x, 33, 47, 74, cd[1]);
      for (const by of [50, 56, 62]) { px(x, 33, by, R.wood[2]); px(x, 32, by, R.wood[4]); }
      // рёбра вязки по низу
      for (let i = 16; i < 52; i += 2) px(x, i, 70, cd[2]);
      // складки у подмышек
      line(x, [17, 44], [20, 49], cd[2]); line(x, [48, 44], [45, 50], cd[1]);
    }), 0, 0);
    // руки
    c.drawImage(outlined(x => {
      if (pose !== 'fid') {
        // дальняя рука: плечо -> локоть -> к центру
        limb(x, [14, 38], [12, 53], 8, 8, cd[3]);
        limb(x, [12, 53], [25, 55], 8, 7, cd[3]);
        hl(x, 11, 15, 38, cd[4]); vl(x, 10, 40, 50, cd[4]);
        line(x, [13, 50], [22, 52], cd[4]);
        hl(x, 22, 26, 51, cd[2]);
      }
      limb(x, [52, 38], [54, 52], 9, 9, cd[2]);
      limb(x, [54, 53], [41, 55], 8, 7, cd[2]);
      vl(x, 50, 39, 48, cd[3]); line(x, [47, 51], [41, 52], cd[3]);
      line(x, [55, 48], [52, 52], cd[1]);
    }), 0, 0);
    c.drawImage(outlined(x => {
      if (pose !== 'fid') drawHand(x, 25, 50, 'clasp', sk);
      drawHand(x, 33, 51, 'rest', sk);
    }), 0, 0);
  }
  /* фиджет: поправляет очки указательным пальцем (дальняя рука) */
  function fidArm(c, k) {
    c.drawImage(outlined(x => {
      const hx = k === 2 ? 25 : 22, hy = k === 2 ? 25 : 38;
      limb(x, [14, 38], [13, 52], 8, 8, cd[3]);
      limb(x, [13, 52], [hx + 2, hy + 6], 8, 7, cd[3]);
      hl(x, 11, 15, 38, cd[4]);
      line(x, [12, 50], [hx, hy + 8], cd[4]);
      map(x, hx, hy, k === 2 ? ['.4.', '.5.', '.43', '5443', '44443', '34443', '.333'] : ['.44.', '5443', '44443', '34443', '.333'],
        { 3: sk[2], 4: sk[3], 5: sk[4] });
    }), 0, 0);
  }
  makeChar({
    id: 'lomax', name: 'Сэмюэл Ломакс', voice: 'mid', emos: DEF_EMOS, seed: 3,
    iso: { skin: sk, top: [R.stone[0], R.stone[1], R.stone[2], R.stone[3], R.stone[4], R.stone[5]], pants: R.wood, shoes: R.wood[0], build: 'thin', seed: 0.3, shirt: R.blue[5],
      hairDraw: isoHair(hb, 'messy'),
      extra(x, f) { x.fillStyle = R.gold[2]; x.fillRect(f.hx, f.hy + 4, 3, 1); x.fillRect(f.hx + 3, f.hy + 4, 3, 1); } },
    fidEmos: ['normal', 'worried', 'hopeful'],
    parts(P) {
      P.add('body/rest', c => body(c, 'rest'), { raw: true });
      P.add('body/fid', c => body(c, 'fid'), { raw: true });
      P.add('arm/fid1', c => fidArm(c, 1), { raw: true });
      P.add('arm/fid2', c => fidArm(c, 2), { raw: true });
      P.add('head', head);
      P.add('glasses', glasses, { raw: true });
      P.add('tears', c => { px(c, HX + 8, HY + 12, R.blue[6]); vl(c, HX + 9, HY + 13, HY + 15, R.blue[5]); px(c, HX + 3, HY + 13, R.blue[5]); }, { raw: true });
      P.add('sweat', c => sweat(c, HX + 3, HY + 3), { raw: true });
      faceParts(P, HX, HY, pal);
    },
    layers(st) {
      const sp = FACESPEC[st.emo];
      const fs = fidStage(st.fid);
      const L = [[fs ? 'body/fid' : 'body/rest'], ['head']];
      const hy = st.emo === 'worried' ? 1 : 0;
      L.push(...faceLayers(st, sp, 0, 0));
      L.push(['glasses']);
      if (st.emo === 'relieved') L.push(['tears']);
      if (st.emo === 'worried') L.push(['sweat']);
      if (fs) L.push(['arm/fid' + fs]);
      return L;
    },
  });
})();

/* все ключи бюстов — для запекания */
G.prebuild(() => { for (const P of BUST_IDS) P.all(); });
})();
