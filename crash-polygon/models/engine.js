// Engine bay: engine block, gearbox, radiator, battery, intake, exhaust manifold, hoses, firewall, rails.
// OWNER: engine agent. Interface: see SPEC.md §Car modules.
//
// Layout (ground heights, chassis x/z; +x = LEFT): longitudinal inline-4 sitting behind the front axle line,
// bell housing at the firewall (z 0.97), gearbox into the tunnel to z 0.80. Intake on the left, exhaust on the right,
// radiator pack + support frame + bumper beam at the nose, rails at x ±0.37 under the bay, subframe at z 1.36.
//
// Damage: the crushed nose profile is sampled from the body panels (per x bin) or taken from car.frontCrush; a
// 1-D stack-up then pushes bumper beam -> radiator pack -> fan/engine back, folds the rails like an accordion and
// bulges the firewall. sys.engineShift / sys.radiatorBroken / sys.leaks are written here.
import { THREE, CG, STD, PALETTE, canvasTex } from './common.js';

// ── shared materials (both cars use the same ones) ──
let M = null;
function mats() {
  if (M) return M;
  const fin = canvasTex(32, 32, (g, w, h) => {
    g.fillStyle = '#2b2d2c'; g.fillRect(0, 0, w, h);
    g.fillStyle = '#4a4d4b'; for (let y = 0; y < h; y += 3) g.fillRect(0, y, w, 1);
    g.fillStyle = '#1a1b1a'; for (let x = 0; x < w; x += 8) g.fillRect(x, 0, 2, h);
  }, true);
  fin.repeat.set(10, 5);
  const fin2 = fin.clone(); fin2.needsUpdate = true; fin2.repeat.set(12, 4);
  M = {
    iron: STD(PALETTE.castIron, { metalness: 0.45, roughness: 0.7 }),
    alu: STD(PALETTE.alu, { metalness: 0.6, roughness: 0.45 }),
    aluDark: STD(0x8a8d8e, { metalness: 0.55, roughness: 0.5 }),
    cover: STD(0x5e2b26, { metalness: 0.35, roughness: 0.5 }),
    steel: STD(PALETTE.steel, { metalness: 0.6, roughness: 0.5 }),
    dark: STD(PALETTE.darkSteel, { metalness: 0.5, roughness: 0.6 }),
    body: STD(0x60666a, { metalness: 0.35, roughness: 0.6 }),         // painted body structure (rails, support)
    exhaust: STD(0x5d4b3e, { metalness: 0.55, roughness: 0.75 }),
    plastic: STD(PALETTE.plasticBlack, { roughness: 0.85 }),
    rubber: STD(PALETTE.rubber, { roughness: 0.95 }),
    hose: STD(PALETTE.hoseBlack, { roughness: 0.9 }),
    felt: STD(0x34322d, { roughness: 1.0 }),
    core: STD(0xffffff, { map: fin, metalness: 0.5, roughness: 0.6 }),
    cond: STD(0xbfbfbf, { map: fin2, metalness: 0.5, roughness: 0.6 }),
    tank: STD(0xc9c5b6, { roughness: 0.55 }),
    washer: STD(0x6f8791, { roughness: 0.55 }),
    batt: STD(0x2a2c2d, { roughness: 0.7 }),
    battTop: STD(0x3a3c3d, { roughness: 0.7 }),
    plus: STD(0x7a2c24, { roughness: 0.6 }),
    copper: STD(0x8a6a45, { metalness: 0.7, roughness: 0.4 }),
    yellow: STD(PALETTE.hazard, { roughness: 0.6 }),
    fluid: STD(0xb8ae84, { roughness: 0.5 }),
  };
  return M;
}

const hash = (a, b, c) => { const h = Math.sin(a * 127.1 + b * 311.7 + c * 74.7) * 43758.5453; return h - Math.floor(h); };
const cl = (x, a, b) => (x < a ? a : x > b ? b : x);

export function createEngineBay(ctx) {
  const { car, CANNON } = ctx;
  const m = mats();
  const root = new THREE.Group(); root.name = 'engineBay'; root.position.y = -CG; ctx.group.add(root);   // ground heights inside

  // ───────────── helpers ─────────────
  const shadow = (o, cast = true) => { o.castShadow = cast; o.receiveShadow = true; return o; };
  const add = (parent, geo, mat, cast = true) => { const o = shadow(new THREE.Mesh(geo, mat), cast); parent.add(o); return o; };
  // box with its geometry baked at a position (for vertex-deformed parts) or placed by mesh.position
  function boxG(w, h, d, x, y, z, sx = 1, sy = 1, sz = 1) { const g = new THREE.BoxGeometry(w, h, d, sx, sy, sz); g.translate(x, y, z); return g; }
  function box(parent, w, h, d, x, y, z, mat, cast = true) { const o = add(parent, new THREE.BoxGeometry(w, h, d), mat, cast); o.position.set(x, y, z); return o; }
  // cylinder along an axis ('x','y','z'); rTop sits at +axis
  function cylG(rTop, rBot, len, seg, axis, open = false) {
    const g = new THREE.CylinderGeometry(rTop, rBot, len, seg, 1, open);
    if (axis === 'z') g.rotateX(Math.PI / 2); else if (axis === 'x') g.rotateZ(-Math.PI / 2);
    return g;
  }
  function cyl(parent, rTop, rBot, len, seg, axis, x, y, z, mat, cast = true) { const o = add(parent, cylG(rTop, rBot, len, seg, axis), mat, cast); o.position.set(x, y, z); return o; }
  // profile (x,y) extruded along z from z0 to z1
  function extr(parent, pts, z0, z1, mat, cast = true) {
    const s = new THREE.Shape(pts.map(p => new THREE.Vector2(p[0], p[1])));
    const g = new THREE.ExtrudeGeometry(s, { depth: z1 - z0, bevelEnabled: false }); g.translate(0, 0, z0);
    return add(parent, g, mat, cast);
  }
  const tubeG = (pts, r, seg = 10, rad = 6) => new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts.map(p => p.isVector3 ? p : new THREE.Vector3(...p))), seg, r, rad, false);
  const V = (x, y, z) => new THREE.Vector3(x, y, z);

  // merge static meshes of a rigid group by material (fewer draw calls); `skip` objects (and their children) stay separate
  function mergeStatic(group, skip) {
    group.updateMatrixWorld(true);
    const inv = group.matrixWorld.clone().invert(), byMat = new Map();
    group.traverse(o => { if (!o.isMesh) return; for (let p = o; p && p !== group; p = p.parent) if (skip.has(p)) return;
      if (!byMat.has(o.material)) byMat.set(o.material, []); byMat.get(o.material).push(o); });
    const mt = new THREE.Matrix4();
    for (const [mat, list] of byMat) {
      if (list.length < 2) continue;
      const parts = list.map(o => { const g = o.geometry.index ? o.geometry.toNonIndexed() : o.geometry.clone(); g.applyMatrix4(mt.multiplyMatrices(inv, o.matrixWorld)); return g; });
      let n = 0; for (const g of parts) n += g.attributes.position.count;
      const P = new Float32Array(n * 3), N = new Float32Array(n * 3), U = new Float32Array(n * 2); let k = 0;
      for (const g of parts) { const c = g.attributes.position.count; P.set(g.attributes.position.array, k * 3); if (g.attributes.normal) N.set(g.attributes.normal.array, k * 3); if (g.attributes.uv) U.set(g.attributes.uv.array, k * 2); k += c; g.dispose(); }
      const G = new THREE.BufferGeometry(); G.setAttribute('position', new THREE.BufferAttribute(P, 3)); G.setAttribute('normal', new THREE.BufferAttribute(N, 3)); G.setAttribute('uv', new THREE.BufferAttribute(U, 2));
      const cast = list.some(o => o.castShadow);
      for (const o of list) { o.parent.remove(o); o.geometry.dispose(); }
      add(group, G, mat, cast);
    }
  }
  // ───────────── ENGINE (moves as one: pivot at the gearbox tail) ─────────────
  const PIV = V(0, 0.45, 0.80);
  const engPivot = new THREE.Group(); engPivot.position.copy(PIV); root.add(engPivot);
  const eng = new THREE.Group(); eng.position.set(-PIV.x, -PIV.y, -PIV.z); engPivot.add(eng);
  const CYL = [1.165, 1.28, 1.395, 1.51];

  // block, oil pan, head, valve cover
  extr(eng, [[-0.13, 0.36], [0.13, 0.36], [0.165, 0.47], [0.155, 0.62], [-0.155, 0.62], [-0.165, 0.47]], 1.08, 1.60, m.iron);
  for (const zc of [1.22, 1.34, 1.46]) {        // cast ribs / water-jacket bosses on both sides
    box(eng, 0.345, 0.07, 0.025, 0, 0.52, zc, m.iron, false);
  }
  extr(eng, [[-0.13, 0.36], [-0.12, 0.31], [-0.10, 0.272], [0.10, 0.272], [0.12, 0.31], [0.13, 0.36]], 1.085, 1.585, m.dark);
  box(eng, 0.29, 0.012, 0.51, 0, 0.362, 1.335, m.dark, false);               // pan flange
  extr(eng, [[-0.155, 0.62], [0.155, 0.62], [0.145, 0.715], [-0.145, 0.715]], 1.09, 1.59, m.alu);
  extr(eng, [[-0.13, 0.715], [0.13, 0.715], [0.13, 0.745], [0.10, 0.785], [-0.10, 0.785], [-0.13, 0.745]], 1.11, 1.57, m.cover);
  for (const zc of CYL) box(eng, 0.05, 0.03, 0.055, 0.035, 0.80, zc, m.plastic, false);     // coil packs
  box(eng, 0.02, 0.016, 0.40, 0.075, 0.795, 1.34, m.plastic, false);                      // coil harness
  cyl(eng, 0.026, 0.026, 0.022, 10, 'y', -0.06, 0.795, 1.50, m.plastic, false);           // oil filler cap
  // timing cover + front pulleys (belt plane z 1.655…1.68)
  extr(eng, [[-0.13, 0.33], [0.13, 0.33], [0.15, 0.50], [0.14, 0.72], [-0.14, 0.72], [-0.15, 0.50]], 1.60, 1.645, m.aluDark);
  const spin = [];   // {o, k} rotate around z at k × crank speed
  const crank = cyl(eng, 0.075, 0.075, 0.036, 14, 'z', 0, 0.42, 1.667, m.dark); spin.push({ o: crank, k: 1 });
  box(crank, 0.10, 0.012, 0.038, 0, 0, 0, m.steel, false);                                 // balancer spokes (show rotation)
  const wpp = cyl(eng, 0.055, 0.055, 0.026, 12, 'z', 0, 0.58, 1.668, m.steel); spin.push({ o: wpp, k: 1.25 });
  cyl(eng, 0.05, 0.05, 0.13, 10, 'z', 0, 0.58, 1.745, m.alu);                               // fan clutch / shaft
  const ALT = V(-0.235, 0.60, 1.60);
  cyl(eng, 0.065, 0.065, 0.10, 12, 'z', ALT.x, ALT.y, ALT.z, m.aluDark);                    // alternator body
  cyl(eng, 0.05, 0.05, 0.012, 12, 'z', ALT.x, ALT.y, 1.548, m.dark, false);                 // rear cap
  box(eng, 0.10, 0.022, 0.03, -0.17, 0.555, 1.60, m.alu, false);                            // bracket to block
  const altp = cyl(eng, 0.032, 0.032, 0.026, 8, 'z', ALT.x, ALT.y, 1.668, m.steel); spin.push({ o: altp, k: 2.6 });
  const idl = cyl(eng, 0.026, 0.026, 0.026, 8, 'z', 0.085, 0.475, 1.668, m.steel); spin.push({ o: idl, k: 2.9 });
  {   // serpentine belt: hull of the pulleys, extruded along z
    const pul = [[0, 0.42, 0.075], [0, 0.58, 0.055], [ALT.x, ALT.y, 0.032], [0.085, 0.475, 0.026]];
    const hull = (dr) => {
      const P = []; for (const [x, y, r] of pul) for (let k = 0; k < 20; k++) { const a = k / 20 * Math.PI * 2; P.push([x + Math.cos(a) * (r + dr), y + Math.sin(a) * (r + dr)]); }
      P.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
      const cr = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
      const lo = [], up = [];
      for (const p of P) { while (lo.length >= 2 && cr(lo[lo.length - 2], lo[lo.length - 1], p) <= 0) lo.pop(); lo.push(p); }
      for (let i = P.length - 1; i >= 0; i--) { const p = P[i]; while (up.length >= 2 && cr(up[up.length - 2], up[up.length - 1], p) <= 0) up.pop(); up.push(p); }
      up.pop(); lo.pop(); return lo.concat(up).map(p => new THREE.Vector2(p[0], p[1]));
    };
    const sh = new THREE.Shape(hull(0.007)); sh.holes.push(new THREE.Path(hull(0).reverse()));
    const g = new THREE.ExtrudeGeometry(sh, { depth: 0.022, bevelEnabled: false, curveSegments: 1 }); g.translate(0, 0, 1.657);
    add(eng, g, m.rubber, false);
  }
  cyl(eng, 0.026, 0.026, 0.04, 8, 'z', 0.04, 0.70, 1.655, m.aluDark, false);                // thermostat housing
  // oil filter, starter, dipstick
  { const f = cyl(eng, 0.042, 0.042, 0.10, 12, 'x', 0.215, 0.43, 1.36, m.yellow, false); f.rotation.z = -0.35; }
  cyl(eng, 0.042, 0.042, 0.15, 10, 'z', -0.175, 0.39, 1.06, m.dark);                        // starter
  add(eng, tubeG([[0.15, 0.46, 1.47], [0.16, 0.62, 1.50], [0.145, 0.78, 1.52]], 0.005, 4, 4), m.steel, false);
  cyl(eng, 0.018, 0.018, 0.012, 8, 'x', 0.145, 0.79, 1.52, m.yellow, false);               // dipstick handle
  // bell housing + gearbox (tunnel from z 0.95 on)
  cyl(eng, 0.19, 0.145, 0.12, 14, 'z', 0, 0.445, 1.03, m.alu);
  cyl(eng, 0.13, 0.095, 0.17, 10, 'z', 0, 0.43, 0.885, m.alu);
  box(eng, 0.14, 0.05, 0.14, 0, 0.345, 0.89, m.aluDark, false);                              // gearbox oil pan
  // engine mounts (rubber + brackets) – the subframe towers carry them
  for (const s of [1, -1]) {
    box(eng, 0.07, 0.07, 0.09, s * 0.19, 0.43, 1.36, m.aluDark, false);
    cyl(eng, 0.035, 0.035, 0.05, 8, 'y', s * 0.21, 0.37, 1.36, m.rubber, false);
  }
  // intake (left, +x): 4 runners into a plenum, throttle body
  for (const zc of CYL) add(eng, tubeG([[0.15, 0.67, zc], [0.205, 0.715, zc], [0.255, 0.70, zc + 0.01], [0.285, 0.655, zc + 0.02]], 0.022, 6, 5), m.alu);
  cyl(eng, 0.052, 0.052, 0.46, 10, 'z', 0.29, 0.645, 1.34, m.alu);
  cyl(eng, 0.038, 0.038, 0.05, 10, 'z', 0.29, 0.645, 1.595, m.aluDark, false);              // throttle body
  // exhaust (right, −x): 4 runners -> collector -> down-pipe to the underbody at z ≈ 1.0
  for (const zc of CYL) add(eng, tubeG([[-0.15, 0.665, zc], [-0.205, 0.645, zc], [-0.245, 0.565, (zc + 1.30) / 2], [-0.25, 0.50, 1.30]], 0.019, 6, 5), m.exhaust);
  cyl(eng, 0.042, 0.042, 0.11, 10, 'y', -0.25, 0.47, 1.30, m.exhaust);
  add(eng, tubeG([[-0.25, 0.43, 1.30], [-0.25, 0.37, 1.20], [-0.22, 0.29, 1.08], [-0.20, 0.235, 0.985]], 0.028, 8, 6), m.exhaust);
  { const hs = box(eng, 0.11, 0.008, 0.44, -0.215, 0.705, 1.34, m.steel, false); hs.rotation.z = 0.55; }   // heat shield
  // fan on the water-pump shaft
  const fan = new THREE.Group(); fan.position.set(0, 0.58, 1.848); eng.add(fan); spin.push({ o: fan, k: 1.25, fan: true });
  add(fan, cylG(0.045, 0.045, 0.03, 10, 'z'), m.plastic, false);
  for (let k = 0; k < 7; k++) {
    const piv = new THREE.Group(); piv.rotation.z = k / 7 * Math.PI * 2; fan.add(piv);
    const b = add(piv, new THREE.BoxGeometry(0.052, 0.13, 0.006), m.plastic, false); b.position.y = 0.11; b.rotation.y = 0.45;
  }

  // ───────────── FRONT STRUCTURE (vertex-deformed) ─────────────
  // layer: 'beam' (bumper beam, crash cans) or 'pack' (radiator, condenser, shroud, support frame)
  const deform = [];
  function defMesh(geo, mat, layer, cast = true) {
    const o = add(root, geo, mat, cast); o.frustumCulled = false;
    const pos = geo.attributes.position; deform.push({ o, layer, orig: Float32Array.from(pos.array) }); return o;
  }
  // bumper beam with swept ends, crash cans
  { const g = boxG(1.24, 0.11, 0.05, 0, 0.40, 2.045, 10, 1, 1); const p = g.attributes.position;
    for (let i = 0; i < p.count; i++) { const x = p.getX(i) / 0.62; p.setZ(i, p.getZ(i) - 0.05 * x * x * x * x); }
    defMesh(g, m.body, 'beam'); }
  for (const s of [1, -1]) defMesh(boxG(0.08, 0.09, 0.04, s * 0.37, 0.37, 2.0, 1, 1, 1), m.dark, 'beam', false);
  // radiator core, side tanks, necks, condenser, shroud
  defMesh(boxG(0.66, 0.34, 0.035, 0, 0.54, 1.9425, 6, 3, 1), m.core, 'pack');
  for (const s of [1, -1]) defMesh(boxG(0.06, 0.38, 0.055, s * 0.36, 0.54, 1.9425, 1, 2, 1), m.plastic, 'pack');
  { const g = cylG(0.02, 0.02, 0.05, 8, 'y'); g.translate(-0.36, 0.745, 1.94); defMesh(g, m.plastic, 'pack', false); }   // inlet neck (right top)
  { const g = cylG(0.03, 0.03, 0.02, 8, 'y'); g.translate(-0.36, 0.765, 1.94); defMesh(g, m.dark, 'pack', false); }     // pressure cap
  { const g = cylG(0.02, 0.02, 0.05, 8, 'z'); g.translate(0.36, 0.38, 1.905); defMesh(g, m.plastic, 'pack', false); }   // outlet neck (left bottom)
  defMesh(boxG(0.70, 0.32, 0.014, 0, 0.545, 1.99, 6, 2, 1), m.cond, 'pack');
  {
    const sh = new THREE.Shape([[-0.25, 0.36], [0.25, 0.36], [0.25, 0.785], [-0.25, 0.785]].map(p => new THREE.Vector2(...p)));
    const hole = new THREE.Path(); hole.absarc(0, 0.58, 0.19, 0, Math.PI * 2, true); sh.holes.push(hole);
    const g = new THREE.ExtrudeGeometry(sh, { depth: 0.012, bevelEnabled: false, curveSegments: 14 }); g.translate(0, 0, 1.898);
    defMesh(g, m.plastic, 'pack');
    const r = new THREE.CylinderGeometry(0.192, 0.192, 0.045, 18, 1, true); r.rotateX(Math.PI / 2); r.translate(0, 0.58, 1.878);
    defMesh(r, m.plastic, 'pack');
  }
  // radiator support: upper/lower crossmembers, pillars (stand on the rails), headlamp brackets, hood latch
  { const g = boxG(1.20, 0.04, 0.06, 0, 0.73, 1.975, 8, 1, 1), p = g.attributes.position;           // upper crossmember follows the hood line
    for (let i = 0; i < p.count; i++) { const x = p.getX(i) / 0.6; p.setY(i, p.getY(i) - 0.04 * x * x); }
    defMesh(g, m.body, 'pack'); }
  defMesh(boxG(0.67, 0.04, 0.06, 0, 0.33, 1.97, 4, 1, 1), m.body, 'pack');
  for (const s of [1, -1]) {
    defMesh(boxG(0.04, 0.33, 0.05, s * 0.40, 0.565, 1.975, 1, 3, 1), m.body, 'pack');
    defMesh(boxG(0.20, 0.15, 0.012, s * 0.52, 0.625, 1.975, 2, 1, 1), m.body, 'pack', false);
  }
  defMesh(boxG(0.06, 0.05, 0.03, 0, 0.70, 2.005), m.dark, 'pack', false);

  // ───────────── RAILS, SUBFRAME (vertex-deformed / pushed) ─────────────
  const rails = [];
  for (const s of [1, -1]) {
    const g = boxG(0.07, 0.10, 1.05, s * 0.37, 0.35, 1.495, 1, 1, 18); const p = g.attributes.position;
    for (let i = 0; i < p.count; i++) { const z = p.getZ(i); if (z < 1.12) p.setY(i, p.getY(i) - (1.12 - z) * 0.55); }   // kick-down under the floor
    const o = add(root, g, m.body); o.frustumCulled = false; rails.push({ o, s, orig: Float32Array.from(p.array) });
  }
  const sub = new THREE.Group(); root.add(sub);
  box(sub, 0.70, 0.05, 0.10, 0, 0.245, 1.36, m.dark);
  for (const s of [1, -1]) {
    box(sub, 0.06, 0.08, 0.08, s * 0.21, 0.305, 1.36, m.dark, false);                        // mount towers
    const br = box(sub, 0.05, 0.04, 0.30, s * 0.30, 0.27, 1.22, m.dark, false); br.rotation.y = s * 0.45;   // diagonal braces to the rails
  }

  // ───────────── FIREWALL, cowl, insulation ─────────────
  const fw = [];
  function fwMesh(geo, mat) { const o = add(root, geo, mat); o.frustumCulled = false; fw.push({ o, orig: Float32Array.from(geo.attributes.position.array) }); return o; }
  fwMesh(boxG(1.40, 0.30, 0.02, 0, 0.75, 0.955, 8, 2, 1), m.body);
  fwMesh(boxG(1.10, 0.34, 0.02, 0, 0.41, 0.955, 8, 3, 1), m.body);
  fwMesh(boxG(1.22, 0.27, 0.02, 0, 0.735, 0.975, 8, 2, 1), m.felt);
  for (const s of [1, -1]) fwMesh(boxG(0.30, 0.28, 0.02, s * 0.37, 0.43, 0.975, 2, 2, 1), m.felt);
  fwMesh(boxG(1.24, 0.05, 0.09, 0, 0.86, 1.02, 6, 1, 1), m.plastic);                       // cowl / plenum panel
  // brake booster + master cylinder (driver side, left)
  const booster = new THREE.Group(); booster.position.set(0.39, 0.70, 1.02); root.add(booster);
  add(booster, cylG(0.105, 0.105, 0.09, 14, 'z'), m.dark);
  add(booster, (() => { const g = cylG(0.028, 0.028, 0.13, 8, 'z'); g.translate(0, 0, 0.11); return g; })(), m.alu, false);
  box(booster, 0.07, 0.05, 0.06, 0, 0.05, 0.11, m.fluid, false);
  // heater hoses through the firewall (right side)
  // (built with the other hoses below)

  // ───────────── LOOSE ITEMS (pushed back by the crush, can break off) ─────────────
  // each: group with origin at its centre; zf/zr/x0/x1 = original extents
  const items = [];
  function item(name, x, y, z, w, h, d) { const g = new THREE.Group(); g.name = name; g.position.set(x, y, z); root.add(g);
    const it = { name, g, p0: g.position.clone(), zf: z + d / 2, zr: z - d / 2, x0: x - w / 2, x1: x + w / 2, half: [w / 2, h / 2, d / 2], gone: false }; items.push(it); return it; }
  // battery (right rear) on a tray with a leg to the rail
  const bat = item('battery', -0.385, 0.69, 1.15, 0.175, 0.20, 0.26);
  box(bat.g, 0.175, 0.17, 0.26, 0, -0.005, 0, m.batt);
  box(bat.g, 0.165, 0.012, 0.25, 0, 0.085, 0, m.battTop, false);
  cyl(bat.g, 0.011, 0.013, 0.02, 8, 'y', 0.045, 0.10, 0.09, m.plus, false);
  cyl(bat.g, 0.011, 0.013, 0.02, 8, 'y', -0.045, 0.10, 0.09, m.plastic, false);
  box(bat.g, 0.19, 0.012, 0.012, 0, 0.088, -0.02, m.dark, false);                             // hold-down clamp
  const tray = new THREE.Group(); root.add(tray);
  box(tray, 0.20, 0.02, 0.28, -0.385, 0.585, 1.15, m.dark, false);
  box(tray, 0.035, 0.19, 0.035, -0.37, 0.48, 1.15, m.dark, false);
  // coolant expansion tank (right, mid)
  const exp = item('expTank', -0.375, 0.69, 1.40, 0.14, 0.15, 0.18);
  box(exp.g, 0.14, 0.13, 0.18, 0, -0.01, 0, m.tank);
  box(exp.g, 0.142, 0.05, 0.182, 0, -0.045, 0, STD(PALETTE.coolant, { roughness: 0.4, transparent: true, opacity: 0.55 }), false);
  cyl(exp.g, 0.024, 0.024, 0.025, 10, 'y', 0.03, 0.065, 0.04, m.plastic, false);
  // windscreen washer bottle (front left, ahead of the wheel arch)
  const wash = item('washer', 0.58, 0.48, 1.86, 0.15, 0.24, 0.10);
  box(wash.g, 0.15, 0.24, 0.10, 0, 0, 0, m.washer);
  cyl(wash.g, 0.018, 0.018, 0.07, 8, 'y', -0.03, 0.15, 0.02, m.washer, false);
  cyl(wash.g, 0.026, 0.026, 0.02, 8, 'y', -0.03, 0.19, 0.02, m.plastic, false);
  // air filter box (front left) with its snorkel
  const air = item('airbox', 0.33, 0.68, 1.78, 0.26, 0.16, 0.20);
  box(air.g, 0.26, 0.09, 0.20, 0, -0.035, 0, m.plastic);
  box(air.g, 0.27, 0.012, 0.21, 0, 0.012, 0, m.plastic, false);
  { const lid = box(air.g, 0.25, 0.06, 0.19, 0, 0.045, 0, m.plastic); lid.scale.set(1, 1, 1); }
  box(air.g, 0.05, 0.05, 0.08, 0.12, 0.01, 0.12, m.plastic, false);

  // ───────────── HOSES / CABLES (rebuilt when the bay deforms) ─────────────
  // point spaces: 'e' engine, 'r' radiator pack (left/right tank), 'f' fixed body, or an item
  const hoses = [];
  function hose(pts, r, mat, seg = 10, rad = 6) { const o = add(root, new THREE.BufferGeometry(), mat, false); o.frustumCulled = false; const h = { o, pts, r, seg, rad }; hoses.push(h); return h; }
  hose([['e', 0.04, 0.70, 1.675], ['e', -0.05, 0.745, 1.745], ['r', -0.24, 0.775, 1.85], ['r', -0.36, 0.765, 1.915]], 0.021, m.hose);      // upper radiator hose
  hose([['e', 0.13, 0.385, 1.645], ['e', 0.20, 0.38, 1.73], ['r', 0.31, 0.38, 1.84], ['r', 0.36, 0.38, 1.88]], 0.021, m.hose);          // lower radiator hose
  hose([['e', -0.10, 0.69, 1.09], ['e', -0.14, 0.76, 1.04], ['f', -0.16, 0.79, 0.985]], 0.012, m.hose, 6, 5);                            // heater hoses
  hose([['e', -0.15, 0.50, 1.12], ['e', -0.20, 0.62, 1.06], ['f', -0.23, 0.74, 0.985]], 0.012, m.hose, 6, 5);
  hose([['e', 0.29, 0.645, 1.615], ['e', 0.30, 0.66, 1.64], [air, 0.31, 0.665, 1.665], [air, 0.32, 0.67, 1.685]], 0.04, m.rubber, 4, 8);  // intake duct
  hose([[exp, -0.35, 0.765, 1.44], [exp, -0.33, 0.80, 1.55], ['r', -0.345, 0.79, 1.88], ['r', -0.355, 0.78, 1.935]], 0.006, m.hose, 8, 4); // overflow
  const cabP = hose([[bat, -0.34, 0.80, 1.24], [bat, -0.30, 0.79, 1.30], ['e', -0.20, 0.52, 1.10], ['e', -0.175, 0.44, 1.07]], 0.009, m.plus, 8, 4);
  const cabN = hose([[bat, -0.43, 0.80, 1.24], [bat, -0.45, 0.76, 1.30], ['f', -0.40, 0.42, 1.33]], 0.008, m.rubber, 6, 4);
  bat.cables = [cabP, cabN]; exp.cables = [hoses[5]]; air.cables = [hoses[4]];

  // fewer draw calls: everything rigid inside the engine, subframe and battery tray
  mergeStatic(eng, new Set([fan, ...spin.map(x => x.o)]));
  mergeStatic(sub, new Set()); mergeStatic(tray, new Set()); mergeStatic(booster, new Set());

  // ───────────── crush model ─────────────
  const NB = 21, XB0 = -0.8, DX = 0.08;
  let prof = null;              // crush per x bin (m)
  let lastFC = -1, dirty = true;
  const st = { E: 0, Es: 0, drop: 0, pitch: 0, squash: 1, bulge: 0, impactX: 0 };
  function computeProfile() {
    const parts = car.parts; if (!parts) { prof = null; return; }
    const front = new Float32Array(NB).fill(-9), sum = new Float32Array(NB), mx = new Float32Array(NB), cnt = new Float32Array(NB);
    const each = (fn) => { for (const p of parts) { if (p.gone || !p.orig || !p.tgt) continue; const o = p.orig, t = p.tgt;
      for (let i = 0; i < o.length; i += 3) { const oz = o[i + 2]; if (oz < 1.45) continue; const oh = o[i + 1] + CG; if (oh < 0.25 || oh > 0.86) continue;
        const b = Math.round((o[i] - XB0) / DX); if (b < 0 || b >= NB) continue; fn(b, oz, t[i + 2]); } } };
    each((b, oz) => { if (oz > front[b]) front[b] = oz; });
    each((b, oz, tz) => { if (oz < front[b] - 0.18) return; const d = Math.max(0, oz - tz); sum[b] += d; cnt[b]++; if (d > mx[b]) mx[b] = d; });
    const out = new Float32Array(NB); let any = false;
    for (let b = 0; b < NB; b++) { if (cnt[b]) { out[b] = 0.85 * sum[b] / cnt[b] + 0.15 * mx[b]; any = true; } else out[b] = -1; }
    if (!any) { prof = null; return; }
    for (let b = 0; b < NB; b++) if (out[b] < 0) { let best = 0, bd = 99; for (let c = 0; c < NB; c++) if (out[c] >= 0 && Math.abs(c - b) < bd) { bd = Math.abs(c - b); best = out[c]; } out[b] = best; }
    // light smoothing so the structure folds, not steps
    const sm = new Float32Array(NB); for (let b = 0; b < NB; b++) { const a = out[Math.max(0, b - 1)], c = out[Math.min(NB - 1, b + 1)]; sm[b] = Math.max(out[b] * 0.6 + (a + c) * 0.2, out[b] * 0.85); }
    prof = sm;
  }
  // crush at x: from the body panels when available, never far below car.frontCrush in the middle
  function crushAt(x) {
    const fc = car.frontCrush || 0;
    if (!prof) return fc;
    const f = cl((x - XB0) / DX, 0, NB - 1), i = Math.min(NB - 2, Math.floor(f)), t = f - i;
    const c = prof[i] * (1 - t) + prof[i + 1] * t;
    return Math.min(Math.max(c, fc * 0.35), fc + 0.15);
  }
  const pushBeam = x => Math.max(0, crushAt(x) - 0.06);
  const pushPack = x => Math.max(0, crushAt(x) - 0.11);
  // radiator-pack vertex: rigid push, then squeezed against the fan/engine in the fan disc
  function packZ(x, y, z) {
    let zz = z - pushPack(x);
    if (Math.abs(x) < 0.3 && y > 0.33 && y < 0.82) { const floor = 1.63 - st.E + (z - 1.86) * 0.35; if (zz < floor) zz = floor; }
    return zz;
  }
  function railMap(s, z) {      // accordion fold of the rail at side s: returns [z', dy, dx]
    const pb = pushBeam(s * 0.37); if (pb <= 0) return [z, 0, 0];
    const zf = 2.02, zf2 = zf - pb; const za = Math.max(0.97, zf - pb / 0.6);
    const k = Math.max(0.06, (zf2 - za) / (zf - za));
    if (z <= za) return [z, 0, 0];
    const u = (z - za) / (zf - za), a = (1 - k);
    return [za + (z - za) * k, 0.03 * a * Math.sin(u * Math.PI * 5), s * 0.025 * a * Math.sin(u * Math.PI * 5 + 1.2)];
  }
  function bulgeAt(x, y) { const wx = Math.max(0, 1 - (x / 0.5) ** 2), wy = Math.max(0, 1 - ((y - 0.48) / 0.36) ** 2); return st.bulge * wx * wy; }
  function itemPush(it) {
    let c = 0; for (let x = it.x0; x <= it.x1 + 1e-6; x += Math.max(0.04, (it.x1 - it.x0) / 3)) c = Math.max(c, crushAt(x));
    const lim = 2.15 - c - 0.15;                                    // behind the squeezed beam + radiator
    const len = it.zf - it.zr; let zf = Math.min(it.zf, lim);
    const rear = Math.max(0.985 - st.bulge * 0.5, zf - len);
    let l2 = Math.max(len * 0.35, zf - rear); if (zf - l2 < 0.9) zf = 0.9 + l2;
    return { dz: (zf - l2 / 2) - (it.zf + it.zr) / 2, s: l2 / len };
  }

  const _v = new THREE.Vector3(), _m = new THREE.Matrix4();
  function applyCrush() {
    // engine stack-up
    let pc = 0; for (let x = -0.24; x <= 0.241; x += 0.08) pc = Math.max(pc, pushPack(x));
    st.E = Math.max(0, pc - 0.32);
    const E = st.E, Es = Math.min(E, 0.26);
    st.Es = Es; st.squash = Math.max(0.55, (1.07 - (E - Es) * 0.6) / 1.07);
    st.drop = Math.min(0.08, E * 0.2 + Math.max(0, E - Es) * 0.2); st.pitch = Math.min(0.07, E * 0.2);
    st.bulge = Math.min(0.3, Math.max(0, E - 0.01) * 0.75);
    // beam / pack vertices
    for (const d of deform) {
      const p = d.o.geometry.attributes.position, a = p.array, o = d.orig;
      for (let i = 0; i < a.length; i += 3) {
        const x = o[i], y = o[i + 1], z = o[i + 2];
        let zz, yy = y, xx = x;
        if (d.layer === 'beam') { const pb = pushBeam(x); zz = z - pb; if (pb > 0) { const j = hash(x * 9, y * 7, z * 5); zz -= pb * 0.08 * j; yy += (j - 0.5) * pb * 0.06; } }
        else { zz = packZ(x, y, z); const pp = pushPack(x); if (pp > 0.02) { const j = hash(x * 7.1, y * 5.3, z * 3.7); zz -= pp * 0.06 * j; yy += (j - 0.5) * pp * 0.08; xx += (hash(y * 3, z * 9, x * 2) - 0.5) * pp * 0.05; } }
        a[i] = xx; a[i + 1] = yy; a[i + 2] = zz;
      }
      p.needsUpdate = true; d.o.geometry.computeVertexNormals(); d.o.geometry.computeBoundingSphere();
    }
    for (const r of rails) {
      const p = r.o.geometry.attributes.position, a = p.array, o = r.orig;
      for (let i = 0; i < a.length; i += 3) { const [z2, dy, dx] = railMap(r.s, o[i + 2]); a[i] = o[i] + dx; a[i + 1] = o[i + 1] + dy; a[i + 2] = z2; }
      p.needsUpdate = true; r.o.geometry.computeVertexNormals(); r.o.geometry.computeBoundingSphere();
    }
    { // fan: shoved onto the pulleys by the radiator, blades fold
      const back = Math.max(0, 1.868 - packZ(0, 0.58, 1.925));
      st.jam = back > 0.004; fan.position.z = Math.max(1.70 - st.E * 0, 1.848 - back); fan.scale.z = Math.max(0.35, 1 - back * 2);
      fan.children.forEach((c, k) => { if (k) { c.rotation.x = Math.min(0.9, back * 3) * (hash(k, 1, 2) - 0.3); c.scale.y = 1 - Math.min(0.4, back * 1.5) * hash(k, 3, 1); } });
    }
    sub.position.z = (railMap(1, 1.36)[0] + railMap(-1, 1.36)[0]) / 2 - 1.36 - Math.max(0, E - 0.15) * 0.4; sub.position.y = -st.drop * 0.6;
    for (const f of fw) {
      const p = f.o.geometry.attributes.position, a = p.array, o = f.orig;
      for (let i = 0; i < a.length; i += 3) { const b = bulgeAt(o[i], o[i + 1]); a[i + 2] = o[i + 2] - b; a[i + 1] = o[i + 1] - b * 0.15; }
      p.needsUpdate = true; f.o.geometry.computeVertexNormals();
    }
    booster.position.z = 1.02 - bulgeAt(0.39, 0.70) - Math.max(0, 1.17 - (2.15 - crushAt(0.39) - 0.15));
    for (const it of items) { if (it.gone) continue; const { dz, s } = itemPush(it); it.g.position.z = it.p0.z + dz; it.g.scale.z = s;
      const tilt = Math.min(0.35, Math.max(0, it.p0.z + 0 - it.g.position.z) * 0.8); it.g.rotation.x = tilt * (it.name === 'washer' ? -1 : 0.6); it.g.rotation.z = tilt * 0.4 * (it.p0.x > 0 ? 1 : -1); }
    tray.position.z = items[0].gone ? 0 : bat.g.position.z - bat.p0.z;
    // engine transform (without vibration) for hose ends
    engPivot.position.set(PIV.x, PIV.y - st.drop, PIV.z - Es); engPivot.rotation.set(st.pitch, 0, 0); engPivot.scale.set(1, 1, st.squash);
    engPivot.updateMatrix(); eng.updateMatrix(); _m.multiplyMatrices(engPivot.matrix, eng.matrix);
    for (const h of hoses) {
      if (h.hidden) continue;
      const pts = h.pts.map(([sp, x, y, z]) => {
        if (sp === 'e') return _v.set(x, y, z).applyMatrix4(_m).clone();
        if (sp === 'r') return V(x, y, packZ(x, y, z));
        if (sp === 'f') return V(x, y, z - bulgeAt(x, y));
        const g = sp.g; return V(x + g.position.x - sp.p0.x, y + g.position.y - sp.p0.y, z + g.position.z - sp.p0.z);
      });
      const old = h.o.geometry; h.o.geometry = tubeG(pts, h.r, h.seg, h.rad); old.dispose();
    }
    if (pc > 0.04 && !ctx.sys.radiatorBroken) breakRadiator(0.35 + pc);
  }

  // ───────────── leaks (shared array, own entries only) ─────────────
  const sys = ctx.sys;
  const leakC = { kind: 'coolant', at: new THREE.Vector3(), rate: 0, src: 'engine.radiator' };
  const leakO = { kind: 'oil', at: new THREE.Vector3(), rate: 0, src: 'engine.sump' };
  function setLeak(L, rate) {
    if (!Array.isArray(sys.leaks)) sys.leaks = [];
    L.rate = Math.max(L.rate, cl(rate, 0, 1));
    if (sys.leaks.indexOf(L) < 0) sys.leaks.push(L);
  }
  function breakRadiator(rate) { sys.radiatorBroken = true; setLeak(leakC, rate); }
  sys.engineShift = 0;

  // ───────────── detach (debris) ─────────────
  const _wp = new THREE.Vector3(), _wq = new THREE.Quaternion(), _q2 = new THREE.Quaternion();
  function detach(it, ev) {
    if (it.gone || !CANNON || !ctx.addDebris) return;
    it.gone = true;
    ctx.group.updateMatrixWorld(true);
    const hood = (car.parts || []).find(p => p.name === 'hood');
    const open = !hood || hood.gone;
    const g = it.g; g.scale.set(1, 1, 1);
    // spawn where the debris will not sit inside the car's collider: out through the open bay, or dropped under the car
    _wp.set(g.position.x, open ? 1.0 : 0.095, g.position.z - 0.05);
    root.localToWorld(_wp);
    g.getWorldQuaternion(_wq);
    let half = it.half.slice();
    if (!open) { _q2.setFromAxisAngle(new THREE.Vector3(0, 0, 1), Math.PI / 2); _wq.multiply(_q2); }   // lies on its side under the floor
    if (it.cables) for (const c of it.cables) { c.hidden = true; c.o.visible = false; }
    g.parent.remove(g); g.position.copy(_wp); g.quaternion.copy(_wq);
    const mass = it.name === 'battery' ? 16 : it.name === 'airbox' ? 3 : 2.5;
    const b = new CANNON.Body({ mass, material: ctx.mProp, linearDamping: 0.08, angularDamping: 0.1 });
    b.addShape(new CANNON.Box(new CANNON.Vec3(Math.max(0.03, half[0]), Math.max(0.03, half[1]), Math.max(0.03, half[2]))));
    b.position.set(_wp.x, _wp.y, _wp.z); b.quaternion.set(_wq.x, _wq.y, _wq.z, _wq.w);
    const vel = car.body.velocity, nW = ev && ev.nW ? ev.nW : { x: 0, y: 0, z: 0 }, r = (a, c) => a + Math.random() * (c - a);
    if (open) b.velocity.set(vel.x * 0.8 - nW.x * r(0.5, 2) + r(-1.2, 1.2), vel.y + r(1.5, 3.5), vel.z * 0.8 - nW.z * r(0.5, 2) + r(-1.2, 1.2));
    else b.velocity.set(vel.x * 0.85 + r(-0.8, 0.8), vel.y - 0.5, vel.z * 0.85 + r(-0.8, 0.8));
    b.angularVelocity.set(r(-6, 6), r(-6, 6), r(-6, 6));
    g.traverse(o => { if (o.isMesh) { o.castShadow = true; o.frustumCulled = false; } });
    ctx.addDebris(g, b);
    if (it.name === 'battery') tray.visible = true;
    if (ctx.sound && ctx.sound.clunk) try { ctx.sound.clunk(0.5); } catch (e) { /* sound optional */ }
    if (it.name === 'washer' || it.name === 'expTank') {     // a burst bottle sprays a little
      if (ctx.fx && ctx.fx.puff) ctx.fx.puff(_wp.clone(), { x: r(-0.3, 0.3), y: r(0.2, 0.6), z: r(-0.3, 0.3) }, { life: 1.2, s0: 0.2, s1: 0.9, a: 0.18, c: 0.9 });
    }
  }

  // ───────────── public ─────────────
  let ang = 0;
  const leakPos = (L, x, y, z, eSpace) => { if (eSpace) { _v.set(x, y, z).applyMatrix4(_m); L.at.set(_v.x, _v.y - CG, _v.z); } else L.at.set(x, y - CG, z); };
  root.userData.engineState = st;
  computeProfile(); applyCrush();

  return {
    root,
    onImpact(ev) {
      if (!ev || ev.scrape) return;
      computeProfile(); dirty = true;
      const v = ev.v || 0, depth = ev.depth || 0;
      const z = ev.pL ? ev.pL.z : 0, x = ev.pL ? ev.pL.x : 0;
      if (ev.frontal) {
        st.impactX = x;
        if (v > 7 && depth > 0.12) breakRadiator(0.25 + (v - 7) / 18);
        if (v > 11 || depth > 0.45) setLeak(leakO, 0.12 + (v - 10) / 26);
        if (v > 15) detach(wash, ev);
        if (v > 16.5) detach(exp, ev);
        if (v > 21) { detach(bat, ev); detach(air, ev); }
      } else if (ev.side && z > 0.95 && v > 15) {          // side hit into the bay corner
        if (x > 0.3) detach(wash, ev); else if (x < -0.3) detach(exp, ev);
        if (v > 18) setLeak(leakO, 0.15 + (v - 15) / 30);
      }
    },
    update(dt) {
      const fc = car.frontCrush || 0;
      if (dirty || Math.abs(fc - lastFC) > 1e-4) { if (Math.abs(fc - lastFC) > 1e-4 && !dirty) computeProfile(); lastFC = fc; dirty = false; applyCrush(); }
      sys.engineShift = st.Es;
      // live engine: tiny shake + pulleys/fan from rpm
      const alive = (car.engine || 0) > 0.06;
      const t = ctx.time ? ctx.time() : 0;
      let ox = 0, oy = 0, rz = 0;
      if (alive) {
        const w = (car.rpm || 850) / 60 * Math.PI * 2;
        ang += w * dt;
        const rough = 1 + (1 - car.engine) * 4;          // a hurt engine shakes more
        ox = Math.sin(t * w * 2.03) * 0.0007 * rough; oy = Math.sin(t * w * 2) * 0.0009 * rough; rz = Math.sin(t * w * 0.5 + 1) * 0.0025 * rough;
        const jam = st.jam;                        // fan blades jammed in the radiator
        for (const s of spin) if (!(s.fan && jam)) s.o.rotation.z = -ang * s.k;
      }
      engPivot.position.set(PIV.x + ox, PIV.y - st.drop + oy, PIV.z - st.Es);
      engPivot.rotation.set(st.pitch, 0, rz);
      // leak points follow the deformed parts
      if (leakC.rate > 0) leakPos(leakC, 0.30, 0.355, packZ(0.30, 0.36, 1.93), false);
      if (leakO.rate > 0) { engPivot.updateMatrix(); eng.updateMatrix(); _m.multiplyMatrices(engPivot.matrix, eng.matrix); leakPos(leakO, 0.02, 0.27, 1.50, true); }
    },
    dispose() {
      root.traverse(o => o.geometry && o.geometry.dispose());
      if (Array.isArray(sys.leaks)) for (const L of [leakC, leakO]) { const i = sys.leaks.indexOf(L); if (i >= 0) sys.leaks.splice(i, 1); }
      if (root.parent) root.parent.remove(root);
    },
  };
}
