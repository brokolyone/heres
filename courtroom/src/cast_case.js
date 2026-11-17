/* =====================================================================
   CAST_CASE — персонажи дел: lomax, hollis, whitfield, crane, park,
   bell, doyle, morales, holloway.
   Бюсты 112x130 (3/4, лицом влево), изометрия ~12x26.
   Всё рисуется попиксельно: маски-формы -> плоская заливка тонами рампы
   по направлению света (сверху слева) -> швы/падающие тени -> контур.
   Лица: карты-строки глаз/ртов + процедурные брови, нос, скулы.
   ===================================================================== */
(function () {
'use strict';
const G = window.G;
const R = G.RAMP, PAL = G.PAL;
const BW = 112, BH = 130;

/* ---------------------------------------------------------------------
   ФОРМЫ (для масок)
   --------------------------------------------------------------------- */
const E = (cx, cy, rx, ry) => ['e', cx, cy, rx, ry];
const EP = E;
const P = (...pts) => ['p', pts];
const Rc = (x, y, w, h) => ['r', x, y, w, h];
const C = (x0, y0, x1, y1, x2, y2, w0, w1) => ['c', x0, y0, x1, y1, x2, y2, w0, w1 === undefined ? w0 : w1];
const SUB = s => ['-', s];
const F = fn => ['f', fn];

const scratch = G.makeCanvas(BW + 8, BH + 8);
const sc = scratch.getContext('2d');

function qpt(s, t) {
  const a = 1 - t;
  return [a * a * s[1] + 2 * a * t * s[3] + t * t * s[5], a * a * s[2] + 2 * a * t * s[4] + t * t * s[6]];
}
function drawShape(c, s) {
  const W = '#ffffff';
  switch (s[0]) {
    case 'e': G.ellipse(c, Math.round(s[1]), Math.round(s[2]), Math.round(s[3]), Math.round(s[4]), W); break;
    case 'p': G.poly(c, s[1], W); break;
    case 'r': G.rect(c, Math.round(s[1]), Math.round(s[2]), Math.round(s[3]), Math.round(s[4]), W); break;
    case 'l': G.line(c, s[1], s[2], s[3], s[4], W); break;
    case 'c': {
      const len = Math.hypot(s[3] - s[1], s[4] - s[2]) + Math.hypot(s[5] - s[3], s[6] - s[4]);
      const n = Math.max(2, Math.ceil(len * 1.6));
      for (let k = 0; k <= n; k++) {
        const t = k / n, p = qpt(s, t), w = s[7] + (s[8] - s[7]) * t;
        if (w < 1.5) G.rect(c, Math.round(p[0]), Math.round(p[1]), 1, 1, W);
        else if (w < 2.5) G.rect(c, Math.round(p[0] - 0.5), Math.round(p[1] - 0.5), 2, 2, W);
        else if (w < 3.5) { const x = Math.round(p[0]), y = Math.round(p[1]); G.rect(c, x - 1, y, 3, 1, W); G.rect(c, x, y - 1, 1, 3, W); G.rect(c, x - 1, y - 1, 2, 2, W); }
        else G.ellipse(c, Math.round(p[0]), Math.round(p[1]), Math.round(w / 2 - 0.4), Math.round(w / 2 - 0.4), W);
      }
      break;
    }
    case '-':
      c.globalCompositeOperation = 'destination-out';
      drawShape(c, s[1]);
      c.globalCompositeOperation = 'source-over';
      break;
  }
}

/* ---------------------------------------------------------------------
   PAINTER: буфер тонов рамп + слои-части
   --------------------------------------------------------------------- */
function Painter(w, h) {
  this.w = w; this.h = h;
  const n = w * h;
  this.col = new Array(n).fill(null);
  this.ramp = new Array(n).fill(null);
  this.tone = new Int8Array(n);
  this.pid = new Int16Array(n).fill(-1);
  this.n = 0;
}
Painter.prototype.mask = function (shapes) {
  const w = this.w, h = this.h;
  sc.setTransform(1, 0, 0, 1, 0, 0);
  sc.clearRect(0, 0, scratch.width, scratch.height);
  const fns = [];
  for (const s of shapes) { if (!s) continue; if (s[0] === 'f') fns.push(s[1]); else drawShape(sc, s); }
  const d = sc.getImageData(0, 0, w, h).data;
  const m = new Uint8Array(w * h);
  for (let i = 0; i < w * h; i++) m[i] = d[i * 4 + 3] > 0 ? 1 : 0;
  for (const fn of fns) for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) if (fn(x, y)) m[y * w + x] = 1;
  return m;
};
Painter.prototype.filled = function (x, y) {
  if (x < 0 || y < 0 || x >= this.w || y >= this.h) return false;
  const i = y * this.w + x; return this.pid[i] !== -1;
};
/* o = {s:shapes, ramp, base, shade(x,y,d,t)->tone, over, cast, edge, lx, ly, hiT, shT, sh2T, clip:maskFn} */
Painter.prototype.part = function (o) {
  const w = this.w, h = this.h;
  const m = o.m || this.mask(o.s);
  if (o.over) for (let i = 0; i < w * h; i++) if (this.pid[i] === -1) m[i] = 0;
  if (o.under) for (let i = 0; i < w * h; i++) if (this.pid[i] !== -1) m[i] = 0;
  if (o.clip) for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) if (!o.clip(x, y)) m[y * w + x] = 0;
  const id = this.n++;
  const dl = new Int16Array(w * h), dr = new Int16Array(w * h), du = new Int16Array(w * h), dd = new Int16Array(w * h);
  for (let y = 0; y < h; y++) {
    let r = 0;
    for (let x = 0; x < w; x++) { const i = y * w + x; if (m[i]) { dl[i] = r; r++; } else r = 0; }
    r = 0;
    for (let x = w - 1; x >= 0; x--) { const i = y * w + x; if (m[i]) { dr[i] = r; r++; } else r = 0; }
  }
  for (let x = 0; x < w; x++) {
    let r = 0;
    for (let y = 0; y < h; y++) { const i = y * w + x; if (m[i]) { du[i] = r; r++; } else r = 0; }
    r = 0;
    for (let y = h - 1; y >= 0; y--) { const i = y * w + x; if (m[i]) { dd[i] = r; r++; } else r = 0; }
  }
  const ramp = o.ramp, base = o.base === undefined ? Math.floor(ramp.length / 2) : o.base;
  const lx = o.lx === undefined ? 0.62 : o.lx, ly = o.ly === undefined ? 0.38 : o.ly;
  const hiT = o.hiT === undefined ? 0.8 : o.hiT, shT = o.shT === undefined ? 0.36 : o.shT, sh2T = o.sh2T === undefined ? 0.1 : o.sh2T;
  const d = {};
  // падающая тень на то, что уже нарисовано (вниз-вправо от новой формы)
  const cast = o.cast === undefined ? 1 : o.cast;
  if (cast > 0) {
    const done = new Uint8Array(w * h);
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      const i = y * w + x;
      if (m[i] || this.pid[i] < 0 || !this.ramp[i]) continue;
      let hit = false;
      for (let k = 1; k <= cast && !hit; k++) {
        if ((x - k >= 0 && m[i - k] && !o.castY) || (y - k >= 0 && m[i - k * w])) hit = true;
      }
      if (hit && !done[i]) { done[i] = 1; this.tone[i] = Math.max(0, this.tone[i] - 1); }
    }
  }
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const i = y * w + x;
    if (!m[i]) continue;
    d.dl = dl[i]; d.dr = dr[i]; d.du = du[i]; d.dd = dd[i];
    d.u = (d.dl + 0.5) / (d.dl + d.dr + 1); d.v = (d.du + 0.5) / (d.du + d.dd + 1);
    d.L = 1 - (lx * d.u + ly * d.v);
    let t = base;
    if (d.L > hiT) t++;
    if (d.L < shT) t--;
    if (d.L < sh2T) t--;
    if (o.shade) t = o.shade(x, y, d, t, base);
    if (t === null || t === undefined) continue;
    t = G.clamp(t, 0, ramp.length - 1);
    this.ramp[i] = ramp; this.tone[i] = t; this.col[i] = null; this.pid[i] = id;
  }
  // край передней формы, касающийся задних форм снизу/справа — на тон темнее
  if (o.edge !== false) {
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      const i = y * w + x;
      if (!m[i] || this.pid[i] !== id) continue;
      const rN = x + 1 < w && !m[i + 1] && this.pid[i + 1] >= 0;
      const dN = y + 1 < h && !m[i + w] && this.pid[i + w] >= 0;
      if (rN || dN) this.tone[i] = Math.max(0, this.tone[i] - 1);
    }
  }
  return m;
};
Painter.prototype.set = function (x, y, ramp, tone) {
  x = Math.round(x); y = Math.round(y);
  if (x < 0 || y < 0 || x >= this.w || y >= this.h) return;
  const i = y * this.w + x;
  this.ramp[i] = ramp; this.tone[i] = G.clamp(tone, 0, ramp.length - 1); this.col[i] = null;
  if (this.pid[i] === -1) this.pid[i] = 999;
};
Painter.prototype.px = function (x, y, col) {
  x = Math.round(x); y = Math.round(y);
  if (x < 0 || y < 0 || x >= this.w || y >= this.h) return;
  const i = y * this.w + x;
  this.col[i] = col; this.ramp[i] = null; if (this.pid[i] === -1) this.pid[i] = 998;
};
/* сдвинуть тон уже нарисованного пикселя (только поверх) */
Painter.prototype.shift = function (x, y, dt, onlyRamp) {
  x = Math.round(x); y = Math.round(y);
  if (x < 0 || y < 0 || x >= this.w || y >= this.h) return;
  const i = y * this.w + x;
  if (!this.ramp[i]) return;
  if (onlyRamp && this.ramp[i] !== onlyRamp) return;
  this.tone[i] = G.clamp(this.tone[i] + dt, 0, this.ramp[i].length - 1);
};
Painter.prototype.toneAt = function (x, y) { const i = y * this.w + x; return this.tone[i]; };
/* сдвинуть тон вдоль кривой (пряди волос, складки) */
Painter.prototype.stroke = function (shape, dt, onlyRamp) {
  const m = this.mask([shape]);
  for (let i = 0; i < m.length; i++) if (m[i] && this.ramp[i] && (!onlyRamp || this.ramp[i] === onlyRamp))
    this.tone[i] = G.clamp(this.tone[i] + dt, 0, this.ramp[i].length - 1);
};
/* заменить тон вдоль кривой на абсолютный */
Painter.prototype.strokeT = function (shape, tone, onlyRamp) {
  const m = this.mask([shape]);
  for (let i = 0; i < m.length; i++) if (m[i] && this.ramp[i] && (!onlyRamp || this.ramp[i] === onlyRamp))
    this.tone[i] = G.clamp(tone, 0, this.ramp[i].length - 1);
};
Painter.prototype.erase = function (shapes) {
  const m = this.mask(shapes);
  for (let i = 0; i < m.length; i++) if (m[i]) { this.pid[i] = -1; this.ramp[i] = null; this.col[i] = null; }
};
Painter.prototype.render = function (noOutline) {
  const w = this.w, h = this.h;
  const c = G.makeCanvas(w, h + 2);
  const x = c.getContext('2d');
  const colAt = i => this.col[i] || (this.ramp[i] ? this.ramp[i][this.tone[i]] : null);
  for (let y = 0; y < h; y++) for (let xx = 0; xx < w; xx++) {
    const i = y * w + xx, col = colAt(i);
    if (col) { x.fillStyle = col; x.fillRect(xx, y, 1, 1); }
  }
  if (!noOutline) {
    for (let y = 0; y < h; y++) for (let xx = 0; xx < w; xx++) {
      const i = y * w + xx;
      if (this.pid[i] !== -1) continue;
      const L = xx > 0 && this.pid[i - 1] !== -1, Rr = xx < w - 1 && this.pid[i + 1] !== -1;
      const U = y > 0 && this.pid[i - w] !== -1, D = y < h - 1 && this.pid[i + w] !== -1;
      if (!(L || Rr || U || D)) continue;
      let col = PAL.outline;
      // освещённая сторона (сверху-слева от формы): контур тёмным тоном самой рампы
      if (!L && !U && (Rr || D)) {
        const j = Rr ? i + 1 : i + w;
        if (this.ramp[j]) col = this.ramp[j][0];
      }
      x.fillStyle = col; x.fillRect(xx, y, 1, 1);
    }
  }
  // продлить нижний край на 2 строки (для дыхания)
  x.drawImage(c, 0, h - 1, w, 1, 0, h, w, 1);
  x.drawImage(c, 0, h - 1, w, 1, 0, h + 1, w, 1);
  return c;
};

/* ---------------------------------------------------------------------
   Карты-строки поверх готового спрайта
   --------------------------------------------------------------------- */
function mapAt(c, rows, x, y, key, mirror) {
  for (let j = 0; j < rows.length; j++) {
    const r = rows[j], n = r.length;
    for (let i = 0; i < n; i++) {
      const ch = r[i];
      if (ch === '.' || ch === ' ') continue;
      const col = key[ch];
      if (!col) continue;
      c.fillStyle = col;
      c.fillRect(x + (mirror ? n - 1 - i : i), y + j, 1, 1);
    }
  }
}
function px(c, x, y, col) { c.fillStyle = col; c.fillRect(Math.round(x), Math.round(y), 1, 1); }

/* ---------------------------------------------------------------------
   ГЛАЗА: near — ближний (справа от носа, 7x5), far — дальний (4x5)
   k ресницы/веко, w белок, W белок в тени, I радужка, i тёмная, j светлая,
   p зрачок, h блик, u складка века, s тень под глазом, S кожа
   --------------------------------------------------------------------- */
const EYES = {
  open: {
    n: ['..uuuu.',
        '.kkkkkk',
        'kwhpIWk',
        '.wIiIw.',
        '..sss..'],
    f: ['.uu.',
        'kkkk',
        'hpWk',
        'Iiw.',
        '.ss.'] },
  look: { // смотрит прямо на собеседника, чуть ниже
    n: ['..uuuu.',
        '.kkkkkk',
        'kwIpIWk',
        '.wjhiw.',
        '..sss..'],
    f: ['.uu.',
        'kkkk',
        'IpWk',
        'hiw.',
        '.ss.'] },
  half: {
    n: ['.......',
        '..uuuu.',
        '.kkkkkk',
        'kwIiIWk',
        '..sss..'],
    f: ['....',
        '.uu.',
        'kkkk',
        'Iiwk',
        '.ss.'] },
  down: {
    n: ['.......',
        '..uuuu.',
        '.kkkkkk',
        'kwIpiWk',
        '.ssss..'],
    f: ['....',
        '.uu.',
        'kkkk',
        'Ipwk',
        '.ss.'] },
  side: { // косится вправо (в сторону), нервно
    n: ['..uuuu.',
        '.kkkkkk',
        'kwWwhpk',
        '.wwWIi.',
        '..sss..'],
    f: ['.uu.',
        'kkkk',
        'wWhk',
        'wIi.',
        '.ss.'] },
  wide: {
    n: ['.kkkkk.',
        'kwwwwwk',
        'kwIpwWk',
        'kwwwwWk',
        '.kkkkk.'],
    f: ['kkk.',
        'wwwk',
        'Ipwk',
        'wwWk',
        'kkk.'] },
  tiny: { // шок: маленькие зрачки
    n: ['.kkkkk.',
        'kwwwwwk',
        'kwwpwWk',
        'kwwwwWk',
        '.kkkkk.'],
    f: ['kkk.',
        'wwwk',
        'wpwk',
        'wwWk',
        'kkk.'] },
  angry: {
    n: ['.......',
        '...kkkk',
        'kkkhpWk',
        '.wIiIw.',
        '..sss..'],
    f: ['....',
        'kk..',
        'hpkk',
        'Iiw.',
        '.ss.'] },
  closed: {
    n: ['.......',
        '..uuuu.',
        '.uuuuuu',
        'kkkkkkk',
        '..sss..'],
    f: ['....',
        '.uu.',
        'uuuu',
        'kkkk',
        '.ss.'] },
  happy: {
    n: ['.......',
        '...kkk.',
        '..k...k',
        '.k.....',
        '.......'],
    f: ['....',
        '.kk.',
        'k..k',
        '....',
        '....'] },
  squeeze: { // зажмурился
    n: ['.......',
        '.kk....',
        '...kkkk',
        '.kk....',
        '.......'],
    f: ['....',
        '..kk',
        'kk..',
        '..kk',
        '....'] },
  blank: { // пустой взгляд (шок-осознание)
    n: ['..uuuu.',
        '.kkkkkk',
        'kwwwIWk',
        '.wwIpw.',
        '..sss..'],
    f: ['.uu.',
        'kkkk',
        'wwIk',
        'wIp.',
        '.ss.'] },
};
/* карты рта, якорь — левый верхний угол (9x5). Дальний угол слева. */
const MOUTHS = {
  closed:  ['.........', '..kkkkk..', '...lll...', '...sss...', '.........'],
  flat:    ['.........', '.kkkkkkk.', '..llll...', '...ss....', '.........'],
  smile:   ['.........', '.k.....k.', '..kkkkk..', '...llll..', '....ss...'],
  bigsmile:['.........', '.k.....kk', '.ktttttk.', '..kdddk..', '...lll...'],
  smirk:   ['.......k.', '..kkkkk..', '...lll...', '...ss....', '.........'],
  frown:   ['.........', '...kkk...', '..k...k..', '...lll...', '.........'],
  wobble:  ['.........', '..k.kk.k.', '...k..k..', '...lll...', '.........'],
  grit:    ['.........', '.kkkkkkk.', '.kttTttk.', '.kkkkkkk.', '..sss....'],
  o:       ['...kk....', '..kddk...', '..kddk...', '...kk....', '...ss....'],
  O:       ['..kkkk...', '.kddddk..', '.kdgddk..', '.kddddk..', '..kkkk...'],
  half:    ['.........', '..kkkkk..', '..kdddk..', '...kkk...', '...ss....'],
  open:    ['..kkkkk..', '.kttttdk.', '.kddgddk.', '..kkkkk..', '...sss...'],
  halfS:   ['.........', '.k.....k.', '..kdddk..', '...kkk...', '...ss....'],
  openS:   ['.k.....k.', '.kttttdk.', '..kdgdk..', '...kkk...', '...ss....'],
  gritO:   ['.kkkkkk..', 'kttttttk.', 'kdddddk..', '.kTTTTk..', '..kkkk...'],
  wail:    ['..kkkk...', '.kTTTTk..', 'kddddddk.', '.kdgggk..', '..kkkk...'],
};

/* ---------------------------------------------------------------------
   Генератор персонажа
   --------------------------------------------------------------------- */
function blinkState(t, seed) {
  const per = 3.4 + (seed % 5) * 0.17;
  const ph = (t + seed * 0.731) % per;
  if (ph < 0.05) return 'half';
  if (ph < 0.15) return 'closed';
  if (ph < 0.2) return 'half';
  // иногда двойное моргание
  if ((Math.floor((t + seed * 0.731) / per) % 3 === 1) && ph > 0.3 && ph < 0.4) return 'closed';
  return 'open';
}

function makeBust(def) {
  const cacheBase = {}, cacheFull = {};
  const NBK = def.bkFrames || 8;
  const BKD = def.bkDur || 1.2;
  const NF = 8;
  const FDUR = def.fidDur || 1.8, FPER = def.fidPer || 8.5;
  function baseFor(emo, bk, fid) {
    const k = emo + '|' + bk + '|' + fid;
    if (cacheBase[k]) return cacheBase[k];
    const p = new Painter(BW, BH);
    const st = { emo, bk, hx: 0, hy: 0, fid, f: fid >= 0 ? (fid + 0.5) / NF : -1 };
    // k: подъём руки 0..1..0, a: фаза действия в удержании 0..1
    if (fid >= 0) { const f = st.f; st.fk = f < 0.3 ? G.ease.inOut(f / 0.3) : f > 0.72 ? G.ease.inOut((1 - f) / 0.28) : 1; st.fa = G.clamp((f - 0.3) / 0.42, 0, 1); }
    else { st.fk = 0; st.fa = 0; }
    def.build(p, st);
    const cnv = p.render();
    if (def.after) def.after(cnv.getContext('2d'), st);
    return (cacheBase[k] = { cnv, st });
  }
  function frameFor(emo, bk, blink, mouthF, fid) {
    fid = fid === undefined ? -1 : fid;
    const k = emo + '|' + bk + '|' + blink + '|' + mouthF + '|' + fid;
    if (cacheFull[k]) return cacheFull[k];
    const b = baseFor(emo, bk, fid);
    const c = G.makeCanvas(BW, BH + 2);
    const x = c.getContext('2d');
    x.drawImage(b.cnv, 0, 0);
    const st = Object.assign({}, b.st, { blink, mouthF });
    const fc = def.face(st);
    if (fid >= 0 && def.fidFace) def.fidFace(st, fc);
    drawFace(x, def, st, fc);
    if (def.post) def.post(x, st, fc);
    if (def.postTop) def.postTop(x, st, fc);
    return (cacheFull[k] = c);
  }
  return {
    w: BW, h: BH,
    frameFor,
    draw(ctx, x, y, o) {
      o = o || {};
      const t = o.t || 0;
      let emo = o.emo && def.emos.indexOf(o.emo) >= 0 ? o.emo : 'normal';
      let bk = -1, dx = 0;
      if (o.anim === 'breakdown' && def.emos.indexOf('breakdown') >= 0) {
        const at = G.clamp(o.animT || 0, 0, BKD - 0.001);
        bk = Math.min(NBK - 1, Math.floor(at / BKD * NBK));
        emo = 'breakdown';
        if (def.shake) dx = def.shake(at / BKD, t);
      } else if (emo === 'breakdown') bk = NBK - 1;
      // привычный жест (fidget): периодически, когда персонаж не говорит
      let fid = -1;
      if (bk < 0 && def.fidEmos && def.fidEmos.indexOf(emo) >= 0) {
        let fp = -1;
        if (o.fidget !== undefined) fp = o.fidget;
        else if (!o.talking) {
          const per = FPER + (def.seed % 3) * 0.9;
          const ph = (t + def.seed * 2.37) % per;
          if (ph < FDUR && t > 1.5) fp = ph / FDUR;
        }
        if (fp >= 0 && fp < 1) fid = Math.min(NF - 1, Math.floor(fp * NF));
      }
      let blink = blinkState(t, def.seed || 1);
      let mouthF = 0;
      if (o.talking && (bk < 0 || bk === NBK - 1)) { const f = Math.floor(t * 8) % 4; mouthF = [0, 1, 2, 1][f]; }
      if (bk >= 0 && bk < NBK - 1) blink = 'open';
      const spr = frameFor(emo, bk, blink, mouthF, fid);
      // дыхание: 1–2 px, своя фаза у каждого
      const amp = def.breath || 1;
      const sv = Math.sin(t * Math.PI * 2 / (def.breathPer || 3.2) + (def.seed || 0) * 1.7);
      const br = amp === 1 ? (sv > 0 ? 1 : 0) : (sv > 0.45 ? 2 : sv > -0.45 ? 1 : 0);
      const hgt = BH + br;
      if (o.flip) {
        ctx.save();
        ctx.translate((x | 0) + BW / 2 - dx, 0); ctx.scale(-1, 1);
        ctx.drawImage(spr, 0, 0, BW, hgt, 0, (y | 0) - hgt, BW, hgt);
        ctx.restore();
      } else {
        ctx.drawImage(spr, 0, 0, BW, hgt, (x | 0) - BW / 2 + dx, (y | 0) - hgt, BW, hgt);
      }
    },
  };
}

/* рука, поднятая из-за нижнего края кадра к точке (hx,hy).
   o: {sleeve, skin, from:[x,y], w, pose:'point'|'flat'|'fist'|'pinch', cuff} */
function armTo(p, hx, hy, o) {
  const fr = o.from, sl = o.sleeve, sk = o.skin;
  const w = o.w || 13;
  const mx = (fr[0] + hx) / 2 + (o.bend || 0), my = Math.max(fr[1], hy) - 4;
  p.part({ s: [E(fr[0], fr[1], Math.round(w / 2) + 1, Math.round(w / 2) + 3), C(fr[0], fr[1], mx, my, hx + (o.wx || 2), hy + 8, w, w - 3)], ramp: sl, base: o.slBase || 3, cast: 2, shT: 0.42, hiT: 0.7 });
  // складки рукава у локтя
  p.stroke(C(fr[0] - 3, fr[1] - 6, mx - 2, my - 2, (mx + hx) / 2, (my + hy) / 2 + 4, 1), -1, sl);
  p.stroke(C(fr[0] + 2, fr[1] - 4, fr[0] - 1, fr[1] - 10, fr[0] - 4, fr[1] - 12, 1), -1, sl);
  if (o.cuff) p.part({ s: [C(hx - 1, hy + 9, hx + 1, hy + 7, hx + 3, hy + 5, 5)], ramp: o.cuff, base: 3, cast: 1 });
  const pose = o.pose || 'flat';
  if (pose === 'point') {
    p.part({ s: [P([hx - 2, hy + 2], [hx + 5, hy], [hx + 7, hy + 4], [hx + 6, hy + 9], [hx, hy + 9], [hx - 2, hy + 6])], ramp: sk, base: 3, cast: 1 });
    p.part({ s: [C(hx, hy + 2, hx - 3, hy - 1, hx - 5, hy - 4, 2)], ramp: sk, base: 3, cast: 1 });
    p.set(hx + 1, hy + 5, sk, 2); p.set(hx + 2, hy + 6, sk, 2);
  } else if (pose === 'pinch') {
    p.part({ s: [P([hx - 1, hy + 1], [hx + 6, hy], [hx + 8, hy + 5], [hx + 6, hy + 9], [hx, hy + 9], [hx - 2, hy + 5])], ramp: sk, base: 3, cast: 1 });
    p.part({ s: [C(hx, hy + 2, hx - 2, hy, hx - 3, hy - 2, 2), C(hx, hy + 4, hx - 3, hy + 3, hx - 4, hy + 1, 2)], ramp: sk, base: 3, cast: 1 });
  } else if (pose === 'fist') {
    p.part({ s: [P([hx - 2, hy], [hx + 6, hy - 1], [hx + 8, hy + 4], [hx + 6, hy + 9], [hx - 1, hy + 9], [hx - 3, hy + 4])], ramp: sk, base: 3, cast: 1 });
    for (let q = 0; q < 3; q++) p.set(hx - 1 + q * 2, hy + 2 + q, sk, 2);
  } else {
    p.part({ s: [P([hx - 3, hy + 1], [hx + 6, hy - 1], [hx + 8, hy + 4], [hx + 6, hy + 10], [hx, hy + 10], [hx - 4, hy + 5])], ramp: sk, base: 3, cast: 1 });
    for (let q = 0; q < 3; q++) p.stroke(['l', hx - 3 + q, hy + 3 + q * 2, hx + 3 + q, hy + 2 + q * 2], -1, sk);
  }
}
const lerpP = (a, b, k) => [Math.round(a[0] + (b[0] - a[0]) * k), Math.round(a[1] + (b[1] - a[1]) * k)];

/* лицо: брови, глаза, рот */
function drawFace(x, def, st, fc) {
  const fp = def.feat;
  const hx = st.hx || 0, hy = st.hy || 0;
  const skin = fp.skin;
  const ir = fp.iris;
  const key = {
    k: fp.lid || PAL.outline, w: R.neutral[8], W: R.neutral[7], I: ir[1], i: ir[0], j: ir[2],
    p: R.neutral[0], h: PAL.white, u: skin[1], s: skin[2], S: skin[3],
  };
  // глаза
  let eyes = fc.eyes || 'open';
  if (st.blink === 'closed' && !fc.noBlink) eyes = (eyes === 'happy' || eyes === 'squeeze') ? eyes : 'closed';
  else if (st.blink === 'half' && !fc.noBlink && (eyes === 'open' || eyes === 'look' || eyes === 'side' || eyes === 'blank')) eyes = 'half';
  const em = EYES[eyes] || EYES.open;
  const nX = fp.eyeN[0] + hx, nY = fp.eyeN[1] + hy, fX = fp.eyeF[0] + hx, fY = fp.eyeF[1] + hy;
  mapAt(x, em.n, nX, nY, key);
  mapAt(x, em.f, fX, fY, key);
  if (fp.lash && eyes !== 'happy' && eyes !== 'squeeze') {
    const ly = (eyes === 'half' || eyes === 'down' || eyes === 'closed') ? 2 : (eyes === 'wide' || eyes === 'tiny') ? 0 : 1;
    px(x, nX + 7, nY + ly - 1, key.k); px(x, nX + 7, nY + ly, key.k);
    px(x, fX - 1, fY + ly, key.k);
  }
  // брови: [inner, outer] смещения по y (минус — вверх)
  const bw = fc.brows || [0, 0];
  const bcol = fp.brow, bcol2 = fp.brow2 || fp.brow;
  const th = fp.browThick || 2;
  const bn = fp.browN, bf = fp.browF;
  const nLen = bn[2], fLen = bf[2];
  for (let i = 0; i < nLen; i++) {
    const t = i / (nLen - 1);
    const arch = fc.flatBrow ? 0 : -Math.round(Math.sin(t * Math.PI) * 0.9);
    const yy = bn[1] + hy + Math.round(bw[0] + (bw[1] - bw[0]) * t) + arch;
    const xx = bn[0] + hx + i;
    px(x, xx, yy, bcol);
    if (th > 1 && i < nLen - 1) px(x, xx, yy + 1, i < 2 ? bcol : bcol2);
  }
  for (let i = 0; i < fLen; i++) {
    const t = i / (fLen - 1); // 0 = внутренний конец (справа)
    const yy = bf[1] + hy + Math.round(bw[0] + (bw[1] - bw[0]) * t);
    const xx = bf[0] + hx + fLen - 1 - i;
    px(x, xx, yy, bcol);
    if (th > 1 && i > 0 && i < fLen - 1) px(x, xx, yy + 1, bcol2);
  }
  // рот
  let mouth = fc.mouth || 'closed';
  if (st.mouthF && fc.talk) mouth = fc.talk[st.mouthF - 1];
  else if (st.mouthF) mouth = st.mouthF === 1 ? 'half' : 'open';
  const mk = {
    k: fp.mouthLine || skin[0], d: R.red[0], t: R.neutral[8], T: R.neutral[6], g: R.red[2],
    l: fp.lipL || skin[4], s: skin[2], L: fp.lip ? fp.lip[1] : skin[1],
  };
  mapAt(x, MOUTHS[mouth] || MOUTHS.closed, fp.mouth[0] + hx, fp.mouth[1] + hy, mk);
  if (fp.lip && mouth !== 'O' && mouth !== 'wail') { // помада: верхняя/нижняя губа
    const m = MOUTHS[mouth] || MOUTHS.closed;
    const mx = fp.mouth[0] + hx, my = fp.mouth[1] + hy;
    for (let j = 0; j < m.length; j++) for (let i = 0; i < 9; i++) {
      if (m[j][i] === 'k') {
        const below = j + 1 < m.length ? m[j + 1][i] : '.';
        if (below === '.' || below === 's' || below === 'l') {
          px(x, mx + i, my + j + 1, fp.lip[2]);
        }
        const above = j > 0 ? m[j - 1][i] : '.';
        if (above === '.' && i > 1 && i < 7) px(x, mx + i, my + j - 1, fp.lip[1]);
      }
    }
  }
}

/* ---------------------------------------------------------------------
   НАБОР ДЕТАЛЕЙ (голова, шея, нос, уши, руки)
   координаты головы: H = {cx, top} — лицо смотрит влево;
   лоб/скулы спереди x≈cx-13, затылок x≈cx+16, подбородок y≈top+36
   --------------------------------------------------------------------- */
function headShapes(H) {
  const cx = H.cx, t = H.top;
  const jw = H.jaw || 0, ch = H.chin || 0, fw = H.fem ? -1 : 0, sk = H.skull || 0;
  const shapes = [
    E(cx + 2 + sk, t + 15, 14 + sk + fw, 15),
    P([cx - 11, t + 4], [cx - 13 - fw * 0, t + 10], [cx - 13, t + 15], [cx - 12, t + 18], [cx - 13, t + 20],
      [cx - 13, t + 24], [cx - 12 - fw, t + 27], [cx - 12 - fw, t + 30], [cx - 10 - fw, t + 33 + ch], [cx - 8 - fw, t + 35 + ch],
      [cx - 5, t + 36 + ch], [cx - 1 + jw * 0.5, t + 36 + ch], [cx + 4 + jw, t + 33 + ch * 0.5], [cx + 9 + jw, t + 29],
      [cx + 12 + jw * 0.6, t + 24], [cx + 14, t + 16], [cx + 12, t + 6]),
  ];
  if (H.jowl) shapes.push(E(cx + 2 + jw, t + 29, 10 + jw, 6));
  return shapes;
}
function head(p, H) {
  const cx = H.cx, t = H.top, sk = H.ramp;
  const sideX = H.sideX || 3;
  p.part({
    s: headShapes(H), ramp: sk, base: 3, cast: 1,
    shade(x, y, d) {
      const rx = x - cx, ry = y - t;
      let tone = 3;
      // боковая плоскость (в тени)
      let bx = sideX;
      if (ry < 12) bx = sideX + 2; else if (ry < 17) bx = sideX + 1;
      else if (ry > 30) bx = sideX - 3; else if (ry > 26) bx = sideX - 1;
      if (rx > bx) tone = 2;
      if (rx > bx + 9 && ry > 20) tone = 1;
      // глазница — лёгкая тень над и под ближним глазом у переносицы
      if (ry >= 15 && ry <= 16 && rx >= -8 && rx <= -6) tone = 2;
      // скула (блик)
      if (ry >= 21 && ry <= 22 && rx >= -10 && rx <= -4) tone = 4;
      if (ry >= 23 && ry <= 23 && rx >= -9 && rx <= -6) tone = 4;
      // щека под скулой — тень (запавшая у худых)
      if (H.gaunt && ry >= 25 && ry <= 29 && rx >= -3 && rx <= 1) tone = 2;
      // лоб
      if (ry >= 3 && ry <= 10 && rx >= -10 && rx <= -1 && d.L > 0.55) tone = 4;
      // подбородок
      if (ry >= 32 + (H.chin || 0) && ry <= 34 + (H.chin || 0) && rx >= -9 && rx <= -6) tone = 4;
      // низ челюсти
      if (d.dd <= 1 && ry > 30) tone = Math.min(tone, 2);
      if (d.dd === 0 && ry > 31 && rx > -6) tone = 1;
      if (H.blush && ry >= 24 && ry <= 26 && ((rx >= -4 && rx <= 0) || (rx >= -12 && rx <= -11)) && ((x + y) & 1) === 0) return null;
      return tone;
    },
  });
  if (H.blush) blushCheeks(p, H, H.blush);
}
function blushCheeks(p, H, ramp) {
  const cx = H.cx, t = H.top;
  for (let y = t + 24; y <= t + 26; y++) for (let x = cx - 4; x <= cx; x++) if (p.filled(x, y)) p.set(x, y, ramp, (x + y) & 1 ? 3 : 4);
  for (let y = t + 24; y <= t + 26; y++) for (let x = cx - 12; x <= cx - 11; x++) if (p.filled(x, y)) p.set(x, y, ramp, (x + y) & 1 ? 3 : 4);
}
/* нос: type 'n' обычный, 'big', 'small', 'sharp', 'round' */
function nose(p, H, type) {
  const cx = H.cx, t = H.top, sk = H.ramp;
  const big = type === 'big' || type === 'round' ? 1 : 0, sm = type === 'small' ? 1 : 0;
  const tipX = cx - 14 - big + sm, tipY = t + 24 + big - sm;
  // выступ за силуэт
  const pts = type === 'sharp'
    ? [[cx - 11, t + 18], [cx - 14, t + 22], [cx - 16, t + 25], [cx - 13, t + 26], [cx - 11, t + 25]]
    : [[cx - 11, t + 18], [cx - 13, t + 21], [tipX - 1, tipY], [tipX, tipY + 2], [cx - 12, t + 26 + big], [cx - 10, t + 25 + big]];
  p.part({ s: [P(...pts)], ramp: sk, base: 3, cast: 0, edge: false,
    shade(x, y) { const ry = y - t; if (ry >= 25 + big) return 2; if (x <= tipX + 1 && ry >= 22) return 4; return 3; } });
  // спинка носа: тень боковой грани
  const bx = cx - 8;
  for (let y = t + 18; y <= t + 23 + big - sm; y++) p.set(bx - Math.floor((y - t - 18) / 2), y, sk, 2);
  // крыло носа
  p.set(cx - 9 - big, t + 25 + big - sm, sk, 1);
  p.set(cx - 10 - big, t + 26 + big - sm, sk, 1);
  p.set(cx - 9 - big, t + 26 + big - sm, sk, 2);
  p.set(cx - 8 - big, t + 24 + big - sm, sk, 2);
  if (big) { p.set(cx - 8, t + 25, sk, 2); p.set(cx - 7, t + 26, sk, 2); }
  // ноздря
  p.set(cx - 12 - big + sm, t + 26 + big - sm, sk, 1);
  // блик на кончике
  p.set(tipX + 1, tipY - 1, sk, 4);
  if (type === 'round') { p.set(tipX + 2, tipY - 1, sk, 4); p.set(tipX + 1, tipY - 2, sk, 4); }
  // тень под носом
  for (let x = cx - 12; x <= cx - 8; x++) p.shift(x, t + 27 + big - sm, -1, sk);
}
function ear(p, H) {
  const ex = H.cx + 7 + (H.earX || 0), ey = H.top + 17, sk = H.ramp;
  p.part({ s: [E(ex + 2, ey + 4, 3, 5)], ramp: sk, base: 2, cast: 0,
    shade(x, y, d) { if (d.dl === 0) return 1; return d.L > 0.6 ? 3 : 2; } });
  p.set(ex + 2, ey + 1, sk, 1); p.set(ex + 3, ey + 2, sk, 1); p.set(ex + 3, ey + 3, sk, 1);
  p.set(ex + 2, ey + 4, sk, 0); p.set(ex + 2, ey + 5, sk, 1); p.set(ex + 3, ey + 6, sk, 1);
  p.set(ex + 1, ey + 3, sk, 1);
}
function neck(p, H, w, len) {
  const cx = H.cx, t = H.top, sk = H.ramp;
  w = w || 12; len = len || 50;
  p.part({ s: [Rc(cx - w / 2 + 1, t + 26, w, len - 26)], ramp: sk, base: 3, cast: 0,
    shade(x, y, d) { const ry = y - t; if (ry < 39) return 1; if (ry < 41) return 2; if (d.u > 0.5) return 2; return 3; } });
  // мышца шеи
  p.strokeT(['l', cx - w / 2 + 3, t + 37, cx - 1, t + 46], 2, sk);
}
/* кисть руки: простая лопатка с пальцами. dir: 'l' пальцы влево */
function hand(p, x, y, sk, o) {
  o = o || {};
  const w = o.w || 9, h = o.h || 8;
  p.part({ s: [P([x, y + 1], [x + w, y], [x + w + 1, y + h - 2], [x + w - 1, y + h], [x + 1, y + h], [x - 1, y + h - 3])], ramp: sk, base: 3, cast: 1 });
  for (let i = 1; i < (o.fingers || 3) + 1; i++) {
    const fy = y + Math.round(i * h / ((o.fingers || 3) + 1));
    for (let k = 0; k < Math.round(w * 0.55); k++) p.shift(x + k, fy, -1, sk);
  }
}

/* общие ключевые точки лица по голове */
function feat(H, extra) {
  const cx = H.cx, t = H.top;
  return Object.assign({
    skin: H.ramp,
    eyeN: [cx - 7, t + 15], eyeF: [cx - 14, t + 15],
    browN: [cx - 7, t + 13, 8], browF: [cx - 14, t + 13, 4],
    mouth: [cx - 13, t + 27],
  }, extra || {});
}

/* пот, слёзы и прочие наложения */
function sweat(c, x, y, big) {
  px(c, x, y, R.blue[6]);
  px(c, x, y + 1, R.blue[6]); px(c, x - 1, y + 1, PAL.white);
  px(c, x, y + 2, R.blue[5]); px(c, x - 1, y + 2, R.blue[6]); px(c, x + 1, y + 2, R.blue[4]);
  px(c, x, y + 3, R.blue[4]);
  if (big) { px(c, x - 1, y + 3, R.blue[5]); px(c, x + 1, y + 1, R.blue[5]); px(c, x, y + 4, R.blue[3]); }
}
function tear(c, x, y, len) {
  for (let i = 0; i < len; i++) {
    px(c, x + (i > len / 2 ? -1 : 0) + (i > len - 2 ? 0 : 0), y + i, i === 0 ? PAL.white : R.blue[6]);
  }
  px(c, x - (len > 3 ? 1 : 0), y + len, R.blue[5]);
}
function shineLine(c, x, y, len, col) { for (let i = 0; i < len; i++) px(c, x + i, y - i, col); }

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

/* ---------------------------------------------------------------------
   Регистрация с общей частью
   --------------------------------------------------------------------- */
const DEF_EMOS = ['normal', 'worried', 'hopeful', 'relieved'];
const WIT_EMOS = ['normal', 'nervous', 'angry', 'shocked', 'breakdown'];
function reg(id, def) {
  const bust = makeBust(def);
  G.Cast.register(id, {
    name: def.name, voice: def.voice,
    emotions: def.emos,
    anims: def.emos.indexOf('breakdown') >= 0 ? { breakdown: def.bkDur || 1.2 } : {},
    bust,
    iso: makeIso(def.iso),
  });
}
/* общий набор лиц */
function witnessFace(st, o) {
  o = o || {};
  const e = st.emo;
  if (e === 'nervous') return { eyes: 'side', brows: [-2, 0], mouth: 'wobble', talk: ['half', 'open'] };
  if (e === 'angry') return { eyes: 'angry', brows: [2, -1], mouth: 'grit', talk: ['gritO', 'gritO'], flatBrow: true };
  if (e === 'shocked') return { eyes: 'tiny', brows: [-3, -2], mouth: 'O', talk: ['O', 'O'] };
  return { eyes: 'open', brows: [0, 0], mouth: o.normalMouth || 'closed' };
}
function defendantFace(st, o) {
  o = o || {};
  const e = st.emo;
  if (e === 'worried') return { eyes: 'down', brows: [-2, 1], mouth: 'frown', talk: ['half', 'half'] };
  if (e === 'hopeful') return { eyes: 'look', brows: [-2, -1], mouth: 'smile', talk: ['halfS', 'openS'] };
  if (e === 'relieved') return { eyes: 'happy', brows: [-2, 1], mouth: 'bigsmile', talk: ['halfS', 'openS'], noBlink: true };
  return { eyes: 'open', brows: [0, 0], mouth: o.normalMouth || 'closed' };
}

/* =====================================================================
   ПЕРСОНАЖИ
   ===================================================================== */

/* ---------- общий хелпер: торс по контрольным точкам ---------- */
function smooth(pts, it) {
  for (let k = 0; k < (it || 2); k++) {
    const o = [];
    for (let i = 0; i < pts.length; i++) {
      const a = pts[i], b = pts[(i + 1) % pts.length];
      if (a[1] >= BH - 1 && b[1] >= BH - 1) { o.push(a); continue; }
      if (a[1] >= BH - 1) o.push(a); else o.push([a[0] * 0.75 + b[0] * 0.25, a[1] * 0.75 + b[1] * 0.25]);
      if (b[1] >= BH - 1) o.push([a[0] * 0.25 + b[0] * 0.75, a[1] * 0.25 + b[1] * 0.75]);
      else o.push([a[0] * 0.25 + b[0] * 0.75, a[1] * 0.25 + b[1] * 0.75]);
    }
    pts = o;
  }
  return pts;
}
function torso(p, pts, ramp, base, opt) {
  pts = smooth(pts.map(q => [q[0], Math.min(q[1], BH + 2)]).map(q => q[1] >= BH ? [q[0], BH + 2] : q), 2);
  return p.part(Object.assign({ s: [P(...pts)], ramp, base: base === undefined ? 3 : base, cast: 1 }, opt || {}));
}
function fold(p, shape, dt, ramp) { p.stroke(shape, dt, ramp); }

/* ФИГУРА: дальняя рука (за торсом) -> торс с талией -> ближняя рука.
   o = {cx, T (основание шеи), wl, wr (до внешнего края плеч), aw (толщина руки), slope, ramp, arm,
        base, waist (сужение), open:[pts] вырез, belly:[cx,cy,rx,ry], upperL/upperR (только плечо до локтя),
        noL/noR, elbow (y локтя от T), fem, pad (плечики)} */
function figure(p, o) {
  const cx = o.cx, T = o.T, aw = o.aw || 12, sl = o.slope === undefined ? 7 : o.slope, ramp = o.ramp, arm = o.arm || ramp;
  const wl = o.wl, wr = o.wr, wst = o.waist === undefined ? 4 : o.waist;
  const ah = Math.round(aw / 2);
  const SL = [cx - wl + ah, T + sl + ah - 1], SR = [cx + wr - ah, T + sl + ah - 1];
  const eY = T + (o.elbow || 56);
  const EL = [SL[0] - 2, eY], ER = [SR[0] + 2, eY];
  const res = { SL, SR, EL, ER };
  const n = BW * BH;
  const all = new Uint8Array(n);
  const armPart = (S, Ep, side, b, upper) => {
    const bot = [Ep[0] - side * 3, BH + 4];
    const sh = [EP(S[0], S[1] + 1, ah + 1, ah + 2), C(S[0], S[1], (S[0] + Ep[0]) / 2 + side, (S[1] + Ep[1]) / 2, Ep[0], Ep[1], aw + 1, aw - 1)];
    if (o.pad) sh.push(Rc(S[0] - ah - (side < 0 ? 0 : 0), S[1] - ah - 1, aw + 1, ah + 2));
    if (!upper) sh.push(C(Ep[0], Ep[1], (Ep[0] + bot[0]) / 2, (Ep[1] + bot[1]) / 2, bot[0], bot[1], aw - 1, aw - 2));
    else sh.push(EP(Ep[0], Ep[1], ah, ah));
    const m = p.part({ s: sh, ramp: arm, base: b, cast: 1, shT: 0.38, hiT: 0.74 });
    // локтевая складка и заломы рукава
    const ix = side < 0 ? Ep[0] + ah - 2 : Ep[0] - ah + 2; // внутренняя сторона руки
    p.stroke(C(ix, Ep[1] - 3, ix - side * 3, Ep[1], ix, Ep[1] + 3, 1), -1, arm);
    p.stroke(['l', ix - side * 1, Ep[1] - 7, ix - side * 3, Ep[1] - 5], -1, arm);
    p.stroke(C(S[0] - side * 1, S[1] + ah + 4, S[0] - side * 2, (S[1] + Ep[1]) / 2, Ep[0] - side * 2, Ep[1] - 8, 1), side < 0 ? 1 : -1, arm);
    if (!upper) p.stroke(['l', Ep[0] - side * 2, Ep[1] + 6, Ep[0] - side * 4, BH], side < 0 ? 1 : -1, arm);
    for (let i = 0; i < n; i++) if (m[i]) all[i] = 1;
    return m;
  };
  let mL = null, mR = null;
  if (!o.noL) mL = armPart(SL, EL, -1, (o.base || 3), o.upperL);
  const tp = [[cx - (o.nl || 9), T - 3], [cx + (o.nr || 11), T - 3], [SR[0], T + sl - 1], [cx + wr - aw + 1, T + sl + 12],
    [cx + wr - aw - wst, eY - 4], [cx + wr - aw - wst + 1, BH + 2], [cx - wl + aw + wst - 1, BH + 2], [cx - wl + aw + wst, eY - 4],
    [cx - wl + aw - 1, T + sl + 12], [SL[0], T + sl - 1]];
  const shapes = [P(...smooth(tp, 2))];
  if (o.belly) shapes.push(EP(o.belly[0], o.belly[1], o.belly[2], o.belly[3]));
  if (o.open) shapes.push(SUB(P(...o.open)));
  if (o.open2) shapes.push(SUB(P(...o.open2)));
  const mT = p.part({ s: shapes, ramp, base: o.base || 3, cast: 1, shT: o.shT || 0.34, hiT: 0.8 });
  for (let i = 0; i < n; i++) if (mT[i]) all[i] = 1;
  // линия-тень между дальней рукой и торсом
  if (mL) for (let y = 0; y < BH; y++) for (let x = 1; x < BW - 1; x++) {
    const i = y * BW + x; if (!mL[i] || mT[i] || p.ramp[i] !== arm) continue;
    if (mT[i + 1] || mT[i - 1]) p.tone[i] = Math.min(p.tone[i], 1);
  }
  if (o.fem) { // мягкая форма груди
    p.stroke(C(cx - 12, T + 26, cx - 2, T + 31, cx + 8, T + 27, 1), -1, ramp);
    p.stroke(C(cx + 10, T + 25, cx + 16, T + 30, cx + 22, T + 26, 1), -1, ramp);
    p.stroke(C(cx - 10, T + 18, cx - 4, T + 16, cx + 2, T + 18, 1), 1, ramp);
  }
  if (!o.noR) {
    mR = armPart(SR, ER, 1, (o.base || 3) - (o.rDark ? 1 : 0), o.upperR);
    // тень на торсе вдоль ближней руки (проём рукава, шов)
    for (let y = 0; y < BH; y++) for (let x = 1; x < BW - 1; x++) {
      const i = y * BW + x; if (mR[i] || !mT[i] || p.ramp[i] !== ramp) continue;
      if (mR[i + 1] || mR[i + 2]) p.tone[i] = Math.max(0, p.tone[i] - (mR[i + 1] ? 2 : 1));
    }
  }
  res.mT = mT; res.mL = mL; res.mR = mR; res.m = all;
  return res;
}

/* ====================== СЭМЮЭЛ ЛОМАКС ====================== */
(function () {
  const sk = R.skinL, hb = R.hairBrown;
  const cardi = [R.stone[0], R.stone[1], R.stone[2], R.stone[3], R.stone[4], R.stone[5]];
  const shirt = [R.blue[2], R.blue[3], R.blue[4], R.blue[5], R.blue[6]];
  const H = { cx: 52, top: 18, ramp: sk, gaunt: true, jaw: -1, chin: 1 };
  const fp = feat(H, { iris: [hb[1], hb[3], hb[4]], brow: hb[1], brow2: hb[2], browThick: 2 });
  reg('lomax', {
    name: 'Сэмюэл Ломакс', voice: 'mid', emos: DEF_EMOS, seed: 3, fidEmos: ['normal', 'worried', 'hopeful'], fidFace(st, f) { if (st.fk > 0.6) { f.eyes = 'half'; } }, feat: fp,
    build(p, st) {
      const cx = H.cx, t = H.top;
      const e = st.emo;
      // волосы сзади
      p.part({ s: [E(cx + 5, t + 12, 15, 13), E(cx + 13, t + 22, 7, 9)], ramp: hb, base: 2, cast: 0 });
      neck(p, H, 11, 52);
      // рубашка (голубая) и вязаный галстук
      torso(p, [[cx - 10, t + 40], [cx + 12, t + 40], [cx + 16, t + 60], [cx - 2, BH], [cx - 20, t + 60]], shirt, 3);
      // кардиган
      const sl = e === 'worried' ? 2 : 0; // плечи сжаты
      const body = [[cx - 14, t + 42], [cx - 29, t + 50 + sl], [cx - 35, t + 60 + sl], [cx - 38, BH], [cx + 44, BH], [cx + 42, t + 62 + sl], [cx + 35, t + 50 + sl], [cx + 18, t + 42], [cx + 12, t + 52], [cx + 2, t + 76], [cx - 8, t + 56]];
      const m = torso(p, body, cardi, 3, { shT: 0.33 });
      // рубчик-«вельвет»: вертикальные рубчики на кардигане
      for (let x = cx - 38; x < cx + 45; x += 2) for (let y = t + 44; y < BH; y++) {
        const i = y * BW + x;
        if (x >= 0 && x < BW && m[i] && ((y + (x >> 1)) % 7 !== 0)) p.shift(x, y, (x >> 1) & 1 ? 0 : -1, cardi);
      }
      // планка с пуговицами
      p.strokeT(['l', cx + 3, t + 76, cx + 6, BH], 2, cardi);
      p.strokeT(['l', cx + 4, t + 76, cx + 7, BH], 4, cardi);
      for (let k = 0; k < 3; k++) { const by = t + 82 + k * 12; p.set(cx + 5 + Math.round(k * 0.6), by, R.wood, 3); p.set(cx + 6 + Math.round(k * 0.6), by, R.wood, 2); p.set(cx + 5 + Math.round(k * 0.6), by + 1, R.wood, 1); }
      // рукава/складки
      fold(p, C(cx - 32, t + 58, cx - 29, t + 80, cx - 30, BH, 1), -1, cardi);
      fold(p, C(cx + 35, t + 60, cx + 33, t + 84, cx + 34, BH, 1), -1, cardi);
      fold(p, C(cx - 24, t + 70, cx - 18, t + 78, cx - 10, t + 82, 1), -1, cardi);
      fold(p, C(cx + 22, t + 66, cx + 18, t + 76, cx + 10, t + 90, 1), -1, cardi);
      fold(p, C(cx - 22, t + 52, cx - 16, t + 54, cx - 12, t + 60, 1), 1, cardi);
      // воротник рубашки
      p.part({ s: [P([cx - 10, t + 39], [cx - 2, t + 46], [cx - 6, t + 52], [cx - 13, t + 44])], ramp: shirt, base: 4, cast: 1 });
      p.part({ s: [P([cx + 11, t + 39], [cx + 4, t + 47], [cx + 9, t + 52], [cx + 15, t + 44])], ramp: shirt, base: 3, cast: 1 });
      // вязаный галстук (тёмно-коричневый)
      p.part({ s: [P([cx - 3, t + 46], [cx + 3, t + 46], [cx + 2, t + 50], [cx + 4, t + 70], [cx + 1, t + 75], [cx - 2, t + 70], [cx - 1, t + 50])], ramp: R.wood, base: 2, cast: 1 });
      for (let y = t + 52; y < t + 74; y += 3) p.shift(cx + 1, y, 1, R.wood);
      head(p, H);
      ear(p, H);
      nose(p, H, 'sharp');
      // щетина
      for (let y = t + 28; y < t + 37; y++) for (let x = cx - 12; x < cx + 9; x++) if (p.filled(x, y) && G.bayer(x, y) < 4 && p.ramp[y * BW + x] === sk) p.shift(x, y, -1, sk);
      // носогубная складка
      p.set(cx - 7, t + 27, sk, 2); p.set(cx - 6, t + 28, sk, 2); p.set(cx - 6, t + 29, sk, 2);
      // взъерошенные волосы: пучки
      const hairClumps = [
        C(cx - 12, t + 6, cx - 8, t - 2, cx + 2, t - 2, 5, 3),
        C(cx - 13, t + 9, cx - 16, t + 3, cx - 12, t - 1, 3, 1),
        C(cx - 4, t + 2, cx - 4, t - 6, cx + 4, t - 4, 5, 1),
        C(cx + 2, t + 0, cx + 6, t - 7, cx + 13, t - 3, 6, 1),
        C(cx + 8, t + 2, cx + 16, t - 4, cx + 20, t + 2, 6, 1),
        C(cx + 12, t + 6, cx + 21, t + 4, cx + 22, t + 12, 6, 2),
        C(cx + 14, t + 12, cx + 21, t + 16, cx + 19, t + 24, 6, 2),
        C(cx + 10, t + 18, cx + 15, t + 24, cx + 12, t + 30, 5, 1),
        C(cx - 10, t + 4, cx - 14, t + 8, cx - 13, t + 12, 3, 1),
        C(cx - 6, t + 3, cx - 7, t + 8, cx - 9, t + 11, 4, 1),
        C(cx + 0, t + 2, cx + 2, t + 6, cx + 1, t + 9, 3, 1),
      ];
      for (const s of hairClumps) p.part({ s: [s], ramp: hb, base: 3, cast: 1, shT: 0.3 });
      // седые прядки у виска
      p.stroke(C(cx + 6, t + 14, cx + 8, t + 18, cx + 7, t + 22, 1), 1, hb);
      // худые плечи вперёд при волнении — нет. Очки рисуются в post
      if (st.fid >= 0) {
        const k = st.fk;
        const hp = lerpP([cx + 16, t + 84], [cx - 5, t + 21], k);
        armTo(p, hp[0], hp[1], { from: [cx + 26, t + 100], sleeve: cardi, skin: sk, pose: 'point', w: 15, bend: 10 });
      }
    },
    face(st) {
      const f = defendantFace(st);
      if (st.emo === 'normal') f.mouth = 'flat';
      return f;
    },
    post(c, st, fc) {
      const cx = H.cx, t = H.top;
      // круглые очки (тонкая оправа)
      const fr = R.gold[1], hi = R.gold[3];
      const ring = (x0, y0, w, h) => {
        for (let i = 1; i < w - 1; i++) { px(c, x0 + i, y0, fr); px(c, x0 + i, y0 + h - 1, fr); }
        for (let j = 1; j < h - 1; j++) { px(c, x0, y0 + j, fr); px(c, x0 + w - 1, y0 + j, fr); }
      };
      const gl = st.fk > 0.95 && st.fa > 0.3 ? -1 : 0;
      const t0 = t; { const t = t0 + gl;
      ring(cx - 9, t + 14, 10, 8);
      ring(cx - 16, t + 14, 5, 8);
      px(c, cx - 11, t + 16, fr); px(c, cx - 10, t + 16, fr); // переносица
      for (let i = 1; i < 16; i++) px(c, cx + 1 + i, t + 16 + (i > 8 ? 1 : 0), fr); // дужка
      px(c, cx - 8, t + 15, hi); px(c, cx - 8, t + 16, hi); px(c, cx - 15, t + 15, hi);
      // блик на стекле
      c.globalAlpha = 0.35; G.rect(c, cx - 3, t + 15, 2, 1, PAL.white); G.rect(c, cx - 2, t + 16, 1, 1, PAL.white); c.globalAlpha = 1;
      }
      if (st.fk > 0.95) { // палец на переносице поверх оправы
        for (let y = t + 16 + gl; y < t + 24; y++) { px(c, cx - 11, y, PAL.outline); px(c, cx - 10, y, sk[3]); px(c, cx - 9, y, sk[2]); px(c, cx - 8, y, PAL.outline); }
        px(c, cx - 10, t + 15 + gl, PAL.outline); px(c, cx - 9, t + 15 + gl, PAL.outline); px(c, cx - 10, t + 16 + gl, sk[4]);
      }
      if (st.emo === 'relieved') {
        tear(c, cx - 3, t + 20, 7); tear(c, cx - 13, t + 20, 5);
      }
      if (st.emo === 'worried') sweat(c, cx - 15, t + 8);
    },
    iso: { skin: sk, top: cardi, pants: R.wood, shoes: R.wood[0], build: 'thin', seed: 0.3, shirt: shirt[3],
      hairDraw: isoHair(hb, 'messy'),
      extra(x, f) { x.fillStyle = R.gold[2]; x.fillRect(f.hx, f.hy + 4, 3, 1); x.fillRect(f.hx + 3, f.hy + 4, 3, 1); } },
  });
})();

/* ====================== ПИТЕР ХОЛЛИС ====================== */
(function () {
  const sk = R.skinL, hg = R.hairGrey;
  const shirt = [R.blue[2], R.blue[3], R.blue[4], R.blue[5], R.blue[6]];
  const navy = [R.blue[0], R.blue[1], R.blue[2], R.blue[3], R.blue[4]];
  const H0 = { cx: 52, top: 22, ramp: sk, jaw: 3, chin: 1, jowl: true, skull: 1, sideX: 4 };
  const RF = [R.red[2], R.red[3], R.skinL[1], R.skinL[2], R.skinL[3]];
  reg('hollis', {
    name: 'Питер Холлис', voice: 'low', emos: WIT_EMOS, seed: 7, fidEmos: ['normal', 'nervous', 'angry', 'shocked'], fidFace(st, f) { if (st.fk > 0.6) { f.eyes = 'half'; f.mouth = 'flat'; f.brows = [1, 0]; } }, bkFrames: 8,
    feat: feat(H0, { iris: [R.blue[2], R.blue[3], R.blue[5]], brow: hg[2], brow2: hg[1], browThick: 2, mouth: [H0.cx - 12, H0.top + 29] }),
    shake: (k, t) => (k < 0.6 ? ((Math.floor(t * 30) & 1) ? 2 : -2) : 0),
    build(p, st) {
      const H = Object.assign({}, H0);
      const cx = H.cx, t = H.top, e = st.emo, bk = st.bk;
      const red = e === 'angry' || bk >= 3;
      if (red) H.ramp = sk;
      // торс: грузный, широкий
      neck(p, H, 14, 50);
      const body = [[cx - 14, t + 38], [cx - 33, t + 46], [cx - 42, t + 58], [cx - 45, BH], [cx + 50, BH], [cx + 48, t + 60], [cx + 39, t + 46], [cx + 20, t + 38]];
      torso(p, body, shirt, 3, { shT: 0.32, hiT: 0.84 });
      // живот (выпирает)
      p.part({ s: [E(cx - 4, BH + 6, 36, 30)], ramp: shirt, base: 3, cast: 0, edge: false, over: true, hiT: 0.75 });
      // планка, пуговицы
      p.strokeT(['l', cx - 6, t + 50, cx - 10, BH], 2, shirt);
      for (let k = 0; k < 4; k++) { const y = t + 56 + k * 13; const x = cx - 7 - Math.round(k * 0.9); p.px(x, y, R.neutral[8]); p.px(x, y + 1, R.neutral[6]); }
      // нагрудные карманы с клапанами
      const pocket = (x0, y0, w) => {
        p.part({ s: [Rc(x0, y0, w, 12)], ramp: shirt, base: 3, cast: 0, edge: false, over: true });
        p.part({ s: [P([x0 - 1, y0 - 1], [x0 + w + 1, y0 - 1], [x0 + w + 1, y0 + 3], [x0 + w / 2, y0 + 5], [x0 - 1, y0 + 3])], ramp: shirt, base: 3, cast: 1, over: true });
        p.px(x0 + w / 2, y0 + 3, R.neutral[7]);
      };
      pocket(cx - 31, t + 60, 13);
      pocket(cx + 8, t + 60, 15);
      // значок охраны (золотой щит) на левом кармане
      const bx = cx + 11, by = t + 52;
      p.part({ s: [P([bx, by], [bx + 8, by], [bx + 8, by + 6], [bx + 4, by + 10], [bx, by + 6])], ramp: R.gold, base: 3, cast: 1 });
      p.set(bx + 4, by + 4, R.gold, 1); p.set(bx + 3, by + 4, R.gold, 2); p.set(bx + 5, by + 4, R.gold, 2); p.set(bx + 4, by + 3, R.gold, 2); p.set(bx + 4, by + 5, R.gold, 2);
      // нашивка на плече
      p.part({ s: [P([cx - 40, t + 64], [cx - 34, t + 60], [cx - 33, t + 70], [cx - 37, t + 74])], ramp: navy, base: 2, cast: 1 });
      p.set(cx - 37, t + 66, R.gold, 4); p.set(cx - 36, t + 67, R.gold, 3);
      // погоны
      p.part({ s: [P([cx - 30, t + 46], [cx - 18, t + 42], [cx - 16, t + 45], [cx - 28, t + 50])], ramp: shirt, base: 4, cast: 1 });
      p.part({ s: [P([cx + 22, t + 42], [cx + 37, t + 47], [cx + 37, t + 51], [cx + 21, t + 46])], ramp: shirt, base: 3, cast: 1 });
      // складки
      fold(p, C(cx - 36, t + 62, cx - 34, t + 84, cx - 37, BH, 1), -1, shirt);
      fold(p, C(cx + 37, t + 60, cx + 39, t + 84, cx + 40, BH, 1), -1, shirt);
      fold(p, C(cx + 28, t + 78, cx + 20, t + 82, cx + 14, t + 94, 1), -1, shirt);
      fold(p, C(cx - 22, t + 78, cx - 18, t + 86, cx - 12, t + 90, 1), -1, shirt);
      // воротник
      p.part({ s: [P([cx - 9, t + 36], [cx - 2, t + 44], [cx - 8, t + 50], [cx - 15, t + 41])], ramp: shirt, base: 4, cast: 1 });
      p.part({ s: [P([cx + 14, t + 36], [cx + 5, t + 45], [cx + 12, t + 50], [cx + 20, t + 40])], ramp: shirt, base: 3, cast: 1 });
      // галстук (тёмно-синий)
      p.part({ s: [P([cx - 2, t + 44], [cx + 4, t + 44], [cx + 3, t + 48], [cx + 4, t + 64], [cx + 1, t + 68], [cx - 2, t + 64], [cx - 1, t + 48])], ramp: navy, base: 2, cast: 1 });
      head(p, H);
      if (red) { // побагровел
        for (let y = t; y < t + 38; y++) for (let x = cx - 16; x < cx + 20; x++) {
          const i = y * BW + x; const flush = (y > t + 20 && y < t + 31 && x < cx + 6) || (bk >= 3 && y > t + 4 && y < t + 12); if (p.ramp[i] === sk && flush && (G.bayer(x, y) < (bk >= 3 ? 10 : 7))) p.set(x, y, RF, p.tone[i]);
        }
      }
      ear(p, H);
      nose(p, H, 'round');
      // морщины
      p.set(cx - 7, t + 26, sk, 2); p.set(cx - 6, t + 27, sk, 2); p.set(cx - 6, t + 28, sk, 2); p.set(cx - 5, t + 29, sk, 2);
      p.set(cx - 2, t + 21, sk, 2); p.set(cx - 1, t + 22, sk, 2);
      for (let i = 0; i < 6; i++) p.set(cx - 10 + i, t + 9, sk, 2);
      // седые волосы по бокам (видны под фуражкой)
      p.part({ s: [C(cx + 6, t + 10, cx + 14, t + 14, cx + 13, t + 22, 5, 2), C(cx + 14, t + 9, cx + 18, t + 16, cx + 16, t + 22, 4, 2)], ramp: hg, base: 2, cast: 1 });
      // усы: пышные седые
      const bristle = bk >= 2;
      const mx = cx - 14, my = t + 26;
      if (!bristle) {
        p.part({ s: [P([mx, my + 2], [mx + 3, my - 1], [mx + 9, my - 1], [mx + 12, my + 1], [mx + 12, my + 4], [mx + 8, my + 3], [mx + 3, my + 3], [mx - 1, my + 4])], ramp: hg, base: 3, cast: 1 });
        for (let i = 1; i < 11; i += 2) p.shift(mx + i, my + 2, -1, hg);
      } else {
        // усы встали дыбом: щетина-иголки
        p.part({ s: [P([mx, my + 1], [mx + 3, my - 1], [mx + 9, my - 1], [mx + 12, my + 1], [mx + 11, my + 3], [mx + 1, my + 3])], ramp: hg, base: 3, cast: 1 });
        const sp = [[mx - 2, my - 1], [mx - 1, my + 4], [mx + 2, my - 3], [mx + 5, my - 3], [mx + 8, my - 3], [mx + 11, my - 2], [mx + 14, my], [mx + 14, my + 3], [mx + 1, my + 5], [mx + 6, my + 5], [mx + 10, my + 5]];
        for (const s of sp) p.part({ s: [['l', mx + 6, my + 1, s[0], s[1]]], ramp: hg, base: 3, cast: 0, edge: false });
      }
      // фуражка
      const capOff = bk >= 1;
      const capFrames = [[0, 0], [2, -8], [8, -18], [16, -26], [26, -30], [40, -30], [60, -40], [99, 0]];
      const drawCap = (dx, dy, tilt) => {
        const X = cx + dx, Y = t + dy;
        p.part({ s: [P([X - 14, Y + 6 - tilt], [X - 12, Y - 2 - tilt], [X + 4, Y - 6], [X + 20, Y - 2 + tilt], [X + 20, Y + 6 + tilt], [X + 4, Y + 8])], ramp: navy, base: 3, cast: 1, hiT: 0.7 });
        p.part({ s: [P([X - 12, Y + 6 - tilt], [X + 18, Y + 6 + tilt], [X + 18, Y + 11 + tilt], [X - 12, Y + 11 - tilt])], ramp: navy, base: 1, cast: 1 });
        // околыш с золотой полосой
        p.strokeT(['l', X - 11, Y + 8 - tilt, X + 17, Y + 8 + tilt], 3, navy);
        // козырёк
        p.part({ s: [P([X - 22, Y + 13 - tilt], [X - 12, Y + 9 - tilt], [X + 2, Y + 11], [X - 4, Y + 15], [X - 18, Y + 16 - tilt])], ramp: R.neutral, base: 1, cast: 2 });
        p.set(X - 16, Y + 12 - tilt, R.neutral, 4); p.set(X - 15, Y + 12 - tilt, R.neutral, 3);
        // кокарда
        p.part({ s: [E(X - 6, Y + 3, 3, 3)], ramp: R.gold, base: 3, cast: 1 });
        p.set(X - 6, Y + 3, R.gold, 1);
      };
      if (!capOff) drawCap(0, 0, 0);
      else {
        // лысина и всклокоченные седые остатки волос
        p.part({ s: [C(cx - 10, t + 4, cx + 2, t - 4, cx + 14, t + 4, 3, 2)], ramp: sk, base: 3, cast: 0, over: true });
        const fl = [C(cx + 4, t + 4, cx + 10, t - 4, cx + 16, t + 0, 3, 1), C(cx + 10, t + 6, cx + 18, t + 2, cx + 21, t + 7, 4, 1), C(cx + 13, t + 12, cx + 21, t + 11, cx + 22, t + 16, 4, 1), C(cx - 4, t + 3, cx - 2, t - 3, cx + 2, t - 4, 2, 1)];
        for (const s of fl) p.part({ s: [s], ramp: hg, base: 3, cast: 1 });
        const f = capFrames[Math.min(bk, 7)];
        if (bk < 7) drawCap(f[0], f[1], bk * 2);
      }
      if (st.fid >= 0 && bk < 0) {
        const k = st.fk, w = Math.round(Math.sin(st.fa * Math.PI * 4) * 3);
        const hp = lerpP([cx + 14, t + 80], [cx - 13 + w, t + 26], k);
        armTo(p, hp[0], hp[1], { from: [cx + 30, t + 96], sleeve: shirt, skin: sk, pose: 'point', w: 18, bend: 12 });
      }
    },
    after(c, st) {
      if (st.bk >= 1 && st.bk < 7) { // линии движения фуражки
        const cx = H0.cx, t = H0.top;
        c.globalAlpha = 0.45;
        for (let i = 0; i < 3; i++) G.line(c, cx - 6 + i * 6, t + 6 - st.bk * 2, cx - 10 + i * 6 + st.bk, t + 14, PAL.white);
        c.globalAlpha = 1;
      }
    },
    face(st) {
      const bk = st.bk;
      if (bk >= 0 || st.emo === 'breakdown') {
        if (bk < 2) return { eyes: 'tiny', brows: [-3, -2], mouth: 'O', noBlink: true };
        if (bk < 5) return { eyes: 'wide', brows: [-3, -1], mouth: 'wail', noBlink: true };
        return { eyes: 'squeeze', brows: [2, 0], mouth: 'gritO', noBlink: true, flatBrow: true, talk: ['gritO', 'wail'] };
      }
      const f = witnessFace(st);
      return f;
    },
    post(c, st) {
      const cx = H0.cx, t = H0.top;
      if (st.emo === 'nervous') { sweat(c, cx - 15, t + 9); sweat(c, cx + 2, t + 12); }
      if (st.emo === 'shocked') { sweat(c, cx - 16, t + 10, true); }
      if (st.emo === 'breakdown' || st.bk >= 0) {
        const bk = st.bk < 0 ? 7 : st.bk;
        if (bk >= 2) { sweat(c, cx - 16, t + 8 + (bk & 1), true); sweat(c, cx - 1, t + 3 + bk, true); }
        if (bk >= 4) { sweat(c, cx + 10, t + 2 + (bk & 1) * 2, true); sweat(c, cx - 20, t + 22, false); }
        if (bk >= 5) { // капли разлетаются
          px(c, cx - 22, t + 2, R.blue[6]); px(c, cx + 24, t + 4, R.blue[6]); px(c, cx + 25, t + 3, R.blue[5]); px(c, cx - 24, t + 14, R.blue[5]);
        }
      }
    },
    iso: { skin: sk, top: shirt, pants: navy, shoes: R.neutral[0], build: 'big', seed: 0.7, tie: navy[1],
      hairDraw(x, hx, hy) { // фуражка
        x.fillStyle = navy[2]; x.fillRect(hx - 1, hy - 2, 9, 3);
        x.fillStyle = navy[3]; x.fillRect(hx, hy - 3, 7, 1);
        x.fillStyle = R.neutral[0]; x.fillRect(hx - 2, hy + 1, 5, 1);
        x.fillStyle = R.gold[4]; x.fillRect(hx + 2, hy - 1, 1, 1);
        x.fillStyle = hg[3]; x.fillRect(hx + 1, hy + 5, 3, 1);
      } },
  });
})();

/* ====================== АННА УИТФИЛД ====================== */
(function () {
  const sk = R.skinL, hr = R.hairRed;
  const dress = [R.green[1], R.green[2], R.green[3], R.green[4], R.green[5], R.green[6]];
  const H = { cx: 54, top: 24, ramp: sk, fem: true, jaw: -3, chin: -1, sideX: 4 };
  const BL = [R.red[2], R.red[3], R.red[4], R.skinL[2], R.skinL[3]];
  reg('whitfield', {
    name: 'Анна Уитфилд', voice: 'high', emos: DEF_EMOS, seed: 5, fidEmos: ['normal', 'worried', 'hopeful'], fidFace(st, f) { if (st.fk > 0.6) { f.eyes = 'down'; } },
    feat: feat(H, { iris: [R.green[2], R.green[4], R.green[5]], brow: hr[2], brow2: hr[3], browThick: 1, lash: true, lip: [R.red[2], R.red[3], R.red[4]], mouthLine: R.red[1] }),
    build(p, st) {
      const cx = H.cx, t = H.top, e = st.emo;
      // пучок сзади/сверху
      p.part({ s: [E(cx + 10, t - 1, 9, 8)], ramp: hr, base: 3, cast: 0, shT: 0.4 });
      // волосы — задняя масса
      p.part({ s: [E(cx + 4, t + 13, 16, 15)], ramp: hr, base: 2, cast: 0 });
      neck(p, H, 10, 48);
      // платье
      const body = [[cx - 10, t + 40], [cx - 26, t + 46], [cx - 33, t + 56], [cx - 34, BH], [cx + 39, BH], [cx + 38, t + 58], [cx + 33, t + 46], [cx + 14, t + 40]];
      const m = torso(p, body, dress, 3, { shT: 0.33 });
      // вырез и воротничок «питер пэн» (кремовый)
      p.part({ s: [P([cx - 8, t + 38], [cx + 11, t + 38], [cx + 4, t + 50], [cx - 2, t + 50])], ramp: sk, base: 3, cast: 1,
        shade(x, y) { return y < t + 42 ? 2 : 3; } });
      p.part({ s: [P([cx - 10, t + 39], [cx - 2, t + 49], [cx - 8, t + 53], [cx - 16, t + 47], [cx - 14, t + 42])], ramp: R.paper, base: 3, cast: 1 });
      p.part({ s: [P([cx + 13, t + 39], [cx + 4, t + 49], [cx + 12, t + 53], [cx + 20, t + 46], [cx + 18, t + 41])], ramp: R.paper, base: 2, cast: 1 });
      // пуговки
      for (let k = 0; k < 4; k++) { p.set(cx + 1 - k, t + 56 + k * 10, R.paper, 4); p.set(cx + 1 - k, t + 57 + k * 10, R.paper, 1); }
      // складки ткани
      fold(p, C(cx - 29, t + 60, cx - 28, t + 80, cx - 30, BH, 1), -1, dress);
      fold(p, C(cx + 32, t + 60, cx + 32, t + 84, cx + 33, BH, 1), -1, dress);
      fold(p, C(cx - 16, t + 64, cx - 10, t + 70, cx - 6, t + 72, 1), -1, dress);
      fold(p, C(cx - 18, t + 66, cx - 12, t + 72, cx - 6, t + 74, 1), 1, dress);
      fold(p, C(cx + 24, t + 70, cx + 18, t + 78, cx + 16, t + 92, 1), -1, dress);
      // мелкий узор-горошек (дизер)
      for (let y = t + 56; y < BH; y += 6) for (let x = cx - 33 + ((y >> 1) % 6); x < cx + 39; x += 6) {
        const i = y * BW + x; if (x > 0 && x < BW && m[i] && p.ramp[i] === dress) p.shift(x, y, 1, dress);
      }
      head(p, H);
      if (e === 'worried' || e === 'relieved') for (let y = t + 23; y <= t + 26; y++) for (let x = cx - 5; x <= cx + 1; x++) if (G.bayer(x, y) < 6 && p.ramp[y * BW + x] === sk) p.set(x, y, BL, 3);
      ear(p, H);
      nose(p, H, 'small');
      // веснушки
      const fr = [[-4, 22], [-2, 23], [-5, 24], [0, 22], [1, 24], [-3, 25], [-10, 22], [-11, 24], [-9, 21], [-8, 23], [-1, 21], [2, 23]];
      for (const f of fr) p.set(cx + f[0], t + f[1], sk, 2);
      // волосы спереди: зачёс к пучку, выбившиеся прядки
      const front = [
        C(cx - 12, t + 10, cx - 8, t - 1, cx + 6, t - 1, 6, 4),
        C(cx - 2, t + 3, cx + 6, t - 3, cx + 12, t + 1, 6, 3),
        C(cx + 6, t + 4, cx + 14, t + 2, cx + 18, t + 8, 6, 3),
        C(cx + 10, t + 10, cx + 18, t + 12, cx + 17, t + 22, 6, 3),
        C(cx - 13, t + 8, cx - 14, t + 12, cx - 13, t + 15, 3, 1),
      ];
      for (const s of front) p.part({ s: [s], ramp: hr, base: 3, cast: 1, shT: 0.3 });
      // пучок: витки
      p.stroke(C(cx + 4, t - 2, cx + 10, t - 9, cx + 17, t - 3, 1), -1, hr);
      p.stroke(C(cx + 5, t + 2, cx + 12, t - 4, cx + 16, t + 3, 1), -1, hr);
      p.stroke(C(cx + 6, t - 4, cx + 10, t - 7, cx + 13, t - 5, 1), 1, hr);
      // выбившиеся прядки
      p.part({ s: [C(cx + 14, t + 20, cx + 17, t + 26, cx + 14, t + 32, 1)], ramp: hr, base: 3, cast: 0, edge: false });
      p.part({ s: [C(cx - 11, t + 11, cx - 15, t + 16, cx - 13, t + 22, 1)], ramp: hr, base: 4, cast: 0, edge: false });
      p.part({ s: [C(cx + 2, t - 6, cx + 1, t - 10, cx + 4, t - 12, 1)], ramp: hr, base: 3, cast: 0, edge: false });
      // мука на щеке (пекарь)
      p.px(cx - 3, t + 30, R.neutral[8]); p.px(cx - 2, t + 31, R.neutral[7]);
      // мука на платье
      for (let i = 0; i < 9; i++) { const x = cx + 14 + (i * 7) % 11, y = t + 88 + (i * 5) % 14; if (G.bayer(x, y) < 8) p.px(x, y, R.neutral[8]); }
      if (st.fid >= 0) {
        const k = st.fk, w = Math.round(st.fa * 4);
        const hp = lerpP([cx + 14, t + 82], [cx + 8 + w, t + 16], k);
        armTo(p, hp[0], hp[1], { from: [cx + 26, t + 96], sleeve: dress, skin: sk, pose: 'pinch', w: 14, bend: 8 });
      }
    },
    face(st) {
      const f = defendantFace(st);
      if (st.emo === 'worried') f.eyes = 'down';
      return f;
    },
    post(c, st) {
      const cx = H.cx, t = H.top;
      if (st.emo === 'relieved') { tear(c, cx - 2, t + 19, 9); tear(c, cx - 12, t + 19, 6); }
      if (st.emo === 'worried') { px(c, cx - 1, t + 21, R.blue[6]); px(c, cx - 1, t + 22, R.blue[5]); }
    },
    iso: { skin: sk, top: dress, pants: R.green, shoes: R.wood[1], build: 'thin', seed: 0.5, shirt: R.paper[3],
      hairDraw: isoHair(hr, 'bun'),
      extra(x, f) { if (!f.sit) { x.fillStyle = dress[2]; x.fillRect(f.fx, 22, 10, 5); x.fillStyle = dress[1]; x.fillRect(f.fx + 6, 22, 4, 5); } } },
  });
})();

/* ====================== ВИКТОР КРЕЙН ====================== */
(function () {
  const sk = R.skinL, hg = R.hairGrey;
  const shirt = [R.neutral[4], R.neutral[5], R.neutral[6], R.neutral[7], R.neutral[8], R.neutral[9]];
  const susp = R.red;
  const H0 = { cx: 52, top: 18, ramp: sk, jaw: 4, chin: 2, jowl: true, skull: 1, sideX: 4 };
  const RF = [R.red[1], R.red[2], R.red[3], R.red[4], R.skinL[3]];
  reg('crane', {
    name: 'Виктор Крейн', voice: 'low', emos: WIT_EMOS, seed: 11, fidEmos: ['normal', 'nervous', 'angry', 'shocked'], fidFace(st, f) { if (st.fk > 0.6) { f.eyes = 'down'; f.brows = [1, 0]; } }, bkFrames: 8,
    feat: feat(H0, { iris: [R.hairBrown[1], R.hairBrown[2], R.hairBrown[4]], brow: R.hairBrown[1], brow2: hg[1], browThick: 3, mouth: [H0.cx - 13, H0.top + 28] }),
    shake: (k, t) => (k > 0.15 && k < 0.7 ? ((Math.floor(t * 26) & 1) ? 2 : -1) : 0),
    build(p, st) {
      const H = Object.assign({}, H0);
      const cx = H.cx, t = H.top, e = st.emo, bk = st.bk;
      const fury = e === 'angry' || bk >= 2;
      if (bk >= 2 || e === 'breakdown') H.ramp = RF;
      neck(p, H, 16, 48);
      // крупный торс, рубашка с закатанными рукавами
      const body = [[cx - 14, t + 38], [cx - 34, t + 46], [cx - 45, t + 58], [cx - 48, BH], [cx + 51, BH], [cx + 50, t + 58], [cx + 40, t + 46], [cx + 20, t + 38]];
      const m = torso(p, body, shirt, 3, { shT: 0.32 });
      p.part({ s: [E(cx - 2, BH + 10, 40, 32)], ramp: shirt, base: 3, cast: 0, edge: false, over: true, hiT: 0.72 });
      // клетка/ткань: легкие складки
      fold(p, C(cx - 37, t + 60, cx - 36, t + 84, cx - 40, BH, 1), -1, shirt);
      fold(p, C(cx + 40, t + 60, cx + 42, t + 84, cx + 44, BH, 1), -1, shirt);
      fold(p, C(cx - 22, t + 82, cx - 12, t + 88, cx - 4, t + 86, 1), -1, shirt);
      fold(p, C(cx + 10, t + 84, cx + 20, t + 90, cx + 30, t + 88, 1), -1, shirt);
      // планка рубашки
      p.strokeT(['l', cx - 4, t + 46, cx - 8, BH], 2, shirt);
      for (let k = 0; k < 5; k++) p.px(cx - 5 - Math.round(k * 0.8), t + 52 + k * 13, R.neutral[6]);
      // воротник расстёгнут
      p.part({ s: [P([cx - 10, t + 36], [cx - 3, t + 46], [cx - 10, t + 52], [cx - 18, t + 42])], ramp: shirt, base: 4, cast: 1 });
      p.part({ s: [P([cx + 16, t + 36], [cx + 5, t + 46], [cx + 13, t + 52], [cx + 22, t + 40])], ramp: shirt, base: 3, cast: 1 });
      // мука: пятна (дизер белым)
      const flourAmt = bk >= 0 ? Math.max(0, 1 - bk / 5) : (e === 'breakdown' ? 0 : 1);
      const fl = [[cx - 30, t + 74, 10, 7], [cx + 24, t + 66, 9, 6], [cx - 8, t + 92, 12, 8], [cx + 34, t + 94, 7, 9], [cx - 40, t + 96, 8, 7], [cx + 8, t + 56, 6, 5]];
      for (const f of fl) for (let y = f[1] - f[3]; y <= f[1] + f[3]; y++) for (let x = f[0] - f[2]; x <= f[0] + f[2]; x++) {
        const dx = (x - f[0]) / f[2], dy = (y - f[1]) / f[3], r = dx * dx + dy * dy;
        if (r > 1 || x < 0 || x >= BW || y < 0 || y >= BH) continue;
        const i = y * BW + x; if (!m[i] || p.ramp[i] !== shirt) continue;
        const lvl = Math.round((1 - r) * 9 * flourAmt);
        if (G.bayer(x, y) < lvl) p.set(x, y, shirt, 5);
      }
      // подтяжки
      const snap = bk >= 2 || e === 'breakdown';
      const strap = (pts, b) => p.part({ s: [P(...pts)], ramp: susp, base: b, cast: 1 });
      // левая (ближе к зрителю слева) — целая
      strap([[cx - 22, t + 42], [cx - 17, t + 42], [cx - 22, BH], [cx - 28, BH]], 3);
      if (!snap) strap([[cx + 22, t + 42], [cx + 28, t + 42], [cx + 30, BH], [cx + 24, BH]], 2);
      else {
        // лопнувшая подтяжка: болтается/подскакивает
        const k = st.bk < 0 ? 7 : st.bk;
        const yy = k <= 3 ? t + 30 + (3 - k) * 4 : t + 70 + (k - 4) * 6;
        p.part({ s: [C(cx + 27, BH, cx + 33, (yy + BH) / 2, cx + 30 + (k & 1) * 4, Math.min(yy, BH - 6), 5, 4)], ramp: susp, base: 2, cast: 1 });
        // металлическая клипса
        const cyy = Math.min(yy, BH - 6);
        p.part({ s: [Rc(cx + 28 + (k & 1) * 4, cyy - 3, 5, 4)], ramp: R.neutral, base: 6, cast: 1 });
        // обрывок сверху
        p.part({ s: [P([cx + 22, t + 42], [cx + 28, t + 42], [cx + 27, t + 48], [cx + 22, t + 47])], ramp: susp, base: 2, cast: 1 });
      }
      // строчка на подтяжке
      for (let y = t + 46; y < BH; y += 2) p.shift(cx - 22 - Math.round((y - t - 46) * 0.07), y, 1, susp);
      // клипсы подтяжек
      head(p, H);
      // двойной подбородок
      p.part({ s: [E(cx - 1, t + 38, 11, 4)], ramp: H.ramp, base: 2, cast: 0, under: false,
        shade(x, y, d) { if (y >= t + 40) return 1; return d.L > 0.6 ? 3 : 2; } });
      p.strokeT(C(cx - 10, t + 37, cx - 2, t + 40, cx + 8, t + 37, 1), 1, H.ramp);
      ear(p, H);
      nose(p, H, 'big');
      // лысина с бликом
      for (let i = 0; i < 4; i++) { p.set(cx - 6 + i, t + 3 - (i > 1 ? 1 : 0), H.ramp, 4); }
      p.set(cx - 5, t + 4, H.ramp, 4); p.set(cx - 4, t + 4, H.ramp, 4);
      // морщины на лбу
      if (fury || e === 'shocked') for (let k = 0; k < 3; k++) for (let i = 0; i < 9; i++) p.shift(cx - 10 + i, t + 6 + k * 2 + (i > 4 ? 0 : 0), -1);
      // носогубка
      p.set(cx - 6, t + 27, H.ramp, 2); p.set(cx - 5, t + 28, H.ramp, 2); p.set(cx - 5, t + 29, H.ramp, 2); p.set(cx - 4, t + 30, H.ramp, 2);
      // венок волос сзади (седой, коротко)
      p.part({ s: [C(cx + 4, t + 14, cx + 14, t + 10, cx + 17, t + 20, 4, 3), C(cx + 12, t + 18, cx + 16, t + 24, cx + 12, t + 28, 3, 2)], ramp: hg, base: 2, cast: 1 });
      for (let y = t + 12; y < t + 28; y += 2) p.shift(cx + 13, y, 1, hg);
      // вздутая жилка на виске в гневе
      if (fury) { p.set(cx + 2, t + 7, H.ramp, 1); p.set(cx + 3, t + 8, H.ramp, 1); p.set(cx + 3, t + 9, H.ramp, 1); p.set(cx + 4, t + 10, H.ramp, 1); }
      if (st.fid >= 0 && bk < 0) {
        const k = st.fk, w = Math.round((st.fa * 2 % 1) * 18);
        const hp = lerpP([cx + 14, t + 86], [cx - 24 + w, t + 74], k);
        armTo(p, hp[0], hp[1], { from: [cx + 30, t + 100], sleeve: shirt, skin: sk, pose: 'flat', w: 18, bend: 2 });
      }
    },
    after(c, st) {
      // облака муки при срыве
      const bk = st.bk;
      if (st.fid >= 0 && st.fk > 0.9) { // отряхивается: облачко муки
        const cx = H0.cx, t = H0.top;
        const x0 = cx - 26 + Math.round((st.fa * 2 % 1) * 18), y0 = t + 70 - Math.round((st.fa * 2 % 1) * 6);
        for (let y = y0 - 5; y <= y0 + 3; y++) for (let x = x0 - 6; x <= x0 + 4; x++) {
          const dx = x - x0, dy = y - y0, r = (dx * dx + dy * dy) / 26; if (r < 1 && G.bayer(x, y) < 9 * (1 - r)) px(c, x, y, r < 0.4 ? PAL.white : R.neutral[8]);
        }
      }
      if (bk < 0) return;
      const cx = H0.cx, t = H0.top;
      const puffs = [[cx - 30, t + 74], [cx + 24, t + 66], [cx - 8, t + 92], [cx + 34, t + 94], [cx - 40, t + 96], [cx + 8, t + 56]];
      const k = bk / 7;
      puffs.forEach((pf, n) => {
        const r = Math.round(3 + k * 12 + (n % 3));
        const ox = Math.round((n % 2 ? 1 : -1) * k * (10 + n * 3)), oy = Math.round(-k * (16 + n * 4));
        const x0 = pf[0] + ox, y0 = pf[1] + oy;
        const dens = Math.round(16 - k * 10);
        if (dens <= 0) return;
        for (let y = y0 - r; y <= y0 + r; y++) for (let x = x0 - r; x <= x0 + r; x++) {
          const dx = x - x0, dy = y - y0; const rr = (dx * dx + dy * dy) / (r * r);
          if (rr > 1) continue;
          const lv = Math.round(dens * (1 - rr * 0.7));
          if (G.bayer(x, y) < lv) px(c, x, y, rr < 0.4 ? PAL.white : R.neutral[8]);
        }
      });
    },
    face(st) {
      const bk = st.bk;
      if (bk >= 0 || st.emo === 'breakdown') {
        if (bk >= 0 && bk < 2) return { eyes: 'tiny', brows: [-3, -2], mouth: 'O', noBlink: true };
        return { eyes: 'angry', brows: [3, -2], mouth: 'wail', noBlink: true, flatBrow: true, talk: ['gritO', 'wail'] };
      }
      const f = witnessFace(st);
      if (st.emo === 'normal') { f.mouth = 'smirk'; f.brows = [1, -1]; f.eyes = 'half'; }
      return f;
    },
    post(c, st) {
      const cx = H0.cx, t = H0.top;
      if (st.emo === 'nervous') { sweat(c, cx - 4, t + 3); sweat(c, cx - 15, t + 12); sweat(c, cx + 8, t + 8); }
      if (st.emo === 'shocked') sweat(c, cx - 15, t + 10, true);
      if (st.emo === 'breakdown' || st.bk >= 3) {
        // пар из ушей/пот
        sweat(c, cx - 2, t + 4, true); sweat(c, cx + 9, t + 6, true);
        c.globalAlpha = 0.45;
        const s = (st.bk < 0 ? 7 : st.bk) & 1;
        G.rect(c, cx + 18, t + 8 - s, 2, 2, PAL.white); G.rect(c, cx + 21, t + 4 - s, 3, 2, PAL.white); G.rect(c, cx + 23, t + 0 - s, 2, 2, PAL.white);
        c.globalAlpha = 1;
      }
    },
    iso: { skin: sk, top: shirt, pants: R.neutral, shoes: R.neutral[0], build: 'big', seed: 0.2,
      hairDraw: isoHair(hg, 'bald'),
      extra(x, f) { x.fillStyle = susp[3]; x.fillRect(f.fx + 2, f.ty, 1, 8); x.fillRect(f.fx + f.tw - 3, f.ty, 1, 8); x.fillStyle = PAL.white; x.fillRect(f.fx + 5, f.ty + 4, 2, 1); } },
  });
})();

/* ====================== ЛИЗА ПАК ====================== */
(function () {
  const sk = R.skinL;
  const hk = R.hairBlack;
  const hood = [R.neutral[3], R.neutral[4], R.neutral[5], R.neutral[6], R.neutral[7]];
  const H = { cx: 54, top: 22, ramp: sk, fem: true, jaw: -3, chin: -1, sideX: 4 };
  const BL = [R.red[2], R.red[3], R.red[4], R.skinL[3], R.skinL[4]];
  reg('park', {
    name: 'Лиза Пак', voice: 'high', emos: DEF_EMOS, seed: 2, fidEmos: ['normal', 'worried', 'hopeful'], fidFace(st, f) { if (st.fk > 0.4) { f.eyes = 'down'; f.brows = [-1, 0]; } },
    feat: feat(H, { iris: [R.hairBrown[0], R.hairBrown[1], R.hairBrown[3]], brow: hk[1], brow2: hk[2], browThick: 2, lash: true, lipL: R.skinL[3], mouthLine: R.skinL[0] }),
    build(p, st) {
      const cx = H.cx, t = H.top, e = st.emo;
      // волосы сзади до плеч
      p.part({ s: [P([cx - 6, t + 2], [cx + 18, t + 4], [cx + 22, t + 24], [cx + 24, t + 46], [cx + 6, t + 48], [cx + 2, t + 30])], ramp: hk, base: 2, cast: 0 });
      neck(p, H, 10, 48);
      // огромная толстовка
      const hunch = e === 'worried' ? 3 : 0;
      const body = [[cx - 12, t + 40 + hunch], [cx - 30, t + 46 + hunch], [cx - 39, t + 58], [cx - 42, BH], [cx + 45, BH], [cx + 44, t + 58], [cx + 38, t + 46 + hunch], [cx + 18, t + 40 + hunch]];
      const m = torso(p, body, hood, 3, { shT: 0.34, hiT: 0.82 });
      // капюшон, лежащий на плечах
      p.part({ s: [C(cx - 22, t + 46, cx + 4, t + 58, cx + 32, t + 44, 9, 9)], ramp: hood, base: 2, cast: 1, hiT: 0.7 });
      p.stroke(C(cx - 18, t + 47, cx + 4, t + 56, cx + 29, t + 45, 1), -1, hood);
      p.stroke(C(cx - 22, t + 45, cx + 4, t + 54, cx + 30, t + 42, 1), 1, hood);
      // шнурки
      p.part({ s: [C(cx - 4, t + 58, cx - 6, t + 72, cx - 4, t + 84, 2)], ramp: R.neutral, base: 8, cast: 1 });
      p.part({ s: [C(cx + 6, t + 58, cx + 8, t + 70, cx + 7, t + 80, 2)], ramp: R.neutral, base: 7, cast: 1 });
      p.set(cx - 4, t + 85, R.neutral, 5); p.set(cx + 7, t + 81, R.neutral, 5);
      // большие складки
      fold(p, C(cx - 35, t + 60, cx - 33, t + 84, cx - 37, BH, 1), -1, hood);
      fold(p, C(cx + 37, t + 62, cx + 38, t + 84, cx + 35, BH, 1), -1, hood);
      fold(p, C(cx - 28, t + 70, cx - 20, t + 78, cx - 26, t + 90, 1), -1, hood);
      fold(p, C(cx + 26, t + 70, cx + 20, t + 80, cx + 28, t + 92, 1), -1, hood);
      fold(p, C(cx - 27, t + 70, cx - 19, t + 77, cx - 25, t + 89, 1), 1, hood);
      // пятна краски на толстовке
      const sp = [[cx + 29, t + 74, R.blue[4]], [cx + 30, t + 75, R.blue[5]], [cx - 33, t + 82, R.gold[4]], [cx - 32, t + 83, R.gold[3]], [cx + 12, t + 96, R.red[3]], [cx - 14, t + 64, R.teal[4]]];
      for (const s of sp) if (m[s[1] * BW + s[0]]) p.px(s[0], s[1], s[2]);
      // руки (кисти с краской) — сжимают рукава у груди
      const handY = t + 92 + (e === 'hopeful' ? -6 : 0) - Math.round(st.fk * 8);
      p.part({ s: [C(cx - 35, t + 70, cx - 29, handY + 6, cx - 14, handY + 6, 14, 12)], ramp: hood, base: 3, cast: 1 });
      p.part({ s: [C(cx + 38, t + 72, cx + 32, handY + 8, cx + 14, handY + 6, 14, 12)], ramp: hood, base: 2, cast: 1 });
      // манжеты
      p.part({ s: [C(cx - 16, handY, cx - 14, handY + 6, cx - 15, handY + 12, 5)], ramp: hood, base: 1, cast: 1 });
      p.part({ s: [C(cx + 14, handY + 1, cx + 16, handY + 7, cx + 15, handY + 12, 5)], ramp: hood, base: 1, cast: 1 });
      // кисти, сцепленные
      p.part({ s: [P([cx - 14, handY + 1], [cx - 2, handY - 1], [cx + 4, handY + 3], [cx + 2, handY + 11], [cx - 12, handY + 12])], ramp: sk, base: 3, cast: 1 });
      p.part({ s: [P([cx + 13, handY + 2], [cx + 2, handY + 1], [cx - 4, handY + 5], [cx - 2, handY + 12], [cx + 12, handY + 12])], ramp: sk, base: 2, cast: 1 });
      for (let k = 0; k < 4; k++) { p.set(cx - 5 + k * 2, handY + 3 + k, sk, 1); }
      for (let k = 0; k < 3; k++) { p.shift(cx + 2 + k * 3, handY + 8, -1, sk); }
      // краска на руках
      const ps = [[cx - 10, handY + 4, R.blue[4]], [cx - 9, handY + 4, R.blue[5]], [cx - 9, handY + 5, R.blue[4]], [cx + 6, handY + 6, R.red[3]], [cx + 7, handY + 6, R.red[4]], [cx + 7, handY + 7, R.red[3]],
        [cx - 3, handY + 9, R.gold[4]], [cx - 2, handY + 9, R.gold[3]], [cx + 10, handY + 3, R.teal[4]], [cx - 6, handY + 1, R.teal[4]], [cx - 12, handY + 9, R.purple[4]]];
      for (const s of ps) p.px(s[0], s[1], s[2]);
      head(p, H);
      if (e === 'relieved' || e === 'hopeful') for (let y = t + 23; y <= t + 26; y++) for (let x = cx - 5; x <= cx + 1; x++) if (G.bayer(x, y) < 5 && p.ramp[y * BW + x] === sk) p.set(x, y, BL, 3);
      ear(p, H);
      nose(p, H, 'small');
      // пятно краски на щеке
      p.px(cx + 2, t + 27, R.blue[5]); p.px(cx + 3, t + 27, R.blue[4]); p.px(cx + 3, t + 28, R.blue[4]);
      // чёлка и пряди по сторонам
      const strands = [
        C(cx - 13, t + 14, cx - 14, t + 2, cx - 4, t - 2, 5, 6),
        C(cx - 8, t + 13, cx - 8, t + 2, cx + 4, t - 2, 5, 7),
        C(cx - 2, t + 10, cx + 2, t, cx + 12, t - 1, 5, 7),
        C(cx + 4, t + 6, cx + 12, t - 1, cx + 18, t + 6, 6, 5),
        C(cx + 10, t + 6, cx + 20, t + 10, cx + 22, t + 30, 6, 3),
        C(cx + 14, t + 20, cx + 22, t + 34, cx + 22, t + 46, 6, 2),
        C(cx + 6, t + 14, cx + 10, t + 30, cx + 6, t + 46, 5, 2),
        C(cx - 12, t + 12, cx - 15, t + 20, cx - 12, t + 28, 3, 1),
      ];
      for (const s of strands) p.part({ s: [s], ramp: hk, base: 2, cast: 1, shT: 0.3, hiT: 0.75 });
      // цветная прядь (бирюза)
      p.part({ s: [C(cx - 6, t + 0, cx - 6, t + 8, cx - 9, t + 15, 3, 2)], ramp: R.teal, base: 3, cast: 1, hiT: 0.7 });
      p.part({ s: [C(cx + 8, t + 18, cx + 11, t + 32, cx + 8, t + 44, 3, 2)], ramp: R.teal, base: 2, cast: 1 });
      // блики на волосах
      p.stroke(C(cx - 4, t + 1, cx + 2, t - 1, cx + 6, t + 0, 1), 2, hk);
      p.stroke(C(cx + 12, t + 2, cx + 15, t + 3, cx + 17, t + 6, 1), 1, hk);
    },
    face(st) {
      const f = defendantFace(st);
      if (st.emo === 'normal') { f.eyes = 'look'; f.brows = [-1, 0]; }
      return f;
    },
    post(c, st) {
      const cx = H.cx, t = H.top;
      if (st.emo === 'relieved') { tear(c, cx - 2, t + 19, 8); tear(c, cx - 12, t + 19, 5); }
      if (st.emo === 'worried') { tear(c, cx - 1, t + 20, 2); }
      if (st.fid >= 0 && st.fk > 0.9) { // отковыривает краску: ноготь и отлетающая чешуйка
        const hy = t + 84, a = st.fa;
        px(c, cx + 5, hy + 2, R.skinL[4]); px(c, cx + 6, hy + 1, R.skinL[4]);
        const fx = cx + 8 + Math.round(a * 10), fy = hy - 2 - Math.round(Math.sin(a * Math.PI) * 10);
        if (a > 0.25) { px(c, fx, fy, R.red[4]); px(c, fx + 1, fy, R.red[3]); }
      }
    },
    iso: { skin: sk, top: hood, pants: R.blue, shoes: R.neutral[8], build: 'mid', seed: 0.9,
      hairDraw(x, hx, hy, fr, pose) { isoHair(hk, 'bob')(x, hx, hy); x.fillStyle = R.teal[4]; x.fillRect(hx + 1, hy + 1, 1, 3); },
      extra(x, f) { x.fillStyle = R.blue[4]; x.fillRect(f.fx - 1, f.armY + 8, 1, 1); x.fillStyle = R.red[4]; x.fillRect(f.fx + f.tw, f.armY + 8, 1, 1); } },
  });
})();

/* ====================== ИРЭН БЕЛЛ ====================== */
(function () {
  const sk = R.skinL;
  const plat = [R.hairGrey[1], R.stone[2], R.stone[4], R.hairGrey[3], R.hairGrey[4]];
  const black = [R.neutral[0], R.neutral[1], R.neutral[2], R.neutral[3], R.neutral[4]];
  const H = { cx: 54, top: 22, ramp: sk, fem: true, jaw: -2, chin: 0, sideX: 4 };
  reg('bell', {
    name: 'Ирэн Белл', voice: 'mid', emos: WIT_EMOS, seed: 9, fidEmos: ['normal', 'nervous', 'angry', 'shocked'], fidFace(st, f) { if (st.fk > 0.6) { f.eyes = 'half'; f.mouth = 'smirk'; } }, bkFrames: 8,
    feat: feat(H, { iris: [R.blue[2], R.blue[4], R.blue[5]], brow: R.hairBrown[2], brow2: R.hairBrown[3], browThick: 1, lash: true, lip: [R.red[1], R.red[2], R.red[3]], mouthLine: R.red[0] }),
    shake: (k, t) => (k > 0.2 && k < 0.55 ? ((Math.floor(t * 30) & 1) ? 1 : -1) : 0),
    build(p, st) {
      const cx = H.cx, t = H.top, e = st.emo, bk = st.bk;
      const messy = bk >= 3 || e === 'breakdown';
      // каре: задняя масса
      if (!messy) p.part({ s: [P([cx - 8, t - 2], [cx + 16, t - 1], [cx + 22, t + 12], [cx + 22, t + 30], [cx + 16, t + 34], [cx + 4, t + 34])], ramp: plat, base: 2, cast: 0 });
      else p.part({ s: [P([cx - 8, t - 2], [cx + 18, t - 3], [cx + 26, t + 12], [cx + 27, t + 38], [cx + 20, t + 42], [cx + 4, t + 36])], ramp: plat, base: 2, cast: 0 });
      neck(p, H, 10, 48);
      // водолазка
      const body = [[cx - 10, t + 38], [cx - 26, t + 46], [cx - 34, t + 58], [cx - 35, BH], [cx + 40, BH], [cx + 39, t + 58], [cx + 33, t + 46], [cx + 14, t + 38]];
      torso(p, body, black, 3, { hiT: 0.82, shT: 0.4 });
      // высокий ворот
      p.part({ s: [P([cx - 9, t + 30], [cx + 10, t + 30], [cx + 13, t + 42], [cx - 10, t + 43])], ramp: black, base: 3, cast: 1, hiT: 0.7 });
      for (let k = 0; k < 3; k++) p.stroke(['l', cx - 9, t + 33 + k * 3, cx + 12, t + 33 + k * 3], -1, black);
      fold(p, C(cx - 29, t + 60, cx - 28, t + 84, cx - 30, BH, 1), -1, black);
      fold(p, C(cx + 33, t + 60, cx + 33, t + 84, cx + 34, BH, 1), -1, black);
      fold(p, C(cx - 20, t + 58, cx - 12, t + 62, cx - 6, t + 60, 1), 1, black);
      // массивное ожерелье-кулон
      p.part({ s: [C(cx - 12, t + 44, cx - 2, t + 60, cx + 14, t + 44, 1)], ramp: R.gold, base: 3, cast: 1 });
      p.part({ s: [P([cx - 4, t + 54], [cx + 4, t + 54], [cx, t + 64])], ramp: R.gold, base: 3, cast: 1 });
      p.set(cx, t + 57, R.red, 3); p.set(cx - 1, t + 56, R.red, 4);
      // сложенные руки? — нет, держит планшет-каталог у груди
      head(p, H);
      ear(p, H);
      nose(p, H, 'sharp');
      // скулы острее
      p.set(cx - 3, t + 25, sk, 2); p.set(cx - 2, t + 26, sk, 2); p.set(cx - 2, t + 27, sk, 2);
      // каре: передние пряди
      if (!messy) {
        const strands = [
          C(cx - 10, t + 10, cx - 12, t - 2, cx + 4, t - 3, 6, 6),
          C(cx - 2, t + 6, cx + 8, t - 4, cx + 18, t + 2, 7, 6),
          C(cx + 10, t + 2, cx + 22, t + 6, cx + 22, t + 32, 7, 6),
          C(cx + 6, t + 10, cx + 14, t + 20, cx + 12, t + 34, 7, 6),
          C(cx - 9, t + 5, cx - 14, t + 10, cx - 12, t + 13, 4, 2),
        ];
        for (const s of strands) p.part({ s: [s], ramp: plat, base: 3, cast: 1, hiT: 0.7, shT: 0.3 });
        // ровный срез каре
        p.strokeT(['l', cx + 4, t + 34, cx + 22, t + 33], 1, plat);
        p.stroke(C(cx - 6, t - 1, cx + 2, t - 3, cx + 8, t - 2, 1), 1, plat);
        p.stroke(C(cx + 14, t + 4, cx + 18, t + 10, cx + 19, t + 20, 1), -1, plat);
      } else {
        // растрёпанные пряди
        const k = st.bk < 0 ? 7 : st.bk;
        const sw = Math.min(1, (k - 2) / 4);
        const strands = [
          C(cx - 10, t + 8, cx - 12, t - 4, cx + 4, t - 6, 6, 4),
          C(cx - 2, t + 4, cx + 8, t - 8, cx + 20, t - 2, 7, 4),
          C(cx + 10, t + 2, cx + 26, t + 4, cx + 26, t + 36, 7, 4),
          C(cx + 6, t + 8, cx + 16, t + 18, cx + 18, t + 38, 6, 3),
          C(cx - 10, t + 6, cx - 18, t + 12 + sw * 4, cx - 14, t + 26, 4, 1),
          C(cx - 6, t + 4, cx - 10, t + 14, cx - 8, t + 24 + sw * 4, 4, 1),
          C(cx + 2, t - 4, cx - 6, t - 10, cx - 14, t - 6, 3, 1),
          C(cx + 12, t - 2, cx + 18, t - 10, cx + 26, t - 8, 3, 1),
          C(cx + 22, t + 20, cx + 30, t + 26, cx + 30, t + 34, 3, 1),
        ];
        for (const s of strands) p.part({ s: [s], ramp: plat, base: 3, cast: 1, hiT: 0.7, shT: 0.3 });
      }
      // массивные серьги (геометрические, золото)
      const ex = cx + 9, ey = t + 27;
      const sway = (bk >= 0 && bk < 7) ? ((bk & 1) ? 2 : -2) : 0;
      p.part({ s: [Rc(ex, ey, 2, 2)], ramp: R.gold, base: 3, cast: 1 });
      p.part({ s: [P([ex - 3 + sway, ey + 3], [ex + 5 + sway, ey + 3], [ex + 1 + sway, ey + 11])], ramp: R.gold, base: 3, cast: 1, hiT: 0.6 });
      p.set(ex + 1 + sway, ey + 5, R.red, 3);
      if (st.fid >= 0 && bk < 0) {
        const k = st.fk;
        const hp = lerpP([cx + 14, t + 82], [cx + 3, t + 15 - Math.round(st.fa * 1)], k);
        armTo(p, hp[0], hp[1], { from: [cx + 26, t + 96], sleeve: black, skin: sk, pose: 'pinch', w: 14, bend: 10 });
      }
    },
    face(st) {
      const bk = st.bk;
      if (bk >= 0 || st.emo === 'breakdown') {
        if (bk >= 0 && bk < 3) return { eyes: 'tiny', brows: [-2, -2], mouth: 'O', noBlink: true };
        return { eyes: 'wide', brows: [-3, 1], mouth: 'wail', noBlink: true, talk: ['open', 'wail'] };
      }
      const f = witnessFace(st);
      if (st.emo === 'normal') { f.eyes = 'half'; f.brows = [0, -2]; f.mouth = 'smirk'; }
      return f;
    },
    post(c, st) {
      const cx = H.cx, t = H.top;
      const bk = st.emo === 'breakdown' && st.bk < 0 ? 7 : st.bk;
      // красные очки «кошачий глаз»
      let slide = 0, crack = false;
      if (bk >= 0) { slide = bk >= 2 ? Math.min(4, bk - 1) : 0; crack = bk >= 1; }
      if (st.fid >= 0 && st.fk > 0.95) slide = st.fa < 0.5 ? 1 : 0;
      const gy = t + 14 + slide;
      const fr = R.red[3], frD = R.red[2], hi = R.red[5];
      const box = (x0, y0, w, h) => {
        for (let i = 0; i < w; i++) { px(c, x0 + i, y0, i < 2 ? hi : fr); px(c, x0 + i, y0 + h - 1, frD); }
        for (let j = 0; j < h; j++) { px(c, x0, y0 + j, fr); px(c, x0 + w - 1, y0 + j, frD); }
        px(c, x0 + w - 1, y0 - 1, fr); px(c, x0 + w, y0 - 1, fr); px(c, x0 + w, y0 - 2, hi); // уголок «кошки»
      };
      // стёкла (лёгкий отблеск)
      c.globalAlpha = 0.25; G.rect(c, cx - 8, gy + 1, 9, 5, R.blue[6]); G.rect(c, cx - 16, gy + 1, 4, 5, R.blue[6]); c.globalAlpha = 1;
      box(cx - 9, gy, 11, 7);
      box(cx - 17, gy, 6, 7);
      px(c, cx - 11, gy + 2, fr); px(c, cx - 10, gy + 2, fr);
      for (let i = 1; i < 14; i++) px(c, cx + 1 + i, gy + 2 + (i > 6 ? 1 : 0), frD);
      px(c, cx - 7, gy + 1, PAL.white); px(c, cx - 6, gy + 1, PAL.white); px(c, cx - 7, gy + 2, PAL.white);
      if (crack) { // трещина по ближнему стеклу
        const k = [[-3, 1], [-4, 2], [-4, 3], [-5, 4], [-3, 3], [-2, 4], [-1, 5], [-5, 5], [-6, 2]];
        for (const q of k) px(c, cx + q[0], gy + q[1], PAL.white);
        px(c, cx - 2, gy + 2, R.neutral[7]); px(c, cx - 6, gy + 4, R.neutral[7]);
        if (bk >= 3) { const k2 = [[-14, 2], [-15, 3], [-13, 4], [-14, 5]]; for (const q of k2) px(c, cx + q[0], gy + q[1], PAL.white); }
      }
      if (st.emo === 'nervous') sweat(c, cx - 15, t + 7);
      if (st.emo === 'shocked') sweat(c, cx - 16, t + 8, true);
      if (bk >= 4) { sweat(c, cx - 16, t + 6, true); sweat(c, cx + 2, t + 4); tear(c, cx - 1, t + 21 + Math.min(slide, 2), 4); }
    },
    iso: { skin: sk, top: black, pants: R.neutral, shoes: R.neutral[0], build: 'thin', seed: 0.4,
      hairDraw: isoHair(plat, 'bob'),
      extra(x, f) { x.fillStyle = R.red[3]; x.fillRect(f.hx, f.hy + 4, 2, 1); x.fillRect(f.hx + 3, f.hy + 4, 2, 1); x.fillStyle = R.gold[4]; x.fillRect(f.hx + 5, f.hy + 6, 1, 2); } },
  });
})();

/* ====================== МАРКУС ДОЙЛ ====================== */
(function () {
  const sk = R.skinM, hk = R.hairBlack;
  const shirt = [R.teal[0], R.teal[1], R.teal[2], R.teal[3], R.teal[4], R.teal[5]];
  const tee = R.neutral;
  const H = { cx: 52, top: 20, ramp: sk, jaw: 1, chin: 1, sideX: 3 };
  reg('doyle', {
    name: 'Маркус Дойл', voice: 'mid', emos: DEF_EMOS, seed: 4, fidEmos: ['normal', 'worried', 'hopeful'], fidFace(st, f) { if (st.fk > 0.6) { f.eyes = 'half'; f.mouth = 'flat'; } },
    feat: feat(H, { iris: [R.hairBrown[0], R.hairBrown[1], R.hairBrown[3]], brow: hk[0], brow2: hk[1], browThick: 2, lid: R.neutral[0] }),
    build(p, st) {
      const cx = H.cx, t = H.top, e = st.emo;
      neck(p, H, 14, 50);
      // белая футболка под рубашкой
      p.part({ s: [P([cx - 10, t + 38], [cx + 14, t + 38], [cx + 10, t + 70], [cx - 8, t + 70])], ramp: tee, base: 7, cast: 1 });
      p.part({ s: [C(cx - 8, t + 39, cx + 2, t + 44, cx + 12, t + 39, 2)], ramp: tee, base: 6, cast: 0 }); // горловина
      // рубашка навыпуск, расстёгнута (клетка тёмный бирюзовый)
      const L = [[cx - 12, t + 38], [cx - 29, t + 44], [cx - 38, t + 56], [cx - 40, BH], [cx - 2, BH], [cx - 6, t + 52]];
      const Rr = [[cx + 14, t + 38], [cx + 6, t + 56], [cx + 10, BH], [cx + 44, BH], [cx + 43, t + 58], [cx + 35, t + 44]];
      const m1 = torso(p, L, shirt, 3, { shT: 0.25 });
      const m2 = torso(p, Rr, shirt, 3, { lx: 0.9, shT: 0.5 });
      // клетка
      for (let y = t + 40; y < BH; y++) for (let x = 0; x < BW; x++) {
        const i = y * BW + x; if (!(m1[i] || m2[i]) || p.ramp[i] !== shirt) continue;
        const gx = ((x + 200) % 8), gy = (y % 8);
        if (gx === 0 || gy === 0) p.shift(x, y, -1, shirt);
        if (gx === 0 && gy === 0) p.shift(x, y, -1, shirt);
      }
      // лацканы/воротник
      p.part({ s: [P([cx - 11, t + 36], [cx - 4, t + 46], [cx - 9, t + 54], [cx - 18, t + 42])], ramp: shirt, base: 4, cast: 1 });
      p.part({ s: [P([cx + 15, t + 36], [cx + 7, t + 46], [cx + 12, t + 54], [cx + 22, t + 41])], ramp: shirt, base: 3, cast: 1 });
      // скрещённые руки: предплечья с закатанными рукавами
      const ay = t + 88 + (e === 'worried' ? -2 : 0);
      // рукава (закатаны до локтя)
      p.part({ s: [C(cx - 38, t + 64, cx - 35, ay + 6, cx - 29, ay + 10, 16, 14)], ramp: shirt, base: 3, cast: 1 });
      p.part({ s: [C(cx + 42, t + 64, cx + 40, ay + 4, cx + 34, ay + 8, 16, 14)], ramp: shirt, base: 2, cast: 1 });
      // заднее предплечье (правая рука персонажа, уходит под)
      p.part({ s: [C(cx + 33, ay + 6, cx + 10, ay + 2, cx - 16, ay - 4, 11, 9)], ramp: sk, base: 2, cast: 1 });
      p.part({ s: [E(cx - 18, ay - 3, 5, 4)], ramp: sk, base: 2, cast: 1 });
      // переднее предплечье с татуировкой
      p.part({ s: [C(cx - 29, ay + 10, cx - 4, ay + 14, cx + 26, ay + 6, 12, 10)], ramp: sk, base: 3, cast: 2 });
      p.part({ s: [E(cx + 28, ay + 6, 5, 5)], ramp: sk, base: 3, cast: 1 });
      p.set(cx + 27, ay + 3, sk, 2); p.set(cx + 28, ay + 5, sk, 2); p.set(cx + 29, ay + 7, sk, 2);
      // манжета закатанного рукава (светлая изнанка)
      p.part({ s: [C(cx - 32, ay + 2, cx - 29, ay + 10, cx - 30, ay + 18, 5)], ramp: shirt, base: 5, cast: 1 });
      p.part({ s: [C(cx + 34, ay - 2, cx + 35, ay + 6, cx + 35, ay + 13, 5)], ramp: shirt, base: 4, cast: 1 });
      // волоски/жилы
      p.stroke(C(cx - 22, ay + 9, cx - 6, ay + 11, cx + 12, ay + 7, 1), 1, sk);
      // татуировка: нож шеф-повара и ветка (чернила)
      const tx = cx - 20, ty = ay + 12;
      const ink = PAL.ink, ink2 = PAL.inkDark;
      for (let i = 0; i < 12; i++) p.px(tx + i, ty - Math.round(i * 0.25), i < 4 ? ink2 : R.blue[3]); // лезвие
      for (let i = 0; i < 9; i++) p.px(tx + 1 + i, ty + 1 - Math.round(i * 0.25), i < 8 ? R.blue[3] : ink);
      p.px(tx + 12, ty - 3, ink2); p.px(tx + 13, ty - 3, ink2); p.px(tx + 14, ty - 4, ink2); p.px(tx + 15, ty - 4, ink2); // рукоять
      p.px(tx + 4, ty + 3, ink); p.px(tx + 6, ty + 3, ink); p.px(tx + 8, ty + 2, ink); p.px(tx + 5, ty + 4, R.green[3]); p.px(tx + 7, ty + 3, R.green[3]); p.px(tx + 9, ty + 3, R.green[3]);
      p.px(tx - 2, ty + 1, ink); p.px(tx - 1, ty + 2, ink);
      head(p, H);
      ear(p, H);
      nose(p, H, 'n');
      // щетина/лёгкая борода
      for (let y = t + 28; y < t + 38; y++) for (let x = cx - 12; x < cx + 10; x++) if (p.ramp[y * BW + x] === sk && G.bayer(x, y) < 6 && !(y < t + 30 && x < cx - 6)) p.shift(x, y, -1, sk);
      // шрам-ожог на брови (повар)
      // короткие кудри
      const rng = G.rng(77);
      p.part({ s: [E(cx + 2, t + 7, 15, 9), E(cx + 12, t + 14, 6, 8)], ramp: hk, base: 2, cast: 1 });
      const curls = [];
      for (let k = 0; k < 26; k++) {
        const a = rng() * Math.PI - Math.PI * 0.05, r = 10 + rng() * 5;
        const x = cx + 2 + Math.cos(Math.PI + a) * r * 1.05, y = t + 9 - Math.sin(a) * r * 0.75;
        curls.push([x, y]);
      }
      curls.push([cx + 16, t + 12], [cx + 17, t + 17], [cx + 14, t + 20], [cx - 11, t + 6], [cx - 8, t + 3], [cx + 3, t + 2], [cx + 8, t + 4], [cx - 2, t + 5]);
      for (const q of curls) {
        if (q[0] < cx - 14 || q[1] > t + 24) continue;
        p.part({ s: [E(q[0], q[1], 2, 2)], ramp: hk, base: 3, cast: 0, hiT: 0.7, shT: 0.35 });
        p.set(q[0] - 1, q[1] - 1, hk, 4);
      }
      if (st.fid >= 0 && st.fk >= 0.3) {
        const k = st.fk, w = Math.round(Math.sin(st.fa * Math.PI * 5) * 2);
        const hp = lerpP([cx + 20, t + 90], [cx + 9 + w, t + 4], k);
        armTo(p, hp[0], hp[1], { from: [cx + 30, t + 70], sleeve: sk, skin: sk, pose: 'fist', w: 11, bend: 10, slBase: 2 });
      }
    },
    face(st) {
      const f = defendantFace(st);
      if (st.emo === 'normal') { f.brows = [1, 0]; f.mouth = 'flat'; f.flatBrow = true; }
      return f;
    },
    post(c, st) {
      const cx = H.cx, t = H.top;
      if (st.emo === 'relieved') { tear(c, cx - 3, t + 19, 6); }
      if (st.emo === 'worried') sweat(c, cx - 15, t + 8);
    },
    iso: { skin: sk, top: shirt, pants: R.neutral, shoes: R.neutral[1], build: 'mid', seed: 0.1, shirt: R.neutral[8],
      hairDraw: isoHair(hk, 'curly'),
      extra(x, f) { if (!f.sit) { x.fillStyle = shirt[2]; x.fillRect(f.fx, 22, 10, 2); } } },
  });
})();

/* ====================== ДЕТЕКТИВ РЭЙ МОРАЛЕС ====================== */
(function () {
  const sk = R.skinM;
  const hs = [R.hairBlack[0], R.hairBlack[2], R.hairBlack[3], R.hairGrey[1], R.hairGrey[3]];
  const coat = [R.stone[0], R.stone[1], R.stone[2], R.stone[3], R.stone[4], R.stone[5]];
  const shirt = [R.neutral[5], R.neutral[6], R.neutral[7], R.neutral[8], R.neutral[9]];
  const H0 = { cx: 52, top: 20, ramp: sk, jaw: 1, chin: 1, sideX: 3, gaunt: true };
  reg('morales', {
    name: 'Детектив Рэй Моралес', voice: 'low', emos: WIT_EMOS, seed: 13, fidEmos: ['normal', 'nervous', 'angry', 'shocked'], fidFace(st, f) { if (st.fk > 0.3) { f.eyes = 'down'; f.brows = [-1, 1]; } }, bkFrames: 8,
    feat: feat(H0, { iris: [R.hairBrown[0], R.hairBrown[2], R.hairBrown[3]], brow: hs[1], brow2: hs[3], browThick: 2, lid: R.neutral[0], mouth: [H0.cx - 12, H0.top + 29] }),
    shake: (k) => 0,
    build(p, st) {
      const H = Object.assign({}, H0);
      const e = st.emo, bk = st.emo === 'breakdown' && st.bk < 0 ? 7 : st.bk;
      // в осознании голова слегка опускается
      if (bk >= 4) { H.top += 1; }
      st.hy = H.top - H0.top;
      const cx = H.cx, t = H.top, T0 = H0.top;
      neck(p, H, 14, 50);
      // рубашка + галстук (ослабленный)
      p.part({ s: [P([cx - 12, T0 + 38], [cx + 16, T0 + 38], [cx + 14, BH], [cx - 14, BH])], ramp: shirt, base: 2, cast: 1 });
      p.part({ s: [P([cx - 10, T0 + 37], [cx - 2, T0 + 46], [cx - 8, T0 + 51], [cx - 15, T0 + 42])], ramp: shirt, base: 3, cast: 1 });
      p.part({ s: [P([cx + 13, T0 + 37], [cx + 4, T0 + 46], [cx + 10, T0 + 51], [cx + 18, T0 + 41])], ramp: shirt, base: 2, cast: 1 });
      p.part({ s: [P([cx - 1, T0 + 47], [cx + 5, T0 + 47], [cx + 4, T0 + 51], [cx + 6, T0 + 74], [cx + 2, T0 + 80], [cx - 1, T0 + 74], [cx + 1, T0 + 51])], ramp: R.red, base: 2, cast: 1 });
      for (let y = T0 + 54; y < T0 + 78; y += 4) { p.set(cx + 2, y, R.red, 1); p.set(cx + 3, y + 1, R.red, 1); }
      // тренч: левая и правая полы + лацканы
      const L = [[cx - 14, T0 + 38], [cx - 30, T0 + 44], [cx - 39, T0 + 56], [cx - 42, BH], [cx - 8, BH], [cx - 6, T0 + 76], [cx - 10, T0 + 52]];
      const Rr = [[cx + 18, T0 + 38], [cx + 12, T0 + 52], [cx + 12, T0 + 78], [cx + 16, BH], [cx + 45, BH], [cx + 44, T0 + 58], [cx + 37, T0 + 44]];
      torso(p, L, coat, 3, { shT: 0.25 });
      torso(p, Rr, coat, 3, { lx: 0.9, shT: 0.55 });
      // лацканы
      p.part({ s: [P([cx - 14, T0 + 38], [cx - 6, T0 + 56], [cx - 4, T0 + 76], [cx - 14, T0 + 60], [cx - 24, T0 + 44])], ramp: coat, base: 4, cast: 2 });
      p.part({ s: [P([cx + 18, T0 + 38], [cx + 10, T0 + 56], [cx + 10, T0 + 76], [cx + 20, T0 + 58], [cx + 29, T0 + 44])], ramp: coat, base: 3, cast: 2 });
      // погон и пуговицы
      p.part({ s: [P([cx - 35, T0 + 50], [cx - 24, T0 + 44], [cx - 22, T0 + 48], [cx - 34, T0 + 54])], ramp: coat, base: 4, cast: 1 });
      p.part({ s: [P([cx + 29, T0 + 44], [cx + 40, T0 + 50], [cx + 39, T0 + 54], [cx + 29, T0 + 48])], ramp: coat, base: 3, cast: 1 });
      for (let k = 0; k < 2; k++) { p.part({ s: [E(cx + 22, T0 + 84 + k * 18, 2, 2)], ramp: R.wood, base: 3, cast: 1 }); p.part({ s: [E(cx - 18, T0 + 84 + k * 18, 2, 2)], ramp: R.wood, base: 4, cast: 1 }); }
      // мятые складки
      fold(p, C(cx - 35, T0 + 60, cx - 33, T0 + 84, cx - 35, BH, 1), -1, coat);
      fold(p, C(cx + 38, T0 + 62, cx + 39, T0 + 84, cx + 37, BH, 1), -1, coat);
      fold(p, C(cx - 29, T0 + 72, cx - 22, T0 + 82, cx - 28, T0 + 96, 1), -1, coat);
      fold(p, C(cx + 30, T0 + 72, cx + 26, T0 + 82, cx + 32, T0 + 98, 1), -1, coat);
      fold(p, C(cx - 29, T0 + 72, cx - 21, T0 + 81, cx - 27, T0 + 95, 1), 1, coat);
      // значок на поясе (виден между полами)
      p.part({ s: [P([cx - 4, T0 + 98], [cx + 6, T0 + 98], [cx + 7, T0 + 104], [cx + 1, T0 + 110], [cx - 5, T0 + 104])], ramp: R.gold, base: 3, cast: 1, hiT: 0.65 });
      p.set(cx + 1, T0 + 103, R.gold, 1); p.set(cx, T0 + 102, R.gold, 2); p.set(cx + 2, T0 + 102, R.gold, 2); p.set(cx + 1, T0 + 101, R.gold, 5);
      p.part({ s: [Rc(cx - 6, T0 + 96, 14, 2)], ramp: R.neutral, base: 1, cast: 0 });
      head(p, H);
      ear(p, H);
      nose(p, H, 'big');
      // мешки под глазами, морщины усталости
      for (let i = 0; i < 5; i++) p.set(cx - 6 + i, t + 21, sk, 2);
      p.set(cx - 13, t + 21, sk, 2); p.set(cx - 12, t + 21, sk, 2);
      p.set(cx - 6, t + 26, sk, 2); p.set(cx - 5, t + 27, sk, 2); p.set(cx - 5, t + 28, sk, 2); p.set(cx - 4, t + 29, sk, 2);
      for (let i = 0; i < 7; i++) p.set(cx - 10 + i, t + 8, sk, 2);
      for (let i = 0; i < 5; i++) p.set(cx - 9 + i, t + 10, sk, 2);
      // волосы: короткая стрижка соль-с-перцем
      p.part({ s: [P([cx - 12, t + 6], [cx - 8, t - 1], [cx + 4, t - 3], [cx + 15, t + 2], [cx + 18, t + 12], [cx + 16, t + 24], [cx + 10, t + 22], [cx + 8, t + 14], [cx - 2, t + 6])], ramp: hs, base: 2, cast: 1, hiT: 0.7 });
      for (let y = t - 2; y < t + 24; y++) for (let x = cx - 12; x < cx + 19; x++) if (p.ramp[y * BW + x] === hs && G.bayer(x, y) < 3 && ((x * 7 + y * 3) % 5 === 0 || x > cx + 6)) p.shift(x, y, 2, hs);
      p.stroke(C(cx - 8, t + 2, cx, t - 2, cx + 8, t - 1, 1), -1, hs);
      p.stroke(C(cx + 8, t + 6, cx + 13, t + 10, cx + 14, t + 20, 1), 2, hs);
      // усы с проседью
      const mx = cx - 14, my = t + 26;
      p.part({ s: [P([mx, my + 2], [mx + 3, my - 1], [mx + 10, my - 1], [mx + 12, my + 2], [mx + 11, my + 4], [mx + 6, my + 2], [mx + 1, my + 4])], ramp: hs, base: 2, cast: 1 });
      for (let i = 1; i < 11; i += 2) p.shift(mx + i, my + 1, 2, hs);
      // рука с блокнотом (в обычной позе у груди слева) — роняет при срыве
      const drop = bk >= 0 ? [0, 0, 6, 16, 30, 60, 99, 99][bk] : 0;
      if (drop < 60) {
        const ny = T0 + 80 + drop, nx = cx - 32 - Math.round(drop * 0.2);
        const tilt = Math.round(drop / 6);
        p.part({ s: [P([nx, ny + tilt], [nx + 14, ny], [nx + 15, ny + 18], [nx + 1, ny + 19 + tilt])], ramp: R.paper, base: 3, cast: 2 });
        p.part({ s: [P([nx, ny + tilt], [nx + 14, ny], [nx + 14, ny + 3], [nx, ny + 3 + tilt])], ramp: R.neutral, base: 2, cast: 0 });
        for (let k = 0; k < 4; k++) { p.set(nx + 3 + k * 3, ny + 1 + (tilt > 2 ? 1 : 0), R.neutral, 7); }
        for (let k = 0; k < 4; k++) for (let i = 2; i < 12; i++) if ((i + k) % 5) p.px(nx + i, ny + 7 + k * 3 + Math.round(tilt * (1 - i / 14)), PAL.ink);
        if (drop === 0 && st.fid >= 0) { // листает страницу
          const a = st.fa, k = st.fk;
          if (k > 0.5) {
            const px0 = nx + 14 - Math.round(Math.sin(a * Math.PI) * 6) - Math.round(a * 14) * (a > 0.5 ? 1 : 0) * 0;
            const ex = Math.round(nx + 14 - a * 14), lift = Math.round(Math.sin(a * Math.PI) * 7);
            p.part({ s: [P([nx + 1, ny + 3], [ex, ny + 3 - lift], [ex, ny + 18 - lift], [nx + 1, ny + 18])], ramp: R.paper, base: 4, cast: 1 });
            for (let q = 0; q < 3; q++) p.px(Math.round((nx + 2 + ex) / 2), ny + 8 + q * 3 - Math.round(lift / 2), PAL.ink);
          }
        }
        if (drop === 0) { // пальцы держат блокнот
          p.part({ s: [C(cx - 39, T0 + 74, cx - 35, T0 + 100, cx - 29, T0 + 104, 12, 10)], ramp: coat, base: 3, cast: 1 });
          p.part({ s: [P([nx + 2, ny + 14], [nx + 12, ny + 13], [nx + 13, ny + 20], [nx + 2, ny + 22])], ramp: sk, base: 3, cast: 1 });
          for (let k = 0; k < 3; k++) p.shift(nx + 4 + k * 3, ny + 16, -1, sk);
        }
      }
      // рука ко лбу
      if (bk >= 2) {
        const k = Math.min(1, (bk - 2) / 2);
        const hx = Math.round(G.lerp(cx - 29, cx - 10, k)), hy = Math.round(G.lerp(T0 + 64, t + 6, k));
        p.part({ s: [C(cx + 38, T0 + 66, cx + 29, T0 + 60, hx + 12, hy + 16, 15, 12)], ramp: coat, base: 3, cast: 2 });
        p.part({ s: [C(hx + 12, hy + 18, hx + 12, hy + 14, hx + 13, hy + 12, 8)], ramp: shirt, base: 3, cast: 1 });
        // ладонь: пальцы к лбу
        p.part({ s: [P([hx - 2, hy + 2], [hx + 8, hy - 1], [hx + 14, hy + 4], [hx + 13, hy + 12], [hx + 4, hy + 11], [hx - 3, hy + 6])], ramp: sk, base: 3, cast: 2 });
        for (let q = 0; q < 3; q++) p.stroke(['l', hx - 1 + q, hy + 3 + q * 2, hx + 7 + q, hy + 1 + q * 2], -1, sk);
        p.set(hx + 12, hy + 6, sk, 2); p.set(hx + 11, hy + 8, sk, 2);
      }
      // голова рисуется до руки? — рука поверх, поэтому голову рисуем раньше: см. ниже
    },
    face(st) {
      const bk = st.emo === 'breakdown' && st.bk < 0 ? 7 : st.bk;
      if (bk >= 0) {
        if (bk < 2) return { eyes: 'tiny', brows: [-2, -2], mouth: 'o', noBlink: true };
        if (bk < 5) return { eyes: 'blank', brows: [-3, 0], mouth: 'O', noBlink: true };
        return { eyes: 'blank', brows: [-3, 1], mouth: 'half', noBlink: false, talk: ['half', 'open'] };
      }
      const f = witnessFace(st);
      if (st.emo === 'normal') { f.eyes = 'half'; f.brows = [0, 1]; f.mouth = 'flat'; }
      if (st.emo === 'nervous') f.mouth = 'flat';
      return f;
    },
    post(c, st) {
      const cx = H0.cx, t = H0.top + (st.hy || 0);
      if (st.emo === 'nervous') sweat(c, cx - 15, t + 8);
      if (st.emo === 'shocked') sweat(c, cx - 16, t + 8, true);
      const bk = st.emo === 'breakdown' && st.bk < 0 ? 7 : st.bk;
      if (bk >= 1) { sweat(c, cx - 16, t + 10, true); }
      if (bk >= 5) sweat(c, cx + 2, t + 10);
    },
    iso: { skin: sk, top: coat, pants: R.neutral, shoes: R.wood[0], build: 'mid', seed: 0.6, long: true, tie: R.red[2], shirt: R.neutral[7],
      hairDraw(x, hx, hy) { isoHair(hs, 'short')(x, hx, hy); x.fillStyle = hs[2]; x.fillRect(hx + 1, hy + 6, 3, 1); } },
  });
})();

/* ====================== ГРАНТ ХОЛЛОУЭЙ ====================== */
(function () {
  const sk = R.skinL;
  const hs = [R.hairBlack[0], R.hairBlack[2], R.hairBlack[3], R.hairGrey[1], R.hairGrey[3]];
  const suit = [R.neutral[0], R.neutral[1], R.neutral[2], R.neutral[3], R.neutral[4], R.neutral[5]];
  const shirt = [R.neutral[6], R.neutral[7], R.neutral[8], R.neutral[9]];
  const H0 = { cx: 52, top: 18, ramp: sk, jaw: 2, chin: 2, sideX: 3 };
  reg('holloway', {
    name: 'Грант Холлоуэй', voice: 'low', emos: WIT_EMOS, seed: 17, fidEmos: ['normal', 'nervous', 'angry', 'shocked'], fidFace(st, f) { if (st.fk > 0.5) { f.eyes = 'down'; f.brows = [1, -1]; f.mouth = 'smirk'; } }, bkFrames: 8, bkDur: 1.2,
    feat: feat(H0, { iris: [R.blue[1], R.blue[3], R.blue[4]], brow: hs[1], brow2: hs[3], browThick: 2 }),
    shake: (k, t) => (k > 0.1 && k < 0.45 ? ((Math.floor(t * 30) & 1) ? 1 : -1) : 0),
    build(p, st) { buildHolloway(p, st); },
    face(st) {
      const bk = st.emo === 'breakdown' && st.bk < 0 ? 7 : st.bk;
      if (bk >= 0) {
        if (bk < 2) return { eyes: 'tiny', brows: [-2, -2], mouth: 'flat', noBlink: true };
        if (bk < 5) return { eyes: 'wide', brows: [-3, 0], mouth: 'gritO', noBlink: true };
        return { eyes: 'down', brows: [-3, 2], mouth: 'wail', noBlink: false, talk: ['open', 'wail'] };
      }
      const f = witnessFace(st);
      if (st.emo === 'normal') { f.eyes = 'half'; f.brows = [1, -2]; f.mouth = 'smirk'; f.talk = ['halfS', 'openS']; }
      return f;
    },
    post(c, st) {
      const cx = H0.cx, t = H0.top + (st.hy || 0), hx = st.hx || 0;
      if (st.emo === 'nervous') { sweat(c, cx - 15 + hx, t + 8); px(c, cx - 14 + hx, t + 22, R.blue[6]); }
      if (st.emo === 'shocked') sweat(c, cx - 16 + hx, t + 8, true);
      const bk = st.emo === 'breakdown' && st.bk < 0 ? 7 : st.bk;
      if (bk >= 3) { sweat(c, cx - 16 + hx, t + 6, true); sweat(c, cx + hx, t + 4, true); sweat(c, cx + 10 + hx, t + 8); }
    },
    iso: { skin: sk, top: suit, pants: R.neutral, shoes: R.neutral[0], build: 'mid', seed: 0.8, shirt: R.neutral[8], tie: R.gold[3],
      hairDraw: isoHair(hs, 'slick'),
      extra(x, f) { x.fillStyle = R.gold[4]; x.fillRect(f.fx - 1, f.armY + (f.sit ? 6 : 7), 2, 1); } },
  });
  function buildHolloway(p, st) {
    const e = st.emo, bk = st.emo === 'breakdown' && st.bk < 0 ? 7 : st.bk;
    const H = Object.assign({}, H0);
    // обрушение: опускается и наклоняется вперёд
    const sink = bk >= 0 ? [0, 0, 1, 3, 8, 14, 17, 18][bk] : 0;
    const lean = bk >= 0 ? [0, 0, 0, -1, -3, -5, -6, -6][bk] : 0;
    H.top += sink; H.cx += lean;
    st.hx = lean; st.hy = sink;
    const cx = H.cx, t = H.top;
    const T = H0.top + Math.round(sink * 0.7), bx = H0.cx + Math.round(lean * 0.5);
    neck(p, H, 13, 50 - Math.round(sink * 0.3));
    // рубашка + золотистый галстук
    p.part({ s: [P([bx - 12, T + 38], [bx + 16, T + 38], [bx + 14, BH], [bx - 14, BH])], ramp: shirt, base: 2, cast: 1 });
    const tieL = bk >= 4; // галстук сбился
    const tx = bx + (tieL ? 3 : 0);
    p.part({ s: [P([bx - 1, T + 46], [bx + 5, T + 46], [bx + 4, T + 50], [tx + 6, T + 80], [tx + 2, T + 86], [tx - 1, T + 80], [bx + 1, T + 50])], ramp: R.gold, base: 3, cast: 1 });
    for (let y = T + 52; y < T + 84; y += 3) p.set(bx + 2 + Math.round((tx - bx) * (y - T - 50) / 30), y, R.gold, 2);
    // дорогой тёмный костюм с тонкой полоской
    const L = [[bx - 14, T + 38], [bx - 32, T + 44], [bx - 40, T + 56], [bx - 43, BH], [bx - 10, BH], [bx - 6, T + 80], [bx - 10, T + 52]];
    const Rr = [[bx + 18, T + 38], [bx + 12, T + 52], [bx + 12, T + 82], [bx + 16, BH], [bx + 47, BH], [bx + 45, T + 58], [bx + 38, T + 44]];
    const m1 = torso(p, L, suit, 3, { shT: 0.25 });
    const m2 = torso(p, Rr, suit, 3, { lx: 0.9, shT: 0.55 });
    for (let y = T + 40; y < BH; y++) for (let x = 0; x < BW; x++) {
      const i = y * BW + x; if (!(m1[i] || m2[i]) || p.ramp[i] !== suit) continue;
      if ((x + 300) % 5 === 0 && (y & 1)) p.shift(x, y, 1, suit);
    }
    // лацканы (сатиновые, с бликом)
    p.part({ s: [P([bx - 14, T + 38], [bx - 6, T + 56], [bx - 6, T + 80], [bx - 14, T + 62], [bx - 26, T + 46])], ramp: suit, base: 3, cast: 2, hiT: 0.7 });
    p.part({ s: [P([bx + 18, T + 38], [bx + 12, T + 56], [bx + 12, T + 80], [bx + 22, T + 60], [bx + 30, T + 46])], ramp: suit, base: 2, cast: 2 });
    p.stroke(['l', bx - 22, T + 46, bx - 8, T + 66], 2, suit);
    // платок в нагрудном кармане
    if (bk < 5) {
      p.part({ s: [P([bx + 26, T + 62], [bx + 34, T + 64], [bx + 34, T + 66], [bx + 26, T + 64])], ramp: suit, base: 1, cast: 0 });
      p.part({ s: [P([bx + 27, T + 62], [bx + 29, T + 57], [bx + 30, T + 61], [bx + 32, T + 56], [bx + 33, T + 63])], ramp: R.red, base: 3, cast: 1 });
    }
    // воротник рубашки
    p.part({ s: [P([bx - 10, T + 37], [bx - 2, T + 46], [bx - 8, T + 51], [bx - 15, T + 42])], ramp: shirt, base: 3, cast: 1 });
    p.part({ s: [P([bx + 13, T + 37], [bx + 4, T + 46], [bx + 10, T + 51], [bx + 18, T + 41])], ramp: shirt, base: 2, cast: 1 });
    fold(p, C(bx - 37, T + 60, bx - 34, T + 84, bx - 37, BH, 1), -1, suit);
    fold(p, C(bx + 39, T + 62, bx + 40, T + 84, bx + 38, BH, 1), -1, suit);
    // рука: поправляет манжету у груди — золотые часы видны
    if (bk < 3) {
      const ay = T + 82 - Math.round((st.fk || 0) * 12);
      p.part({ s: [C(bx - 40, T + 62, bx - 37, ay + 18, bx - 16, ay + 10, 15, 12)], ramp: suit, base: 3, cast: 2 });
      p.part({ s: [P([bx - 18, ay + 2], [bx - 12, ay + 1], [bx - 11, ay + 15], [bx - 17, ay + 16])], ramp: shirt, base: 3, cast: 1 }); // манжета
      p.part({ s: [P([bx - 12, ay + 2], [bx - 2, ay], [bx + 4, ay + 6], [bx + 2, ay + 13], [bx - 11, ay + 14])], ramp: sk, base: 3, cast: 1 });
      for (let k = 0; k < 3; k++) p.shift(bx - 6 + k * 3, ay + 8 + k, -1, sk);
      // часы
      const broken = bk >= 1;
      const wx = bx - 17, wy = ay + 4;
      if (!broken) {
        p.part({ s: [Rc(wx - 2, wy - 2, 4, 14)], ramp: R.gold, base: 3, cast: 1 });
        for (let y = wy - 2; y < wy + 12; y += 2) p.shift(wx - 1, y, 1, R.gold);
        p.part({ s: [E(wx - 1, wy + 5, 3, 3)], ramp: R.gold, base: 4, cast: 1 });
        p.px(wx - 1, wy + 5, R.neutral[8]); p.px(wx - 2, wy + 4, PAL.white); p.px(wx - 1, wy + 4, PAL.ink);
      } else {
        // ремешок лопнул: часы падают
        const fall = [0, 6, 18, 40][Math.min(bk, 3)];
        p.part({ s: [C(wx - 1, wy - 2, wx - 4, wy + 2, wx - 6, wy + 6, 3, 2)], ramp: R.gold, base: 3, cast: 1 });
        if (fall < 30) {
          p.part({ s: [C(wx + 2, wy + 6 + fall, wx + 0, wy + 10 + fall, wx - 3, wy + 14 + fall, 3, 2)], ramp: R.gold, base: 3, cast: 1 });
          p.part({ s: [E(wx + 2, wy + 6 + fall, 3, 3)], ramp: R.gold, base: 4, cast: 1 });
          p.px(wx + 2, wy + 6 + fall, R.neutral[8]); p.px(wx + 1, wy + 5 + fall, PAL.white);
          for (let q = 0; q < 3; q++) p.px(wx + 6 + q, wy + 2 + q * 3 + fall, R.gold[5]); // искры
        }
      }
    }
    // голова
    head(p, H);
    ear(p, H);
    nose(p, H, 'sharp');
    p.set(cx - 7, t + 27, sk, 2); p.set(cx - 6, t + 28, sk, 2); p.set(cx - 6, t + 29, sk, 2);
    // ямочка на подбородке
    p.set(cx - 7, t + 35, sk, 2);
    // загар/блик на скуле уже есть. Волосы:
    const messy = bk >= 2;
    if (!messy) {
      // зачёс назад: гладкая масса и длинные пряди к затылку
      p.part({ s: [P([cx - 13, t + 8], [cx - 10, t + 0], [cx + 2, t - 4], [cx + 14, t - 1], [cx + 19, t + 8], [cx + 18, t + 22], [cx + 11, t + 24], [cx + 8, t + 14], [cx - 2, t + 8])], ramp: hs, base: 2, cast: 1, hiT: 0.72 });
      // объёмный зачёс: передний «вал» над лбом, блестящие полосы геля к затылку
      p.part({ s: [C(cx - 14, t + 6, cx - 12, t - 3, cx - 2, t - 4, 5, 4)], ramp: hs, base: 2, cast: 1, hiT: 0.6 });
      p.stroke(C(cx - 12, t + 1, cx - 4, t - 4, cx + 8, t - 2, 1), 2, hs);
      p.stroke(C(cx - 6, t + 2, cx + 4, t - 1, cx + 16, t + 6, 1), 1, hs);
      p.stroke(C(cx - 4, t + 5, cx + 6, t + 3, cx + 17, t + 12, 1), -1, hs);
      p.stroke(C(cx - 9, t + 0, cx + 2, t - 3, cx + 15, t + 2, 1), -1, hs);
      p.stroke(C(cx + 2, t + 7, cx + 10, t + 7, cx + 16, t + 16, 1), 1, hs);
      p.stroke(C(cx + 10, t + 4, cx + 15, t + 10, cx + 16, t + 18, 1), 2, hs); // седина на висках
      p.stroke(C(cx + 9, t + 6, cx + 13, t + 12, cx + 12, t + 18, 1), 2, hs);
    } else {
      const k = Math.min(1, (bk - 1) / 4);
      p.part({ s: [P([cx - 13, t + 8], [cx - 10, t + 0], [cx + 2, t - 4], [cx + 14, t - 1], [cx + 19, t + 8], [cx + 18, t + 22], [cx + 11, t + 24], [cx + 8, t + 14], [cx - 2, t + 8])], ramp: hs, base: 2, cast: 1 });
      const fl = [
        C(cx - 6, t + 1, cx - 12, t + 6, cx - 13, t + 10 + k * 5, 3, 1),
        C(cx - 2, t + 0, cx - 6, t + 8, cx - 5, t + 12 + k * 6, 3, 1),
        C(cx + 2, t - 1, cx + 0, t + 6, cx + 2, t + 11 + k * 4, 3, 1),
        C(cx + 6, t - 3, cx + 10, t - 9, cx + 15, t - 8, 2, 1),
        C(cx + 12, t + 0, cx + 20, t - 2, cx + 23, t + 3, 2, 1),
        C(cx - 8, t - 1, cx - 14, t - 4, cx - 17, t - 1, 2, 1),
      ];
      for (const s of fl) p.part({ s: [s], ramp: hs, base: 3, cast: 1 });
      p.stroke(C(cx + 10, t + 4, cx + 15, t + 10, cx + 16, t + 18, 1), 2, hs);
    }
    // перила свидетельской трибуны и руки, вцепившиеся в них
    if (bk >= 3) {
      const ry = BH - 12;
      p.part({ s: [Rc(0, ry, BW, 12)], ramp: R.wood, base: 3, cast: 2, hiT: 0.9, shT: 0.2,
        shade(x, y) { if (y === ry) return 5; if (y === ry + 1) return 4; if (y > ry + 8) return 1; return 3; } });
      for (let x = 0; x < BW; x += 7) p.shift(x, ry + 5, -1, R.wood);
      // руки сжимают перила
      const grip = (x0, side) => {
        p.part({ s: [C(x0 + side * 22, BH - 30, x0 + side * 10, BH - 22, x0, ry - 2, 13, 11)], ramp: suit, base: 3, cast: 1 });
        p.part({ s: [P([x0 - 7, ry - 4], [x0 + 6, ry - 5], [x0 + 8, ry + 4], [x0 + 5, ry + 7], [x0 - 6, ry + 7], [x0 - 8, ry + 2])], ramp: sk, base: 3, cast: 1 });
        for (let q = 0; q < 4; q++) { p.set(x0 - 6 + q * 3, ry + 4, sk, 1); p.set(x0 - 5 + q * 3, ry + 6, sk, 2); p.set(x0 - 6 + q * 3, ry + 1, sk, 4); }
        p.set(x0 - 2, ry - 2, sk, 1); p.set(x0 + 2, ry - 3, sk, 1); // костяшки
      };
      grip(bx - 26, -1);
      grip(bx + 29, 1);
    }
  }
})();


})();
