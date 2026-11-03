// Wheels, tyres, brakes and suspension.
// OWNER: wheels agent. Interface: see SPEC.md §Car modules.
import { THREE, WHEELS, WHEEL_R, WHEEL_W, STD, PALETTE, CG, ZF, ZR, gy, clamp, rnd } from './common.js';

// ───────────────────────────── small geometry builder (non-indexed, flat shaded)
// Winding is fixed per triangle from an "inside" reference point, so FrontSide culling works on hand-made shells.
const V = (x, y, z) => [x, y, z];
class GB {
  constructor() { this.p = []; }
  tri(a, b, c, inside) {
    if (inside) {
      const ux = b[0] - a[0], uy = b[1] - a[1], uz = b[2] - a[2], vx = c[0] - a[0], vy = c[1] - a[1], vz = c[2] - a[2];
      const nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
      const mx = (a[0] + b[0] + c[0]) / 3 - inside[0], my = (a[1] + b[1] + c[1]) / 3 - inside[1], mz = (a[2] + b[2] + c[2]) / 3 - inside[2];
      if (nx * mx + ny * my + nz * mz < 0) { const t = b; b = c; c = t; }
    }
    this.p.push(...a, ...b, ...c);
  }
  quad(a, b, c, d, inside) { this.tri(a, b, c, inside); this.tri(a, c, d, inside); }
  geo() { const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(this.p, 3)); g.computeVertexNormals(); return g; }
}
// point on a ring around the x axis: radius r, axial x, angle th (y = r cos th, z = r sin th)
const P = (r, x, th) => V(x, r * Math.cos(th), r * Math.sin(th));
// surface of revolution around x from a profile [[r, x], ...]; insideOf(th) gives the reference point for winding
function lathe(gb, prof, N, insideOf) {
  for (let j = 0; j < N; j++) {
    const a0 = j / N * Math.PI * 2, a1 = (j + 1) / N * Math.PI * 2, am = (a0 + a1) / 2;
    for (let k = 0; k < prof.length - 1; k++) {
      const [r0, x0] = prof[k], [r1, x1] = prof[k + 1];
      gb.quad(P(r0, x0, a0), P(r1, x1, a0), P(r1, x1, a1), P(r0, x0, a1), insideOf ? insideOf(am, k) : null);
    }
  }
}
// block bent along an arc around x: radii r0..r1, angles a0..a1, axial x0..x1, n arc steps
function arcBlock(gb, r0, r1, a0, a1, x0, x1, n = 2) {
  const am = (a0 + a1) / 2, c = P((r0 + r1) / 2, (x0 + x1) / 2, am);
  for (let k = 0; k < n; k++) {
    const t0 = a0 + (a1 - a0) * k / n, t1 = a0 + (a1 - a0) * (k + 1) / n, cm = P((r0 + r1) / 2, (x0 + x1) / 2, (t0 + t1) / 2);
    gb.quad(P(r1, x0, t0), P(r1, x1, t0), P(r1, x1, t1), P(r1, x0, t1), cm);   // outer
    gb.quad(P(r0, x0, t0), P(r0, x1, t0), P(r0, x1, t1), P(r0, x0, t1), cm);   // inner
    gb.quad(P(r0, x1, t0), P(r1, x1, t0), P(r1, x1, t1), P(r0, x1, t1), cm);   // +x face
    gb.quad(P(r0, x0, t0), P(r1, x0, t0), P(r1, x0, t1), P(r0, x0, t1), cm);   // -x face
  }
  gb.quad(P(r0, x0, a0), P(r1, x0, a0), P(r1, x1, a0), P(r0, x1, a0), c);
  gb.quad(P(r0, x0, a1), P(r1, x0, a1), P(r1, x1, a1), P(r0, x1, a1), c);
}
// prism along x: n-gon of radius r centred at (y,z), from x0 to x1, capped at x1
function prismX(gb, n, r, y, z, x0, x1, rot = 0) {
  const ctr = V((x0 + x1) / 2, y, z), pt = (k, x) => { const a = rot + k / n * Math.PI * 2; return V(x, y + r * Math.cos(a), z + r * Math.sin(a)); };
  for (let k = 0; k < n; k++) gb.quad(pt(k, x0), pt(k + 1, x0), pt(k + 1, x1), pt(k, x1), ctr);
  for (let k = 1; k < n - 1; k++) gb.tri(pt(0, x1), pt(k, x1), pt(k + 1, x1), ctr);
}

// ───────────────────────────── shared look
const TYRE_N = 24;
function tyreGeometry() {
  const gb = new GB();
  // carcass: bead → sidewall → shoulder → groove floor → centre rib → … (r, x); outer side is +x
  const prof = [[0.212, -0.091], [0.262, -0.109], [0.304, -0.104], [0.320, -0.095], [0.320, -0.037], [0.330, -0.033],
    [0.330, 0.033], [0.320, 0.037], [0.320, 0.095], [0.304, 0.104], [0.262, 0.109], [0.212, 0.091]];
  lathe(gb, prof, TYRE_N, a => P(0.262, 0, a));
  // shoulder tread blocks, staggered left/right, slanted lateral grooves
  const pitch = Math.PI * 2 / TYRE_N, hw = pitch * 0.41;
  for (const sd of [1, -1]) for (let j = 0; j < TYRE_N; j++) {
    const c = (j + (sd > 0 ? 0 : 0.5)) * pitch, sk = 0.22 * pitch * sd;
    const xi = sd * 0.041, xo = sd * 0.099, xb = sd * 0.104;
    const tiA = P(0.330, xi, c - hw + sk), tiB = P(0.330, xi, c + hw + sk), toA = P(0.327, xo, c - hw), toB = P(0.327, xo, c + hw);
    const biA = P(0.319, xi, c - hw + sk), biB = P(0.319, xi, c + hw + sk), boA = P(0.303, xb, c - hw), boB = P(0.303, xb, c + hw);
    const ins = P(0.312, sd * 0.07, c + sk * 0.5);
    gb.quad(tiA, tiB, toB, toA, ins); gb.quad(tiA, toA, boA, biA, ins); gb.quad(tiB, toB, boB, biB, ins);
    gb.quad(tiA, tiB, biB, biA, ins); gb.quad(toA, toB, boB, boA, ins);
  }
  return gb.geo();
}
function rimGeometry() {   // barrel + flanges + outer lip (double sided material)
  const gb = new GB();
  lathe(gb, [[0.186, 0.093], [0.221, 0.101], [0.227, 0.091], [0.207, 0.080], [0.204, -0.082], [0.223, -0.097]], 14, null);
  return gb.geo();
}
function spokesGeometry() {  // 5 dished spokes from the hub to the lip, plus the hub face and lug nut bosses
  const gb = new GB(), n = 5;
  for (let k = 0; k < n; k++) {
    const a = k / n * Math.PI * 2, ca = Math.cos(a), sa = Math.sin(a);
    const pt = (r, w, x) => V(x, r * ca - w * sa, r * sa + w * ca);
    const r0 = 0.058, r1 = 0.197, w0 = 0.024, w1 = 0.019, xf0 = 0.066, xf1 = 0.094, t = 0.026;
    const ins = pt(0.13, 0, 0.068);
    gb.quad(pt(r0, -w0, xf0), pt(r0, w0, xf0), pt(r1, w1, xf1), pt(r1, -w1, xf1), ins);                       // face
    gb.quad(pt(r0, -w0, xf0 - t), pt(r0, w0, xf0 - t), pt(r1, w1 * 1.6, xf1 - t), pt(r1, -w1 * 1.6, xf1 - t), ins); // back (flared into barrel)
    gb.quad(pt(r0, w0, xf0), pt(r0, w0, xf0 - t), pt(r1, w1 * 1.6, xf1 - t), pt(r1, w1, xf1), ins);
    gb.quad(pt(r0, -w0, xf0), pt(r0, -w0, xf0 - t), pt(r1, -w1 * 1.6, xf1 - t), pt(r1, -w1, xf1), ins);
  }
  // hub: 10-sided boss, face at x 0.066
  prismX(gb, 8, 0.07, 0, 0, 0.036, 0.066, Math.PI / 8);
  return gb.geo();
}
function nutsGeometry() {
  const gb = new GB();
  for (let k = 0; k < 5; k++) { const a = (k + 0.5) / 5 * Math.PI * 2; prismX(gb, 6, 0.0105, 0.05 * Math.cos(a), 0.05 * Math.sin(a), 0.06, 0.08, a); }
  return gb.geo();
}
function capGeometry() {   // centre cap, slightly domed, centred on its own origin (it can pop off as debris)
  const gb = new GB(), n = 8, ctr = V(-0.004, 0, 0), x0 = -0.007, x1 = 0.004, x2 = 0.008;
  const pt = (r, x, k) => P(r, x, k / n * Math.PI * 2 + Math.PI / 8);
  for (let k = 0; k < n; k++) { gb.quad(pt(0.031, x0, k), pt(0.031, x0, k + 1), pt(0.029, x1, k + 1), pt(0.029, x1, k), ctr); gb.quad(pt(0.029, x1, k), pt(0.029, x1, k + 1), pt(0.016, x2, k + 1), pt(0.016, x2, k), ctr); }
  for (let k = 1; k < n - 1; k++) gb.tri(pt(0.016, x2, 0), pt(0.016, x2, k), pt(0.016, x2, k + 1), ctr);
  return gb.geo();
}
function caliperGeometry(a) {   // floating caliper straddling the disc edge at angle a: outboard pad housing, bridge, inboard piston body
  const gb = new GB();
  arcBlock(gb, 0.112, 0.180, a - 0.34, a + 0.34, 0.001, 0.019, 2);
  arcBlock(gb, 0.157, 0.190, a - 0.30, a + 0.30, -0.034, 0.002, 2);
  arcBlock(gb, 0.104, 0.184, a - 0.42, a + 0.42, -0.074, -0.031, 2);
  prismX(gb, 6, 0.028, 0.142 * Math.cos(a), 0.142 * Math.sin(a), -0.090, -0.072);       // piston cap bulge
  return gb.geo();
}
let _ventTex = null;
function ventTexture() {   // disc edge: two friction plates with the cooling vanes between them
  if (_ventTex) return _ventTex;
  const c = document.createElement('canvas'); c.width = 128; c.height = 16; const x = c.getContext('2d');
  x.fillStyle = '#6d6a66'; x.fillRect(0, 0, 128, 16); x.fillStyle = '#151413'; x.fillRect(0, 5, 128, 6);
  x.fillStyle = '#4c4946'; for (let i = 0; i < 128; i += 8) x.fillRect(i, 5, 3, 6);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.wrapS = THREE.RepeatWrapping; t.repeat.set(3, 1);
  return (_ventTex = t);
}

const _X = new THREE.Vector3(1, 0, 0), _Yv = new THREE.Vector3(0, 1, 0), _Z = new THREE.Vector3(0, 0, 1);
const _qa = new THREE.Quaternion(), _qb = new THREE.Quaternion(), _qc = new THREE.Quaternion(), _qd = new THREE.Quaternion();

// Per-car data shared by the 4 wheel modules and the suspension module.
const SHARED = new WeakMap();
const shared = car => { let s = SHARED.get(car); if (!s) SHARED.set(car, s = { flat: [0, 0, 0, 0], bend: [0, 0, 0, 0] }); return s; };

// One rolling wheel assembly (tyre + rim + brake disc...). Lives in the SCENE (world space): the game copies the
// cannon wheel transform onto `group` every frame. Local frame: axle along x, wheel centre at origin.
export function createWheel(ctx, i) {
  const W = WHEELS[i], side = W.x > 0 ? 1 : -1, sys = ctx.sys, sh = shared(ctx.car);
  if (!sys.tyreFlat) sys.tyreFlat = [false, false, false, false];
  const g = new THREE.Group(); g.name = 'wheel' + i;
  const mRubber = STD(PALETTE.rubber, { roughness: 0.93 });
  const mRim = STD(0xaeb2b4, { metalness: 0.65, roughness: 0.38, side: THREE.DoubleSide });
  const mHub = STD(0x8e9294, { metalness: 0.6, roughness: 0.45 });
  const mNut = STD(0xc4c7c9, { metalness: 0.8, roughness: 0.3 });
  const mCap = STD(0x3a3d3f, { metalness: 0.4, roughness: 0.5 });
  const mDisc = STD(0x8a8784, { metalness: 0.7, roughness: 0.42 });
  const mVent = STD(0xffffff, { metalness: 0.5, roughness: 0.6, map: ventTexture() });
  const mHat = STD(PALETTE.castIron, { metalness: 0.5, roughness: 0.6 });
  const mCal = STD(0x7a2f27, { metalness: 0.3, roughness: 0.55 });
  const mShield = STD(PALETTE.darkSteel, { metalness: 0.4, roughness: 0.7, side: THREE.DoubleSide });

  // rotor: everything that spins. Its quaternion fixes the order of spin and camber (see update).
  const rotor = new THREE.Group(); g.add(rotor);
  const bend = new THREE.Group(); rotor.add(bend);               // bent rim: tilt that wobbles as it spins
  const mir = new THREE.Group(); mir.scale.x = side; bend.add(mir); // outer face is +x on the left, -x on the right
  const tyreGeo = tyreGeometry();
  const tyre = new THREE.Mesh(tyreGeo, mRubber); tyre.castShadow = true; tyre.receiveShadow = true; mir.add(tyre);
  const oval = new THREE.Group(); mir.add(oval);                  // rim ovality after a hit
  const rim = new THREE.Mesh(rimGeometry(), mRim); rim.castShadow = true; oval.add(rim);
  const spokes = new THREE.Mesh(spokesGeometry(), mRim); spokes.castShadow = true; oval.add(spokes);
  const nuts = new THREE.Mesh(nutsGeometry(), mNut); oval.add(nuts);
  const cap = new THREE.Mesh(capGeometry(), mCap); cap.position.x = 0.073; oval.add(cap);
  const disc = new THREE.Mesh(new THREE.CylinderGeometry(0.155, 0.155, 0.026, 14), [mVent, mDisc, mDisc]); disc.rotation.z = Math.PI / 2; disc.position.x = -0.015; mir.add(disc);
  const hat = new THREE.Mesh(new THREE.CylinderGeometry(0.078, 0.078, 0.038, 10, 1, true), mHat); hat.rotation.z = Math.PI / 2; hat.position.x = 0.017; mir.add(hat);
  // fixed: caliper and dust shield ride on the knuckle (steer + camber, no spin)
  const fixed = new THREE.Group(); g.add(fixed);
  const fmir = new THREE.Group(); fmir.scale.x = side; fixed.add(fmir);
  const calA = -(Math.PI / 2 - 0.35);                             // behind the axle, a little above it
  const caliper = new THREE.Mesh(caliperGeometry(calA), mCal); fmir.add(caliper);
  const shield = new THREE.Mesh(new THREE.CircleGeometry(0.168, 12), mShield); shield.rotation.y = Math.PI / 2; shield.position.x = -0.082; fmir.add(shield);

  let flat = false, base = null, bent = false, bendAmt = 0, lastRot = NaN, popped = false;
  function deflate(rot) {   // flatten the contact patch in the non-spinning frame, then spin back
    const pos = tyreGeo.attributes.position, a = pos.array, f = 0.287, c = Math.cos(rot), s = Math.sin(rot);
    for (let k = 0; k < a.length; k += 3) {
      let x = base[k], y = base[k + 1], z = base[k + 2];
      let ys = y * c + z * s, zs = -y * s + z * c;          // R(x, -rot)
      const d = -f - ys;
      if (d > -0.05) { const e = Math.max(0, d), bul = Math.min(1, (d + 0.05) / 0.07); if (e > 0) ys = -f - e * 0.15; x *= 1 + bul * bul * 0.16; zs *= 1 + e * 1.4; }
      a[k] = x; a[k + 1] = ys * c - zs * s; a[k + 2] = ys * s + zs * c;   // R(x, +rot)
    }
    pos.needsUpdate = true;
  }
  return {
    group: g,
    // state: ctx.car.wheelState[i] = {dmg, broken, camber}; wi = cannon WheelInfo (suspensionLength, steering, rotation, skidInfo)
    update(dt, state, wi) {
      const rot = wi.rotation || 0, cam = state.camber || 0;
      // game: group = chassis·steer·spin·camber. Visible rotor should be chassis·steer·camber·spin, caliper chassis·steer·camber.
      _qa.setFromAxisAngle(_Z, -cam); _qb.setFromAxisAngle(_X, rot); _qc.setFromAxisAngle(_Z, cam); _qd.setFromAxisAngle(_X, -rot);
      fixed.quaternion.copy(_qa).multiply(_qb).multiply(_qc);
      rotor.quaternion.copy(fixed.quaternion).multiply(_qd);
      const dmg = state.dmg || 0;
      if (dmg > 0.15) {
        if (!bent) { bent = true; bendAmt = rnd(0.6, 1) * (Math.random() < 0.5 ? -1 : 1); }
        const k = Math.min(1, (dmg - 0.15) / 0.4);
        bend.rotation.set(0, 0, bendAmt * (0.025 + 0.06 * k)); oval.scale.set(1, 1 - 0.05 * k, 1 + 0.03 * k);
        sh.bend[i] = k;
      }
      if (dmg > 0.3 && !flat) {
        flat = true; sys.tyreFlat[i] = true; sh.flat[i] = 1; base = Float32Array.from(tyreGeo.attributes.position.array);
        if (!state.broken && wi.radius > 0.29) wi.radius = 0.29;
      }
      if (flat && rot !== lastRot) { lastRot = rot; deflate(rot); }
    },
    onBreak() {   // the assembly becomes debris; the centre cap pops off on its own
      if (popped) return; popped = true;
      sys.tyreFlat[i] = true;
      cap.updateWorldMatrix(true, false);
      const p = new THREE.Vector3(), q = new THREE.Quaternion(), sc = new THREE.Vector3(); cap.matrixWorld.decompose(p, q, sc);
      if (side < 0) q.multiply(_qa.setFromAxisAngle(_Yv, Math.PI));   // mirrored side: face the cap outward without negative scale
      cap.parent.remove(cap); cap.position.copy(p); cap.quaternion.copy(q); cap.scale.set(1, 1, 1);
      const { CANNON } = ctx; const b = new CANNON.Body({ mass: 0.4, material: ctx.mProp, linearDamping: 0.1, angularDamping: 0.1 });
      b.addShape(new CANNON.Box(new CANNON.Vec3(0.008, 0.03, 0.03)));
      b.position.set(p.x, p.y, p.z); b.quaternion.set(q.x, q.y, q.z, q.w);
      const out = _X.clone().applyQuaternion(q), v = ctx.car.body.velocity;
      b.velocity.set(v.x + out.x * 4 + rnd(-1, 1), v.y + rnd(2, 4), v.z + out.z * 4 + rnd(-1, 1));
      b.angularVelocity.set(rnd(-20, 20), rnd(-20, 20), rnd(-20, 20));
      ctx.addDebris(cap, b);
    },
    dispose() { g.traverse(o => o.geometry && o.geometry.dispose()); if (!popped) cap.geometry.dispose(); },
  };
}

// ───────────────────────────── suspension (chassis frame)
// unit-length parts along +y from 0 to 1, stretched between two points every frame
function unitCyl(r0, r1, n = 6, open = true) { const g = new THREE.CylinderGeometry(r1, r0, 1, n, 1, open); g.translate(0, 0.5, 0); return g; }
function unitBox(w, t) { const g = new THREE.BoxGeometry(w, 1, t); g.translate(0, 0.5, 0); return g; }
class Helix extends THREE.Curve {
  constructor(R, n) { super(); this.R = R; this.n = n; }
  getPoint(t, o = new THREE.Vector3()) {   // closed, flat end coils
    const a = t * this.n * Math.PI * 2, e = 0.6 / this.n; let h;
    if (t < e) h = t * 0.35; else if (t > 1 - e) h = 1 - (1 - t) * 0.35; else h = e * 0.35 + (t - e) / (1 - 2 * e) * (1 - 2 * e * 0.35);
    return o.set(this.R * Math.cos(a), h, this.R * Math.sin(a));
  }
}
const springGeo = (R, wire, n) => new THREE.TubeGeometry(new Helix(R, n), Math.round(n * 7), wire, 4, false);
const _d = new THREE.Vector3(), _bx = new THREE.Vector3(), _bz = new THREE.Vector3(), _m = new THREE.Matrix4(), _up = new THREE.Vector3();
// orient mesh so its local +y runs from a to b (length scale on y); up hint keeps flat arms flat
function span(m, a, b, up = _X, stretch = true) {
  _d.subVectors(b, a); const L = _d.length() || 1e-4; _d.divideScalar(L);
  _bx.crossVectors(_d, up); if (_bx.lengthSq() < 1e-6) _bx.crossVectors(_d, _Z); _bx.normalize(); _bz.crossVectors(_bx, _d);
  _m.makeBasis(_bx, _d, _bz); m.quaternion.setFromRotationMatrix(_m); m.position.copy(a); if (stretch) m.scale.set(1, L, 1);
}

export function createSuspension(ctx) {
  const car = ctx.car, sys = ctx.sys;
  const root = new THREE.Group(); root.name = 'suspension'; ctx.group.add(root);
  const mSteel = STD(0x55595c, { metalness: 0.55, roughness: 0.55 });
  const mArm = STD(0x4b4e50, { metalness: 0.45, roughness: 0.6 });
  const mCast = STD(PALETTE.castIron, { metalness: 0.5, roughness: 0.65 });
  const mAlu = STD(PALETTE.alu, { metalness: 0.7, roughness: 0.4 });
  const mSpring = STD(0x8c2f24, { metalness: 0.35, roughness: 0.5 });
  const mDamper = STD(0x3c3f41, { metalness: 0.5, roughness: 0.45 });
  const mRod = STD(0xc9ccce, { metalness: 0.9, roughness: 0.2 });
  const mRubber = STD(PALETTE.rubber, { roughness: 0.92 });
  const add = (geo, mat, shadow = false, parent = root) => { const m = new THREE.Mesh(geo, mat); m.castShadow = shadow; parent.add(m); return m; };
  const v3 = (x, y, z) => new THREE.Vector3(x, y, z);
  const sh = shared(car);

  // shared unit geometries
  const G = {
    body: unitCyl(0.027, 0.027, 8), rod: unitCyl(0.011, 0.011, 6), seat: unitCyl(0.072, 0.072, 10, false), mount: unitCyl(0.062, 0.05, 10, false),
    tie: unitCyl(0.011, 0.011, 6), boot: unitCyl(0.024, 0.016, 6), arm: unitBox(0.05, 0.028), link: unitCyl(0.008, 0.008, 5),
    bar: unitCyl(0.013, 0.013, 6), tarm: unitBox(0.065, 0.035), rdamp: unitCyl(0.024, 0.024, 8), bush: unitCyl(0.022, 0.022, 8, false),
    ball: new THREE.IcosahedronGeometry(0.02, 0), fspring: springGeo(0.058, 0.0085, 5.5), rspring: springGeo(0.062, 0.0095, 4.5),
  };

  // ── front corners: McPherson strut, lower wishbone, knuckle, tie rod
  const front = [], rear = [];
  WHEELS.forEach((W, i) => {
    const s = W.x > 0 ? 1 : -1;
    if (W.f) {
      const c = { i, s, W };
      c.T = v3(0.555 * s, gy(0.775), W.z - 0.03);                        // strut top mount (fixed in the tower)
      c.P1 = v3(0.44 * s, gy(0.215), W.z + 0.04); c.P2 = v3(0.45 * s, gy(0.225), W.z - 0.36);   // wishbone bushes on the subframe
      // knuckle group: pivot at the wheel centre, follows steer + camber
      const k = c.knuckle = new THREE.Group(); k.rotation.order = 'YZX'; root.add(k);
      const kb = new GB(), ins = V(-0.11 * s, 0, 0);
      prismX(kb, 8, 0.058, 0, 0, -0.085 * s, -0.128 * s);                // hub bearing boss
      const knk = (a, b, w, t) => { const m = add(unitBox(w, t), mCast, false, k); span(m, a, b, _Z); return m; };
      c.kUp = knk(v3(-0.11 * s, 0.03, 0), v3(-0.125 * s, 0.095, 0), 0.06, 0.05);   // up to the strut clamp
      c.kLo = knk(v3(-0.10 * s, -0.02, 0), v3(-0.10 * s, -0.13, 0.0), 0.05, 0.04);  // down to the ball joint
      c.kSt = knk(v3(-0.11 * s, -0.01, -0.02), v3(-0.12 * s, -0.025, -0.15), 0.035, 0.03); // steering arm
      add(kb.geo(), mCast, false, k);
      const kcl = add(new THREE.CylinderGeometry(0.036, 0.036, 0.07, 8), mCast, false, k); kcl.position.set(-0.125 * s, 0.11, 0);
      c.kClamp = kcl;
      // strut
      c.body = add(G.body, mDamper, true); c.rod = add(G.rod, mRod); c.seatLo = add(G.seat, mSteel); c.seatHi = add(G.seat, mSteel);
      c.spring = add(G.fspring, mSpring, true); c.mount = add(G.mount, mRubber); c.bump = add(G.boot, mRubber);
      // wishbone
      c.armF = add(G.arm, mArm, true); c.armR = add(G.arm, mArm, true); c.bj = add(G.ball, mSteel);
      c.bushF = add(G.bush, mRubber); c.bushR = add(G.bush, mRubber);
      // tie rod + rack boot
      c.tie = add(G.tie, mSteel); c.tieEnd = add(G.ball, mSteel); c.rackBoot = add(G.boot, mRubber); c.rackRod = add(G.rod, mRod);
      // anti-roll bar drop link
      c.drop = add(G.link, mSteel);
      front.push(c);
    } else {
      const c = { i, s, W };
      c.lowerP = v3(0.615 * s, gy(0.27), W.z + 0.52); c.upperP = v3(0.50 * s, gy(0.45), W.z + 0.30);
      c.springTop = v3(0.555 * s, gy(0.61), W.z + 0.02); c.damperTop = v3(0.615 * s, gy(0.68), W.z - 0.21);
      c.lower = add(G.tarm, mArm, true); c.upper = add(G.arm, mArm, true);
      c.bushL = add(G.bush, mRubber); c.bushU = add(G.bush, mRubber);
      c.spring = add(G.rspring, mSpring, true); c.seatLo = add(G.seat, mSteel); c.seatHi = add(G.seat, mRubber);
      c.dBody = add(G.rdamp, mDamper, true); c.dRod = add(G.rod, mRod); c.dTop = add(G.bush, mRubber); c.dEye = add(G.bush, mRubber);
      c.pad = add(new THREE.BoxGeometry(0.11, 0.03, 0.12), mSteel); c.brk = add(new THREE.BoxGeometry(0.05, 0.16, 0.06), mSteel);
      rear.push(c);
    }
  });
  // steering rack housing with pinion
  const RZ = 1.10, RY = gy(0.30);
  const rack = add(unitCyl(0.026, 0.026, 8, false), mAlu, true); span(rack, v3(-0.30, RY, RZ), v3(0.30, RY, RZ));
  const pinion = add(unitCyl(0.03, 0.03, 8, false), mAlu); span(pinion, v3(0.22, RY, RZ), v3(0.22, RY + 0.09, RZ - 0.07));
  // anti-roll bar: U-bar ahead of the axle, clamped to the subframe, drop links to the struts
  const ARB = { y: gy(0.245), z: 1.64 };
  const arbSegs = []; for (let k = 0; k < 5; k++) arbSegs.push(add(G.bar, mSteel));
  const arbClamps = [add(new THREE.BoxGeometry(0.05, 0.04, 0.05), mRubber), add(new THREE.BoxGeometry(0.05, 0.04, 0.05), mRubber)];

  const C = new THREE.Vector3(), B = new THREE.Vector3(), BJ = new THREE.Vector3(), SA = new THREE.Vector3(), tmp = new THREE.Vector3(), tmp2 = new THREE.Vector3(), dir = new THREE.Vector3();
  const local = (c, x, y, z, out) => out.set(x, y, z).applyEuler(c.knuckle.rotation).add(c.knuckle.position);
  const leaks = [null, null, null, null];
  function leak(i, at, rate) {
    if (!sys.leaks) sys.leaks = [];
    let L = leaks[i]; if (!L) L = leaks[i] = { kind: 'brake', at: new THREE.Vector3(), rate: 0 };
    if (sys.leaks.indexOf(L) < 0) sys.leaks.push(L);
    L.at.copy(at); L.rate = rate;
  }
  const brokenPose = [];   // random but stable dangling pose per corner

  return {
    root,
    onImpact(ev) {
      // a hard hit near a wheel cracks the brake line on that corner even before the wheel is gone
      if (!ev || ev.scrape || !(ev.depth > 0.18)) return;
      WHEELS.forEach((W, i) => { const d = Math.hypot(ev.pL.x - W.x, ev.pL.z - W.z); if (d < 0.75 && ev.v > 9) { const L = leaks[i]; const r = clamp((ev.depth - 0.1) * 1.5, 0.15, 0.6); if (!L || L.rate < r) sh['hit' + i] = r; } });
    },
    update(dt) {
      const wis = car.vehicle.wheelInfos, fc = car.frontCrush || 0, rc = car.rearCrush || 0;
      const steerAvg = front.reduce((a, c) => a + (car.wheelState[c.i].broken ? 0 : wis[c.i].steering || 0), 0) / 2;
      const rackShift = -0.15 * Math.sin(steerAvg);
      for (const c of front) {
        const st = car.wheelState[c.i], wi = wis[c.i], s = c.s, broken = st.broken;
        let L = clamp(wi.suspensionLength, 0.02, 0.4);
        C.set(c.W.x, -0.1 - L, c.W.z);
        const k = c.knuckle; k.position.copy(C);
        if (!broken) k.rotation.set(0, wi.steering || 0, (st.camber || 0) * 0.8 * 1);
        else {
          if (!brokenPose[c.i]) brokenPose[c.i] = { yaw: rnd(-0.6, 0.6), roll: rnd(0.35, 0.6) * s, drop: rnd(0.10, 0.16) };
          const bp = brokenPose[c.i]; k.rotation.set(0, bp.yaw, bp.roll);
          k.position.x -= 0.06 * s; k.position.y = Math.max(k.position.y - 0.04, gy(0.13));
        }
        k.updateMatrixWorld();
        // strut: clamp on the knuckle → top mount
        local(c, -0.125 * s, 0.075, 0, B);
        // a deep frontal crush folds the strut tower back and down
        const ex = Math.max(0, c.T.z + 0.12 - (ZF - fc)), T = c.Tc || (c.Tc = new THREE.Vector3());
        T.set(c.T.x, c.T.y - Math.min(0.12, ex * 0.3), c.T.z - ex * 0.6);
        dir.subVectors(T, B); const len = dir.length(); dir.divideScalar(len);
        span(c.body, B, tmp.copy(B).addScaledVector(dir, Math.min(0.27, len - 0.06)), _Z);
        span(c.rod, tmp, T, _Z);
        span(c.bump, tmp, tmp2.copy(tmp).addScaledVector(dir, 0.05), _Z);
        const sLo = tmp2.copy(B).addScaledVector(dir, 0.17); span(c.seatLo, sLo, tmp.copy(sLo).addScaledVector(dir, 0.01), _Z, true);
        span(c.spring, tmp, tmp2.copy(T).addScaledVector(dir, -0.04), _Z);
        span(c.seatHi, tmp2, tmp.copy(tmp2).addScaledVector(dir, 0.012), _Z);
        span(c.mount, tmp, tmp2.copy(T).addScaledVector(dir, 0.02), _Z);
        // strut point for the drop link
        SA.copy(B).addScaledVector(dir, 0.11);
        // wishbone: from the bushes to the ball joint under the knuckle
        if (!broken) local(c, -0.10 * s, -0.13, 0, BJ);
        else { const bp = brokenPose[c.i]; BJ.set(c.W.x - 0.13 * s, Math.max(gy(0.04), C.y - bp.drop - 0.13), c.W.z + 0.04); }
        c.bj.position.copy(BJ);
        span(c.armF, c.P1, BJ, _Yv); span(c.armR, c.P2, tmp.copy(BJ).lerp(c.P1, 0.12), _Yv);
        span(c.bushF, tmp.copy(c.P1).add(tmp2.set(0, 0, -0.03)), tmp2.copy(c.P1).add(_up.set(0, 0, 0.03)), _Yv);
        span(c.bushR, tmp.copy(c.P2).add(tmp2.set(-0.03 * s, 0, 0)), tmp2.copy(c.P2).add(_up.set(0.03 * s, 0, 0)), _Yv);
        // tie rod: rack end → steering arm (dangles when the corner is torn off)
        const RE = tmp.set(0.30 * s + rackShift, RY, RZ);
        const inner = v3(0.355 * s + rackShift, RY, RZ);
        span(c.rackRod, RE, inner, _Yv); span(c.rackBoot, v3(0.30 * s, RY, RZ), tmp2.set(0.30 * s + 0.07 * s + rackShift * 0.5, RY, RZ), _Yv);
        if (!broken) local(c, -0.12 * s, -0.025, -0.15, tmp2); else tmp2.set(inner.x + 0.08 * s, gy(0.06), RZ - 0.18);
        span(c.tie, inner, tmp2, _Yv); c.tieEnd.position.copy(tmp2);
        // anti-roll bar end and drop link
        const zb = Math.min(ARB.z, ZF - fc - 0.08);
        c.arbEnd = v3(0.585 * s, ARB.y + 0.01, Math.min(c.W.z + 0.07, zb - 0.12));
        span(c.drop, c.arbEnd, SA, _Z);
        // brake fluid: badly bent corner seeps, torn-off corner pours
        const hit = sh['hit' + c.i] || 0;
        if (broken) leak(c.i, tmp.set(c.W.x * 0.86, gy(0.30), c.W.z - 0.05), 0.8);
        else if (st.dmg > 0.35 || hit) leak(c.i, tmp.set(c.W.x - 0.1 * s, C.y + 0.06, c.W.z - 0.12), Math.max(hit, clamp((st.dmg - 0.3) * 1.3, 0.1, 0.65)));
      }
      // anti-roll bar body (follows the front crush back)
      {
        const zb = Math.min(ARB.z, ZF - fc - 0.08), [l, r] = front[0].s > 0 ? front : [front[1], front[0]];
        const pts = [l.arbEnd, v3(0.53, ARB.y, zb - 0.04), v3(0.42, ARB.y, zb), v3(-0.42, ARB.y, zb), v3(-0.53, ARB.y, zb - 0.04), r.arbEnd];
        for (let k = 0; k < 5; k++) span(arbSegs[k], pts[k], pts[k + 1], _Yv);
        arbClamps[0].position.set(0.34, ARB.y + 0.01, zb); arbClamps[1].position.set(-0.34, ARB.y + 0.01, zb);
      }
      // ── rear: live axle located by lower + upper trailing arms, coil springs on pads, dampers behind the axle
      for (const c of rear) {
        const st = car.wheelState[c.i], wi = wis[c.i], s = c.s;
        const L = clamp(wi.suspensionLength, 0.02, 0.4);
        const yc = -0.1 - L, z = c.W.z;
        const zOff = Math.max(0, ZR + rc + 0.06 - c.damperTop.z);   // rear crush pushes the damper top forward
        const ax = (x, dy, dz) => tmp.set(x * s, yc + dy, z + dz);
        const lowA = ax(0.615, -0.085, 0).clone(), upA = ax(0.50, 0.085, 0.02).clone();
        span(c.lower, c.lowerP, lowA, _X); span(c.upper, c.upperP, upA, _X);
        span(c.bushL, tmp.copy(c.lowerP).add(tmp2.set(-0.03 * s, 0, 0)), tmp2.copy(c.lowerP).add(_up.set(0.03 * s, 0, 0)), _Yv);
        span(c.bushU, tmp.copy(c.upperP).add(tmp2.set(-0.03 * s, 0, 0)), tmp2.copy(c.upperP).add(_up.set(0.03 * s, 0, 0)), _Yv);
        c.brk.position.set(0.58 * s, yc, z); c.pad.position.set(0.555 * s, yc + 0.075, z + 0.02);
        const sb = v3(0.555 * s, yc + 0.09, z + 0.02);
        span(c.seatLo, sb, tmp.copy(sb).setY(sb.y + 0.01), _Z); span(c.spring, tmp, tmp2.copy(c.springTop), _Z);
        span(c.seatHi, tmp2, tmp.copy(tmp2).setY(tmp2.y + 0.015), _Z);
        // damper: lower eye on the axle bracket behind the tube; torn loose and hanging when the corner is gone
        const top = v3(c.damperTop.x, c.damperTop.y, c.damperTop.z + zOff);
        let eye = v3(0.615 * s, yc - 0.05, z - 0.13);
        if (st.broken) { if (!brokenPose[c.i]) brokenPose[c.i] = { a: rnd(0.3, 0.6) }; eye = v3(0.66 * s, top.y - 0.40, top.z - brokenPose[c.i].a * 0.3); }
        dir.subVectors(top, eye).normalize();
        span(c.dBody, eye, tmp.copy(eye).addScaledVector(dir, 0.24), _X); span(c.dRod, tmp, top, _X);
        span(c.dEye, tmp.copy(eye).add(tmp2.set(-0.025 * s, 0, 0)), tmp2.copy(eye).add(_up.set(0.025 * s, 0, 0)), _Yv);
        span(c.dTop, tmp.copy(top).add(tmp2.set(-0.025 * s, 0, 0)), tmp2.copy(top).add(_up.set(0.025 * s, 0, 0)), _Yv);
        const hit = sh['hit' + c.i] || 0;
        if (st.broken) leak(c.i, tmp.set(c.W.x * 0.82, yc + 0.02, z), 0.75);
        else if (st.dmg > 0.35 || hit) leak(c.i, tmp.set(c.W.x - 0.1 * s, yc + 0.06, z - 0.12), Math.max(hit, clamp((st.dmg - 0.3) * 1.3, 0.1, 0.65)));
      }
    },
    dispose() {
      root.traverse(o => o.geometry && o.geometry.dispose());
      if (sys.leaks) for (const L of leaks) { const j = L ? sys.leaks.indexOf(L) : -1; if (j >= 0) sys.leaks.splice(j, 1); }
    },
  };
}
