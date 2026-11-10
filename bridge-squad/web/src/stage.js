import * as THREE from 'three';
import { Crowd } from './assets.js';

// Separate "stage" scenes for the menu, victory and defeat screens: a lit diorama with its own
// camera, lights and props, unrelated to the gameplay bridge.

const rand = (a, b) => a + Math.random() * (b - a);

function gradientTex(stops) {
  const c = document.createElement('canvas'); c.width = 4; c.height = 512;
  const g = c.getContext('2d'), gr = g.createLinearGradient(0, 0, 0, 512);
  stops.forEach(([p, col]) => gr.addColorStop(p, col));
  g.fillStyle = gr; g.fillRect(0, 0, 4, 512);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}
function radialTex(inner, outer) {
  const c = document.createElement('canvas'); c.width = c.height = 512;
  const g = c.getContext('2d'), gr = g.createRadialGradient(256, 256, 0, 256, 256, 256);
  gr.addColorStop(0, inner); gr.addColorStop(0.55, inner); gr.addColorStop(1, outer);
  g.fillStyle = gr; g.fillRect(0, 0, 512, 512);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}
function hazardTex() {
  const c = document.createElement('canvas'); c.width = 512; c.height = 32;
  const g = c.getContext('2d');
  g.fillStyle = '#ffcc00'; g.fillRect(0, 0, 512, 32);
  g.fillStyle = '#14161a';
  for (let x = -32; x < 544; x += 32) { g.beginPath(); g.moveTo(x, 32); g.lineTo(x + 16, 32); g.lineTo(x + 32, 0); g.lineTo(x + 16, 0); g.closePath(); g.fill(); }
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.wrapS = THREE.RepeatWrapping; t.repeat.set(6, 1); return t;
}
function flagTex(color, emblem) {
  const c = document.createElement('canvas'); c.width = 256; c.height = 160;
  const g = c.getContext('2d');
  g.fillStyle = color; g.fillRect(0, 0, 256, 160);
  g.fillStyle = 'rgba(0,0,0,.18)'; g.fillRect(0, 128, 256, 32);
  g.fillStyle = '#ffffff';
  if (emblem === 'star') {
    g.beginPath();
    for (let i = 0; i < 10; i++) { const r = i % 2 ? 22 : 54, a = -Math.PI / 2 + i * Math.PI / 5; g.lineTo(128 + r * Math.cos(a), 72 + r * Math.sin(a)); }
    g.closePath(); g.fill();
  } else {
    g.beginPath(); g.arc(128, 66, 38, 0, Math.PI * 2); g.fill();
    g.fillStyle = color; g.beginPath(); g.arc(115, 60, 9, 0, Math.PI * 2); g.arc(141, 60, 9, 0, Math.PI * 2); g.fill();
    g.fillStyle = '#ffffff'; g.fillRect(104, 98, 48, 14);
  }
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}

export class Stage {
  constructor(renderer, M, blueParts, redParts) {
    this.renderer = renderer;
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(36, 1, 0.1, 200);
    this.t = 0;
    this.mode = null;
    const s = this.scene;

    this.bg = {
      menu: gradientTex([[0, '#16233b'], [0.4, '#2f4466'], [0.72, '#c9774a'], [1, '#f6b878']]),
      win: gradientTex([[0, '#10203a'], [0.5, '#2c5a8f'], [0.82, '#f5c25a'], [1, '#ffe7a6']]),
      lose: gradientTex([[0, '#07080b'], [0.55, '#2a0d10'], [0.85, '#6e1714'], [1, '#a3301f']]),
    };
    s.fog = new THREE.Fog(0x22324d, 14, 34);

    // ground: soft round floor that fades into the backdrop
    this.floorMat = new THREE.MeshStandardMaterial({ map: radialTex('#3a3f38', '#22324d'), roughness: 0.95 });
    const floor = new THREE.Mesh(new THREE.CircleGeometry(30, 64), this.floorMat);
    floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true; s.add(floor);

    // pedestal: octagonal steel drum with a hazard band
    const ped = new THREE.Group();
    const steel = new THREE.MeshStandardMaterial({ color: 0x2b313b, roughness: 0.55, metalness: 0.4 });
    const top = new THREE.MeshStandardMaterial({ color: 0x3a4250, roughness: 0.7, metalness: 0.2 });
    const drum = new THREE.Mesh(new THREE.CylinderGeometry(2.6, 2.75, 0.45, 8), steel);
    drum.position.y = 0.225; drum.castShadow = drum.receiveShadow = true; ped.add(drum);
    const plate = new THREE.Mesh(new THREE.CylinderGeometry(2.45, 2.45, 0.06, 8), top);
    plate.position.y = 0.48; plate.receiveShadow = true; ped.add(plate);
    const band = new THREE.Mesh(new THREE.CylinderGeometry(2.77, 2.77, 0.14, 8, 1, true), new THREE.MeshStandardMaterial({ map: hazardTex(), roughness: 0.6 }));
    band.position.y = 0.2; ped.add(band);
    this.pedTop = 0.51;
    s.add(ped);

    // props around the pedestal
    this.props = new THREE.Group(); s.add(this.props);
    const place = (src, x, z, ry, sc) => { const o = src.clone(true); o.position.set(x, 0, z); o.rotation.y = ry; o.scale.setScalar(sc); this.props.add(o); return o; };
    place(M.crate, -4.4, -2.2, 0.5, 1.0);
    place(M.tires, 4.3, -2.6, -0.3, 0.9);
    place(M.crate, 5.6, 0.8, -1.1, 0.7);
    place(M.tires, -5.8, 0.6, 0.8, 0.7);

    // flag pole + cloth
    this.flag = new THREE.Group();
    const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.06, 5.4, 10), new THREE.MeshStandardMaterial({ color: 0xc9ced6, metalness: 0.7, roughness: 0.3 }));
    pole.position.y = 2.7; pole.castShadow = true; this.flag.add(pole);
    const knob = new THREE.Mesh(new THREE.SphereGeometry(0.11, 12, 8), new THREE.MeshStandardMaterial({ color: 0xffcc00, metalness: 0.6, roughness: 0.3 }));
    knob.position.y = 5.45; this.flag.add(knob);
    this.clothGeo = new THREE.PlaneGeometry(1.9, 1.2, 20, 10);
    this.clothGeo.translate(0.95, 0, 0);
    this.clothBase = this.clothGeo.attributes.position.array.slice();
    this.flagTex = { blue: flagTex('#2f6fe8', 'star'), red: flagTex('#c42a22', 'skull') };
    this.clothMat = new THREE.MeshStandardMaterial({ map: this.flagTex.blue, side: THREE.DoubleSide, roughness: 0.8 });
    const cloth = new THREE.Mesh(this.clothGeo, this.clothMat);
    cloth.position.set(0.06, 4.7, 0); cloth.castShadow = true; this.flag.add(cloth);
    this.flag.position.set(2.1, this.pedTop, -1.7);
    s.add(this.flag);

    // lights
    this.hemi = new THREE.HemisphereLight(0x9fb4d9, 0x2a2420, 0.9); s.add(this.hemi);
    this.key = new THREE.DirectionalLight(0xffc48a, 3.0);
    this.key.position.set(5, 9, 6); this.key.castShadow = true;
    this.key.shadow.mapSize.set(1024, 1024);
    Object.assign(this.key.shadow.camera, { left: -8, right: 8, top: 8, bottom: -8, near: 1, far: 30 });
    this.key.shadow.bias = -0.0005; this.key.shadow.normalBias = 0.02;
    s.add(this.key);
    this.rim = new THREE.DirectionalLight(0x6fa8ff, 2.2); this.rim.position.set(-6, 5, -7); s.add(this.rim);
    this.spot = new THREE.SpotLight(0xffffff, 60, 18, 0.5, 0.6, 1.6);
    this.spot.position.set(0, 9, 3); this.spot.target.position.set(0, 0.5, 0); s.add(this.spot, this.spot.target);

    // characters
    this.blue = new Crowd(s, blueParts, 24);
    this.red = new Crowd(s, redParts, 12);
    this.boss = M.boss.clone(true);
    this.boss.visible = false; s.add(this.boss);
    this.bossLegs = [];
    this.boss.traverse(o => { if (/leg/i.test(o.name) && !o.isMesh) this.bossLegs.push(o); });
    this.squad = []; this.foes = [];

    // confetti
    this.conf = [];
    const cm = new THREE.MeshBasicMaterial({ side: THREE.DoubleSide, toneMapped: false });
    this.confMesh = new THREE.InstancedMesh(new THREE.PlaneGeometry(0.14, 0.08), cm, 220);
    const col = new THREE.Color();
    const palette = [0xffcc00, 0x3d86ff, 0xffffff, 0x4ade80, 0xff5a4a];
    for (let i = 0; i < 220; i++) {
      this.confMesh.setColorAt(i, col.set(palette[i % palette.length]));
      this.conf.push({ x: 0, y: -10, z: 0, vy: 0, rx: rand(0, 6), ry: rand(0, 6), sx: rand(-6, 6), sy: rand(-6, 6), sway: rand(0, 6) });
    }
    this.confMesh.frustumCulled = false; this.confMesh.visible = false; s.add(this.confMesh);

    // drifting dust / embers
    const n = 160, pos = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) { pos[i * 3] = rand(-9, 9); pos[i * 3 + 1] = rand(0, 7); pos[i * 3 + 2] = rand(-8, 4); }
    const pg = new THREE.BufferGeometry(); pg.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    this.dustMat = new THREE.PointsMaterial({ color: 0xffd9a0, size: 0.06, transparent: true, opacity: 0.7, depthWrite: false });
    this.dust = new THREE.Points(pg, this.dustMat); s.add(this.dust);

    this._m = new THREE.Matrix4(); this._q = new THREE.Quaternion(); this._e = new THREE.Euler(); this._v = new THREE.Vector3(); this._s = new THREE.Vector3();
  }

  setMode(mode, opts = {}) {
    this.mode = mode; this.t = 0;
    this.applyShift();
    const s = this.scene;
    s.background = this.bg[mode];
    const lose = mode === 'lose', win = mode === 'win';
    s.fog.color.set(lose ? 0x2a0d10 : win ? 0x2c5a8f : 0x22324d);
    this.floorMat.map.dispose();
    this.floorMat.map = radialTex(lose ? '#2a2224' : '#3a3f38', lose ? '#2a0d10' : win ? '#2c5a8f' : '#22324d');
    this.floorMat.needsUpdate = true;
    this.key.color.set(lose ? 0xff5a3c : win ? 0xffe0a0 : 0xffc48a);
    this.key.intensity = lose ? 3.2 : 3.4;
    this.rim.color.set(lose ? 0xff2a1a : 0x6fa8ff);
    this.hemi.intensity = lose ? 0.9 : 1.2;
    this.spot.color.set(lose ? 0xff6050 : 0xffffff);
    this.dustMat.color.set(lose ? 0xff7050 : 0xffd9a0);
    this.clothMat.map = lose ? this.flagTex.red : this.flagTex.blue; this.clothMat.needsUpdate = true;
    this.confMesh.visible = win;

    // who stands on the pedestal
    this.squad = []; this.foes = [];
    const top = this.pedTop;
    if (mode === 'menu' || mode === 'win') {
      const n = Math.max(1, Math.min(mode === 'win' ? 15 : 9, opts.count || 1));
      // arrowhead formation, leader in front
      const slots = [[0, 0.9]];
      for (let row = 1; slots.length < n; row++) for (const side of [-1, 1]) if (slots.length < n) slots.push([side * row * 0.75, 0.9 - row * 0.62]);
      for (let i = 0; i < 4 && slots.length < n; i++) for (let k = 0; k < 3 && slots.length < n; k++) slots.push([(k - 1) * 0.7, -1.2 - i * 0.6]);
      slots.forEach(([x, z], i) => this.squad.push({ x, y: top, z, bx: x, bz: z, rot: 0, run: false, ph: rand(0, 6), s: i === 0 ? 1.25 : 1, i }));
      this.boss.visible = false;
    } else {
      this.boss.visible = true;
      this.boss.position.set(0, top, -0.6); this.boss.rotation.set(0, 0, 0); this.boss.scale.setScalar(0.62);
      [[-1.6, 0.9], [1.6, 0.9], [-0.8, 1.6], [0.8, 1.6], [-2.1, -0.2], [2.1, -0.2]].forEach(([x, z]) =>
        this.foes.push({ x, y: top, z, bx: x, bz: z, rot: 0, run: false, ph: rand(0, 6), s: 1 }));
      // a dropped blue helmet in front of the pedestal is told by a lone fallen soldier
      this.squad.push({ x: 0.4, y: 0.12, z: 3.3, rot: 2.2, rz: Math.PI / 2, run: false, s: 1 });
    }
    for (const c of this.conf) { c.x = rand(-4, 4); c.y = rand(4, 12); c.z = rand(-3, 3); c.vy = rand(1.2, 2.4); }
  }

  resize(w, h) {
    this.w = w; this.h = h;
    this.camera.aspect = w / h;
    // keep the pedestal (≈6 m wide) in frame on narrow phones
    const want = 2 * Math.atan(Math.tan(THREE.MathUtils.degToRad(22)) / this.camera.aspect);
    this.camera.fov = THREE.MathUtils.clamp(THREE.MathUtils.radToDeg(want), 34, 72);
    this.applyShift();
  }
  // win/lose put the result panel over the lower half, so the diorama is framed in the upper part
  applyShift() {
    if (!this.w) return;
    const shift = this.mode === 'menu' ? 0.06 : 0.25;
    this.camera.setViewOffset(this.w, this.h, 0, this.h * shift, this.w, this.h);
    this.camera.updateProjectionMatrix();
  }

  update(dt) {
    this.t += dt; const t = this.t;
    const mode = this.mode;
    // camera: slow orbit; framed a bit low so the title sits above the squad
    const orbit = Math.sin(t * 0.18) * 0.32 + (mode === 'lose' ? 0.25 : 0);
    const dist = mode === 'lose' ? 10.5 : 9.6;
    const camY = mode === 'lose' ? 2.6 : 3.1;
    this.camera.position.set(Math.sin(orbit) * dist, camY, Math.cos(orbit) * dist);
    this.camera.lookAt(0, mode === 'lose' ? 2.0 : 1.45, 0);

    // flag wave
    const p = this.clothGeo.attributes.position, b = this.clothBase;
    const wind = mode === 'lose' ? 1.6 : 3.2;
    for (let i = 0; i < p.count; i++) {
      const x = b[i * 3], y = b[i * 3 + 1];
      p.array[i * 3 + 2] = Math.sin(x * 3.2 - t * wind + y * 0.8) * 0.16 * x;
      p.array[i * 3 + 1] = y - (mode === 'lose' ? x * 0.18 : 0);
    }
    p.needsUpdate = true; this.clothGeo.computeVertexNormals();

    // squad idle / cheer
    for (const u of this.squad) {
      if (u.rz) continue;
      if (mode === 'win') {
        const hop = Math.max(0, Math.sin(t * 7 + u.ph));
        u.y = this.pedTop + hop * 0.35; u.run = hop > 0.2; u.rot = Math.sin(t * 2 + u.ph) * 0.25;
      } else {
        u.y = this.pedTop + Math.abs(Math.sin(t * 2 + u.ph)) * 0.015;
        u.rot = Math.sin(t * 0.7 + u.ph) * 0.12; u.run = false;
      }
    }
    for (const e of this.foes) { e.rot = Math.sin(t * 0.9 + e.ph) * 0.2; e.y = this.pedTop + Math.abs(Math.sin(t * 2.4 + e.ph)) * 0.02; }
    this.blue.update(this.squad, t);
    this.red.update(this.foes, t);
    if (this.boss.visible) { this.boss.position.y = this.pedTop + Math.sin(t * 1.6) * 0.03; this.boss.rotation.y = Math.sin(t * 0.5) * 0.15; }

    // confetti
    if (this.confMesh.visible) {
      const m = this._m, q = this._q, e = this._e;
      this.conf.forEach((c, i) => {
        c.y -= c.vy * dt; c.rx += c.sx * dt; c.ry += c.sy * dt;
        if (c.y < 0.1) { c.y = rand(7, 10); c.x = rand(-4.5, 4.5); c.z = rand(-3, 3); }
        e.set(c.rx, c.ry, 0); q.setFromEuler(e);
        m.compose(this._v.set(c.x + Math.sin(t * 2 + c.sway) * 0.3, c.y, c.z), q, this._s.set(1, 1, 1));
        this.confMesh.setMatrixAt(i, m);
      });
      this.confMesh.instanceMatrix.needsUpdate = true;
    }
    // dust drift
    const d = this.dust.geometry.attributes.position;
    for (let i = 0; i < d.count; i++) {
      let y = d.array[i * 3 + 1] + dt * (mode === 'lose' ? 0.5 : 0.18);
      if (y > 7) y = 0;
      d.array[i * 3 + 1] = y; d.array[i * 3] += Math.sin(t + i) * dt * 0.05;
    }
    d.needsUpdate = true;
  }

  render() { this.renderer.render(this.scene, this.camera); }
}
