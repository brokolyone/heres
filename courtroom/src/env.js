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
  '-': '000000111000000', '&': '010101010101011',
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
    if (h2(x, y >> 1) < 0.04) return C(ramp, b + 1);
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
  drawSeal(bd.getContext('2d'), bd.width >> 1, 32, 12);
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
  box(b, 4.375, 0.0, 4.875, 0.125, 25, 52, { top: R.red[2], l: R.red[1], r: R.red[0], hl: R.red[3] });
  for (let k = 0; k < 4; k++) px(b, ix(4.375, 0.125) + 2 + k * 2, iy(4.375, 0.125, 50) + k + 1, GO[4]);
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
    box(b, gx - 0.25, gy - 0.125, gx + 0.25, gy, 0, 20, { top: NE[3], l: NE[2], r: NE[1], hl: NE[4] });
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
const FANS = [[5, 8.5, 156], [10.5, 9.5, 184]];
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
    wide: { x: 280, y: 172, z: 1 },
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
