// Visual models of the proving ground. The game owns placement and physics colliders; every factory here returns an
// Object3D whose origin sits at the collider centre with the collider's orientation (see SPEC.md §Environment).
// OWNER: environment agent.
import { THREE, STD, PALETTE, canvasTex, rnd } from './common.js';

export const hazardTex = canvasTex(256, 64, (x, w, h) => { x.fillStyle = '#161614'; x.fillRect(0, 0, w, h); x.fillStyle = '#e3ae1c';
  for (let i = -2; i < 12; i++) { x.beginPath(); x.moveTo(i * 32, h); x.lineTo(i * 32 + 16, h); x.lineTo(i * 32 + 16 + h, 0); x.lineTo(i * 32 + h, 0); x.fill(); } }, true);

// ───────────────────────────── shared helpers
const V3 = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);
const UP = V3(0, 1, 0);
// deterministic hash of a (quantised) position: duplicated vertices of one surface get the same value → no cracks
const hsh = (x, y = 0, z = 0) => { const h = Math.sin(Math.round(x * 97) * 127.1 + Math.round(y * 97) * 311.7 + Math.round(z * 97) * 74.7) * 43758.5453; return h - Math.floor(h); };
const pick = a => a[(Math.random() * a.length) | 0];
const tag = o => { o.userData.env = true; return o; };
// every material takes vertex colours (all geometry built here carries a colour attribute)
const M = (c, o = {}) => STD(c, Object.assign({ vertexColors: true }, o));
const MAT = {
  concrete: M(PALETTE.concrete, { roughness: 0.95 }),
  concreteL: M(0xb4b0a6, { roughness: 0.95 }),
  steel: M(PALETTE.steel, { metalness: 0.6, roughness: 0.45 }),
  dark: M(PALETTE.darkSteel, { metalness: 0.5, roughness: 0.55 }),
  galv: M(0xa4a9ab, { metalness: 0.6, roughness: 0.4 }),
  black: M(0x1c1c1b, { roughness: 0.75 }),
  yellow: M(PALETTE.hazard, { roughness: 0.6 }),
  rubber: M(PALETTE.rubber, { roughness: 0.95 }),
  glass: M(0x2b3a42, { metalness: 0.6, roughness: 0.12 }),
  white: M(0xffffff, { roughness: 0.85 }),
  lamp: M(0xfff2d6, { emissive: 0xfff0cc, emissiveIntensity: 0.55, roughness: 0.3 }),
};
const hazCache = new Map();
function hazMat(rx, ry = 1) {
  const k = rx.toFixed(2) + '_' + ry.toFixed(2); let m = hazCache.get(k);
  if (!m) { const t = hazardTex.clone(); t.needsUpdate = true; t.repeat.set(rx, ry);
    m = new THREE.MeshStandardMaterial({ map: t, roughness: 0.7, flatShading: true, vertexColors: true }); hazCache.set(k, m); }
  return m;
}
// paint vertex colours (and optionally move vertices) by position
function paint(g, fn) {
  const P = g.attributes.position, col = new Float32Array(P.count * 3), c = new THREE.Color(), v = V3();
  for (let i = 0; i < P.count; i++) { v.fromBufferAttribute(P, i); c.setRGB(1, 1, 1); fn(v, c); P.setXYZ(i, v.x, v.y, v.z); col[i * 3] = c.r; col[i * 3 + 1] = c.g; col[i * 3 + 2] = c.b; }
  g.setAttribute('color', new THREE.BufferAttribute(col, 3)); g.computeVertexNormals(); return g;
}
// merge many (geometry, matrix, tint) into one non-indexed geometry with position/normal/uv/color
function merge(list) {
  const parts = []; let n = 0;
  for (const it of list) { const g = it.g.index ? it.g.toNonIndexed() : it.g.clone(); if (it.m) g.applyMatrix4(it.m); if (!g.attributes.normal) g.computeVertexNormals();
    parts.push([g, it.c]); n += g.attributes.position.count; }
  const pos = new Float32Array(n * 3), nor = new Float32Array(n * 3), uv = new Float32Array(n * 2), col = new Float32Array(n * 3).fill(1), c = new THREE.Color();
  let o = 0;
  for (const [g, cc] of parts) { const k = g.attributes.position.count; pos.set(g.attributes.position.array, o * 3); nor.set(g.attributes.normal.array, o * 3);
    if (g.attributes.uv) uv.set(g.attributes.uv.array, o * 2); if (g.attributes.color) col.set(g.attributes.color.array, o * 3);
    if (cc != null) { if (typeof cc === 'number' && cc <= 1) c.setRGB(cc, cc, cc); else c.set(cc); for (let i = 0; i < k; i++) { col[(o + i) * 3] *= c.r; col[(o + i) * 3 + 1] *= c.g; col[(o + i) * 3 + 2] *= c.b; } }
    o += k; g.dispose(); }
  const out = new THREE.BufferGeometry();
  out.setAttribute('position', new THREE.BufferAttribute(pos, 3)); out.setAttribute('normal', new THREE.BufferAttribute(nor, 3));
  out.setAttribute('uv', new THREE.BufferAttribute(uv, 2)); out.setAttribute('color', new THREE.BufferAttribute(col, 3));
  out.computeBoundingSphere(); out.computeBoundingBox(); return out;
}
const _m = new THREE.Matrix4(), _q = new THREE.Quaternion(), _e = new THREE.Euler(), _s = V3(1, 1, 1), _p = V3(), _v = V3();
// Kit: collects primitives per material, then merges them (one draw call per material)
class Kit {
  constructor() { this.parts = new Map(); }
  addM(mat, g, m, c) { let L = this.parts.get(mat); if (!L) this.parts.set(mat, L = []); L.push({ g, m: m && m.clone(), c }); return this; }
  add(mat, g, x = 0, y = 0, z = 0, rx = 0, ry = 0, rz = 0, c, q) { _p.set(x, y, z); if (q) _q.copy(q); else _q.setFromEuler(_e.set(rx, ry, rz)); return this.addM(mat, g, _m.compose(_p, _q, _s), c); }
  box(mat, w, h, d, x, y, z, rx, ry, rz, c) { return this.add(mat, new THREE.BoxGeometry(w, h, d), x, y, z, rx, ry, rz, c); }
  cyl(mat, rt, rb, h, seg, x, y, z, rx, ry, rz, c, open) { return this.add(mat, new THREE.CylinderGeometry(rt, rb, h, seg, 1, !!open), x, y, z, rx, ry, rz, c); }
  beam(mat, a, b, tw, th, c, seg) { const d = _v.subVectors(b, a); const len = d.length(); const q = new THREE.Quaternion().setFromUnitVectors(UP, d.normalize());
    const g = seg ? new THREE.CylinderGeometry(tw, tw, len, seg, 1, true) : new THREE.BoxGeometry(tw, len, th ?? tw);
    return this.add(mat, g, (a.x + b.x) / 2, (a.y + b.y) / 2, (a.z + b.z) / 2, 0, 0, 0, c, q); }
  geoms() { return [...this.parts].map(([mat, L]) => [merge(L), mat]); }
}
// build meshes from cached [geometry, material] pairs
function inst(parts, cast = true, recv = true) {
  const g = new THREE.Group();
  for (const [geo, mat] of parts) { const m = new THREE.Mesh(geo, mat); m.castShadow = cast; m.receiveShadow = recv; g.add(m); }
  return tag(g);
}
const once = f => { let v; return () => v || (v = f()); };
// basis matrix: panel u,v,w axes → world axes, then translate
const basis = (u, v, w, x, y, z) => new THREE.Matrix4().makeBasis(u, v, w).setPosition(x, y, z);
// corrugated sheet: length L along u, height H along v, outer face at w=0 with troughs down to -dep, normal +w
function corrugated(L, H, pitch, dep, rows = 1) {
  const np = Math.max(1, Math.round(L / pitch)), p = L / np, prof = [];
  for (let i = 0; i < np; i++) { const u = -L / 2 + i * p; prof.push([u, 0], [u + 0.3 * p, 0], [u + 0.5 * p, -dep], [u + 0.8 * p, -dep]); }
  prof.push([L / 2, 0]);
  const pos = [];
  for (let r = 0; r < rows; r++) { const v0 = -H / 2 + H * r / rows, v1 = -H / 2 + H * (r + 1) / rows;
    for (let i = 0; i < prof.length - 1; i++) { const [a, wa] = prof[i], [b, wb] = prof[i + 1];
      pos.push(a, v0, wa, b, v0, wb, b, v1, wb, a, v0, wa, b, v1, wb, a, v1, wa); } }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.computeVertexNormals(); return g;
}
// segmented box with chamfered edges; fn(v, c, edge) may move vertices (chips) and sets colour
function chamferBox(w, h, d, nx, ny, nz, ch, fn) {
  const g = new THREE.BoxGeometry(w, h, d, nx, ny, nz), P = g.attributes.position, col = new Float32Array(P.count * 3), c = new THREE.Color(), v = V3();
  const remap = (x, L, N) => { const i = Math.round((x / L + 0.5) * N); let r;
    if (i <= 0) r = -L / 2; else if (i >= N) r = L / 2; else if (i === 1) r = -L / 2 + ch; else if (i === N - 1) r = L / 2 - ch; else r = -L / 2 + ch + (i - 1) / (N - 2) * (L - 2 * ch);
    return [r, i <= 0 ? -1 : i >= N ? 1 : 0]; };
  for (let k = 0; k < P.count; k++) {
    const [x, ex] = remap(P.getX(k), w, nx), [y, ey] = remap(P.getY(k), h, ny), [z, ez] = remap(P.getZ(k), d, nz);
    v.set(x, y, z); const e = !!ex + !!ey + !!ez;
    if (e >= 2) { v.x -= ex * ch * 0.5; v.y -= ey * ch * 0.5; v.z -= ez * ch * 0.5; }
    c.setRGB(1, 1, 1); fn(v, c, e, ex, ey, ez); P.setXYZ(k, v.x, v.y, v.z); col[k * 3] = c.r; col[k * 3 + 1] = c.g; col[k * 3 + 2] = c.b;
  }
  g.setAttribute('color', new THREE.BufferAttribute(col, 3)); g.computeVertexNormals(); return g;
}
const shadows = (o, recv = true) => { o.traverse(m => { if (m.isMesh) { m.castShadow = true; m.receiveShadow = recv; } }); return tag(o); };
// concrete colouring: noise, dirt splash near the ground, rain streaks
function concreteTone(v, c, groundY, seed = 0) {
  const n = 0.9 + hsh(v.x + seed, v.y, v.z) * 0.16; const hg = v.y - groundY;
  let k = n * (hg < 0.45 ? 0.72 + 0.28 * Math.max(0, hg) / 0.45 : 1);
  if (hsh(Math.floor(v.x * 2.3) + seed, 7) > 0.62) k *= 1 - 0.1 * Math.min(1, Math.max(0, hg) / 3);
  k *= 1.15; c.setRGB(k * 0.98, k, k * 1.03);
}

// ───────────────────────────── crash barrier
// Crash barrier block: collider half extents (4, 1.5, 1.2); impact face is local −z.
const barrierParts = once(() => {
  const k = new Kit(), G = -1.5;           // local ground height
  // reinforced concrete block, face set back behind the load-cell wall (front of the wall plates = collider face z=-1.2)
  const ZF = -1.15, D = 1.2 - ZF;
  const block = chamferBox(8, 3, D, 34, 13, 10, 0.07, (v, c, e, ex, ey, ez) => {
    concreteTone(v, c, -1.5, 3);
    if (e >= 2 && hsh(v.x, v.y, v.z) > 0.66 && v.y > -1.4) {      // chipped edges: old impacts and handling damage
      const d = 0.025 + hsh(v.z, v.x, 3) * 0.06; v.x -= ex * d; v.y -= ey * d; v.z -= ez * d; c.multiplyScalar(1.18);
    }
  });
  block.translate(0, 0, (1.2 + ZF) / 2);
  k.addM(MAT.concrete, block);
  // steel backing plate and load-cell wall (grid of square plates on load cells)
  const COLS = 19, ROWS = 4, S = 0.4, X0 = -COLS * S / 2, Y0 = G + 0.1;
  k.box(MAT.dark, COLS * S + 0.04, ROWS * S + 0.04, 0.02, 0, Y0 + ROWS * S / 2, ZF - 0.01);
  for (let i = 0; i < COLS; i++) for (let j = 0; j < ROWS; j++) {
    const x = X0 + (i + 0.5) * S, y = Y0 + (j + 0.5) * S;
    const dent = hsh(i, j, 1) > 0.8 ? 0.008 + hsh(j, i) * 0.012 : 0;            // a few plates pushed in by earlier tests
    const tone = 0.82 + hsh(i, j, 5) * 0.3 - (Math.abs(x) < 1.3 && j < 3 ? 0.18 : 0);
    k.box(MAT.galv, S - 0.025, S - 0.025, 0.03, x, y, -1.185 + dent, (hsh(i, j, 2) - 0.5) * 0.02 * (dent ? 1 : 0), (hsh(j, i, 2) - 0.5) * 0.02 * (dent ? 1 : 0), 0, new THREE.Color(tone, tone, tone * 0.98));
    for (const [bx, by] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) k.box(MAT.dark, 0.026, 0.026, 0.014, x + bx * (S / 2 - 0.05), y + by * (S / 2 - 0.05), -1.204 + dent);
  }
  // hazard-painted steel edging around the wall
  const FW = COLS * S, FY0 = Y0 - 0.06, FY1 = Y0 + ROWS * S + 0.06;
  k.box(hazMat(FW / 0.48, 1), FW + 0.24, 0.12, 0.045, 0, FY1 + 0.04, -1.1775);
  k.box(hazMat(FW / 0.48, 1), FW + 0.24, 0.1, 0.045, 0, G + 0.05, -1.1775);
  for (const s of [-1, 1]) k.box(hazMat(1, Math.round((FY1 - G + 0.1) * 4 / 0.12)), 0.12, FY1 - G + 0.1, 0.045, s * (FW / 2 + 0.06), (G + FY1) / 2 + 0.05, -1.1775);
  // hazard band across the top and down the front corners of the concrete
  k.add(hazMat(8 / 1.4, 1), new THREE.PlaneGeometry(7.86, 0.35), 0, 1.1, ZF - 0.003, 0, Math.PI, 0);
  for (const s of [-1, 1]) {
    k.add(hazMat(1, 1.1 * 4 / 0.32), new THREE.PlaneGeometry(0.32, 1.1), s * 3.85, 0.38, ZF - 0.003, 0, Math.PI, 0);
    k.add(hazMat(1, 28), new THREE.PlaneGeometry(0.4, 2.8), s * 4.004, 0, ZF + 0.3, 0, s * Math.PI / 2, 0);
  }
  // lifting anchors on top and steel base angle at the back
  for (const x of [-2.6, 2.6]) for (const z of [-0.5, 0.6]) {
    k.add(MAT.steel, new THREE.TorusGeometry(0.07, 0.014, 4, 8, Math.PI), x, 1.5, z);
    k.box(MAT.dark, 0.2, 0.01, 0.12, x, 1.5, z);
  }
  k.box(MAT.dark, 7.6, 0.12, 0.012, 0, G + 0.06, 1.206);
  return k.geoms();
});
export function barrier() { return inst(barrierParts()); }

// ───────────────────────────── poles and light masts
// Vertical steel pole, radius r, height h, origin at mid height (collider: cylinder r,h).
const poleCache = new Map();
const gussetGeo = (r, gw, gh) => { const s = new THREE.Shape(); s.moveTo(r, 0); s.lineTo(r + gw, 0); s.lineTo(r + gw, 0.015); s.lineTo(r, gh); s.lineTo(r, 0);
  const g = new THREE.ExtrudeGeometry(s, { depth: 0.012, bevelEnabled: false }); g.translate(0, 0, -0.006); return g; };
export function pole(r, h, color = 0x6f7477) {
  const key = [r, h, color].join();
  let parts = poleCache.get(key);
  if (!parts) {
    const k = new Kit(), y0 = -h / 2, mast = h > 5, tube = M(color, { metalness: 0.55, roughness: 0.45 });
    const rt = mast ? r * 0.62 : r, rAt = y => r + (rt - r) * (y - y0) / h;
    const FH = 0.015, BH = 0.025, yb = y0 + FH + BH;
    k.cyl(tube, rt, r, h - FH - BH, mast ? 12 : 16, 0, (yb + h / 2) / 2, 0, 0, 0, 0, undefined, true);
    k.cyl(tube, rt * 1.03, rt * 1.03, 0.02, mast ? 12 : 16, 0, h / 2 - 0.01, 0);
    // foundation (flush, 1.5 cm proud) with anchor plate, bolts and gussets
    const fs = Math.max(0.6, r * 4.6), bp = r * 2.8;
    k.add(MAT.concrete, paint(new THREE.BoxGeometry(fs, FH, fs, 3, 1, 3), (v, c) => { const n = 0.95 + hsh(v.x, v.z) * 0.15; c.setRGB(n * 1.08, n * 1.06, n); }), 0, y0 + FH / 2, 0);
    k.box(MAT.dark, bp, BH, bp, 0, y0 + FH + BH / 2, 0);
    for (const [sx, sz] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) {
      k.cyl(MAT.galv, 0.024, 0.024, 0.022, 6, sx * bp * 0.37, yb + 0.011, sz * bp * 0.37);
      k.cyl(MAT.galv, 0.011, 0.011, 0.05, 6, sx * bp * 0.37, yb + 0.025, sz * bp * 0.37);
    }
    const gh = mast ? 0.34 : 0.16, gg = gussetGeo(r * 0.98, bp / 2 - r - 0.012, gh);
    for (let i = 0; i < 4; i++) k.add(MAT.dark, gg, 0, yb, 0, 0, Math.PI / 4 + i * Math.PI / 2, 0);
    // hazard band (rx=1 so it wraps seamlessly; ry keeps the stripes at 45°)
    const b0 = mast ? y0 + 0.3 : y0 + 0.8, b1 = mast ? y0 + 1.5 : y0 + 1.6, rb = rAt(b0), rbt = rAt(b1);
    k.add(hazMat(1, (b1 - b0) * 4 / (2 * Math.PI * rb)), new THREE.CylinderGeometry(rbt * 1.012, rb * 1.012, b1 - b0, mast ? 12 : 16, 1, true), 0, (b0 + b1) / 2, 0);
    if (mast) { // service hatch and a cable junction box
      const r1 = rAt(y0 + 0.75); k.box(MAT.dark, 0.11, 0.32, 0.03, 0, y0 + 0.75, r1 - 0.004);
      k.box(MAT.galv, 0.012, 0.04, 0.02, 0.035, y0 + 0.75, r1 + 0.018);
      const r2 = rAt(y0 + 2.6); k.box(MAT.galv, 0.18, 0.24, 0.1, 0, y0 + 2.6, -(r2 + 0.045));
      k.cyl(MAT.black, 0.012, 0.012, 2.4, 5, 0, y0 + 1.42, -(rAt(y0 + 1.4) + 0.012));
    } else {    // rigid side-impact pole: a heavier collar welded at its base
      k.cyl(MAT.dark, r * 1.06, r * 1.06, 0.05, 16, 0, yb + 0.025, 0);
    }
    parts = k.geoms(); poleCache.set(key, parts);
  }
  const g = inst(parts); g.children.forEach(m => { m.receiveShadow = false; }); return g;
}
// Lamp head that sits on top of a 9 m mast (origin at the head centre, mast top at y=-0.125).
const lampParts = once(() => {
  const k = new Kit();
  k.cyl(MAT.galv, 0.085, 0.1, 0.32, 10, 0, -0.06, 0);                      // spigot over the mast top
  k.box(MAT.galv, 2.1, 0.08, 0.08, 0, 0.12, 0);                            // crossarm
  k.box(MAT.galv, 2.1, 0.05, 0.05, 0, -0.08, -0.08);
  for (const s of [-1, 1]) k.beam(MAT.galv, V3(s * 0.08, -0.08, 0), V3(s * 0.75, 0.1, 0), 0.035);
  k.box(MAT.dark, 0.26, 0.3, 0.14, 0, -0.32, -0.12);                       // control gear box
  k.cyl(MAT.galv, 0.008, 0.008, 0.9, 4, 0.12, 0.6, 0);                     // lightning rod
  for (const x of [-0.82, -0.28, 0.28, 0.82]) {                           // floodlights, facing +z, tilted down
    const tilt = 0.55;
    const f = new THREE.Group(); f.position.set(x, 0.1, 0.09); f.rotation.x = tilt;
    const loc = (gx, gy, gz) => { const p = V3(gx, gy, gz).applyEuler(f.rotation).add(f.position); return p; };
    const add = (mat, geo, gx, gy, gz) => { const p = loc(gx, gy, gz); k.add(mat, geo, p.x, p.y, p.z, tilt, 0, 0); };
    add(MAT.dark, new THREE.BoxGeometry(0.44, 0.34, 0.11), 0, -0.02, 0.1);  // housing
    add(MAT.lamp, new THREE.BoxGeometry(0.38, 0.28, 0.01), 0, -0.02, 0.157);
    for (let i = -2; i <= 2; i++) add(MAT.dark, new THREE.BoxGeometry(0.008, 0.3, 0.05), i * 0.08, -0.02, 0.02);  // heat-sink fins
    add(MAT.dark, new THREE.BoxGeometry(0.44, 0.03, 0.06), 0, 0.165, 0.18); // visor
    for (const s of [-1, 1]) k.box(MAT.galv, 0.012, 0.18, 0.05, x + s * 0.235, 0.05, 0.07);  // yoke
  }
  return k.geoms();
});
export function lampHead() {
  const g = inst(lampParts(), true, false);
  // floodlights aim at the middle of the pad once the game has placed the head
  g.addEventListener('added', function f() { g.removeEventListener('added', f); g.rotation.y = Math.atan2(-g.position.x, -g.position.z); });
  return g;
}

// ───────────────────────────── jersey barrier
// Jersey barrier segment: collider half (0.22, 0.405, 1.95).
const jerseyParts = once(() => {
  const k = new Kit(), H = 0.81, L = 3.9;
  // New-Jersey profile (half widths), slightly slimmer than the 0.6 m standard to stay on the collider
  const prof = [[0.25, 0], [0.25, 0.08], [0.125, 0.33], [0.085, 0.79], [0.07, 0.81]];
  const shapeFrom = y0 => { const s = new THREE.Shape(); const pts = prof.filter(p => p[1] >= y0);
    s.moveTo(-pts[0][0], y0); pts.forEach(p => s.lineTo(p[0], p[1])); [...pts].reverse().forEach(p => s.lineTo(-p[0], p[1])); return s; };
  const full = shapeFrom(0), pocket = shapeFrom(0.08);
  const segs = [[-1.95, -1.08, full, 3], [-1.08, -0.78, pocket, 1], [-0.78, 0.78, full, 5], [0.78, 1.08, pocket, 1], [1.08, 1.95, full, 3]];
  for (const [z0, z1, sh, st] of segs) {
    const g = new THREE.ExtrudeGeometry(sh, { depth: z1 - z0, steps: st, bevelEnabled: false }); g.translate(0, -H / 2, z0);
    paint(g, (v, c) => {
      const hg = v.y + H / 2, top = hg > 0.78, end = Math.abs(v.z) > 1.93, edge = top || (end && (Math.abs(v.x) > 0.06 || hg < 0.02));
      concreteTone(v, c, -H / 2, 11);
      if (edge && hsh(v.x, v.y, v.z) > 0.6) { const d = 0.012 + hsh(v.z, v.y) * 0.03; v.y -= top ? d : 0; v.x *= 0.88; if (end) v.z -= Math.sign(v.z) * d; c.multiplyScalar(1.15); }
      if (hg > 0.05 && hg < 0.32 && Math.abs(v.x) > 0.12 && hsh(Math.floor(v.z * 2.5), Math.sign(v.x)) > 0.72) c.multiplyScalar(0.55);   // tyre scuffs on the slope
    });
    k.addM(MAT.concrete, g);
  }
  // pin-and-loop connectors at the ends, lifting anchors on top
  for (const s of [-1, 1]) for (const y of [-0.2, 0.15]) k.add(MAT.rust, new THREE.TorusGeometry(0.045, 0.011, 4, 8, Math.PI), 0, y, s * 1.95, 0, s > 0 ? -Math.PI / 2 : Math.PI / 2, Math.PI / 2);
  for (const z of [-1.0, 1.0]) k.add(MAT.rust, new THREE.TorusGeometry(0.035, 0.009, 4, 6, Math.PI), 0, H / 2 - 0.01, z, 0, Math.PI / 2, 0);
  return k.geoms();
});
MAT.rust = M(0x6b4a33, { metalness: 0.4, roughness: 0.8 });
export function jersey() { const g = new THREE.Group(); const m = inst(jerseyParts()); if (Math.random() < 0.5) m.rotation.y = Math.PI; g.add(m); return tag(g); }

// ───────────────────────────── ramps
// Ramp / kicker slab: collider is a box of full size (w,h,l), already tilted by the game.
const treadTex = canvasTex(128, 128, (x, w, h) => {
  x.fillStyle = '#8e9091'; x.fillRect(0, 0, w, h);
  for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++) { const cx = i * 32 + 16, cy = j * 32 + 16, r = (i + j) % 2 ? Math.PI / 4 : -Math.PI / 4;
    x.fillStyle = 'rgba(30,30,30,.55)'; x.beginPath(); x.ellipse(cx + 1.5, cy + 1.5, 12, 3, r, 0, 7); x.fill();
    x.fillStyle = '#b4b6b6'; x.beginPath(); x.ellipse(cx, cy, 12, 3, r, 0, 7); x.fill(); }
  for (let i = 0; i < 900; i++) { x.fillStyle = `rgba(${60 + Math.random() * 40},${50 + Math.random() * 30},40,.12)`; x.fillRect(Math.random() * w, Math.random() * h, 2, 2); }
}, true);
const rampMats = new Map();
export function ramp(w, h, l) {
  const key = [w, h, l].join(); let parts = rampMats.get(key);
  if (!parts) {
    const k = new Kit(), t = treadTex.clone(); t.needsUpdate = true; t.repeat.set(w / 0.3, l / 0.3);
    const deck = new THREE.MeshStandardMaterial({ map: t, bumpMap: t, bumpScale: 1.5, metalness: 0.3, roughness: 0.55, flatShading: true, vertexColors: true });
    const T = 0.012, CW = 0.09, top = h / 2;
    k.box(deck, w, T, l, 0, top - T / 2, 0);
    for (const s of [-1, 1]) {        // side C-channels, open outward
      k.box(MAT.steel, T, h - T, l, s * (w / 2 - CW), -T / 2, 0);
      k.box(MAT.yellow, CW, 0.014, l, s * (w / 2 - CW / 2), top - T - 0.007, 0);
      k.box(MAT.steel, CW, 0.014, l, s * (w / 2 - CW / 2), -h / 2 + 0.007, 0);
      for (let z = -l / 2 + 0.5; z < l / 2; z += 1.0) k.box(MAT.steel, CW - 0.01, h - 0.05, 0.01, s * (w / 2 - CW / 2), -T / 2, z);
    }
    const ni = Math.max(1, Math.round(w / 1.3) - 1);
    for (let i = 1; i <= ni; i++) k.box(MAT.dark, 0.08, h * 0.55, l - 0.1, -w / 2 + CW + i * (w - 2 * CW) / (ni + 1), top - T - h * 0.275, 0);
    for (let z = -l / 2 + 0.7; z < l / 2 - 0.3; z += 1.2) k.box(MAT.dark, w - 2 * CW, h * 0.45, 0.07, 0, top - T - h * 0.225, z);
    k.box(hazMat(w / (4 * h)), w, h, 0.012, 0, 0, l / 2 - 0.006);             // painted end plate
    parts = { geoms: k.geoms(), w, h, l }; rampMats.set(key, parts);
  }
  const g = inst(parts.geoms);
  // support legs down to the ground, built once the game has positioned and tilted the slab
  g.addEventListener('added', function f() {
    g.removeEventListener('added', f);
    try {
      const q = g.quaternion, P = g.position, k = new Kit(), xs = [-(w / 2 - 0.15), w / 2 - 0.15];
      const zs = []; for (let z = -l / 2 + 0.4; z < l / 2 - 0.2; z += 1.7) zs.push(z); zs.push(l / 2 - 0.2);
      const tops = [];
      for (const z of zs) {
        const row = [];
        for (const x of xs) { const o = V3(x, -h / 2, z).applyQuaternion(q); const y = P.y + o.y; if (y < 0.22) { row.push(null); continue; }
          k.beam(MAT.steel, V3(o.x, -P.y, o.z), V3(o.x, o.y, o.z), 0.1); k.box(MAT.dark, 0.26, 0.02, 0.26, o.x, -P.y + 0.01, o.z); row.push(o); }
        if (row[0] && row[1] && Math.min(row[0].y, row[1].y) + P.y > 0.7) k.beam(MAT.steel, V3(row[0].x, -P.y + 0.15, row[0].z), V3(row[1].x, row[1].y - 0.1, row[1].z), 0.05);
        tops.push(row);
      }
      for (let i = 1; i < tops.length; i++) for (let s = 0; s < 2; s++) { const a = tops[i - 1][s], b = tops[i][s];
        if (a && b) { const yy = (Math.min(a.y, b.y) - P.y) * 0.45; k.beam(MAT.steel, V3(a.x, -P.y + yy, a.z), V3(b.x, -P.y + yy, b.z), 0.05); } }
      if (k.parts.size) { const lg = inst(k.geoms()); lg.quaternion.copy(q).invert(); g.add(lg); }
    } catch (e) { console.error('ramp legs', e); }
  });
  return g;
}

// ───────────────────────────── hangar
// Hangar: collider box half (17, 6, 11) centred at y=6; origin of this model is on the GROUND under that centre. Door faces +z.
function spans(lo, hi, holes) { let s = [[lo, hi]];
  for (const [a, b] of holes) { const n = []; for (const [p, q] of s) { if (b <= p || a >= q) { n.push([p, q]); continue; } if (a > p) n.push([p, a]); if (b < q) n.push([b, q]); } s = n; }
  return s; }
const hangarParts = once(() => {
  const k = new Kit(), X = 16.9, Z = 10.9, EAVE = 8, RIDGE = 11.95, PL = 0.5, SL = 0.23, ribs = [];
  const clad = M(0xbfc4c4, { metalness: 0.15, roughness: 0.6 }), roofM = M(0x6c7173, { metalness: 0.4, roughness: 0.5 }), trim = M(0x5d6468, { metalness: 0.25, roughness: 0.55 }),
    doorM = M(0x8796a0, { metalness: 0.15, roughness: 0.55 }), sky = M(0xd7dcd6, { roughness: 0.35, emissive: 0x30332f, emissiveIntensity: 0.4 });
  const cTone = (v, c) => concreteTone(v, c, 0, 21);
  // plinth (front split around the doors)
  const pl = (x0, x1, z0, z1) => k.addM(MAT.concrete, paint(new THREE.BoxGeometry(x1 - x0, PL, z1 - z0, Math.ceil((x1 - x0) / 1.5), 1, Math.ceil((z1 - z0) / 1.5)), cTone), _m.makeTranslation((x0 + x1) / 2, PL / 2, (z0 + z1) / 2));
  pl(-16.98, 16.98, -10.98, -10.8); pl(-16.98, -16.8, -10.8, 10.8); pl(16.8, 16.98, -10.8, 10.8);
  pl(-16.98, -6.35, 10.8, 10.98); pl(6.35, 8.4, 10.8, 10.98); pl(9.7, 16.98, 10.8, 10.98);
  // wall box, gable prism, roof slabs
  k.box(clad, 2 * X, EAVE - PL, 2 * Z, 0, PL + (EAVE - PL) / 2, 0);
  { const s = new THREE.Shape(); s.moveTo(-X, EAVE); s.lineTo(X, EAVE); s.lineTo(0, RIDGE - 0.1); s.lineTo(-X, EAVE);
    const g = new THREE.ExtrudeGeometry(s, { depth: 2 * Z, bevelEnabled: false }); g.translate(0, 0, -Z); k.addM(clad, g); }
  const a = Math.atan(SL), RX = 17.05, len = RX / Math.cos(a), n = V3(Math.sin(a), Math.cos(a), 0);
  const skyZ = [-6, 0, 6];
  for (const s of [-1, 1]) {
    const mid = V3(s * RX / 2, RIDGE - RX * SL / 2, 0);
    k.box(roofM, len, 0.08, 22.1, mid.x - s * n.x * 0.04, mid.y - n.y * 0.04, 0, 0, 0, -s * a);
    for (const zc of skyZ) k.box(sky, len - 2.6, 0.03, 1.3, mid.x + s * n.x * 0.01 + s * 0.3, mid.y + n.y * 0.01 - 0.3 * SL, zc, 0, 0, -s * a);
    for (let z = -10.8; z <= 10.81; z += 0.45) { if (skyZ.some(zc => Math.abs(z - zc) < 0.8)) continue;
      ribs.push({ p: V3(mid.x + s * n.x * 0.02, mid.y + n.y * 0.02, z), r: V3(0, 0, -s * a), s: V3(len - 0.05, 0.045, 0.06), c: 0x6c7173 }); }
    // verge trims along the gable edges
    for (const z of [-11.02, 11.02]) k.box(trim, len, 0.2, 0.06, mid.x, mid.y - 0.05, z, 0, 0, -s * a);
    // gutter and down pipes
    k.box(MAT.galv, 0.12, 0.12, 22.1, s * 16.99, EAVE - 0.06, 0);
    for (const z of [-10.55, 10.55]) { k.cyl(MAT.galv, 0.055, 0.055, 7.6, 8, s * 16.985, 4.15, z);
      k.box(MAT.concreteL, 0.35, 0.01, 0.5, s * 16.9, 0.005, z); }
  }
  k.box(trim, 0.55, 0.08, 22.1, 0, RIDGE + 0.01, 0);     // ridge cap
  for (const [x, z] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) k.box(trim, 0.14, EAVE - PL, 0.14, x * 16.93, PL + (EAVE - PL) / 2, z * 10.93);
  // wall ribs (trapezoidal cladding), skipping openings
  const vr = (fx, fz, along, holes, top) => {
    for (let t = -along + 0.25; t <= along - 0.2; t += 0.5) {
      const hh = holes.filter(o => t > o[0] - 0.05 && t < o[1] + 0.05).map(o => [o[2], o[3]]);
      for (const [y0, y1] of spans(PL, top ? top(t) : EAVE, hh)) if (y1 - y0 > 0.05) {
        const p = fx ? V3(fx, (y0 + y1) / 2, t) : V3(t, (y0 + y1) / 2, fz);
        ribs.push({ p, r: V3(), s: fx ? V3(0.05, y1 - y0, 0.07) : V3(0.07, y1 - y0, 0.05), c: 0xbfc4c4 });
      }
    }
  };
  const winZ = [-7.5, -2.5, 2.5, 7.5], winHoles = winZ.map(z => [z - 1.85, z + 1.85, 4.55, 5.65]);
  vr(16.925, 0, 10.9, winHoles); vr(-16.925, 0, 10.9, [...winHoles, [3.35, 4.65, 0, 2.45]]);
  vr(0, 10.925, 16.9, [[-6.45, 6.45, 0, 6.65], [8.3, 9.8, 0, 2.45], [-1.2, 1.2, 9.1, 10.1]]);
  vr(0, -10.925, 16.9, []);
  for (const fz of [10.925, -10.925]) for (let x = -16.65; x <= 16.66; x += 0.5) {
    const top = RIDGE - 0.12 - (RIDGE - 0.12 - EAVE) * Math.abs(x) / X; if (top - EAVE < 0.1) continue;
    const hs = fz > 0 && Math.abs(x) < 1.25 ? spans(EAVE, top, [[9.1, 10.1]]) : [[EAVE, top]];
    for (const [y0, y1] of hs) ribs.push({ p: V3(x, (y0 + y1) / 2, fz), r: V3(), s: V3(0.07, y1 - y0, 0.05), c: 0xbfc4c4 });
  }
  // side ribbon windows
  for (const s of [-1, 1]) for (const z of winZ) {
    k.box(MAT.glass, 0.02, 1.0, 3.6, s * 16.93, 5.1, z);
    for (const y of [4.56, 5.64]) k.box(trim, 0.07, 0.08, 3.76, s * 16.95, y, z);
    for (const dz of [-1.84, -0.6, 0.6, 1.84]) k.box(trim, 0.07, 1.1, 0.07, s * 16.95, 5.1, z + dz);
    k.box(trim, 0.11, 0.04, 3.8, s * 16.98, 4.5, z);
  }
  // sectional door
  k.box(MAT.black, 12.4, 6.45, 0.02, 0, 3.22, 10.91);
  for (let i = 0; i < 6; i++) { const y = 0.51 + i;
    k.box(doorM, 12, 0.97, 0.05, 0, y, 10.935);
    k.box(doorM, 12, 0.05, 0.02, 0, y + 0.22, 10.968, 0, 0, 0, 0xdddddd); k.box(doorM, 12, 0.05, 0.02, 0, y - 0.22, 10.968, 0, 0, 0, 0xdddddd);
    if (i === 3) for (let j = 0; j < 8; j++) k.box(MAT.glass, 0.85, 0.32, 0.02, -5.25 + j * 1.5, y, 10.965);
  }
  k.box(MAT.rubber, 12, 0.04, 0.07, 0, 0.02, 10.94);
  for (const s of [-1, 1]) { k.box(trim, 0.35, 6.6, 0.12, s * 6.2, 3.3, 10.95); k.box(hazMat(1, 1.5 / 0.36 * 4), 0.36, 1.5, 0.124, s * 6.2, 0.75, 10.95); }
  k.box(trim, 12.75, 0.45, 0.12, 0, 6.82, 10.95);
  k.box(trim, 0.6, 0.16, 0.12, 0, 7.2, 10.98); k.box(MAT.lamp, 0.5, 0.02, 0.08, 0, 7.115, 10.99);
  // gable louvre
  k.box(trim, 2.4, 1.0, 0.05, 0, 9.6, 10.95);
  for (let i = 0; i < 6; i++) k.box(MAT.dark, 2.2, 0.06, 0.06, 0, 9.2 + i * 0.16, 10.98, -0.6, 0, 0);
  // personnel doors (front and west side)
  const pdoor = (x, z, ry) => {
    const q = new THREE.Quaternion().setFromEuler(_e.set(0, ry, 0)), at = (dx, dy, dz) => V3(dx, dy, dz).applyQuaternion(q).add(V3(x, 0, z));
    const put = (mat, w, h, d, dx, dy, dz) => { const p = at(dx, dy, dz); k.box(mat, w, h, d, p.x, p.y, p.z, 0, ry, 0); };
    put(trim, 1.32, 2.42, 0.07, 0, 1.21, 0); put(doorM, 1.12, 2.24, 0.04, 0, 1.12, 0.045); put(MAT.glass, 0.34, 0.5, 0.01, 0, 1.6, 0.068);
    put(MAT.galv, 0.14, 0.035, 0.035, 0.36, 1.05, 0.08); put(trim, 0.4, 0.14, 0.1, 0, 2.62, 0.02); put(MAT.lamp, 0.3, 0.02, 0.06, 0, 2.54, 0.03);
    const p = at(0, 0, 0.45); k.box(MAT.concreteL, 1.6, 0.01, 0.9, p.x, 0.005, p.z, 0, ry, 0);
  };
  pdoor(9.05, 10.93, 0); pdoor(-16.93, 4.0, -Math.PI / 2);
  // electrical cabinet on the back wall, conduit
  k.box(MAT.galv, 0.8, 1.2, 0.08, 5, 1.4, -10.98, 0, 0, 0); k.cyl(MAT.black, 0.03, 0.03, 5.6, 6, 5.2, 4.8, -10.97);
  // apron (отмосток) and the slab in front of the door: flat, 1 cm
  const ap = (w, d, x, z, c) => k.addM(MAT.concreteL, paint(new THREE.BoxGeometry(w, 0.01, d, Math.ceil(w / 2), 1, Math.ceil(d / 2)), (v, cc) => { const t = 0.9 + hsh(v.x, v.z, 4) * 0.12; cc.setRGB(t, t, t * 0.98); }), _m.makeTranslation(x, 0.005, z), c);
  ap(36, 1.0, 0, -11.5); ap(1.0, 22, -17.5, 0); ap(1.0, 22, 17.5, 0); ap(36, 1.0, -0.0, 11.5); ap(14, 6, 0, 15);
  // instanced cladding ribs
  return { geoms: k.geoms(), ribs };
});
const ribGeo = once(() => paint(new THREE.BoxGeometry(1, 1, 1), () => {}));
const ribMat = M(0xffffff, { metalness: 0.15, roughness: 0.6 });
export function hangar() {
  const P = hangarParts(), hg = inst(P.geoms);
  const im = new THREE.InstancedMesh(ribGeo(), ribMat, P.ribs.length), m = new THREE.Matrix4(), c = new THREE.Color();
  P.ribs.forEach((r, i) => { im.setMatrixAt(i, m.compose(r.p, _q.setFromEuler(_e.set(r.r.x, r.r.y, r.r.z)), r.s)); im.setColorAt(i, c.set(r.c)); });
  im.castShadow = true; im.receiveShadow = true; hg.add(im);
  return hg;
}

// ───────────────────────────── observation tower
// Observation tower on 4 legs (no collider), origin on the ground.
const towerParts = once(() => {
  const k = new Kit(), L = 1.5, PH = 10, legM = M(0x55595b, { metalness: 0.5, roughness: 0.5 }), cabM = M(0xb9b4a6, { roughness: 0.7 }), grate = M(0x46494b, { metalness: 0.5, roughness: 0.6 });
  // legs, footings, bracing
  for (const [x, z] of [[-L, -L], [L, -L], [-L, L], [L, L]]) {
    k.box(legM, 0.22, PH, 0.22, x, PH / 2, z); k.box(MAT.concreteL, 0.8, 0.02, 0.8, x, 0.01, z); k.box(MAT.dark, 0.4, 0.03, 0.4, x, 0.035, z);
  }
  const faces = [[V3(-L, 0, -L), V3(L, 0, -L)], [V3(L, 0, -L), V3(L, 0, L)], [V3(L, 0, L), V3(-L, 0, L)], [V3(-L, 0, L), V3(-L, 0, -L)]];
  for (let lv = 0; lv < 4; lv++) { const y0 = lv * 2.5 + (lv ? 0 : 0.3), y1 = (lv + 1) * 2.5;
    for (const [a, b] of faces) {
      k.beam(legM, V3(a.x, y1, a.z), V3(b.x, y1, b.z), 0.1);
      k.beam(legM, V3(a.x, y0, a.z), V3(b.x, y1, b.z), 0.06); k.beam(legM, V3(b.x, y0, b.z), V3(a.x, y1, a.z), 0.06);
    } }
  // platform with grating and railing
  const PW = 2.4; k.box(MAT.dark, 2 * PW, 0.18, 2 * PW, 0, PH + 0.01, 0); k.box(grate, 2 * PW - 0.04, 0.02, 2 * PW - 0.04, 0, PH + 0.11, 0);
  const rail = (a, b) => { const d = a.distanceTo(b), n = Math.max(1, Math.round(d / 1.2));
    for (let i = 0; i <= n; i++) { const p = a.clone().lerp(b, i / n); k.box(MAT.yellow, 0.05, 1.1, 0.05, p.x, p.y + 0.55, p.z); }
    k.beam(MAT.yellow, V3(a.x, a.y + 1.1, a.z), V3(b.x, b.y + 1.1, b.z), 0.045); k.beam(MAT.yellow, V3(a.x, a.y + 0.55, a.z), V3(b.x, b.y + 0.55, b.z), 0.03);
    k.beam(MAT.yellow, V3(a.x, a.y + 0.06, a.z), V3(b.x, b.y + 0.06, b.z), 0.012, 0.12); };
  const py = PH + 0.12, e = PW - 0.03;
  rail(V3(-e, py, e), V3(e, py, e)); rail(V3(e, py, e), V3(e, py, -e)); rail(V3(e, py, -e), V3(-e, py, -e)); rail(V3(-e, py, -1.4), V3(-e, py, e));
  // switchback stair along the west side
  const SX0 = -3.4, SX1 = -2.42, SW = SX1 - SX0, sxm = (SX0 + SX1) / 2;
  for (let f = 0; f < 4; f++) {
    const y0 = f * 2.5, y1 = y0 + 2.5, s = f % 2 ? -1 : 1, z0 = -s * 1.5, z1 = s * 1.5;
    for (const x of [SX0 + 0.03, SX1 - 0.03]) k.beam(legM, V3(x, y0 - 0.08, z0), V3(x, y1 - 0.08, z1), 0.04, 0.2);
    for (let i = 0; i < 12; i++) { const t = (i + 0.5) / 12; k.box(grate, SW - 0.08, 0.04, 0.24, sxm, y0 + 2.5 * t - 0.02, z0 + (z1 - z0) * t); }
    k.beam(MAT.yellow, V3(SX0 + 0.02, y0 + 1.0, z0), V3(SX0 + 0.02, y1 + 1.0, z1), 0.035);
    for (const t of [0, 0.5, 1]) { const zz = z0 + (z1 - z0) * t, yy = y0 + 2.5 * t; k.box(MAT.yellow, 0.04, 1.0, 0.04, SX0 + 0.02, yy + 0.5, zz); }
    // landing
    const lz = s * 2.0; k.box(MAT.dark, SW, 0.08, 1.0, sxm, y1 - 0.04, lz); k.box(grate, SW - 0.04, 0.02, 0.96, sxm, y1 + 0.005, lz);
    k.beam(legM, V3(SX1, y1 - 0.08, s * 1.5), V3(-L, y1 - 0.1, s * L), 0.08);
    k.beam(legM, V3(SX0, y1 - 0.08, lz), V3(-L, y1 - 1.2, s * L), 0.06);
    if (f < 3) { rail(V3(SX0 + 0.02, y1, s * 1.5), V3(SX0 + 0.02, y1, s * 2.48)); rail(V3(SX0 + 0.02, y1, s * 2.48), V3(SX1, y1, s * 2.48)); }
    else rail(V3(SX0 + 0.02, y1, s * 1.5), V3(SX0 + 0.02, y1, s * 2.48));
  }
  // cab: solid lower walls, outward-leaning glazing, overhanging roof
  const C = 1.7, CB = py, CW0 = CB + 1.0, CW1 = CW0 + 1.5, R2 = Math.SQRT2;
  k.box(cabM, 2 * C, 1.0, 2 * C, 0, CB + 0.5, 0);
  k.add(MAT.glass, new THREE.CylinderGeometry(1.95 * R2, C * R2, CW1 - CW0, 4, 1, true), 0, (CW0 + CW1) / 2, 0, 0, Math.PI / 4, 0);
  k.add(MAT.glass, new THREE.CylinderGeometry(1.95 * R2 - 0.01, 1.95 * R2 - 0.01, 0.01, 4), 0, CW1 - 0.01, 0, 0, Math.PI / 4, 0);
  for (const [sx, sz] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) k.beam(MAT.dark, V3(sx * C, CW0, sz * C), V3(sx * 1.95, CW1, sz * 1.95), 0.06);
  for (const [sx, sz] of [[0, -1], [0, 1], [-1, 0], [1, 0]]) k.beam(MAT.dark, V3(sx * C, CW0, sz * C), V3(sx * 1.95, CW1, sz * 1.95), 0.045);
  k.box(MAT.dark, 2 * C + 0.08, 0.08, 2 * C + 0.08, 0, CW0, 0);
  k.box(MAT.dark, 4.5, 0.26, 4.5, 0, CW1 + 0.13, 0); k.box(cabM, 4.56, 0.08, 4.56, 0, CW1 + 0.22, 0);
  k.box(MAT.galv, 0.9, 0.5, 0.6, 0.9, CW1 + 0.5, -0.8); k.box(MAT.dark, 0.5, 0.02, 0.5, 0.9, CW1 + 0.76, -0.8);
  k.cyl(MAT.galv, 0.025, 0.035, 2.6, 6, -1.2, CW1 + 1.55, 1.2); k.box(MAT.galv, 0.9, 0.03, 0.03, -1.2, CW1 + 2.3, 1.2);
  k.cyl(M(0xc23a22, { emissive: 0x801a0a, emissiveIntensity: 0.6, roughness: 0.4 }), 0.07, 0.07, 0.14, 8, -1.2, CW1 + 2.92, 1.2);
  k.box(cabM, 0.06, 2.15, 0.95, -C - 0.03, CB + 1.075, -0.9); k.box(MAT.glass, 0.02, 0.6, 0.5, -C - 0.065, CB + 1.55, -0.9);
  k.box(MAT.galv, 0.03, 0.03, 0.14, -C - 0.08, CB + 1.0, -0.6);
  k.cyl(MAT.black, 0.025, 0.025, PH, 6, L + 0.15, PH / 2, L + 0.05);   // cable along one leg
  return k.geoms();
});
export function tower() { return inst(towerParts(), true, true); }

// ───────────────────────────── shipping container
// 40 ft shipping container: collider half (1.22, 1.3, 6.06), origin at centre.
const containerGeo = once(() => {
  const k = new Kit(), X = 1.22, Y = 1.3, Z = 6.06, body = MAT.white;
  const grime = (v, c) => { const hg = v.y + Y; let t = 0.92 + hsh(v.x, v.y, v.z) * 0.12; if (hg < 0.5) t *= 0.78 + 0.44 * hg;
    if (hsh(Math.floor(v.z * 1.3), Math.floor(v.y * 2), Math.sign(v.x)) > 0.83) c.setRGB(t * 0.8, t * 0.62, t * 0.48); else c.setRGB(t, t, t); };
  const panel = (L, H, pitch, dep, rows, m) => { const g = corrugated(L, H, pitch, dep, rows); g.applyMatrix4(m); return paint(g, grime); };
  const SH = 2.36, SL = 11.8;
  k.addM(body, panel(SL, SH, 0.278, 0.036, 2, basis(V3(0, 0, -1), V3(0, 1, 0), V3(1, 0, 0), X - 0.02, -0.02, 0)));
  k.addM(body, panel(SL, SH, 0.278, 0.036, 2, basis(V3(0, 0, 1), V3(0, 1, 0), V3(-1, 0, 0), -(X - 0.02), -0.02, 0)));
  k.addM(body, panel(SL, 2.2, 0.278, 0.02, 1, basis(V3(0, 0, 1), V3(1, 0, 0), V3(0, 1, 0), 0, Y - 0.025, 0)));
  k.addM(body, panel(2.14, SH, 0.27, 0.036, 2, basis(V3(-1, 0, 0), V3(0, 1, 0), V3(0, 0, -1), 0, -0.02, -(Z - 0.03))));
  // door end: two leaves with horizontal corrugation
  for (const s of [-1, 1]) {
    k.addM(body, panel(2.18, 1.04, 0.36, 0.022, 1, basis(V3(0, 1, 0), V3(-1, 0, 0), V3(0, 0, 1), s * 0.535, -0.02, Z - 0.03)));
    k.box(body, 1.08, 0.06, 0.03, s * 0.535, 1.08, Z - 0.035, 0, 0, 0, 0.9); k.box(body, 1.08, 0.08, 0.03, s * 0.535, -1.12, Z - 0.035, 0, 0, 0, 0.8);
    k.box(body, 0.05, 2.24, 0.03, s * 1.05, -0.02, Z - 0.035); k.box(body, 0.04, 2.24, 0.03, s * 0.02, -0.02, Z - 0.035);
    for (const y of [-0.95, -0.3, 0.35, 0.95]) k.cyl(MAT.dark, 0.028, 0.028, 0.12, 6, s * 1.1, y, Z - 0.02);   // hinges
    for (const bx of [0.22, 0.82]) {        // locking bars with guides, cams and handles
      const x = s * bx; k.cyl(MAT.galv, 0.016, 0.016, 2.48, 6, x, 0, Z - 0.004);
      for (const y of [-0.75, 0.75]) k.box(MAT.galv, 0.07, 0.04, 0.03, x, y, Z - 0.012);
      for (const y of [-1.2, 1.2]) k.box(MAT.dark, 0.08, 0.07, 0.05, x, y, Z - 0.02);
      k.box(MAT.galv, 0.035, 0.34, 0.02, x - s * 0.1, -0.12, Z - 0.003, 0, 0, s * 1.25);
      k.box(MAT.dark, 0.05, 0.08, 0.025, x - s * 0.2, -0.24, Z - 0.012);
    }
  }
  k.box(MAT.rubber, 0.03, 2.24, 0.02, 0, -0.02, Z - 0.02);
  // frame: corner posts, rails, castings, underside
  for (const sx of [-1, 1]) for (const sz of [-1, 1]) {
    k.box(body, 0.15, 2.36, 0.15, sx * (X - 0.075), 0, sz * (Z - 0.075), 0, 0, 0, 0.85);
    for (const sy of [-1, 1]) { const x = sx * (X - 0.089), y = sy * (Y - 0.059), z = sz * (Z - 0.081);
      k.box(MAT.dark, 0.178, 0.118, 0.162, x, y, z);
      k.box(MAT.black, 0.004, 0.05, 0.08, sx * X, y, z); k.box(MAT.black, 0.08, 0.05, 0.004, x, y, sz * Z); k.box(MAT.black, 0.06, 0.004, 0.1, x, sy * Y, z); }
  }
  for (const s of [-1, 1]) { k.box(body, 0.07, 0.16, 11.74, s * (X - 0.035), -Y + 0.08, 0, 0, 0, 0, 0.7); k.box(body, 0.06, 0.1, 11.74, s * (X - 0.03), Y - 0.05, 0, 0, 0, 0, 0.85); }
  for (const s of [-1, 1]) { k.box(body, 2.08, 0.18, 0.08, 0, -Y + 0.09, s * (Z - 0.04), 0, 0, 0, 0.7); k.box(body, 2.08, 0.12, 0.08, 0, Y - 0.06, s * (Z - 0.04), 0, 0, 0, 0.85); }
  k.box(MAT.dark, 2.3, 0.05, 11.8, 0, -Y + 0.03, 0);
  return k.parts;
});
const contMats = new Map();
export function container(color) {
  let parts = contMats.get(color);
  if (!parts) {
    const raw = containerGeo(); if (!containerGeo.merged) containerGeo.merged = new Map([...raw].map(([mat, L]) => [mat, merge(L)]));
    const paintM = M(color, { roughness: 0.72, metalness: 0.1 });
    parts = [...containerGeo.merged].map(([mat, g]) => [g, mat === MAT.white ? paintM : mat]); contMats.set(color, parts);
  }
  return inst(parts);
}

// ───────────────────────────── dynamic props
// Dynamic props (origin at collider centre): cone = cannon Cylinder(0.04,0.18,0.62); drum = Cylinder(0.29,0.29,0.88);
// tyre = Cylinder(0.4,0.4,0.22) (axis vertical, lying flat).
const coneParts = once(() => {
  const k = new Kit(), Y0 = -0.275, Y1 = 0.285, R0 = 0.155, R1 = 0.035, r = y => R0 + (R1 - R0) * (y - Y0) / (Y1 - Y0);
  const orange = M(0xd9541f, { roughness: 0.55 }), refl = M(0xeeeee6, { roughness: 0.28, metalness: 0.15 });
  k.cyl(orange, R1, R0, Y1 - Y0, 14, 0, (Y0 + Y1) / 2, 0, 0, 0, 0, undefined, true);
  k.cyl(orange, 0.022, R1, 0.025, 14, 0, Y1 + 0.0125, 0);
  for (const [a, b] of [[0.04, 0.16], [-0.09, -0.02]]) k.cyl(refl, r(b) + 0.003, r(a) + 0.003, b - a, 14, 0, (a + b) / 2, 0, 0, 0, 0, undefined, true);
  k.cyl(MAT.black, 0.205, 0.205, 0.035, 8, 0, -0.31 + 0.0175, 0, 0, Math.PI / 8, 0);
  k.cyl(MAT.black, R0 + 0.012, R0 + 0.02, 0.02, 14, 0, Y0 + 0.008, 0);
  return k.geoms();
});
export function cone() { const g = inst(coneParts()); g.children[0].rotation.y = Math.random() * 6; return g; }
const drumGeo = once(() => {
  const pts = [[0, -0.44], [0.255, -0.44], [0.275, -0.432], [0.283, -0.41], [0.283, -0.185], [0.29, -0.17], [0.29, -0.115], [0.283, -0.1], [0.283, 0.1], [0.29, 0.115], [0.29, 0.17], [0.283, 0.185],
    [0.283, 0.405], [0.277, 0.43], [0.262, 0.44], [0.248, 0.44], [0.242, 0.425], [0, 0.425]].map(([x, y]) => new THREE.Vector2(x, y));
  const k = new Kit(); k.add(MAT.white, new THREE.LatheGeometry(pts, 16));
  for (const x of [-0.15, 0.15]) { k.cyl(MAT.white, 0.032, 0.035, 0.022, 8, x, 0.436, 0.02, 0, 0, 0, 0.8); k.cyl(MAT.white, 0.018, 0.018, 0.008, 6, x, 0.449, 0.02, 0, 0, 0, 0.7); }
  return k.parts.get(MAT.white);
});
const drumMats = new Map();
export function drum() {
  const col = pick([0x2c5687, 0x2c5687, 0x325f8f, 0x27507d, 0x3b6896]);
  if (!drumGeo.g) drumGeo.g = merge(drumGeo());
  let m = drumMats.get(col); if (!m) drumMats.set(col, m = M(col, { roughness: 0.6 }));
  const g = inst([[drumGeo.g, m]]); g.children[0].rotation.y = Math.random() * 6; return g;
}
const tyreGeos = [0.012, 0.006].map(depth => once(() => {
  const pts = [[0.33, -0.11], [0.372, -0.105], [0.393, -0.09], [0.4, -0.06], [0.4, -0.02], [0.388, -0.014], [0.388, 0.014], [0.4, 0.02], [0.4, 0.06], [0.393, 0.09], [0.372, 0.105], [0.33, 0.11],
    [0.265, 0.1], [0.225, 0.078], [0.212, 0.0], [0.225, -0.078], [0.265, -0.1], [0.33, -0.11]].map(([x, y]) => new THREE.Vector2(x, y));
  const SEG = 16, g = new THREE.LatheGeometry(pts, SEG), P = g.attributes.position, np = pts.length;
  for (let i = 0; i <= SEG; i++) for (let j = 0; j < np; j++) {   // lateral tread grooves: alternate columns sink
    const [x, y] = [pts[j].x, pts[j].y]; if (x < 0.399 || ((i % SEG) % 2)) continue;
    const idx = i * np + j, s = 1 - depth / 0.4 * (Math.abs(y) > 0.04 ? 1 : 0.6); P.setX(idx, P.getX(idx) * s); P.setZ(idx, P.getZ(idx) * s);
  }
  const ng = g.toNonIndexed(); ng.computeVertexNormals();
  return merge([{ g: paint(ng, (v, c) => { const t = 0.9 + hsh(v.x, v.y, v.z) * 0.15, dust = v.y > 0.09 ? 1.6 : 1; c.setRGB(t * dust, t * dust * 0.97, t * dust * 0.92); }) }]);
}));
const tyreMat = M(0x1d1d1c, { roughness: 0.95 });
export function tyre() { const g = inst([[pick(tyreGeos)(), tyreMat]]); g.children[0].rotation.y = Math.random() * 6; return g; }

// ───────────────────────────── scenery
// Non-colliding scenery outside the pad (|x|>120 or |z|>150): trees, hills, fences, buildings far away.
function treeKinds() {
  // Low-poly but botanically shaped: irregular silhouettes, crown shading (darker underneath and inside), several variants.
  let seed = 0;
  const R = () => { seed += 1; return hsh(seed * 0.731, seed * 0.177, 3.3); };
  const clump = (r, sy, col, flat = 0) => { const sd = R() * 10;
    return paint(new THREE.IcosahedronGeometry(r, 1), (v, c) => {
      const n = hsh(v.x + sd, v.y, v.z), m = hsh(v.z, v.x + sd, v.y);
      const k = 0.72 + 0.5 * n; v.x *= k; v.z *= k; v.y *= sy * (0.8 + 0.4 * m); if (flat && v.y < 0) v.y *= 0.45;
      const t = v.y / (r * sy); const sh = t < 0 ? 0.55 + 0.3 * (1 + t) : 0.85 + 0.35 * t; const j = 0.9 + 0.2 * m;
      c.setRGB(col[0] * sh * j, col[1] * sh * j, col[2] * sh * (0.95 + 0.1 * n)); }); };
  const trunk = (k, pts, r0, r1, colFn) => { for (let i = 0; i < pts.length - 1; i++) { const a = pts[i], b = pts[i + 1], t0 = i / (pts.length - 1);
      const d = V3().subVectors(b, a), len = d.length(), q = new THREE.Quaternion().setFromUnitVectors(UP, d.normalize());
      const ra = r0 + (r1 - r0) * t0, rb = r0 + (r1 - r0) * (i + 1) / (pts.length - 1);
      const g = paint(new THREE.CylinderGeometry(rb, ra, len, 6, 3, true), (v, c) => colFn(v.y + len / 2 + a.y, c));
      k.add(MAT.white, g, (a.x + b.x) / 2, (a.y + b.y) / 2, (a.z + b.z) / 2, 0, 0, 0, null, q); } };
  const bark = (lo, hi, split) => (y, c) => { const t = Math.min(1, y / split); c.setRGB(lo[0] + (hi[0] - lo[0]) * t, lo[1] + (hi[1] - lo[1]) * t, lo[2] + (hi[2] - lo[2]) * t); };
  const branch = (k, a, b, w, col) => k.beam(MAT.white, a, b, w, w, col);

  // Norway spruce: dense, narrow, drooping tiers with ragged edges, dark blue-green
  const spruce = (H, tiers, wid) => { const k = new Kit();
    trunk(k, [V3(0, -0.2, 0), V3(0, 3.0, 0)], 0.3, 0.2, bark([0.24, 0.19, 0.15], [0.33, 0.25, 0.18], 3));
    for (let i = 0; i < tiers; i++) { const t = i / (tiers - 1), y0 = 1.0 + t * (H - 3.4), r = wid * Math.pow(1 - t, 0.9) + 0.3, h = 3.2 - 1.6 * t, sd = R() * 10;
      const g = paint(new THREE.ConeGeometry(r, h, 8, 1, true), (v, c) => { const rim = v.y < -h * 0.2; const rr = Math.hypot(v.x, v.z);
        if (rr > 0.01) { const j = 0.78 + 0.42 * hsh(v.x + sd, v.z, v.y); v.x *= j; v.z *= j; }
        if (rim) v.y -= r * 0.22 * (0.5 + hsh(v.z + sd, v.x, 1));                      // tips droop
        const sh = rim ? 0.95 + 0.25 * hsh(v.x, v.z + sd, 2) : 0.62 + 0.3 * (v.y / h + 0.5);
        c.setRGB(0.075 * sh, 0.14 * sh, 0.095 * sh); });
      k.add(MAT.white, g, 0, y0 + h / 2, 0, 0, R() * 6.3, 0); }
    k.add(MAT.white, paint(new THREE.ConeGeometry(0.28, 1.8, 5), (v, c) => c.setRGB(0.09, 0.16, 0.1)), 0, H + 0.1, 0);
    return merge(k.parts.get(MAT.white)); };

  // Scots pine: tall bare trunk, grey-brown below and orange above, slight bend, wide flat irregular crown on a few limbs
  const pine = (H, lean) => { const k = new Kit(); const lx = lean * (R() - 0.5), lz = lean * (R() - 0.5);
    const p1 = V3(lx * 0.3, H * 0.45, lz * 0.3), p2 = V3(lx * 0.8, H * 0.78, lz * 0.8), top = V3(lx, H, lz);
    trunk(k, [V3(0, -0.2, 0), p1, p2, top], 0.32, 0.1, bark([0.3, 0.26, 0.23], [0.62, 0.36, 0.2], H * 0.6));
    const n = 7; for (let i = 0; i < n; i++) { const a = i / n * 6.283 + R() * 0.9, hy = H * (0.72 + 0.24 * R()), spread = 0.7 + 1.3 * R();
      const base = V3().lerpVectors(p2, top, Math.max(0, (hy - p2.y) / (top.y - p2.y))); const end = V3(base.x + Math.cos(a) * spread, hy + 0.4 + R() * 0.6, base.z + Math.sin(a) * spread);
      branch(k, base, end, 0.11, 0x6a4a33);
      k.add(MAT.white, clump(1.5 + R() * 0.9, 0.62, [0.13, 0.2, 0.1]), end.x, end.y + 0.2, end.z, 0, R() * 6, 0); }
    k.add(MAT.white, clump(1.9, 0.7, [0.15, 0.22, 0.11]), top.x, top.y + 0.2, top.z);
    return merge(k.parts.get(MAT.white)); };

  // Silver birch: slender white trunk with black lenticels, upswept limbs, airy drooping crown in light yellow-green
  const birch = (H) => { const k = new Kit(); const lx = 0.9 * (R() - 0.5), lz = 0.9 * (R() - 0.5);
    const pts = [V3(0, -0.2, 0), V3(lx * 0.4, H * 0.4, lz * 0.4), V3(lx, H * 0.85, lz)];
    trunk(k, pts, 0.17, 0.06, (y, c) => { const dark = y < 0.8 ? 1 : hsh(Math.round(y * 2.5), 1, 7) > 0.62; const g = y < 0.8 ? 0.22 : dark ? 0.16 : 0.86; c.setRGB(g, g * 0.98, g * 0.94); });
    const n = 8; for (let i = 0; i < n; i++) { const a = i / n * 6.283 + R(), hy = H * (0.4 + 0.5 * i / n), reach = 0.7 + 1.2 * R() * (1 - i / n * 0.5);
      const base = V3(lx * hy / H, hy, lz * hy / H), end = V3(base.x + Math.cos(a) * reach, hy + 1.0 + R(), base.z + Math.sin(a) * reach);
      branch(k, base, end, 0.05, 0x8d877c);
      k.add(MAT.white, clump(1.15 + R() * 0.6, 1.3, [0.3, 0.38, 0.15]), end.x, end.y - 0.4, end.z, 0, R() * 6, 0); }
    k.add(MAT.white, clump(1.3, 1.35, [0.32, 0.4, 0.16]), lx, H, lz);
    return merge(k.parts.get(MAT.white)); };

  const bush = () => { const k = new Kit(); for (let i = 0; i < 4; i++) { const a = i * 1.7 + R(), d = i ? 0.5 + R() * 0.4 : 0, s = 0.65 + R() * 0.45;
      k.add(MAT.white, clump(s, 0.75, [0.2, 0.27, 0.14]), Math.cos(a) * d, s * 0.55, Math.sin(a) * d, 0, R() * 6, 0); }
    return merge(k.parts.get(MAT.white)); };
  return { spruceA: spruce(14, 10, 2.5), spruceB: spruce(17, 12, 2.2), pineA: pine(17, 1.6), pineB: pine(15, 2.4),
    birchA: birch(11), birchB: birch(13), bush: bush() };
}
function pylonGeo() {
  const k = new Kit(), m = MAT.white, B = 4, T = 0.8, H1 = 26, H2 = 33;
  const leg = (sx, sz, y) => { const t = y <= H1 ? y / H1 : 1, w = y <= H1 ? B + (T - B) * t : T - 0.2 * (y - H1) / (H2 - H1); return V3(sx * w, y, sz * w); };
  const lv = [0, 6, 12, 18, 23, 26, 33], cs = [[-1, -1], [1, -1], [1, 1], [-1, 1]];
  for (let i = 0; i < lv.length - 1; i++) for (let c = 0; c < 4; c++) { const [sx, sz] = cs[c], [tx, tz] = cs[(c + 1) % 4];
    k.beam(m, leg(sx, sz, lv[i]), leg(sx, sz, lv[i + 1]), 0.28);
    k.beam(m, leg(sx, sz, lv[i + 1]), leg(tx, tz, lv[i + 1]), 0.14);
    if (i < 4) { k.beam(m, leg(sx, sz, lv[i]), leg(tx, tz, lv[i + 1]), 0.1); k.beam(m, leg(tx, tz, lv[i]), leg(sx, sz, lv[i + 1]), 0.1); } }
  for (const [y, w] of [[23, 7], [28, 5]]) { k.beam(m, V3(0, y, -w), V3(0, y, w), 0.3); k.beam(m, V3(0, y + 1.2, -0.8), V3(0, y, -w), 0.15); k.beam(m, V3(0, y + 1.2, 0.8), V3(0, y, w), 0.15);
    for (const s of [-1, 1]) k.cyl(m, 0.12, 0.12, 2.2, 6, 0, y - 1.1, s * w, 0, 0, 0, 0x8d8a80); }
  k.beam(m, V3(0, 33, 0), V3(0, 36, 0), 0.2);
  return merge(k.parts.get(m));
}
export function scenery(scene) {
  const TF = globalThis.K7_TREE_FACTOR ?? 1;   // tree density (the phone build uses 1/15)
  const root = tag(new THREE.Group()); root.name = 'scenery'; scene.add(root);
  const mm = new THREE.Matrix4(), q = new THREE.Quaternion(), s = V3(), p = V3(), col = new THREE.Color();
  const excl = [[-215, 205, 42], [222, -215, 30], [210, 222, 34], [0, -250, 0]];
  const free = (x, z, m = 0) => (Math.abs(x) > 136 + m || Math.abs(z) > 166 + m) && x * x + z * z < 345 * 345 && Math.abs(z + 250) > 14 &&
    !excl.some(([ex, ez, er]) => er && (x - ex) ** 2 + (z - ez) ** 2 < er * er);
  const scatter = (geo, n, fn, colFn, near = 0) => {
    const im = new THREE.InstancedMesh(geo, MAT.white, n); let i = 0, guard = 0;
    while (i < n && guard++ < n * 60) {
      const x = rnd(-285, 285), z = rnd(-285, 285); if (!free(x, z, near) || x * x + z * z > 285 * 285 || (Math.abs(x) < 150 && Math.abs(z) < 180 && Math.random() < 0.6)) continue;
      const dens = 0.55 + 0.45 * Math.sin(x * 0.021 + 1.3) * Math.cos(z * 0.017 - 0.4); if (Math.random() > dens) continue;
      const k = fn(); p.set(x, -0.1, z); q.setFromAxisAngle(UP, rnd(0, 6.3)); s.set(k, k * rnd(0.85, 1.2), k);
      im.setMatrixAt(i, mm.compose(p, q, s)); im.setColorAt(i, colFn(col)); i++;
    }
    im.count = i; im.receiveShadow = true; root.add(im); return im;
  };
  const T = treeKinds(), green = c => c.setRGB(rnd(0.8, 1.15), rnd(0.85, 1.15), rnd(0.8, 1.1));
  const tint = c => { const k = rnd(0.85, 1.12); return c.setRGB(k * rnd(0.95, 1.05), k, k * rnd(0.92, 1.05)); };
  scatter(T.spruceA, Math.round(260 * TF), () => rnd(0.75, 1.25), tint);
  scatter(T.spruceB, Math.round(220 * TF), () => rnd(0.8, 1.3), tint);
  scatter(T.pineA, Math.round(120 * TF), () => rnd(0.85, 1.15), tint);
  scatter(T.pineB, Math.round(100 * TF), () => rnd(0.85, 1.15), tint);
  scatter(T.birchA, Math.round(80 * TF), () => rnd(0.85, 1.15), c => c.setRGB(rnd(0.9, 1.15), rnd(0.92, 1.12), rnd(0.8, 1.0)));
  scatter(T.birchB, Math.round(70 * TF), () => rnd(0.85, 1.15), c => c.setRGB(rnd(0.9, 1.15), rnd(0.92, 1.12), rnd(0.8, 1.0)));
  // mass forest: ~150k cheap instanced trees (≈20 triangles each) filling everything from the near belt out into the fog
  { const lowSpruce = (() => { const k = new Kit();
      k.add(MAT.white, paint(new THREE.CylinderGeometry(0.12, 0.2, 2, 3, 1, true), (v, c) => c.setRGB(0.25, 0.2, 0.15)), 0, 1, 0);
      for (const [y, r, h] of [[2.6, 2.4, 5], [6, 1.7, 4.2], [9.2, 1.0, 3.4]]) k.add(MAT.white, paint(new THREE.ConeGeometry(r, h, 6, 1, true), (v, c) => { const t = v.y / h + 0.5; c.setRGB(0.06 + 0.04 * t, 0.12 + 0.05 * t, 0.08 + 0.03 * t); }), 0, y, 0, 0, y, 0);
      return merge(k.parts.get(MAT.white)); })();
    const lowBroad = (top, trunkC, crownC) => { const k = new Kit();
      k.add(MAT.white, paint(new THREE.CylinderGeometry(0.1, 0.18, top, 3, 1, true), (v, c) => c.setRGB(...trunkC)), 0, top / 2, 0);
      for (const [x, y, z, r] of [[0, top + 0.6, 0, 2.2], [0.9, top - 0.6, 0.5, 1.6]]) k.add(MAT.white, paint(new THREE.OctahedronGeometry(r, 0), (v, c) => { const t = v.y > 0 ? 1.1 : 0.6; c.setRGB(crownC[0] * t, crownC[1] * t, crownC[2] * t); }), x, y, z, 0, x, 0);
      return merge(k.parts.get(MAT.white)); };
    const kinds = [[lowSpruce, 0.62], [lowBroad(10, [0.55, 0.33, 0.2], [0.13, 0.2, 0.1]), 0.24], [lowBroad(7, [0.8, 0.79, 0.75], [0.3, 0.38, 0.15]), 0.14]];
    const TOTAL = Math.round(150000 * TF), Rmax = 470;
    const inForest = (x, z) => { if (Math.abs(x) < 150 && Math.abs(z) < 180) return false; if (Math.abs(z + 250) < 16) return false;   // power-line cut
      if (excl.some(([ex, ez, er]) => er && (x - ex) ** 2 + (z - ez) ** 2 < er * er)) return false;
      const glade = Math.sin(x * 0.013 + 0.7) * Math.cos(z * 0.011 - 1.1) + 0.35 * Math.sin(x * 0.041 + z * 0.037);   // natural clearings
      return glade > -0.55; };
    for (const [geo, share] of kinds) { const n = Math.round(TOTAL * share), im = new THREE.InstancedMesh(geo, MAT.white, n); let i = 0, guard = 0;
      while (i < n && guard++ < n * 8) { const a = Math.random() * 6.2832, r = Math.sqrt(rnd(140 * 140, Rmax * Rmax)), x = Math.cos(a) * r, z = Math.sin(a) * r;
        if (!inForest(x, z)) continue; const k = rnd(0.7, 1.35);
        p.set(x, -0.15, z); q.setFromAxisAngle(UP, rnd(0, 6.3)); s.set(k, k * rnd(0.85, 1.25), k); im.setMatrixAt(i, mm.compose(p, q, s));
        const t = rnd(0.82, 1.15); im.setColorAt(i, col.setRGB(t * rnd(0.95, 1.05), t, t)); i++; }
      im.count = i; im.castShadow = false; im.receiveShadow = false; im.frustumCulled = false; root.add(im); } }
  // bushes: a belt along the fence plus scattered clumps
  { const n = Math.max(12, Math.round(180 * TF)), im = new THREE.InstancedMesh(T.bush, MAT.white, n);
    for (let i = 0; i < n; i++) { const side = i % 4, t = rnd(-1, 1); let x, z;
      if (side < 2) { x = (side ? 1 : -1) * rnd(131, 150); z = t * 170; } else { z = (side === 2 ? 1 : -1) * rnd(161, 180); x = t * 140; }
      if (!free(x, z)) { x *= 1.15; z *= 1.08; }
      p.set(x, 0, z); q.setFromAxisAngle(UP, rnd(0, 6.3)); const k = rnd(0.6, 1.5); s.set(k, k * rnd(0.7, 1.1), k);
      im.setMatrixAt(i, mm.compose(p, q, s)); im.setColorAt(i, green(col)); }
    root.add(im); }
  // hills on the horizon and gentle mounds closer in
  { const hm = M(0xffffff, { roughness: 1 });
    const hg = paint(new THREE.IcosahedronGeometry(1, 1), (v, c) => { const t = 0.85 + hsh(v.x * 5, v.y * 5, v.z * 5) * 0.25; c.setRGB(0.42 * t, 0.45 * t, 0.34 * t); });
    const n = 22, im = new THREE.InstancedMesh(hg, hm, n);
    for (let i = 0; i < n; i++) { const far = i < 16, a = (far ? i / 16 : (i - 16) / 6 + 0.04) * Math.PI * 2 + rnd(-0.1, 0.1), r = far ? rnd(310, 370) : rnd(215, 255), R = far ? rnd(45, 85) : rnd(25, 40);
      p.set(Math.cos(a) * r, far ? -6 : -3, Math.sin(a) * r); q.setFromAxisAngle(UP, rnd(0, 6)); s.set(R, R * (far ? rnd(0.18, 0.32) : rnd(0.1, 0.16)), R * rnd(0.8, 1.2));
      im.setMatrixAt(i, mm.compose(p, q, s)); im.setColorAt(i, col.setRGB(rnd(0.9, 1.1), rnd(0.9, 1.1), rnd(0.9, 1.05))); }
    root.add(im); }
  // perimeter chain-link fence with concrete posts and barbed wire outriggers
  { const FX = 128, FZ = 158, sides = [[V3(FX, 0, -FZ), V3(FX, 0, FZ), 0], [V3(-FX, 0, FZ), V3(-FX, 0, -FZ), Math.PI], [V3(FX, 0, FZ), V3(-FX, 0, FZ), -Math.PI / 2], [V3(-FX, 0, -FZ), V3(FX, 0, -FZ), Math.PI / 2]];
    const pk = new Kit();
    pk.add(MAT.white, paint(new THREE.BoxGeometry(0.16, 2.5, 0.16), (v, c) => { const t = v.y < -0.9 ? 0.75 : 0.95; c.setRGB(0.66 * t, 0.65 * t, 0.62 * t); }), 0, 1.2, 0);
    pk.box(MAT.white, 0.07, 0.55, 0.07, 0.17, 2.6, 0, 0, 0, -Math.PI / 4, 0x8a8c8c);
    const pg = merge(pk.parts.get(MAT.white)), posts = [];
    const lines = [], wire = new Kit(), meshTex = canvasTex(64, 64, (x, w, h) => { x.clearRect(0, 0, w, h); x.strokeStyle = 'rgba(150,156,156,1)'; x.lineWidth = 1.6;
      for (let i = -64; i <= 64; i += 16) { x.beginPath(); x.moveTo(i, 0); x.lineTo(i + 64, 64); x.stroke(); x.beginPath(); x.moveTo(i + 64, 0); x.lineTo(i, 64); x.stroke(); } }, true);
    for (const [a, b, ry] of sides) {
      const L = a.distanceTo(b), n = Math.round(L / 4), dir = b.clone().sub(a).normalize(), out = V3(Math.cos(ry), 0, -Math.sin(ry));
      for (let i = 0; i < n; i++) posts.push([a.clone().addScaledVector(dir, i * L / n), ry]);
      const t = meshTex.clone(); t.needsUpdate = true; t.repeat.set(L / 0.5, 4);
      const fm = new THREE.MeshStandardMaterial({ map: t, transparent: true, side: THREE.DoubleSide, depthWrite: false, metalness: 0.4, roughness: 0.6 });
      const pl = new THREE.Mesh(new THREE.PlaneGeometry(L, 2.0), fm); pl.position.copy(a).add(b).multiplyScalar(0.5); pl.position.y = 1.08; pl.rotation.y = ry + Math.PI / 2; root.add(pl);
      for (const y of [0.08, 2.08]) wire.beam(MAT.galv, V3(a.x, y, a.z), V3(b.x, y, b.z), 0.025, 0.025);
      for (let w = 0; w < 3; w++) { const o = 0.08 + w * 0.12; const A = a.clone().addScaledVector(out, o), B = b.clone().addScaledVector(out, o);
        lines.push(A.x, 2.5 + o, A.z, B.x, 2.5 + o, B.z); }
    }
    const im = new THREE.InstancedMesh(pg, MAT.white, posts.length);
    posts.forEach(([pp, ry], i) => im.setMatrixAt(i, mm.compose(pp, q.setFromAxisAngle(UP, ry), s.set(1, 1, 1)))); root.add(im);
    root.add(inst(wire.geoms(), false, false));
    const lg = new THREE.BufferGeometry(); lg.setAttribute('position', new THREE.Float32BufferAttribute(lines, 3));
    root.add(new THREE.LineSegments(lg, new THREE.LineBasicMaterial({ color: 0x55595a }))); }
  // power line in the distance
  { const pg = pylonGeo(), xs = [-350, -210, -70, 70, 210, 350], ZL = -250, im = new THREE.InstancedMesh(pg, M(0x8a8f90, { metalness: 0.5, roughness: 0.6 }), xs.length);
    xs.forEach((x, i) => im.setMatrixAt(i, mm.compose(p.set(x, 0, ZL + Math.sin(i) * 2), q.identity(), s.set(1, 1, 1)))); root.add(im);
    const L = [], att = [[21.9, -7], [21.9, 7], [26.9, -5], [26.9, 5], [36, 0]];
    for (let i = 0; i < xs.length - 1; i++) for (const [y, z] of att) { const sag = y > 30 ? 2.2 : 3.2, z0 = ZL + Math.sin(i) * 2 + z, z1 = ZL + Math.sin(i + 1) * 2 + z;
      for (let j = 0; j < 12; j++) { const t0 = j / 12, t1 = (j + 1) / 12, f = t => y - sag * 4 * t * (1 - t);
        L.push(xs[i] + (xs[i + 1] - xs[i]) * t0, f(t0), z0 + (z1 - z0) * t0, xs[i] + (xs[i + 1] - xs[i]) * t1, f(t1), z0 + (z1 - z0) * t1); } }
    const lg = new THREE.BufferGeometry(); lg.setAttribute('position', new THREE.Float32BufferAttribute(L, 3));
    root.add(new THREE.LineSegments(lg, new THREE.LineBasicMaterial({ color: 0x3c3f40 }))); }
  // a few far buildings: warehouse, boiler house with chimney, office block
  { const k = new Kit(), win = MAT.glass;
    const wh = (x, z, ry, w, h, d, wallC, roofC) => { const g = new THREE.Group(); g.position.set(x, 0, z); g.rotation.y = ry; g.updateMatrixWorld();
      const at = (lx, ly, lz) => V3(lx, ly, lz).applyMatrix4(g.matrixWorld), put = (mat, W, H, D, lx, ly, lz, c, rz = 0) => { const P = at(lx, ly, lz); k.box(mat, W, H, D, P.x, P.y, P.z, 0, ry, rz, c); };
      return { put, at }; };
    { const { put } = wh(-215, 205, 0.35, 48, 9, 24); put(MAT.white, 48, 9, 24, 0, 4.5, 0, 0xa7a59c);
      const a = Math.atan(4 / 12); for (const sd of [-1, 1]) put(MAT.white, 48.6, 0.3, 13.2, 0, 11, sd * 6, 0x6b4e42, 0);
      for (let i = 0; i < 4; i++) put(MAT.white, 5, 5, 0.1, -16 + i * 10.5, 2.5, 12.03, 0x50565a);
      for (let i = 0; i < 10; i++) put(win, 2.2, 0.9, 0.08, -20 + i * 4.5, 7.2, 12.03); }
    { const { put, at } = wh(222, -215, -0.4, 20, 12, 16); put(MAT.white, 20, 12, 16, 0, 6, 0, 0x8a6f5f); put(MAT.white, 20.4, 0.4, 16.4, 0, 12.2, 0, 0x55514c);
      for (let i = 0; i < 4; i++) put(win, 2, 3, 0.08, -6 + i * 4, 7, 8.03);
      const c = at(14, 0, 0); k.cyl(MAT.white, 1.1, 2.0, 42, 10, c.x, 21, c.z, 0, 0, 0, 0x9b968c); k.cyl(MAT.white, 1.2, 1.2, 1.2, 10, c.x, 38, c.z, 0, 0, 0, 0x5d5a55); }
    { const { put } = wh(210, 222, 0.2, 32, 11, 14); put(MAT.white, 32, 11, 14, 0, 5.5, 0, 0xc8c3b6); put(MAT.white, 32.4, 0.5, 14.4, 0, 11.2, 0, 0x707070);
      for (const y of [2, 5.5, 9]) { put(win, 30, 1.4, 0.08, 0, y, -7.03); put(win, 30, 1.4, 0.08, 0, y, 7.03); }
      put(MAT.white, 3, 1.5, 2, 6, 12.2, 2, 0x9a9c9c); }
    const parts = k.geoms(); root.add(inst(parts, false, true));
    // gable roof on the warehouse (two slabs)
    const r = new Kit(); const g = new THREE.Group(); g.position.set(-215, 0, 205); g.rotation.y = 0.35; g.updateMatrixWorld();
    for (const sd of [-1, 1]) { const sh = new THREE.BoxGeometry(48.6, 0.3, 13.4); sh.rotateX(sd * Math.atan(4 / 12)); sh.translate(0, 11, sd * 6.1); sh.applyMatrix4(g.matrixWorld); r.addM(MAT.white, sh, null, 0x6b4e42); }
    { const s2 = new THREE.Shape(); s2.moveTo(-12, 9); s2.lineTo(12, 9); s2.lineTo(0, 13); s2.lineTo(-12, 9); const eg = new THREE.ExtrudeGeometry(s2, { depth: 47.8, bevelEnabled: false });
      eg.rotateY(Math.PI / 2); eg.translate(-23.9, 0, 0); eg.applyMatrix4(g.matrixWorld); r.addM(MAT.white, eg, null, 0xa7a59c); }
    root.add(inst(r.geoms(), false, true)); }
  // flat details on the pad (≤ 1 cm, no colliders): storm drains, asphalt patches, oil stains, rubber marks
  { const flat = (map, opacity, rough = 0.85) => new THREE.MeshStandardMaterial({ map, transparent: true, opacity, depthWrite: false, roughness: rough, polygonOffset: true, polygonOffsetFactor: -3, polygonOffsetUnits: -3, vertexColors: true });
    const stainTex = canvasTex(128, 128, (x, w, h) => { x.clearRect(0, 0, w, h); for (let i = 0; i < 9; i++) { const cx = 64 + rnd(-22, 22), cy = 64 + rnd(-22, 22), r = rnd(14, 34);
      const g = x.createRadialGradient(cx, cy, 0, cx, cy, r); g.addColorStop(0, 'rgba(18,16,12,.32)'); g.addColorStop(0.7, 'rgba(18,16,12,.14)'); g.addColorStop(1, 'rgba(18,16,12,0)'); x.fillStyle = g; x.fillRect(0, 0, w, h); } });
    const grateTex = canvasTex(64, 128, (x, w, h) => { x.fillStyle = '#5d5b57'; x.fillRect(0, 0, w, h); x.fillStyle = '#2a2927'; x.fillRect(4, 4, w - 8, h - 8);
      x.fillStyle = '#4a4946'; for (let yy = 8; yy < h - 8; yy += 8) x.fillRect(6, yy, w - 12, 3); x.fillRect(w / 2 - 2, 6, 4, h - 12); });
    const skidTex = canvasTex(32, 128, (x, w, h) => { const g = x.createLinearGradient(0, 0, w, 0); g.addColorStop(0, 'rgba(15,15,14,0)'); g.addColorStop(0.5, 'rgba(15,15,14,.5)'); g.addColorStop(1, 'rgba(15,15,14,0)'); x.fillStyle = g; x.fillRect(0, 0, w, h); });
    const k = new Kit(), stainM = flat(stainTex, 0.9, 0.35), grateM = flat(grateTex, 1, 0.7), patchM = flat(null, 0.3, 0.9), skidM = flat(skidTex, 0.55);
    const quad = (mat, w, d, x, z, ry, y = 0.004) => k.add(mat, new THREE.PlaneGeometry(w, d), x, y, z, -Math.PI / 2, 0, 0, undefined, new THREE.Quaternion().setFromEuler(_e.set(-Math.PI / 2, 0, ry, 'YXZ')));
    for (let z = -70; z <= 50; z += 24) { quad(grateM, 0.5, 1.0, -29.5, z, 0, 0.006); quad(grateM, 0.5, 1.0, 31, z + 12, 0, 0.006); }
    for (const [x, z] of [[-75, -104.5], [-70, -104.5], [-80, -104.5]]) quad(grateM, 1.0, 0.5, x, z, 0, 0.006);
    const stains = [[0.4, 58.6, 0.9], [-1.4, 59.4, 0.6], [4.6, 59, 0.8], [-16, 56, 1.5], [18.5, 57, 1.6], [31, -2.8, 1.3], [-47.2, 45.2, 0.7], [-75, -103, 2.4], [-70, -101, 1.4],
      [58, -21, 1.8], [-58, -60, 1.6], [12, 20, 1.1], [-8, -30, 1.3], [40, 30, 1.4], [-30, -64, 1.5], [24, -50, 1.2]];
    for (const [x, z, r] of stains) quad(stainM, r * 1.3, r * 1.3 * rnd(0.7, 1.1), x, z, rnd(0, 6));
    for (let i = 0; i < 12; i++) { const x = rnd(-110, 110), z = rnd(-140, 140); if (x > -30 && x < 32 && z > -80 && z < 66) continue;
      const sh = new THREE.Shape(), W = rnd(0.8, 2.2), D = rnd(0.6, 1.6), j = () => rnd(-0.06, 0.06); sh.moveTo(-W + j(), -D + j()); sh.lineTo(W + j(), -D + j()); sh.lineTo(W + j(), D + j()); sh.lineTo(-W + j(), D + j());
      k.add(patchM, new THREE.ShapeGeometry(sh), x, 0.003, z, 0, 0, 0, 0x4a4a47, new THREE.Quaternion().setFromEuler(_e.set(-Math.PI / 2, 0, rnd(0, 6), 'YXZ'))); }
    for (const lx of [0, -16, 18]) for (const s of [-0.78, 0.78]) { quad(skidM, 0.3, 14, lx + s + rnd(-0.1, 0.1), 52, rnd(-0.02, 0.02), 0.005); }
    for (const [geo, mat] of k.geoms()) { const m = new THREE.Mesh(geo, mat); m.receiveShadow = true; m.renderOrder = 1; root.add(m); }
  }
}
