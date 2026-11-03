// Fluids and damage atmosphere: oil/coolant/fuel/brake leaks, falling drops, puddles on the ground,
// steam from a broken radiator, engine smoke, and (rarely) a fuel fire.
// OWNER: fluids agent. Interface: see SPEC.md §Car modules.
//
// car.sys keys:  reads  leaks, radiatorBroken, fuelTankBroken, engineShift (unused), tyreFlat (unused)
//                writes leaks (fallback entries tagged owner:'fluids', removed once a real entry of that kind exists),
//                       fire (0…1)
// Puddles and in-flight drops live in a per-scene shared pool (they outlive the car that made them).
import { THREE, CG, ZF, gy, rnd, clamp, canvasTex } from './common.js';

// ───────────────────────────── per-kind look and behaviour
const KIND = {
  //        drops/s at rate 1, m² per drop, max puddle radius, reservoir (m² of puddle), drop colour
  oil:     { dps: 9,  area: 0.0110, rMax: 1.20, cap: 3.5,  drop: 0x17120a },
  coolant: { dps: 14, area: 0.0160, rMax: 1.70, cap: 7.0,  drop: 0x6fd27c },
  fuel:    { dps: 12, area: 0.0120, rMax: 1.60, cap: 6.5,  drop: 0xd8cf9c },
  brake:   { dps: 3,  area: 0.0030, rMax: 0.32, cap: 0.16, drop: 0xc9a54a },
};
const KINDS = Object.keys(KIND);
const MAX_PUDDLES = 40, MAX_DROPS = 220, N_SHAPES = 10;

// ───────────────────────────── shared (per scene) pool: materials, puddle shapes, drops, puddles
const SHARED = new WeakMap();

function blobGeometry(seed) {
  // irregular flat puddle in XZ, unit size: fan with a soft outer ring (vertex alpha), uv = xz*0.5+0.5
  const R = (a, b) => { seed = (seed * 16807) % 2147483647; return a + (b - a) * (seed / 2147483647); };
  const N = 28, ph = [R(0, 6.3), R(0, 6.3), R(0, 6.3), R(0, 6.3)], am = [R(.10, .2), R(.06, .14), R(.04, .09), R(.02, .05)];
  const lobes = []; for (let i = 0, n = 1 + Math.floor(R(0, 3)); i < n; i++) lobes.push([R(0, 6.28), R(.25, .5), R(.2, .45)]);
  const rad = []; let mx = 0;
  for (let i = 0; i < N; i++) {
    const t = i / N * Math.PI * 2;
    let r = 1 + am[0] * Math.sin(2 * t + ph[0]) + am[1] * Math.sin(3 * t + ph[1]) + am[2] * Math.sin(5 * t + ph[2]) + am[3] * Math.sin(9 * t + ph[3]);
    for (const [c, w, h] of lobes) { let d = Math.abs(t - c); d = Math.min(d, Math.PI * 2 - d); if (d < w) r += h * (1 - d / w) * (1 - d / w); }
    r *= R(0.94, 1.06); rad.push(r); mx = Math.max(mx, r);
  }
  const pos = [0, 0, 0], col = [1, 1, 1, 1], idx = [];
  const ring = (k, a) => { for (let i = 0; i < N; i++) { const t = i / N * Math.PI * 2, r = rad[i] / mx * k; pos.push(Math.cos(t) * r, 0, Math.sin(t) * r); col.push(1, 1, 1, a); } };
  ring(0.55, 1); ring(0.86, 0.95); ring(1.0, 0.0);
  for (let i = 0; i < N; i++) {
    const j = (i + 1) % N; idx.push(0, 1 + j, 1 + i);
    for (let r = 0; r < 2; r++) { const a = 1 + r * N + i, b = 1 + r * N + j, c = 1 + (r + 1) * N + i, d = 1 + (r + 1) * N + j; idx.push(a, b, d, a, d, c); }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('normal', new THREE.Float32BufferAttribute(new Array(pos.length).fill(0).map((_, i) => (i % 3 === 1 ? 1 : 0)), 3));
  g.setAttribute('color', new THREE.Float32BufferAttribute(col, 4));
  const uv = []; for (let i = 0; i < pos.length; i += 3) uv.push(pos[i] * 0.5 + 0.5, pos[i + 2] * 0.5 + 0.5);
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  g.setIndex(idx); g.computeBoundingSphere(); return g;
}

function filmTexture() {
  // thin-film rainbow swirls for fuel (no text, just colour bands)
  return canvasTex(128, 128, (g, w, h) => {
    const im = g.createImageData(w, h); const f = []; for (let k = 0; k < 5; k++) f.push([rnd(2, 7), rnd(2, 7), rnd(0, 6.3), rnd(.5, 1.2)]);
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      const u = x / w, v = y / h; let s = 0; for (const [a, b, p, m] of f) s += Math.sin(u * a * 6.28 + Math.sin(v * b * 6.28 + p) * 1.6 + p) * m;
      const hue = (s * 0.22 + 0.5 + u * 0.3) % 1; const c = new THREE.Color().setHSL((hue + 1) % 1, 0.55, 0.62);
      const o = (y * w + x) * 4; im.data[o] = c.r * 255; im.data[o + 1] = c.g * 255; im.data[o + 2] = c.b * 255; im.data[o + 3] = 255;
    }
    g.putImageData(im, 0, 0);
  });
}

function getShared(scene) {
  let S = SHARED.get(scene); if (S) return S;
  const common = { transparent: true, depthWrite: false, vertexColors: true, polygonOffset: true, polygonOffsetFactor: -3, polygonOffsetUnits: -6, flatShading: false };
  const film = filmTexture();
  const mats = {
    oil: new THREE.MeshPhysicalMaterial(Object.assign({ color: 0x120e09, roughness: 0.07, metalness: 0.0, clearcoat: 1, clearcoatRoughness: 0.03, iridescence: 0.55, iridescenceIOR: 1.45, iridescenceThicknessRange: [250, 600], envMapIntensity: 2.0, opacity: 0.94 }, common)),
    coolant: new THREE.MeshPhysicalMaterial(Object.assign({ color: 0x3a9a50, roughness: 0.05, metalness: 0.0, envMapIntensity: 1.3, opacity: 0.5 }, common)),
    fuel: new THREE.MeshPhysicalMaterial(Object.assign({ color: 0xffffff, map: film, roughness: 0.04, metalness: 0.0, iridescence: 1, iridescenceIOR: 1.35, iridescenceThicknessRange: [180, 520], envMapIntensity: 1.4, opacity: 0.32 }, common)),
    brake: new THREE.MeshPhysicalMaterial(Object.assign({ color: 0xb49038, roughness: 0.08, metalness: 0.0, envMapIntensity: 1.2, opacity: 0.6 }, common)),
  };
  const shapes = []; for (let i = 0; i < N_SHAPES; i++) shapes.push(blobGeometry(1234 + i * 7919));
  // drops: one instanced mesh, elongated low-poly spheres, colour per instance
  const dGeo = new THREE.SphereGeometry(1, 5, 4);
  const dMesh = new THREE.InstancedMesh(dGeo, new THREE.MeshStandardMaterial({ roughness: 0.15, metalness: 0.1, flatShading: true }), MAX_DROPS);
  dMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage); dMesh.frustumCulled = false; dMesh.castShadow = false; dMesh.count = 0;
  const kc = {}; for (const k of KINDS) kc[k] = new THREE.Color(KIND[k].drop);
  for (let i = 0; i < MAX_DROPS; i++) dMesh.setColorAt(i, kc.oil);
  scene.add(dMesh);
  S = {
    scene, mats, shapes, dMesh, kc, t: -1, users: 0,
    drops: [],            // {p:Vector3, v:Vector3, kind, area, owner}
    puddles: [],          // {mesh, kind, x, z, area, r, rShown, dir, sx, sz, born, last, fade, base}
  };
  SHARED.set(scene, S); return S;
}

const _m = new THREE.Matrix4(), _q = new THREE.Quaternion(), _v = new THREE.Vector3(), _s = new THREE.Vector3(), _up = new THREE.Vector3(0, 1, 0);

function addPuddle(S, kind, x, z, area, toward, stretch) {
  let p;
  if (S.puddles.length >= MAX_PUDDLES) { // recycle the oldest / most faded one
    let bi = 0, bs = Infinity; S.puddles.forEach((q, i) => { const s = q.last - q.fade * 1000; if (s < bs) { bs = s; bi = i; } });
    p = S.puddles.splice(bi, 1)[0]; S.scene.remove(p.mesh); p.mesh.material.dispose();
  }
  const mat = S.mats[kind].clone();
  const mesh = new THREE.Mesh(S.shapes[Math.floor(Math.random() * N_SHAPES)], mat);
  mesh.renderOrder = 2; mesh.receiveShadow = true; mesh.castShadow = false; mesh.matrixAutoUpdate = true;
  const dir = toward != null ? toward : rnd(0, Math.PI * 2);
  p = { mesh, kind, x, z, area, r: 0, rShown: 0.02, dir, sx: stretch || 1, sz: Math.random() < 0.5 ? 1 : -1, born: S.t, last: S.t, fade: 0, base: mat.opacity };
  mesh.position.set(x, 0.006 + (S.puddles.length % 20) * 0.0002, z); mesh.rotation.y = Math.atan2(-Math.sin(dir), Math.cos(dir));
  S.scene.add(mesh); S.puddles.push(p); return p;
}

function landDrop(S, d, carGround) {
  const k = KIND[d.kind]; const hs = Math.hypot(d.v.x, d.v.z);
  if (hs > 1.6) { // moving car: elongated spot on the road, a trail
    for (const p of S.puddles) if (p.kind === d.kind && S.t - p.born < 0.6 && Math.hypot(p.x - d.p.x, p.z - d.p.z) < 0.18) { p.area += d.area * 0.5; p.last = S.t; return; }
    const p = addPuddle(S, d.kind, d.p.x, d.p.z, d.area * 2.2 + 0.004, Math.atan2(d.v.z, d.v.x), clamp(1 + hs * 0.25, 1, 2.6));
    p.trail = true; return;
  }
  let best = null, bd = Infinity;
  for (const p of S.puddles) { if (p.kind !== d.kind || p.trail) continue; const dd = Math.hypot(p.x - d.p.x, p.z - d.p.z); if (dd < Math.max(0.22, p.rShown * 0.85) && dd < bd) { bd = dd; best = p; } }
  if (best) { best.area += d.area * Math.max(0.05, 1 - (best.r / k.rMax) ** 2); best.last = S.t; best.fade = Math.max(0, best.fade - 0.02); return; }
  const toward = carGround ? Math.atan2(carGround.z - d.p.z, carGround.x - d.p.x) : null;
  addPuddle(S, d.kind, d.p.x + rnd(-0.04, 0.04), d.p.z + rnd(-0.04, 0.04), d.area * rnd(1, 3.5), toward, 1);
}

function tickShared(S, now, carGround) {
  if (now <= S.t) return; const dt = S.t < 0 ? 0 : Math.min(0.1, now - S.t); S.t = now;
  // drops
  let n = 0; const D = S.drops;
  for (let i = D.length - 1; i >= 0; i--) {
    const d = D[i]; d.v.y -= 9.8 * dt; d.p.addScaledVector(d.v, dt);
    if (d.p.y <= 0.01) { d.p.y = 0.01; landDrop(S, d, d.carGround); D.splice(i, 1); }
  }
  for (const d of D) {
    if (n >= MAX_DROPS) break;
    const sp = d.v.length(); const st = clamp(1 + sp * 0.35, 1, 3.2);
    if (sp > 0.01) _q.setFromUnitVectors(_up, _v.copy(d.v).multiplyScalar(-1 / sp)); else _q.identity();
    _m.compose(d.p, _q, _s.set(0.009, 0.011 * st, 0.009)); S.dMesh.setMatrixAt(n, _m); S.dMesh.setColorAt(n, S.kc[d.kind]); n++;
  }
  S.dMesh.count = n; S.dMesh.instanceMatrix.needsUpdate = true; if (S.dMesh.instanceColor) S.dMesh.instanceColor.needsUpdate = true;
  // puddles: spread towards their target size, drift toward the car, fade when old
  for (const p of S.puddles) {
    const k = KIND[p.kind];
    p.r = Math.min(k.rMax * (p.trail ? 0.4 : 1), Math.sqrt(p.area / Math.PI));
    const dr = (p.r - p.rShown) * (1 - Math.exp(-dt * 1.4));
    if (dr > 0) {
      p.rShown += dr;
      if (!p.trail) { // fluid runs toward where the car stands (under it), the blob stretches that way
        p.x += Math.cos(p.dir) * dr * 0.15; p.z += Math.sin(p.dir) * dr * 0.15;
        p.sx = Math.min(1.3, p.sx + dr * 0.35);
      }
    }
    const age = S.t - p.last;
    if (age > 45) p.fade = Math.min(0.85, p.fade + dt / 240);       // old puddles slowly go pale (soak in / dry out)
    p.mesh.material.opacity = p.base * (1 - p.fade);
    p.mesh.position.x = p.x; p.mesh.position.z = p.z;
    p.mesh.scale.set(p.rShown * p.sx, 1, p.rShown * p.sz);
  }
  // fuel puddles shimmer a little (texture drift)
  const fm = S.mats.fuel.map; if (fm) { fm.offset.x = (S.t * 0.004) % 1; }
}

// ───────────────────────────── flames (one instanced cluster per car)
function flameMaterial() {
  return new THREE.ShaderMaterial({
    uniforms: { time: { value: 0 }, power: { value: 0 } }, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    side: THREE.DoubleSide, toneMapped: false, fog: false,
    vertexShader: `uniform float time; varying float vH; varying float vS;
      void main(){ vec3 p=position; float h=clamp(p.y,0.,1.); vH=h;
        vec4 w=vec4(p,1.);
        #ifdef USE_INSTANCING
          vec2 sd=instanceMatrix[3].xz*7.13; vS=fract(sin(dot(sd,vec2(12.9898,78.233)))*43758.55);
          w=instanceMatrix*w;
        #else
          vS=0.5;
        #endif
        float ph=time*(7.0+vS*5.0)+vS*40.0;
        w.x+=sin(ph+h*5.0)*0.07*h*h; w.z+=cos(ph*1.3+h*4.0)*0.06*h*h;
        w.y+=sin(ph*0.7)*0.03*h;
        gl_Position=projectionMatrix*viewMatrix*w; }`,
    fragmentShader: `uniform float power; varying float vH; varying float vS;
      void main(){ float h=vH;
        vec3 c=mix(vec3(1.0,0.78,0.32),vec3(1.0,0.36,0.04),smoothstep(0.0,0.4,h));
        c=mix(c,vec3(0.6,0.07,0.01),smoothstep(0.5,0.95,h));
        float a=(1.0-smoothstep(0.45,1.0,h))*(0.5+0.25*vS)*power;
        gl_FragColor=vec4(c*a,a); }`,
  });
}

// ───────────────────────────── the module
export function createFluids(ctx) {
  const car = ctx.car, sys = ctx.sys || (car.sys = car.sys || {}), scene = ctx.scene;
  if (!Array.isArray(sys.leaks)) sys.leaks = [];
  sys.fire = 0;
  const S = getShared(scene); S.users++;
  const w = new THREE.Vector3(), w2 = new THREE.Vector3(), vel = { x: 0, y: 0, z: 0 };
  const carGround = { x: 0, z: 0 };
  const emitted = { oil: 0, coolant: 0, fuel: 0, brake: 0 };   // m² of puddle released per kind (reservoirs)
  const acc = new Map();                                        // leak → fractional drops
  let smokeT = 0, steamT = 0, fireSmokeT = 0, lastImpactT = -99, impactK = 0, steamHeat = 0, lastScrapeT = -99, scrapeRolled = false;
  let fire = 0, fireFuel = 0, fireOn = false, fireT = 0;
  const fireAt = new THREE.Vector3(0, gy(0.25), -1.0);          // chassis frame, updated to the fuel leak

  // flames: instanced cones, base at y=0, height 1
  const FL = 16;
  const fGeo = new THREE.ConeGeometry(0.5, 1, 6, 4, true); fGeo.translate(0, 0.5, 0);
  const fMat = flameMaterial();
  const flames = new THREE.InstancedMesh(fGeo, fMat, FL); flames.frustumCulled = false; flames.count = 0; flames.renderOrder = 5;
  scene.add(flames);
  // burning pool under the car: low flames beneath the floor, tall tongues where it escapes at the sills
  const fSeed = []; for (let i = 0; i < FL; i++) {
    const inner = i >= FL - 4, side = i % 2 ? 1 : -1, ox = inner ? rnd(-0.5, 0.5) : side * rnd(0.7, 1.25);
    fSeed.push({ ox, oz: rnd(-0.75, 0.75), r: rnd(0.24, 0.4), h: Math.abs(ox) > 0.85 ? rnd(0.75, 1.35) : rnd(0.18, 0.3), ph: rnd(0, 6.3), sp: rnd(6, 11) });
  }
  const light = new THREE.PointLight(0xff7a2e, 0, 8, 2); light.castShadow = false; scene.add(light);

  const hoodGone = () => { const h = car.parts && car.parts.find(p => p.name === 'hood'); return !!(h && h.gone); };
  const real = k => sys.leaks.some(l => l.kind === k && l.owner !== 'fluids');
  const mine = k => sys.leaks.find(l => l.kind === k && l.owner === 'fluids');
  function fallback(k, x, h, z, rate) {
    if (real(k)) return; const m = mine(k);
    if (m) { m.rate = Math.max(m.rate, rate); return; }
    sys.leaks.push({ kind: k, at: new THREE.Vector3(x, gy(h), z), rate, owner: 'fluids' });
  }
  function hasFuelLeak() { return sys.fuelTankBroken || sys.leaks.some(l => l.kind === 'fuel' && l.rate > 0.02); }
  function ignite(chance) {
    if (fireOn || !hasFuelLeak() || Math.random() > chance) return;
    const f = sys.leaks.find(l => l.kind === 'fuel'); if (f) fireAt.copy(f.at);
    fireOn = true; fireT = 0; fireFuel = rnd(16, 26);
  }

  return {
    onImpact(ev) {
      const now = ctx.time();
      if (ev.scrape) {
        if (now - lastScrapeT > 1.5) scrapeRolled = false; lastScrapeT = now;
        if (!scrapeRolled && hasFuelLeak()) { scrapeRolled = true; ignite(0.25); }   // sparks from scraping + fuel → 25 %
        return;
      }
      const k = clamp((ev.v - 4) / 20, 0, 1) * clamp(ev.depth / 0.4, 0.3, 1);
      if (k > 0.05) { lastImpactT = now; impactK = Math.max(impactK * 0.5, k); }
      // fallback leak points until the owners' modules publish their own (SPEC: sys.leaks)
      if (car.frontCrush > 0.25) {
        fallback('oil', 0, 0.25, 1.35, clamp(0.4 + car.frontCrush, 0, 1));
        fallback('coolant', 0.1, 0.42, 1.95, clamp(0.5 + car.frontCrush, 0, 1));
      }
      if (car.rearCrush > 0.4 || sys.fuelTankBroken) fallback('fuel', 0.25, 0.22, -1.0, 0.8);
      // a hard hit (>60 km/h) with fuel leaking: about half the time it lights up
      if (ev.v * 3.6 > 60) ignite(0.5);
    },

    update(dt) {
      if (!(dt > 0)) return;
      const now = ctx.time(); const b = car.body; const G = ctx.group;
      G.updateMatrixWorld();
      carGround.x = b.position.x; carGround.z = b.position.z;
      vel.x = b.velocity.x; vel.y = b.velocity.y; vel.z = b.velocity.z;

      // ── leaks: tidy fallback entries, emit drops
      for (let i = sys.leaks.length - 1; i >= 0; i--) {
        const l = sys.leaks[i];
        if (l.owner === 'fluids') { if (real(l.kind)) { sys.leaks.splice(i, 1); acc.delete(l); continue; } l.rate *= Math.exp(-dt / 50); }
      }
      // front fallback points ride back with the crushed nose
      for (const l of sys.leaks) if (l.owner === 'fluids' && l.kind !== 'fuel') l.at.z = Math.min(l.kind === 'oil' ? 1.35 : 1.95, ZF - car.frontCrush - 0.12);
      for (const l of sys.leaks) {
        const K = KIND[l.kind]; if (!K || !l.at) continue;
        const left = 1 - emitted[l.kind] / K.cap; if (left <= 0) continue;
        const boost = 1 + 2.5 * Math.exp(-(now - lastImpactT) / 2.5) * impactK;    // gush right after a hit
        const rate = clamp(+l.rate || 0, 0, 1) * Math.min(1, left * 4) * boost;
        let a = (acc.get(l) || 0) + rate * K.dps * dt;
        while (a >= 1) {
          a -= 1;
          w.set(l.at.x + rnd(-0.02, 0.02), l.at.y, l.at.z + rnd(-0.02, 0.02)); G.localToWorld(w);
          if (w.y < 0.02) w.y = 0.02;
          if (S.drops.length < MAX_DROPS) {
            const inh = now - lastImpactT < 0.6 ? 0.1 : 1;
            const ar = K.area * rnd(0.7, 1.3); emitted[l.kind] += ar;
            S.drops.push({ p: w.clone(), v: new THREE.Vector3(vel.x * inh + rnd(-0.05, 0.05), Math.min(vel.y, 0) * inh - rnd(0, 0.2), vel.z * inh + rnd(-0.05, 0.05)), kind: l.kind, area: ar, carGround: { x: carGround.x, z: carGround.z } });
          }
        }
        acc.set(l, a);
      }
      tickShared(S, now, carGround);

      const sinceHit = now - lastImpactT, hood = hoodGone();
      const zNose = ZF - car.frontCrush;
      // ── steam from a broken radiator: dense white right after the hit, then wisps
      const steamy = sys.radiatorBroken || car.frontCrush > 0.35;
      if (steamy) {
        steamHeat = Math.max(steamHeat, 1);
        const burst = Math.exp(-Math.max(0, sinceHit) / 5);
        const rate = (10 + 40 * burst) * clamp(steamHeat, 0, 1) * (emitted.coolant / KIND.coolant.cap < 0.98 ? 1 : 0.35);
        steamHeat = Math.max(0.15, steamHeat - dt / 90);
        steamT += dt * rate;
        while (steamT > 1) {
          steamT -= 1; const r = Math.random();
          if (r < 0.45) w.set(rnd(-0.45, 0.45), gy(rnd(0.45, 0.7)), zNose - 0.05);                      // through the grille
          else if (r < 0.8 || hood) w.set(rnd(-0.5, 0.5), gy(hood ? 0.85 : 0.93), rnd(Math.max(1.1, zNose - 0.9), zNose - 0.15)); // hood gaps / open bay
          else w.set(rnd(-0.3, 0.3), gy(0.2), zNose - rnd(0.2, 0.5));                                   // under the bumper
          G.localToWorld(w);
          ctx.fx.puff(w, { x: vel.x * 0.4 + rnd(-.25, .25), y: rnd(0.5, 1.2) * (0.7 + burst * 0.5), z: vel.z * 0.4 + rnd(-.25, .25) },
            { life: rnd(1.6, 2.8), s0: 0.25, s1: rnd(1.2, 2.0), a: 0.2 + 0.3 * burst, c: 0.97 });
        }
      }
      // ── engine smoke by health: grey → black below 0.2, denser and higher with the hood gone
      if (car.engine < 0.65) {
        const dark = car.engine < 0.2, dmg = 1 - car.engine;
        smokeT += dt * dmg * (hood ? 26 : 16);
        while (smokeT > 1) {
          smokeT -= 1;
          if (hood) w.set(rnd(-0.4, 0.4), gy(0.8), rnd(1.15, Math.max(1.2, zNose - 0.3)));
          else if (Math.random() < 0.6) w.set(rnd(-0.6, 0.6), gy(0.93), rnd(0.98, 1.15));           // hood/windscreen gap
          else w.set(rnd(-0.75, 0.75), gy(0.86), rnd(1.2, Math.max(1.25, zNose - 0.3)));             // hood/wing seams
          G.localToWorld(w); const c = dark ? 0.12 + rnd(0, 0.06) : lerpN(0.62, 0.38, (0.65 - car.engine) / 0.45);
          ctx.fx.puff(w, { x: vel.x * 0.4 + rnd(-.25, .25), y: rnd(.35, .8) * (hood ? 1.4 : 1), z: vel.z * 0.4 + rnd(-.25, .25) },
            { life: rnd(3, 5) * (hood ? 1.2 : 1), s0: 0.3, s1: rnd(1.8, 2.8) * (hood ? 1.25 : 1), a: dark ? 0.5 : 0.3, c });
        }
      }

      // ── fire
      if (fireOn) {
        fireT += dt;
        const target = fireT < fireFuel ? 1 : 0; fire += (target - fire) * (1 - Math.exp(-dt / (target ? 1.2 : 5)));
        if (fireT > fireFuel && fire < 0.02) { fireOn = false; fire = 0; }
      }
      sys.fire = fire;
      fMat.uniforms.time.value = now; fMat.uniforms.power.value = clamp(fire * 1.2, 0, 1);
      if (fire > 0.01) {
        w2.copy(fireAt); G.localToWorld(w2);
        const gx = w2.x, gz = w2.z;
        let n = 0;
        for (const s of fSeed) {
          const fl = 0.75 + 0.25 * Math.sin(now * s.sp + s.ph) + 0.1 * Math.sin(now * s.sp * 2.3 + s.ph * 3);
          const sc = fire * fl;
          const spread = 0.35 + 0.65 * Math.min(1, fireT / 4);
          w.set(s.ox * spread, 0, s.oz * spread).applyQuaternion(G.quaternion);
          _m.compose(_v.set(gx + w.x, 0.01, gz + w.z), _q.identity(), _s.set(s.r * sc, s.h * sc, s.r * sc));
          flames.setMatrixAt(n++, _m);
        }
        flames.count = n; flames.instanceMatrix.needsUpdate = true;
        light.position.set(gx, 0.3, gz);
        light.intensity = fire * (2.4 + 0.7 * Math.sin(now * 17) + 0.5 * Math.sin(now * 29.3));
        fireSmokeT += dt * fire * 22;
        while (fireSmokeT > 1) {
          fireSmokeT -= 1; const sd = Math.random() < 0.5 ? 1 : -1; w.set(sd * rnd(0.8, 1.1), 0, rnd(-0.6, 0.6)).applyQuaternion(G.quaternion); w.x += gx; w.z += gz; w.y = 0.6 + fire * 0.5;
          ctx.fx.puff(w, { x: rnd(-.3, .3), y: rnd(0.9, 1.7), z: rnd(-.3, .3) }, { life: rnd(3.5, 5.5), s0: 0.45, s1: rnd(2.6, 3.8), a: 0.55, c: 0.06 });
        }
        if (Math.random() < dt * 6 * fire) ctx.fx.spark({ x: gx + rnd(-.3, .3), y: 0.3, z: gz + rnd(-.3, .3) }, { x: rnd(-.6, .6), y: rnd(2, 4), z: rnd(-.6, .6) });
      } else { flames.count = 0; light.intensity = 0; }
    },

    dispose() {
      // puddles stay in the world; drops of this car in flight are dropped, fire and light go
      scene.remove(flames); scene.remove(light); fGeo.dispose(); fMat.dispose(); light.dispose && light.dispose();
      S.users = Math.max(0, S.users - 1);
      if (S.users === 0) { S.drops.length = 0; S.dMesh.count = 0; }
      sys.fire = 0;
    },
  };
}
const lerpN = (a, b, t) => a + (b - a) * clamp(t, 0, 1);
