/* =====================================================================
   ISO — маленькие изометрические персонажи (контракт v3, §3).
   Переопределяет G.Cast.defs[id].iso для всех персонажей.
   Фигурка ~14×28 стоя, сидя ~16 px верха. Лицо: кожа 3 тона,
   глаза — по одному тёмному пикселю, рот только при речи/реакции.
   Кадры: G.cacheCanvas('iso/<id>/<pose>/<dir>/<state>/<frame>').
   Спрайты нарисованы смотрящими влево; 'r' — зеркальная копия.
   ===================================================================== */
(function () {
'use strict';
const G = window.G;
const R = G.RAMP, P = G.PAL;
const W = 24, H = 40, AX = 12, AY = 37; // буфер и якорь (точка ступней)

/* ---------------- пиксельный буфер ---------------- */
class PB {
  constructor(w, h) { this.w = w; this.h = h; this.d = new Array(w * h).fill(null); }
  set(x, y, c) { x |= 0; y |= 0; if (c && x >= 0 && y >= 0 && x < this.w && y < this.h) this.d[y * this.w + x] = c; }
  get(x, y) { return (x >= 0 && y >= 0 && x < this.w && y < this.h) ? this.d[y * this.w + x] : null; }
  rect(x, y, w, h, c) { for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) this.set(x + i, y + j, c); }
  hl(x0, x1, y, c) { for (let x = x0; x <= x1; x++) this.set(x, y, c); }
  vl(x, y0, y1, c) { for (let y = y0; y <= y1; y++) this.set(x, y, c); }
  line(x0, y0, x1, y1, c, fn) {
    const dx = Math.abs(x1 - x0), dy = -Math.abs(y1 - y0), sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1;
    let e = dx + dy;
    for (;;) {
      if (fn) fn(x0, y0); else this.set(x0, y0, c);
      if (x0 === x1 && y0 === y1) break;
      const e2 = 2 * e;
      if (e2 >= dy) { e += dy; x0 += sx; }
      if (e2 <= dx) { e += dx; y0 += sy; }
    }
  }
  outline(col) {
    const add = [];
    for (let y = 0; y < this.h; y++) for (let x = 0; x < this.w; x++) {
      if (this.get(x, y)) continue;
      if (this.get(x - 1, y) || this.get(x + 1, y) || this.get(x, y - 1) || this.get(x, y + 1)) add.push(x, y);
    }
    for (let i = 0; i < add.length; i += 2) this.set(add[i], add[i + 1], col);
  }
  render(c, flip) {
    for (let y = 0; y < this.h; y++) for (let x = 0; x < this.w; x++) {
      const v = this.d[y * this.w + x]; if (!v) continue;
      c.fillStyle = v; c.fillRect(flip ? this.w - 1 - x : x, y, 1, 1);
    }
  }
}
function hashStr(s) { let h = 2166136261; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }

/* ткань: [разделитель, тень, основа, блик] из рампы */
const T = (ramp, b) => [ramp[Math.max(0, b - 2)], ramp[Math.max(0, b - 1)], ramp[b], ramp[Math.min(ramp.length - 1, b + 1)]];
const EYE = R.neutral[0], MOUTH = R.red[0];

/* ---------------- причёски: карты 9×11 (x −1..7, y −3..7), лицом влево ----------------
   a — тень, b — основа, c — блик, d — светлый блик, k — тёмная прядь. */
const HAIR = {
  short: [
    '.........',
    '.........',
    '..bcbbb..',
    '.bbbbbba.',
    '.b...bba.',
    '......ba.',
    '.......a.',
  ],
  side: [
    '.........',
    '.........',
    '..bbcbb..',
    '.bbcbbba.',
    '.bbb.bba.',
    '......ba.',
    '.......a.',
  ],
  messy: [
    '.........',
    '..b..c...',
    '.bbcbbba.',
    '.bbbbbbaa',
    '.bb.b.ba.',
    '......ba.',
    '.......a.',
  ],
  slick: [
    '.........',
    '.........',
    '..bccbb..',
    '.bbbbbbaa',
    '.b...bba.',
    '......ba.',
    '.......a.',
  ],
  buzz: [
    '.........',
    '.........',
    '..bbcbb..',
    '.b....ba.',
    '.......a.',
  ],
  bald: [
    '.........',
    '.........',
    '.........',
    '.........',
    '......ba.',
    '......ba.',
    '......aa.',
  ],
  white: [ // судья: седая шевелюра с объёмом за ушами
    '.........',
    '..bbcb...',
    '.bcbbbba.',
    'bbbbbbbaa',
    'b.....baa',
    '......baa',
    '.......a.',
  ],
  curly: [
    '.........',
    '..b.b.b..',
    '.bbcbbbb.',
    'bbcbbbbba',
    'bb...bbaa',
    '.....bbaa',
    '......aa.',
  ],
  afro: [
    '..bbbbb..',
    '.bbcbbbba',
    'bbcbbbbba',
    'bbbbbbbba',
    'bb....bba',
    'b.....bba',
    '......aa.',
  ],
  bob: [
    '.........',
    '.........',
    '..bccbb..',
    '.bbbbbbba',
    'bbbbbbbba',
    'b.....bba',
    'b.....bba',
    'b.....bba',
    'a.....aaa',
  ],
  long: [
    '.........',
    '.........',
    '..bcbbb..',
    '.bcbbbbba',
    'bbb...bba',
    'b.....bba',
    'b.....bba',
    'b.....bba',
    'b.....bba',
    '......bba',
    '......aa.',
  ],
  bun: [
    '......bb.',
    '.....bcba',
    '..bcbbbaa',
    '.bbbbbba.',
    '.b...bba.',
    '......ba.',
    '.......a.',
  ],
  pony: [
    '.........',
    '.........',
    '..bcbbb..',
    '.bbbbbbab',
    '.b...bbab',
    '......bab',
    '.......ab',
    '........a',
  ],
};
/* лица: глаза по позициям x (лок.), строка 3 */
/* ---------------- описания персонажей ---------------- */
const SK = { L: R.skinL, M: R.skinM, D: R.skinD };
const HR = { brown: R.hairBrown, black: R.hairBlack, blond: R.hairBlond, red: R.hairRed, grey: R.hairGrey };
const TAN = [R.wood[2], R.wood[4], R.wood[5], R.wood[6]];
const DEFS = {
  player:     { skin: 'L', hair: 'brown', hs: 'side', top: T(R.blue, 3), pants: T(R.blue, 2), shirt: R.neutral[9], tie: R.red[3], pin: R.gold[4], fid: 'tie' },
  judge:      { skin: 'L', hair: 'grey', hb: 3, hs: 'white', top: T(R.neutral, 2), pants: T(R.neutral, 2), robe: 1, shirt: R.neutral[9], fid: 'papers' },
  prosecutor: { skin: 'L', hair: 'black', hs: 'bob', top: T(R.neutral, 5), skirt: T(R.neutral, 4), shirt: R.neutral[9], build: 'thin', fid: 'papers', shoes: R.neutral[0] },
  clerk:      { skin: 'L', hair: 'black', hs: 'bun', top: T(R.teal, 3), skirt: T(R.neutral, 3), shirt: R.neutral[8], glasses: 'gold', build: 'thin', fid: 'write' },
  bailiff:    { skin: 'D', hair: 'black', hs: 'buzz', top: TAN, pants: T(R.green, 2), star: 1, belt: R.neutral[1], build: 'big', fid: 'cross', pocket: 1 },
  reporter:   { skin: 'M', hair: 'brown', hs: 'bun', top: T(R.carpet, 3), skirt: T(R.neutral, 2), shirt: R.neutral[8], glasses: 'dark', build: 'thin', fid: 'type' },
  juror1:     { skin: 'L', hair: 'blond', hb: 3, hs: 'long', top: T(R.red, 3), skirt: T(R.carpet, 2), build: 'thin', fid: 'look' },
  juror2:     { skin: 'D', hair: 'black', hs: 'short', top: T(R.green, 3), pants: T(R.stone, 2), beard: 1, build: 'big', fid: 'scratch' },
  juror3:     { skin: 'M', hair: 'black', hs: 'pony', top: T(R.purple, 3), skirt: T(R.neutral, 3), shirt: R.neutral[8], build: 'thin', fid: 'write' },
  juror4:     { skin: 'L', hair: 'grey', hs: 'bald', top: T(R.wood, 3), pants: T(R.wood, 2), shirt: R.neutral[8], tie: R.blue[3], stache: 'grey', fid: 'look' },
  juror5:     { skin: 'L', hair: 'red', hs: 'curly', top: T(R.blue, 4), pants: T(R.carpet, 2), stripe: R.blue[6], fid: 'scratch' },
  juror6:     { skin: 'M', hair: 'brown', hs: 'short', top: T(R.gold, 3), pants: T(R.carpet, 2), shirt: R.neutral[8], glasses: 'dark', build: 'big', fid: 'glasses' },
  foreperson: { skin: 'L', hair: 'grey', hb: 3, hs: 'curly', top: T(R.stone, 3), skirt: T(R.wood, 3), shirt: R.blue[5], pearls: 1, fid: 'write' },
  spectator1: { skin: 'L', hair: 'brown', hs: 'short', top: T(R.stone, 2), pants: T(R.neutral, 3), shirt: R.neutral[8], tie: R.red[2], hat: 'fedora', fid: 'write' },
  spectator2: { skin: 'M', hair: 'black', hs: 'long', top: T(R.neutral, 3), pants: T(R.neutral, 2), shirt: R.red[3], hat: 'beret', fid: 'sketch' },
  spectator3: { skin: 'L', hair: 'grey', hs: 'bald', top: T(R.wood, 2), pants: T(R.wood, 2), shirt: R.neutral[8], tie: R.green[3], glasses: 'dark', build: 'big', fid: 'glasses' },
  spectator4: { skin: 'L', hair: 'grey', hb: 3, hs: 'curly', top: T(R.purple, 4), skirt: T(R.purple, 2), shirt: R.neutral[8], glasses: 'gold', pearls: 1, build: 'thin', fid: 'glasses' },
  spectator5: { skin: 'D', hair: 'black', hs: 'afro', top: T(R.red, 3), pants: T(R.carpet, 3), hood: 1, fid: 'scratch' },
  spectator6: { skin: 'L', hair: 'blond', hb: 3, hs: 'pony', top: T(R.teal, 4), pants: T(R.carpet, 3), glasses: 'dark', build: 'thin', fid: 'write' },
  spectator7: { skin: 'L', hair: 'black', hs: 'bob', top: T(R.neutral, 2), skirt: T(R.neutral, 2), shirt: R.neutral[1], hat: 'veil', build: 'thin', fid: 'hanky' },
  spectator8: { skin: 'M', hair: 'black', hs: 'short', top: T(R.neutral, 2), pants: T(R.neutral, 2), shirt: R.neutral[8], tie: R.neutral[0], fid: 'look' },
  spectator9: { skin: 'L', hair: 'brown', hs: 'short', top: T(R.green, 2), pants: T(R.blue, 3), shirt: R.neutral[7], hat: 'cap', capc: R.red, beard: 1, build: 'big', fid: 'cap' },
  spectator10:{ skin: 'D', hair: 'black', hs: 'long', top: T(R.gold, 4), skirt: T(R.carpet, 3), build: 'thin', fid: 'look', earring: 1 },
  spectator11:{ skin: 'L', hair: 'red', hs: 'side', top: T(R.blue, 2), pants: T(R.blue, 2), shirt: R.neutral[8], tie: R.gold[3], build: 'thin', fid: 'tie' },
  spectator12:{ skin: 'M', hair: 'grey', hs: 'short', top: T(R.stone, 3), pants: T(R.stone, 2), shirt: R.neutral[7], hat: 'flat', beard: 1, fid: 'look' },
  lomax:      { skin: 'L', hair: 'brown', hs: 'messy', top: T(R.stone, 2), pants: T(R.wood, 2), shirt: R.blue[4], cardigan: 1, glasses: 'gold', build: 'thin', fid: 'glasses' },
  hollis:     { skin: 'L', hair: 'grey', hs: 'short', top: T(R.blue, 5), pants: T(R.blue, 1), tie: R.blue[1], hat: 'cap', capc: R.blue, stache: 'grey', badgeS: 1, build: 'big', fid: 'cap' },
  whitfield:  { skin: 'L', hair: 'red', hs: 'bun', top: T(R.green, 3), skirt: T(R.green, 3), shirt: R.paper[3], build: 'thin', fid: 'hanky' },
  crane:      { skin: 'L', hair: 'grey', hs: 'bald', top: T(R.neutral, 7), pants: T(R.neutral, 2), susp: R.red[3], build: 'big', fid: 'cross' },
  park:       { skin: 'L', hair: 'black', hs: 'bob', streak: R.teal[5], top: T(R.neutral, 5), pants: T(R.blue, 3), hood: 1, fid: 'look', shoes: R.neutral[8] },
  bell:       { skin: 'L', hair: 'plat', hs: 'bob', top: T(R.neutral, 2), pants: T(R.neutral, 2), glasses: 'red', earring: 1, build: 'thin', fid: 'glasses' },
  doyle:      { skin: 'M', hair: 'black', hs: 'curly', top: T(R.teal, 3), pants: T(R.neutral, 2), shirt: R.neutral[8], fid: 'scratch' },
  morales:    { skin: 'M', hair: 'salt', hs: 'short', top: T(R.stone, 3), pants: T(R.neutral, 2), shirt: R.neutral[7], tie: R.red[2], coat: 1, stache: 'black', fid: 'cross' },
  holloway:   { skin: 'L', hair: 'salt', hs: 'slick', top: T(R.neutral, 2), pants: T(R.neutral, 1), shirt: R.neutral[8], tie: R.gold[3], watch: 1, fid: 'watch' },
};
const PLAT = [R.hairGrey[1], R.stone[3], R.hairBlond[4], R.hairGrey[4], R.neutral[9]];
const SALT = [R.hairBlack[0], R.hairBlack[1], R.hairBlack[3], R.hairGrey[2], R.hairGrey[3]];
function hairRamp(d) {
  if (d.hair === 'plat') return PLAT;
  if (d.hair === 'salt') return SALT;
  const r = HR[d.hair];
  if (d.hb === 3) return [r[0], r[1], r[3], r[4], r[4]]; // светлые волосы: основа на ступень выше
  return r;
}
const BUILD = { thin: 8, mid: 9, big: 11 };

/* ---------------- голова: рисуется в собственный буфер 11×12 ---------------- */
/* hb: {eyes:'q'|'b'|'p'|'down'|'happy'|'wide', mouth:0|1|2|3, red} ; голова 7×7 в лок. (2..8, 3..9) */
function paintHead(d, st) {
  const pb = new PB(11, 13);
  const OX = 2, OY = 3; // лок. (0,0) головы
  const sk0 = SK[d.skin];
  const sk = st.red ? [sk0[0], R.red[2], R.red[3], R.red[4], R.red[5]] : sk0;
  const s = (x, y, c) => pb.set(OX + x, OY + y, c);
  // маска головы
  for (let y = 0; y < 7; y++) {
    const a = (y === 0 || y === 6) ? 1 : 0, b = y === 6 ? 5 : (y === 0 ? 5 : 6);
    for (let x = a; x <= b; x++) {
      let c = sk[3];
      if (x >= 5) c = sk[2];
      if (y === 6 && x >= 3) c = sk[2];
      s(x, y, c);
    }
  }
  s(1, 1, sk[4]); s(0, 4, sk[4]); // блик на лбу/скуле
  s(5, 3, sk[1]); // ухо (тень)
  s(5, 4, sk[2]);
  const hs = d.hs, H = hairRamp(d);
  // глаза
  const ey = (st.eyes === 'down') ? 4 : 3;
  const eyeC = d.glasses === 'red' ? EYE : EYE;
  if (st.eyes === 'b') { s(1, 3, sk[2]); s(4, 3, sk[2]); }
  else if (st.eyes === 'happy') { s(1, 3, sk[1]); s(4, 3, sk[1]); }
  else if (st.eyes === 'p') { s(0, 3, eyeC); s(-1, 4, sk[3]); }
  else if (st.eyes === 'wide') { s(1, 3, eyeC); s(4, 3, eyeC); s(1, 2, P.white); s(4, 2, P.white); }
  else { s(1, ey, eyeC); s(4, ey, eyeC); }
  // рот
  const mx = st.eyes === 'p' ? 1 : 2, my = d.stache ? 6 : 5;
  if (st.mouth === 1) s(mx, my, MOUTH);
  else if (st.mouth === 2) { s(mx, my, MOUTH); s(mx + 1, my, MOUTH); }
  else if (st.mouth === 3) { s(mx, my, MOUTH); if (my === 5) s(mx, 6, R.red[1]); }
  // борода / усы
  if (d.beard) {
    const B = H;
    for (let x = 0; x <= 5; x++) s(x, 5 + (x === 0 ? 0 : 0), x >= 4 ? B[1] : B[2]);
    for (let x = 1; x <= 5; x++) s(x, 6, x >= 4 ? B[1] : B[2]);
    s(2, 7, B[1]); s(3, 7, B[1]);
    s(5, 4, B[1]); s(0, 4, sk[3]);
    if (st.mouth) { s(mx, 5, MOUTH); if (st.mouth === 2) s(mx + 1, 5, MOUTH); }
    else s(2, 5, B[3]);
  }
  if (d.stache) {
    const sc = d.stache === 'grey' ? R.hairGrey : R.hairBlack;
    s(0, 5, sc[3]); s(1, 5, sc[2]); s(2, 5, sc[2]); s(3, 5, sc[1]); s(0, 4, sk[3]);
  }
  // волосы
  const map = HAIR[hs];
  if (map) {
    for (let j = 0; j < map.length; j++) {
      const row = map[j];
      for (let i = 0; i < row.length; i++) {
        const ch = row[i]; if (ch === '.') continue;
        const col = ch === 'a' ? H[1] : ch === 'b' ? H[2] : ch === 'c' ? H[3] : ch === 'd' ? H[4] : H[0];
        s(i - 1, j - 3 + 0, col);
      }
    }
  }
  if (hs === 'bald') { s(2, 0, sk[4]); s(1, 0, sk[3]); }
  if (d.streak) { s(1, 0, d.streak); s(0, 1, d.streak); s(-1, 2, d.streak); s(-1, 3, d.streak); }
  // очки
  if (d.glasses) {
    const gc = d.glasses === 'red' ? R.red[3] : d.glasses === 'gold' ? R.gold[3] : R.neutral[6];
    if (st.eyes === 'p') { s(-1, 3, gc); s(1, 3, gc); }
    else if (d.glasses === 'red') { s(0, ey, gc); s(2, ey, gc); s(3, ey, gc); s(5, ey, gc); }
    else { s(2, ey, gc); s(3, ey, gc); s(5, ey, gc); }
    if (st.glint) s(st.eyes === 'p' ? 0 : 1, ey - 1, P.white);
  }
  if (d.earring && hs !== 'long') s(5, 6, R.gold[4]);
  else if (d.earring) s(4, 6, R.gold[4]);
  // головные уборы
  if (d.hat === 'cap') {
    const C = d.capc;
    for (let x = 0; x <= 6; x++) s(x, -1, C[2]);
    for (let x = 0; x <= 6; x++) s(x, 0, x >= 5 ? C[1] : C[2]);
    for (let x = 1; x <= 5; x++) s(x, -2, C[2]);
    s(1, -2, C[3]); s(2, -2, C[3]);
    s(-2, 1, C[1]); s(-1, 1, C[1]); s(0, 1, C[1]); s(1, 1, C[1]); // козырёк влево
    if (d === DEFS.hollis) s(3, -1, R.gold[4]); // кокарда
  } else if (d.hat === 'fedora') {
    const C = R.wood;
    for (let x = -1; x <= 7; x++) s(x, 0, C[2]);
    s(-1, 0, C[3]); s(7, 0, C[1]);
    for (let x = 0; x <= 6; x++) { s(x, -1, x >= 5 ? C[2] : C[3]); s(x, -2, C[3]); }
    s(2, -2, C[4]); for (let x = 0; x <= 6; x++) s(x, -1, R.neutral[1]);
    s(1, -3, C[3]); s(2, -3, C[4]); s(3, -3, C[3]); s(4, -3, C[3]); s(5, -3, C[2]);
  } else if (d.hat === 'beret') {
    const C = R.red;
    for (let x = 0; x <= 7; x++) s(x, -1, x >= 6 ? C[2] : C[3]);
    for (let x = 1; x <= 6; x++) s(x, -2, C[3]);
    s(2, -2, C[4]); s(4, -3, C[2]);
    s(0, 0, C[2]); s(7, 0, C[1]);
  } else if (d.hat === 'flat') {
    const C = R.neutral;
    for (let x = 0; x <= 6; x++) { s(x, -1, x >= 5 ? C[3] : C[4]); s(x, 0, x >= 5 ? C[2] : C[3]); }
    s(-1, 0, C[3]); s(1, -1, C[5]); s(2, -1, C[5]);
  } else if (d.hat === 'veil') {
    const C = R.neutral;
    for (let x = 0; x <= 6; x++) s(x, -1, C[1]);
    s(1, -1, C[3]); s(2, -1, C[2]); s(0, -2, C[1]); s(1, -2, C[1]); s(2, -2, C[1]);
    // вуаль: редкий дизер на лбу
    s(0, 1, C[1]); s(2, 1, C[1]); s(4, 1, C[1]); s(1, 2, C[2]); s(3, 2, C[2]);
  }
  return pb;
}

/* ---------------- тело ---------------- */
/* st: {sit, bob, jump, lean, hx, hy, head:{...}, flipHead, arms:{f:[[x,y],...], b:[[x,y],...]}, prop, red} */
function paint(id, st) {
  const d = DEFS[id];
  const pb = new PB(W, H);
  const sit = st.sit;
  const J = st.jump || 0;
  const ub = (sit ? 8 : 0) + (st.bob || 0) + J;
  const bw = BUILD[d.build || 'mid'];
  const x0 = bw > 10 ? 6 : 7, x1 = x0 + bw - 1;
  const cx = x0 + Math.floor((bw - 1) / 2);
  const ty = 13 + ub;
  const tb = (sit ? 28 : 22) + J; // низ корпуса
  const top = d.top, sk = SK[d.skin];
  const pants = d.pants || d.skirt || T(R.neutral, 2);
  const shoe = d.shoes || R.neutral[1];
  const lean = st.lean || 0;
  const L = { x0, x1, ty, tb, cx, sit };
  // ----- низ -----
  if (!sit) {
    const yb = 34 + J;
    if (d.robe) {
      for (let y = 23 + J; y <= 33 + J; y++) {
        const k = y - 23 - J, a = x0 - (k > 6 ? 1 : 0), b = x1 + (k > 3 ? 1 : 0);
        for (let x = a; x <= b; x++) pb.set(x, y, x === a ? top[3] : x >= b - 1 ? top[1] : top[2]);
        pb.set(cx + 1, y, top[1]);
      }
      pb.hl(x0, x0 + 2, yb, shoe); pb.hl(cx + 2, cx + 4, yb, shoe);
    } else if (d.skirt) {
      const S = d.skirt;
      for (let y = 23 + J; y <= 28 + J; y++) {
        const k = y - 23 - J, a = x0 + 1 - (k > 2 ? 1 : 0), b = x1 - 1 + (k > 2 ? 1 : 0);
        for (let x = a; x <= b; x++) pb.set(x, y, x === a ? S[3] : x >= b ? S[1] : S[2]);
      }
      pb.hl(x0 + 1, x1 - 1, 28 + J, S[1]);
      for (let y = 29 + J; y <= 32 + J; y++) { pb.hl(cx - 2, cx - 1, y, sk[2]); pb.hl(cx + 1, cx + 2, y, sk[1]); pb.set(cx - 2, y, sk[3]); }
      pb.hl(cx - 3, cx - 1, 33 + J, shoe); pb.hl(cx - 3, cx - 1, yb, shoe);
      pb.hl(cx + 1, cx + 3, 33 + J, shoe); pb.hl(cx + 1, cx + 3, yb, shoe);
      pb.set(cx - 3, 33 + J, R.neutral[4]);
    } else {
      const p = pants;
      for (let y = 23 + J; y <= 32 + J; y++) {
        pb.set(cx - 3, y, p[3]); pb.hl(cx - 2, cx - 1, y, p[2]);
        pb.set(cx, y, y < 25 + J ? p[2] : p[0]);
        pb.hl(cx + 1, cx + 3, y, p[1]);
      }
      pb.hl(cx - 4, cx - 1, 33 + J, shoe); pb.hl(cx - 4, cx - 1, yb, shoe);
      pb.hl(cx + 1, cx + 3, 33 + J, shoe); pb.hl(cx + 1, cx + 4, yb, shoe);
      pb.set(cx - 3, 33 + J, d.shoes === R.neutral[8] ? R.neutral[9] : R.neutral[4]);
      if (d.coat) { // длинное пальто до колен
        for (let y = 23 + J; y <= 27 + J; y++) { const a = x0 - (y > 25 + J ? 1 : 0); for (let x = a; x <= x1; x++) pb.set(x, y, x === a ? top[3] : x >= x1 - 1 ? top[1] : top[2]); pb.set(cx, y, top[0]); }
      }
    }
  } else {
    // сидя: бёдра вперёд-влево, голени вниз
    const p = d.skirt || pants;
    const ly = tb + 1;
    for (let x = x0 - 3; x <= x1 - 1; x++) { pb.set(x, ly, p[3]); pb.set(x, ly + 1, p[2]); pb.set(x, ly + 2, p[1]); }
    const shin = d.skirt ? sk : null;
    for (let y = ly + 3; y <= ly + 5; y++) { pb.set(x0 - 3, y, shin ? shin[2] : p[2]); pb.set(x0 - 2, y, shin ? shin[1] : p[1]); }
    pb.hl(x0 - 5, x0 - 2, ly + 6, shoe); pb.set(x0 - 5, ly + 6, R.neutral[3]);
  }
  // ----- задняя рука (за корпусом) -----
  const armF = st.arms && st.arms.f, armB = st.arms && st.arms.b;
  const shF = [x0 - 2 + lean, ty + 1], shB = [x1 + 2 + lean, ty + 1];
  function arm(sh, path, cA, cB, front) {
    let px = sh[0], py = sh[1];
    const pts = [[px, py]].concat(path);
    for (let i = 0; i + 1 < pts.length; i++) {
      const a = pts[i], b = pts[i + 1];
      pb.line(a[0], a[1], b[0], b[1], null, (x, y) => { pb.set(x + (front ? 1 : -1), y, cB); pb.set(x, y, cA); });
    }
    const h = pts[pts.length - 1];
    // кисть 2×2
    const hx = h[0] + (front ? 0 : -1), hy = h[1];
    pb.set(hx, hy, sk[3]); pb.set(hx + 1, hy, sk[3]); pb.set(hx, hy + 1, sk[2]); pb.set(hx + 1, hy + 1, sk[2]);
    if (st.red) { pb.set(hx, hy, R.red[4]); pb.set(hx + 1, hy, R.red[4]); }
  }
  const defF = [[x0 - 2, tb - 1]], defB = [[x1 + 2, tb - 1]];
  const backBehind = !armB || st.backBehind !== false;
  if (backBehind) arm(shB, armB || defB, top[1], top[0], false);
  // ----- корпус -----
  for (let y = ty; y <= tb; y++) {
    const lx = (y < ty + 3 ? lean : 0);
    const a = x0 + lx + (y === ty ? 1 : 0), b = x1 + lx - (y === ty ? 1 : 0);
    for (let x = a; x <= b; x++) {
      let c = top[2];
      if (x === a) c = top[3];
      if (x >= b) c = top[1];
      if (y === tb) c = top[1];
      pb.set(x, y, c);
    }
  }
  const sx = cx + lean;
  if (d.robe) { pb.hl(sx - 1, sx + 1, ty, d.shirt); pb.set(sx, ty + 1, d.shirt); pb.vl(sx + 1, ty + 2, tb, top[1]); }
  else if (d.cardigan) {
    pb.vl(sx, ty, tb - 1, d.shirt); pb.vl(sx + 1, ty, tb - 1, R.blue[3]); pb.set(sx - 1, ty, d.shirt);
    pb.set(sx - 1, ty + 3, R.wood[5]); pb.set(sx - 1, ty + 6, R.wood[5]);
  } else if (d.hood) {
    pb.hl(x1 - 2 + lean, x1 + lean, ty - 1, top[1]); pb.set(x1 - 3 + lean, ty - 1, top[2]);
    pb.set(sx - 1, ty + 1, R.neutral[9]); pb.set(sx + 1, ty + 1, R.neutral[9]); pb.set(sx - 1, ty + 2, R.neutral[8]);
    pb.hl(sx - 2, sx + 2, tb - 3, top[1]);
  } else if (d.shirt) {
    pb.hl(sx - 1, sx + 1, ty, d.shirt); pb.set(sx, ty + 1, d.shirt);
    if (!d.tie) pb.set(sx, ty + 2, top[1]);
  }
  if (d.tie) { pb.set(sx, ty, d.tie); pb.vl(sx, ty + 1, ty + 4, d.tie); pb.set(sx, ty + 5, top[1]); }
  if (d === DEFS.player) { pb.set(sx - 1, ty + 1, top[1]); pb.set(sx + 1, ty + 1, top[1]); }
  if (d.pin) pb.set(sx - 2, ty + 2, d.pin);
  if (d.star) { pb.set(sx - 2, ty + 3, R.gold[4]); pb.set(sx - 2, ty + 2, R.gold[5]); pb.set(sx - 3, ty + 3, R.gold[3]); pb.set(sx - 1, ty + 3, R.gold[3]); pb.set(sx - 2, ty + 4, R.gold[2]); }
  if (d.badgeS) { pb.set(sx - 2, ty + 2, R.gold[4]); pb.set(sx - 2, ty + 3, R.gold[2]); pb.hl(sx + 2, sx + 3, ty + 1, R.neutral[8]); }
  if (d.pocket) { pb.hl(sx + 2, sx + 3, ty + 2, top[1]); pb.vl(sx, ty, tb - 1, top[1]); }
  if (d.belt && !sit) { pb.hl(x0, x1, tb, d.belt); pb.set(sx, tb, R.gold[3]); }
  if (d.stripe) for (let y = ty + 2; y < tb; y += 2) pb.hl(x0 + 1 + (y < ty + 3 ? lean : 0), x1 - 1, y, d.stripe);
  if (d.susp) { pb.vl(x0 + 2, ty, tb, d.susp); pb.vl(x1 - 2, ty, tb, R.red[2]); pb.set(sx, ty, R.neutral[9]); pb.set(sx, ty + 1, R.neutral[6]); }
  if (d.pearls) { pb.set(sx - 1, ty + 1, P.white); pb.set(sx, ty + 2, R.neutral[8]); pb.set(sx + 1, ty + 1, R.neutral[8]); }
  if (d.coat && !d.tie) { }
  // ----- голова -----
  const hp = paintHead(d, st.head || {});
  const hx0 = x0 + 1 + (st.hx || 0) + lean * 2 - (bw > 10 ? -1 : 0) - 2, hy0 = ty - 7 + (st.hy || 0) - 3;
  for (let y = 0; y < hp.h; y++) for (let x = 0; x < hp.w; x++) {
    const c = hp.d[y * hp.w + x]; if (!c) continue;
    const xx = st.flipHead ? hp.w - 1 - x : x;
    pb.set(hx0 + xx, hy0 + y, c);
  }
  L.hx = hx0 + 2; L.hy = hy0 + 3;
  // ----- реквизит под руками -----
  if (st.prop) drawProp(pb, st.prop, L, st);
  // ----- передняя рука -----
  if (!backBehind) arm(shB, armB, top[1], top[0], false);
  arm(shF, armF || defF, top[2], top[1], true);
  if (d.watch) { const h = (armF || defF); const w = h[h.length - 1]; pb.set(w[0] + 1, w[1] - 1, R.gold[4]); if (st.glint) pb.set(w[0] + 1, w[1] - 2, P.white); }
  if (st.prop2) drawProp(pb, st.prop2, L, st);
  pb.outline(P.outline);
  return pb;
}

function drawProp(pb, prop, L, st) {
  const { x0, ty, tb } = L;
  if (prop === 'pad') { // блокнот на коленях / в руке
    pb.rect(x0 - 2, tb - 3, 5, 3, R.paper[4]); pb.hl(x0 - 2, x0 + 2, tb - 1, R.paper[2]); pb.hl(x0 - 1, x0 + 1, tb - 2, R.paper[1]);
  } else if (prop === 'sketch') {
    pb.rect(x0 - 3, tb - 6, 6, 6, R.wood[3]); pb.rect(x0 - 2, tb - 5, 4, 4, R.paper[4]);
    pb.set(x0 - 1, tb - 4, R.neutral[3]); pb.set(x0, tb - 3, R.neutral[3]); pb.set(x0 - 2, tb - 2, R.paper[2]);
  } else if (prop === 'steno') {
    pb.rect(x0 - 4, tb - 2, 7, 3, R.neutral[2]); pb.hl(x0 - 4, x0 + 2, tb - 2, R.neutral[4]);
    pb.hl(x0 - 3, x0 + 1, tb - 1, R.neutral[1]); pb.set(x0 - 2, tb - 3, R.paper[4]); pb.set(x0 - 1, tb - 3, R.paper[4]); pb.set(x0, tb - 3, R.paper[3]);
  } else if (prop === 'papers') {
    pb.rect(x0 - 3, ty + 4, 5, 4, R.paper[4]); pb.hl(x0 - 2, x0, ty + 5, R.paper[1]); pb.hl(x0 - 2, x0 + 1, ty + 6, R.paper[2]);
    if (st.page) { pb.set(x0 - 4, ty + 3, R.paper[3]); pb.set(x0 - 3, ty + 3, R.paper[4]); }
  } else if (prop === 'hanky') {
    pb.set(L.hx + 1, L.hy + 5, P.white); pb.set(L.hx + 2, L.hy + 5, R.neutral[8]); pb.set(L.hx + 1, L.hy + 6, R.neutral[8]);
  } else if (prop && prop.gavel) {
    const g = prop.gavel; // [x,y,'up'|'down'|'mid']
    if (g[2] === 'up') { pb.line(g[0], g[1], g[0] + 1, g[1] - 3, R.wood[5]); pb.rect(g[0] - 1, g[1] - 6, 4, 2, R.wood[3]); pb.set(g[0] - 1, g[1] - 6, R.wood[5]); }
    else if (g[2] === 'mid') { pb.line(g[0], g[1], g[0] - 3, g[1] - 2, R.wood[5]); pb.rect(g[0] - 5, g[1] - 4, 2, 4, R.wood[3]); pb.set(g[0] - 5, g[1] - 4, R.wood[5]); }
    else {
      pb.hl(g[0] - 3, g[0], g[1], R.wood[5]); pb.rect(g[0] - 5, g[1] - 2, 2, 4, R.wood[3]); pb.set(g[0] - 5, g[1] - 2, R.wood[5]);
      pb.set(g[0] - 7, g[1] + 2, P.white); pb.set(g[0] - 7, g[1] - 2, P.white); pb.set(g[0] - 2, g[1] + 3, P.white);
    }
  }
}

/* ---------------- состояния и кадры ---------------- */
const REACTS = ['whisper', 'gasp', 'murmur', 'angry', 'cheer', 'clap', 'laugh', 'shout'];
const STATES = ['idle', 'fid', 'talk', 'bk'].concat(REACTS);
const NF = { idle: 8, fid: 4, talk: 4, bk: 4, gavel: 4 };
REACTS.forEach(r => NF[r] = 4);

/* описание позы для (id, pose, state, frame) */
function spec(id, pose, state, f) {
  const d = DEFS[id];
  const sit = pose === 'sit';
  const bw = BUILD[d.build || 'mid'];
  const x0 = bw > 10 ? 6 : 7, x1 = x0 + bw - 1;
  const st = { sit, bob: 0, jump: 0, head: { eyes: 'q', mouth: 0 }, arms: null };
  const ub = () => (sit ? 8 : 0) + st.bob + st.jump;
  const ty = () => 13 + ub();
  const tb = () => (sit ? 28 : 22) + st.jump;
  const hy = () => ty() - 7 + (st.hy || 0); // верх головы
  const hx = () => x0 + 1 + (st.hx || 0) + (st.lean || 0) * 2 + (bw > 10 ? 1 : 0); // левый край головы
  switch (state) {
    case 'idle': {
      st.bob = f & 1;
      const h = f >> 1;
      if (h === 1) st.head.eyes = 'b';
      if (h === 2) { st.head.eyes = 'p'; st.hx = -1; }
      if (h === 3) { st.flipHead = true; st.hx = 0; }
      break;
    }
    case 'talk': {
      st.head.mouth = f & 1;
      const g = f >> 1;
      st.arms = { f: g ? [[x0 - 3, ty() + 4], [x0 - 5, ty() + 3]] : [[x0 - 2, ty() + 5], [x0 - 4, ty() + 6]] };
      if (id === 'judge' && sit) st.arms.f = g ? [[x0 - 2, ty() + 4], [x0 - 4, ty() + 2]] : [[x0 - 2, ty() + 5], [x0 - 4, ty() + 5]];
      break;
    }
    case 'gavel': {
      // 0 замах, 1 вверху, 2 удар, 3 после
      if (f === 0) { st.arms = { f: [[x0 - 2, ty() + 2], [x0 - 2, ty() - 2]] }; st.prop2 = { gavel: [x0 - 2, ty() - 2, 'up'] }; }
      if (f === 1) { st.arms = { f: [[x0 - 1, ty() - 1], [x0, ty() - 5]] }; st.prop2 = { gavel: [x0, ty() - 5, 'up'] }; st.head.mouth = 1; }
      if (f === 2) { st.arms = { f: [[x0 - 3, ty() + 3], [x0 - 4, ty() + 6]] }; st.prop2 = { gavel: [x0 - 3, ty() + 7, 'down'] }; st.head.eyes = 'down'; st.head.mouth = 2; st.bob = 1; }
      if (f === 3) { st.arms = { f: [[x0 - 3, ty() + 3], [x0 - 4, ty() + 3]] }; st.prop2 = { gavel: [x0 - 3, ty() + 3, 'mid'] }; }
      break;
    }
    case 'bk': {
      const sh = (f & 1) ? 1 : -1;
      st.hx = sh > 0 ? 0 : -1; st.bob = 1; st.hy = 1;
      st.head.eyes = 'b'; st.head.mouth = f >= 2 ? 3 : 2; st.head.red = true;
      st.arms = { f: [[x0 - 3, ty() - 1], [hx() - 1, hy() + 1]], b: [[x1 + 3, ty() - 1], [hx() + 7, hy() + 1]] };
      st.backBehind = false;
      st.red = false;
      break;
    }
    case 'whisper': {
      st.lean = -1; st.hx = -1 - (f >> 1 & 1);
      st.head.eyes = (f === 3) ? 'p' : 'q'; st.head.mouth = f & 1;
      st.arms = { f: [[x0 - 2, ty() + 4], [hx() - 2, hy() + 4]] };
      break;
    }
    case 'gasp': {
      st.jump = f === 0 ? -1 : 0; st.hy = f === 0 ? 0 : 0;
      st.head.eyes = 'wide'; st.head.mouth = 3;
      if (f === 0) st.arms = { f: [[x0 - 2, ty() + 5], [x0 - 2, ty() + 1]], b: [[x1 + 2, ty() + 5], [x1 + 2, ty() + 1]] };
      else st.arms = { f: [[x0 - 2, ty() + 3], [hx() - 1, hy() + 4]], b: [[x1 + 2, ty() + 3], [hx() + 5, hy() + 4]] };
      if (f === 2) st.head.eyes = 'q';
      if (f >= 1) st.backBehind = false;
      break;
    }
    case 'murmur': {
      const seq = [-1, 0, 1, 0];
      st.hx = seq[f] < 0 ? -1 : 0; st.flipHead = seq[f] > 0;
      st.head.eyes = seq[f] < 0 ? 'p' : 'q'; st.head.mouth = (f & 1) ? 1 : 0;
      st.arms = { f: [[x0 - 1, ty() + 5], [x0 + 1, tb() - 2]], b: [[x1 + 1, ty() + 5], [x1 - 1, tb() - 2]] };
      break;
    }
    case 'angry': {
      st.head.red = true; st.head.mouth = 2; st.red = false;
      st.hx = (f & 1) ? 0 : -1; st.jump = (f & 1) ? 0 : -1;
      const up = f < 2 ? 0 : 1;
      st.arms = { f: [[x0 - 3, ty() - 1], [x0 - 3 - (f & 1), ty() - 6 - up]] };
      break;
    }
    case 'cheer': {
      st.jump = (f & 1) ? 0 : -2; st.head.eyes = 'happy'; st.head.mouth = 2;
      const w = (f >> 1) & 1;
      st.arms = { f: [[x0 - 3, ty() - 2], [x0 - 3 - w, ty() - 7]], b: [[x1 + 3, ty() - 2], [x1 + 3 + w, ty() - 7]] };
      st.backBehind = false;
      break;
    }
    case 'clap': {
      st.head.eyes = 'happy'; st.head.mouth = (f >> 1) & 1;
      const c = x0 + Math.floor((bw - 1) / 2);
      if (f & 1) st.arms = { f: [[x0 - 1, ty() + 5], [c - 2, ty() + 4]], b: [[x1, ty() + 5], [c + 1, ty() + 4]] };
      else st.arms = { f: [[x0 - 2, ty() + 5], [c - 4, ty() + 3]], b: [[x1 + 1, ty() + 5], [c + 3, ty() + 3]] };
      st.backBehind = false;
      st.bob = (f & 1);
      break;
    }
    case 'laugh': {
      st.head.eyes = 'happy'; st.head.mouth = 2; st.bob = f & 1; st.hy = (f & 1) ? 0 : -1;
      st.arms = { f: [[x0 - 1, ty() + 5], [x0 + 2, tb() - 2]], b: f >= 2 ? [[x1 + 2, ty() + 3], [x1 + 1, ty()]] : null };
      if (!st.arms.b) delete st.arms.b;
      st.lean = f >= 2 ? 0 : 0;
      break;
    }
    case 'shout': {
      st.lean = -1; st.head.mouth = 3; st.head.eyes = (f & 1) ? 'wide' : 'q'; st.jump = (f & 1) ? -1 : 0;
      st.arms = { f: [[x0 - 3, ty() + 3], [hx() - 3, hy() + 4]] };
      if (f >= 2) st.arms.b = [[x1 + 3, ty() - 1], [x1 + 3, ty() - 5]], st.backBehind = false;
      break;
    }
    case 'fid': fidget(id, d, st, f, { x0, x1, ty, tb, hx, hy, sit, bw }); break;
  }
  return st;
}

function fidget(id, d, st, f, L) {
  const { x0, x1, ty, tb, hx, hy, sit, bw } = L;
  const c = x0 + Math.floor((bw - 1) / 2);
  switch (d.fid) {
    case 'write': {
      st.prop = 'pad'; st.head.eyes = 'down'; st.bob = f === 3 ? 1 : 0;
      const k = [0, 1, 2, 1][f];
      st.arms = { f: [[x0 - 1, ty() + 5], [x0 + k - 1, tb() - 4]], b: [[x1 + 1, ty() + 5], [x0 + 3, tb() - 2]] };
      st.backBehind = false;
      break;
    }
    case 'sketch': {
      st.prop = 'sketch'; st.head.eyes = f === 2 ? 'q' : 'down';
      const k = [0, 2, 0, 1][f];
      st.arms = { f: [[x0 - 1, ty() + 4], [x0 - 1 + k, tb() - 5 + (f & 1)]], b: [[x1 + 1, ty() + 5], [x0 + 3, tb() - 3]] };
      st.backBehind = false;
      break;
    }
    case 'type': {
      st.prop = 'steno'; st.head.eyes = f === 3 ? 'q' : 'down';
      st.arms = { f: [[x0 - 2, ty() + 5], [x0 - 3 + (f & 1), tb() - 4 + ((f >> 1) & 1)]], b: [[x1 + 1, ty() + 5], [x0 + 1 - (f & 1), tb() - 4 + (f === 1 ? 1 : 0)]] };
      st.backBehind = false;
      break;
    }
    case 'glasses': {
      const up = f === 1 || f === 2;
      st.arms = { f: up ? [[x0 - 2, ty() + 3], [hx() + 1, hy() + 4]] : [[x0 - 2, ty() + 5], [x0 - 1, ty() + 3]] };
      st.glint = f === 2; st.head.eyes = f === 1 ? 'b' : 'q';
      break;
    }
    case 'cap': {
      const up = f === 1 || f === 2;
      st.arms = { f: up ? [[x0 - 3, ty() + 1], [hx() - 1, hy()]] : [[x0 - 2, ty() + 5], [x0 - 2, ty() + 3]] };
      st.head.eyes = f === 2 ? 'b' : 'q'; st.hy = f === 2 ? 1 : 0;
      break;
    }
    case 'watch': {
      st.arms = { f: [[x0 - 1, ty() + 5], [c - 1, ty() + 4]] };
      st.head.eyes = f === 3 ? 'q' : 'down'; st.glint = f === 1 || f === 2; st.bob = f === 2 ? 1 : 0;
      break;
    }
    case 'scratch': {
      st.arms = { f: [[x0 - 2, ty() + 1], [hx() + 1, hy() - 1 + (f & 1)]] };
      st.head.eyes = f === 2 ? 'b' : 'q'; st.hx = f >= 2 ? -1 : 0;
      break;
    }
    case 'cross': {
      st.arms = { f: [[x0, ty() + 4], [c + 2, ty() + 4]], b: [[x1, ty() + 5], [c - 2, ty() + 5]] };
      st.backBehind = true;
      st.bob = f & 1;
      if (f === 2) { st.head.eyes = 'p'; st.hx = -1; }
      if (f === 3) st.flipHead = true;
      break;
    }
    case 'tie': {
      const up = f === 1 || f === 2;
      st.arms = { f: up ? [[x0 - 1, ty() + 4], [c - 1, ty() + 1 + (f & 1)]] : [[x0 - 1, ty() + 6], [x0, ty() + 7]] };
      st.head.eyes = up ? 'down' : 'q';
      break;
    }
    case 'papers': {
      st.prop = 'papers'; st.page = f === 2; st.head.eyes = f === 3 ? 'q' : 'down';
      st.arms = { f: [[x0 - 2, ty() + 5], [x0 - 3, ty() + 6]], b: [[x1 + 1, ty() + 5], [x0 + 1, ty() + 6]] };
      st.backBehind = false;
      if (f === 3) st.bob = 1;
      break;
    }
    case 'hanky': {
      const up = f === 1 || f === 2;
      st.arms = { f: up ? [[x0 - 2, ty() + 3], [hx(), hy() + 5]] : [[x0 - 1, ty() + 5], [x0 + 1, ty() + 6]] };
      if (up) st.prop2 = 'hanky';
      st.head.eyes = up ? 'b' : 'down'; st.hy = 1;
      break;
    }
    default: { // look: оглядывается
      st.head.eyes = ['p', 'p', 'q', 'q'][f]; st.hx = f < 2 ? -1 : 0; st.flipHead = f === 3;
      st.bob = f & 1; if (f === 2) st.head.eyes = 'b';
    }
  }
}

/* ---------------- кэш и рантайм ---------------- */
function key(id, pose, dir, state, f) { return 'iso/' + id + '/' + pose + '/' + dir + '/' + state + '/' + f; }
function sprite(id, pose, dir, state, f) {
  return G.cacheCanvas(key(id, pose, dir, state, f), W, H, c => {
    const pb = paint(id, spec(id, pose, state, f));
    pb.render(c, dir === 'r');
  });
}
function pick(id, o) {
  const d = DEFS[id];
  const h = hashStr(id), ph = (h % 1000) / 1000;
  const t = (o.t || 0) + ph * 17;
  if (o.react && NF[o.react]) {
    const rt = o.reactT !== undefined ? o.reactT : (o.t || 0);
    const rate = { whisper: 3, gasp: 4, murmur: 3, angry: 7, cheer: 5, clap: 7, laugh: 7, shout: 6 }[o.react];
    let f = Math.floor(rt * rate) % 4;
    if (o.react === 'gasp') f = rt < 0.2 ? 0 : 1 + (Math.floor(rt * 2) % 3);
    return ['react', o.react, f];
  }
  if (o.emo === 'breakdown' || o.anim === 'breakdown') return ['bk', 'bk', Math.floor((o.t || 0) * 8) % 4];
  if (id === 'judge' && o.anim === 'gavel') {
    const a = o.animT || 0;
    if (a < 0.9) return ['gavel', 'gavel', a < 0.25 ? 0 : a < 0.45 ? 1 : a < 0.65 ? 2 : 3];
  }
  if (o.talking) {
    const m = Math.floor((o.t || 0) * 8) % 2, g = Math.floor(t * 1.3) % 2;
    return ['talk', 'talk', g * 2 + m];
  }
  // постоянная работа
  if (d.fid === 'type' && o.pose === 'sit') return ['fid', 'fid', Math.floor(t * 9) % 4];
  // фиджет по циклу
  const fp = 9 + (h % 7);
  const fpos = (t * 1.0) % fp;
  const fl = d.fid === 'write' || d.fid === 'sketch' ? 4.5 : d.fid === 'cross' ? 4 : 2.2;
  if (fpos < fl && !(d.fid === 'write' && o.pose !== 'sit')) {
    let f;
    if (d.fid === 'write' || d.fid === 'sketch' || d.fid === 'type') f = Math.floor(t * 5) % 4;
    else if (d.fid === 'cross') f = fpos < 1.5 ? 0 + Math.floor(t / 1.4) % 2 : (fpos < 2.8 ? 2 : 3);
    else if (d.fid === 'look') f = Math.min(3, Math.floor(fpos / fl * 4));
    else f = fpos < 0.4 ? 0 : fpos < 1.2 ? 1 : fpos < 1.8 ? 2 : 3;
    return ['fid', 'fid', f];
  }
  // дыхание, моргание, повороты головы
  const per = 2.5 + (h % 8) * 0.2;
  const bob = ((t / per) % 1) < 0.5 ? 0 : 1;
  let hd = 0;
  const bp = 3.1 + (h % 5) * 0.35;
  if ((t % bp) < 0.13) hd = 1;
  const lp = 6 + (h % 6);
  const lpos = (t * 1.07 + 3) % lp;
  if (lpos < 1.3) hd = 2; else if (lpos > lp - 1.1 && (h & 2)) hd = 3;
  return ['idle', 'idle', hd * 2 + bob];
}
function makeDraw(id) {
  return function (ctx, x, y, o) {
    o = o || {};
    const pose = o.pose === 'sit' ? 'sit' : 'stand';
    const dir = o.dir === 'r' ? 'r' : 'l';
    const p = pick(id, o);
    const spr = sprite(id, pose, dir, p[1], p[2]);
    ctx.drawImage(spr, (x | 0) - AX, (y | 0) - AY);
  };
}

const NAMES = { reporter: 'Стенографистка', foreperson: 'Старшина присяжных' };
for (const id in DEFS) {
  const iso = { draw: makeDraw(id), w: W, h: H, anchor: [AX, AY] };
  const def = G.Cast.defs[id];
  if (def) def.iso = iso;
  else G.Cast.register(id, {
    name: NAMES[id] || (id.startsWith('juror') ? 'Присяжный №' + id.slice(5) : 'Зритель'),
    voice: 'mid', emotions: [], anims: id === 'judge' ? { gavel: 0.9 } : {}, iso,
  });
}
G.Iso = { ids: Object.keys(DEFS), states: STATES, reacts: REACTS, frames: NF, sprite, key };

G.prebuild(() => {
  for (const id in DEFS) for (const pose of ['stand', 'sit']) for (const dir of ['l', 'r']) {
    const sts = STATES.slice(); if (id === 'judge') sts.push('gavel');
    for (const s of sts) for (let f = 0; f < NF[s]; f++) sprite(id, pose, dir, s, f);
  }
});
})();
