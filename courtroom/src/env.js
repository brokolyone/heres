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
  WB = G.cacheCanvas('env/world/back', WW, WH, worldBack);
  WF = G.cacheCanvas('env/world/front', WW, WH, worldFront);
}
function worldBack(b) {

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

}
function worldFront(f) {
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
  SHAFT = G.cacheCanvas('env/world/shafts', WW, WH, shaftsFn);
}
function shaftsFn(c) {
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
    flagFrames.us.push(G.cacheCanvas('env/world/flag/us/' + i, 13, 26, c => c.drawImage(makeFlag('us', 11, 22, i * Math.PI / 2), 0, 0)));
    flagFrames.ca.push(G.cacheCanvas('env/world/flag/ca/' + i, 13, 26, c => c.drawImage(makeFlag('ca', 11, 22, i * Math.PI / 2 + 1), 0, 0)));
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
   CLOSE-UP SHOTS, OFFICE, HALLWAY, EXTERIOR
   Drawn at native 192x108, cached x2 (384x216) — matches the 2x busts.
   Animated details are drawn per frame in native coords under a x2 transform.
   ===================================================================== */
(function () {
'use strict';
const G = window.G, E = G.Env, Lb = E._lib;
const R = G.RAMP, P = G.PAL;
const WD = R.wood, ST = R.stone, NE = R.neutral, GO = R.gold, GR = R.green;
const { C, h2, fill, text3, text3W, moulding, shade } = Lb;
const px = G.px;
const NW = 192, NH = 108, SW = 384, SH = 216;
const SHOTS = E._SHOTS;
const WHITE = P.white;

/* cache a native-res drawing upscaled x2 */
function x2(key, w, h, fn) {
  return G.cacheCanvas(key, w * 2, h * 2, c => {
    const n = G.makeCanvas(w, h);
    fn(n.getContext('2d'), w, h);
    c.imageSmoothingEnabled = false;
    c.drawImage(n, 0, 0, w * 2, h * 2);
  });
}
function nat(ctx, fn) { ctx.save(); ctx.transform(2, 0, 0, 2, 0, 0); fn(ctx); ctx.restore(); }

/* ---------------- native drawing helpers ---------------- */
function grainCol(x, y, b, ramp) {
  ramp = ramp || WD;
  const g = (x * 7 + Math.floor(y / 9 + Math.sin(x * 0.45) * 2.5)) % 19;
  if (g === 0) return C(ramp, b - 1);
  if (g === 9 && (y % 7) < 3) return C(ramp, b - 1);
  return C(ramp, b);
}
function woodFill(c, x, y, w, h, b, ramp) {
  for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) px(c, x + i, y + j, grainCol(x + i, y + j, b, ramp));
}
/* raised panel with groove, bevels, grain and varnish glints */
function panel(c, x, y, w, h, b, ramp) {
  ramp = ramp || WD;
  if (w < 4 || h < 4) { fill(c, x, y, w, h, C(ramp, b)); return; }
  fill(c, x, y, w, 1, C(ramp, b - 2)); fill(c, x, y, 1, h, C(ramp, b - 2));
  fill(c, x, y + h - 1, w, 1, C(ramp, b + 1)); fill(c, x + w - 1, y, 1, h, C(ramp, b + 1));
  fill(c, x + 1, y + 1, w - 2, 1, C(ramp, b + 2)); fill(c, x + 1, y + 1, 1, h - 2, C(ramp, b + 1));
  fill(c, x + 1, y + h - 2, w - 2, 1, C(ramp, b - 1)); fill(c, x + w - 2, y + 1, 1, h - 2, C(ramp, b - 1));
  woodFill(c, x + 2, y + 2, w - 4, h - 4, b, ramp);
  px(c, x + 1, y + 1, C(ramp, b + 3));
  if (w > 8) { px(c, x + 2, y + 1, C(ramp, b + 3)); if (b + 3 >= ramp.length - 1) px(c, x + 2, y + 1, WHITE); }
}
function rosette(c, x, y) {
  px(c, x, y, WD[5]); px(c, x - 1, y, WD[3]); px(c, x + 1, y, WD[2]); px(c, x, y - 1, WD[4]); px(c, x, y + 1, WD[1]);
  px(c, x - 1, y - 1, WD[6]); px(c, x + 1, y + 1, WD[0]);
}
/* moulding with varnish glints on the brightest row */
function mould(c, x, y, w, idx, glint) {
  idx.forEach((k, j) => {
    fill(c, x, y + j, w, 1, C(WD, k));
    if (glint && k >= 5) for (let i = (x * 7 + j * 3) % 13; i < w; i += 17 + ((i * 3) % 7)) { px(c, x + i, y + j, WHITE); if (i + 1 < w) px(c, x + i + 1, y + j, WD[6]); }
  });
}
function plaster(c, x, y, w, h, b, topShade) {
  fill(c, x, y, w, h, ST[b]);
  if (topShade) { G.dither(c, x, y, w, topShade, ST[b - 1], 8); G.dither(c, x, y + topShade, w, topShade >> 1, ST[b - 1], 3); }
}
function brassGlint(c, x, y) { px(c, x, y, WHITE); }
function ditherRows(c, y0, y1, col, w) { for (let y = y0; y < y1; y++) G.dither(c, 0, y, w || NW, 1, col, Math.min(16, (y - y0) * 2)); }
function vignette(c, lv) {
  for (let i = 0; i < 3; i++) { G.dither(c, i * 2, 0, 2, NH, P.black, lv - i * 3); G.dither(c, NW - 2 - i * 2, 0, 2, NH, P.black, lv - i * 3); }
}
function beamFn(pts) {
  return c => {
    G.poly(c, pts, P.glow);
    const cx = pts.reduce((s, p) => s + p[0], 0) / pts.length, cy = pts.reduce((s, p) => s + p[1], 0) / pts.length;
    const m = G.makeCanvas(NW, NH), mx = m.getContext('2d');
    G.dither(mx, 0, 0, NW, NH, '#000', 8);
    mx.globalCompositeOperation = 'destination-out';
    G.poly(mx, pts.map(p => [cx + (p[0] - cx) * 0.78, cy + (p[1] - cy) * 0.95]), '#000');
    c.globalCompositeOperation = 'destination-out'; c.drawImage(m, 0, 0); c.globalCompositeOperation = 'source-over';
  };
}
function inPoly(pts, x, y) {
  let ins = false;
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const [xi, yi] = pts[i], [xj, yj] = pts[j];
    if (((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi)) ins = !ins;
  }
  return ins;
}
function motes(seed, n, area) { const r = G.rng(seed), a = []; for (let i = 0; i < n; i++) a.push({ x: r(), y: r(), sp: 0.3 + r() * 0.7, ph: r() * 6.28, area }); return a; }
function drawMotes(c, ms, t, poly) {
  for (const m of ms) {
    const [x0, y0, w, h] = m.area;
    const x = x0 + ((m.x * w + t * 1.4 * m.sp + Math.sin(t * 0.5 + m.ph) * 2) % w + w) % w;
    const y = y0 + ((m.y * h + t * 0.9 * m.sp + Math.sin(t * 0.3 + m.ph) * 2) % h + h) % h;
    if (poly && !inPoly(poly, x, y)) continue;
    c.globalAlpha = 0.25 + 0.25 * Math.sin(t * 2 + m.ph * 3);
    px(c, x | 0, y | 0, m.sp > 0.85 ? WHITE : P.glow);
  }
  c.globalAlpha = 1;
}
function shaftDraw(ctx, img, t, base) { ctx.globalAlpha = (base || 0.13) + 0.035 * Math.sin(t * 0.37) + 0.012 * Math.sin(t * 1.7); ctx.drawImage(img, 0, 0); ctx.globalAlpha = 1; }

/* Great Seal of California (native, r 6..24) */
function seal(c, cx, cy, r) {
  const band = Math.max(2, Math.round(r * 0.26));
  for (let y = -r; y <= r; y++) for (let x = -r; x <= r; x++) {
    const d = Math.sqrt(x * x + y * y);
    if (d > r + 0.3) continue;
    let col;
    if (d > r - 1) col = (x + y < -r * 0.5) ? GO[5] : GO[1];
    else if (d > r - band) {
      const a = Math.atan2(y, x), k = Math.floor((a + Math.PI) / (Math.PI * 2) * r * 2.6);
      col = (k % 2 === 0 && d < r - 1.4 && d > r - band + 0.6) ? GO[1] : (x + y < -r * 0.3 ? GO[4] : GO[3]);
    } else if (d > r - band - 1) col = GO[1];
    else {
      const ry = y / (r - band);
      if (ry < -0.2) col = (G.bayer(x, y) < 5) ? R.blue[5] : R.blue[6];
      else if (ry < 0.08) col = (Math.abs(x + r * 0.25) < (r - band) * 0.55 - (ry + 0.2) * r * 1.2) ? ST[4] : R.blue[5];
      else if (ry < 0.38) col = ((x + y) & 1) ? R.blue[4] : R.blue[3];
      else col = ((x * 2 + y) % 3) ? GO[3] : GO[2];
    }
    px(c, cx + x, cy + y, col);
  }
  const s = r / 12;
  // Minerva
  const mx = cx - Math.round(3 * s), my = cy + Math.round(3 * s);
  fill(c, mx, my - Math.round(7 * s), Math.max(2, Math.round(3 * s)), Math.round(8 * s), GO[4]);
  fill(c, mx, my - Math.round(7 * s), 1, Math.round(8 * s), GO[5]);
  G.ellipse(c, mx + 1, my - Math.round(9 * s), Math.max(1, Math.round(s)), Math.max(1, Math.round(s)), GO[4]);
  px(c, mx + 1, my - Math.round(11 * s), R.red[3]);
  G.ellipse(c, mx - Math.round(2 * s), my - Math.round(2 * s), Math.max(1, Math.round(2.2 * s)), Math.max(1, Math.round(2.2 * s)), GO[2]);
  px(c, mx - Math.round(2.5 * s), my - Math.round(2.6 * s), GO[5]);
  G.line(c, mx + Math.round(4 * s), my - Math.round(11 * s), mx + Math.round(4 * s), my + 1, GO[5]);
  // grizzly
  const bx = cx + Math.round(3 * s), by = cy + Math.round(5 * s);
  fill(c, bx, by - Math.round(2 * s), Math.round(6 * s), Math.max(2, Math.round(2.2 * s)), R.hairBrown[2]);
  fill(c, bx + Math.round(6 * s) - 1, by - Math.round(3 * s), Math.max(2, Math.round(1.6 * s)), Math.max(2, Math.round(1.6 * s)), R.hairBrown[2]);
  fill(c, bx, by - Math.round(2 * s), Math.round(6 * s), 1, R.hairBrown[3]);
  // star + rim glints
  px(c, cx, cy - r + band + 1, WHITE);
  px(c, cx - Math.round(r * 0.6), cy - Math.round(r * 0.75), WHITE); px(c, cx - Math.round(r * 0.72), cy - Math.round(r * 0.62), WHITE);
}
/* pole with eagle finial (native) */
function pole(c, x, y0, y1) {
  fill(c, x, y0, 2, y1 - y0, GO[3]); fill(c, x, y0, 1, y1 - y0, GO[5]);
  for (let y = y0 + 3; y < y1; y += 11) px(c, x, y, WHITE);
  fill(c, x - 1, y0 - 2, 4, 2, GO[4]); px(c, x - 1, y0 - 2, WHITE);
  px(c, x, y0 - 4, GO[4]); px(c, x + 1, y0 - 4, GO[3]); px(c, x, y0 - 5, GO[5]);
  G.line(c, x, y0 - 4, x - 4, y0 - 7, GO[3]); G.line(c, x + 1, y0 - 4, x + 5, y0 - 7, GO[2]);
  px(c, x - 3, y0 - 7, WHITE); px(c, x - 4, y0 - 7, GO[5]);
  fill(c, x - 2, y1 - 2, 6, 2, GO[2]); fill(c, x - 2, y1 - 2, 6, 1, GO[4]); px(c, x - 2, y1 - 2, WHITE);
}
/* draped flag sprite native */
function flagFn(kind, w, h, ph) {
  return c => {
    for (let x = 0; x < w; x++) {
      const f = Math.sin(x * 0.85 + ph) + 0.45 * Math.sin(x * 1.7 - ph * 1.3);
      const len = h - Math.round(x * x / (w * w) * h * 0.2) + Math.round(Math.sin(ph + x * 0.5));
      for (let y = 0; y < len; y++) {
        let col;
        if (kind === 'us') {
          if (x < w * 0.5 && y < h * 0.42) col = ((x % 2 === 1) && (y % 3 === 1 + (x >> 1) % 2)) ? WHITE : R.blue[2];
          else col = (Math.floor(y / (h / 13)) % 2 === 0) ? R.red[3] : NE[8];
        } else {
          col = NE[8];
          if (y > len - Math.max(3, h * 0.12)) col = R.red[3];
          const dx = x - w * 0.5, dy = y - h * 0.5;
          if (Math.abs(dx) < w * 0.3 && dy > -2 && dy < 2) col = R.hairBrown[2];
          if (Math.abs(dx + w * 0.26) < 1.5 && dy > -3 && dy < 0) col = R.hairBrown[2];
          if ((x === Math.round(w * 0.32) || x === Math.round(w * 0.66)) && dy >= 2 && dy < 4) col = R.hairBrown[1];
          if (dy >= 4 && dy < 5 && Math.abs(dx) < w * 0.4) col = R.green[3];
          if (x === 2 && y === 3) col = R.red[3];
        }
        if (f < -0.8) col = shade(shade(col, -1), -1); else if (f < -0.1) col = shade(col, -1);
        else if (f > 1.05) col = (col === NE[8]) ? WHITE : shade(col, 1);
        px(c, x, y, col);
      }
      px(c, x, len, (x & 1) ? GO[4] : GO[2]); if (x % 3 === 0) px(c, x, len, GO[5]);
    }
  };
}
function clockFace(c, cx, cy, r) {
  G.ellipse(c, cx + 1, cy + 1, r, r, NE[1]);
  G.ellipse(c, cx, cy, r, r, WD[1]); G.ellipse(c, cx, cy, r - 1, r - 1, GO[3]); G.ellipse(c, cx, cy, r - 2, r - 2, NE[9]);
  for (let i = 0; i < 12; i++) { const a = i / 12 * Math.PI * 2; px(c, cx + Math.round(Math.sin(a) * (r - 3)), cy - Math.round(Math.cos(a) * (r - 3)), i % 3 ? NE[6] : NE[2]); }
  px(c, cx - r + 1, cy - 2, WHITE); px(c, cx - r + 2, cy - 3, WHITE); px(c, cx - 2, cy - r + 1, GO[5]);
}
function clockHandsN(ctx, cx, cy, r, t) {
  const a = Lb.clockHands(t);
  const hand = (ang, l, col) => { for (let i = 1; i <= l; i++) px(ctx, cx + Math.round(Math.sin(ang) * i), cy - Math.round(Math.cos(ang) * i), col); };
  hand(a.h, Math.max(1, r - 5), NE[1]); hand(a.m, r - 3, NE[1]); hand(a.s, r - 3, R.red[3]); px(ctx, cx, cy, GO[2]);
}
function windowN(c, x, y, w, h, palms) {
  fill(c, x - 2, y - 2, w + 4, h + 4, WD[2]); fill(c, x - 2, y - 2, w + 4, 1, WD[4]); fill(c, x - 2, y - 2, 1, h + 4, WD[4]);
  for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) {
    const f = j / h; let col = f < 0.33 ? P.sky : f < 0.68 ? P.sky2 : P.glow;
    if (f > 0.28 && f < 0.33 && G.bayer(i, j) < 8) col = P.sky2;
    if (f > 0.63 && f < 0.68 && G.bayer(i, j) < 8) col = P.glow;
    px(c, x + i, y + j, col);
  }
  if (palms) {
    const p1 = x + Math.round(w * 0.3), ty = y + Math.round(h * 0.3);
    for (let j = ty; j < y + h; j++) px(c, p1 + (((j - ty) / 6) | 0) % 2, j, R.green[2]);
    [[-6, 2], [-5, 4], [5, 1], [6, 4], [-2, 5], [3, 5]].forEach(([dx, dy]) => G.line(c, p1, ty, p1 + dx, ty + dy, R.green[2]));
  }
  // glare streaks
  for (let k = 0; k < Math.min(h, w) - 2; k++) { if (k % 2 === 0) px(c, x + 2 + k, y + h - 3 - k, WHITE); }
  fill(c, x + (w >> 1), y, 1, h, WD[2]); for (let j = y + 8; j < y + h; j += 9) fill(c, x, j, w, 1, WD[2]);
  fill(c, x, y, w, 3, ST[4]); fill(c, x, y + 1, w, 1, ST[3]); fill(c, x, y + 3, w, 1, ST[2]);
  fill(c, x - 3, y + h + 1, w + 6, 2, WD[4]); fill(c, x - 3, y + h + 1, w + 6, 1, WD[5]); px(c, x - 2, y + h + 1, WHITE);
}
function glassN(c, x, y, h, full) {
  fill(c, x, y - h, 4, h, R.blue[5]); fill(c, x + 3, y - h, 1, h, R.blue[4]);
  if (full) { fill(c, x + 1, y - Math.round(h * 0.6), 2, Math.round(h * 0.6), R.blue[6]); fill(c, x, y - Math.round(h * 0.6), 4, 1, NE[9]); }
  fill(c, x, y - h, 4, 1, NE[8]); px(c, x, y - h + 1, WHITE); px(c, x, y - h + 2, WHITE); px(c, x + 1, y - 1, NE[9]);
}
function pitcherN(c, x, y) {
  for (let j = 0; j < 12; j++) {
    const w = 3 + Math.round(Math.sin(j / 12 * Math.PI) * 1.2);
    for (let i = -w; i <= w; i++) {
      let col = NE[6];
      if (i === -w) col = NE[7]; else if (i === -w + 1) col = NE[8]; else if (i >= w - 1) col = NE[4]; else if (i === w - 2) col = NE[5];
      px(c, x + i, y - 12 + j, col);
    }
  }
  fill(c, x - 3, y - 13, 7, 1, NE[7]); px(c, x - 4, y - 13, NE[7]); px(c, x - 5, y - 14, NE[6]);
  fill(c, x - 2, y - 10, 1, 6, WHITE); px(c, x - 1, y - 9, WHITE);
  fill(c, x + 5, y - 11, 1, 7, NE[4]); px(c, x + 4, y - 11, NE[5]); px(c, x + 4, y - 5, NE[4]);
}
function legalPadN(c, x, y, w, h, seed, rot) {
  // slight perspective: rows get wider toward the viewer
  for (let j = 0; j < h; j++) {
    const o = Math.round((h - j) * (rot || 0.2));
    fill(c, x + o, y + j, w - o * 2 + Math.round(j * 0.1), 1, j < 2 ? R.red[2] : GO[5]);
    if (j >= 3 && j % 2 === 1) fill(c, x + o + 1, y + j, w - o * 2 - 2, 1, GO[4]);
  }
  const r = G.rng(seed || 3);
  for (let j = 3; j < h - 1; j += 2) {
    const o = Math.round((h - j) * (rot || 0.2));
    let i = 2; const end = (w - o * 2) * (0.45 + r() * 0.45);
    while (i < end) { const wl = 2 + Math.floor(r() * 4); for (let k = 0; k < wl && i < end; k++, i++) px(c, x + o + i, y + j - 1 + ((k + (r() < 0.3 ? 1 : 0)) & 1), P.ink); i += 1; }
  }
  fill(c, x, y + h, w, 1, GO[2]); px(c, x + Math.round(h * (rot || 0.2)), y + 1, WHITE);
}
function penN(c, x, y, len, col) { fill(c, x, y, len, 1, col || P.inkDark); px(c, x + len - 1, y, GO[4]); px(c, x + 1, y - 1, NE[6]); px(c, x, y, NE[7]); fill(c, x + 1, y + 1, len - 1, 1, NE[1]); }
function stickyN(c, x, y, col) { fill(c, x, y, 4, 4, col); fill(c, x, y + 4, 4, 1, shade(col, -1)); px(c, x, y, WHITE); fill(c, x + 1, y + 2, 2, 1, NE[3]); }
function laptopBackN(c, x, y) {
  fill(c, x, y - 14, 22, 14, NE[5]); fill(c, x, y - 14, 22, 1, NE[8]); fill(c, x, y - 14, 1, 14, NE[7]);
  fill(c, x + 21, y - 14, 1, 14, NE[3]); px(c, x + 1, y - 13, WHITE); px(c, x + 2, y - 13, WHITE);
  G.ellipse(c, x + 11, y - 7, 2, 2, NE[6]); px(c, x + 10, y - 8, WHITE);
  fill(c, x - 2, y, 26, 2, NE[4]); fill(c, x - 2, y, 26, 1, NE[7]); px(c, x - 1, y, WHITE);
}
function folderStackN(c, x, y, n, seed) {
  const r = G.rng(seed);
  for (let i = 0; i < n; i++) {
    const dx = Math.round(r() * 2 - 1), ramp = i % 3 === 1 ? [GO, R.blue, R.red, R.stone][Math.floor(r() * 4)] : R.paper;
    const yy = y - i * 2;
    fill(c, x + dx, yy - 1, 24, 1, C(ramp, 3)); fill(c, x + dx + 1, yy, 24, 1, C(ramp, 1));
    if (ramp === R.paper) px(c, x + dx + 2, yy - 1, WHITE);
    if (r() < 0.5) fill(c, x + dx + 8 + Math.floor(r() * 10), yy - 2, 3, 1, [R.red[3], R.blue[4], GR[4], GO[4]][i % 4]);
  }
  fill(c, x + 14, y - n * 2, 1, n * 2 + 1, R.red[3]);
}
function tentCard(c, x, y, txt) {
  const w = text3W(txt) + 4;
  fill(c, x, y - 7, w, 7, NE[8]); fill(c, x, y - 7, w, 1, WHITE); fill(c, x, y - 1, w, 1, NE[6]);
  text3(c, txt, x + 2, y - 6, NE[2]);
}
/* desk top in perspective + front (native) */
function deskN(c, y0, y1, x0, x1, b) {
  for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) {
    let col = grainCol(x, y * 3, b);
    if (y === y0) col = C(WD, b - 1);
    px(c, x, y, col);
  }
  // reflections of windows on polished top
  for (let x = x0; x < x1; x++) if (((x / 9) | 0) % 5 === 1) px(c, x, y1 - 2, C(WD, b + 1));
  fill(c, x0, y1, x1 - x0, 1, WD[6]);
  for (let x = x0 + 3; x < x1; x += 19) { px(c, x, y1, WHITE); px(c, x + 1, y1, WHITE); }
  fill(c, x0, y1 + 1, x1 - x0, 1, C(WD, b + 1)); fill(c, x0, y1 + 2, x1 - x0, 1, C(WD, b - 1));
  fill(c, x0, y1 + 3, x1 - x0, NH - y1 - 3, C(WD, b - 2));
  for (let x = x0 + 3; x + 20 < x1 + 3; x += 24) { panel(c, x, y1 + 5, 20, NH - y1 - 4, b - 1); rosette(c, x + 22, y1 + 8); }
}

/* ---------------- small pixel people (native) ---------------- */
const HEADS = {
  s: { rows: [2, 3, 3, 3, 3, 3, 3, 2], ey: 4, sw: 6, H: 20 },
  m: { rows: [2, 3, 4, 4, 4, 4, 4, 4, 3, 2], ey: 5, sw: 8, H: 26 },
};
function personFn(o, frame) {
  const S = HEADS[o.size || 'm'];
  const W = S.sw * 2 + 6, H = S.H;
  return [W, H, c => {
    const d = o.dim || 0;
    const sk = i => C(o.skin, i - d), hr = i => C(o.hair, i - d), cl = i => C(o.cloth, i - d);
    const cx = W >> 1, hy = 2, hh = S.rows.length;
    const look = frame === 2 ? (o.look || -1) : 0;
    const hx = cx + (frame === 2 ? (o.look || -1) * 0 : 0);
    // long hair behind
    if (o.style === 'long') fill(c, hx - S.rows[3] - 1, hy + 3, S.rows[3] * 2 + 3, hh + 2, hr(2));
    // body
    const by = hy + hh + 1;
    for (let y = by; y < H; y++) {
      const k = y - by, half = Math.min(S.sw, 2 + k * 3);
      for (let x = -half; x <= half; x++) {
        let col = cl(3);
        if (x <= -half + 1) col = cl(4); else if (x >= half - 1) col = cl(2);
        if (k === 0 || (k === 1 && Math.abs(x) > half - 3)) col = cl(4);
        px(c, cx + x, y, col);
      }
    }
    if (o.lapel) { for (let k = 0; k < 4; k++) { px(c, cx - 1 - (k >> 1), by + 1 + k, cl(2)); px(c, cx + 1 + (k >> 1), by + 1 + k, cl(2)); } }
    if (o.collar) { px(c, cx - 1, by, o.collar); px(c, cx + 1, by, o.collar); px(c, cx, by + 1, o.collar); px(c, cx - 1, by + 1, o.collar); }
    if (o.tie) fill(c, cx, by + 1, 1, 5, o.tie);
    if (o.pearls) for (let x = -2; x <= 2; x++) px(c, cx + x, by + 1 + (Math.abs(x) < 2 ? 1 : 0), WHITE);
    // neck
    fill(c, cx - 1, hy + hh - 1, 3, 2, sk(1));
    // head
    S.rows.forEach((hw, j) => {
      for (let x = -hw; x <= hw - 1; x++) {
        let col = sk(2);
        if (x === -hw) col = sk(3); else if (x === hw - 1) col = sk(1);
        if (j >= hh - 2 && x > 0) col = sk(1);
        px(c, hx + x, hy + j, col);
      }
    });
    px(c, hx + S.rows[4], hy + S.ey, sk(1)); // ear
    // hair
    const top = o.style === 'bald' ? 0 : (o.size === 's' ? 2 : 3);
    if (o.style !== 'bald') {
      for (let j = -1; j < top; j++) {
        const hw = j < 0 ? S.rows[0] : S.rows[j] + (j > 0 ? 1 : 0);
        for (let x = -hw; x <= hw - 1; x++) px(c, hx + x, hy + j, (x < -hw / 2 && j < 1) ? hr(4) : (x >= hw - 2 ? hr(1) : hr(3)));
      }
      // fringe / side part
      px(c, hx - S.rows[3] + 1, hy + top, hr(3)); px(c, hx - S.rows[3] + 2, hy + top, hr(2));
      if (o.style === 'bob' || o.style === 'long' || o.style === 'curly') {
        const sideLen = o.style === 'curly' ? hh - 3 : hh - 2;
        fill(c, hx - S.rows[3] - 1, hy + 1, 2, sideLen, hr(3)); px(c, hx - S.rows[3] - 1, hy + 1, hr(4));
        fill(c, hx + S.rows[3] - 1, hy + 1, 2, sideLen, hr(1));
      }
      if (o.style === 'curly') for (let x = -S.rows[0] - 2; x <= S.rows[0] + 1; x += 2) { px(c, hx + x, hy - 2, hr(3)); px(c, hx + x, hy - 1, hr(4)); }
      if (o.style === 'bun') { fill(c, hx - 1, hy - 3, 3, 2, hr(3)); px(c, hx - 1, hy - 3, hr(4)); }
      if (o.style === 'cap') { fill(c, hx - S.rows[2] - 1, hy - 1, S.rows[2] * 2 + 1, 3, o.capCol || R.blue[3]); fill(c, hx - S.rows[2] - 3, hy + 2, S.rows[2] + 2, 1, o.capCol2 || R.blue[2]); px(c, hx - 2, hy - 1, WHITE); }
      if (o.style === 'grey') { /* receding */ }
    } else {
      px(c, hx - 2, hy, sk(4)); px(c, hx - 1, hy, WHITE);
      fill(c, hx - S.rows[3], hy + 2, 1, 3, C(R.hairGrey, 2)); fill(c, hx + S.rows[3] - 1, hy + 2, 1, 3, C(R.hairGrey, 1));
    }
    // face
    const ey = hy + S.ey, ex1 = hx - 2 + look, ex2 = hx + 1 + look;
    if (frame === 1) { px(c, ex1, ey, sk(1)); px(c, ex2, ey, sk(1)); }
    else { px(c, ex1, ey, NE[1]); px(c, ex2, ey, NE[1]); }
    if (o.glasses) { px(c, ex1 - 1, ey, o.glasses); px(c, ex2 + 1, ey, o.glasses); px(c, hx + look, ey - 1, o.glasses); px(c, ex1, ey - 1, WHITE); }
    else if (o.size !== 's') { px(c, ex1, ey - 1, hr(1)); px(c, ex2, ey - 1, hr(1)); }
    px(c, hx + look - (look < 0 ? 1 : 0), ey + 2, sk(1)); // nose shadow
    if (o.beard) { fill(c, hx - S.rows[6] + 1, hy + hh - 3, S.rows[6] * 2 - 2, 2, hr(2)); px(c, hx - 1, hy + hh - 3, sk(1)); }
    if (o.lips) px(c, hx + look, ey + 3, o.lips);
    if (frame === 2) px(c, hx + look, ey + 3 + (o.size === 's' ? 0 : 1), R.red[1]);
    if (o.earring) px(c, hx + S.rows[4], hy + S.ey + 2, WHITE);
  }];
}
function people(key, list) {
  return list.map((p, i) => {
    const fr = [0, 1, 2].map(f => { const [w, h, fn] = personFn(p.o, f); return x2(key + '/p' + i + '/f' + f, w, h, fn); });
    return Object.assign({ i, fr }, p);
  });
}
function drawPeople(ctx, list, t) { // ctx in screen space (cached sprites are x2)
  for (const p of list) {
    const ph = p.i * 1.37 + p.x * 0.11;
    const breath = Math.sin(t * 2.0 + ph) > 0.55 ? 1 : 0;
    const blink = ((t + ph) % 3.9) < 0.14;
    const cyc = (t + ph * 3) % 7.7;
    const whisper = p.whisper && cyc < 1.8;
    const turn = whisper || ((t * 0.6 + ph) % 9.5) < 1.3;
    const fr = blink ? 1 : turn ? 2 : 0;
    const lean = whisper ? (p.o.look || -1) : 0;
    const shift = (((t * 0.21 + ph) % 6) < 0.8) ? (p.o.look || -1) : 0;
    const spr = p.fr[fr];
    ctx.drawImage(spr, (p.x + lean + shift) * 2 - (spr.width >> 1), (p.y + breath) * 2 - spr.height);
  }
}
const SKINS = [R.skinL, R.skinM, R.skinD];
const LOOKS = [
  { style: 'bun', skin: R.skinL, hair: R.hairGrey, cloth: R.purple, glasses: NE[2], earring: 1 },
  { style: 'short', skin: R.skinD, hair: R.hairBlack, cloth: R.stone, tie: R.red[2], collar: NE[8], lapel: 1 },
  { style: 'long', skin: R.skinL, hair: R.hairBlond, cloth: R.teal, lips: R.red[2] },
  { style: 'bald', skin: R.skinM, hair: R.hairBrown, cloth: R.green, beard: 1 },
  { style: 'curly', skin: R.skinD, hair: R.hairBlack, cloth: R.gold },
  { style: 'cap', skin: R.skinL, hair: R.hairRed, cloth: R.red },
  { style: 'bob', skin: R.skinM, hair: R.hairBlack, cloth: R.blue, glasses: NE[1], pearls: 1 },
  { style: 'short', skin: R.skinL, hair: R.hairBrown, cloth: NE, collar: NE[8], lapel: 1, tie: R.blue[3] },
  { style: 'bob', skin: R.skinL, hair: R.hairRed, cloth: R.green, lips: R.red[2] },
  { style: 'short', skin: R.skinM, hair: R.hairGrey, cloth: R.wood, glasses: GO[2] },
  { style: 'long', skin: R.skinD, hair: R.hairBrown, cloth: R.purple, earring: 1 },
  { style: 'short', skin: R.skinL, hair: R.hairBlack, cloth: R.blue, collar: NE[8] },
];
function look(i, extra) { return Object.assign({}, LOOKS[i % LOOKS.length], extra); }

/* ---------------- shot registry ---------------- */
const SH_INFO = E.shots;
Object.assign(SH_INFO, {
  judge: { anchor: { x: 192, y: 184 }, flip: false },
  witness: { anchor: { x: 210, y: 184 }, flip: false },
  defense: { anchor: { x: 120, y: 186 }, flip: true },
  prosecution: { anchor: { x: 264, y: 186 }, flip: false },
  jury: { anchor: { x: 192, y: 190 }, flip: false, extras: [] },
  visit: { anchor: { x: 196, y: 186 }, flip: false },
  defendant: { anchor: { x: 236, y: 188 }, flip: false },
  office: { anchor: { x: 128, y: 216 }, flip: true, extras: [{ x: 276, y: 216, flip: false }] },
  hallway: { anchor: { x: 140, y: 216 }, flip: true, extras: [{ x: 262, y: 216, flip: false }] },
});
const BUILT = {};
function get(id, builder) { return BUILT[id] || (BUILT[id] = builder()); }

/* ======================= JUDGE ======================= */
function buildJudge() {
  const K = 'env/shot/judge/';
  const SHP = [[0, 0], [34, 0], [112, 76], [62, 76]];
  return {
    back: x2(K + 'back', NW, NH, b => {
      woodFill(b, 0, 0, NW, NH, 1);
      // side wings (darker), stacked panels
      for (const x0 of [0, 162]) { panel(b, x0 + 3, 14, 24, 30, 1); panel(b, x0 + 3, 47, 24, 24, 1); rosette(b, x0 + 15, 45); }
      // pilasters
      for (const x of [33, 151]) {
        fill(b, x, 8, 8, 70, WD[3]); fill(b, x, 8, 1, 70, WD[5]); fill(b, x + 7, 8, 1, 70, WD[1]);
        for (let k = 0; k < 3; k++) { fill(b, x + 2 + k * 2, 13, 1, 60, WD[1]); fill(b, x + 3 + k * 2, 13, 1, 60, WD[4]); }
        for (let y = 16; y < 70; y += 13) px(b, x + 1, y, WHITE);
        mould(b, x - 1, 8, 10, [6, 5, 3, 1], true); fill(b, x - 1, 76, 10, 2, WD[4]);
      }
      // central backdrop frame
      fill(b, 43, 10, 106, 68, WD[2]);
      panel(b, 45, 12, 102, 64, 2);
      // cornice
      mould(b, 0, 0, NW, [0, 3, 6, 5, 3, 1], true);
      for (let x = 1; x < NW; x += 3) { fill(b, x, 6, 2, 2, WD[4]); px(b, x, 6, WD[6]); px(b, x + 1, 7, WD[1]); }
      mould(b, 0, 8, NW, [0, 2], false);
      // halo shadow + seal
      b.globalAlpha = 0.35; G.ellipse(b, 98, 38, 23, 23, P.shadow); b.globalAlpha = 1;
      seal(b, 96, 36, 22);
      // "IN GOD WE TRUST" small brass letters above
      // poles
      pole(b, 18, 14, 76); pole(b, 172, 14, 76);
      // under-bench shadow
      ditherRows(b, 66, 76, P.black);
      vignette(b, 8);
    }),
    flags: [0, 1, 2, 3].map(i => [x2(K + 'flag/us/' + i, 16, 50, flagFn('us', 16, 46, i * 1.57)), x2(K + 'flag/ca/' + i, 16, 50, flagFn('ca', 16, 46, i * 1.57 + 0.8))]),
    shaft: x2(K + 'shaft', NW, NH, beamFn(SHP)), shp: SHP, motes: motes(11, 26, [0, 0, 112, 76]),
    front: x2(K + 'front', NW, NH, f => {
      // bench top: overhanging cornice
      mould(f, 0, 70, NW, [6, 5, 4, 3], true);
      fill(f, 0, 74, NW, 3, WD[2]);
      for (let x = 0; x < NW; x += 4) { fill(f, x, 74, 3, 2, WD[3]); px(f, x, 74, WD[5]); }
      mould(f, 0, 77, NW, [1, 0, 3], false);
      fill(f, 0, 80, NW, NH - 80, WD[2]);
      for (let x = 3; x < NW; x += 32) { panel(f, x, 82, 28, 26, 3); rosette(f, x + 30, 85); }
      // banker's lamp
      const lx = 13;
      fill(f, lx - 4, 67, 10, 3, GO[2]); fill(f, lx - 4, 67, 10, 1, GO[4]); px(f, lx - 3, 67, WHITE);
      fill(f, lx, 59, 1, 8, GO[4]); px(f, lx, 60, WHITE);
      G.poly(f, [[lx - 8, 59], [lx + 9, 59], [lx + 7, 54], [lx - 6, 54]], GR[3]);
      fill(f, lx - 6, 54, 13, 1, GR[5]); fill(f, lx - 8, 58, 17, 1, GR[2]); px(f, lx - 4, 55, WHITE); px(f, lx - 3, 55, GR[6]);
      fill(f, lx - 7, 59, 15, 1, P.glow);
      // gavel + sound block
      const gx = 36;
      fill(f, gx - 6, 67, 13, 3, WD[1]); fill(f, gx - 6, 67, 13, 1, WD[4]); px(f, gx - 5, 67, WD[6]);
      fill(f, gx - 12, 62, 8, 4, WD[3]); fill(f, gx - 12, 62, 8, 1, WD[5]); px(f, gx - 11, 62, WHITE); fill(f, gx - 12, 65, 8, 1, WD[1]);
      px(f, gx - 11, 63, GO[4]); px(f, gx - 6, 63, GO[4]);
      G.line(f, gx - 4, 64, gx + 9, 66, WD[4]); G.line(f, gx - 4, 65, gx + 9, 67, WD[1]);
      // nameplate
      const nx = 122, ny = 60, tw = text3W('HON. H. WHITAKER');
      fill(f, nx - 2, 68, tw + 10, 2, WD[1]); fill(f, nx - 2, 68, tw + 10, 1, WD[4]);
      fill(f, nx, ny, tw + 6, 8, GO[3]); fill(f, nx, ny, tw + 6, 1, GO[5]); fill(f, nx, ny + 7, tw + 6, 1, GO[1]);
      fill(f, nx, ny, 1, 8, GO[4]); fill(f, nx + tw + 5, ny, 1, 8, GO[2]);
      px(f, nx + 1, ny + 1, WHITE); px(f, nx + 2, ny + 1, WHITE); px(f, nx + 12, ny, WHITE);
      text3(f, 'HON. H. WHITAKER', nx + 3, ny + 2, GO[1]);
      px(f, nx + 1, ny + 4, GO[1]); px(f, nx + tw + 4, ny + 4, GO[1]); // screws
      // papers + pen on bench
      fill(f, 52, 68, 16, 2, R.paper[4]); fill(f, 53, 67, 15, 1, R.paper[3]); px(f, 52, 68, WHITE); penN(f, 60, 69, 8);
    }),
  };
}
SHOTS.judge = function (ctx, layer, t) {
  const S = get('judge', buildJudge);
  if (layer === 'back') {
    ctx.drawImage(S.back, 0, 0);
    const k = Math.floor(t * 1.3) % 4, k2 = (k + 1) % 4;
    ctx.drawImage(S.flags[k][0], 20 * 2, 15 * 2);
    G.blit(ctx, S.flags[k2][1], 171 * 2 - 32, 15 * 2, true);
    shaftDraw(ctx, S.shaft, t);
    nat(ctx, c => drawMotes(c, S.motes, t, S.shp));
  } else {
    ctx.drawImage(S.front, 0, 0);
    nat(ctx, c => {
      c.globalAlpha = 0.16 + 0.03 * Math.sin(t * 9) * Math.sin(t * 2.3); G.dither(c, 5, 60, 18, 8, P.glow, 8); c.globalAlpha = 1;
      const g = ((t * 0.4) % 2.2) * 40; if (g < 70) { px(c, 122 + (g | 0), 60, WHITE); px(c, 123 + (g | 0), 60, GO[5]); }
    });
  }
};

/* ======================= WITNESS ======================= */
function buildWitness() {
  const K = 'env/shot/witness/';
  const SHP = [[8, 4], [26, 4], [100, 85], [42, 85]];
  return {
    back: x2(K + 'back', NW, NH, b => {
      plaster(b, 0, 0, NW, 50, 4, 6);
      mould(b, 0, 0, NW, [1, 4, 6, 3, 1], true); fill(b, 0, 5, NW, 1, ST[3]);
      mould(b, 0, 15, NW, [4, 1], false);
      // wainscot
      fill(b, 0, 47, NW, 40, WD[1]);
      mould(b, 0, 45, NW, [6, 5, 3, 1], true);
      for (let x = 2; x < NW; x += 18) panel(b, x, 51, 15, 30, 3);
      fill(b, 0, 84, NW, 3, WD[0]);
      for (let y = 87; y < NH; y++) for (let x = 0; x < NW; x++) px(b, x, y, ((x + y * 2) % 8 === 0) ? R.carpet[2] : R.carpet[1]);
      windowN(b, 8, 4, 18, 38, true);
      // clock
      clockFace(b, 40, 24, 7);
      // framed portrait of a former judge
      fill(b, 104, 9, 18, 23, GO[2]); fill(b, 104, 9, 18, 1, GO[5]); fill(b, 104, 9, 1, 23, GO[4]); px(b, 104, 9, WHITE);
      fill(b, 106, 11, 14, 19, R.wood[0]);
      G.ellipse(b, 113, 17, 3, 4, R.skinL[1]); px(b, 112, 16, R.skinL[2]); fill(b, 109, 21, 9, 9, NE[1]); fill(b, 112, 22, 3, 2, NE[8]);
      fill(b, 108, 13, 10, 2, R.hairGrey[1]);
      fill(b, 108, 33, 10, 2, GO[3]); px(b, 108, 33, WHITE); // plaque
      // power outlet + vent
      fill(b, 88, 60, 3, 5, ST[5]); px(b, 89, 61, NE[3]); px(b, 89, 63, NE[3]);
      // judge's bench side mass (right)
      fill(b, 148, 10, 44, 77, WD[1]);
      mould(b, 146, 10, 46, [6, 5, 4, 2, 0], true);
      panel(b, 151, 17, 18, 30, 2); panel(b, 171, 17, 18, 30, 2); panel(b, 151, 50, 38, 32, 2);
      fill(b, 146, 10, 2, 77, WD[4]); px(b, 146, 20, WHITE); px(b, 146, 40, WHITE);
      pole(b, 140, 8, 85);
      ditherRows(b, 76, 87, P.black);
      vignette(b, 7);
    }),
    flag: [0, 1, 2, 3].map(i => x2(K + 'flag/ca/' + i, 14, 44, flagFn('ca', 14, 40, i * 1.57))),
    shaft: x2(K + 'shaft', NW, NH, beamFn(SHP)), shp: SHP, motes: motes(21, 24, [8, 4, 100, 82]),
    front: x2(K + 'front', NW, NH, f => {
      // side panel (receding)
      for (let x = 18; x < 24; x++) { const tp = 75 - (x - 18); fill(f, x, tp, 1, NH - tp, WD[1]); px(f, x, tp, WD[5]); }
      fill(f, 0, 82, 18, NH - 82, WD[0]);
      // stand top rail
      for (let x = 24; x < NW; x++) {
        const tp = 70 + ((x - 24) >> 5);
        px(f, x, tp, WD[6]); fill(f, x, tp + 1, 1, 2, WD[5]); fill(f, x, tp + 3, 1, 2, WD[4]); px(f, x, tp + 5, WD[1]);
        if ((x * 7) % 23 === 0) px(f, x, tp, WHITE);
        fill(f, x, tp + 6, 1, NH - tp - 6, WD[2]);
      }
      fill(f, 24, 70, 1, NH - 70, WD[6]);
      for (let x = 28; x < NW; x += 34) { panel(f, x, 80, 30, 28, 3); rosette(f, x + 32, 83); }
      // gooseneck mic
      fill(f, 52, 68, 9, 2, NE[1]); fill(f, 52, 68, 9, 1, NE[4]); px(f, 53, 68, WHITE);
      const neck = [[56, 68], [57, 63], [57, 59], [55, 55], [52, 53]];
      for (let i = 0; i + 1 < neck.length; i++) { G.line(f, neck[i][0], neck[i][1], neck[i + 1][0], neck[i + 1][1], NE[3]); }
      px(f, 57, 62, NE[6]); px(f, 57, 60, NE[6]); px(f, 56, 57, NE[6]);
      fill(f, 46, 50, 6, 4, NE[1]); fill(f, 46, 50, 6, 1, NE[4]); px(f, 47, 50, WHITE); px(f, 48, 52, NE[3]); px(f, 50, 52, NE[3]);
      // water glass, carafe, sheet, tissue box
      glassN(f, 150, 70, 7, true);
      pitcherN(f, 166, 70);
      fill(f, 98, 68, 18, 2, R.paper[4]); fill(f, 99, 67, 17, 1, R.paper[3]); px(f, 98, 68, WHITE);
      for (let k = 0; k < 3; k++) fill(f, 101 + k * 4, 68, 3, 1, R.paper[2]);
      fill(f, 176, 63, 12, 7, R.blue[4]); fill(f, 176, 63, 12, 1, R.blue[5]); px(f, 176, 63, WHITE);
      G.poly(f, [[180, 63], [184, 63], [185, 59], [181, 58]], NE[9]); px(f, 182, 60, WHITE);
    }),
  };
}
SHOTS.witness = function (ctx, layer, t) {
  const S = get('witness', buildWitness);
  if (layer === 'back') {
    ctx.drawImage(S.back, 0, 0);
    G.blit(ctx, S.flag[Math.floor(t * 1.2) % 4], 142 * 2 - 28 - 2, 9 * 2, true);
    nat(ctx, c => clockHandsN(c, 40, 24, 7, t));
    shaftDraw(ctx, S.shaft, t);
    nat(ctx, c => drawMotes(c, S.motes, t, S.shp));
  } else {
    ctx.drawImage(S.front, 0, 0);
    nat(ctx, c => {
      px(c, 51, 53, (t % 1.4) < 1.0 ? R.red[4] : R.red[2]);
      px(c, 151, 64 + Math.floor(t * 2) % 3, WHITE);
    });
  }
};

/* ======================= COUNSEL (defense / prosecution) ======================= */
function buildCounsel(side) {
  const L = side === 'def', K = 'env/shot/' + (L ? 'defense' : 'prosecution') + '/';
  const SHP = L ? [[154, 6], [184, 2], [96, 76], [44, 76]] : [[0, 0], [30, 0], [96, 76], [52, 76]];
  const xs = L ? [92, 110, 130, 148, 168, 186, 8, 26] : [6, 24, 44, 62, 82, 104, 168, 186];
  const ppl = xs.map((x, i) => ({ x, y: 66 + (i % 2), o: look(i * 5 + (L ? 1 : 3), { size: 'm', dim: 1, look: (i % 2) ? -1 : 1 }), whisper: i % 2 === 0 }));
  return {
    back: x2(K + 'back', NW, NH, b => {
      plaster(b, 0, 0, NW, 46, 3, 6);
      mould(b, 0, 0, NW, [0, 3, 5, 2, 1], true);
      mould(b, 0, 12, NW, [3, 1], false);
      fill(b, 0, 40, NW, 26, WD[1]);
      mould(b, 0, 38, NW, [6, 5, 3, 1], true);
      for (let x = 2; x < NW; x += 18) panel(b, x, 44, 15, 18, 2);
      if (L) {
        // receding side wall with windows (right)
        for (let x = 150; x < NW; x++) {
          const s = (x - 150) / 42, tp = Math.round(6 - s * 6), bt = Math.round(66 + s * 8);
          for (let y = tp; y < bt; y++) {
            const v = (y - tp) / (bt - tp);
            const inW = (s > 0.08 && s < 0.42) || (s > 0.58 && s < 0.92);
            let col = ST[4];
            if (inW && v > 0.08 && v < 0.6) { const q = (v - 0.08) / 0.52; col = q < 0.4 ? P.sky : q < 0.75 ? P.sky2 : P.glow; if (((x + y) % 7) === 0 && q > 0.2) col = WHITE; }
            else if (inW && v >= 0.6 && v < 0.64) col = WD[5];
            else if (v > 0.66) col = v < 0.68 ? WD[5] : WD[1];
            px(b, x, y, col);
          }
        }
        fill(b, 149, 0, 1, 66, WD[1]);
        // brass wall sconces
        for (const sx of [40, 118]) { fill(b, sx, 20, 3, 6, GO[3]); px(b, sx, 20, WHITE); fill(b, sx - 1, 17, 5, 3, ST[5]); px(b, sx, 17, WHITE); b.globalAlpha = 0.2; G.dither(b, sx - 5, 12, 13, 10, P.glow, 8); b.globalAlpha = 1; }
        // framed portrait
        fill(b, 70, 10, 16, 20, GO[2]); fill(b, 70, 10, 16, 1, GO[5]); px(b, 70, 10, WHITE); fill(b, 72, 12, 12, 16, R.green[0]);
        G.ellipse(b, 78, 18, 3, 3, R.skinL[1]); fill(b, 74, 22, 9, 6, NE[1]); px(b, 77, 17, R.skinL[2]);
      } else {
        // exit door
        const dx = 56;
        fill(b, dx - 2, 10, 30, 56, WD[3]); fill(b, dx - 2, 10, 30, 1, WD[5]); fill(b, dx - 2, 10, 1, 56, WD[4]); px(b, dx - 2, 10, WHITE);
        for (let k = 0; k < 2; k++) { fill(b, dx + k * 13, 12, 12, 54, WD[2]); fill(b, dx + 2 + k * 13, 14, 8, 10, NE[3]); G.dither(b, dx + 2 + k * 13, 14, 8, 10, NE[4], 4); px(b, dx + 2 + k * 13, 14, WHITE); panel(b, dx + 1 + k * 13, 28, 10, 16, 2); }
        fill(b, dx - 1, 46, 28, 2, NE[6]); fill(b, dx - 1, 46, 28, 1, NE[8]); px(b, dx, 46, WHITE);
        fill(b, dx + 3, 2, 20, 7, NE[8]); fill(b, dx + 3, 2, 20, 1, WHITE); text3(b, 'EXIT', dx + 6, 3, R.red[3]);
        clockFace(b, 130, 20, 7);
        // bulletin / seal plaque
        fill(b, 160, 10, 22, 16, WD[1]); fill(b, 161, 11, 20, 14, ST[3]);
        fill(b, 163, 13, 6, 7, R.paper[4]); fill(b, 171, 12, 7, 5, R.paper[3]); fill(b, 172, 19, 6, 5, R.paper[4]);
        px(b, 165, 13, R.red[3]); px(b, 174, 12, R.blue[4]); px(b, 174, 19, GO[4]); px(b, 163, 13, WHITE);
        fill(b, 30, 30, 3, 5, ST[5]); px(b, 31, 31, NE[3]); px(b, 31, 33, NE[3]);
      }
      vignette(b, 7);
    }),
    rail: x2(K + 'rail', NW, NH, rr => {
      // pew back
      fill(rr, 0, 61, NW, 2, WD[5]); fill(rr, 0, 61, NW, 1, WD[6]); fill(rr, 0, 63, NW, 3, WD[2]);
      for (let x = 5; x < NW; x += 29) px(rr, x, 61, WHITE);
      // bar rail with balusters
      fill(rr, 0, 66, NW, 2, WD[5]); fill(rr, 0, 66, NW, 1, WD[6]); fill(rr, 0, 68, NW, 1, WD[2]);
      for (let x = 7; x < NW; x += 23) { px(rr, x, 66, WHITE); px(rr, x + 1, 66, WHITE); }
      for (let x = 1; x < NW; x += 5) { fill(rr, x, 69, 2, 9, WD[3]); px(rr, x, 69, WD[5]); px(rr, x, 72, WD[6]); fill(rr, x + 1, 70, 1, 8, WD[1]); }
      fill(rr, 0, 77, NW, 2, WD[2]);
    }),
    ppl: people(K + 'crowd', ppl),
    shaft: x2(K + 'shaft', NW, NH, beamFn(SHP)), shp: SHP, motes: motes(L ? 31 : 32, 24, L ? [44, 2, 140, 74] : [0, 0, 96, 76]), L,
    front: x2(K + 'front', NW, NH, f => {
      deskN(f, 74, 80, 0, NW, 4);
      if (L) {
        folderStackN(f, 2, 77, 6, 7);
        stickyN(f, 30, 72, GO[5]); stickyN(f, 35, 73, R.red[5]);
        legalPadN(f, 74, 74, 24, 6, 3);
        penN(f, 100, 78, 8);
        laptopBackN(f, 116, 77);
        pitcherN(f, 147, 79); glassN(f, 153, 79, 6, true);
        tentCard(f, 160, 79, 'DEFENSE');
      } else {
        tentCard(f, 2, 79, 'PEOPLE');
        pitcherN(f, 34, 79); glassN(f, 42, 79, 6, true);
        laptopBackN(f, 52, 77);
        legalPadN(f, 88, 74, 24, 6, 9);
        penN(f, 114, 78, 8, R.red[2]);
        for (let i = 0; i < 3; i++) {
          const bx = 154 + i * 2, by = 79 - i * 3, col = [R.red, R.blue, NE][i];
          fill(f, bx, by - 3, 34, 3, C(col, 3)); fill(f, bx, by - 3, 34, 1, C(col, 4)); px(f, bx, by - 3, WHITE);
          fill(f, bx + 34, by - 3, 2, 3, R.paper[4]); fill(f, bx + 3, by - 2, 8, 1, NE[8]);
        }
        stickyN(f, 140, 74, R.teal[5]);
      }
    }),
  };
}
function counsel(side) {
  return function (ctx, layer, t) {
    const S = get(side, () => buildCounsel(side));
    if (layer === 'back') {
      ctx.drawImage(S.back, 0, 0);
      if (!S.L) nat(ctx, c => clockHandsN(c, 130, 20, 7, t));
      drawPeople(ctx, S.ppl, t);
      ctx.drawImage(S.rail, 0, 0);
      shaftDraw(ctx, S.shaft, t, 0.12);
      nat(ctx, c => drawMotes(c, S.motes, t, S.shp));
    } else {
      ctx.drawImage(S.front, 0, 0);
      nat(ctx, c => {
        if (S.L) {
          px(c, 135, 76, (t % 2) < 1.6 ? GR[5] : GR[3]);
          const l = [0, 1, 1, 0][Math.floor(t * 5) % 4]; // sheet corner lifting in the vent draft
          fill(c, 186, 75 - l, 6, 1, R.paper[4]); px(c, 186, 75 - l, WHITE);
        } else px(c, 71, 76, (t % 2) < 1.6 ? GR[5] : GR[3]);
      });
    }
  };
}
SHOTS.defense = counsel('def');
SHOTS.prosecution = counsel('pro');

/* ======================= JURY ======================= */
function buildJury() {
  const K = 'env/shot/jury/';
  const SHP = [[0, 0], [36, 0], [112, 76], [56, 76]];
  const rearX = [16, 46, 76, 116, 146, 176], frontX = [24, 58, 96, 134, 168];
  const rear = rearX.map((x, i) => ({ x, y: 62, o: look(i, { size: 's', dim: 1, look: i < 3 ? -1 : 1 }), whisper: i === 1 || i === 4 }));
  const front = frontX.map((x, i) => ({ x, y: 84, o: look(i + 6, { size: 'm', look: i < 2 ? 1 : -1 }), whisper: i === 0 || i === 3 }));
  return {
    back: x2(K + 'back', NW, NH, b => {
      plaster(b, 0, 0, NW, 32, 4, 5);
      mould(b, 0, 0, NW, [1, 4, 6, 3, 1], true);
      seal(b, 96, 15, 9);
      clockFace(b, 160, 15, 6);
      // two framed portraits
      for (const fx of [22, 140 - 120 + 40]) { }
      fill(b, 26, 6, 14, 18, GO[2]); fill(b, 26, 6, 14, 1, GO[5]); px(b, 26, 6, WHITE); fill(b, 28, 8, 10, 14, R.red[0]);
      G.ellipse(b, 33, 13, 2, 3, R.skinL[1]); fill(b, 30, 17, 7, 5, NE[1]);
      // jury box back wall
      fill(b, 0, 30, NW, 30, WD[1]);
      mould(b, 0, 28, NW, [6, 5, 3, 1], true);
      for (let x = 2; x < NW; x += 24) panel(b, x, 33, 21, 22, 2);
      fill(b, 0, 56, NW, 3, WD[4]); fill(b, 0, 56, NW, 1, WD[5]);
      // rear chairs
      rearX.forEach(x => { fill(b, x - 7, 44, 14, 16, R.red[1]); fill(b, x - 7, 44, 14, 1, R.red[3]); fill(b, x - 7, 44, 1, 16, R.red[2]); px(b, x - 6, 45, R.red[4]); for (let k = 0; k < 3; k++) px(b, x - 5 + k * 5, 45, GO[4]); });
    }),
    mid: x2(K + 'mid', NW, NH, md => {
      fill(md, 0, 61, NW, 2, WD[5]); fill(md, 0, 61, NW, 1, WD[6]); fill(md, 0, 63, NW, 8, WD[2]);
      for (let x = 3; x < NW; x += 9 * 3) { px(md, x, 61, WHITE); }
      for (let x = 2; x < NW; x += 16) panel(md, x, 64, 13, 6, 2);
      // front chairs
      frontX.forEach(x => { fill(md, x - 9, 60, 18, 24, R.red[2]); fill(md, x - 9, 60, 18, 1, R.red[4]); fill(md, x - 9, 60, 1, 24, R.red[3]); fill(md, x + 8, 60, 1, 24, R.red[1]); px(md, x - 8, 61, WHITE); for (let k = 0; k < 4; k++) px(md, x - 7 + k * 5, 61, GO[4]); });
    }),
    rear: people(K + 'rear', rear), front: people(K + 'front', front),
    shaft: x2(K + 'shaft', NW, NH, beamFn(SHP)), shp: SHP, motes: motes(41, 22, [0, 0, 112, 76]),
    fg: x2(K + 'front', NW, NH, f => {
      fill(f, 0, 74, NW, 1, WD[6]); fill(f, 0, 75, NW, 2, WD[5]); fill(f, 0, 77, NW, 2, WD[3]); fill(f, 0, 79, NW, NH - 79, WD[2]);
      for (let x = 4; x < NW; x += 31) { px(f, x, 74, WHITE); px(f, x + 1, 74, WHITE); }
      for (let x = 3; x < NW; x += 24) { panel(f, x, 82, 20, 26, 3); rosette(f, x + 22, 85); }
      // notepads + pens on the rail
      fill(f, 18, 72, 12, 2, R.paper[4]); px(f, 18, 72, WHITE); for (let k = 0; k < 3; k++) fill(f, 20 + k * 3, 72, 2, 1, P.ink); penN(f, 31, 73, 6);
      fill(f, 150, 72, 12, 2, R.paper[4]); px(f, 150, 72, WHITE);
    }),
  };
}
SHOTS.jury = function (ctx, layer, t) {
  const S = get('jury', buildJury);
  if (layer === 'back') {
    ctx.drawImage(S.back, 0, 0);
    nat(ctx, c => clockHandsN(c, 160, 15, 6, t));
    drawPeople(ctx, S.rear, t);
    ctx.drawImage(S.mid, 0, 0);
    drawPeople(ctx, S.front, t);
    // a juror fans herself with a sheet
    nat(ctx, c => {
      const off = [0, -1, -2, -1][Math.floor(t * 7) % 4];
      G.poly(c, [[176, 74], [181, 70 + off], [183, 74 + off], [178, 78]], R.paper[4]); px(c, 181, 70 + off, WHITE);
    });
    shaftDraw(ctx, S.shaft, t, 0.11);
    nat(ctx, c => drawMotes(c, S.motes, t, S.shp));
  } else {
    ctx.drawImage(S.fg, 0, 0);
    nat(ctx, c => { if ((t % 3) < 1.5) px(c, 20 + Math.floor(t * 8) % 9, 73, P.ink); });
  }
};

/* ======================= VISIT ======================= */
function buildVisit() {
  const K = 'env/shot/visit/';
  return {
    back: x2(K + 'back', NW, NH, b => {
      for (let y = 0; y < 85; y++) for (let x = 0; x < NW; x++) {
        const row = Math.floor(y / 5), bx = (x + (row & 1) * 6) % 12, by = y % 5;
        let col = GR[3];
        if (by === 0 || bx === 0) col = GR[2];
        else if (by === 1 || bx === 1) col = GR[4];
        if (y > 60) col = (by === 0 || bx === 0) ? GR[1] : GR[2];
        px(b, x, y, col);
      }
      fill(b, 0, 60, NW, 1, GR[1]);
      // steel door + wire glass window
      fill(b, 142, 14, 32, 71, NE[3]); fill(b, 143, 15, 30, 70, NE[4]); fill(b, 143, 15, 30, 1, NE[6]); px(b, 143, 15, WHITE);
      fill(b, 150, 22, 9, 13, NE[1]); fill(b, 151, 23, 7, 11, R.blue[1]);
      for (let k = 0; k < 11; k += 3) { px(b, 151 + (k % 7), 23 + k, NE[3]); }
      px(b, 151, 23, WHITE);
      fill(b, 168, 48, 3, 2, NE[7]); px(b, 168, 48, WHITE); fill(b, 169, 47, 1, 4, NE[2]);
      // sign
      fill(b, 44, 13, 51, 13, NE[8]); fill(b, 44, 13, 51, 1, WHITE); fill(b, 44, 25, 51, 1, NE[5]); px(b, 45, 14, NE[4]); px(b, 93, 14, NE[4]);
      text3(b, 'NO CONTACT', 50, 14, R.red[2]);
      text3(b, 'VISIT 15 MIN', 46, 20, NE[2]);
      // red alarm button + CCTV dome
      fill(b, 118, 6, 7, 4, NE[2]); G.ellipse(b, 121, 10, 3, 2, NE[1]); px(b, 120, 9, WHITE);
      // counter (inmate side)
      fill(b, 0, 75, NW, 10, NE[3]); fill(b, 0, 75, NW, 1, NE[6]);
      // fluorescent fixture
      fill(b, 60, 0, 76, 4, NE[6]); fill(b, 60, 3, 76, 1, NE[5]);
    }),
    glare: x2(K + 'glare', NW, NH, g => { G.dither(g, 30, 4, 136, 30, WHITE, 3); G.dither(g, 56, 4, 84, 14, WHITE, 5); }),
    refl: x2(K + 'refl', NW, NH, rf => {
      for (const [x0, w] of [[46, 12], [64, 4], [130, 9], [146, 3]]) G.poly(rf, [[x0, 7], [x0 + w, 7], [x0 + w - 35, 74], [x0 - 35, 74]], WHITE);
      G.dither(rf, 124, 46, 8, 7, WHITE, 6); G.dither(rf, 122, 42, 2, 4, WHITE, 6); G.dither(rf, 126, 40, 2, 5, WHITE, 6);
    }),
    front: x2(K + 'front', NW, NH, f => {
      // booth dividers (steel, perspective)
      for (let x = 0; x < 35; x++) { const tp = Math.round(x * 0.2), bt = NH - Math.round(x * 0.9); for (let y = tp; y < bt; y++) px(f, x, y, x > 32 ? NE[2] : x > 30 ? GR[1] : ((y + x) % 12 === 0 ? GR[2] : x < 3 ? GR[4] : GR[3])); }
      for (let x = 157; x < NW; x++) { const s = NW - 1 - x, tp = Math.round(s * 0.2), bt = NH - Math.round(s * 0.9); for (let y = tp; y < bt; y++) px(f, x, y, x < 159 ? NE[5] : x < 161 ? GR[4] : ((y + x) % 12 === 0 ? GR[1] : GR[2])); }
      fill(f, 159, 7, 1, 60, WHITE);
      // glass frame
      fill(f, 35, 5, 122, 2, NE[3]); fill(f, 35, 5, 122, 1, NE[6]); for (let x = 40; x < 156; x += 19) px(f, x, 5, WHITE);
      fill(f, 34, 5, 2, 70, NE[3]); px(f, 34, 6, WHITE); fill(f, 156, 5, 2, 70, NE[2]);
      // speaking holes / screws
      px(f, 37, 8, NE[1]); px(f, 154, 8, NE[1]);
      // counter (our side)
      fill(f, 0, 74, NW, 1, NE[8]); fill(f, 0, 75, NW, 1, NE[7]); fill(f, 0, 76, NW, 3, NE[5]); fill(f, 0, 79, NW, NH - 79, GR[2]);
      for (let x = 10; x < NW; x += 29) px(f, x, 74, WHITE);
      for (let k = 0; k < 9; k++) { const x = 16 + (k * 31) % 160; G.line(f, x, 76 + (k % 3), x + 3 + (k % 3), 77, NE[4]); }
      // phone on the left divider
      fill(f, 13, 37, 9, 15, NE[2]); fill(f, 13, 37, 9, 1, NE[4]); px(f, 13, 37, WHITE);
      for (let k = 0; k < 3; k++) for (let j = 0; j < 3; j++) px(f, 15 + k * 2, 41 + j * 2, NE[6]);
      fill(f, 9, 35, 3, 17, NE[1]); px(f, 9, 36, NE[4]); fill(f, 8, 34, 5, 3, NE[1]); fill(f, 8, 50, 5, 3, NE[1]); px(f, 8, 34, NE[5]);
      for (let y = 53; y < 70; y += 2) { fill(f, 10, y, 2, 1, NE[5]); px(f, 10, y, WHITE); }
      fill(f, 15, 55, 6, 4, GO[4]); fill(f, 16, 56, 4, 1, NE[1]);
    }),
  };
}
SHOTS.visit = function (ctx, layer, t) {
  const S = get('visit', buildVisit);
  const cyc = t % 6.3;
  const on = !(cyc > 4.1 && cyc < 4.5 && (Math.floor(t * 30) % 3) === 0);
  if (layer === 'back') {
    ctx.drawImage(S.back, 0, 0);
    nat(ctx, c => {
      const gp = (t % 11) / 11;
      if (gp < 0.25) { const gx = 148 + Math.round(gp / 0.25 * 16); G.ellipse(c, gx, 27, 2, 3, NE[1]); fill(c, gx - 3, 30, 7, 5, NE[1]); }
      fill(c, 61, 3, 74, 1, on ? WHITE : NE[6]);
      if (on) px(c, 120, 10, (t % 1) < 0.5 ? R.red[4] : R.red[2]);
    });
    ctx.globalAlpha = on ? 0.12 : 0.03; ctx.drawImage(S.glare, 0, 0); ctx.globalAlpha = 1;
    if (!on) { ctx.globalAlpha = 0.25; G.dither(ctx, 0, 0, SW, SH, P.black, 8); ctx.globalAlpha = 1; }
  } else {
    ctx.globalAlpha = on ? 0.13 : 0.06; ctx.drawImage(S.refl, 0, 0); ctx.globalAlpha = 1;
    ctx.drawImage(S.front, 0, 0);
    if (!on) { ctx.globalAlpha = 0.2; G.dither(ctx, 0, 0, SW, SH, P.black, 6); ctx.globalAlpha = 1; }
  }
};

/* ======================= DEFENDANT ======================= */
function buildDefendant() {
  const K = 'env/shot/defendant/';
  const SHP = [[126, 4], [164, 0], [116, 80], [60, 80]];
  return {
    back: x2(K + 'back', NW, NH, b => {
      plaster(b, 0, 0, NW, 56, 3, 6);
      mould(b, 0, 0, NW, [0, 3, 5, 2, 1], true);
      // bench backdrop far left
      fill(b, 0, 7, 76, 56, WD[1]); mould(b, 0, 6, 76, [5, 3, 1], true);
      panel(b, 3, 11, 34, 45, 1); panel(b, 39, 11, 34, 45, 1);
      seal(b, 38, 25, 8);
      pole(b, 80, 10, 62);
      // distant bench
      fill(b, 0, 48, 96, 25, WD[2]); mould(b, 0, 47, 96, [6, 5, 3], true);
      for (let x = 2; x < 94; x += 16) panel(b, x, 52, 13, 19, 2);
      fill(b, 30, 35, 15, 13, R.red[1]); fill(b, 30, 35, 15, 1, R.red[3]); px(b, 31, 36, WHITE); for (let k = 0; k < 4; k++) px(b, 31 + k * 4, 36, GO[4]);
      // receding right wall with windows
      for (let x = 96; x < NW; x++) {
        const s = (x - 96) / 96, tp = Math.round(9 - s * 9), bt = Math.round(73 + s * 12);
        for (let y = tp; y < bt; y++) {
          const v = (y - tp) / (bt - tp);
          const inW = (s > 0.16 && s < 0.38) || (s > 0.6 && s < 0.84);
          let col = h2(x, y) < 0.03 ? ST[3] : ST[4];
          if (inW && v > 0.08 && v < 0.6) { const q = (v - 0.08) / 0.52; col = q < 0.4 ? P.sky : q < 0.75 ? P.sky2 : P.glow; if ((x + y * 2) % 9 === 0 && q > 0.3) col = WHITE; }
          else if (v > 0.66) col = v < 0.68 ? WD[5] : (((x >> 2) & 1) ? WD[2] : WD[1]);
          px(b, x, y, col);
        }
      }
      ditherRows(b, 73, 86, P.black);
      vignette(b, 7);
    }),
    flag: [0, 1, 2, 3].map(i => x2(K + 'flag/us/' + i, 12, 34, flagFn('us', 12, 30, i * 1.57))),
    ppl: people(K + 'ppl', [
      { x: 108, y: 74, o: { size: 'm', dim: 1, style: 'bald', skin: R.skinD, hair: R.hairBlack, cloth: GR, look: -1 } },
      { x: 12, y: 54, o: { size: 's', dim: 1, style: 'bun', skin: R.skinL, hair: R.hairBlack, cloth: R.teal, glasses: NE[2], look: 1 } },
    ]),
    shaft: x2(K + 'shaft', NW, NH, beamFn(SHP)), shp: SHP, motes: motes(51, 22, [60, 0, 110, 80]),
    front: x2(K + 'front', NW, NH, f => {
      deskN(f, 76, 82, 0, NW, 4);
      // paper cup, legal pad with doodles, tissue box, pencil
      fill(f, 48, 72, 5, 8, NE[8]); fill(f, 48, 72, 5, 1, WHITE); fill(f, 52, 72, 1, 8, NE[6]); fill(f, 49, 73, 3, 1, R.blue[5]);
      legalPadN(f, 60, 76, 22, 5, 17);
      for (let k = 0; k < 4; k++) px(f, 74 + k, 79 - (k & 1), P.ink);
      penN(f, 84, 80, 7, GO[4]);
      fill(f, 150, 70, 17, 10, R.blue[4]); fill(f, 150, 70, 17, 1, R.blue[5]); fill(f, 150, 70, 1, 10, R.blue[5]); fill(f, 166, 70, 1, 10, R.blue[2]);
      G.poly(f, [[156, 70], [161, 70], [162, 66], [158, 65], [155, 67]], NE[9]); px(f, 158, 66, WHITE);
      for (let x = 152; x < 166; x += 3) fill(f, x, 75, 2, 2, R.blue[3]);
    }),
  };
}
SHOTS.defendant = function (ctx, layer, t) {
  const S = get('defendant', buildDefendant);
  if (layer === 'back') {
    ctx.drawImage(S.back, 0, 0);
    ctx.drawImage(S.flag[Math.floor(t * 1.2) % 4], 82 * 2, 11 * 2);
    drawPeople(ctx, S.ppl, t);
    shaftDraw(ctx, S.shaft, t, 0.12);
    nat(ctx, c => drawMotes(c, S.motes, t, S.shp));
  } else ctx.drawImage(S.front, 0, 0);
};

/* ======================= OFFICE (night) ======================= */
function buildOffice() {
  const K = 'env/shot/office/';
  const r = G.rng(808);
  const lights = [];
  const BL = [[106, 40], [114, 30], [122, 44], [128, 22], [138, 36], [146, 18], [156, 32], [164, 26], [174, 40], [180, 34], [186, 0]];
  for (let i = 0; i < 90 && lights.length < 46; i++) {
    const x = 107 + Math.floor(r() * 78), y = 26 + Math.floor(r() * 37);
    const seg = BL.findIndex((q, k) => x >= q[0] && x < BL[k + 1][0]);
    if (seg < 0 || y < 64 - BL[seg][1] + 2 || x === 145 || x === 146 || y === 35) continue;
    lights.push([x, y, r()]);
  }
  return {
    lights,
    back: x2(K + 'back', NW, NH, b => {
      // dark wall
      fill(b, 0, 0, NW, NH, R.blue[1]);
      for (let x = 0; x < NW; x += 12) fill(b, x, 0, 1, 70, R.blue[0]);
      // bookshelves (left)
      fill(b, 2, 4, 46, 72, WD[0]); fill(b, 2, 4, 46, 1, WD[2]);
      const bc = [R.red, R.blue, GR, GO, R.purple, R.teal, NE, R.wood];
      for (let sy = 8; sy < 72; sy += 16) {
        fill(b, 3, sy + 12, 44, 2, WD[2]); fill(b, 3, sy + 12, 44, 1, WD[3]);
        let x = 4;
        while (x < 45) {
          const w = 2 + Math.floor(r() * 3), h = 8 + Math.floor(r() * 4), ramp = bc[Math.floor(r() * bc.length)];
          if (x + w > 46) break;
          if (r() < 0.1) { // leaning book
            G.line(b, x, sy + 12, x + 4, sy + 12 - h + 2, C(ramp, 2)); x += 5; continue;
          }
          fill(b, x, sy + 12 - h, w, h, C(ramp, 1)); fill(b, x, sy + 12 - h, 1, h, C(ramp, 2));
          if (r() < 0.6) fill(b, x, sy + 14 - h, w, 1, GO[3]);
          x += w;
        }
      }
      // diplomas on the wall
      for (const [dx, dy] of [[56, 10], [76, 12]]) {
        fill(b, dx, dy, 16, 12, WD[1]); fill(b, dx + 1, dy + 1, 14, 10, R.paper[3]); px(b, dx, dy, GO[4]);
        for (let k = 0; k < 3; k++) fill(b, dx + 3, dy + 3 + k * 2, 10, 1, R.paper[1]);
        px(b, dx + 11, dy + 8, R.red[3]); px(b, dx + 1, dy + 1, R.paper[4]);
      }
      // window with LA skyline at night
      fill(b, 104, 6, 84, 60, WD[1]);
      for (let y = 8; y < 64; y++) for (let x = 106; x < 186; x++) {
        const f = (y - 8) / 56;
        let col = f < 0.4 ? R.blue[1] : f < 0.75 ? R.blue[2] : R.purple[2];
        if (f > 0.36 && f < 0.4 && G.bayer(x, y) < 8) col = R.blue[2];
        if (f > 0.71 && f < 0.75 && G.bayer(x, y) < 8) col = R.purple[2];
        px(b, x, y, col);
      }
      // stars + moon
      for (let i = 0; i < 12; i++) px(b, 108 + Math.floor(r() * 76), 9 + Math.floor(r() * 16), NE[7]);
      G.ellipse(b, 170, 16, 3, 3, R.paper[4]); px(b, 171, 15, R.paper[3]); px(b, 169, 15, WHITE);
      // skyline silhouettes
      const bl = [[106, 40], [114, 30], [122, 44], [128, 22], [138, 36], [146, 18], [156, 32], [164, 26], [174, 40], [180, 34]];
      bl.forEach(([x, h], i) => fill(b, x, 64 - h, (bl[i + 1] ? bl[i + 1][0] : 186) - x, h, R.blue[0]));
      fill(b, 140, 30, 5, 34, R.blue[0]); fill(b, 141, 24, 3, 6, R.blue[0]); px(b, 142, 21, R.blue[0]); px(b, 142, 22, R.blue[0]); // city hall
      // mullions
      fill(b, 145, 8, 2, 56, WD[1]); fill(b, 106, 35, 80, 1, WD[1]);
      // blinds half down
      for (let y = 8; y < 22; y += 2) { fill(b, 106, y, 80, 1, R.stone[1]); }
      fill(b, 106, 22, 80, 1, R.stone[2]);
      fill(b, 102, 65, 88, 3, WD[2]); fill(b, 102, 65, 88, 1, WD[4]);
      // wall clock
      clockFace(b, 92, 40, 5);
      // floor
      fill(b, 0, 76, NW, NH - 76, R.wood[0]);
    }),
    front: x2(K + 'front', NW, NH, f => {
      // desk (mid-ground) across the frame
      for (let y = 66; y < 74; y++) for (let x = 0; x < NW; x++) px(f, x, y, grainCol(x, y * 3, 2));
      fill(f, 0, 74, NW, 1, WD[4]); fill(f, 0, 75, NW, NH - 75, WD[0]);
      // lamp pool of light (pre-lit desk area)
      for (let y = 66; y < 74; y++) for (let x = 90; x < 150; x++) {
        const d = Math.abs(x - 120) / 30 + Math.abs(y - 70) / 8;
        if (d < 1 && G.bayer(x, y) < (1 - d) * 22) px(f, x, y, grainCol(x, y * 3, 4));
      }
      // brass desk lamp
      fill(f, 120, 64, 8, 2, GO[2]); fill(f, 120, 64, 8, 1, GO[4]); px(f, 121, 64, WHITE);
      G.line(f, 124, 64, 128, 52, GO[3]); G.line(f, 128, 52, 122, 46, GO[3]); px(f, 127, 53, WHITE);
      G.poly(f, [[114, 50], [124, 44], [127, 48], [118, 53]], GR[3]); px(f, 120, 46, GR[5]); px(f, 121, 46, WHITE);
      fill(f, 116, 51, 5, 1, P.glow);
      // case files, coffee mug, phone, papers
      folderStackN(f, 6, 72, 5, 12);
      for (let i = 0; i < 3; i++) { fill(f, 92 + i * 2, 70 - i, 16, 1, R.paper[4 - (i & 1)]); px(f, 92 + i * 2, 70 - i, WHITE); }
      fill(f, 136, 64, 6, 7, NE[8]); fill(f, 136, 64, 6, 1, WHITE); fill(f, 142, 65, 2, 1, NE[7]); fill(f, 143, 66, 1, 2, NE[7]); fill(f, 137, 65, 4, 1, R.wood[1]);
      fill(f, 136, 67, 6, 1, R.red[3]);
      fill(f, 158, 66, 14, 5, NE[1]); fill(f, 158, 66, 14, 1, NE[3]); fill(f, 160, 64, 10, 2, NE[2]); px(f, 160, 64, NE[5]); px(f, 170, 68, GR[5]);
      penN(f, 70, 71, 9); stickyN(f, 54, 67, GO[5]);
      // file box
      fill(f, 176, 56, 16, 12, R.paper[1]); fill(f, 176, 56, 16, 1, R.paper[3]); fill(f, 180, 60, 7, 2, R.paper[0]);
    }),
  };
}
SHOTS.office = function (ctx, layer, t) {
  const S = get('office', buildOffice);
  if (layer === 'back') {
    ctx.drawImage(S.back, 0, 0);
    nat(ctx, c => {
      for (const [x, y, ph] of S.lights) {
        const on = Math.sin(t * (0.2 + ph * 0.5) + ph * 30) > -0.6;
        if (!on) continue;
        // only on buildings: below silhouette tops (approx by y > 26)
        px(c, x, y, ph < 0.3 ? P.glow : ph < 0.6 ? GO[4] : NE[8]);
      }
      if ((t % 1.6) < 0.2) px(c, 142, 20, R.red[4]); // antenna light
      clockHandsN(c, 92, 40, 5, t + 13.5 * 3600);
    });
  } else {
    ctx.drawImage(S.front, 0, 0);
    nat(ctx, c => {
      c.globalAlpha = 0.16 + 0.03 * Math.sin(t * 7) * Math.sin(t * 1.9); G.dither(c, 96, 64, 50, 10, P.glow, 8); G.dither(c, 106, 66, 30, 6, P.glow, 6); c.globalAlpha = 1;
      // steam from the mug
      for (let k = 0; k < 4; k++) {
        const y = 62 - ((t * 5 + k * 3) % 12), x = 139 + Math.round(Math.sin(t * 2 + k) * 1.5);
        c.globalAlpha = 0.35 * (1 - (62 - y) / 12); px(c, x, Math.round(y), NE[8]);
      }
      c.globalAlpha = 1;
      // moth around the lamp
      const a = t * 3.3; px(c, 120 + Math.round(Math.cos(a) * 5 + Math.sin(t * 9) * 1), 48 + Math.round(Math.sin(a * 1.4) * 3), ST[5]);
    });
  }
};

/* ======================= HALLWAY ======================= */
function buildHallway() {
  const K = 'env/shot/hallway/';
  const VX = 96, VY = 44; // vanishing point
  return {
    back: x2(K + 'back', NW, NH, b => {
      // ceiling
      for (let y = 0; y < VY; y++) for (let x = 0; x < NW; x++) {
        const d = (VY - y) / VY; px(b, x, y, d > 0.7 ? ST[3] : ST[4]);
      }
      // walls: left/right receding (per column)
      for (let x = 0; x < NW; x++) {
        const s = Math.abs(x - VX) / VX;
        const top = Math.round(VY - s * VY * 0.95), bot = Math.round(VY + s * 60 * 0.9) + 4;
        for (let y = top; y < bot; y++) {
          const v = (y - top) / (bot - top);
          let col = ST[4];
          if (v > 0.62) col = v < 0.64 ? WD[5] : WD[2];
          if (v > 0.98) col = WD[0];
          px(b, x, y, col);
        }
      }
      // far end wall with elevator
      fill(b, 82, 30, 28, 24, ST[4]);
      fill(b, 88, 34, 16, 20, NE[6]); fill(b, 95, 34, 1, 20, NE[4]); fill(b, 88, 34, 16, 1, WHITE);
      fill(b, 91, 30, 10, 3, NE[1]);
      fill(b, 106, 42, 2, 3, NE[5]); px(b, 106, 42, WHITE);
      // floor: marble with reflections
      for (let x = 0; x < NW; x++) for (let y = Math.max(VY + 6, Math.round(VY + Math.abs(x - VX) / VX * 54) + 4); y < NH; y++) {
        const d = (y - VY) / (NH - VY);
        const u = (x - VX) / Math.max(1, (y - VY));
        const tile = (Math.floor(u * 3 + 100) + Math.floor(Math.log(y - VY + 1) * 4)) & 1;
        let col = tile ? ST[4] : ST[3];
        if (Math.abs(x - VX) < 3 + d * 14 && G.bayer(x, y) < 5) col = ST[5]; // light reflection
        if (Math.abs(x - VX) < 1 + d * 4 && G.bayer(x, y) < 3) col = WHITE;
        px(b, x, y, col);
      }
      // courtroom doors along the walls with brass plaques
      const door = (x, y, w, h, label) => {
        fill(b, x - 1, y - 1, w + 2, h + 1, WD[4]); fill(b, x, y, w, h, WD[2]);
        panel(b, x + 1, y + 2, w - 2, h - 4, 2);
        fill(b, x + w - 3, y + (h >> 1), 1, 2, GO[4]); px(b, x + w - 3, y + (h >> 1), WHITE);
        if (label) { fill(b, x + 1, y - 7, text3W(label) + 2, 6, GO[3]); px(b, x + 1, y - 7, WHITE); text3(b, label, x + 2, y - 6, GO[1]); }
      };
      door(14, 34, 18, 46, 'DEPT 112'); door(52, 38, 10, 22, ''); door(158, 34, 18, 46, 'DEPT 113'); door(130, 38, 10, 22, '');
      // benches
      for (const bx of [36, 136]) { fill(b, bx, 70, 20, 2, WD[5]); px(b, bx, 70, WHITE); fill(b, bx, 72, 20, 4, WD[2]); fill(b, bx + 1, 76, 2, 4, WD[1]); fill(b, bx + 17, 76, 2, 4, WD[1]); fill(b, bx, 62, 20, 6, WD[3]); fill(b, bx, 62, 20, 1, WD[5]); }
      // ceiling lights
      for (const [y, w] of [[3, 30], [14, 18], [22, 10], [27, 6]]) { fill(b, VX - (w >> 1), y, w, 2, WHITE); fill(b, VX - (w >> 1), y + 2, w, 1, ST[3]); }
      // directory sign + flag
      fill(b, 120, 22, 14, 10, NE[2]); for (let k = 0; k < 4; k++) fill(b, 122, 24 + k * 2, 9, 1, NE[7]);
      // water fountain
      fill(b, 64, 56, 7, 5, NE[6]); fill(b, 64, 56, 7, 1, WHITE);
    }),
    walkers: people(K + 'walk', [0, 1, 2, 3].map(i => ({ x: 0, y: 0, o: look(i * 3 + 1, { size: 's', dim: 1 }) }))),
    front: x2(K + 'front', NW, NH, () => {}),
  };
}
SHOTS.hallway = function (ctx, layer, t) {
  const S = get('hallway', buildHallway);
  if (layer === 'back') {
    ctx.drawImage(S.back, 0, 0);
    // elevator floor indicator
    nat(ctx, c => { const fl = 1 + Math.floor(t / 3) % 9; text3(c, String(fl), 94, 30, (t % 3) > 2.6 ? GO[4] : R.red[4]); });
    // people walking across the far corridor
    S.walkers.forEach((p, i) => {
      const per = 14 + i * 3, ph = (t + i * 5.3) % per, dir = i & 1 ? -1 : 1;
      const xn = dir > 0 ? 60 + ph * 5 : 132 - ph * 5;
      if (xn < 60 || xn > 132) return;
      const bob = Math.floor(t * 6 + i) % 2;
      const spr = p.fr[0];
      ctx.globalAlpha = 0.9; ctx.drawImage(spr, Math.round(xn) * 2 - (spr.width >> 1), (58 + bob) * 2 - spr.height); ctx.globalAlpha = 1;
      nat(ctx, c => { fill(c, Math.round(xn) - 3, 58 + bob, 6, 4, C(p.o.cloth, 1)); px(c, Math.round(xn) - 2 + (bob ? 0 : 3), 62, NE[1]); });
    });
  } else ctx.drawImage(S.front, 0, 0);
};

/* ======================= EXTERIOR ======================= */
function buildExterior() {
  const K = 'env/exterior/';
  const X0 = 64, X1 = NW, TOP = 28, CB = 82;
  return {
    X0, X1, TOP, CB,
    sky: x2(K + 'sky', NW, NH, s => {
      const bands = [R.blue[4], R.blue[5], P.sky, P.sky2, GO[5], R.red[5], GO[4]];
      const by = [0, 12, 26, 40, 54, 64, 72, 80];
      for (let i = 0; i < bands.length; i++) {
        fill(s, 0, by[i], NW, by[i + 1] - by[i], bands[i]);
        if (i + 1 < bands.length) for (let k = 0; k < 3; k++) G.dither(s, 0, by[i + 1] - 3 + k, NW, 1, bands[i], 12 - k * 4);
      }
      for (let k = 3; k >= 0; k--) { s.globalAlpha = 0.2; G.ellipse(s, 16, 70, 8 + k * 5, 5 + k * 3, P.glow); } s.globalAlpha = 1;
      G.ellipse(s, 16, 70, 6, 6, GO[5]); G.ellipse(s, 16, 70, 5, 5, WHITE);
      // skyline + City Hall
      const sk = [[0, 6], [8, 10], [14, 5], [20, 14], [30, 8], [36, 12], [44, 6], [52, 9], [60, 5]];
      sk.forEach(([x, h], i) => { fill(s, x, 76 - h, (sk[i + 1] ? sk[i + 1][0] : 66) - x, h + 4, R.purple[3]); });
      fill(s, 24, 46, 9, 30, R.purple[3]); fill(s, 26, 39, 5, 7, R.purple[3]); fill(s, 27, 34, 3, 5, R.purple[3]); fill(s, 28, 30, 1, 4, R.purple[3]);
      fill(s, 24, 46, 1, 30, R.purple[4]); px(s, 26, 39, R.purple[4]);
      for (let y = 48; y < 74; y += 3) for (let x = 26; x < 32; x += 2) px(s, x, y, GO[4]);
      px(s, 28, 30, R.red[4]);
      // lawn & hedges
      for (let y = 76; y < 92; y++) for (let x = 0; x < NW; x++) {
        let col = y < 79 ? R.purple[2] : y < 84 ? (((x * 3 + y) % 5 === 0) ? GR[1] : GR[2]) : (((x + y * 3) % 7 === 0) ? GR[2] : GR[3]);
        if (y === 79 && (x % 5) < 3) col = GR[3];
        px(s, x, y, col);
      }
    }),
    bld: x2(K + 'building', NW, NH, b => {
      // side face (shade) for depth
      for (let y = TOP - 8; y < 92; y++) for (let x = X0 - 6; x < X0; x++) { if (y < TOP - 8 + (X0 - x)) continue; px(b, x, y, ((y - TOP) % 4 === 0) ? ST[1] : ST[2]); }
      // attic + cornice
      fill(b, X0, TOP - 10, X1 - X0, 10, ST[4]);
      fill(b, X0, TOP - 11, X1 - X0, 1, ST[5]); for (let x = X0; x < X1; x += 9) px(b, x + 3, TOP - 11, WHITE);
      for (let x = X0 + 2; x < X1; x += 8) { fill(b, x, TOP - 8, 5, 5, ST[3]); fill(b, x, TOP - 8, 5, 1, ST[5]); fill(b, x + 4, TOP - 8, 1, 5, ST[2]); } // attic panels
      mould(b, X0 - 2, TOP - 2, X1 - X0 + 2, [], false);
      [ST[5], ST[4], ST[2], ST[1]].forEach((col, j) => fill(b, X0 - 2, TOP - 2 + j, X1 - X0 + 2, 1, col));
      for (let x = X0 - 1; x < X1; x += 3) { px(b, x, TOP + 2, ST[5]); px(b, x, TOP + 3, ST[2]); } // dentils
      // entablature + engraved inscription
      fill(b, X0, TOP + 4, X1 - X0, 13, ST[4]); fill(b, X0, TOP + 4, X1 - X0, 1, WHITE); fill(b, X0, TOP + 16, X1 - X0, 1, ST[1]);
      const cx = (X0 + X1) >> 1;
      const eng = (txt, y) => { const x = cx - (text3W(txt) >> 1); text3(b, txt, x, y + 1, ST[5]); text3(b, txt, x, y, ST[1]); };
      eng('SUPERIOR COURT OF CALIFORNIA', TOP + 5); eng('COUNTY OF LOS ANGELES', TOP + 11);
      // portico depth
      fill(b, X0, TOP + 17, X1 - X0, CB - TOP - 17, ST[1]);
      for (let x = X0 + 6; x < X1 - 4; x += 13) {
        fill(b, x, TOP + 26, 6, 22, NE[2]); fill(b, x + 1, TOP + 27, 4, 20, R.blue[1]); G.dither(b, x + 1, TOP + 27, 4, 8, GO[2], 4);
        fill(b, x + 1, TOP + 36, 4, 1, NE[2]); px(b, x + 1, TOP + 27, GO[4]);
      }
      // bronze doors, glowing
      fill(b, cx - 7, TOP + 30, 14, 24, GO[1]); fill(b, cx - 6, TOP + 31, 6, 23, GO[2]); fill(b, cx + 1, TOP + 31, 6, 23, GO[2]);
      G.dither(b, cx - 6, TOP + 31, 13, 6, GO[4], 6); px(b, cx - 1, TOP + 42, WHITE); px(b, cx + 1, TOP + 42, WHITE);
      // columns, lit from the left by the setting sun
      for (let x = X0 + 2; x < X1; x += 13) {
        for (let y = TOP + 17; y < CB; y++) for (let i = 0; i < 7; i++) {
          let col = [ST[3], ST[5], ST[5], ST[4], ST[3], ST[2], ST[1]][i];
          if ((i === 2 || i === 4) && y > TOP + 20 && y < CB - 3) col = shade(col, -1);
          px(b, x + i, y, col);
        }
        fill(b, x + 1, TOP + 21, 1, CB - TOP - 25, GO[5]);
        for (let y = TOP + 22; y < CB - 4; y += 9) px(b, x + 1, y, WHITE);
        fill(b, x - 1, TOP + 17, 9, 2, ST[4]); fill(b, x - 1, TOP + 17, 9, 1, WHITE); fill(b, x - 1, TOP + 19, 9, 1, ST[2]);
        fill(b, x - 1, CB - 2, 9, 2, ST[4]); fill(b, x - 1, CB - 2, 9, 1, ST[5]);
      }
      // steps
      for (let k = 0; k < 6; k++) {
        const y = CB + k * 2, ext = k * 4;
        fill(b, X0 - 6 - ext, y, X1 - X0 + 6 + ext, 2, ST[4]); fill(b, X0 - 6 - ext, y, X1 - X0 + 6 + ext, 1, ST[5]);
        for (let x = X0 - 6 - ext + (k * 5) % 11; x < X1; x += 23) px(b, x, y, WHITE);
      }
      // plaza
      for (let y = 94; y < NH; y++) for (let x = 0; x < NW; x++) {
        let col = ST[2];
        if ((x + y * 2) % 16 === 0 || y % 5 === 0) col = ST[1];
        px(b, x, y, col);
      }
      for (let x = 0; x < NW; x++) if (x % 4 === 0) px(b, x, 94, ST[3]);
      b.globalAlpha = 0.25; for (let x = X0 + 2; x < NW; x += 13) G.poly(b, [[x, 94], [x + 7, 94], [x + 26, NH], [x + 18, NH]], P.shadow); b.globalAlpha = 1;
      // lamp posts
      for (const lx of [56, 184]) {
        fill(b, lx, 70, 2, 25, NE[1]); fill(b, lx - 2, 93, 6, 2, NE[1]); fill(b, lx - 1, 66, 4, 5, NE[1]); fill(b, lx, 67, 2, 3, GO[5]); px(b, lx, 67, WHITE);
      }
      // planters with agaves
      for (const p0 of [70, 172]) {
        fill(b, p0, 88, 12, 5, ST[3]); fill(b, p0, 88, 12, 1, WHITE); fill(b, p0 + 11, 88, 1, 5, ST[1]);
        for (let k = 0; k < 5; k++) G.line(b, p0 + 6, 88, p0 + 1 + k * 2, 82 + Math.abs(2 - k) * 2, R.teal[3 + (k & 1)]);
      }
      // roof flagpole
      fill(b, cx, 4, 1, TOP - 14, NE[7]); px(b, cx, 3, GO[5]); px(b, cx, 3, WHITE);
    }),
    palms: x2(K + 'palms', NW, NH, pl => {
      const trunk = (x, yb, h, lean) => { for (let y = 0; y < h; y++) { const xx = x + Math.round(lean * (y / h) * (y / h) * 6); fill(pl, xx, yb - y, 2, 1, (y % 3 === 0) ? WD[1] : WD[2]); if (y % 3 === 0) px(pl, xx - 1, yb - y, WD[3]); } };
      trunk(10, 104, 78, 1); trunk(30, 100, 60, -0.6); trunk(48, 96, 40, 0.4);
    }),
    heads: [[16, 26, 1.3], [26, 40, 1.0], [50, 56, 0.8]],
    clouds: [[10, 10, 30, 0.45], [70, 18, 22, 0.3], [130, 6, 36, 0.38], [40, 34, 24, 0.25]].map(([x, y, w, sp], i) => ({ x, y, w, sp, spr: x2(K + 'cloud/' + i, w, Math.round(w * 0.34), cloudFn(w, Math.round(w * 0.34), i)) })),
    birds: motes(91, 5, [0, 4, NW, 34]),
  };
}
function cloudFn(w, h, seed) {
  return c => {
    const r = G.rng(seed * 31 + 7), puffs = [];
    for (let i = 0; i < 6; i++) puffs.push([Math.round(w * (0.15 + r() * 0.7)), Math.round(h * (0.45 + r() * 0.25)), h * (0.25 + r() * 0.2)]);
    puffs.push([w >> 1, Math.round(h * 0.45), h * 0.42]);
    const ins = (x, y) => puffs.some(([a, b, pr]) => (x - a) ** 2 + ((y - b) * 1.5) ** 2 < pr * pr * 1.6) || (y > h * 0.6 && y < h * 0.85 && x > w * 0.1 && x < w * 0.9);
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      if (!ins(x, y)) continue;
      let col = P.sky2;
      if (!ins(x, y + 1)) col = (G.bayer(x, y) < 8) ? R.red[5] : GO[5];
      else if (!ins(x - 2, y)) col = GO[5];
      else if (!ins(x, y - 1)) col = WHITE;
      else if (y > h * 0.62) col = GO[5];
      px(c, x, y, col);
    }
  };
}
function fronds(c, hx, hy, ph, sc) {
  for (let k = 0; k < 8; k++) {
    const a = -Math.PI * 0.95 + k * (Math.PI * 1.9 / 7) + Math.sin(ph + k) * 0.07;
    const len = Math.round((8 + (k % 3) * 2) * sc);
    let x0 = hx, y0 = hy;
    for (let i = 1; i <= len; i++) {
      const dr = (i / len) * (i / len) * 5 * sc;
      const xx = Math.round(hx + Math.cos(a) * i), yy = Math.round(hy + Math.sin(a) * i * 0.6 + dr);
      G.line(c, x0, y0, xx, yy, k % 2 ? GR[2] : GR[3]);
      if (i > 2 && i < len - 1) { px(c, xx, yy + 1, GR[1]); if (i % 2) px(c, xx, yy + 2, GR[0]); }
      if (i % 3 === 0) px(c, xx, yy - 1, GR[4]);
      x0 = xx; y0 = yy;
    }
  }
  fill(c, hx - 1, hy, 3, 2, WD[1]); px(c, hx, hy, WD[3]);
}
E._exterior = function (ctx, t) {
  const S = get('exterior', buildExterior);
  ctx.drawImage(S.sky, 0, 0);
  for (const cl of S.clouds) {
    const xx = Math.round(((cl.x + t * cl.sp) % (NW + cl.w + 20)) - cl.w - 10 + 20);
    ctx.drawImage(cl.spr, xx * 2, (cl.y - (cl.w * 0.17 | 0)) * 2);
  }
  ctx.drawImage(S.bld, 0, 0);
  nat(ctx, c => {
    const cx = (S.X0 + S.X1) >> 1;
    // roof flag
    for (let x = 0; x < 11; x++) {
      const w = Math.sin(t * 5 - x * 0.6), wv = Math.round(w * (x / 11) * 1.5);
      for (let y = 0; y < 7; y++) {
        let col = (y % 2 === 0) ? R.red[3] : NE[8];
        if (x < 5 && y < 4) col = ((x + y) % 2 === 0) ? WHITE : R.blue[3];
        if (w > 0.5) col = shade(col, -1);
        px(c, cx + 1 + x, 4 + y + wv, col);
      }
    }
    // lamp glow
    for (const lx of [56, 184]) { c.globalAlpha = 0.18 + 0.03 * Math.sin(t * 3 + lx); G.dither(c, lx - 5, 63, 12, 10, P.glow, 8); c.globalAlpha = 1; }
    // people walking on the plaza
    for (let i = 0; i < 5; i++) {
      const per = 40 + i * 9, dir = (i & 1) ? -1 : 1;
      const p = ((t + i * 17) % per) / per;
      const x = Math.round(dir > 0 ? -6 + p * 204 : 198 - p * 204), y = 99 + (i % 3) * 3;
      const st = Math.floor(t * 4 + i) % 2;
      const cl = [R.blue, R.red, NE, R.teal, GO][i];
      fill(c, x - 1, y - 9, 3, 3, [R.skinL, R.skinM, R.skinD][i % 3][2]); fill(c, x - 1, y - 10, 3, 1, [R.hairBlack, R.hairBrown, R.hairBlond][i % 3][2]);
      fill(c, x - 2, y - 6, 5, 4, cl[3]); px(c, x - 2, y - 6, cl[4]);
      px(c, x - 1, y - 2 + 0, NE[1]); px(c, x + 1, y - 2, NE[1]); px(c, x - 1 + st, y - 1, NE[1]); px(c, x + 1 - st, y - 1, NE[1]);
      if (i === 2) fill(c, x + 2 * dir, y - 4, 2, 2, WD[1]); // briefcase
      c.globalAlpha = 0.3; fill(c, x - 1, y, 5, 1, P.shadow); c.globalAlpha = 1;
    }
    // pigeons
    [[86, 93], [96, 95], [150, 96], [124, 93]].forEach(([x, y], i) => {
      const peck = ((t * 1.3 + i * 0.7) % 2) < 0.3 ? 1 : 0, X = x + Math.round(Math.sin(t * 0.3 + i) * 2);
      fill(c, X, y - 2, 3, 2, NE[5]); px(c, X, y - 2, NE[6]); px(c, X + (i & 1 ? -1 : 3), y - 3 + peck, NE[4]); px(c, X + 1, y, R.red[3]);
    });
    // birds
    for (const m of S.birds) {
      const x = Math.round(((m.x * NW + t * 7 * m.sp) % (NW + 10)) - 5), y = Math.round(6 + m.y * 30 + Math.sin(t * 0.8 + m.ph) * 2);
      const fl = Math.floor(t * 6 + m.ph * 3) % 2;
      px(c, x, y, NE[2]); px(c, x - 1, y - fl, NE[2]); px(c, x + 1, y - fl, NE[2]);
    }
  });
  ctx.drawImage(S.palms, 0, 0);
  nat(ctx, c => S.heads.forEach(([hx, hy, sc], i) => fronds(c, hx + Math.round(sc * 4), hy, t * 0.9 + i * 2, sc)));
};

/* ---------------- prebuild: touch every cached key ---------------- */
G.prebuild(() => {
  E.build();
  ['judge', 'witness', 'defense', 'prosecution', 'jury', 'visit', 'defendant', 'office', 'hallway'].forEach(id => {
    const c = G.makeCanvas(SW, SH).getContext('2d');
    SHOTS[id](c, 'back', 0); SHOTS[id](c, 'front', 0);
  });
  E._exterior(G.makeCanvas(SW, SH).getContext('2d'), 0);
});
})();
