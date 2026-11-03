// Cabin interior, crash-test dummies, underbody (floor pan, sills, driveshaft, rear axle, exhaust, fuel tank).
// OWNER: interior/underbody agent. Interface: see SPEC.md §Car modules.
// Everything is built in ground heights inside `inner` (position.y = -CG). +z forward, +x = LEFT (driver side).
import { THREE, CG, ZF, ZR, gy, STD, PALETTE, clamp, canvasTex } from './common.js';

// ── shared, read-only resources (two cars share them; nothing here is mutated per car)
let SH = null;
function shared() {
  if (SH) return SH;
  // Hybrid III calibration target: black/white quadrants inside a black ring (no text)
  const target = canvasTex(64, 64, (g, w, h) => {
    g.fillStyle = '#d8a531'; g.fillRect(0, 0, w, h);
    g.fillStyle = '#111'; g.beginPath(); g.arc(32, 32, 31, 0, 7); g.fill();
    g.fillStyle = '#eee'; g.beginPath(); g.arc(32, 32, 26, 0, 7); g.fill();
    g.fillStyle = '#111';
    g.beginPath(); g.moveTo(32, 32); g.arc(32, 32, 26, 0, Math.PI / 2); g.fill();
    g.beginPath(); g.moveTo(32, 32); g.arc(32, 32, 26, Math.PI, Math.PI * 1.5); g.fill();
  });
  const M = {
    seat: STD(0x3a3d42, { roughness: 0.95 }),
    seatDark: STD(0x2a2b2d, { roughness: 0.95 }),
    trim: STD(0x2c2d2f, { roughness: 0.75 }),
    trimSoft: STD(0x3b3a38, { roughness: 0.85 }),
    gloss: STD(0x0c0d0e, { roughness: 0.25, metalness: 0.2 }),
    gauge: STD(0x8a9094, { roughness: 0.5, emissive: 0x1a1d1f }),
    needle: STD(0xc8532e, { roughness: 0.6 }),
    carpet: STD(0x2e2c29, { roughness: 1 }),
    alu: STD(PALETTE.alu, { metalness: 0.6, roughness: 0.4 }),
    steel: STD(PALETTE.steel, { metalness: 0.55, roughness: 0.5 }),
    dark: STD(PALETTE.darkSteel, { metalness: 0.35, roughness: 0.7 }),
    under: STD(0x2d2f2f, { metalness: 0.2, roughness: 0.9 }),
    cast: STD(PALETTE.castIron, { metalness: 0.45, roughness: 0.75 }),
    rubber: STD(PALETTE.rubber, { roughness: 0.95 }),
    exhaust: STD(0x5b5550, { metalness: 0.5, roughness: 0.7 }),
    rust: STD(PALETTE.rust, { metalness: 0.3, roughness: 0.85 }),
    tank: STD(0x262828, { metalness: 0.15, roughness: 0.8 }),
    dummy: STD(PALETTE.dummy, { roughness: 0.5 }),
    dumBlack: STD(0x151515, { roughness: 0.6 }),
    target: STD(0xffffff, { map: target, roughness: 0.6 }),
    belt: STD(0x2b2d31, { roughness: 0.9 }),
    buckle: STD(0x9a9ea2, { metalness: 0.7, roughness: 0.35 }),
    bag: STD(0xeeeeea, { roughness: 0.95, side: THREE.DoubleSide }),
    mirror: STD(0x9fb3b8, { metalness: 0.8, roughness: 0.15 }),
  };
  SH = { M, target };
  return SH;
}

const V = (x, y, z) => new THREE.Vector3(x, y, z);
const UP = V(0, 1, 0);
const hash = (x, y, z) => { const h = Math.sin(x * 127.1 + y * 311.7 + z * 74.7) * 43758.5453; return h - Math.floor(h); };

export function createInterior(ctx) {
  const { car, sys } = ctx; const { M } = shared();
  const inner = new THREE.Group(); inner.name = 'interior'; inner.position.y = -CG; ctx.group.add(inner);
  const geos = [];

  // ── helpers (all in ground-height coordinates of `inner`)
  const mesh = (g, mat, parent, shadow = false) => { geos.push(g); const m = new THREE.Mesh(g, mat); m.castShadow = shadow; m.receiveShadow = shadow; parent.add(m); return m; };
  const box = (w, h, d, x, y, z, mat, parent, rx = 0, ry = 0, rz = 0, shadow = false) => {
    const m = mesh(new THREE.BoxGeometry(w, h, d), mat, parent, shadow); m.position.set(x, y, z); m.rotation.set(rx, ry, rz); return m; };
  const cyl = (a, b, r0, r1, seg, mat, parent, sx = 1, sz = 1, shadow = false) => {
    const d = b.clone().sub(a), L = d.length(); const g = new THREE.CylinderGeometry(r1, r0, L, seg); if (sx !== 1 || sz !== 1) g.scale(sx, 1, sz);
    const m = mesh(g, mat, parent, shadow); m.position.copy(a).addScaledVector(d, 0.5); m.quaternion.setFromUnitVectors(UP, d.normalize()); return m; };
  const ball = (r, p, mat, parent, det = 0, s = null) => { const g = new THREE.IcosahedronGeometry(r, det); if (s) g.scale(s[0], s[1], s[2]); const m = mesh(g, mat, parent); m.position.copy(p); return m; };
  // side profile [z,h] extruded across x0..x1
  const prof = (pts, x0, x1, mat, parent, shadow = false) => {
    const s = new THREE.Shape(); pts.forEach(([z, h], i) => i ? s.lineTo(z, h) : s.moveTo(z, h));
    const g = new THREE.ExtrudeGeometry(s, { depth: x1 - x0, bevelEnabled: false, curveSegments: 1 }); g.rotateY(-Math.PI / 2); g.translate(x1, 0, 0);
    return mesh(g, mat, parent, shadow); };
  // cross-section [x,h] extruded along z0..z1
  const sect = (pts, z0, z1, mat, parent, shadow = false) => {
    const s = new THREE.Shape(); pts.forEach(([x, h], i) => i ? s.lineTo(x, h) : s.moveTo(x, h));
    const g = new THREE.ExtrudeGeometry(s, { depth: z1 - z0, bevelEnabled: false, curveSegments: 1 }); g.translate(0, 0, z0);
    return mesh(g, mat, parent, shadow); };
  // flat strap from a to b, thickness along n
  const strap = (a, b, w, t, n, mat, parent) => {
    const d = b.clone().sub(a), L = d.length(); const zA = d.clone().normalize();
    const yA = n.clone().addScaledVector(zA, -n.dot(zA)).normalize(), xA = new THREE.Vector3().crossVectors(yA, zA);
    const m = mesh(new THREE.BoxGeometry(w, t, L), mat, parent); m.position.copy(a).addScaledVector(d, 0.5);
    m.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(xA, yA, zA)); return m; };
  // re-express meshes made in `inner` coordinates inside a transformed child group
  const adopt = (grp, objs) => { grp.updateMatrix(); const inv = grp.matrix.clone().invert(); for (const o of objs) { o.applyMatrix4(inv); grp.add(o); } };
  const tmpG = () => new THREE.Group();

  // ════════════════════════════════ CABIN
  const cabin = new THREE.Group(); cabin.name = 'cabin'; inner.add(cabin);

  // carpet floor with toe board; front vertices bulge with intrusion
  const carpetG = new THREE.PlaneGeometry(1.58, 2.06, 8, 14); carpetG.rotateX(-Math.PI / 2); carpetG.translate(0, 0, -0.09);
  const cpos = carpetG.attributes.position; const carpetBase = new Float32Array(cpos.count);
  for (let i = 0; i < cpos.count; i++) { const z = cpos.getZ(i); const h = 0.24 + (z > 0.62 ? (z - 0.62) / 0.32 * 0.24 : 0); cpos.setY(i, h); carpetBase[i] = h; }
  carpetG.computeVertexNormals(); const carpet = mesh(carpetG, M.carpet, cabin); carpet.receiveShadow = true;
  // transmission tunnel (hollow inverted U, open below so the driveshaft shows from underneath)
  sect([[-0.17, 0.22], [-0.135, 0.22], [-0.10, 0.385], [0.10, 0.385], [0.135, 0.22], [0.17, 0.22], [0.12, 0.42], [-0.12, 0.42]], -0.95, 0.93, M.carpet, cabin);
  // rear kick-up and parcel shelf
  box(1.56, 0.26, 0.03, 0, 0.36, -1.0, M.carpet, cabin);
  box(1.4, 0.02, 0.36, 0, 0.98, -1.36, M.trim, cabin);

  // ── dashboard (moves back/up with intrusion)
  const dash = new THREE.Group(); dash.name = 'dash'; cabin.add(dash);
  prof([[0.95, 0.60], [0.95, 0.90], [0.90, 0.95], [0.64, 0.99], [0.54, 0.975], [0.50, 0.93], [0.49, 0.84], [0.53, 0.76], [0.57, 0.70], [0.58, 0.60]], -0.79, 0.79, M.trim, dash, true);
  // soft upper pad (slightly different tone)
  prof([[0.90, 0.951], [0.64, 0.992], [0.54, 0.977], [0.53, 0.985], [0.64, 1.0], [0.90, 0.96]], -0.78, 0.78, M.trimSoft, dash);
  // instrument binnacle over the cluster
  prof([[0.485, 1.035], [0.51, 1.06], [0.60, 1.065], [0.69, 0.995], [0.60, 0.99], [0.565, 1.04]], 0.19, 0.55, M.trim, dash);
  box(0.34, 0.075, 0.02, 0.37, 1.0, 0.575, M.gloss, dash, -0.15);
  for (const [x, r] of [[0.29, 0.034], [0.45, 0.034], [0.37, 0.022]]) {
    const c = mesh(new THREE.CircleGeometry(r, 12), M.gauge, dash); c.position.set(x, 1.0, 0.563); c.rotation.set(-0.15, Math.PI, 0);
    const n = box(0.004, r * 0.85, 0.003, x, 1.0, 0.561, M.needle, dash, -0.15, 0, x > 0.4 ? -0.9 : 0.7); n.translateY(r * 0.3);
  }
  // centre stack, screen, vents, glovebox seam
  prof([[0.505, 0.93], [0.52, 0.80], [0.56, 0.62], [0.62, 0.43], [0.88, 0.43], [0.88, 0.93]], -0.13, 0.13, M.trim, dash, true);
  box(0.24, 0.14, 0.015, 0, 1.06, 0.57, M.gloss, dash, -0.25);
  box(0.03, 0.06, 0.03, 0, 0.99, 0.58, M.trim, dash);
  for (const x of [-0.06, 0.06]) box(0.09, 0.04, 0.012, x, 0.885, 0.508, M.gloss, dash, -0.12);
  for (const x of [-0.64, 0.64]) box(0.12, 0.05, 0.012, x, 0.89, 0.493, M.gloss, dash, -0.1);
  box(0.016, 0.03, 0.10, 0, 0.75, 0.55, M.gloss, dash, -0.4); // climate knobs strip
  box(0.34, 0.006, 0.012, -0.40, 0.79, 0.528, M.gloss, dash, 0.5);
  box(0.006, 0.12, 0.012, -0.57, 0.75, 0.545, M.gloss, dash, 0.5);
  // passenger airbag door outline (bag emerges here)
  box(0.36, 0.004, 0.2, -0.40, 0.993, 0.70, M.trimSoft, dash, 0.12);

  // ── steering column + wheel (own group: rides back/up with intrusion)
  const WC = V(0.37, 0.93, 0.20), TILT = 0.44;
  const column = new THREE.Group(); column.name = 'steering'; column.position.copy(WC); column.rotation.x = TILT; cabin.add(column);
  // in column-local space: z runs forward-down along the column, wheel plane is local xy
  const rim = mesh(new THREE.TorusGeometry(0.185, 0.019, 6, 18), M.rubber, column, true);
  mesh(new THREE.CylinderGeometry(0.062, 0.07, 0.07, 10).rotateX(Math.PI / 2).translate(0, 0.0, 0.02), M.trimSoft, column);
  for (const a of [0, Math.PI, -Math.PI / 2]) {
    const s = box(0.13, 0.03, 0.018, Math.cos(a) * 0.115, Math.sin(a) * 0.115, 0.03, M.trim, column, 0, 0, a); s.scale.x = 1; }
  box(0.11, 0.09, 0.2, 0, -0.01, 0.17, M.trim, column, 0, 0, 0, true);      // shroud
  box(0.14, 0.012, 0.02, 0.09, 0.0, 0.12, M.trim, column, 0, 0, -0.2);       // stalks
  box(0.14, 0.012, 0.02, -0.09, 0.0, 0.12, M.trim, column, 0, 0, 0.2);
  cyl(V(0, -0.01, 0.26), V(0, -0.01, 0.64), 0.024, 0.024, 6, M.dark, column);
  void rim;

  // ── pedals (manual box: clutch, brake, throttle), hang from the pedal box under the dash
  const pedals = new THREE.Group(); pedals.name = 'pedals'; pedals.position.set(0, 0.66, 0.80); cabin.add(pedals);
  box(0.30, 0.08, 0.10, 0.40, 0.0, 0.02, M.dark, pedals);
  for (const [x, w] of [[0.51, 0.075], [0.39, 0.09], [0.27, 0.05]]) {
    cyl(V(x, 0.0, 0.0), V(x, -0.28, -0.12), 0.011, 0.011, 4, M.steel, pedals);
    box(w, 0.09, 0.016, x, -0.31, -0.13, M.rubber, pedals, -0.45);
  }

  // ── centre console, armrest, gear lever, handbrake
  sect([[-0.11, 0.41], [0.11, 0.41], [0.10, 0.50], [-0.10, 0.50]], -0.30, 0.48, M.trim, cabin);
  prof([[-0.32, 0.50], [0.0, 0.50], [0.0, 0.57], [-0.06, 0.59], [-0.32, 0.585]], -0.10, 0.10, M.seat, cabin);
  for (const z of [0.04, 0.11]) { const c = mesh(new THREE.CircleGeometry(0.03, 8), M.gloss, cabin); c.position.set(0, 0.502, z + 0.30); c.rotation.x = -Math.PI / 2; }
  cyl(V(0, 0.50, 0.24), V(0, 0.56, 0.235), 0.06, 0.03, 6, M.rubber, cabin);
  cyl(V(0, 0.55, 0.235), V(0, 0.66, 0.205), 0.012, 0.010, 5, M.alu, cabin);
  ball(0.028, V(0, 0.675, 0.20), M.gloss, cabin, 1, [1, 0.85, 1.15]);
  cyl(V(0.0, 0.50, 0.10), V(0.0, 0.56, -0.12), 0.022, 0.018, 5, M.trim, cabin);  // handbrake

  // ── rear view mirror and sun visors
  cyl(V(0, 1.335, 0.27), V(0, 1.27, 0.25), 0.012, 0.012, 5, M.trim, cabin);
  box(0.25, 0.065, 0.035, 0, 1.25, 0.245, M.trim, cabin, -0.15);
  box(0.23, 0.05, 0.004, 0, 1.25, 0.226, M.mirror, cabin, -0.15);
  for (const x of [0.38, -0.38]) box(0.34, 0.016, 0.16, x, 1.32, 0.22, M.trimSoft, cabin, 0.12);

  // ── seats
  function frontSeat(xc, parent) {
    const g = new THREE.Group(); g.name = 'seat'; parent.add(g);
    for (const s of [-1, 1]) { // slide rails and risers
      box(0.03, 0.025, 0.66, xc + s * 0.17, 0.255, -0.18, M.steel, g);
      box(0.035, 0.07, 0.05, xc + s * 0.17, 0.30, 0.08, M.dark, g); box(0.035, 0.07, 0.05, xc + s * 0.17, 0.30, -0.42, M.dark, g); }
    box(0.36, 0.05, 0.50, xc, 0.345, -0.18, M.dark, g);                           // pan
    prof([[-0.46, 0.37], [0.06, 0.37], [0.10, 0.41], [0.07, 0.455], [-0.15, 0.44], [-0.40, 0.415], [-0.46, 0.41]], xc - 0.17, xc + 0.17, M.seat, g, true);
    for (const s of [-1, 1]) prof([[-0.46, 0.37], [0.04, 0.37], [0.08, 0.43], [0.0, 0.50], [-0.30, 0.47], [-0.46, 0.44]], xc + (s > 0 ? 0.17 : -0.255), xc + (s > 0 ? 0.255 : -0.17), M.seatDark, g, true);
    // backrest in its own reclined frame (pivot at the hip, recline 0.30 rad)
    const b = new THREE.Group(); b.position.set(xc, 0.445, -0.335); b.rotation.x = -0.30; g.add(b);
    prof([[-0.13, -0.06], [0.0, -0.06], [0.03, 0.10], [0.05, 0.28], [0.02, 0.50], [0.0, 0.64], [-0.13, 0.66]], -0.17, 0.17, M.seat, b, true);
    for (const s of [-1, 1]) prof([[-0.13, -0.04], [0.06, -0.04], [0.09, 0.20], [0.06, 0.48], [0.0, 0.63], [-0.13, 0.64]], s > 0 ? 0.17 : -0.26, s > 0 ? 0.26 : -0.17, M.seatDark, b, true);
    for (const s of [-1, 1]) cyl(V(s * 0.07, 0.62, -0.05), V(s * 0.07, 0.70, -0.05), 0.007, 0.007, 4, M.alu, b);
    prof([[-0.10, 0.67], [0.0, 0.68], [0.025, 0.76], [0.01, 0.86], [-0.10, 0.85]], -0.13, 0.13, M.seat, b, true);
    box(0.06, 0.03, 0.04, xc + (xc > 0 ? -0.20 : 0.20), 0.42, -0.30, M.trim, g);  // recline lever / side trim
    return g;
  }
  const sideL = new THREE.Group(); sideL.name = 'driverSide'; cabin.add(sideL);
  const sideR = new THREE.Group(); sideR.name = 'passengerSide'; cabin.add(sideR);
  frontSeat(0.37, sideL); frontSeat(-0.37, sideR);
  // rear bench
  prof([[-1.04, 0.25], [-0.56, 0.25], [-0.53, 0.34], [-0.57, 0.45], [-0.95, 0.43], [-1.04, 0.42]], -0.74, 0.74, M.seat, cabin, true);
  {
    const b = new THREE.Group(); b.position.set(0, 0.42, -1.0); b.rotation.x = -0.40; cabin.add(b);
    prof([[-0.12, 0.0], [0.03, 0.0], [0.07, 0.20], [0.04, 0.50], [0.0, 0.58], [-0.12, 0.58]], -0.74, 0.74, M.seat, b, true);
    for (const x of [0.42, -0.42]) { prof([[-0.08, 0.58], [0.03, 0.58], [0.03, 0.70], [-0.08, 0.70]], x - 0.12, x + 0.12, M.seatDark, b); }
    prof([[-0.10, 0.20], [0.12, 0.20], [0.13, 0.30], [0.08, 0.48], [-0.10, 0.48]], -0.12, 0.12, M.seatDark, b); // fold-down armrest
  }

  // ════════════════════════════════ DUMMIES (Hybrid III 50th, scaled to the cabin)
  const OUT_DIR = x => (x > 0 ? 1 : -1);
  function dummy(xc, driver, parent) {
    const out = OUT_DIR(xc); const D = { xc, driver };
    const root = new THREE.Group(); root.name = driver ? 'dummyDriver' : 'dummyPassenger'; parent.add(root);
    const H = V(xc, 0.48, -0.22), R0 = 0.30;
    // pelvis + hips (static, belted to the seat)
    ball(0.15, V(xc, 0.48, -0.24), M.dummy, root, 1, [1.15, 0.6, 0.95]);
    for (const s of [-1, 1]) ball(0.055, V(xc + s * 0.10, 0.47, -0.18), M.dumBlack, root, 0);
    // legs
    const legs = driver ? [[0.12, 0.505, V(0.51, 0.30, 0.50)], [-0.10, 0.27, V(0.27, 0.30, 0.50)]]
                        : [[0.10, -0.27, null], [-0.10, -0.47, null]];
    for (const [dx, fx] of legs) {
      const hip = V(xc + dx * 0.95, 0.48, -0.17), knee = V(xc + dx * 1.15, 0.585, 0.20);
      const ank = driver ? V(fx, 0.33, 0.53) : V(fx, 0.31, 0.57);
      cyl(hip, knee, 0.078, 0.06, 7, M.dummy, root, 1, 1, true);
      ball(0.058, knee, M.dumBlack, root, 0);
      const kt = mesh(new THREE.CircleGeometry(0.035, 10), M.target, root); kt.position.copy(knee).add(V(out * 0.0, 0.035, 0.045)); kt.lookAt(kt.position.clone().add(V(0, 0.6, 1)));
      cyl(knee, ank, 0.052, 0.04, 6, M.dummy, root, 1, 1, true);
      const toe = driver ? ank.clone().add(V(0, 0.07, 0.20)) : ank.clone().add(V(0, -0.02, 0.21));
      const heel = ank.clone().add(V(0, -0.05, -0.03));
      strap(heel, toe, 0.09, 0.07, V(0, 1, driver ? -0.35 : 0), M.dumBlack, root);
    }
    // torso: pivot at the H-point, reclined like the seat back
    const torso = new THREE.Group(); torso.position.copy(H); torso.rotation.x = -R0; root.add(torso);
    cyl(V(0, 0.04, -0.01), V(0, 0.17, -0.01), 0.075, 0.07, 8, M.dumBlack, torso);                // lumbar spine
    const chestG = new THREE.CylinderGeometry(0.175, 0.15, 0.33, 9); chestG.scale(1, 1, 0.64); chestG.translate(0, 0.33, 0); mesh(chestG, M.dummy, torso, true);
    box(0.13, 0.25, 0.012, 0, 0.33, 0.106, M.dumBlack, torso);                                     // sternum / jacket zip
    box(0.43, 0.075, 0.13, 0, 0.475, -0.005, M.dummy, torso, 0, 0, 0, true);                      // shoulder yoke
    for (const s of [-1, 1]) { ball(0.05, V(s * 0.215, 0.47, 0), M.dumBlack, torso, 0);
      const t = mesh(new THREE.CircleGeometry(0.035, 10), M.target, torso); t.position.set(s * 0.177, 0.33, 0); t.rotation.y = s * Math.PI / 2; }
    for (let i = 0; i < 4; i++) cyl(V(0, 0.51 + i * 0.03, 0.005), V(0, 0.535 + i * 0.03, 0.005), i % 2 ? 0.043 : 0.05, i % 2 ? 0.043 : 0.05, 7, M.dumBlack, torso); // neck discs
    // head on the occipital pivot
    const head = new THREE.Group(); head.position.set(0, 0.625, 0.005); head.rotation.x = R0 - 0.04; torso.add(head);
    const hg = new THREE.SphereGeometry(0.1, 10, 8); hg.scale(0.78, 1.08, 1.0); hg.translate(0, 0.105, 0.02); mesh(hg, M.dummy, head, true);
    box(0.032, 0.045, 0.03, 0, 0.10, 0.12, M.dummy, head, 0.25);                                   // nose
    box(0.08, 0.02, 0.04, 0, 0.045, 0.095, M.dummy, head);                                         // chin
    for (const s of [-1, 1]) { const t = mesh(new THREE.CircleGeometry(0.04, 12), M.target, head); t.position.set(s * 0.079, 0.11, 0.015); t.rotation.y = s * Math.PI / 2; }
    const tt = mesh(new THREE.CircleGeometry(0.035, 12), M.target, head); tt.position.set(0, 0.214, 0.02); tt.rotation.x = -Math.PI / 2;
    box(0.06, 0.03, 0.06, 0, 0.0, -0.02, M.dumBlack, head);                                        // head/neck bracket
    // arms: modelled at rest in inner space, then adopted into the torso frame
    torso.updateMatrix(); const tm = torso.matrix; const armObjs = [];
    const tmp = tmpG();
    for (const s of [-1, 1]) {
      const S = V(s * 0.235, 0.465, 0).applyMatrix4(tm);
      let Hn; if (driver) { const hl = V(s * 0.172, 0.05, -0.012); hl.applyEuler(new THREE.Euler(TILT, 0, 0)).add(WC); Hn = hl; }
      else Hn = V(xc + s * 0.11, 0.62, 0.06);
      const l1 = 0.30, l2 = 0.27; const d = Hn.clone().sub(S); let L = d.length(); const dir = d.clone().normalize();
      if (L > l1 + l2 - 0.01) { L = l1 + l2 - 0.01; Hn = S.clone().addScaledVector(dir, L); }
      const a = (l1 * l1 - l2 * l2 + L * L) / (2 * L), hh = Math.sqrt(Math.max(0, l1 * l1 - a * a));
      const pole = V(s * 0.8, -1, driver ? -0.2 : -0.6); pole.addScaledVector(dir, -pole.dot(dir)).normalize();
      const E = S.clone().addScaledVector(dir, a).addScaledVector(pole, hh);
      armObjs.push(cyl(S, E, 0.05, 0.043, 7, M.dummy, tmp, 1, 1, true), ball(0.042, E, M.dumBlack, tmp, 0),
        cyl(E, Hn, 0.04, 0.032, 6, M.dummy, tmp, 1, 1, true), ball(0.038, Hn, M.dumBlack, tmp, 0, [0.9, 1.3, 0.8]));
    }
    // seat belt: B-pillar anchor → shoulder → across the chest → inner hip buckle, plus lap belt
    const anchor = V(xc + out * 0.385, 1.12, -0.52);
    const sh = V(out * 0.11, 0.50, 0.075), mid = V(out * 0.01, 0.33, 0.118), hipIn = V(-out * 0.155, 0.08, 0.095);
    const beltObjs = [strap(sh, mid, 0.05, 0.006, V(0, 0, 1), M.belt, tmp), strap(mid, hipIn, 0.05, 0.006, V(0, 0.2, 1), M.belt, tmp)];
    for (const o of beltObjs) { tmp.remove(o); o.applyMatrix4(tm); }
    armObjs.push(...beltObjs);
    for (const o of armObjs) tmp.remove(o);
    adopt(torso, armObjs);
    const shW = sh.clone().applyMatrix4(tm);
    strap(anchor, shW, 0.05, 0.006, V(-out, 0, 0.3), M.belt, root);
    box(0.05, 0.08, 0.025, anchor.x, anchor.y, anchor.z, M.trim, root);                          // D-ring
    const bIn = V(xc - out * 0.21, 0.47, -0.22), bOut = V(xc + out * 0.215, 0.46, -0.24), lap = V(xc, 0.535, -0.10);
    strap(bOut, lap, 0.05, 0.006, V(0, 1, 0.6), M.belt, root); strap(lap, bIn, 0.05, 0.006, V(0, 1, 0.6), M.belt, root);
    box(0.03, 0.06, 0.045, bIn.x, bIn.y, bIn.z, M.buckle, root, -0.3);
    cyl(V(bIn.x, 0.30, -0.27), V(bIn.x, 0.45, -0.23), 0.012, 0.012, 4, M.trim, root);
    Object.assign(D, { root, torso, head, R0, th: 0, thv: 0, ro: 0, rov: 0, hn: 0, hnv: 0, hr: 0, hrv: 0, thMax: 0.62 });
    return D;
  }
  const dummies = [dummy(0.37, true, sideL), dummy(-0.37, false, sideR)];

  // ── airbags (hidden until a frontal hit above 7 m/s)
  function bagGeo(sx, sy, sz) {
    const g = new THREE.IcosahedronGeometry(1, 1); const p = g.attributes.position;
    for (let i = 0; i < p.count; i++) { const x = p.getX(i), y = p.getY(i), z = p.getZ(i); const k = 0.9 + 0.2 * hash(x * 3, y * 3, z * 3); p.setXYZ(i, x * sx * k, y * sy * k, z * sz * k); }
    g.computeVertexNormals(); return g; }
  const bagD = mesh(bagGeo(0.27, 0.27, 0.13), M.bag, column); bagD.position.set(0, 0.0, -0.10); bagD.visible = false;
  const bagP = mesh(bagGeo(0.27, 0.21, 0.22), M.bag, dash); bagP.position.set(-0.40, 0.99, 0.34); bagP.rotation.x = -0.35; bagP.visible = false;
  const bags = { t: -1, puffed: false };

  // ════════════════════════════════ UNDERBODY
  const under = new THREE.Group(); under.name = 'underbody'; inner.add(under);
  // floor pan: two halves beside the tunnel, rear centre section, kick-up over the axle, trunk floor
  for (const s of [-1, 1]) box(0.58, 0.02, 1.80, s * 0.455, 0.205, 0.0, M.under, under, 0, 0, 0, true);
  box(0.36, 0.02, 0.22, 0.0, 0.205, -1.02, M.under, under);
  box(1.44, 0.02, 0.86, 0, 0.47, -1.52, M.under, under);                    // over-axle / trunk floor
  box(1.44, 0.26, 0.02, 0, 0.34, -1.09, M.under, under);                    // kick-up
  box(1.30, 0.02, 0.26, 0, 0.255, -1.94, M.under, under);                   // spare well floor
  // floor stiffening rails and cross member
  for (const s of [-1, 1]) box(0.06, 0.045, 1.70, s * 0.50, 0.175, -0.02, M.dark, under);
  box(1.0, 0.04, 0.07, 0, 0.18, -0.36, M.dark, under);
  // sills (pinch-welded rocker panels)
  for (const s of [-1, 1]) { sect([[s * 0.745, 0.20], [s * 0.86, 0.20], [s * 0.865, 0.31], [s * 0.75, 0.30]], -0.82, 0.86, M.dark, under, true);
    box(0.012, 0.04, 1.66, s * 0.80, 0.18, 0.02, M.dark, under); }

  // driveshaft: gearbox output (z 0.80) → centre bearing → pinion (z −1.12)
  const DS0 = V(0, 0.28, 0.80), DSm = V(0, 0.29, -0.20), DS1 = V(0, 0.31, -1.10);
  cyl(DS0, DSm, 0.032, 0.032, 8, M.steel, under, 1, 1, true); cyl(DSm, DS1, 0.034, 0.034, 8, M.steel, under, 1, 1, true);
  for (const p of [DS0, DSm, DS1]) { box(0.07, 0.07, 0.05, p.x, p.y, p.z, M.cast, under); }
  box(0.16, 0.05, 0.05, 0, 0.27, -0.24, M.rubber, under);                    // centre bearing bracket
  // rear axle: diff housing, pinion nose, rear cover, axle tubes
  ball(0.12, V(0, 0.33, -1.27), M.cast, under, 1, [1.0, 0.95, 0.85]).castShadow = true;
  cyl(V(0, 0.32, -1.16), V(0, 0.31, -1.07), 0.06, 0.045, 8, M.cast, under);
  mesh(new THREE.CylinderGeometry(0.105, 0.105, 0.03, 10).rotateX(Math.PI / 2).translate(0, 0.33, -1.37), M.dark, under);
  cyl(V(-0.62, 0.33, -1.28), V(0.62, 0.33, -1.28), 0.042, 0.042, 8, M.cast, under, 1, 1, true);
  for (const s of [-1, 1]) { cyl(V(s * 0.10, 0.33, -1.28), V(s * 0.30, 0.33, -1.28), 0.06, 0.045, 8, M.cast, under); box(0.03, 0.1, 0.12, s * 0.58, 0.33, -1.28, M.dark, under); }

  // fuel tank under the rear seat (left of the tunnel), straps, filler neck
  const tankG = new THREE.Group(); tankG.name = 'fuelTank'; under.add(tankG);
  const tank = sect([[0.07, 0.11], [0.09, 0.08], [0.58, 0.08], [0.63, 0.12], [0.63, 0.20], [0.60, 0.215], [0.10, 0.215], [0.07, 0.19]], -0.80, -0.40, M.tank, tankG, true);
  for (const z of [-0.50, -0.70]) box(0.60, 0.008, 0.035, 0.35, 0.076, z, M.steel, tankG);
  cyl(V(0.55, 0.20, -0.78), V(0.60, 0.40, -0.92), 0.022, 0.022, 6, M.rubber, tankG);
  cyl(V(0.12, 0.17, -0.42), V(0.05, 0.21, 0.20), 0.006, 0.006, 4, M.steel, tankG);   // fuel line along the tunnel
  const tankHole = ball(0.035, V(0.40, 0.078, -0.60), M.gloss, tankG, 0, [1.4, 0.3, 1]); tankHole.visible = false;

  // exhaust (right of the tunnel): front pipe with cat (stays), resonator → muffler → tailpipe (can tear off)
  const exF = new THREE.Group(); exF.name = 'exhaustFront'; exF.position.set(0, 0, 0.30); under.add(exF);
  const exR = new THREE.Group(); exR.name = 'exhaustRear'; under.add(exR);
  {
    const f = [], o = V(0, 0, 0.30); const tf = tmpG();
    f.push(cyl(V(-0.17, 0.21, 1.00), V(-0.19, 0.15, 0.86), 0.027, 0.027, 7, M.exhaust, tf));
    f.push(ball(0.032, V(-0.19, 0.15, 0.86), M.exhaust, tf, 0));
    f.push(cyl(V(-0.19, 0.15, 0.86), V(-0.20, 0.135, 0.76), 0.027, 0.06, 7, M.exhaust, tf));
    f.push(cyl(V(-0.20, 0.135, 0.76), V(-0.20, 0.135, 0.46), 0.06, 0.06, 8, M.exhaust, tf, 1.45, 1, true)); // catalytic converter
    f.push(cyl(V(-0.20, 0.135, 0.46), V(-0.21, 0.13, 0.38), 0.06, 0.027, 7, M.exhaust, tf));
    f.push(cyl(V(-0.21, 0.13, 0.38), V(-0.215, 0.13, 0.28), 0.027, 0.027, 7, M.exhaust, tf));
    f.push(box(0.32, 0.006, 0.52, -0.20, 0.205, 0.61, M.alu, tf));        // heat shield over the cat
    for (const m of f) { tf.remove(m); m.position.sub(o); exF.add(m); }
    const r = [];
    r.push(cyl(V(-0.215, 0.13, 0.30), V(-0.22, 0.13, -0.08), 0.027, 0.027, 7, M.exhaust, exR));
    r.push(cyl(V(-0.22, 0.13, -0.08), V(-0.22, 0.13, -0.46), 0.058, 0.058, 8, M.exhaust, exR, 1.3, 1, true)); // resonator
    r.push(cyl(V(-0.22, 0.13, -0.46), V(-0.18, 0.13, -1.05), 0.027, 0.027, 7, M.exhaust, exR));
    r.push(cyl(V(-0.18, 0.13, -1.05), V(-0.12, 0.16, -1.72), 0.027, 0.027, 7, M.exhaust, exR));
    r.push(cyl(V(-0.02, 0.165, -1.86), V(-0.62, 0.165, -1.86), 0.085, 0.085, 10, M.exhaust, exR, 1, 1.35, true)); // muffler
    r.push(box(0.64, 0.006, 0.3, -0.32, 0.258, -1.86, M.alu, exR));                                      // its heat shield
    r.push(cyl(V(-0.12, 0.16, -1.72), V(-0.12, 0.165, -1.79), 0.03, 0.03, 6, M.exhaust, exR));
    r.push(cyl(V(-0.55, 0.15, -1.95), V(-0.50, 0.185, -2.10), 0.027, 0.027, 7, M.exhaust, exR));
    r.push(cyl(V(-0.50, 0.185, -2.10), V(-0.49, 0.19, -2.17), 0.035, 0.035, 8, M.alu, exR));             // tip
    for (const [x, z] of [[-0.22, -0.60], [-0.40, -1.86]]) r.push(cyl(V(x, 0.16, z), V(x, 0.21, z), 0.012, 0.012, 4, M.rubber, exR)); // hangers
  }

  // ════════════════════════════════ shadows & flags
  inner.traverse(o => { if (o.isMesh && o.castShadow) o.receiveShadow = true; });

  // ════════════════════════════════ DAMAGE STATE
  sys.leaks = sys.leaks || [];
  let intr = 0, sideLs = 0, sideRs = 0, scrapeAcc = 0, fuelLeak = null;
  const p0 = { dash: dash.position.clone(), col: column.position.clone(), colRx: column.rotation.x, ped: pedals.position.clone() };

  function tearExhaust(ev) {
    if (sys.exhaustLoose) return; sys.exhaustLoose = true;
    // rebuild the rear section around its own centre and hand it to physics
    under.remove(exR); exR.position.set(0, 0, 0); exR.updateMatrixWorld(true);
    const bb = new THREE.Box3().setFromObject(exR), c = new THREE.Vector3(), sz = new THREE.Vector3(); bb.getCenter(c); bb.getSize(sz);
    for (const ch of exR.children) ch.position.sub(c);
    inner.updateMatrixWorld(true); const wc = inner.localToWorld(c.clone()); const q = new THREE.Quaternion(); ctx.group.getWorldQuaternion(q);
    exR.position.copy(wc); exR.quaternion.copy(q);
    const { CANNON } = ctx; const b = new CANNON.Body({ mass: 14, material: ctx.mProp, linearDamping: 0.1, angularDamping: 0.2 });
    b.addShape(new CANNON.Box(new CANNON.Vec3(Math.max(0.05, sz.x / 2), Math.max(0.04, sz.y / 2), Math.max(0.05, sz.z / 2))));
    b.position.set(wc.x, wc.y - 0.02, wc.z); b.quaternion.set(q.x, q.y, q.z, q.w);
    const v = car.body.velocity; b.velocity.set(v.x * 0.8, v.y - 0.5, v.z * 0.8); b.angularVelocity.set((Math.random() - 0.5) * 3, (Math.random() - 0.5) * 2, (Math.random() - 0.5) * 3);
    ctx.addDebris(exR, b); ctx.sound && ctx.sound.clunk && ctx.sound.clunk(0.5);
    if (ctx.fx && ctx.fx.spark) { const w = inner.localToWorld(V(-0.2, 0.13, 0.28)); for (let i = 0; i < 6; i++) ctx.fx.spark(w.clone(), { x: v.x * 0.5 + (Math.random() - 0.5) * 3, y: Math.random() * 2, z: v.z * 0.5 + (Math.random() - 0.5) * 3 }); }
    void ev;
  }
  function breakTank(rate) {
    if (!sys.fuelTankBroken) { sys.fuelTankBroken = true; tankHole.visible = true; tank.scale.y = 0.85; tank.position.y = 0.025;
      fuelLeak = { kind: 'fuel', at: V(0.40, gy(0.07), -0.60), rate }; sys.leaks.push(fuelLeak); }
    else if (fuelLeak) fuelLeak.rate = Math.max(fuelLeak.rate, rate);
  }

  function kick(D, ev, a) {
    const dTh = -ev.nL.z * a, dRo = -ev.nL.x * a;
    if (Math.abs(dTh) > 0.05 && (Math.sign(dTh) !== Math.sign(D.thv) || Math.abs(dTh) > Math.abs(D.thv))) D.thv = dTh;
    if (Math.abs(dRo) > 0.05 && (Math.sign(dRo) !== Math.sign(D.rov) || Math.abs(dRo) > Math.abs(D.rov))) D.rov = dRo;
    const dHn = dTh * 0.7; if (Math.abs(dHn) > 0.05 && (Math.sign(dHn) !== Math.sign(D.hnv) || Math.abs(dHn) > Math.abs(D.hnv))) D.hnv = dHn;
    const dHr = dRo * 0.7; if (Math.abs(dHr) > 0.05 && (Math.sign(dHr) !== Math.sign(D.hrv) || Math.abs(dHr) > Math.abs(D.hrv))) D.hrv = dHr;
    if (ev.nL.y < -0.4 || ev.nL.y > 0.4) D.hnv += (Math.random() - 0.5) * a * 0.5;
  }
  function stepDummy(D, dt) {
    const w = 7.5, z = 0.32, wh = 11, zh = 0.28; const lim = bags.t >= 0 ? 0.44 : D.thMax;
    const acc = -w * w * D.th - 2 * z * w * D.thv; D.thv += acc * dt; D.th += D.thv * dt;
    if (D.th > lim) { D.th = lim; if (D.thv > 0) D.thv *= -0.35; }
    if (D.th < -0.10) { D.th = -0.10; if (D.thv < 0) D.thv *= -0.3; }
    const accR = -w * w * D.ro - 2 * z * w * D.rov; D.rov += accR * dt; D.ro += D.rov * dt;
    const rl = 0.42; if (Math.abs(D.ro) > rl) { D.ro = Math.sign(D.ro) * rl; D.rov *= -0.3; }
    // head lags the chest: driven by the torso's angular acceleration
    const ah = -wh * wh * D.hn - 2 * zh * wh * D.hnv - acc * 0.9; D.hnv += ah * dt; D.hn += D.hnv * dt;
    const hl = bags.t >= 0 ? 0.35 : 0.75; if (D.hn > hl) { D.hn = hl; D.hnv *= -0.3; } if (D.hn < -0.6) { D.hn = -0.6; D.hnv *= -0.3; }
    const ar = -wh * wh * D.hr - 2 * zh * wh * D.hrv - accR * 0.9; D.hrv += ar * dt; D.hr += D.hrv * dt; D.hr = clamp(D.hr, -0.6, 0.6);
  }

  return {
    root: inner,
    onImpact(ev) {
      const low = ev.pL.y < gy(0.32);
      // underbody: scraping belly or a hit from below
      if (ev.scrape) { if (low && ev.nL.y > 0.3) scrapeAcc += 1; }
      else if (!ev.roof && low && ev.nL.y > 0.45) scrapeAcc += ev.v * 1.2;
      if (scrapeAcc > 6 && !sys.exhaustLoose) tearExhaust(ev);
      if (scrapeAcc > 18) breakTank(0.5);
      if (ev.scrape) return;
      if (ev.v < 1.2) return;
      // occupants: thrown along −nL, stopped by belts
      const a = clamp(ev.v * 0.32, 0, 6.5);
      for (const D of dummies) kick(D, ev, a);
      // airbags on a hard frontal
      if (ev.frontal && ev.v > 7 && bags.t < 0) {
        bags.t = 0; bagD.visible = true; bagP.visible = true; bagD.scale.setScalar(0.05); bagP.scale.setScalar(0.05);
      }
    },
    update(dt) {
      dt = Math.min(dt, 0.05);
      // ── intrusion: dash, column and pedals pushed back/up, footwell floor bulges
      const want = clamp(0.6 * car.cabinIntr + 0.45 * Math.max(0, car.frontCrush - 0.5), 0, 0.30);
      if (want > intr) intr += Math.min(want - intr, dt * 3);
      dash.position.set(p0.dash.x, p0.dash.y + intr * 0.22, p0.dash.z - intr * 0.75);
      column.position.set(p0.col.x - intr * 0.05, p0.col.y + intr * 0.35, p0.col.z - intr * 0.85); column.rotation.x = p0.colRx - intr * 0.9;
      pedals.position.set(p0.ped.x, p0.ped.y + intr * 0.35, p0.ped.z - intr * 1.1); pedals.rotation.x = -intr * 1.4;
      if (intr > 0.001 && Math.abs(intr - (carpet.userData.k || 0)) > 0.004) {
        carpet.userData.k = intr;
        for (let i = 0; i < cpos.count; i++) { const x = cpos.getX(i), z = cpos.getZ(i); const f = clamp((z - 0.15) / 0.6, 0, 1) * Math.exp(-Math.pow((Math.abs(x) - 0.38) / 0.28, 2));
          cpos.setY(i, carpetBase[i] + intr * 0.55 * f * f * (0.8 + 0.4 * hash(x, z, 1))); }
        cpos.needsUpdate = true; carpetG.computeVertexNormals();
      }
      // side intrusion pushes the near seat + dummy inboard
      const sl = clamp((car.zone.L - 0.10) * 0.8, 0, 0.24), sr = clamp((car.zone.Rt - 0.10) * 0.8, 0, 0.24);
      sideLs += (sl - sideLs) * Math.min(1, dt * 8); sideRs += (sr - sideRs) * Math.min(1, dt * 8);
      sideL.position.x = -sideLs; sideR.position.x = sideRs;
      // exhaust front pipe squashed by a deep frontal crush; rear crush tears the back box and the tank
      const fp = Math.max(0, 1.02 - (ZF - car.frontCrush)); exF.scale.z = clamp((0.70 - fp) / 0.70, 0.3, 1);
      if (car.rearCrush > 0.4) { tearExhaust(null); breakTank(clamp(0.4 + car.rearCrush * 0.4, 0, 1)); }
      if (!sys.exhaustLoose) { const rp = Math.max(0, (ZR + car.rearCrush) - (-2.18)); exR.position.z = Math.min(rp, 0.3); }
      // ── dummies
      const n = Math.max(1, Math.ceil(dt / 0.004)), h = dt / n;
      for (const D of dummies) { for (let i = 0; i < n; i++) stepDummy(D, h);
        D.torso.rotation.set(-D.R0 + D.th, 0, -D.ro); D.head.rotation.set(D.R0 - 0.04 + D.hn - D.th * 0.3, 0, -D.hr * 0.8); }
      // ── airbags: inflate in ~40 ms, then vent slowly
      if (bags.t >= 0) {
        bags.t += dt; const t = bags.t;
        const s = t < 0.04 ? 0.05 + 0.95 * (t / 0.04) : t < 0.25 ? 1.0 + 0.06 * Math.sin((t - 0.04) * 30) * Math.exp(-(t - 0.04) * 12) : Math.max(0.62, 1 - (t - 0.25) * 0.35);
        bagD.scale.set(s, s, s * (0.7 + 0.3 * s)); bagP.scale.set(s, s, s);
        bagD.position.z = -0.10 * s; bagP.position.z = 0.50 - 0.16 * s;
        if (!bags.puffed && t > 0.03 && ctx.fx && ctx.fx.puff) { bags.puffed = true;
          for (const m of [bagD, bagP]) { const w = new THREE.Vector3(); m.getWorldPosition(w);
            for (let i = 0; i < 3; i++) ctx.fx.puff(w.clone(), { x: (Math.random() - 0.5) * 0.6, y: 0.3 + Math.random() * 0.4, z: (Math.random() - 0.5) * 0.6 }, { life: 2.5, s0: 0.2, s1: 1.2, a: 0.14, c: 0.95 }); } }
      }
    },
    dispose() {
      inner.parent && inner.parent.remove(inner);
      for (const g of geos) if (!(sys.exhaustLoose && exR.children.some(c => c.geometry === g))) g.dispose();
    },
  };
}
