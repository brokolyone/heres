/* =====================================================================
   ENV — окружение «Слово защиты»: изометрический зал суда,
   крупные планы и фасад здания суда.
   ===================================================================== */
(function () {
'use strict';
const G = window.G;
const R = G.RAMP, P = G.PAL;
const WD = R.wood, ST = R.stone, NE = R.neutral, CA = R.carpet, GO = R.gold;

/* ---------------------------------------------------------------- utils */
function C(ramp, i) { return ramp[i < 0 ? 0 : i >= ramp.length ? ramp.length - 1 : i]; }
function hash(n) {
  n = (n ^ 61) ^ (n >>> 16); n = n + (n << 3); n = n ^ (n >>> 4);
  n = Math.imul(n, 0x27d4eb2d); n = n ^ (n >>> 15); return (n >>> 0) / 4294967296;
}
function h2(x, y) { return hash((x * 374761393 + y * 668265263) | 0); }
const rect = G.rect, px = G.px;
function fill(c, x, y, w, h, col) { if (w > 0 && h > 0) { c.fillStyle = col; c.fillRect(x, y, w, h); } }

/* 3x5 pixel font for engravings / plates / signs */
const F3 = {
  A: '010101111101101', B: '110101110101110', C: '011100100100011', D: '110101101101110',
  E: '111100110100111', F: '111100110100100', G: '011100101101011', H: '101101111101101',
  I: '111010010010111', J: '001001001101010', K: '101101110101101', L: '100100100100111',
  M: '101111111101101', N: '110101101101101', O: '010101101101010', P: '110101110100100',
  Q: '010101101110011', R: '110101110101101', S: '011100010001110', T: '111010010010010',
  U: '101101101101111', V: '101101101101010', W: '101101111111101', X: '101101010101101',
  Y: '101101010010010', Z: '111001010100111', '.': '000000000000010', ' ': '000000000000000',
  '1': '010110010010111', '2': '110001010100111', '0': '010101101101010', '3': '110001010001110',
  '-': '000000111000000', '4': '101101111001001', '5': '111100110001110', '6': '011100110101010', '7': '111001010010010', '8': '010101010101010', '9': '010101011001110', '&': '010101010101011',
};
function text3(c, s, x, y, col, sh) {
  for (let i = 0; i < s.length; i++) {
    const g = F3[s[i]] || F3[' '];
    for (let k = 0; k < 15; k++) if (g[k] === '1') {
      if (sh) px(c, x + i * 4 + (k % 3), y + ((k / 3) | 0) + 1, sh);
    }
    for (let k = 0; k < 15; k++) if (g[k] === '1') px(c, x + i * 4 + (k % 3), y + ((k / 3) | 0), col);
  }
}
function text3W(s) { return s.length * 4 - 1; }

/* Raised carved panel shading by pixel distances to the panel edges.
   Light from top-left: top/left bevels lit, bottom/right bevels in shade. */
function panelCol(dl, dr, dt, db, ramp, b, bev, x, y) {
  const m = Math.min(dl, dr, dt, db);
  if (m < 0) return null;
  if (m === 0) return (dt === 0 || dl === 0) ? C(ramp, b - 2) : C(ramp, b + 1);
  if (m <= bev) {
    if (dt === m) return C(ramp, b + 2);
    if (db === m) return C(ramp, b - 1);
    if (dl === m) return C(ramp, b + 1);
    return C(ramp, b - 1);
  }
  if (m === bev + 1 && (db === m || dr === m)) return C(ramp, b - 1);
  // grain
  if (x !== undefined) {
    const gq = ((x * 3 + ((y / 5) | 0) * (((x >> 2) & 1) ? 1 : -1)) % 7 + 7) % 7;
    if (gq === 0 && (y & 1)) return C(ramp, b - 1);
  }
  return C(ramp, b);
}
/* draw a flat (elevation) raised panel into canvas */
function panelRect(c, x, y, w, h, ramp, b, bev) {
  for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) {
    const col = panelCol(i, w - 1 - i, j, h - 1 - j, ramp, b, bev || 2, x + i, y + j);
    if (col) px(c, x + i, y + j, col);
  }
}
/* horizontal moulding stack: list of ramp indices from top to bottom */
function moulding(c, x, y, w, ramp, idx) { idx.forEach((k, j) => fill(c, x, y + j, w, 1, C(ramp, k))); }

/* ================================================================
   ISOMETRIC WORLD
   ================================================================ */
const WW = 560, WH = 320;
const TX = 256, TY = 102;          // floor top corner
const RW = 14, RD = 11, HW = 84;   // room size in tiles (gx, gy), wall height px
function ix(gx, gy) { return Math.round(TX + (gx - gy) * 16); }
function iyF(gx, gy) { return Math.round(TY + (gx + gy) * 8); }
function iy(gx, gy, z) { return iyF(gx, gy) - (z || 0); }

/* face along gx (fixed gy) facing +gy (screen down-left side). src: color | canvas texture */
function faceX(c, gx0, gx1, gy, z0, z1, src) {
  const x0 = ix(gx0, gy), w = ix(gx1, gy) - x0, yb = iyF(gx0, gy) - z0, h = z1 - z0;
  if (typeof src === 'string') {
    c.fillStyle = src;
    for (let u = 0; u < w; u++) c.fillRect(x0 + u, yb + (u >> 1) - h, 1, h);
  } else {
    const sh = src.height;
    for (let u = 0; u < w; u++) c.drawImage(src, u % src.width, 0, 1, sh, x0 + u, yb + (u >> 1) - sh, 1, sh);
  }
}
/* face along gy (fixed gx) facing +gx (screen down-right side). Texture u=0 is the FRONT end (gy1) */
function faceY(c, gx, gy0, gy1, z0, z1, src) {
  const xb = ix(gx, gy0), L = xb - ix(gx, gy1), yb = iyF(gx, gy0) - z0, h = z1 - z0;
  if (typeof src === 'string') {
    c.fillStyle = src;
    for (let u = 0; u < L; u++) c.fillRect(xb - L + u, yb + ((L - 1 - u) >> 1) - h, 1, h);
  } else {
    const sh = src.height;
    for (let u = 0; u < L; u++) c.drawImage(src, u % src.width, 0, 1, sh, xb - L + u, yb + ((L - 1 - u) >> 1) - sh, 1, sh);
  }
}
/* horizontal surface at height z; src: color | fn(gx,gy,x,y)->color */
function topF(c, gx0, gy0, gx1, gy1, z, src) {
  const xL = ix(gx0, gy1), xT = ix(gx0, gy0), xR = ix(gx1, gy0), xB = ix(gx1, gy1);
  const yL = iyF(gx0, gy1) - z, yT = iyF(gx0, gy0) - z, yR = iyF(gx1, gy0) - z;
  const isFn = typeof src === 'function';
  if (!isFn) c.fillStyle = src;
  for (let x = xL; x < xR; x++) {
    const bb = x < xT ? yT + ((xT - 1 - x) >> 1) : yT + ((x - xT) >> 1);
    const fb = x < xB ? yL + ((x - xL) >> 1) : yR + ((xR - 1 - x) >> 1);
    if (!isFn) { if (fb > bb) c.fillRect(x, bb, 1, fb - bb); continue; }
    for (let y = bb; y < fb; y++) {
      const a = (x + 0.5 - TX) / 16, s = (y + 0.5 + z - TY) / 8;
      const col = src((s + a) / 2, (s - a) / 2, x, y);
      if (col) { c.fillStyle = col; c.fillRect(x, y, 1, 1); }
    }
  }
}
/* box with top/left(+gy)/right(+gx) faces + crisp edges */
function box(c, gx0, gy0, gx1, gy1, z0, z1, o) {
  if (o.top) topF(c, gx0, gy0, gx1, gy1, z1, o.top);
  if (o.l) faceX(c, gx0, gx1, gy1, z0, z1, o.l);
  if (o.r) faceY(c, gx1, gy0, gy1, z0, z1, o.r);
  if (o.hl) { faceX(c, gx0, gx1, gy1, z1 - 1, z1, o.hl); }
  if (o.hr) { faceY(c, gx1, gy0, gy1, z1 - 1, z1, o.hr); }
  if (o.edge) { // vertical front corner
    const x = ix(gx1, gy1), y = iyF(gx1, gy1);
    fill(c, x - 1, y - z1, 1, z1 - z0, o.edge);
  }
  if (o.ol) { // dark outline at the base
    faceX(c, gx0, gx1, gy1, z0, z0 + 1, o.ol); faceY(c, gx1, gy0, gy1, z0, z0 + 1, o.ol);
  }
}
function shadowTop(c, gx0, gy0, gx1, gy1, a) {
  c.globalAlpha = a || 0.3; topF(c, gx0, gy0, gx1, gy1, 0, P.shadow); c.globalAlpha = 1;
}

/* ---- layout (tile coords, multiples of 1/8) ---- */
const L = {
  bench: [3.375, 0.5, 5.875, 1.625, 34],
  clerk: [1.25, 0.75, 3.0, 1.625, 22],
  reporter: [5.875, 1.875, 6.625, 2.5, 12],
  witness: [6.375, 0.875, 7.5, 1.875, 26],
  jury: [8.5, 0, 13.75, 2.25],
  def: [1.25, 4.5, 3.75, 5.5, 10],
  pro: [7.0, 4.5, 9.5, 5.5, 10],
  lectern: [5.0, 4.75, 5.5, 5.25, 18],
  bar: 6.625,
  pews: [7.75, 9.125, 10.5],
};
// light: window point (0,gy,z) falls to floor at (z*LK, gy+z*LM)
const LK = 1 / 17, LM = 1 / 34;
const WINS = [[1.0, 2.5], [3.25, 4.75], [5.5, 7.0]];
const WZ0 = 34, WZ1 = 76;
function litAmt(gx, gy) {
  const z = gx / LK; if (z < WZ0 - 3 || z > WZ1 + 3) return 0;
  const g = gy - z * LM;
  let best = 0;
  for (const w of WINS) {
    const d = Math.min(g - w[0], w[1] - g, (z - WZ0) / 16 * 0.3 + 0.1, (WZ1 - z) / 16 * 0.3 + 0.1);
    best = Math.max(best, d);
  }
  return G.clamp(best / 0.18, 0, 1);
}

/* ---- spots ---- */
function spot(gx, gy, z, pose, dir) { return { x: ix(gx, gy), y: iy(gx, gy, z), pose, dir, gx, gy }; }
const juryFront = [], juryRear = [];
for (let i = 0; i < 6; i++) {
  juryFront.push(spot(8.875 + i * 0.75, 1.75, 0, 'sit', 'l'));
  juryRear.push(spot(9.375 + i * 0.75, 0.5, 10, 'sit', 'l'));
}
const gallery = [];
const galSeats = [1.0, 2.25, 3.375, 6.0, 7.25, 8.5, 9.75];
L.pews.forEach((gy, r) => galSeats.forEach((gx, k) => {
  if (r === 2 && k > 4) return;
  gallery.push(spot(gx + (r & 1) * 0.25, gy, 0, 'sit', k < 3 ? 'r' : 'l'));
}));
const spots = {
  judge: spot(4.625, 0.25, 25, 'sit', 'l'),
  clerk: spot(2.125, 0.5, 12, 'sit', 'l'),
  witness: spot(6.875, 0.625, 16, 'sit', 'l'),
  reporter: spot(6.25, 1.625, 0, 'sit', 'l'),
  bailiff: spot(0.875, 3.0, 0, 'stand', 'r'),
  defense: spot(1.875, 4.25, 0, 'stand', 'r'),
  defendant: spot(3.125, 4.25, 0, 'sit', 'r'),
  prosecution: spot(8.375, 4.25, 0, 'stand', 'l'),
  jury: juryFront.concat(juryRear),
  gallery,
};

/* ---- textures ---- */
function wallTexR() { // back-right wall elevation, u = gx*16 (0..224), height HW
  const w = RW * 16, h = HW;
  return G.makeSprite(w, h, c => {
    // plaster
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      let col = ST[4];
      const n = h2(x, y);
      if (n < 0.05) col = ST[3]; else if (n > 0.97) col = ST[5];
      px(c, x, y, col);
    }
    // soft top shading (higher = dimmer), dithered
    G.dither(c, 0, 0, w, 10, ST[3], 10); G.dither(c, 0, 10, w, 8, ST[3], 4);
    // crown
    moulding(c, 0, 0, w, WD, [1, 4, 3, 2, 1, 0]);
    fill(c, 0, 6, w, 1, ST[3]);
    // picture rail
    moulding(c, 0, 20, w, WD, [3, 1]);
    // wainscot
    const wt = h - 34;
    fill(c, 0, wt, w, 34, WD[2]);
    moulding(c, 0, wt - 1, w, WD, [5, 4, 3, 1, 2]);
    for (let p = 0; p < w; p += 16) panelRect(c, p + 2, wt + 7, 12, 19, WD, 3, 1);
    moulding(c, 0, h - 5, w, WD, [3, 1, 1, 0, 0]);
  });
}
function wallTexL() { // left wall elevation, u=0 front (gy=11) .. 176 back (gy=0)
  const w = RD * 16, h = HW;
  return G.makeSprite(w, h, c => {
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      const n = h2(x + 999, y);
      px(c, x, y, n < 0.06 ? ST[2] : ST[3]);
    }
    G.dither(c, 0, 0, w, 12, ST[2], 8);
    moulding(c, 0, 0, w, WD, [0, 3, 2, 1, 0, 0]);
    fill(c, 0, 6, w, 1, ST[2]);
    moulding(c, 0, 20, w, WD, [2, 0]);
    const wt = h - 34;
    fill(c, 0, wt, w, 34, WD[1]);
    moulding(c, 0, wt - 1, w, WD, [4, 3, 2, 0, 1]);
    for (let p = 0; p < w; p += 16) panelRect(c, p + 2, wt + 7, 12, 19, WD, 2, 1);
    moulding(c, 0, h - 5, w, WD, [2, 0, 0, 0, 0]);
    // windows
    for (const wn of WINS) {
      const u0 = Math.round((RD - wn[1]) * 16), u1 = Math.round((RD - wn[0]) * 16);
      const y0 = h - WZ1, y1 = h - WZ0;
      // casing
      fill(c, u0 - 3, y0 - 3, u1 - u0 + 6, y1 - y0 + 5, WD[2]);
      fill(c, u0 - 3, y0 - 3, u1 - u0 + 6, 1, WD[4]);
      fill(c, u0 - 3, y0 - 3, 1, y1 - y0 + 5, WD[3]);
      fill(c, u0 - 4, y1 + 1, u1 - u0 + 8, 2, WD[4]); fill(c, u0 - 4, y1 + 3, u1 - u0 + 8, 1, WD[0]);
      // reveal (deep wall, light side)
      fill(c, u0 - 1, y0 - 1, u1 - u0 + 2, y1 - y0 + 2, ST[4]);
      fill(c, u1 - 2, y0 - 1, 3, y1 - y0 + 2, ST[5]);
      // glass: sky outside, bright toward bottom
      for (let y = y0; y < y1; y++) for (let x = u0; x < u1 - 2; x++) {
        const f = (y - y0) / (y1 - y0);
        let col = f < 0.35 ? P.sky : f < 0.7 ? P.sky2 : P.glow;
        const b = G.bayer(x, y);
        if (f >= 0.27 && f < 0.35 && b < 8) col = P.sky2;
        if (f >= 0.62 && f < 0.7 && b < 8) col = P.glow;
        px(c, x, y, col);
      }
      // palm silhouette outside
      const pxx = u0 + 4 + (u0 % 7);
      for (let y = y0 + 10; y < y1; y++) px(c, pxx + (((y - y0) / 9) | 0) % 2, y, R.green[2]);
      [[-5, -2], [-4, 1], [4, -1], [5, 2], [-2, 3], [2, 3]].forEach(([dx, dy]) =>
        G.line(c, pxx, y0 + 10, pxx + dx, y0 + 10 + dy + 2, R.green[2]));
      // mullions
      const mid = (u0 + u1 - 2) >> 1;
      fill(c, mid, y0, 1, y1 - y0, WD[2]);
      for (let y = y0 + 9; y < y1; y += 10) fill(c, u0, y, u1 - u0 - 2, 1, WD[2]);
      fill(c, u0, y0 + 13, u1 - u0 - 2, 1, WD[3]);
      // blinds pulled up
      fill(c, u0, y0, u1 - u0 - 2, 4, ST[4]);
      for (let k = 0; k < 4; k += 2) fill(c, u0, y0 + k, u1 - u0 - 2, 1, ST[3]);
      fill(c, u0, y0 + 4, u1 - u0 - 2, 1, ST[2]);
    }
    // exit door
    const d0 = Math.round((RD - 10.125) * 16), d1 = Math.round((RD - 8.625) * 16);
    const dy0 = h - 50;
    fill(c, d0 - 3, dy0 - 3, d1 - d0 + 6, 53, WD[3]);
    fill(c, d0 - 3, dy0 - 3, d1 - d0 + 6, 1, WD[5]);
    fill(c, d0 - 3, dy0 - 3, 1, 53, WD[4]);
    fill(c, d0, dy0, d1 - d0, 50, WD[0]);
    const half = (d1 - d0) >> 1;
    for (let k = 0; k < 2; k++) {
      const dx = d0 + k * half;
      fill(c, dx, dy0, half - 1, 50, WD[2]);
      panelRect(c, dx + 2, dy0 + 3, half - 5, 14, WD, 2, 1);
      // small door window
      fill(c, dx + 3, dy0 + 5, half - 7, 10, NE[3]); fill(c, dx + 3, dy0 + 5, half - 7, 1, NE[2]);
      G.dither(c, dx + 3, dy0 + 6, half - 7, 9, NE[4], 4);
      panelRect(c, dx + 2, dy0 + 21, half - 5, 24, WD, 2, 1);
      fill(c, dx + (k ? 1 : half - 4), dy0 + 26, 2, 1, GO[4]);
    }
    fill(c, d0 - 1, dy0 + 32, d1 - d0 + 2, 2, NE[4]); // push bar
    fill(c, d0 - 1, dy0 + 32, d1 - d0 + 2, 1, NE[6]);
    // EXIT sign
    const sx = ((d0 + d1) >> 1) - 9, sy = dy0 - 12;
    fill(c, sx, sy, 19, 8, NE[8]); fill(c, sx, sy + 7, 19, 1, NE[5]); fill(c, sx, sy, 19, 1, NE[9]);
    text3(c, 'EXIT', sx + 2, sy + 2, R.red[3]);
    // thermostat + vent
    fill(c, 30, h - 46, 5, 7, ST[5]); fill(c, 30, h - 40, 5, 1, ST[2]); px(c, 32, h - 44, NE[4]);
  });
}
const BD0 = 3.0, BD1 = 6.25; // bench backdrop on the right wall
function backdropTex() {
  const w = Math.round((BD1 - BD0) * 16), h = HW - 2;
  return G.makeSprite(w, h, c => {
    fill(c, 0, 0, w, h, WD[1]);
    // pediment / cornice
    moulding(c, 0, 0, w, WD, [0, 4, 5, 3, 2, 1, 0]);
    fill(c, 0, 7, w, 1, WD[3]);
    for (let x = 1; x < w; x += 3) { px(c, x, 8, WD[4]); px(c, x, 9, WD[1]); } // dentils
    fill(c, 0, 10, w, 1, WD[0]);
    // tall pilasters at edges
    for (const xx of [0, w - 5]) {
      fill(c, xx, 11, 5, h - 11, WD[3]);
      fill(c, xx, 11, 1, h - 11, WD[5]); fill(c, xx + 4, 11, 1, h - 11, WD[1]);
      fill(c, xx + 2, 14, 1, h - 20, WD[2]);
    }
    // big field behind the seal
    panelRect(c, 7, 13, w - 14, 38, WD, 2, 2);
    panelRect(c, 7, 54, (w - 16) >> 1, 26, WD, 2, 1);
    panelRect(c, 9 + ((w - 16) >> 1), 54, (w - 16) >> 1, 26, WD, 2, 1);
  });
}
/* Great Seal of California, r ~ radius (elevation drawing) */
function drawSeal(c, cx, cy, r) {
  for (let y = -r; y <= r; y++) for (let x = -r; x <= r; x++) {
    const d = Math.sqrt(x * x + y * y);
    if (d > r + 0.4) continue;
    let col;
    if (d > r - 1) col = GO[1];
    else if (d > r - 2) col = (x + y < 0) ? GO[5] : GO[3];
    else if (d > r - Math.max(3, r * 0.28)) {
      // lettering band with dots
      const a = Math.atan2(y, x), k = Math.floor((a + Math.PI) / (Math.PI * 2) * r * 3.2);
      col = (k % 2 === 0 && d < r - 2.5 && d > r - Math.max(3, r * 0.28) + 0.7) ? GO[1] : GO[3];
      if (x + y < -r * 0.4 && col === GO[3]) col = GO[4];
    } else if (d > r - Math.max(3, r * 0.28) - 1) col = GO[1];
    else {
      // inner scene
      const ry = y / (r * 0.7);
      if (ry < -0.15) col = (G.bayer(x, y) < 4) ? R.blue[5] : R.blue[6];
      else if (ry < 0.1) col = (Math.abs(x + r * 0.2) < r * 0.4 - (ry + 0.15) * r * 1.4) ? ST[4] : R.blue[5]; // mountains
      else if (ry < 0.35) col = (G.bayer(x, y) < 6) ? R.blue[3] : R.blue[4]; // bay
      else col = GO[2];
      if (ry > 0.35) col = (x + y) & 3 ? GO[3] : GO[2];
    }
    px(c, cx + x, cy + y, col);
  }
  const s = r / 11;
  // Minerva (seated) + shield
  const mx = cx - Math.round(2 * s), my = cy + Math.round(2 * s);
  fill(c, mx, my - Math.round(6 * s), Math.max(2, Math.round(3 * s)), Math.round(7 * s), GO[4]);
  fill(c, mx, my - Math.round(8 * s), 2, 2, GO[5]);
  fill(c, mx + 1, my - Math.round(9 * s), 1, 1, R.red[3]);
  G.ellipse(c, mx - Math.round(2 * s), my - Math.round(2 * s), Math.max(1, Math.round(2 * s)), Math.max(1, Math.round(2 * s)), GO[3]);
  px(c, mx - Math.round(2 * s), my - Math.round(2 * s), GO[5]);
  G.line(c, mx + Math.round(3 * s), my - Math.round(9 * s), mx + Math.round(3 * s), my + 1, GO[5]); // spear
  // grizzly bear
  const bx = cx + Math.round(3 * s), by = cy + Math.round(4 * s);
  fill(c, bx, by - Math.round(2 * s), Math.round(5 * s), Math.max(2, Math.round(2 * s)), R.hairBrown[2]);
  fill(c, bx + Math.round(5 * s) - 1, by - Math.round(3 * s), 2, 2, R.hairBrown[2]);
  // star
  px(c, cx, cy - r + Math.max(3, Math.round(r * 0.28)) + 1, GO[5]);
}

/* clock face (elevation) and hands */
function clockHands(t) {
  const sec = 9 * 3600 + 41 * 60 + 12 + t;
  return {
    m: (sec / 3600) % 1 * Math.PI * 2, h: (sec / 43200) % 1 * Math.PI * 2,
    s: Math.floor(sec % 60) / 60 * Math.PI * 2,
  };
}

/* ---- world pre-render ---- */
let WB = null, WF = null; // back/front canvases
const flagFrames = { us: [], ca: [] };

function makeFlag(kind, w, h, ph) {
  // hanging (draped) flag: cloth hangs from top bar along the pole, folds sway with phase ph
  return G.makeSprite(w + 2, h + 4, c => {
    for (let x = 0; x < w; x++) {
      const fold = Math.sin(x * 1.3 + ph) ;
      const len = h - (x > w - 3 ? (x - (w - 3)) * 2 : 0) + Math.round(Math.sin(ph * 0.7 + x * 0.5));
      for (let y = 0; y < len; y++) {
        let col;
        if (kind === 'us') {
          const inCanton = x < w * 0.45 && y < h * 0.5;
          if (inCanton) col = ((x + y * 2) % 4 === 0 && x > 0 && y > 0) ? NE[9] : R.blue[2];
          else col = ((y / 2 | 0) % 2 === 0) ? R.red[3] : NE[8];
        } else {
          if (y >= len - 3) col = R.red[3];
          else col = NE[8];
          // bear + star
          const cy = (h * 0.5) | 0, cx = (w * 0.5) | 0;
          if (y > cy - 2 && y < cy + 2 && x > cx - 3 && x < cx + 3) col = R.hairBrown[2];
          if (y === cy + 2 && (x === cx - 2 || x === cx + 1)) col = R.hairBrown[2];
          if (y === 3 && x === 1) col = R.red[3];
          if (y > cy + 3 && y < cy + 5 && x > 0 && x < w - 1) col = (y === cy + 4) ? R.green[3] : col;
        }
        // shading by fold
        if (fold < -0.4) col = shade(col, -1);
        else if (fold > 0.6) col = shade(col, 1);
        px(c, x, y + 1, col);
      }
    }
    // fringe at bottom
    for (let x = 0; x < w; x += 1) {
      const len = h - (x > w - 3 ? (x - (w - 3)) * 2 : 0) + Math.round(Math.sin(ph * 0.7 + x * 0.5));
      px(c, x, len + 1, (x & 1) ? GO[4] : GO[3]);
    }
  });
}
const SHADE_MAP = {};
(function buildShade() {
  for (const ramp of Object.values(R)) ramp.forEach((col, i) => {
    if (!SHADE_MAP[col]) SHADE_MAP[col] = [ramp[Math.max(0, i - 1)], ramp[Math.min(ramp.length - 1, i + 1)]];
  });
})();
function shade(col, d) { const m = SHADE_MAP[col]; if (!m) return col; return d < 0 ? m[0] : m[1]; }

function drawPole(c, x, yTop, yBot) {
  fill(c, x, yTop, 1, yBot - yTop, GO[4]); fill(c, x + 1, yTop, 1, yBot - yTop, GO[2]);
  // eagle finial
  fill(c, x - 1, yTop - 3, 4, 2, GO[4]); px(c, x - 2, yTop - 4, GO[3]); px(c, x + 3, yTop - 4, GO[3]);
  px(c, x, yTop - 4, GO[5]); px(c, x + 1, yTop - 5, GO[4]);
  // base
  fill(c, x - 2, yBot - 2, 6, 2, GO[2]); fill(c, x - 2, yBot - 2, 6, 1, GO[4]);
}

/* shared chair (iso) */
function isoChair(c, gx, gy, z, col, backH, faceL) {
  const s = 0.1875;
  box(c, gx - s, gy - s, gx + s, gy + s, z, z + 5, { top: C(col, 2), l: C(col, 1), r: C(col, 0) });
  if (faceL) box(c, gx - s, gy - s - 0.125, gx + s, gy - s, z, z + backH, { top: C(col, 3), l: C(col, 2), r: C(col, 0) });
  else box(c, gx - s - 0.125, gy - s, gx - s, gy + s, z, z + backH, { top: C(col, 3), l: C(col, 1), r: C(col, 2) });
}

function buildWorld() {
  WB = G.makeCanvas(WW, WH);
  WF = G.makeCanvas(WW, WH);
  const b = WB.getContext('2d'), f = WF.getContext('2d');

  /* ---------- floor ---------- */
  topF(b, 0, 0, RW, RD, 0, (gx, gy, x, y) => {
    const lit = litAmt(gx, gy);
    const L1 = lit > 0 && G.bayer(x, y) < lit * 16 ? 1 : 0;
    let idx = 2;
    const fx = gx * 2 - Math.floor(gx * 2), fy = gy * 2 - Math.floor(gy * 2);
    // diamond medallion pattern
    const d = Math.abs(fx - 0.5) + Math.abs(fy - 0.5);
    if (d > 0.46 && d < 0.54) idx = 1;
    if (d < 0.12) idx = 3;
    if ((Math.floor(gx * 2) + Math.floor(gy * 2)) & 1 && d < 0.2 && d > 0.1) idx = 1;
    // aisle runner (red) through the gate
    let ramp = CA;
    if (gx >= 4.25 && gx < 5.25 && gy > L.bar) {
      ramp = R.red; idx = (gx < 4.375 || gx >= 5.125) ? 2 : 1;
      if (gx >= 4.375 && gx < 4.4375 || gx >= 5.0625 && gx < 5.125) idx = 3;
    }
    // well in front of the bench: plain darker carpet
    if (gy < 3.0 && gx < 8.5 && idx === 3) idx = 2;
    // wall AO
    if ((gx < 0.25 || gy < 0.25) && G.bayer(x, y) < 8) idx--;
    if (gx < 0.125 || gy < 0.125) idx--;
    return C(ramp, idx + L1);
  });
  // shadows on the floor (light from the left windows -> shadows toward +gx)
  shadowTop(b, L.def[0] + 0.25, L.def[1] + 0.125, L.def[2] + 0.5, L.def[3] + 0.125, 0.3);
  shadowTop(b, L.pro[0] + 0.25, L.pro[1] + 0.125, L.pro[2] + 0.5, L.pro[3] + 0.125, 0.3);
  shadowTop(b, L.bench[0] + 0.25, L.bench[1], L.bench[2] + 0.5, L.bench[3] + 0.25, 0.3);
  shadowTop(b, L.witness[0] + 0.25, L.witness[1], L.witness[2] + 0.375, L.witness[3] + 0.25, 0.3);
  shadowTop(b, L.clerk[0] + 0.25, L.clerk[1], L.clerk[2] + 0.375, L.clerk[3] + 0.25, 0.3);
  shadowTop(b, L.jury[0], L.jury[3], L.jury[2] + 0.25, L.jury[3] + 0.375, 0.3);
  for (const gy of L.pews) shadowTop(b, 0.5, gy + 0.375, 4.25, gy + 0.75, 0.25), shadowTop(b, 5.75, gy + 0.375, 11.0, gy + 0.75, 0.25);
  shadowTop(b, 0, L.bar, 4.5, L.bar + 0.375, 0.2); shadowTop(b, 5.25, L.bar, RW, L.bar + 0.375, 0.2);

  /* ---------- walls ---------- */
  faceX(b, 0, RW, 0, 0, HW, wallTexR());
  faceY(b, 0, 0, RD, 0, HW, wallTexL());
  // wall caps (cutaway thickness)
  topF(b, -0.25, -0.25, RW, 0, HW, NE[3]);
  topF(b, -0.25, 0, 0, RD, HW, NE[3]);
  faceX(b, -0.25, RW, 0, HW - 1, HW, NE[4]);
  faceY(b, 0, -0.25, RD, HW - 1, HW, NE[2]);
  faceY(b, RW, -0.25, 0, 0, HW, NE[2]);
  faceY(b, RW, -0.25, 0, HW - 1, HW, NE[4]);
  faceX(b, -0.25, 0, RD, 0, HW, NE[3]);
  faceX(b, -0.25, 0, RD, HW - 1, HW, NE[5]);

  // chambers door (right wall)
  const door = G.makeSprite(18, 50, c => {
    fill(c, 0, 0, 18, 50, WD[3]); fill(c, 0, 0, 18, 1, WD[5]); fill(c, 0, 0, 1, 50, WD[4]); fill(c, 17, 0, 1, 50, WD[1]);
    fill(c, 2, 2, 14, 48, WD[2]);
    panelRect(c, 3, 4, 12, 18, WD, 3, 1); panelRect(c, 3, 25, 12, 22, WD, 3, 1);
    fill(c, 13, 27, 2, 2, GO[4]); px(c, 13, 27, GO[5]);
  });
  faceX(b, 0.5, 1.625, 0, 0, 50, door);
  // brass plaque by the door: DEPT 112
  const plaque = G.makeSprite(16, 7, c => {
    fill(c, 0, 0, 16, 7, GO[3]); fill(c, 0, 0, 16, 1, GO[5]); fill(c, 0, 6, 16, 1, GO[1]);
    text3(c, '112', 2, 1, GO[1]);
  });
  faceX(b, 1.75, 2.75, 0, 40, 47, plaque);
  // bench backdrop + seal
  const bd = backdropTex();
  drawSeal(bd.getContext('2d'), bd.width >> 1, 26, 12);
  faceX(b, BD0, BD1, 0, 0, HW - 2, bd);
  // clock face on the right wall (above the jury box)
  const clk = G.makeSprite(14, 14, c => {
    G.ellipse(c, 7, 7, 6, 6, WD[1]); G.ellipse(c, 7, 7, 5, 5, GO[3]); G.ellipse(c, 7, 7, 4, 4, NE[9]);
    px(c, 7, 3, NE[2]); px(c, 7, 11, NE[2]); px(c, 3, 7, NE[2]); px(c, 11, 7, NE[2]);
    px(c, 5, 4, NE[6]); px(c, 9, 4, NE[6]); px(c, 5, 10, NE[6]); px(c, 9, 10, NE[6]);
    px(c, 2, 4, GO[5]); px(c, 3, 3, GO[5]);
  });
  faceX(b, 10.5, 11.375, 0, 56, 70, clk);
  // wall vent (right wall, above clerk) with streaks of dust
  const vent = G.makeSprite(14, 6, c => {
    fill(c, 0, 0, 14, 6, ST[2]); fill(c, 0, 0, 14, 1, ST[5]);
    for (let y = 1; y < 6; y += 2) fill(c, 1, y, 12, 1, NE[3]);
  });
  faceX(b, 1.5, 2.375, 0, 62, 68, vent);
  // framed portrait between clerk and backdrop? -> notice board on the jury side
  const board = G.makeSprite(20, 14, c => {
    fill(c, 0, 0, 20, 14, WD[1]); fill(c, 1, 1, 18, 12, R.stone[3]);
    fill(c, 3, 3, 5, 6, R.paper[4]); fill(c, 9, 2, 6, 5, R.paper[3]); fill(c, 12, 8, 5, 4, R.paper[4]);
    px(c, 5, 3, R.red[3]); px(c, 11, 2, R.blue[4]); px(c, 14, 8, R.red[3]);
    for (let y = 5; y < 9; y += 2) fill(c, 4, y, 3, 1, NE[5]);
  });
  faceX(b, 7.75, 9.0, 0, 36, 50, board);

  /* ---------- back-layer furniture ---------- */
  // judge's dais & high-back chair
  box(b, BD0, 0, BD1, 0.5, 0, 25, { top: WD[2], l: WD[1] });
  box(b, 4.375, 0.0, 4.875, 0.125, 25, 46, { top: R.red[2], l: R.red[1], r: R.red[0], hl: R.red[3] });
  for (let k = 0; k < 4; k++) px(b, ix(4.375, 0.125) + 2 + k * 2, iy(4.375, 0.125, 44) + k + 1, GO[4]);
  // clerk chair, witness chair, reporter chair
  box(b, 1.875, 0.125, 2.375, 0.25, 12, 30, { top: NE[3], l: NE[2], r: NE[1] });
  box(b, 6.625, 0.375, 7.125, 0.5, 16, 34, { top: WD[3], l: WD[2], r: WD[1], hl: WD[4] });
  // jury riser (rear tier) + chairs
  box(b, L.jury[0], 0, L.jury[2], 0.875, 0, 10, { top: WD[2], l: panelStrip(84, 10, 2), r: WD[1] });
  juryRear.forEach(s => {
    box(b, s.gx - 0.25, s.gy - 0.375, s.gx + 0.25, s.gy - 0.25, 10, 28, { top: R.red[2], l: R.red[1], r: R.red[0], hl: R.red[3] });
  });
  juryFront.forEach(s => {
    box(b, s.gx - 0.25, s.gy - 0.375, s.gx + 0.25, s.gy - 0.25, 0, 18, { top: R.red[2], l: R.red[1], r: R.red[0], hl: R.red[3] });
  });
  // jury box right side wall
  box(b, L.jury[2] - 0.125, 0, L.jury[2], L.jury[3], 0, 26, { top: WD[3], r: WD[1], l: WD[2] });
  // reporter chair
  box(b, 6.0, 1.25, 6.5, 1.375, 0, 16, { top: NE[3], l: NE[2], r: NE[1] });
  // counsel chairs
  [[1.875, 3.875], [3.125, 3.875], [8.375, 3.875], [9.0, 3.75]].forEach(([gx, gy], i) => {
    box(b, gx - 0.25, gy - 0.125, gx + 0.25, gy, 0, 16, { top: R.red[2], l: R.red[1], r: R.red[0], hl: R.red[3] });
    box(b, gx - 0.25, gy, gx + 0.25, gy + 0.375, 0, 7, { top: NE[2], l: NE[1], r: NE[0] });
  });
  // bailiff's flag-free corner: water cooler & a ficus
  box(b, 0.25, 5.125, 0.625, 5.5, 0, 14, { top: ST[4], l: ST[3], r: ST[2], hl: ST[5] });
  box(b, 0.3125, 5.1875, 0.5625, 5.4375, 14, 24, { top: R.blue[6], l: R.blue[5], r: R.blue[4] });
  box(b, 0.25, 6.0, 0.625, 6.375, 0, 7, { top: WD[1], l: R.red[2], r: R.red[1] });
  plant(b, ix(0.4375, 6.1875), iy(0.4375, 6.1875, 7));
  // evidence cart near the bailiff
  box(b, 0.25, 2.0, 0.75, 2.5, 0, 12, { top: NE[5], l: NE[3], r: NE[2], hl: NE[6] });
  box(b, 0.3125, 2.0625, 0.6875, 2.4375, 12, 16, { top: R.paper[3], l: R.paper[1], r: R.paper[0] });

  /* ---------- FRONT layer ---------- */
  // clerk desk
  box(f, L.clerk[0], L.clerk[1], L.clerk[2], L.clerk[3], 0, L.clerk[4], { top: WD[4], l: panelStrip(28, 22, 3), r: panelStrip(14, 22, 1), hl: WD[5], hr: WD[3], edge: WD[5] });
  monitor(f, 1.625, 1.0, L.clerk[4]);
  paperStack(f, 2.5, 1.25, L.clerk[4], 3);
  // reporter's stenograph
  box(f, L.reporter[0], L.reporter[1], L.reporter[2], L.reporter[3], 0, L.reporter[4], { top: WD[4], l: panelStrip(12, 12, 3), r: WD[1], hl: WD[5], edge: WD[5] });
  box(f, 6.0, 1.9375, 6.375, 2.25, 12, 14, { top: NE[2], l: NE[1], r: NE[0] });
  // judge's bench (two-step massive front)
  const bnc = L.bench;
  box(f, bnc[0], bnc[1], bnc[2], bnc[3], 0, bnc[4], { top: WD[4], l: benchFront(40, bnc[4]), r: panelStrip(18, bnc[4], 1), hl: WD[6], hr: WD[3], edge: WD[5] });
  box(f, bnc[0] - 0.0625, bnc[1] - 0.0625, bnc[2] + 0.0625, bnc[3] + 0.0625, bnc[4], bnc[4] + 2, { top: WD[5], l: WD[3], r: WD[2], hl: WD[6] });
  // nameplate, gavel block, papers on bench
  paperStack(f, 3.75, 0.875, bnc[4] + 2, 2);
  box(f, 5.25, 1.0, 5.5, 1.25, bnc[4] + 2, bnc[4] + 3, { top: WD[2], l: WD[1], r: WD[0] });
  box(f, 5.3125, 1.0625, 5.4375, 1.1875, bnc[4] + 3, bnc[4] + 5, { top: WD[4], l: WD[3], r: WD[1] });
  box(f, 4.0, 1.5, 5.25, 1.625, bnc[4] + 2, bnc[4] + 5, { top: GO[3], l: GO[4], r: GO[2], hl: GO[5] });
  // seal medallion on bench front
  const medal = G.makeSprite(9, 9, c => drawSeal(c, 4, 4, 4));
  faceX(f, 4.375, 4.9375, bnc[3], 18, 27, medal);
  // witness stand
  const ws = L.witness;
  box(f, ws[0], ws[1], ws[2], ws[3], 0, ws[4], { top: WD[4], l: panelStrip(18, ws[4], 3), r: panelStrip(16, ws[4], 1), hl: WD[6], hr: WD[3], edge: WD[5] });
  // microphone gooseneck
  {
    const mx = ix(6.75, 1.25), my = iy(6.75, 1.25, ws[4]);
    fill(f, mx - 1, my - 1, 3, 1, NE[2]);
    G.line(f, mx, my - 1, mx, my - 6, NE[3]); G.line(f, mx, my - 6, mx - 2, my - 9, NE[4]);
    fill(f, mx - 4, my - 11, 3, 3, NE[2]); px(f, mx - 4, my - 11, NE[5]);
    // water glass
    const gxp = ix(7.125, 1.5), gyp = iy(7.125, 1.5, ws[4]);
    fill(f, gxp, gyp - 4, 2, 4, R.blue[6]); px(f, gxp, gyp - 4, NE[9]); fill(f, gxp, gyp - 1, 2, 1, R.blue[5]);
  }
  // jury box: rear parapet strip + front rail
  faceX(f, L.jury[0], L.jury[2] - 0.125, 0.875, 10, 21, panelStrip(84, 11, 2));
  topF(f, L.jury[0], 0.75, L.jury[2] - 0.125, 0.875, 21, WD[4]);
  faceX(f, L.jury[0], L.jury[2] - 0.125, 0.875, 20, 21, WD[5]);
  box(f, L.jury[0], 2.125, L.jury[2], L.jury[3], 0, 13, { top: WD[4], l: panelStrip(84, 13, 3), r: WD[1], hl: WD[6], edge: WD[5] });
  // jury box left side (low gate)
  box(f, L.jury[0], 0.875, L.jury[0] + 0.125, 2.125, 0, 13, { top: WD[4], l: WD[2], r: WD[1] });

  // lectern
  const lc = L.lectern;
  box(f, lc[0], lc[1], lc[2], lc[3], 0, lc[4], { top: WD[5], l: panelStrip(8, lc[4], 3), r: panelStrip(8, lc[4], 1), hl: WD[6], edge: WD[5] });
  box(f, lc[0] + 0.0625, lc[1] + 0.0625, lc[2] - 0.0625, lc[3] - 0.0625, lc[4], lc[4] + 1, { top: R.paper[4], l: R.paper[2], r: R.paper[1] });
  // counsel tables
  table(f, L.def, 'def');
  table(f, L.pro, 'pro');
  // bar railing with gate
  barRail(f);
  // pews
  for (const gy of L.pews) { pew(f, 0.5, 4.125, gy); pew(f, 5.5, 10.875, gy); }
}

/* strip of raised panels for furniture faces (elevation) */
function panelStrip(w, h, base) {
  return G.makeSprite(w, h, c => {
    fill(c, 0, 0, w, h, C(WD, base - 1));
    fill(c, 0, 0, w, 1, C(WD, base + 1));
    fill(c, 0, h - 2, w, 2, C(WD, base - 2));
    if (h >= 9) for (let p = 1; p + 7 <= w; p += 8) panelRect(c, p + 1, 2, 6, h - 5, WD, base, 1);
  });
}
function benchFront(w, h) {
  return G.makeSprite(w, h, c => {
    fill(c, 0, 0, w, h, WD[2]);
    moulding(c, 0, 0, w, WD, [5, 4, 2, 1]);
    for (let p = 1; p + 9 <= w; p += 10) panelRect(c, p + 1, 6, 8, h - 11, WD, 3, 1);
    moulding(c, 0, h - 4, w, WD, [3, 1, 0, 0]);
  });
}
function monitor(c, gx, gy, z) {
  const x = ix(gx, gy), y = iy(gx, gy, z);
  fill(c, x - 1, y - 2, 4, 2, NE[2]);
  fill(c, x - 4, y - 10, 9, 8, NE[1]); fill(c, x - 3, y - 9, 7, 6, R.blue[3]);
  fill(c, x - 3, y - 9, 7, 1, R.blue[4]); px(c, x - 2, y - 7, R.blue[5]); fill(c, x - 2, y - 5, 4, 1, R.blue[4]);
}
function paperStack(c, gx, gy, z, n) {
  for (let i = 0; i < n; i++) {
    const o = (i & 1) ? 0.0625 : 0;
    box(c, gx + o, gy, gx + 0.5 + o, gy + 0.375, z + i, z + i + 1, { top: i === n - 1 ? R.paper[4] : R.paper[3], l: R.paper[2], r: R.paper[1] });
  }
}
function plant(c, x, y) {
  const leaves = [[0, -14], [-3, -12], [3, -12], [-5, -9], [4, -9], [-2, -8], [2, -10], [0, -6], [-4, -5], [3, -5]];
  leaves.forEach(([dx, dy], i) => {
    fill(c, x + dx - 1, y + dy, 3, 2, R.green[2 + (i % 3)]);
    px(c, x + dx - 1, y + dy, R.green[i % 2 ? 5 : 4]);
  });
  G.line(c, x, y, x, y - 8, WD[1]);
}
function table(c, T, kind) {
  const [x0, y0, x1, y1, z] = T;
  // legs (visible under top)
  for (const [gx, gy] of [[x0 + 0.125, y1 - 0.125], [x1 - 0.125, y1 - 0.125], [x1 - 0.125, y0 + 0.125]])
    box(c, gx - 0.0625, gy - 0.0625, gx + 0.0625, gy + 0.0625, 0, z - 2, { l: WD[1], r: WD[0] });
  // modesty panel
  faceX(c, x0 + 0.125, x1 - 0.125, y1 - 0.25, 3, z - 2, WD[1]);
  box(c, x0, y0, x1, y1, z - 2, z, {
    top: (gx, gy, X, Y) => (((X + Y * 3) % 13 === 0) ? WD[3] : WD[4]),
    l: WD[3], r: WD[2], hl: WD[5], edge: WD[5],
  });
  faceX(c, x0, x1, y1, z - 3, z - 2, WD[1]);
  // items
  if (kind === 'def') {
    paperStack(c, x0 + 1.125, y0 + 0.5, z, 1);
    box(c, x0 + 1.75, y0 + 0.375, x0 + 2.25, y0 + 0.75, z, z + 3, { top: R.blue[3], l: R.blue[2], r: R.blue[1] }); // folder stack
    box(c, x0 + 1.75, y0 + 0.375, x0 + 2.25, y0 + 0.75, z + 3, z + 4, { top: R.paper[4], l: R.paper[2] });
    box(c, x0 + 0.25, y0 + 0.5, x0 + 0.625, y0 + 0.875, z, z + 1, { top: R.paper[3], l: R.paper[1], r: R.paper[0] });
    // legal pad yellow
    box(c, x0 + 0.75, y0 + 0.5, x0 + 1.0625, y0 + 0.875, z, z + 1, { top: GO[5], l: GO[3], r: GO[2] });
    pitcher(c, ix(x0 + 2.5, y0 + 0.5), iy(x0 + 2.5, y0 + 0.5, z));
  } else {
    // neat binders with coloured tabs
    for (let i = 0; i < 3; i++)
      box(c, x0 + 0.25 + i * 0.25, y0 + 0.375, x0 + 0.4375 + i * 0.25, y0 + 0.75, z, z + 5, { top: [R.red[2], NE[2], R.blue[2]][i], l: [R.red[3], NE[3], R.blue[3]][i], r: [R.red[1], NE[1], R.blue[1]][i] });
    // laptop
    box(c, x0 + 1.25, y0 + 0.375, x0 + 1.75, y0 + 0.75, z, z + 1, { top: NE[5], l: NE[4], r: NE[3] });
    faceX(c, x0 + 1.25, x0 + 1.75, y0 + 0.375, z + 1, z + 7, NE[2]);
    faceX(c, x0 + 1.3125, x0 + 1.6875, y0 + 0.375, z + 2, z + 6, R.blue[4]);
    paperStack(c, x0 + 1.875, y0 + 0.5, z, 2);
    pitcher(c, ix(x0 + 0.375, y0 + 0.875), iy(x0 + 0.375, y0 + 0.875, z));
  }
}
function pitcher(c, x, y) {
  fill(c, x - 1, y - 6, 4, 6, R.blue[6]); fill(c, x - 1, y - 6, 4, 1, NE[9]); px(c, x - 1, y - 4, NE[9]);
  fill(c, x + 3, y - 5, 1, 3, R.blue[5]); fill(c, x - 1, y - 3, 4, 3, R.blue[5]); px(c, x + 2, y - 1, R.blue[4]);
  fill(c, x + 5, y - 3, 2, 3, R.blue[6]); px(c, x + 5, y - 3, NE[9]);
}
function barRail(c) {
  const gy = L.bar, z = 14;
  const segs = [[0, 4.25], [5.25, RW]];
  for (const [a, bb] of segs) {
    // balusters
    for (let gx = a + 0.125; gx < bb - 0.05; gx += 0.25) {
      const x = ix(gx, gy), y = iyF(gx, gy);
      fill(c, x, y - z + 2, 2, z - 3, WD[3]); px(c, x, y - z + 2, WD[5]); px(c, x + 1, y - z + 4, WD[1]);
      fill(c, x, y - 4, 2, 1, WD[4]); fill(c, x, y - 7, 2, 1, WD[2]);
    }
    box(c, a, gy - 0.0625, bb, gy + 0.0625, 0, 2, { top: WD[2], l: WD[1], r: WD[0] });
    box(c, a, gy - 0.125, bb, gy + 0.125, z - 2, z, { top: WD[5], l: WD[3], r: WD[2], hl: WD[6] });
    // newel posts
    for (const p of [a, bb - 0.25]) box(c, p, gy - 0.125, p + 0.25, gy + 0.125, 0, z + 3, { top: WD[5], l: WD[3], r: WD[1], hl: WD[6], edge: WD[4] });
  }
  // swing gate (half open)
  box(c, 4.25, gy - 0.0625, 4.625, gy + 0.0625, 2, z - 3, { top: WD[4], l: panelStrip(6, z - 5, 3), r: WD[1] });
  box(c, 4.875, gy - 0.0625, 5.25, gy + 0.0625, 2, z - 3, { top: WD[4], l: panelStrip(6, z - 5, 3), r: WD[1] });
}
function pew(c, a, bb, gy) {
  // seat
  box(c, a, gy - 0.125, bb, gy + 0.25, 4, 6, { top: WD[4], l: WD[2], r: WD[1], hl: WD[5] });
  // end panels + backrest (toward the viewer: +gy side)
  box(c, a, gy + 0.25, bb, gy + 0.375, 0, 12, { top: WD[4], l: panelStrip(Math.round((bb - a) * 16), 12, 3), r: WD[1], hl: WD[6] });
  box(c, bb - 0.125, gy - 0.25, bb, gy + 0.375, 0, 13, { top: WD[4], l: WD[2], r: panelStrip(10, 13, 2), edge: WD[5] });
}

/* ---- animated world bits ---- */
const motes = [];
(function initMotes() {
  const rnd = G.rng(77);
  WINS.forEach((w, wi) => {
    for (let i = 0; i < 14; i++) motes.push({ wi, gy: w[0] + rnd() * (w[1] - w[0]), z: WZ0 + rnd() * (WZ1 - WZ0), s: rnd(), sp: 0.01 + rnd() * 0.02, ph: rnd() * 6.28 });
  });
})();
let SHAFT = null;
function buildShafts() {
  SHAFT = G.makeCanvas(WW, WH);
  const c = SHAFT.getContext('2d');
  for (const w of WINS) {
    // hull of window and floor patch
    const pts = [];
    for (const gy of [w[0], w[1]]) for (const z of [WZ0, WZ1]) {
      pts.push([ix(0, gy), iy(0, gy, z)]);
      pts.push([ix(z * LK, gy + z * LM), iyF(z * LK, gy + z * LM)]);
    }
    const hull = convexHull(pts);
    // soft dithered edges: draw shrunken core solid, outer with dither
    const cx = hull.reduce((s, p) => s + p[0], 0) / hull.length, cy = hull.reduce((s, p) => s + p[1], 0) / hull.length;
    const tmp = G.makeCanvas(WW, WH), t = tmp.getContext('2d');
    G.poly(t, hull, P.glow);
    t.globalCompositeOperation = 'destination-out';
    // carve dithered border
    const inner = hull.map(p => [cx + (p[0] - cx) * 0.86, cy + (p[1] - cy) * 0.9]);
    const mask = G.makeCanvas(WW, WH), m = mask.getContext('2d');
    G.dither(m, 0, 0, WW, WH, '#000', 9);
    m.globalCompositeOperation = 'destination-out';
    G.poly(m, inner, '#000');
    t.drawImage(mask, 0, 0);
    c.drawImage(tmp, 0, 0);
  }
}
function convexHull(pts) {
  pts = pts.slice().sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const cr = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const lo = [], up = [];
  for (const p of pts) { while (lo.length >= 2 && cr(lo[lo.length - 2], lo[lo.length - 1], p) <= 0) lo.pop(); lo.push(p); }
  for (let i = pts.length - 1; i >= 0; i--) { const p = pts[i]; while (up.length >= 2 && cr(up[up.length - 2], up[up.length - 1], p) <= 0) up.pop(); up.push(p); }
  up.pop(); lo.pop(); return lo.concat(up);
}
function drawClockHands(c, t, x0, y0, rH, rM, colH, colM) {
  // generic analogue hands at centre x0,y0 (screen), with optional iso shear (sh=0.5 for right wall)
  const a = clockHands(t);
  const hand = (ang, r, col, sh) => {
    for (let k = 1; k <= r; k++) {
      const u = Math.round(Math.sin(ang) * k), v = Math.round(-Math.cos(ang) * k);
      px(c, x0 + u, y0 + v + (sh ? Math.floor(u / 2) : 0), col);
    }
  };
  return { a, hand };
}
const FANS = [[5, 8.5, 140], [10.5, 9.5, 186]];
function drawFan(c, x, y, t, ph) {
  // downrod
  fill(c, x, 0, 1, y - 3, NE[3]); px(c, x + 1, ((t * 7 + ph * 9) | 0) % Math.max(1, y - 4), NE[4]);
  const ang = t * 2.4 + ph;
  // blades (iso ellipse), 4 blades of walnut with brass arms
  const blades = [];
  for (let i = 0; i < 4; i++) {
    const a = ang + i * Math.PI / 2;
    const ca = Math.cos(a), sa = Math.sin(a);
    blades.push({ a, d: ca + sa, ca, sa });
  }
  blades.sort((p, q) => p.d - q.d);
  const drawBlade = bl => {
    for (let k = 3; k <= 13; k++) {
      const bx = x + Math.round((bl.ca - bl.sa) * k * 1.4), by = y + Math.round((bl.ca + bl.sa) * k * 0.7);
      const w = k < 5 ? 1 : 2;
      fill(c, bx, by, w, 1, k < 5 ? GO[3] : (bl.d > 0 ? WD[3] : WD[2]));
      if (k > 5) px(c, bx, by + 1, WD[1]);
    }
  };
  blades.filter(bl => bl.d <= 0).forEach(drawBlade);
  // motor housing + light kit
  fill(c, x - 3, y - 3, 7, 4, GO[2]); fill(c, x - 3, y - 3, 7, 1, GO[4]); fill(c, x - 2, y - 4, 5, 1, GO[3]);
  fill(c, x - 2, y + 1, 5, 3, ST[5]); fill(c, x - 1, y + 4, 3, 1, P.glow); px(c, x - 2, y + 1, NE[9]);
  blades.filter(bl => bl.d > 0).forEach(drawBlade);
  // warm glow
  c.globalAlpha = 0.2; G.dither(c, x - 6, y + 2, 13, 6, P.glow, 6); c.globalAlpha = 1;
}

function drawWorld(ctx, layer, t) {
  if (!WB) build();
  t = t || 0;
  if (layer === 'back') {
    ctx.drawImage(WB, 0, 0);
    // flags (US left of the bench backdrop, California right)
    const fi = Math.floor(t * 1.6) % 4, fj = (fi + 2) % 4;
    const lpx = ix(BD0 - 0.125, 0.25), lpy = iyF(BD0 - 0.125, 0.25);
    drawPole(ctx, lpx, lpy - 64, lpy);
    ctx.drawImage(flagFrames.us[fi], lpx + 2, lpy - 62);
    const rpx = ix(BD1 + 0.125, 0.25), rpy = iyF(BD1 + 0.125, 0.25);
    drawPole(ctx, rpx, rpy - 64, rpy);
    G.blit(ctx, flagFrames.ca[fj], rpx - flagFrames.ca[fj].width, rpy - 62, true);
    // clock hands on the right wall (sheared)
    const cxp = ix(10.9375, 0), cyp = iyF(10.9375, 0) - 63;
    const a = clockHands(t);
    const hand = (ang, r, col) => {
      for (let k = 1; k <= r; k++) {
        const u = Math.round(Math.sin(ang) * k), v = Math.round(-Math.cos(ang) * k);
        px(ctx, cxp + u, cyp + v + (u >> 1), col);
      }
    };
    hand(a.h, 2, NE[1]); hand(a.m, 3, NE[1]); hand(a.s, 3, R.red[3]);
    px(ctx, cxp, cyp, GO[2]);
    // monitor flicker on clerk desk
    if (Math.sin(t * 0.7) > 0.95) px(ctx, ix(1.625, 1.0) - 1, iy(1.625, 1.0, L.clerk[4]) - 7, R.blue[6]);
  } else {
    ctx.drawImage(WF, 0, 0);
    // fluttering paper near the wall vent (on clerk desk)
    const fl = Math.floor(t * 9) % 6;
    const ppx = ix(2.75, 1.25), ppy = iy(2.75, 1.25, L.clerk[4] + 3);
    const lift = [0, 1, 2, 1, 0, 0][fl];
    G.poly(ctx, [[ppx - 4, ppy - 1], [ppx + 2, ppy - 4 - lift], [ppx + 5, ppy - 2 - lift * 2], [ppx - 1, ppy + 1]], R.paper[4]);
    px(ctx, ppx + 4, ppy - 3 - lift * 2, R.paper[2]);
    // laptop screen on prosecution table: cursor blink
    if ((t * 2 | 0) % 2) px(ctx, ix(L.pro[0] + 1.4375, L.pro[1] + 0.375) , iy(L.pro[0] + 1.4375, L.pro[1] + 0.375, L.pro[4] + 4), R.blue[6]);
    // light shafts (breathing intensity)
    ctx.globalAlpha = 0.13 + 0.035 * Math.sin(t * 0.37) + 0.015 * Math.sin(t * 1.3);
    ctx.drawImage(SHAFT, 0, 0);
    ctx.globalAlpha = 1;
    // dust motes
    for (const m of motes) {
      const w = WINS[m.wi];
      const s = (m.s + t * m.sp) % 1;
      const gy = m.gy + Math.sin(t * 0.4 + m.ph) * 0.15;
      const z0 = m.z + Math.sin(t * 0.3 + m.ph * 2) * 3;
      const gx = s * z0 * LK, gyy = gy + s * z0 * LM, z = z0 * (1 - s);
      if (gyy < w[0] - 0.2 + s * z0 * LM || gyy > w[1] + 0.2 + s * z0 * LM) continue;
      const tw = 0.5 + 0.5 * Math.sin(t * 3 + m.ph * 5);
      ctx.globalAlpha = 0.25 + 0.25 * tw;
      px(ctx, ix(gx, gyy), iy(gx, gyy, z), P.glow);
    }
    ctx.globalAlpha = 1;
    // ceiling fans with light kits, a moth circling one
    FANS.forEach(([gx, gy, z], i) => drawFan(ctx, ix(gx, gy), iy(gx, gy, z), t, i * 1.7));
    const fx = ix(FANS[0][0], FANS[0][1]), fy = iy(FANS[0][0], FANS[0][1], FANS[0][2]) + 7;
    const ma = t * 3.1;
    const mx = fx + Math.round(Math.cos(ma) * 6 + Math.sin(t * 7.3) * 1.5), my = fy + Math.round(Math.sin(ma * 1.3) * 3 + 2);
    px(ctx, mx, my, ST[5]); if ((t * 20 | 0) & 1) px(ctx, mx + 1, my, ST[3]); else px(ctx, mx - 1, my - 1, ST[3]);
  }
}

/* ================================================================
   CLOSE-UP SHOTS (384x216)  — defined below
   ================================================================ */
const SHOTS = {};
const shots = {
  judge: { anchor: { x: 192, y: 182 }, flip: false },
  witness: { anchor: { x: 212, y: 182 }, flip: false },
  defense: { anchor: { x: 118, y: 184 }, flip: true },
  prosecution: { anchor: { x: 266, y: 184 }, flip: false },
  jury: { anchor: { x: 192, y: 186 }, flip: false, extras: [] },
  visit: { anchor: { x: 196, y: 184 }, flip: false },
  defendant: { anchor: { x: 236, y: 186 }, flip: false },
};

/* ================================================================
   BUILD
   ================================================================ */
let built = false;
function build() {
  if (built) return; built = true;
  for (let i = 0; i < 4; i++) {
    flagFrames.us.push(makeFlag('us', 11, 22, i * Math.PI / 2));
    flagFrames.ca.push(makeFlag('ca', 11, 22, i * Math.PI / 2 + 1));
  }
  buildWorld();
  buildShafts();
  if (G.Env._buildShots) G.Env._buildShots();
}

G.Env = {
  world: { w: WW, h: WH },
  spots,
  cams: {
    wide: { x: 280, y: 160, z: 1 },
    judge: { x: 318, y: 112, z: 2 },
    witness: { x: 350, y: 132, z: 2 },
    defense: { x: 236, y: 140, z: 2 },
    prosecution: { x: 318, y: 186, z: 2 },
    jury: { x: 404, y: 170, z: 2 },
  },
  shots,
  drawWorld,
  drawShot(ctx, id, layer, t) {
    if (!built) build();
    const s = SHOTS[id];
    if (s) s(ctx, layer, t || 0);
  },
  drawExterior(ctx, t) {
    if (!built) build();
    if (G.Env._exterior) G.Env._exterior(ctx, t || 0);
  },
  build,
  _SHOTS: SHOTS,
  _lib: { C, hash, h2, fill, text3, text3W, panelCol, panelRect, moulding, drawSeal, shade, makeFlag, clockHands, F3, convexHull },
};
})();

/* =====================================================================
   CLOSE-UP SHOTS & EXTERIOR
   ===================================================================== */
(function () {
'use strict';
const G = window.G, E = G.Env, Lb = E._lib;
const R = G.RAMP, P = G.PAL;
const WD = R.wood, ST = R.stone, NE = R.neutral, GO = R.gold;
const { C, h2, fill, text3, text3W, panelCol, panelRect, moulding, drawSeal, shade } = Lb;
const px = G.px;
const SW = 384, SH = 216;
const SHOTS = E._SHOTS;

/* per-column trapezoid (vertical edges at xa,xb). fn(x,y,u,v) -> colour. k: far/near depth ratio for perspective-correct u */
function quad(c, xa, xb, ta, ba, tb, bb, fn, k) {
  k = k || 1;
  for (let x = xa; x < xb; x++) {
    const s = (x + 0.5 - xa) / (xb - xa);
    const u = (s / k) / ((1 - s) + s / k);
    const top = Math.round(ta + (tb - ta) * s), bot = Math.round(ba + (bb - ba) * s);
    if (typeof fn === 'string') { fill(c, x, top, 1, bot - top, fn); continue; }
    for (let y = top; y < bot; y++) {
      const col = fn(x, y, u, (y - top) / Math.max(1, bot - top), top, bot);
      if (col) px(c, x, y, col);
    }
  }
}
/* inverse: screen x of parameter u on such a wall */
function quadX(xa, xb, u, k) { k = k || 1; const s = u * k / ((1 - u) + u * k); return Math.round(xa + s * (xb - xa)); }

/* walnut wall with raised panels drawn in perspective: columns of panels between u-cuts, rows between v-cuts */
function panelWall(c, xa, xb, ta, ba, tb, bb, k, ucuts, vcuts, base, bev, ramp) {
  ramp = ramp || WD;
  const xs = ucuts.map(u => quadX(xa, xb, u, k));
  quad(c, xa, xb, ta, ba, tb, bb, (x, y, u, v, top, bot) => {
    for (let i = 0; i + 1 < ucuts.length; i += 2) {
      const xl = xs[i], xr = xs[i + 1];
      if (x < xl || x > xr) continue;
      for (let j = 0; j + 1 < vcuts.length; j += 2) {
        const yt = Math.round(top + vcuts[j] * (bot - top)), yb = Math.round(top + vcuts[j + 1] * (bot - top));
        if (y < yt || y > yb) continue;
        return panelCol(x - xl, xr - x, y - yt, yb - y, ramp, base, bev, x, y);
      }
    }
    return C(ramp, base - 1);
  }, k);
}
function plaster(c, x0, y0, w, h, base, seed) {
  for (let y = y0; y < y0 + h; y++) for (let x = x0; x < x0 + w; x++) {
    const n = h2(x + (seed || 0), y);
    px(c, x, y, n < 0.05 ? C(ST, base - 1) : n > 0.985 ? C(ST, base + 1) : ST[base]);
  }
}
function vignette(c, lv) {
  for (let i = 0; i < 4; i++) {
    G.dither(c, 0, 0, 14 - i * 3, SH, P.black, (lv || 8) - i * 2);
    G.dither(c, SW - 14 + i * 3, 0, 14 - i * 3, SH, P.black, (lv || 8) - i * 2);
  }
}
function beam(c, pts, a) { // light shaft polygon with dithered core
  const t = G.makeCanvas(SW, SH), x = t.getContext('2d');
  G.poly(x, pts, P.glow);
  const cx = pts.reduce((s, p) => s + p[0], 0) / pts.length, cy = pts.reduce((s, p) => s + p[1], 0) / pts.length;
  const m = G.makeCanvas(SW, SH), mx = m.getContext('2d');
  G.dither(mx, 0, 0, SW, SH, '#000', 8);
  mx.globalCompositeOperation = 'destination-out';
  G.poly(mx, pts.map(p => [cx + (p[0] - cx) * 0.8, cy + (p[1] - cy) * 0.95]), '#000');
  x.globalCompositeOperation = 'destination-out'; x.drawImage(m, 0, 0);
  return t;
}
function makeMotes(seed, n, area) {
  const r = G.rng(seed), a = [];
  for (let i = 0; i < n; i++) a.push({ x: r(), y: r(), sp: 0.3 + r() * 0.7, ph: r() * 6.28, area });
  return a;
}
function drawMotes(c, motes, t, inside) {
  for (const m of motes) {
    const [x0, y0, w, h] = m.area;
    const x = x0 + ((m.x * w + t * 2.5 * m.sp + Math.sin(t * 0.5 + m.ph) * 4) % w + w) % w;
    const y = y0 + ((m.y * h + t * 1.5 * m.sp + Math.sin(t * 0.3 + m.ph) * 3) % h + h) % h;
    if (inside && !inside(x, y)) continue;
    c.globalAlpha = 0.3 + 0.2 * Math.sin(t * 2 + m.ph * 3);
    px(c, x | 0, y | 0, P.glow);
    if (m.sp > 0.9) px(c, (x | 0) + 1, y | 0, P.glow);
  }
  c.globalAlpha = 1;
}
function inPoly(pts, x, y) {
  let ins = false;
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const [xi, yi] = pts[i], [xj, yj] = pts[j];
    if (((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi)) ins = !ins;
  }
  return ins;
}

/* big draped flag (hanging along a pole) */
function bigFlag(kind, w, h, ph) {
  return G.makeSprite(w, h + 6, c => {
    for (let x = 0; x < w; x++) {
      const f = Math.sin(x * 0.42 + ph) + 0.5 * Math.sin(x * 0.9 - ph * 1.3);
      const sag = Math.round(Math.sin(x / w * Math.PI) * 2);
      const len = h - Math.round(x * x / (w * w) * h * 0.18) + Math.round(Math.sin(ph + x * 0.3) * 1.5);
      for (let y = 0; y < len; y++) {
        let col;
        const yy = y - sag * (1 - y / len);
        if (kind === 'us') {
          if (x < w * 0.5 && yy < h * 0.42) col = ((x % 4 === 1) && (yy % 4 === 1 + ((x >> 2) & 1) * 2)) ? NE[9] : R.blue[2];
          else col = (Math.floor(yy / (h / 13)) % 2 === 0) ? R.red[3] : NE[8];
        } else {
          col = NE[8];
          if (yy > len - h * 0.12) col = R.red[3];
          const cx = w * 0.5, cy = h * 0.48;
          const dx = x - cx, dy = yy - cy;
          if (Math.abs(dx) < w * 0.28 && dy > -h * 0.06 && dy < h * 0.05) col = R.hairBrown[2];
          if (Math.abs(dx + w * 0.22) < 2 && dy > -h * 0.1 && dy < -h * 0.03) col = R.hairBrown[2];
          if ((Math.abs(dx + w * 0.15) < 1.5 || Math.abs(dx - w * 0.15) < 1.5) && dy >= h * 0.05 && dy < h * 0.1) col = R.hairBrown[1];
          if (dy > h * 0.11 && dy < h * 0.14 && Math.abs(dx) < w * 0.4) col = R.green[3];
          if (Math.abs(x - w * 0.15) < 2 && Math.abs(yy - h * 0.12) < 2 && (Math.abs(x - w * 0.15) + Math.abs(yy - h * 0.12)) < 2.5) col = R.red[3];
        }
        if (f < -0.7) col = shade(shade(col, -1), -1); else if (f < -0.1) col = shade(col, -1);
        else if (f > 1.0) col = shade(col, 1);
        px(c, x, y, col);
      }
      px(c, x, len, (x & 1) ? GO[4] : GO[2]); px(c, x, len + 1, (x & 2) ? GO[3] : GO[1]);
    }
  });
}
function bigPole(c, x, y0, y1) {
  fill(c, x, y0, 3, y1 - y0, GO[3]); fill(c, x, y0, 1, y1 - y0, GO[5]); fill(c, x + 2, y0, 1, y1 - y0, GO[1]);
  // eagle finial
  fill(c, x - 1, y0 - 3, 5, 3, GO[4]); fill(c, x - 1, y0 - 1, 5, 1, GO[2]);
  G.ellipse(c, x + 1, y0 - 6, 2, 2, GO[4]);
  G.line(c, x + 1, y0 - 7, x - 6, y0 - 13, GO[3]); G.line(c, x + 1, y0 - 8, x - 5, y0 - 15, GO[4]);
  G.line(c, x + 2, y0 - 7, x + 9, y0 - 13, GO[3]); G.line(c, x + 2, y0 - 8, x + 8, y0 - 15, GO[4]);
  px(c, x + 1, y0 - 9, GO[5]);
}

/* ---------------- background people (sprites) ---------------- */
const SKINS = [R.skinL, R.skinM, R.skinD];
const HAIRS = [R.hairBrown, R.hairBlack, R.hairBlond, R.hairRed, R.hairGrey];
const CLOTH = [R.blue, R.red, R.green, R.purple, R.teal, NE, R.stone, R.wood, R.gold];
/* draw a person (head+shoulders) into a sprite. o: {s(scale), skin, hair, style, cloth, glasses, dim, look} ; frame: 0 normal, 1 blink, 2 turned */
function personSprite(o, frame) {
  const s = o.s || 1;
  const W = Math.round(30 * s), H = Math.round(40 * s);
  const dim = o.dim || 0;
  const sk = i => C(o.skin, i - dim), hr = i => C(o.hair, i - dim), cl = i => C(o.cloth, i - dim);
  return G.makeSprite(W, H, c => {
    const cx = (W >> 1), hy = Math.round(13 * s);
    const rx = Math.max(3, Math.round(5 * s * (o.wide || 1))), ry = Math.max(4, Math.round(6 * s));
    const turn = frame === 2 ? (o.look || -1) : 0;
    // shoulders / torso
    const sw = Math.round(13 * s * (o.bulk || 1)), ty = hy + ry + Math.round(2 * s);
    for (let y = ty; y < H; y++) {
      const k = y - ty, half = Math.min(sw, Math.round(sw * 0.55 + k * 2.2));
      for (let x = -half; x <= half; x++) {
        let col = cl(3);
        if (x < -half + 2 + k * 0.1) col = cl(4); else if (x > half - 3) col = cl(2);
        if (y === ty) col = cl(4);
        px(c, cx + x, y, col);
      }
    }
    // collar / shirt V
    if (o.collar) { for (let k = 0; k < Math.round(5 * s); k++) { px(c, cx - 1 - (k >> 1), ty + k, o.collar); px(c, cx + (k >> 1), ty + k, o.collar); } }
    if (o.tie) fill(c, cx, ty + 1, 1, Math.round(7 * s), o.tie);
    // neck
    fill(c, cx - Math.round(2 * s), hy + ry - 2, Math.round(4 * s) + 1, Math.round(4 * s), sk(1));
    // long hair behind
    if (o.style === 'long' || o.style === 'bob') G.ellipse(c, cx, hy + Math.round(2 * s), rx + 2, ry + (o.style === 'long' ? Math.round(5 * s) : 1), hr(2));
    if (o.style === 'curly') G.ellipse(c, cx, hy - 1, rx + 3, ry + 1, hr(2));
    // head
    G.ellipse(c, cx + turn, hy, rx, ry, sk(2));
    for (let y = -ry; y <= ry; y++) { // lit left side, shade right
      const wv = Math.round(rx * Math.sqrt(Math.max(0, 1 - y * y / (ry * ry + 0.01))));
      px(c, cx + turn - wv, hy + y, sk(3)); if (wv > 1) px(c, cx + turn - wv + 1, hy + y, sk(3));
      px(c, cx + turn + wv, hy + y, sk(1));
    }
    // ear
    px(c, cx + turn + rx, hy, sk(1)); px(c, cx + turn + rx, hy + 1, sk(1));
    // hair styles
    const hx = cx + turn;
    if (o.style !== 'bald') {
      for (let y = -ry - 1; y <= -Math.round(ry * 0.15); y++) {
        const wv = Math.round((rx + 1) * Math.sqrt(Math.max(0, 1 - y * y / ((ry + 1) * (ry + 1)))));
        for (let x = -wv; x <= wv; x++) {
          // hairline: curved, fringe dips on the left (side part)
          const edge = -Math.round(ry * 0.15) - Math.round(((x + wv) / (2 * wv + 1)) * ry * 0.45) + ((x & 1) ? 0 : 1);
          if (y > edge && Math.abs(x) < wv - 1) continue;
          const lit = (x + y * 0.5) < -wv * 0.3;
          px(c, hx + x, hy + y, lit ? hr(4) : (x > wv / 2 ? hr(1) : ((x + y) % 3 === 0 ? hr(2) : hr(3))));
        }
      }
      if (o.style === 'bob' || o.style === 'long') { fill(c, hx - rx - 1, hy - 2, 2, ry + 2, hr(3)); fill(c, hx + rx - 1, hy - 2, 2, ry + 2, hr(1)); }
      if (o.style === 'bun') { G.ellipse(c, hx, hy - ry - 2, 2, 2, hr(3)); px(c, hx - 1, hy - ry - 3, hr(4)); }
      if (o.style === 'cap') { fill(c, hx - rx - 1, hy - ry, rx * 2 + 3, Math.round(3 * s), o.capCol || R.red[3]); fill(c, hx - rx - 4, hy - ry + Math.round(3 * s) - 1, rx + 3, 1, o.capCol2 || R.red[2]); }
      if (o.style === 'curly') for (let k = 0; k < 6; k++) px(c, hx - rx + k * 2, hy - ry - 1 + (k & 1), hr(4));
      // side part fringe
      px(c, hx - rx + 1, hy - Math.round(ry * 0.2), hr(2));
    } else { px(c, hx - 2, hy - ry + 1, sk(4)); px(c, hx - 1, hy - ry + 1, sk(4)); fill(c, hx - rx, hy - 1, 1, 3, C(R.hairGrey, 2 - dim)); fill(c, hx + rx, hy - 1, 1, 3, C(R.hairGrey, 1 - dim)); }
    // face: eyes looking left (or turned)
    const ey = hy + Math.round(ry * 0.1), lk = (o.look || -1);
    const ex1 = hx - Math.round(rx * 0.45) + (frame === 2 ? lk : 0) - 1, ex2 = hx + Math.round(rx * 0.35) + (frame === 2 ? lk : 0) - 1;
    if (frame === 1) { fill(c, ex1, ey, 2, 1, sk(1)); fill(c, ex2, ey, 2, 1, sk(1)); }
    else { px(c, ex1, ey, C(NE, 1)); px(c, ex2, ey, C(NE, 1)); if (s > 1.2) { px(c, ex1 + 1, ey, NE[8 - dim * 2]); px(c, ex2 + 1, ey, NE[8 - dim * 2]); } }
    px(c, ex1, ey - 2, hr(1)); px(c, ex2 + 1, ey - 2, hr(1)); if (s > 1.2) { px(c, ex1 + 1, ey - 2, hr(1)); px(c, ex2, ey - 2, hr(1)); } // brows
    px(c, ex1 - 1, ey + 2, sk(3)); // cheek light
    if (o.glasses) { G.frame(c, ex1 - 1, ey - 1, 4, 3, o.glasses); G.frame(c, ex2 - 1, ey - 1, 4, 3, o.glasses); }
    px(c, hx - 1 + (frame === 2 ? lk : 0), ey + Math.round(ry * 0.35), sk(1)); // nose
    fill(c, hx - 1 + (frame === 2 ? lk : 0), ey + Math.round(ry * 0.6), 2, 1, sk(0)); // mouth
    if (o.beard) for (let y = 0; y < 3; y++) fill(c, hx - rx + 1 + y, ey + Math.round(ry * 0.45) + y, rx * 2 - 1 - y * 2, 1, hr(2));
  });
}
function randPerson(r, s, dim) {
  const style = ['short', 'bob', 'bald', 'bun', 'long', 'curly', 'short', 'cap', 'long', 'short'][Math.floor(r() * 10)];
  return {
    s, dim, style,
    skin: SKINS[Math.floor(r() * 3)],
    hair: HAIRS[Math.floor(r() * 5)],
    cloth: CLOTH[Math.floor(r() * CLOTH.length)],
    glasses: r() < 0.3 ? NE[2] : null,
    collar: r() < 0.5 ? NE[8] : null,
    tie: r() < 0.25 ? R.red[2] : null,
    bulk: 0.85 + r() * 0.35, wide: 0.9 + r() * 0.25,
    look: r() < 0.5 ? -1 : 1, beard: r() < 0.15,
    capCol: R.blue[3], capCol2: R.blue[2],
  };
}
/* crowd of animated background people: each has frames, whisper pairs, breathing */
function crowd(list) {
  return list.map((p, i) => ({ ...p, fr: [0, 1, 2].map(f => personSprite(p.o, f)), i }));
}
function drawCrowd(c, cr, t, clipFn) {
  for (const p of cr) {
    const ph = p.i * 1.37 + p.x * 0.05;
    const breath = Math.sin(t * 2.2 + ph) > 0.6 ? 1 : 0;
    const blink = ((t + ph) % 3.7) < 0.13;
    // whisper window: lean toward neighbour for ~1.6s every ~7s
    const wcyc = (t + ph * 3) % 7.3;
    const whisper = p.whisper && wcyc < 1.6;
    const turn = whisper || ((t * 0.6 + ph) % 9) < 1.2;
    const fr = blink ? 1 : turn ? 2 : 0;
    const lean = whisper ? (p.o.look || -1) * (wcyc < 0.25 || wcyc > 1.35 ? 1 : 2) : 0;
    const shift = Math.round(Math.sin(t * 0.23 + ph * 2) * 0.6);
    G.blit(c, p.fr[fr], p.x + lean + shift - (p.fr[0].width >> 1), p.y - p.fr[0].height + breath + (whisper ? 1 : 0));
  }
}

/* ---------------- common props ---------------- */
function legalPad(c, pts, lines, seed) {
  // pts: quad [tl,tr,br,bl]
  G.poly(c, pts, GO[5]);
  const [tl, tr, br, bl] = pts;
  // binding strip
  G.poly(c, [tl, tr, [tr[0] + (br[0] - tr[0]) * 0.12, tr[1] + (br[1] - tr[1]) * 0.12], [tl[0] + (bl[0] - tl[0]) * 0.12, tl[1] + (bl[1] - tl[1]) * 0.12]], R.red[2]);
  const r = G.rng(seed || 5);
  for (let i = 0; i < lines; i++) {
    const f = 0.2 + i * (0.75 / lines);
    const ax = tl[0] + (bl[0] - tl[0]) * f, ay = tl[1] + (bl[1] - tl[1]) * f;
    const bx = tr[0] + (br[0] - tr[0]) * f, by = tr[1] + (br[1] - tr[1]) * f;
    // rule
    G.line(c, Math.round(ax), Math.round(ay), Math.round(bx), Math.round(by), GO[4]);
    // handwriting squiggle above rule
    const n = Math.floor(Math.hypot(bx - ax, by - ay));
    let x = 2, end = n * (0.5 + r() * 0.45);
    while (x < end) {
      const wl = 3 + Math.floor(r() * 6);
      for (let k = 0; k < wl && x < end; k++, x++) {
        const qx = ax + (bx - ax) * x / n, qy = ay + (by - ay) * x / n;
        px(c, Math.round(qx), Math.round(qy) - 1 - ((k + Math.floor(r() * 2)) % 2), P.ink);
      }
      x += 2;
    }
  }
}
function pen(c, x, y, len, col) {
  for (let i = 0; i < len; i++) { px(c, x + i, y - (i >> 2), col || P.inkDark); px(c, x + i, y - (i >> 2) + 1, NE[1]); }
  px(c, x + len - 1, y - ((len - 1) >> 2), GO[4]); px(c, x, y, NE[6]);
}
function glass(c, x, y, h, full) {
  fill(c, x, y - h, 7, h, R.blue[5]);
  fill(c, x, y - h, 1, h, NE[8]); fill(c, x + 6, y - h, 1, h, R.blue[4]);
  if (full) { fill(c, x + 1, y - Math.round(h * 0.6), 5, Math.round(h * 0.6) - 1, R.blue[6]); fill(c, x + 1, y - Math.round(h * 0.6), 5, 1, NE[9]); }
  fill(c, x, y - h, 7, 1, NE[8]); fill(c, x, y - 1, 7, 1, R.blue[4]); px(c, x + 2, y - h + 2, NE[9]); px(c, x + 2, y - h + 3, NE[9]);
}
function pitcherBig(c, x, y) {
  // stainless steel water pitcher
  for (let j = 0; j < 22; j++) {
    const w = 6 + Math.round(Math.sin(j / 22 * Math.PI) * 2) + (j > 18 ? -1 : 0);
    for (let i = -w; i <= w; i++) {
      let col = NE[6];
      if (i < -w + 2) col = NE[8]; else if (i < -w + 4) col = NE[7]; else if (i > w - 2) col = NE[4]; else if (i > w - 5) col = NE[5];
      if (i === -w + 5 && j > 3 && j < 18) col = NE[9];
      px(c, x + i, y - 22 + j, col);
    }
  }
  fill(c, x - 6, y - 23, 12, 2, NE[7]); px(c, x - 8, y - 23, NE[7]); px(c, x - 9, y - 24, NE[6]); // spout
  // handle
  fill(c, x + 8, y - 19, 3, 1, NE[5]); fill(c, x + 10, y - 19, 1, 12, NE[4]); fill(c, x + 8, y - 8, 3, 1, NE[4]);
  fill(c, x - 6, y, 13, 1, NE[3]);
}
function folderStack(c, x, y, n, seed) {
  const r = G.rng(seed);
  const cols = [R.paper, R.stone, GO, R.blue, R.red];
  for (let i = 0; i < n; i++) {
    const dx = Math.round(r() * 4 - 2), ramp = i % 3 === 2 ? cols[Math.floor(r() * 5)] : R.paper;
    const yy = y - i * 3;
    G.poly(c, [[x + dx, yy - 3], [x + 46 + dx, yy - 3], [x + 52 + dx, yy], [x + 6 + dx, yy]], C(ramp, 3));
    fill(c, x + 6 + dx, yy, 47, 2, C(ramp, 1)); fill(c, x + 6 + dx, yy, 47, 1, C(ramp, 2));
    if (r() < 0.6) fill(c, x + 20 + dx + Math.floor(r() * 20), yy - 4, 6, 1, [R.red[3], R.blue[4], R.green[4], GO[4]][i % 4]); // tab
    if (r() < 0.4) fill(c, x + 8 + dx, yy + 1, 45, 1, R.paper[4]); // sheets peeking
  }
  // rubber band / clip
  fill(c, x + 30, y - n * 3 - 2, 2, n * 3 + 3, R.red[3]);
}
function laptopBack(c, x, y) {
  // lid seen from behind (screen faces the speaker)
  G.poly(c, [[x, y - 28], [x + 44, y - 30], [x + 46, y], [x + 2, y]], NE[5]);
  G.poly(c, [[x + 1, y - 27], [x + 43, y - 29], [x + 44, y - 2], [x + 3, y - 2]], NE[6]);
  fill(c, x + 2, y - 2, 44, 2, NE[3]);
  G.line(c, x + 1, y - 27, x + 43, y - 29, NE[8]);
  G.ellipse(c, x + 23, y - 15, 3, 3, NE[7]); px(c, x + 22, y - 16, NE[9]);
  fill(c, x - 4, y, 54, 3, NE[4]); fill(c, x - 4, y, 54, 1, NE[7]);
}
function shotDesk(c, y0, y1, x0, x1, base, topRamp) {
  // perspective table top from y0 (far edge) to y1 (near edge) + front edge below
  topRamp = topRamp || WD;
  for (let y = y0; y < y1; y++) {
    const f = (y - y0) / (y1 - y0);
    for (let x = x0; x < x1; x++) {
      let col = C(topRamp, base);
      const g = Math.sin(x * 0.07 + Math.sin(y * 0.9 + x * 0.013) * 2.2);
      if (g > 0.85) col = C(topRamp, base - 1);
      if (f < 0.12 && G.bayer(x, y) < 6) col = C(topRamp, base - 1);
      px(c, x, y, col);
    }
  }
  // reflections of windows on polished top
  fill(c, x0, y1, x1 - x0, 1, C(topRamp, base + 2));
  fill(c, x0, y1 + 1, x1 - x0, 2, C(topRamp, base + 1));
  fill(c, x0, y1 + 3, x1 - x0, 1, C(topRamp, base - 2));
  fill(c, x0, y1 + 4, x1 - x0, SH - y1 - 4, C(topRamp, base - 2));
  for (let x = x0 + 6; x < x1; x += 46) panelRect(c, x, y1 + 8, 40, SH - y1 - 6, topRamp, base - 1, 2);
}

/* ======================= JUDGE ======================= */
function buildJudge() {
  const back = G.makeCanvas(SW, SH), b = back.getContext('2d');
  // tall walnut wall, low camera: verticals lean in slightly toward the top
  panelWall(b, 0, SW, 0, 170, 0, 170, 1, [], [], 2, 2);
  // side wings (darker, receding)
  panelWall(b, 0, 70, 6, 170, 0, 170, 1.0, [0.12, 0.88], [0.12, 0.45, 0.52, 0.92], 1, 2);
  panelWall(b, 314, SW, 0, 170, 6, 170, 1.0, [0.12, 0.88], [0.12, 0.45, 0.52, 0.92], 1, 2);
  // central backdrop
  panelWall(b, 84, 300, 22, 170, 22, 170, 1, [0.05, 0.95], [0.04, 0.96], 2, 3);
  // pilasters
  for (const x of [70, 300]) {
    fill(b, x, 0, 14, 170, WD[3]); fill(b, x, 0, 2, 170, WD[5]); fill(b, x + 12, 0, 2, 170, WD[1]);
    for (let k = 0; k < 3; k++) { fill(b, x + 4 + k * 3, 14, 1, 150, WD[1]); fill(b, x + 5 + k * 3, 14, 1, 150, WD[4]); }
    moulding(b, x - 2, 10, 18, WD, [6, 4, 2, 1]);
  }
  // cornice
  moulding(b, 0, 0, SW, WD, [1, 3, 5, 6, 4, 3, 2, 1, 0]);
  for (let x = 2; x < SW; x += 5) { fill(b, x, 9, 3, 3, WD[4]); fill(b, x, 11, 3, 1, WD[2]); fill(b, x + 2, 9, 1, 3, WD[2]); }
  moulding(b, 0, 12, SW, WD, [1, 0, 4, 3]);
  // seal (big) with halo shadow
  b.globalAlpha = 0.35; G.ellipse(b, 196, 78, 44, 44, P.shadow); b.globalAlpha = 1;
  drawSeal(b, 192, 74, 42);
  // ring text dots enhancement: "THE GREAT SEAL OF THE STATE OF CALIFORNIA" suggested by tick marks
  // flag stands
  bigPole(b, 40, 22, 170); bigPole(b, 342, 22, 170);
  // light shaft from upper-left
  const sh = [[0, 0], [60, 0], [210, 170], [120, 170]];
  // lower shadow under bench overhang
  for (let y = 150; y < 170; y++) G.dither(b, 0, y, SW, 1, P.black, (y - 150) >> 1);
  vignette(b, 9);
  const shaft = beam(b, sh);
  // ---- front: bench ----
  const front = G.makeCanvas(SW, SH), f = front.getContext('2d');
  // bench top seen from below: big overhanging cornice
  moulding(f, 0, 140, SW, WD, [6, 5, 5, 4, 3]);
  fill(f, 0, 145, SW, 6, WD[2]);
  for (let x = 0; x < SW; x += 6) { fill(f, x, 146, 4, 3, WD[3]); px(f, x, 146, WD[5]); fill(f, x, 149, 4, 1, WD[1]); }
  moulding(f, 0, 151, SW, WD, [1, 0, 3, 2]);
  fill(f, 0, 155, SW, SH - 155, WD[2]);
  for (let x = 4; x < SW; x += 64) panelRect(f, x, 160, 56, 54, WD, 3, 3);
  // banker's lamp (left)
  const lx = 30;
  fill(f, lx - 8, 136, 18, 4, GO[2]); fill(f, lx - 8, 136, 18, 1, GO[4]);
  fill(f, lx, 122, 2, 14, GO[3]); px(f, lx, 122, GO[5]);
  G.poly(f, [[lx - 14, 122], [lx + 16, 122], [lx + 12, 112], [lx - 10, 112]], R.green[3]);
  fill(f, lx - 10, 112, 22, 2, R.green[4]); fill(f, lx - 13, 120, 28, 2, R.green[2]); px(f, lx - 6, 114, R.green[6]); px(f, lx - 5, 114, R.green[5]);
  fill(f, lx - 12, 122, 26, 1, P.glow);
  // gavel on sound block
  const gx = 74;
  G.ellipse(f, gx, 138, 12, 3, WD[1]); G.ellipse(f, gx, 137, 12, 2, WD[3]); fill(f, gx - 12, 137, 24, 1, WD[4]);
  fill(f, gx - 22, 127, 16, 7, WD[3]); fill(f, gx - 22, 127, 16, 2, WD[5]); fill(f, gx - 22, 133, 16, 1, WD[1]);
  fill(f, gx - 20, 127, 1, 7, GO[4]); fill(f, gx - 9, 127, 1, 7, GO[4]);
  G.line(f, gx - 6, 131, gx + 20, 135, WD[4]); G.line(f, gx - 6, 132, gx + 20, 136, WD[2]);
  // nameplate: HON. H. WHITAKER
  const nx = 258, ny = 122;
  G.poly(f, [[nx - 4, 140], [nx + 80, 140], [nx + 76, 136], [nx, 136]], WD[1]);
  fill(f, nx, ny, 76, 14, GO[3]); fill(f, nx, ny, 76, 1, GO[5]); fill(f, nx, ny + 13, 76, 1, GO[1]);
  fill(f, nx, ny, 1, 14, GO[4]); fill(f, nx + 75, ny, 1, 14, GO[2]);
  G.frame(f, nx + 2, ny + 2, 72, 10, GO[2]);
  const tx = 'HON. H. WHITAKER';
  text3(f, tx, nx + 38 - (text3W(tx) >> 1), ny + 4, GO[1], GO[4]);
  // microphone
  fill(f, 330, 136, 14, 4, NE[2]); fill(f, 330, 136, 14, 1, NE[4]);
  G.line(f, 336, 136, 334, 120, NE[3]); G.line(f, 334, 120, 326, 110, NE[3]); fill(f, 322, 106, 5, 6, NE[1]); px(f, 323, 107, NE[4]);
  return { back, front, shaft, flags: [0, 1, 2, 3].map(i => [bigFlag('us', 30, 90, i * 1.57), bigFlag('ca', 30, 90, i * 1.57 + 0.8)]), motes: makeMotes(11, 40, [0, 0, 210, 170]) };
}
let J = null;
SHOTS.judge = function (ctx, layer, t) {
  if (!J) J = buildJudge();
  if (layer === 'back') {
    ctx.drawImage(J.back, 0, 0);
    const k = Math.floor(t * 1.3) % 4, k2 = (k + 1) % 4;
    G.blit(ctx, J.flags[k][0], 43, 24);
    G.blit(ctx, J.flags[k2][1], 341 - 30, 24, true);
    ctx.globalAlpha = 0.12 + 0.04 * Math.sin(t * 0.4);
    ctx.drawImage(J.shaft, 0, 0); ctx.globalAlpha = 1;
    drawMotes(ctx, J.motes, t, (x, y) => inPoly([[0, 0], [60, 0], [210, 170], [120, 170]], x, y));
  } else {
    ctx.drawImage(J.front, 0, 0);
    // lamp light flicker + glint on the nameplate
    ctx.globalAlpha = 0.18 + 0.03 * Math.sin(t * 9) * Math.sin(t * 2.3);
    G.dither(ctx, 14, 123, 34, 13, P.glow, 8); ctx.globalAlpha = 1;
    const gl = ((t * 0.35) % 1.6) * 60;
    if (gl < 80) { px(ctx, 258 + gl | 0, 123, GO[5]); px(ctx, 259 + gl | 0, 123, P.white); }
  }
};

/* ======================= WITNESS ======================= */
function buildWitness() {
  const back = G.makeCanvas(SW, SH), b = back.getContext('2d');
  // back wall: plaster top, walnut wainscot, receding to the left
  plaster(b, 0, 0, SW, 110, 4, 3);
  G.dither(b, 0, 0, SW, 14, ST[3], 8);
  moulding(b, 0, 0, SW, WD, [1, 4, 3, 2, 1]);
  moulding(b, 0, 30, SW, WD, [3, 1]);
  panelWall(b, 0, SW, 96, 170, 92, 170, 1, [0.01, 0.09, 0.11, 0.19, 0.21, 0.29, 0.31, 0.39, 0.41, 0.49, 0.51, 0.59, 0.61, 0.69, 0.71, 0.79, 0.81, 0.89, 0.91, 0.99], [0.15, 0.85], 3, 2);
  moulding(b, 0, 91, SW, WD, [5, 4, 3, 1]);
  // tall window, left, with light
  const wx = 18, ww = 50;
  fill(b, wx - 5, 10, ww + 10, 86, WD[2]); fill(b, wx - 5, 10, ww + 10, 1, WD[4]); fill(b, wx - 5, 10, 1, 86, WD[4]);
  for (let y = 14; y < 92; y++) for (let x = wx; x < wx + ww; x++) {
    const f = (y - 14) / 78;
    let col = f < 0.3 ? P.sky : f < 0.65 ? P.sky2 : P.glow;
    if (f > 0.25 && f < 0.3 && G.bayer(x, y) < 8) col = P.sky2;
    if (f > 0.6 && f < 0.65 && G.bayer(x, y) < 8) col = P.glow;
    px(b, x, y, col);
  }
  // palm silhouettes outside
  for (let y = 40; y < 92; y++) px(b, wx + 14 + ((y / 11) | 0) % 2, y, R.green[2]);
  [[-12, 4], [-9, 8], [10, 3], [12, 9], [-4, 10], [5, 11]].forEach(([dx, dy]) => G.line(b, wx + 15, 40, wx + 15 + dx, 40 + dy, R.green[2]));
  for (let y = 40; y < 92; y++) px(b, wx + 38, y, R.green[3]);
  [[-7, 3], [7, 3], [-5, 6], [6, 6]].forEach(([dx, dy]) => G.line(b, wx + 38, 40, wx + 38 + dx, 40 + dy, R.green[3]));
  fill(b, wx + 24, 14, 2, 78, WD[2]); for (let y = 30; y < 92; y += 16) fill(b, wx, y, ww, 1, WD[2]);
  fill(b, wx, 14, ww, 6, ST[4]); for (let k = 0; k < 6; k += 2) fill(b, wx, 14 + k, ww, 1, ST[3]);
  fill(b, wx - 6, 94, ww + 12, 3, WD[4]);
  // clock
  G.ellipse(b, 128, 46, 13, 13, WD[1]); G.ellipse(b, 128, 46, 12, 12, GO[3]); G.ellipse(b, 128, 46, 10, 10, NE[9]);
  for (let i = 0; i < 12; i++) { const a = i / 12 * Math.PI * 2; px(b, 128 + Math.round(Math.sin(a) * 8), 46 - Math.round(Math.cos(a) * 8), NE[3]); }
  px(b, 121, 39, GO[5]); px(b, 122, 38, GO[5]);
  b.globalAlpha = 0.3; G.ellipse(b, 131, 49, 13, 13, P.shadow); b.globalAlpha = 1;
  G.ellipse(b, 128, 46, 13, 13, WD[1]); G.ellipse(b, 128, 46, 12, 12, GO[3]); G.ellipse(b, 128, 46, 10, 10, NE[9]);
  for (let i = 0; i < 12; i++) { const a = i / 12 * Math.PI * 2; px(b, 128 + Math.round(Math.sin(a) * 8), 46 - Math.round(Math.cos(a) * 8), i % 3 ? NE[5] : NE[2]); }
  px(b, 121, 39, NE[9]);
  // judge's bench mass on the right (closer, darker)
  panelWall(b, 300, SW, 30, 170, 18, 170, 1, [0.1, 0.9], [0.18, 0.55, 0.62, 0.95], 2, 2);
  moulding(b, 296, 26, 88, WD, [6, 5, 4, 2, 1, 0]);
  fill(b, 296, 26, 3, 144, WD[4]); fill(b, 299, 26, 1, 144, WD[1]);
  // CA flag pole in front of the bench edge
  bigPole(b, 284, 14, 170);
  // floor (carpet) below the wainscot
  for (let y = 170; y < SH; y++) for (let x = 0; x < SW; x++) px(b, x, y, ((x + y * 2) % 16 === 0) ? R.carpet[2] : R.carpet[1]);
  vignette(b, 7);
  for (let y = 150; y < 170; y++) G.dither(b, 0, y, SW, 1, P.black, (y - 150) >> 1);
  const shaft = beam(b, [[wx, 14], [wx + ww, 14], [wx + ww + 150, 170], [wx + 70, 170]]);
  // ---- front: witness stand ----
  const front = G.makeCanvas(SW, SH), f = front.getContext('2d');
  // stand top rail (angled slightly, receding to the left)
  for (let x = 92; x < SW; x++) {
    const top = 146 + Math.round((x - 92) * 0.02);
    for (let y = top; y < top + 9; y++) px(f, x, y, y === top ? WD[6] : y < top + 3 ? WD[5] : y < top + 6 ? WD[4] : WD[3]);
    for (let y = top + 9; y < SH; y++) px(f, x, y, WD[2]);
  }
  // side panel of the stand (left, receding)
  quad(f, 70, 92, 150, SH, 146, SH, (x, y, u, v) => v < 0.04 ? WD[5] : panelCol(Math.round(u * 21) - 3, 18 - Math.round(u * 21), Math.round(v * 70) - 8, 60 - Math.round(v * 70), WD, 1, 1, x, y) || WD[1], 1);
  fill(f, 92, 146, 1, 70, WD[6]);
  for (let x = 100; x < SW; x += 70) panelRect(f, x, 160, 62, 56, WD, 3, 2);
  // gooseneck mic
  fill(f, 136, 143, 18, 4, NE[1]); fill(f, 136, 143, 18, 1, NE[4]); fill(f, 138, 141, 14, 2, NE[2]);
  const neck = [[145, 141], [146, 134], [146, 127], [144, 121], [140, 116], [135, 113]];
  for (let i = 0; i + 1 < neck.length; i++) { G.line(f, neck[i][0], neck[i][1], neck[i + 1][0], neck[i + 1][1], NE[3]); G.line(f, neck[i][0] + 1, neck[i][1], neck[i + 1][0] + 1, neck[i + 1][1], NE[1]); }
  for (let i = 0; i < 5; i++) px(f, neck[i][0], neck[i][1] - 2, NE[5]);
  fill(f, 126, 108, 10, 7, NE[1]); fill(f, 126, 108, 10, 1, NE[4]); for (let k = 0; k < 3; k++) px(f, 128 + k * 3, 110, NE[3]); fill(f, 126, 114, 10, 1, NE[2]);
  // glass of water + carafe
  glass(f, 300, 147, 14, true);
  pitcherBig(f, 330, 147);
  // nameplate-free; a folded tissue & sheet of exhibit
  G.poly(f, [[200, 147], [236, 147], [240, 150], [196, 150]], R.paper[4]); fill(f, 196, 150, 44, 1, R.paper[2]);
  return { back, front, shaft, flag: [0, 1, 2, 3].map(i => bigFlag('ca', 26, 80, i * 1.57)), motes: makeMotes(21, 36, [18, 14, 220, 156]) };
}
let Wt = null;
SHOTS.witness = function (ctx, layer, t) {
  if (!Wt) Wt = buildWitness();
  if (layer === 'back') {
    ctx.drawImage(Wt.back, 0, 0);
    const k = Math.floor(t * 1.2) % 4;
    G.blit(ctx, Wt.flag[k], 287 - 26, 16, true);
    // clock hands
    const a = Lb.clockHands(t);
    const hand = (ang, r, col) => { for (let i = 1; i <= r; i++) px(ctx, 128 + Math.round(Math.sin(ang) * i), 46 - Math.round(Math.cos(ang) * i), col); };
    hand(a.h, 5, NE[1]); hand(a.m, 8, NE[1]); hand(a.s, 8, R.red[3]); px(ctx, 128, 46, GO[2]);
    ctx.globalAlpha = 0.13 + 0.04 * Math.sin(t * 0.33); ctx.drawImage(Wt.shaft, 0, 0); ctx.globalAlpha = 1;
    drawMotes(ctx, Wt.motes, t, (x, y) => inPoly([[18, 14], [68, 14], [218, 170], [88, 170]], x, y));
  } else {
    ctx.drawImage(Wt.front, 0, 0);
    // mic LED + glass shimmer
    px(ctx, 134, 113, (t % 1.4) < 1.0 ? R.red[4] : R.red[2]);
    const s = Math.floor(t * 3) % 6;
    px(ctx, 301, 140 + (s % 3), NE[9]);
  }
};

/* ======================= COUNSEL (defense / prosecution) ======================= */
function buildCounsel(side) {
  const L = side === 'def';
  const back = G.makeCanvas(SW, SH), b = back.getContext('2d');
  // back wall (gallery side): plaster with windows on the left wall (def) or door/clock (pro)
  plaster(b, 0, 0, SW, 120, 3, L ? 7 : 9);
  G.dither(b, 0, 0, SW, 16, ST[2], 8);
  moulding(b, 0, 0, SW, WD, [0, 3, 2, 1, 0]);
  moulding(b, 0, 26, SW, WD, [2, 0]);
  // receding side wall with tall windows (perspective) on the far side
  const sx0 = L ? 300 : 0, sx1 = L ? SW : 84;
  if (L) {
    quad(b, sx0, sx1, 12, 132, 0, 150, (x, y, u, v) => {
      const inW = (u > 0.12 && u < 0.42) || (u > 0.6 && u < 0.9);
      if (inW && v > 0.1 && v < 0.62) { const f = (v - 0.1) / 0.52; return f < 0.4 ? P.sky : f < 0.75 ? P.sky2 : P.glow; }
      if (inW && v >= 0.62 && v < 0.66) return WD[4];
      if (v > 0.72) return v < 0.74 ? WD[4] : WD[1];
      return h2(x, y) < 0.05 ? ST[3] : ST[4];
    }, 1.6);
  } else {
    quad(b, sx0, sx1, 0, 150, 12, 132, (x, y, u, v) => {
      if (v > 0.72) return v < 0.74 ? WD[4] : WD[1];
      return h2(x, y) < 0.05 ? ST[2] : ST[3];
    }, 0.6);
  }
  // wainscot on back wall
  const wx0 = L ? 0 : 84, wx1 = L ? 300 : SW;
  panelWall(b, wx0, wx1, 82, 140, 82, 140, 1, (() => { const a = []; for (let u = 0; u < 1; u += 0.1) a.push(u + 0.01, u + 0.09); return a; })(), [0.12, 0.85], 2, 2);
  moulding(b, wx0, 80, wx1 - wx0, WD, [5, 4, 3, 1]);
  if (L) {
    // windows' light pool on back wall + shaft
  } else {
    // exit door + sign + clock
    const dx = 120;
    fill(b, dx - 4, 22, 58, 100, WD[3]); fill(b, dx - 4, 22, 58, 1, WD[5]); fill(b, dx - 4, 22, 1, 100, WD[4]);
    fill(b, dx, 26, 50, 96, WD[0]);
    for (let k = 0; k < 2; k++) { fill(b, dx + k * 25, 26, 24, 96, WD[2]); panelRect(b, dx + 2 + k * 25, 52, 20, 30, WD, 2, 2); fill(b, dx + 4 + k * 25, 30, 16, 18, NE[3]); G.dither(b, dx + 4 + k * 25, 30, 16, 18, NE[4], 4); }
    fill(b, dx - 2, 88, 54, 3, NE[5]); fill(b, dx - 2, 88, 54, 1, NE[7]);
    fill(b, dx + 6, 8, 38, 12, NE[8]); fill(b, dx + 6, 8, 38, 1, NE[9]); fill(b, dx + 6, 19, 38, 1, NE[5]);
    const s = 'EXIT'; for (let i = 0; i < 4; i++) { const g = Lb.F3[s[i]]; for (let k = 0; k < 15; k++) if (g[k] === '1') fill(b, dx + 10 + i * 8 + (k % 3) * 2, 10 + ((k / 3) | 0) * 2 - 1, 2, 2, R.red[3]); }
    // clock
    const ccx = 262, ccy = 40;
    G.ellipse(b, ccx, ccy, 12, 12, WD[1]); G.ellipse(b, ccx, ccy, 11, 11, GO[3]); G.ellipse(b, ccx, ccy, 9, 9, NE[9]);
    for (let i = 0; i < 12; i++) { const a = i / 12 * Math.PI * 2; px(b, ccx + Math.round(Math.sin(a) * 7), ccy - Math.round(Math.cos(a) * 7), i % 3 ? NE[5] : NE[2]); }
  }
  // gallery pews (back row), people get drawn per-frame, then bar railing in front of them
  const rail = G.makeCanvas(SW, SH), rr = rail.getContext('2d');
  // pew backs
  fill(rr, 0, 122, SW, 4, WD[4]); fill(rr, 0, 122, SW, 1, WD[5]); fill(rr, 0, 126, SW, 6, WD[2]);
  // bar rail
  fill(rr, 0, 132, SW, 3, WD[5]); fill(rr, 0, 132, SW, 1, WD[6]); fill(rr, 0, 135, SW, 2, WD[2]);
  for (let x = 3; x < SW; x += 9) { fill(rr, x, 137, 4, 18, WD[3]); fill(rr, x, 137, 1, 18, WD[5]); fill(rr, x + 3, 137, 1, 18, WD[1]); fill(rr, x, 142, 4, 1, WD[4]); fill(rr, x, 145, 4, 1, WD[1]); }
  fill(rr, 0, 155, SW, 3, WD[2]);
  // darken rail a bit (depth)
  // crowd
  const r = G.rng(L ? 101 : 202);
  const ppl = [];
  const xs = L ? [186, 222, 262, 298, 338, 372, 18, 52] : [14, 50, 88, 124, 162, 208, 340, 372];
  xs.forEach((x, i) => {
    const o = randPerson(r, 1.45 + (i % 3) * 0.06, 1);
    ppl.push({ x, y: 140 + (i % 2) * 2, o, whisper: i % 2 === 0 });
  });
  // sometimes neighbour looks toward whisperer
  ppl.forEach((p, i) => { if (i % 2 === 0 && ppl[i + 1]) { p.o.look = (ppl[i + 1].x > p.x) ? 1 : -1; } });
  const cr = crowd(ppl);
  // shaft from side windows (def) / overhead light (pro)
  const shPts = L ? [[310, 20], [372, 10], [160, 170], [40, 170]] : [[0, 0], [70, 0], [190, 170], [100, 170]];
  const shaft = beam(b, shPts);
  vignette(b, 7);
  // ---- front: counsel table ----
  const front = G.makeCanvas(SW, SH), f = front.getContext('2d');
  shotDesk(f, 148, 160, 0, SW, 4);
  if (L) {
    folderStack(f, 2, 152, 6, 7);
    legalPad(f, [[150, 148], [196, 148], [204, 160], [146, 160]], 4, 3);
    pen(f, 206, 156, 14);
    laptopBack(f, 232, 154);
    pitcherBig(f, 312, 158);
    glass(f, 330, 158, 12, true);
    G.poly(f, [[338, 152], [384, 150], [384, 158], [344, 160]], R.paper[4]); fill(f, 344, 160, 40, 1, R.paper[2]);
    for (let k = 0; k < 4; k++) fill(f, 348 + k, 153 + k * 2, 26, 1, R.paper[2]);
    // paper clip, sticky note
    fill(f, 116, 151, 8, 6, GO[5]); fill(f, 116, 151, 8, 1, GO[4]);
  } else {
    pitcherBig(f, 36, 158);
    glass(f, 52, 158, 12, true);
    laptopBack(f, 96, 154);
    legalPad(f, [[178, 148], [222, 148], [228, 160], [172, 160]], 4, 9);
    pen(f, 160, 157, 14, R.red[2]);
    // binders
    for (let i = 0; i < 3; i++) {
      const bx = 316 + i * 3, by = 160 - i * 6, col = [R.red, R.blue, NE][i];
      fill(f, bx, by - 6, 62, 6, C(col, 3)); fill(f, bx, by - 6, 62, 1, C(col, 4)); fill(f, bx + 62, by - 6, 3, 6, R.paper[3]);
      fill(f, bx + 4, by - 4, 14, 2, NE[8]);
    }
  }
  return { back, rail, front, cr, shaft, shPts, motes: makeMotes(L ? 31 : 32, 34, L ? [40, 10, 330, 160] : [0, 0, 190, 170]), L };
}
const CS = {};
function counselShot(side) {
  return function (ctx, layer, t) {
    if (!CS[side]) CS[side] = buildCounsel(side);
    const S = CS[side];
    if (layer === 'back') {
      ctx.drawImage(S.back, 0, 0);
      if (!S.L) {
        const a = Lb.clockHands(t);
        const hand = (ang, r, col) => { for (let i = 1; i <= r; i++) px(ctx, 262 + Math.round(Math.sin(ang) * i), 40 - Math.round(Math.cos(ang) * i), col); };
        hand(a.h, 4, NE[1]); hand(a.m, 7, NE[1]); hand(a.s, 7, R.red[3]);
      }
      drawCrowd(ctx, S.cr, t);
      ctx.drawImage(S.rail, 0, 0);
      ctx.globalAlpha = 0.12 + 0.04 * Math.sin(t * 0.31); ctx.drawImage(S.shaft, 0, 0); ctx.globalAlpha = 1;
      drawMotes(ctx, S.motes, t, (x, y) => inPoly(S.shPts, x, y));
    } else {
      ctx.drawImage(S.front, 0, 0);
      if (S.L) { // laptop power LED, paper corner lifting in air from vent
        px(ctx, 270, 152, (t % 2) < 1.6 ? R.green[5] : R.green[3]);
        const l = [0, 1, 2, 1][Math.floor(t * 6) % 4];
        G.poly(ctx, [[372, 150 - l], [384, 148 - l * 2], [384, 151], [374, 152]], R.paper[3]);
      } else {
        px(ctx, 134, 152, (t % 2) < 1.6 ? R.green[5] : R.green[3]);
      }
    }
  };
}
SHOTS.defense = counselShot('def');
SHOTS.prosecution = counselShot('pro');

/* ======================= JURY ======================= */
function buildJury() {
  const back = G.makeCanvas(SW, SH), b = back.getContext('2d');
  plaster(b, 0, 0, SW, 70, 4, 13);
  G.dither(b, 0, 0, SW, 12, ST[3], 8);
  moulding(b, 0, 0, SW, WD, [1, 4, 3, 2, 1]);
  // back wall of the jury box: walnut
  panelWall(b, 0, SW, 60, 120, 60, 120, 1, (() => { const a = []; for (let u = 0; u < 1; u += 1 / 8) a.push(u + 0.008, u + 0.117); return a; })(), [0.1, 0.9], 2, 2);
  moulding(b, 0, 58, SW, WD, [5, 4, 3, 1]);
  // a framed seal plaque and the clock
  drawSeal(b, 192, 30, 16);
  // rear tier riser + chairs
  fill(b, 0, 118, SW, 4, WD[4]); fill(b, 0, 118, SW, 1, WD[5]);
  const r = G.rng(404);
  const rear = [], frontRow = [];
  const rearX = [34, 92, 150, 224, 286, 346], frontX = [52, 118, 192, 266, 332];
  // fixed variety for readability
  const looks = [
    { style: 'bun', skin: R.skinL, hair: R.hairGrey, cloth: R.purple, glasses: NE[2] },
    { style: 'short', skin: R.skinD, hair: R.hairBlack, cloth: R.stone, tie: R.red[2], collar: NE[8] },
    { style: 'long', skin: R.skinL, hair: R.hairBlond, cloth: R.teal },
    { style: 'bald', skin: R.skinM, hair: R.hairBrown, cloth: R.green, beard: true },
    { style: 'curly', skin: R.skinD, hair: R.hairBlack, cloth: R.gold },
    { style: 'cap', skin: R.skinL, hair: R.hairRed, cloth: R.red, capCol: R.blue[3], capCol2: R.blue[2] },
    { style: 'bob', skin: R.skinM, hair: R.hairBlack, cloth: R.blue, glasses: NE[1] },
    { style: 'short', skin: R.skinL, hair: R.hairBrown, cloth: NE, collar: NE[8] },
    { style: 'bob', skin: R.skinL, hair: R.hairRed, cloth: R.green },
    { style: 'short', skin: R.skinM, hair: R.hairGrey, cloth: R.wood, glasses: GO[2] },
    { style: 'long', skin: R.skinD, hair: R.hairBrown, cloth: R.purple },
  ];
  let li = 0;
  rearX.forEach((x, i) => rear.push({ x, y: 130, o: Object.assign({ s: 1.0, dim: 1, bulk: 0.9 + r() * 0.3, look: i < 3 ? -1 : 1 }, looks[li++ % looks.length]), whisper: i === 1 || i === 4 }));
  frontX.forEach((x, i) => frontRow.push({ x, y: 164, o: Object.assign({ s: 1.45, dim: 0, bulk: 0.9 + r() * 0.3, look: i < 2 ? 1 : -1 }, looks[li++ % looks.length]), whisper: i === 0 || i === 3 }));
  // chair backs
  const chairs = G.makeCanvas(SW, SH), ch = chairs.getContext('2d');
  rearX.forEach(x => { fill(ch, x - 13, 96, 26, 26, R.red[1]); fill(ch, x - 13, 96, 26, 2, R.red[2]); fill(ch, x - 13, 96, 1, 26, R.red[2]); });
  const chairs2 = G.makeCanvas(SW, SH), ch2 = chairs2.getContext('2d');
  frontX.forEach(x => { fill(ch2, x - 17, 116, 34, 30, R.red[2]); fill(ch2, x - 17, 116, 34, 2, R.red[3]); fill(ch2, x - 17, 116, 2, 30, R.red[3]); fill(ch2, x + 15, 116, 2, 30, R.red[1]); });
  // mid parapet between tiers
  const mid = G.makeCanvas(SW, SH), md = mid.getContext('2d');
  fill(md, 0, 126, SW, 3, WD[5]); fill(md, 0, 126, SW, 1, WD[6]); fill(md, 0, 129, SW, 12, WD[2]);
  for (let x = 4; x < SW; x += 32) panelRect(md, x, 130, 28, 10, WD, 2, 1);
  // front rail (front layer)
  const front = G.makeCanvas(SW, SH), f = front.getContext('2d');
  fill(f, 0, 150, SW, 4, WD[6]); fill(f, 0, 152, SW, 3, WD[5]); fill(f, 0, 155, SW, 3, WD[3]); fill(f, 0, 158, SW, SH - 158, WD[2]);
  for (let x = 6; x < SW; x += 48) panelRect(f, x, 162, 42, 50, WD, 3, 2);
  // notepads on the rail
  G.poly(f, [[60, 149], [80, 149], [82, 152], [58, 152]], R.paper[4]);
  G.poly(f, [[300, 149], [322, 149], [324, 152], [298, 152]], R.paper[4]);
  pen(f, 84, 151, 10);
  vignette(b, 7);
  const shaft = beam(b, [[0, 0], [80, 0], [230, 170], [120, 170]]);
  return { back, chairs, chairs2, mid, front, rear: crowd(rear), fr: crowd(frontRow), shaft, motes: makeMotes(41, 30, [0, 0, 230, 170]) };
}
let JY = null;
SHOTS.jury = function (ctx, layer, t) {
  if (!JY) JY = buildJury();
  if (layer === 'back') {
    ctx.drawImage(JY.back, 0, 0);
    ctx.drawImage(JY.chairs, 0, 0);
    drawCrowd(ctx, JY.rear, t);
    ctx.drawImage(JY.mid, 0, 0);
    ctx.drawImage(JY.chairs2, 0, 0);
    drawCrowd(ctx, JY.fr, t);
    // a juror fans herself with a sheet
    const fx = 332 + 16, fy = 132, ph = Math.floor(t * 8) % 4;
    const off = [0, -2, -3, -2][ph];
    G.poly(ctx, [[fx - 2, fy + 4], [fx + 6, fy + off], [fx + 8, fy + off + 6], [fx, fy + 10]], R.paper[4]);
    fill(ctx, fx - 3, fy + 8, 4, 4, R.skinL[3]);
    ctx.globalAlpha = 0.11 + 0.03 * Math.sin(t * 0.3); ctx.drawImage(JY.shaft, 0, 0); ctx.globalAlpha = 1;
    drawMotes(ctx, JY.motes, t, (x, y) => inPoly([[0, 0], [80, 0], [230, 170], [120, 170]], x, y));
  } else {
    ctx.drawImage(JY.front, 0, 0);
    // pen writing scratch on a notepad
    if ((t % 3) < 1.5) { const k = Math.floor(t * 10) % 6; px(ctx, 64 + k * 2, 150, P.ink); }
  }
};

/* ======================= VISIT (county jail) ======================= */
function buildVisit() {
  const back = G.makeCanvas(SW, SH), b = back.getContext('2d');
  const GR = R.green;
  // cinder block wall (institutional green) behind the glass
  for (let y = 0; y < 170; y++) for (let x = 0; x < SW; x++) {
    const row = Math.floor(y / 9), off = (row & 1) * 12;
    const bx = (x + off) % 24, by = y % 9;
    let col = GR[3];
    if (by === 0 || bx === 0) col = GR[2];
    else if (by === 1 || bx === 1) col = GR[4];
    else if (h2(x, y) < 0.08) col = GR[2];
    if (y > 120) col = (by === 0 || bx === 0) ? GR[1] : (y > 124 ? GR[2] : col);
    px(b, x, y, col);
  }
  // painted lower band (darker)
  fill(b, 0, 120, SW, 2, GR[1]);
  // steel door far right with tiny window
  fill(b, 284, 28, 64, 142, NE[3]); fill(b, 286, 30, 60, 140, NE[4]); fill(b, 286, 30, 60, 1, NE[6]);
  fill(b, 300, 44, 18, 26, NE[1]); fill(b, 302, 46, 14, 22, R.blue[1]);
  for (let k = 0; k < 22; k += 4) G.line(b, 302, 46 + k, 302 + Math.min(14, 22 - k), 46 + k + Math.min(14, 22 - k), NE[3]);
  fill(b, 336, 98, 6, 3, NE[6]); fill(b, 338, 96, 2, 8, NE[2]);
  // sign
  fill(b, 92, 30, 64, 22, NE[8]); fill(b, 92, 30, 64, 1, NE[9]); fill(b, 92, 51, 64, 1, NE[5]);
  text3(b, 'NO CONTACT', 105, 34, R.red[2]);
  text3(b, 'VISIT 15 MIN', 101, 43, NE[2]);
  // the inmate side counter
  fill(b, 0, 150, SW, 20, NE[3]); fill(b, 0, 150, SW, 1, NE[5]);
  // fluorescent fixture (visible over the glass)
  fill(b, 120, 0, 150, 7, NE[6]); fill(b, 122, 7, 146, 3, NE[9]); fill(b, 120, 10, 150, 1, NE[5]);
  const glare = G.makeCanvas(SW, SH), gl = glare.getContext('2d');
  G.dither(gl, 60, 10, 270, 60, P.white, 3); G.dither(gl, 110, 10, 170, 30, P.white, 5);
  // ---- front: glass + booth ----
  const front = G.makeCanvas(SW, SH), f = front.getContext('2d');
  // glass reflections (semi transparent streaks)
  const refl = G.makeCanvas(SW, SH), rf = refl.getContext('2d');
  for (const [x0, w] of [[90, 26], [128, 8], [262, 18], [292, 6]]) G.poly(rf, [[x0, 14], [x0 + w, 14], [x0 + w - 70, 150], [x0 - 70, 150]], P.white);
  // smudge (hand print)
  G.dither(rf, 250, 92, 16, 14, P.white, 5); G.dither(rf, 246, 86, 4, 8, P.white, 5); G.dither(rf, 252, 82, 4, 10, P.white, 5);
  // booth dividers (steel, perspective)
  quad(f, 0, 70, 0, SH, 14, 150, (x, y, u, v) => {
    if (u > 0.94) return NE[2];
    if (u > 0.88) return GR[1];
    return ((y + Math.round(u * 40)) % 23 === 0) ? GR[1] : (u < 0.1 ? GR[4] : GR[3]);
  }, 0.5);
  quad(f, 314, SW, 14, 150, 0, SH, (x, y, u, v) => {
    if (u < 0.06) return NE[5];
    if (u < 0.12) return GR[4];
    return ((y + Math.round(u * 40)) % 23 === 0) ? GR[1] : (u > 0.9 ? GR[1] : GR[2]);
  }, 2.0);
  // glass frame
  fill(f, 70, 10, 244, 5, NE[3]); fill(f, 70, 10, 244, 1, NE[6]); fill(f, 70, 14, 244, 1, NE[1]);
  fill(f, 68, 10, 4, 140, NE[3]); fill(f, 68, 10, 1, 140, NE[6]); fill(f, 312, 10, 4, 140, NE[3]); fill(f, 315, 10, 1, 140, NE[1]);
  // counter (our side)
  fill(f, 0, 148, SW, 3, NE[7]); fill(f, 0, 148, SW, 1, NE[8]); fill(f, 0, 151, SW, 6, NE[5]); fill(f, 0, 157, SW, SH - 157, GR[2]);
  for (let k = 0; k < 14; k++) { const x = 30 + (k * 53) % 330; G.line(f, x, 152 + (k % 4), x + 6 + (k % 5), 153 + (k % 3), NE[4]); }
  // phone on the left divider
  fill(f, 26, 74, 18, 30, NE[2]); fill(f, 26, 74, 18, 1, NE[4]); fill(f, 28, 78, 14, 2, NE[1]);
  for (let k = 0; k < 3; k++) for (let j = 0; j < 3; j++) fill(f, 30 + k * 4, 84 + j * 4, 2, 2, NE[5]);
  // handset on hook
  fill(f, 18, 70, 6, 34, NE[1]); fill(f, 18, 70, 2, 34, NE[3]); fill(f, 16, 68, 10, 6, NE[1]); fill(f, 16, 100, 10, 6, NE[1]); px(f, 17, 69, NE[4]);
  // armored cord (coiled steel)
  for (let y = 106; y < 140; y += 2) { fill(f, 20 + ((y >> 1) & 1), y, 4, 1, NE[5]); fill(f, 20 + ((y >> 1) & 1), y + 1, 4, 1, NE[3]); }
  // sticker
  fill(f, 30, 110, 12, 8, GO[4]); fill(f, 31, 112, 10, 1, NE[1]); fill(f, 31, 114, 7, 1, NE[1]);
  return { back, glare, front, refl };
}
let V = null;
SHOTS.visit = function (ctx, layer, t) {
  if (!V) V = buildVisit();
  // fluorescent flicker: mostly steady, occasional stutters
  const cyc = t % 6.3;
  const flick = (cyc > 4.1 && cyc < 4.5) ? ((Math.floor(t * 30) % 3) === 0 ? 0 : 1) : 1;
  if (layer === 'back') {
    ctx.drawImage(V.back, 0, 0);
    // guard's shadow passing behind door window
    const gp = (t % 11) / 11;
    if (gp < 0.25) {
      const gx = 296 + Math.round(gp / 0.25 * 30);
      G.ellipse(ctx, gx, 54, 4, 5, NE[1]); fill(ctx, gx - 6, 59, 12, 9, NE[1]);
    }
    fill(ctx, 122, 7, 146, 3, flick ? NE[9] : NE[6]);
    ctx.globalAlpha = flick ? 0.12 : 0.03; ctx.drawImage(V.glare, 0, 0); ctx.globalAlpha = 1;
    if (!flick) { ctx.globalAlpha = 0.25; G.dither(ctx, 0, 0, SW, SH, P.black, 8); ctx.globalAlpha = 1; }
  } else {
    ctx.globalAlpha = 0.1 + (flick ? 0.04 : 0); ctx.drawImage(V.refl, 0, 0); ctx.globalAlpha = 1;
    ctx.drawImage(V.front, 0, 0);
    if (!flick) { ctx.globalAlpha = 0.2; G.dither(ctx, 0, 0, SW, SH, P.black, 6); ctx.globalAlpha = 1; }
  }
};

/* ======================= DEFENDANT ======================= */
function buildDefendant() {
  const back = G.makeCanvas(SW, SH), b = back.getContext('2d');
  // far view toward the bench (left), receding wall to the right
  plaster(b, 0, 0, SW, 110, 3, 21);
  G.dither(b, 0, 0, SW, 16, ST[2], 8);
  moulding(b, 0, 0, SW, WD, [0, 3, 2, 1, 0]);
  // bench backdrop far left
  panelWall(b, 0, 150, 14, 120, 18, 118, 1, [0.06, 0.48, 0.52, 0.94], [0.08, 0.92], 1, 1);
  moulding(b, 0, 12, 150, WD, [4, 3, 1]);
  drawSeal(b, 76, 50, 16);
  bigPole(b, 160, 20, 120);
  // judge's bench (distant, dark)
  fill(b, 0, 96, 190, 50, WD[2]); fill(b, 0, 96, 190, 3, WD[4]); fill(b, 0, 96, 190, 1, WD[5]);
  for (let x = 4; x < 186; x += 30) panelRect(b, x, 104, 26, 38, WD, 2, 1);
  // empty judge's chair top over the bench
  fill(b, 60, 70, 30, 26, R.red[1]); fill(b, 60, 70, 30, 2, R.red[2]); for (let k = 0; k < 6; k++) px(b, 62 + k * 5, 72, GO[3]);
  // right side wall: windows light
  quad(b, 190, SW, 18, 146, 0, 170, (x, y, u, v) => {
    const inW = (u > 0.18 && u < 0.4) || (u > 0.62 && u < 0.86);
    if (inW && v > 0.08 && v < 0.6) { const f = (v - 0.08) / 0.52; return f < 0.4 ? P.sky : f < 0.75 ? P.sky2 : P.glow; }
    if (v > 0.66) return v < 0.68 ? WD[4] : (((x >> 3) & 1) ? WD[2] : WD[1]);
    return h2(x, y) < 0.05 ? ST[3] : ST[4];
  }, 1.8);
  // bailiff and clerk silhouettes in the distance
  const people = crowd([
    { x: 216, y: 146, o: { s: 0.9, dim: 1, style: 'bald', skin: R.skinD, hair: R.hairBlack, cloth: R.green, look: -1 }, whisper: false },
    { x: 26, y: 112, o: { s: 0.75, dim: 1, style: 'bun', skin: R.skinL, hair: R.hairBlack, cloth: R.teal, glasses: NE[2], look: 1 }, whisper: false },
  ]);
  for (let y = 146; y < 170; y++) G.dither(b, 0, y, SW, 1, P.black, (y - 146) >> 2);
  vignette(b, 7);
  const shPts = [[250, 10], [330, 0], [230, 170], [120, 170]];
  const shaft = beam(b, shPts);
  // ---- front: defense table (side view) ----
  const front = G.makeCanvas(SW, SH), f = front.getContext('2d');
  shotDesk(f, 152, 164, 0, SW, 4);
  // paper cup of water, legal pad with nervous doodles, tissue box
  fill(f, 96, 146, 10, 14, NE[8]); fill(f, 96, 146, 10, 1, NE[9]); fill(f, 104, 146, 2, 14, NE[6]); fill(f, 97, 147, 8, 2, R.blue[5]);
  legalPad(f, [[124, 152], [168, 152], [174, 164], [118, 164]], 3, 17);
  for (let k = 0; k < 5; k++) px(f, 150 + k, 160 - (k & 1), P.ink);
  fill(f, 300, 140, 34, 20, R.blue[4]); fill(f, 300, 140, 34, 1, R.blue[5]); fill(f, 300, 140, 1, 20, R.blue[5]); fill(f, 333, 140, 1, 20, R.blue[2]);
  G.poly(f, [[312, 140], [322, 140], [324, 132], [316, 130], [310, 134]], NE[9]); px(f, 316, 132, NE[7]);
  for (let x = 302; x < 332; x += 6) fill(f, x, 150, 3, 3, R.blue[3]);
  return { back, front, people, shaft, shPts, motes: makeMotes(51, 30, [120, 0, 220, 170]) };
}
let DF = null;
SHOTS.defendant = function (ctx, layer, t) {
  if (!DF) DF = buildDefendant();
  if (layer === 'back') {
    ctx.drawImage(DF.back, 0, 0);
    drawCrowd(ctx, DF.people, t);
    ctx.globalAlpha = 0.12 + 0.04 * Math.sin(t * 0.29); ctx.drawImage(DF.shaft, 0, 0); ctx.globalAlpha = 1;
    drawMotes(ctx, DF.motes, t, (x, y) => inPoly(DF.shPts, x, y));
  } else {
    ctx.drawImage(DF.front, 0, 0);
  }
};

/* ======================= EXTERIOR ======================= */
function buildExterior() {
  const sky = G.makeCanvas(SW, SH), s = sky.getContext('2d');
  // golden hour sky: dithered bands from blue (top) to warm gold at the horizon
  const bands = [R.blue[4], R.blue[5], P.sky, P.sky2, GO[5], R.red[5], GO[4]];
  const by = [0, 24, 50, 78, 104, 124, 140, 160];
  for (let i = 0; i < bands.length; i++) {
    fill(s, 0, by[i], SW, by[i + 1] - by[i], bands[i]);
    if (i + 1 < bands.length) for (let k = 0; k < 4; k++) G.dither(s, 0, by[i + 1] - 4 + k, SW, 1, bands[i], 12 - k * 3);
  }
  // sun low on the right
  for (let k = 3; k >= 0; k--) { s.globalAlpha = 0.2; G.ellipse(s, 30, 140, 16 + k * 9, 10 + k * 6, P.glow); } s.globalAlpha = 1;
  G.ellipse(s, 30, 140, 11, 11, GO[5]); G.ellipse(s, 30, 140, 9, 9, P.white);
  // distant city: LA City Hall tower + skyline silhouettes (cool purple haze)
  const skyline = [[0, 14], [18, 22], [30, 10], [44, 30], [60, 18], [74, 26], [88, 12], [98, 20]];
  skyline.forEach(([x, h], i) => { fill(s, x, 150 - h, (skyline[i + 1] ? skyline[i + 1][0] : 112) - x, h + 10, R.purple[3]); });
  // City Hall tower
  fill(s, 52, 92, 18, 60, R.purple[3]); fill(s, 55, 78, 12, 14, R.purple[3]); fill(s, 58, 68, 6, 10, R.purple[3]); fill(s, 60, 60, 2, 8, R.purple[3]);
  fill(s, 52, 92, 2, 60, R.purple[4]); fill(s, 55, 78, 1, 14, R.purple[4]);
  for (let y = 96; y < 148; y += 4) for (let x = 56; x < 68; x += 3) px(s, x, y, GO[4]);
  // ground below the skyline: hedges + lawn
  for (let y = 150; y < 186; y++) for (let x = 0; x < SW; x++) {
    let col = y < 156 ? R.purple[2] : y < 166 ? (((x * 3 + y) % 7 === 0) ? R.green[1] : R.green[2]) : (((x + y * 3) % 9 === 0) ? R.green[2] : R.green[3]);
    if (y >= 166 && y < 168 && G.bayer(x, y) < 8) col = R.green[2];
    if (y >= 156 && y < 160 && (x % 9) < 6) col = R.green[3];
    px(s, x, y, col);
  }
  for (let x = 0; x < SW; x += 2) if (h2(x, 3) < 0.4) px(s, x, 165, GO[4]);
  // ---- building (right) ----
  const bl = G.makeCanvas(SW, SH), b = bl.getContext('2d');
  const X0 = 136, X1 = SW, top = 64;
  // main block
  for (let y = top; y < 176; y++) for (let x = X0; x < X1; x++) {
    let col = ST[3];
    if (((y - top) % 8 === 0)) col = ST[2];
    else if (((x + ((((y - top) / 8) | 0) & 1) * 10) % 20) === 0) col = ST[2];
    else if (h2(x, y) < 0.04) col = ST[4];
    px(b, x, y, col);
  }
  // warm sunlit right faces / shadow left: sun from right -> faces lit warm
  // cornice + attic
  fill(b, X0 - 6, top - 14, X1 - X0 + 6, 14, ST[4]);
  moulding(b, X0 - 8, top - 16, X1 - X0 + 8, ST, [5, 4, 3, 1]);
  for (let x = X0 - 6; x < X1; x += 6) { fill(b, x, top - 12, 4, 3, ST[5]); fill(b, x, top - 9, 4, 1, ST[2]); }
  moulding(b, X0 - 6, top - 2, X1 - X0 + 6, ST, [1, 2, 4, 5]);
  // entablature with engraving
  fill(b, X0, top + 2, X1 - X0, 22, ST[4]); fill(b, X0, top + 2, X1 - X0, 1, ST[5]); fill(b, X0, top + 23, X1 - X0, 1, ST[1]);
  const t1 = 'SUPERIOR COURT OF CALIFORNIA', t2 = 'COUNTY OF LOS ANGELES';
  const cxm = ((X0 + X1) >> 1);
  // engraved: dark letter with lit lower edge
  const eng = (txt, y) => {
    const x = cxm - (text3W(txt) >> 1);
    text3(b, txt, x, y + 1, ST[5]);
    text3(b, txt, x, y, ST[1]);
  };
  eng(t1, top + 6); eng(t2, top + 15);
  // colonnade
  const colTop = top + 26, colBot = 166;
  fill(b, X0, colTop, X1 - X0, colBot - colTop, ST[1]); // deep shadow behind columns
  // windows/doors deep inside the portico
  for (let x = X0 + 12; x < X1 - 8; x += 26) {
    fill(b, x, colTop + 16, 12, 44, NE[2]); fill(b, x + 1, colTop + 17, 10, 42, R.blue[1]);
    G.dither(b, x + 1, colTop + 17, 10, 20, GO[2], 3);
    fill(b, x + 5, colTop + 17, 1, 42, NE[2]); fill(b, x + 1, colTop + 37, 10, 1, NE[2]);
  }
  // central bronze doors
  fill(b, cxm - 14, colTop + 30, 28, 46, GO[1]); fill(b, cxm - 12, colTop + 32, 11, 44, GO[2]); fill(b, cxm + 1, colTop + 32, 11, 44, GO[2]);
  G.dither(b, cxm - 12, colTop + 32, 24, 10, GO[3], 4);
  // columns
  for (let x = X0 + 4; x < X1; x += 26) {
    const w = 12;
    for (let y = colTop; y < colBot; y++) for (let i = 0; i < w; i++) {
      let col = ST[3];
      if (i < 1) col = ST[3]; else if (i < 3) col = ST[5]; else if (i < 6) col = ST[4]; else if (i < 9) col = ST[3]; else if (i < 11) col = ST[2]; else col = ST[1];
      if ((i === 3 || i === 6 || i === 9) && y > colTop + 6 && y < colBot - 6) col = shade(col, -1); // flutes
      px(b, x + i, y, col);
    }
    // capital & base
    fill(b, x - 2, colTop, w + 4, 4, ST[4]); fill(b, x - 2, colTop, w + 4, 1, ST[5]); fill(b, x - 2, colTop + 3, w + 4, 1, ST[2]);
    fill(b, x - 2, colBot - 4, w + 4, 4, ST[4]); fill(b, x - 2, colBot - 4, w + 4, 1, ST[5]);
    // warm light on the right edge (sun)
    fill(b, x + 1, colTop + 4, 1, colBot - colTop - 8, GO[5]);
  }
  // stylobate + steps
  for (let k = 0; k < 6; k++) {
    const y = colBot + k * 3, ext = k * 6;
    fill(b, X0 - 6 - ext, y, X1 - X0 + 6 + ext, 3, ST[4]); fill(b, X0 - 6 - ext, y, X1 - X0 + 6 + ext, 1, ST[5]);
    fill(b, X0 - 6 - ext, y + 2, X1 - X0 + 6 + ext, 1, ST[2]);
  }
  // plaza
  for (let y = 184; y < SH; y++) for (let x = 0; x < SW; x++) {
    let col = ST[2];
    if ((x + y * 2) % 24 === 0 || y % 8 === 0) col = ST[1];
    else if (h2(x, y) < 0.05) col = ST[3];
    px(b, x, y, col);
  }
  // long shadows of columns across plaza (sun from right)
  b.globalAlpha = 0.25; for (let x = X0 + 4; x < SW; x += 26) G.poly(b, [[x, 184], [x + 12, 184], [x + 52, SH], [x + 36, SH]], P.shadow); b.globalAlpha = 1;
  // building's left side face (in shade), gives depth
  for (let y = top - 16; y < 184; y++) for (let x = X0 - 14; x < X0 - 6; x++) {
    const d = (X0 - 6 - x); if (y < top - 16 + d) continue;
    px(b, x, y, ((y - top) % 8 === 0) ? ST[1] : (x === X0 - 7 ? ST[4] : ST[2]));
  }
  // planters with agaves along the steps
  for (const px0 of [148, 340]) {
    fill(b, px0, 174, 22, 10, ST[3]); fill(b, px0, 174, 22, 1, ST[5]); fill(b, px0 + 21, 174, 1, 10, ST[1]);
    for (let k = 0; k < 7; k++) G.line(b, px0 + 11, 174, px0 + 2 + k * 3, 162 + Math.abs(3 - k) * 2, R.teal[3 + (k & 1)]);
  }
  // lamp posts by the steps
  for (const lx of [118, 368]) {
    fill(b, lx, 140, 3, 46, NE[1]); fill(b, lx - 3, 184, 9, 3, NE[1]);
    fill(b, lx - 2, 132, 7, 9, NE[1]); fill(b, lx - 1, 133, 5, 6, GO[5]); px(b, lx, 134, P.white);
  }
  // flagpole on the roof (centre)
  fill(b, cxm, 10, 2, top - 18, NE[6]); fill(b, cxm + 1, 10, 1, top - 18, NE[4]); fill(b, cxm - 1, 8, 4, 2, GO[4]);
  // palm trees (foreground, left and far right)
  const palms = G.makeCanvas(SW, SH), pl = palms.getContext('2d');
  const palm = (x, yb, h, lean) => {
    for (let y = 0; y < h; y++) {
      const xx = x + Math.round(lean * (y / h) * (y / h) * 12);
      fill(pl, xx, yb - y, 3, 1, (y % 4 === 0) ? WD[1] : WD[2]); px(pl, xx + 2, yb - y, WD[0]);
      if (y % 4 === 0) px(pl, xx - 1, yb - y, WD[3]);
    }
    return [x + Math.round(lean * 12), yb - h];
  };
  const heads = [palm(22, 200, 150, 1), palm(64, 196, 118, -0.6), palm(100, 190, 80, 0.4)];
  const fronds = (c, hx, hy, ph, sc) => {
    for (let k = 0; k < 9; k++) {
      const a = -Math.PI * 0.95 + k * (Math.PI * 1.9 / 8) + Math.sin(ph + k) * 0.06;
      const len = (16 + (k % 3) * 4) * sc;
      let px0 = hx, py0 = hy;
      for (let i = 1; i <= len; i++) {
        const droop = (i / len) * (i / len) * 10 * sc;
        const xx = Math.round(hx + Math.cos(a) * i), yy = Math.round(hy + Math.sin(a) * i * 0.6 + droop);
        G.line(c, px0, py0, xx, yy, k % 2 ? R.green[2] : R.green[3]);
        const lf = Math.round(4 * sc * Math.sin(i / len * Math.PI));
        if (i > 2) for (let q = 1; q <= lf; q++) { px(c, xx - (q >> 1), yy + q, (q & 1) ? R.green[1] : R.green[2]); px(c, xx + (q >> 1), yy + q, R.green[1]); }
        if (i % 3 === 0) px(c, xx, yy - 1, R.green[4]);
        px0 = xx; py0 = yy;
      }
    }
    G.ellipse(c, hx + 1, hy + 1, 3, 2, WD[1]);
  };
  return { sky, bl, palms, heads, fronds, cxm, top,
    clouds: [[20, 22, 60, 0.9], [150, 40, 44, 0.6], [260, 16, 70, 0.75], [90, 70, 50, 0.5]],
    birds: makeMotes(91, 6, [0, 10, SW, 80]) };
}
const CLOUDS = {};
function cloudSprite(w) {
  if (CLOUDS[w]) return CLOUDS[w];
  const h = Math.round(w * 0.32);
  const spr = G.makeSprite(w, h, c => {
    const r = G.rng(w * 13);
    const puffs = [];
    for (let i = 0; i < 7; i++) puffs.push([Math.round(w * (0.12 + r() * 0.76)), Math.round(h * (0.45 + r() * 0.3)), Math.round(h * (0.22 + r() * 0.25))]);
    puffs.push([w >> 1, Math.round(h * 0.45), Math.round(h * 0.42)]);
    const inside = (x, y) => puffs.some(([px0, py0, pr]) => (x - px0) ** 2 + ((y - py0) * 1.4) ** 2 < pr * pr * 1.4) || (y > h * 0.62 && y < h * 0.82 && x > w * 0.08 && x < w * 0.92);
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      if (!inside(x, y)) continue;
      // shading: lit from the lower-left (setting sun), warm underside
      const up = !inside(x, y - 2), dn = !inside(x, y + 2), lf = !inside(x - 3, y);
      let col = P.sky2;
      if (dn) col = (G.bayer(x, y) < 8) ? R.red[5] : GO[5];
      else if (lf) col = GO[5];
      else if (up) col = P.white;
      else if (y > h * 0.6) col = (G.bayer(x, y) < 6) ? GO[5] : P.sky2;
      else if (G.bayer(x, y) < 3 && x > w * 0.6) col = R.blue[6];
      px(c, x, y, col);
    }
  });
  CLOUDS[w] = spr; return spr;
}
function cloud(c, x, y, w) { c.drawImage(cloudSprite(w), x, y - Math.round(w * 0.16)); }
let EX = null;
E._exterior = function (ctx, t) {
  if (!EX) EX = buildExterior();
  ctx.drawImage(EX.sky, 0, 0);
  // drifting clouds (wrap)
  for (const [x, y, w, sp] of EX.clouds) {
    const xx = Math.round(((x + t * sp * 2) % (SW + w + 40)) - w - 20 + 40);
    cloud(ctx, xx, y, w);
  }
  ctx.drawImage(EX.bl, 0, 0);
  // waving flag on the roof pole
  const fx = EX.cxm + 2, fy = 11;
  for (let x = 0; x < 22; x++) {
    const wv = Math.round(Math.sin(t * 5 - x * 0.45) * (x / 22) * 2.5);
    for (let y = 0; y < 13; y++) {
      let col = (Math.floor(y / 2) % 2 === 0) ? R.red[3] : NE[8];
      if (x < 9 && y < 7) col = ((x + y) % 3 === 0) ? NE[9] : R.blue[3];
      if (Math.sin(t * 5 - x * 0.45) > 0.5) col = shade(col, -1);
      px(ctx, fx + x, fy + y + wv, col);
    }
  }
  // palms sway
  ctx.drawImage(EX.palms, 0, 0);
  EX.heads.forEach(([hx, hy], i) => EX.fronds(ctx, hx, hy, t * 0.9 + i * 2, i === 0 ? 1.4 : i === 1 ? 1.1 : 0.9));
  // birds gliding (V shapes)
  for (const m of EX.birds) {
    const x = ((m.x * SW + t * 14 * m.sp) % (SW + 20)) - 10, y = 14 + m.y * 70 + Math.sin(t * 0.8 + m.ph) * 4;
    const fl = Math.floor(t * 6 + m.ph * 3) % 2;
    const X = Math.round(x), Y = Math.round(y);
    px(ctx, X, Y, NE[2]); px(ctx, X - 1, Y - fl, NE[2]); px(ctx, X + 1, Y - fl, NE[2]); px(ctx, X - 2, Y - 1 + fl * 0, NE[3]); px(ctx, X + 2, Y - 1, NE[3]);
  }
  // pigeons pecking on the steps / plaza
  [[178, 183], [196, 189], [300, 190], [252, 186]].forEach(([x, y], i) => {
    const peck = ((t * 1.3 + i * 0.7) % 2) < 0.3 ? 1 : 0;
    const walk = Math.round(Math.sin(t * 0.3 + i) * 3);
    const X = x + walk;
    fill(ctx, X, y - 3, 4, 3, NE[5]); px(ctx, X + 3, y - 3, NE[4]); fill(ctx, X + 1, y - 2, 2, 1, NE[6]);
    px(ctx, X - 1 + (i & 1 ? 5 : 0), y - 4 + peck * 2, NE[4]);
    px(ctx, X + 1, y, R.red[3]); px(ctx, X + 2, y, R.red[3]);
    px(ctx, X + (i & 1 ? 0 : 3), y - 4 + peck, R.teal[4]);
  });
};

/* expose for tests */
E._buildShots = function () {};
})();
