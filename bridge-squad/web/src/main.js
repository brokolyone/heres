import * as THREE from 'three';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { loadModels, bakeCharacter, Crowd, instanceStatic, tuneMaterials } from './assets.js';
import { sfx, unlock, suspend, setSound, soundOn } from './audio.js';

// ---------------------------------------------------------------- constants
const HALF = 5;             // road half-width
const SPEED = 9;            // squad forward speed
const MAXU = 300;           // max squad size
const MAXE = 420;
const SP = 0.52;            // formation spacing
const $ = id => document.getElementById(id);

// ---------------------------------------------------------------- save data
const SAVE_KEY = 'bridge-squad-save-v1';
const save = (() => {
  const d = { level: 1, coins: 0, best: 0, sound: true, up: { squad: 0, fire: 0, power: 0 } };
  try { const s = JSON.parse(localStorage.getItem(SAVE_KEY)); if (s) { Object.assign(d, s); d.up = Object.assign({ squad: 0, fire: 0, power: 0 }, s.up); } } catch (e) {}
  return d;
})();
function persist() { try { localStorage.setItem(SAVE_KEY, JSON.stringify(save)); } catch (e) {} }
setSound(save.sound);

const SHOP = [
  { id: 'squad', name: 'СТАРТОВЫЙ ОТРЯД', max: 25, cost: l => Math.round(40 * Math.pow(1.42, l)),
    desc: l => `бойцов на старте: ${1 + l}`,
    icon: '<svg viewBox="0 0 24 24"><circle cx="9" cy="8" r="3.2"/><path d="M3.5 19.5c0-3.6 2.4-5.8 5.5-5.8s5.5 2.2 5.5 5.8"/><circle cx="17" cy="9" r="2.5"/><path d="M16 13.8c2.6 0 4.5 1.9 4.5 5"/></svg>' },
  { id: 'fire', name: 'СКОРОСТРЕЛЬНОСТЬ', max: 20, cost: l => Math.round(55 * Math.pow(1.45, l)),
    desc: l => `темп огня: +${l * 12}%`,
    icon: '<svg viewBox="0 0 24 24"><path d="M3 10h11l2-3h3v6h-3l-2-2"/><path d="M6 10v6h3l1-6"/><path d="M19 8.5h2M19 11.5h2"/></svg>' },
  { id: 'power', name: 'БРОНЕБОЙНЫЕ ПУЛИ', max: 20, cost: l => Math.round(65 * Math.pow(1.48, l)),
    desc: l => `урон: ×${(1 + l * 0.25).toFixed(2)}`,
    icon: '<svg viewBox="0 0 24 24"><path d="M9 21V10c0-3 1.3-5.6 3-7 1.7 1.4 3 4 3 7v11z"/><path d="M9 16h6M7 21h10"/></svg>' },
];
const stat = {
  startUnits: () => 1 + save.up.squad,
  fireMul: () => 1 + save.up.fire * 0.12,
  dmg: () => 1 + save.up.power * 0.25,
};

// ---------------------------------------------------------------- helpers
function mulberry32(a) { return function () { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
const clamp = (v, a, b) => v < a ? a : v > b ? b : v;
const rand = (a, b) => a + Math.random() * (b - a);
function vib(ms) {
  try { if (window.Android && window.Android.vibrate) window.Android.vibrate(ms); else if (navigator.vibrate) navigator.vibrate(ms); } catch (e) {}
}
function rr(ctx, x, y, w, h, r) { ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); }
const FONT = "'Oswald','Arial Narrow',sans-serif";

// ---------------------------------------------------------------- renderer
const canvas = $('gl');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.NeutralToneMapping;
renderer.toneMappingExposure = 1.05;

const scene = new THREE.Scene();
{
  const c = document.createElement('canvas'); c.width = 4; c.height = 256;
  const g = c.getContext('2d'), gr = g.createLinearGradient(0, 0, 0, 256);
  gr.addColorStop(0, '#3fa4ea'); gr.addColorStop(0.55, '#8fd3f4'); gr.addColorStop(1, '#d9f2ff');
  g.fillStyle = gr; g.fillRect(0, 0, 4, 256);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace;
  scene.background = t;
}
scene.fog = new THREE.Fog(0xc4e8fb, 75, 185);
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
scene.environmentIntensity = 0.45;

const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 400);
scene.add(new THREE.HemisphereLight(0xe6f5ff, 0x4d6a8c, 1.1));
const sun = new THREE.DirectionalLight(0xfff3e0, 2.4);
sun.castShadow = true;
sun.shadow.mapSize.set(1024, 1024);
Object.assign(sun.shadow.camera, { left: -16, right: 16, top: 30, bottom: -30, near: 1, far: 100 });
sun.shadow.bias = -0.0006; sun.shadow.normalBias = 0.03;
scene.add(sun, sun.target);

let W = 1, H = 1;
function resize() {
  W = window.innerWidth; H = window.innerHeight;
  renderer.setSize(W, H, false);
  const a = W / H;
  camera.aspect = a;
  const want = 2 * Math.atan(Math.tan(THREE.MathUtils.degToRad(24)) / a);
  camera.fov = clamp(THREE.MathUtils.radToDeg(want), 52, 82);
  camera.updateProjectionMatrix();
}
window.addEventListener('resize', resize);
resize();

// water
const waterTex = (() => {
  const c = document.createElement('canvas'); c.width = c.height = 256;
  const g = c.getContext('2d');
  g.fillStyle = '#2a95d6'; g.fillRect(0, 0, 256, 256);
  for (let i = 0; i < 70; i++) {
    g.strokeStyle = `rgba(255,255,255,${rand(0.08, 0.35)})`; g.lineWidth = rand(1.5, 3.5); g.lineCap = 'round';
    const x = rand(0, 256), y = rand(0, 256), w = rand(8, 30);
    g.beginPath(); g.moveTo(x, y); g.quadraticCurveTo(x + w / 2, y - 3, x + w, y); g.stroke();
  }
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(30, 60); t.anisotropy = 4;
  return t;
})();
const water = new THREE.Mesh(new THREE.PlaneGeometry(700, 1400), new THREE.MeshStandardMaterial({ map: waterTex, roughness: 0.25, metalness: 0.05 }));
water.rotation.x = -Math.PI / 2; water.position.y = -9; scene.add(water);

// bullets, particles, glow
const MAXB = 280;
const bulletMesh = new THREE.InstancedMesh(new THREE.BoxGeometry(0.1, 0.1, 0.95), new THREE.MeshBasicMaterial({ color: 0xffe68a, toneMapped: false }), MAXB);
bulletMesh.frustumCulled = false; bulletMesh.count = 0; scene.add(bulletMesh);
const MAXP = 900;
const partMesh = new THREE.InstancedMesh(new THREE.BoxGeometry(0.16, 0.16, 0.16), new THREE.MeshBasicMaterial({ color: 0xffffff, toneMapped: false }), MAXP);
partMesh.frustumCulled = false;
{ const c = new THREE.Color(); for (let i = 0; i < MAXP; i++) partMesh.setColorAt(i, c.set(0xffffff)); }
partMesh.count = 0; scene.add(partMesh);
const glow = (() => {
  const c = document.createElement('canvas'); c.width = c.height = 128;
  const g = c.getContext('2d'), gr = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  gr.addColorStop(0, 'rgba(255,225,90,0.75)'); gr.addColorStop(0.6, 'rgba(255,190,40,0.25)'); gr.addColorStop(1, 'rgba(255,190,40,0)');
  g.fillStyle = gr; g.fillRect(0, 0, 128, 128);
  const m = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(c), transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false }));
  m.rotation.x = -Math.PI / 2; m.position.y = 0.04; scene.add(m); return m;
})();

// ---------------------------------------------------------------- state
let M = null;                       // models
let blue, red, bossTpl;             // crowds
let state = 'loading', t = 0;
let units = [], enemies = [], gates = [], obstacles = [], bullets = [], parts = [], flyers = [], redFlyers = [];
let boss = null, cx = 0, cz = 0, targetX = 0, fireAcc = 0, finishZ = -200, runLen = 200;
let towers = [];
let endTimer = 0, runCoins = 0, peak = 1, shake = 0, levelGroup = null, bossObj = null;

// ---------------------------------------------------------------- UI
const ui = {
  show(id) { for (const s of ['menu', 'pause', 'win', 'lose', 'loading']) $(s).hidden = s !== id; $('hud').hidden = !(id === null || id === 'pause'); },
  coins() { $('menuCoins').textContent = save.coins; $('hudCoins').textContent = save.coins + runCoins; },
  level() {
    const op = String(save.level).padStart(2, '0');
    $('menuLv').textContent = op; $('hudOp').textContent = 'ОП-' + op;
    $('winOp').textContent = '// ОПЕРАЦИЯ ' + op; $('loseOp').textContent = '// ОПЕРАЦИЯ ' + op;
  },
  shop() {
    const box = $('shop'); box.innerHTML = '';
    for (const it of SHOP) {
      const lv = save.up[it.id], max = lv >= it.max, cost = it.cost(lv);
      const el = document.createElement('button');
      el.className = 'arm' + (max ? ' max' : save.coins < cost ? ' poor' : '');
      const pipsOn = Math.round(lv / it.max * 10);
      el.innerHTML = `<span class="arm-ic">${it.icon}</span><span class="arm-txt"><b>${it.name}</b><small>УР.${lv + 1} · ${it.desc(lv)}</small>` +
        `<span class="pips">${Array.from({ length: 10 }, (_, k) => `<i${k < pipsOn ? ' class="on"' : ''}></i>`).join('')}</span></span>` +
        `<span class="arm-buy">${max ? 'МАКС' : `<i class="tok"></i>${cost}`}</span>`;
      el.addEventListener('click', () => {
        unlock();
        if (max) return;
        if (save.coins < cost) { sfx.deny(); vib(30); el.classList.remove('flash'); void el.offsetWidth; return; }
        save.coins -= cost; save.up[it.id]++; persist(); sfx.buy(); vib(20);
        ui.shop(); ui.coins();
        if (it.id === 'squad') { resetSquad(); }
        const again = box.children[SHOP.indexOf(it)]; again.classList.add('flash');
      });
      box.appendChild(el);
    }
  },
  sound() { $('soundBtn').classList.toggle('off', !save.sound); },
};

let floatCount = 0;
const _v = new THREE.Vector3();
function floatText(txt, x, y, z, cls) {
  if (floatCount > 14) return;
  _v.set(x, y, z).project(camera);
  const el = document.createElement('div');
  el.className = 'float ' + (cls || ''); el.textContent = txt;
  el.style.left = ((_v.x * 0.5 + 0.5) * W) + 'px'; el.style.top = ((-_v.y * 0.5 + 0.5) * H) + 'px';
  $('fx').appendChild(el); floatCount++;
  const done = () => { if (el.parentNode) { el.remove(); floatCount--; } };
  el.addEventListener('animationend', done); setTimeout(done, 1400);
}

// ---------------------------------------------------------------- level building
function clearLevel() {
  if (levelGroup) {
    scene.remove(levelGroup);
    levelGroup.traverse(o => {
      if (o.userData.ownGeo && o.geometry) o.geometry.dispose();
      if (o.material) for (const m of [].concat(o.material)) { if (m.userData && m.userData.own) { if (m.map) m.map.dispose(); m.dispose(); } }
      if (o.isInstancedMesh) o.dispose();
    });
  }
  for (const o of obstacles) o.el.root.remove();
  levelGroup = new THREE.Group(); scene.add(levelGroup);
}
const own = m => { m.userData.own = true; return m; };

function buildEnvironment(len) {
  const segs = Math.ceil((len + 120) / 20);
  const mats = [];
  for (let i = 0; i < segs; i++) mats.push(new THREE.Matrix4().makeTranslation(0, 0, 60 - 20 * i));
  levelGroup.add(instanceStatic(M.bridgeSegment, mats, { cast: false, receive: true }));
  towers = [];
  for (let z = -40; z > -len - 40; z -= 110) {
    const tw = M.tower.clone(true);
    const mats = [];
    tw.traverse(o => { if (o.isMesh) { o.material = [].concat(o.material).map(m => { const c = own(m.clone()); c.transparent = false; mats.push(c); return c; }); if (o.material.length === 1) o.material = o.material[0]; } });
    tw.position.z = z; levelGroup.add(tw);
    towers.push({ obj: tw, z, mats, faded: false });
  }
  // skyline: long axis along the road, both sides
  const box = new THREE.Box3().setFromObject(M.skyline);
  const size = box.getSize(new THREE.Vector3());
  const rotate = size.x > size.z;              // make the long side run along Z
  const depth = rotate ? size.z : size.x, span = rotate ? size.x : size.z;
  const sk = [];
  for (let z = 40; z > -len - 120; z -= span * 0.95) {
    for (const side of [-1, 1]) {
      const m = new THREE.Matrix4();
      const r = new THREE.Matrix4().makeRotationY(rotate ? side * Math.PI / 2 : (side < 0 ? Math.PI : 0));
      const c = box.getCenter(new THREE.Vector3());
      const off = new THREE.Matrix4().makeTranslation(-c.x, 0, -c.z);
      m.makeTranslation(side * (34 + depth / 2), 0, z - span / 2).multiply(r).multiply(off);
      sk.push(m);
    }
  }
  levelGroup.add(instanceStatic(M.skyline, sk, { cast: false, receive: false }));
}

function drawGate(g) {
  const ctx = g.ctx, w = 256, h = 140;
  const good = g.kind === 'mul' || Math.round(g.val) >= 0;
  ctx.clearRect(0, 0, w, h);
  const gr = ctx.createLinearGradient(0, 0, 0, h);
  if (good) { gr.addColorStop(0, 'rgba(90,160,255,0.62)'); gr.addColorStop(1, 'rgba(30,100,240,0.42)'); }
  else { gr.addColorStop(0, 'rgba(255,110,100,0.62)'); gr.addColorStop(1, 'rgba(220,40,35,0.42)'); }
  ctx.fillStyle = gr; ctx.fillRect(0, 0, w, h);
  ctx.fillStyle = 'rgba(255,255,255,0.18)'; ctx.fillRect(0, 0, w, 10);
  const sign = g.kind === 'mul' ? '×' : (Math.round(g.val) >= 0 ? '+' : '−');
  const num = String(g.kind === 'mul' ? g.mul : Math.abs(Math.round(g.val)));
  const big = `700 104px ${FONT}`, small = `700 66px ${FONT}`;
  ctx.font = small; const sw = ctx.measureText(sign).width + 4;
  ctx.font = big; const nw = ctx.measureText(num).width;
  let x = (w - sw - nw) / 2; const y = h / 2 + 6;
  ctx.textAlign = 'left'; ctx.textBaseline = 'middle'; ctx.lineJoin = 'round';
  const draw = (t, font, xx, yy) => {
    ctx.font = font;
    ctx.fillStyle = 'rgba(11,15,22,0.55)'; ctx.fillText(t, xx + 3, yy + 5);
    ctx.fillStyle = '#ffffff'; ctx.fillText(t, xx, yy);
  };
  draw(sign, small, x, y + 4); draw(num, big, x + sw, y);
  g.tex.needsUpdate = true;
  const col = good ? 0x2f7bff : 0xef4a43;
  for (const m of g.accents) { m.color.setHex(col); if (m.emissive) { m.emissive.setHex(col); m.emissiveIntensity = 0.6; } }
  g.good = good;
}
let pairSeq = 0;
function addGatePair(z, opts) {
  const pid = ++pairSeq;
  [-1, 1].forEach((side, i) => {
    const o = opts[i];
    const grp = new THREE.Group(); grp.position.set(side * HALF / 2, 0, z);
    const frame = M.gate.clone(true);
    const accents = [];
    frame.traverse(n => {
      if (!n.isMesh) return;
      n.material = [].concat(n.material).map(m => {
        if (/accent/i.test(m.name)) { const c = own(m.clone()); accents.push(c); return c; }
        return m;
      });
      if (n.material.length === 1) n.material = n.material[0];
    });
    grp.add(frame);
    const c = document.createElement('canvas'); c.width = 256; c.height = 140;
    const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace;
    const panel = new THREE.Mesh(new THREE.PlaneGeometry(4.4, 2.4), own(new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false, side: THREE.DoubleSide, toneMapped: false })));
    panel.userData.ownGeo = true; panel.position.y = 1.35; grp.add(panel);
    levelGroup.add(grp);
    const g = { z, cx: side * HALF / 2, hw: 2.35, kind: o.kind, val: o.val || 0, mul: o.mul || 1, ctx: c.getContext('2d'), tex, grp, accents, pid, used: false, fade: 1, pulse: 0 };
    drawGate(g); gates.push(g);
  });
}
function gateOpt(rng, good, lv) {
  if (good) {
    if (rng() < 0.27) return { kind: 'mul', mul: rng() < 0.82 ? 2 : 3 };
    return { kind: 'add', val: 3 + Math.floor(rng() * (5 + lv * 2.5)) };
  }
  return { kind: 'add', val: -(3 + Math.floor(rng() * (5 + lv * 3))) };
}

const SHIELD = '<svg viewBox="0 0 24 24"><path d="M12 2 4 5v6c0 5 3.4 9.4 8 11 4.6-1.6 8-6 8-11V5z" fill="#ff4d45" stroke="#0f2343" stroke-width="2.2" stroke-linejoin="round"/><path d="M12 6v12" stroke="#fff" stroke-width="2" stroke-linecap="round" opacity=".6"/></svg>';
const PERSON = '<svg viewBox="0 0 24 24"><circle cx="12" cy="7" r="4.5"/><path d="M3.5 22c0-5.5 3.8-8.5 8.5-8.5s8.5 3 8.5 8.5z"/></svg>';
function drawObs(o) {
  const hp = Math.max(0, Math.ceil(o.hp));
  o.el.num.textContent = hp;
  o.el.bar.style.width = (hp / o.max * 100) + '%';
  o.el.root.classList.remove('hit'); void o.el.root.offsetWidth; o.el.root.classList.add('hit');
}
function addObstacle(kind, x, z, hp, reward) {
  const grp = new THREE.Group(); grp.position.set(x, 0, z);
  const model = (kind === 'crate' ? M.crate : M.tires).clone(true);
  model.rotation.y = rand(-0.3, 0.3);
  grp.add(model);
  levelGroup.add(grp);
  const root = document.createElement('div');
  root.className = 'tag otag'; root.hidden = true;
  root.innerHTML = `<div class="o-plate"><div class="o-row"><small>ПРОЧН.</small><b>${hp}</b></div><div class="o-bar"><i></i></div></div>` +
    `<div class="o-rew">+${reward}${PERSON}</div>`;
  $('tags').appendChild(root);
  const el = { root, num: root.querySelector('b'), bar: root.querySelector('.o-bar i') };
  const o = { x, z, hp, max: hp, reward, grp, model, el, alive: true, punch: 0, shownHp: hp };
  obstacles.push(o);
}
function addEnemyGroup(rng, x0, z0, n) {
  const cols = Math.min(7, Math.max(3, Math.ceil(Math.sqrt(n * 1.6))));
  for (let i = 0; i < n && enemies.length < MAXE; i++) {
    const r = Math.floor(i / cols), c = i % cols;
    const x = clamp(x0 + (c - (cols - 1) / 2) * 0.85 + (rng() - 0.5) * 0.45, -HALF + 0.5, HALF - 0.5);
    enemies.push({ x, z: z0 - r * 0.85 + (rng() - 0.5) * 0.45, rot: Math.PI, run: false, ph: rng() * 6, active: false, dead: false, flash: 0 });
  }
}

function resetSquad() {
  if (state !== 'menu') return;
  units = [];
  addUnits(stat.startUnits(), 0, 0, false);
  for (const u of units) { u.x = cx; u.z = cz; }
}

function buildLevel(lv) {
  clearLevel();
  const rng = mulberry32(lv * 7919 + 13);
  units = []; enemies = []; gates = []; obstacles = []; bullets = []; parts = []; flyers = []; redFlyers = [];
  cx = 0; cz = 0; targetX = 0; fireAcc = 0; endTimer = 0; runCoins = 0;
  addUnits(stat.startUnits(), 0, 0, false);
  peak = units.length;
  const L = 200 + Math.min(lv, 25) * 22;
  let z = -26, seg = 0, last = '';
  while (z > -L + 30) {
    let type;
    if (seg === 0) type = 'gate';
    else {
      const r = rng();
      type = r < 0.42 ? 'gate' : r < 0.78 ? 'enemy' : 'obs';
      if (type === last && type !== 'gate') type = 'gate';
    }
    if (type === 'gate') {
      const r = rng();
      let a, b;
      if (seg === 0) { a = gateOpt(rng, true, lv); b = { kind: 'add', val: 3 + Math.floor(rng() * 4) }; }
      else if (r < 0.5) { a = gateOpt(rng, true, lv); b = gateOpt(rng, false, lv); }
      else if (r < 0.85) { a = gateOpt(rng, true, lv); b = gateOpt(rng, true, lv); }
      else { a = gateOpt(rng, false, lv); b = gateOpt(rng, false, lv); }
      if (rng() < 0.5) [a, b] = [b, a];
      addGatePair(z, [a, b]);
    } else if (type === 'enemy') {
      const n = Math.round((4 + lv * 2.6 + seg * 1.5) * (0.75 + rng() * 0.5));
      addEnemyGroup(rng, (rng() - 0.5) * 4, z, Math.min(n, 80));
    } else {
      const hp = Math.round(16 + lv * 11 + seg * 4 + rng() * 14);
      addObstacle(rng() < 0.5 ? 'tires' : 'crate', (rng() < 0.5 ? -1 : 1) * (1.1 + rng() * 2), z, hp, 4 + Math.floor(rng() * (5 + lv * 2)));
    }
    last = type; seg++;
    z -= 24 + rng() * 8;
  }
  const bz = Math.min(z, -L);
  const hp = 60 + lv * 45;
  boss = { x: 0, z: bz, hp, max: hp, active: false, alive: true, hit: 0, punch: 0, walk: 0 };
  bossObj = M.boss.clone(true);
  bossObj.position.set(0, 0, bz); bossObj.rotation.y = Math.PI;
  bossObj.userData.legs = ['leg_L', 'leg_R'].map(n => {
    let found = null; bossObj.traverse(o => { if (!found && o.name.replace(/[^a-z_]/gi, '').toLowerCase() === n.toLowerCase()) found = o; });
    return found ? { node: found, base: found.quaternion.clone() } : null;
  }).filter(Boolean);
  bossObj.userData.mats = [];
  bossObj.traverse(o => { if (o.isMesh) { o.material = [].concat(o.material).map(m => { const c = own(m.clone()); bossObj.userData.mats.push(c); return c; }); if (o.material.length === 1) o.material = o.material[0]; } });
  bossObj.userData.mats.forEach(m => { m.userData.baseEmissive = m.emissive ? m.emissive.clone() : null; m.userData.baseEI = m.emissiveIntensity || 0; });
  levelGroup.add(bossObj);
  finishZ = bz - 18; runLen = -finishZ;
  const fin = M.finish.clone(true); fin.position.set(0, 0, finishZ); levelGroup.add(fin);
  buildEnvironment(runLen + 40);
  $('progBoss').style.width = (22 / runLen * 100) + '%';
  ui.level(); ui.coins();
  snapCamera();
}

// ---------------------------------------------------------------- squad ops
function addUnits(n, x, z, pop) {
  n = Math.min(n, MAXU - units.length);
  for (let i = 0; i < n; i++) units.push({ x: x + rand(-0.4, 0.4), z: z + rand(-0.4, 0.4), rot: 0, run: true, ph: Math.random() * 6, flash: pop ? 0.25 : 0 });
  if (pop && n > 0) burst(x, 1, z, 0x7fb2ff, Math.min(n, 14), 1.2);
  peak = Math.max(peak, units.length);
  bumpTag();
}
function removeUnits(n) {
  n = Math.min(n, units.length);
  for (let i = 0; i < n; i++) { const u = units.pop(); fling(u, flyers, 1); }
  bumpTag();
}
function fling(u, list, dir) {
  if (list.length > 120) list.shift();
  list.push({ x: u.x, y: 0, z: u.z, vx: rand(-3, 3), vy: rand(5, 8), vz: dir * rand(3, 6), rot: u.rot || 0, rx: 0, rz: 0,
    srx: rand(-9, 9), srz: rand(-9, 9), life: 1, fly: true, s: 1 });
}
function burst(x, y, z, color, n, power = 1) {
  for (let i = 0; i < n && parts.length < MAXP; i++) {
    const a = Math.random() * Math.PI * 2, s = (2 + Math.random() * 4) * power;
    parts.push({ x, y, z, vx: Math.cos(a) * s, vy: (3 + Math.random() * 4) * power, vz: Math.sin(a) * s, life: 0.5 + Math.random() * 0.45, color });
  }
}
let tagBumpT = 0, coinsDirty = false;
function bumpTag() { tagBumpT = 0.25; }
function applyGate(g) {
  const n = units.length;
  if (g.kind === 'mul') { addUnits(n * (g.mul - 1), cx, cz + 1, true); floatText('×' + g.mul, cx, 2.5, cz, 'good big'); sfx.gateGood(); vib(15); }
  else {
    const v = Math.round(g.val);
    if (v >= 0) { addUnits(v, cx, cz + 1, true); floatText('+' + v, cx, 2.5, cz, 'good'); sfx.gateGood(); vib(15); }
    else { removeUnits(-v); floatText('−' + (-v), cx, 2.5, cz, 'bad'); sfx.gateBad(); vib(60); shake = 0.25; }
  }
}
function addCoins(n, x, y, z) {
  runCoins += n; ui.coins();
  if (x !== undefined) { floatText('+' + n, x, y, z, 'gold'); sfx.coin(); }
}

// ---------------------------------------------------------------- input
let drag = null;
const keys = {};
canvas.addEventListener('pointerdown', e => { unlock(); drag = { x: e.clientX, tx: targetX }; try { canvas.setPointerCapture(e.pointerId); } catch (_) {} });
canvas.addEventListener('pointermove', e => {
  if (!drag || state !== 'play') return;
  targetX = clamp(drag.tx + (e.clientX - drag.x) / Math.min(W, 520) * 11.5, -HALF + 0.6, HALF - 0.6);
});
const endDrag = () => { drag = null; };
canvas.addEventListener('pointerup', endDrag);
canvas.addEventListener('pointercancel', endDrag);
window.addEventListener('keydown', e => { keys[e.code] = true; if (e.code === 'Escape') window.onAppBack(); });
window.addEventListener('keyup', e => { keys[e.code] = false; });
document.addEventListener('pointerdown', unlock, { capture: true });

function startRun() { sfx.click(); ui.show(null); state = 'play'; drag = null; }
$('playBtn').addEventListener('click', () => { unlock(); startRun(); });
$('pauseBtn').addEventListener('click', () => pauseGame());
$('resumeBtn').addEventListener('click', () => { sfx.click(); ui.show(null); state = 'play'; });
$('quitBtn').addEventListener('click', () => { sfx.click(); bankRun(); toMenu(); });
$('nextBtn').addEventListener('click', () => { sfx.click(); toMenu(); });
$('retryBtn').addEventListener('click', () => { sfx.click(); buildLevel(save.level); startRun(); });
$('loseMenuBtn').addEventListener('click', () => { sfx.click(); toMenu(); });
$('soundBtn').addEventListener('click', () => { save.sound = !save.sound; setSound(save.sound); persist(); ui.sound(); unlock(); sfx.click(); });

function pauseGame() { if (state !== 'play') return; state = 'pause'; ui.show('pause'); }
function toMenu() { state = 'menu'; buildLevel(save.level); ui.shop(); ui.coins(); ui.show('menu'); }
function bankRun() { save.coins += runCoins; runCoins = 0; persist(); }
window.onAppPause = () => { pauseGame(); suspend(); };
window.onAppBack = () => {
  if (state === 'play') { pauseGame(); return true; }
  if (state === 'pause') { ui.show(null); state = 'play'; return true; }
  if (state === 'win' || state === 'lose') { toMenu(); return true; }
  return false;
};
document.addEventListener('visibilitychange', () => { if (document.hidden) window.onAppPause(); });

function win() {
  state = 'win';
  const survivors = units.length;
  const bonus = 20 + save.level * 6 + survivors;
  addCoins(bonus);
  const stars = 1 + (survivors >= peak * 0.3 ? 1 : 0) + (survivors >= peak * 0.65 ? 1 : 0);
  $('winSquad').textContent = survivors;
  $('winCoins').textContent = runCoins;
  [...document.querySelectorAll('.medals i')].forEach((s, i) => s.classList.toggle('on', i < stars));
  $('winPeak').textContent = peak;
  save.best = Math.max(save.best, survivors);
  bankRun();
  save.level++; persist();
  sfx.win(); vib(40);
  setTimeout(() => { if (state === 'win') ui.show('win'); }, 700);
}
function lose() {
  state = 'lose';
  $('loseCoins').textContent = runCoins;
  const tips = ['Проходи через синие ворота, а красные расстреливай издалека — они станут синими.',
    'Улучши «Стартовый отряд» в меню — с бо́льшим отрядом проще.',
    'Шины и ящики дают бойцов, если их сломать выстрелами. Не врезайся в них.',
    'Босса бьют пули и бойцы. Подходи к нему с большим отрядом.'];
  $('loseTip').textContent = tips[(Math.random() * tips.length) | 0];
  bankRun();
  sfx.lose(); vib(200);
  setTimeout(() => { if (state === 'lose') ui.show('lose'); }, 500);
}

// ---------------------------------------------------------------- simulation
function spawnBullet(x, z) {
  if (bullets.length >= MAXB) return;
  bullets.push({ x: x + 0.08, z: z - 0.55, pz: z - 0.55, life: 0.7 });
}

function update(dt) {
  t += dt;
  let moveDz = 0;
  const playing = state === 'play';
  if (playing) {
    if (keys.ArrowLeft || keys.KeyA) targetX -= dt * 10;
    if (keys.ArrowRight || keys.KeyD) targetX += dt * 10;
    targetX = clamp(targetX, -HALF + 0.6, HALF - 0.6);
    const blocked = boss.alive && cz - boss.z < 3.1;
    if (!blocked) moveDz = SPEED * dt;
    cz -= moveDz;
    cx += (targetX - cx) * Math.min(1, dt * 12);
  } else if (state === 'win') {
    moveDz = SPEED * 0.6 * dt; cz -= moveDz;
    cx += (0 - cx) * Math.min(1, dt * 3);
  }
  // formation (sunflower, squashed lengthwise once wider than the road)
  const n = units.length;
  const R = SP * Math.sqrt(Math.max(n, 1));
  const f = R > 4.1 ? 4.1 / R : 1;
  const k = Math.min(1, dt * 7);
  for (let i = 0; i < n; i++) {
    const u = units[i];
    const r = SP * Math.sqrt(i + 0.3), th = i * 2.39996;
    const tx = clamp(cx + r * Math.cos(th) * f, -HALF + 0.35, HALF - 0.35);
    const tz = cz + r * Math.sin(th) / f;
    u.z -= moveDz;
    u.x += (tx - u.x) * k; u.z += (tz - u.z) * k;
    u.run = state === 'play' || state === 'win';
    u.rot = state === 'win' ? 0 : (tx - u.x) * -0.25;
    if (u.flash > 0) u.flash = Math.max(0, u.flash - dt * 2);
  }

  if (playing) {
    // shooting
    if (n > 0) {
      fireAcc += dt * Math.min(46, (3 + n * 0.7) * stat.fireMul());
      let shots = 0;
      while (fireAcc >= 1) { fireAcc -= 1; const u = units[(Math.random() * n) | 0]; spawnBullet(u.x, u.z); shots++; }
      if (shots) sfx.shot();
    }
    // gates
    for (const g of gates) {
      if (g.used || cz > g.z) continue;
      const pair = gates.filter(o => o.pid === g.pid);
      const chosen = pair.find(o => (cx < 0) === (o.cx < 0)) || pair[0];
      pair.forEach(o => o.used = true);
      applyGate(chosen);
    }
    // enemies
    const act = [];
    for (const e of enemies) {
      if (e.dead) continue;
      if (e.flash > 0) e.flash -= dt * 3;
      if (!e.active && e.z > cz - 30) e.active = true;
      if (!e.active) continue;
      const dx = cx - e.x, dz = cz - e.z, d = Math.hypot(dx, dz) || 1;
      e.x += dx / d * 4.3 * dt; e.z += dz / d * 4.3 * dt;
      e.rot = Math.atan2(-dx, -dz); e.run = true;
      if (e.z > cz + 8) { e.dead = true; continue; }
      act.push(e);
    }
    if (act.length && units.length) {
      let killed = false;
      for (const e of act) {
        for (let i = 0; i < units.length; i++) {
          const u = units[i];
          if (u.dead) continue;
          const dx = u.x - e.x, dz = u.z - e.z;
          if (dx * dx + dz * dz < 0.45) {
            u.dead = true; e.dead = true; killed = true;
            fling(u, flyers, 1); fling(e, redFlyers, -1);
            burst((u.x + e.x) / 2, 0.7, (u.z + e.z) / 2, 0xffffff, 3);
            break;
          }
        }
      }
      if (killed) { units = units.filter(u => !u.dead); sfx.ouch(); vib(12); bumpTag(); }
    }
    // obstacles vs squad
    for (const o of obstacles) {
      if (!o.alive || Math.abs(o.z - cz) > 14) continue;
      let hit = false;
      for (const u of units) {
        if (Math.abs(u.x - o.x) < 1.2 && Math.abs(u.z - o.z) < 1.05) {
          u.dead = true; hit = true; o.hp -= 2 * stat.dmg(); fling(u, flyers, 1);
          if (o.hp <= 0) break;
        }
      }
      if (hit) { units = units.filter(u => !u.dead); o.punch = 0.2; vib(20); sfx.ouch(); bumpTag(); }
      if (o.hp <= 0) breakObstacle(o);
    }
    // boss
    if (boss.alive) {
      if (!boss.active && boss.z > cz - 36) { boss.active = true; sfx.bossRoar(); shake = 0.35; vib(80); }
      if (boss.active) {
        const dz = cz - boss.z;
        if (dz > 2.6) { boss.z += 2.4 * dt; boss.walk += dt; }
        boss.x += (cx - boss.x) * Math.min(1, dt * 0.8);
        let hit = false;
        for (const u of units) {
          const dx = u.x - boss.x, dzz = u.z - boss.z;
          if (dx * dx + dzz * dzz < 1.9 * 1.9) { u.dead = true; hit = true; boss.hp -= 3 * stat.dmg(); fling(u, flyers, 1); }
        }
        if (hit) { units = units.filter(u => !u.dead); boss.hit = 0.15; shake = Math.max(shake, 0.12); bumpTag(); sfx.ouch(); }
        if (boss.hp <= 0) killBoss();
      }
    }
    if (!units.length) { endTimer += dt; if (endTimer > 0.7) lose(); }
    if (!boss.alive && cz < finishZ + 2) win();
  }

  // bullets
  const dmg = stat.dmg();
  let gateTicked = false;
  for (let i = bullets.length - 1; i >= 0; i--) {
    const b = bullets[i];
    b.pz = b.z; b.z -= 48 * dt; b.life -= dt;
    let dead = b.life <= 0;
    if (!dead) for (const g of gates) {
      if (g.used || !(b.pz >= g.z && b.z <= g.z) || Math.abs(b.x - g.cx) > g.hw) continue;
      dead = true;
      if (g.kind === 'add') {
        const before = Math.round(g.val);
        g.val += 0.3 * dmg;
        if (Math.round(g.val) !== before) { drawGate(g); g.pulse = 0.12; if (!gateTicked) { sfx.gateTick(); gateTicked = true; } }
      }
      if (Math.random() < 0.35) burst(b.x, 1.2 + Math.random(), g.z + 0.1, 0xfff1a8, 1, 0.5);
      break;
    }
    if (!dead) for (const o of obstacles) {
      if (!o.alive || Math.abs(b.x - o.x) > 1.25 || !(b.z <= o.z + 1 && b.pz >= o.z - 1)) continue;
      dead = true; o.hp -= dmg; o.punch = Math.max(o.punch, 0.1);
      if (Math.random() < 0.3) burst(b.x, 1 + Math.random(), o.z + 1, 0x444a55, 1, 0.6);
      if (o.hp <= 0) breakObstacle(o);
      break;
    }
    if (!dead) for (const e of enemies) {
      if (e.dead || Math.abs(b.x - e.x) > 0.45 || !(e.z >= b.z - 0.4 && e.z <= b.pz + 0.4)) continue;
      dead = true; e.dead = true; fling(e, redFlyers, -1); burst(e.x, 0.8, e.z, 0xef4a43, 4); sfx.pop();
      runCoins += 1; coinsDirty = true;
      break;
    }
    if (!dead && boss && boss.alive && Math.abs(b.x - boss.x) < 1.4 && boss.z >= b.z - 1.1 && boss.z <= b.pz + 1.1) {
      dead = true; boss.hp -= dmg; boss.hit = Math.max(boss.hit, 0.06);
      if (Math.random() < 0.4) burst(b.x, 1.5 + Math.random() * 2, boss.z + 1, 0xffe68a, 1, 0.6);
      if (boss.hp <= 0 && state === 'play') killBoss();
    }
    if (dead) bullets.splice(i, 1);
  }
  // fx sims
  for (let i = parts.length - 1; i >= 0; i--) {
    const p = parts[i];
    p.life -= dt; p.vy -= 18 * dt;
    p.x += p.vx * dt; p.y += p.vy * dt; p.z += p.vz * dt;
    if (p.y < 0.08) { p.y = 0.08; p.vy *= -0.3; p.vx *= 0.6; p.vz *= 0.6; }
    if (p.life <= 0) parts.splice(i, 1);
  }
  for (const list of [flyers, redFlyers]) {
    for (let i = list.length - 1; i >= 0; i--) {
      const u = list[i];
      u.life -= dt * 1.1; u.vy -= 20 * dt;
      u.x += u.vx * dt; u.y += u.vy * dt; u.z += u.vz * dt;
      u.rx += u.srx * dt; u.rz += u.srz * dt;
      u.s = Math.min(1, u.life * 3);
      if (u.life <= 0) list.splice(i, 1);
    }
  }
  for (const g of gates) {
    if (g.used && g.fade > 0) { g.fade = Math.max(0, g.fade - dt * 3.5); g.grp.scale.setScalar(Math.max(0.001, g.fade)); g.grp.visible = g.fade > 0; }
    else if (g.pulse > 0) { g.pulse -= dt; g.grp.scale.setScalar(1 + Math.max(0, g.pulse) * 0.4); }
  }
  for (const o of obstacles) {
    if (!o.alive) continue;
    const hp = Math.max(0, Math.ceil(o.hp));
    if (hp !== o.shownHp) { o.shownHp = hp; drawObs(o); }
    o.punch = Math.max(0, o.punch - dt);
    const s = 1 + o.punch * 0.6;
    o.model.scale.set(s, 1 - o.punch * 0.4, s);
  }
  enemies = enemies.filter(e => !e.dead);
  if (shake > 0) shake = Math.max(0, shake - dt);
  if (tagBumpT > 0) tagBumpT -= dt;
  if (coinsDirty) { coinsDirty = false; ui.coins(); }
}

function breakObstacle(o) {
  if (!o.alive) return;
  o.alive = false; o.grp.visible = false; o.el.root.hidden = true;
  burst(o.x, 1, o.z, 0x2f3540, 16, 1.3); burst(o.x, 1.4, o.z, 0xef4a43, 8); burst(o.x, 1.4, o.z, 0xffcb2e, 8);
  addUnits(o.reward, o.x, o.z, true);
  floatText('+' + o.reward, o.x, 3, o.z, 'good');
  addCoins(5, o.x, 4.2, o.z);
  sfx.smash(); vib(35); shake = Math.max(shake, 0.15);
}
function killBoss() {
  if (!boss.alive) return;
  boss.alive = false;
  for (let i = 0; i < 5; i++) burst(boss.x + rand(-1.2, 1.2), rand(1, 3), boss.z, [0xef4a43, 0xffcb2e, 0x2f3540][i % 3], 22, 1.4);
  bossObj.visible = false;
  floatText('БОСС ПОВЕРЖЕН', boss.x, 4.5, boss.z, 'big');
  addCoins(30, boss.x, 3, boss.z);
  sfx.bossDown(); vib(120); shake = 0.6;
}

// ---------------------------------------------------------------- render
const camPos = new THREE.Vector3(), camLook = new THREE.Vector3(), _w = new THREE.Vector3();
let bossTrail = 0, bossShown = -1;
const _m4 = new THREE.Matrix4(), _col = new THREE.Color(), _qx = new THREE.Quaternion(), _ax = new THREE.Vector3(1, 0, 0);
function camTarget() {
  const R = SP * Math.sqrt(Math.max(units.length, 1));
  const g = Math.min(R, 6);
  if (state === 'menu' || state === 'loading') {
    camPos.set(cx + 3.2, 4.2, cz + 7.5); camLook.set(cx, 1.0, cz - 1.5);
  } else {
    camPos.set(cx * 0.35, 11.5 + g * 1.15, cz + 11 + g * 0.95);
    camLook.set(cx * 0.2, 0, cz - 11);
  }
}
function snapCamera() { camTarget(); camera.position.copy(camPos); camera.lookAt(camLook); }

function render() {
  const blueList = flyers.length ? units.concat(flyers) : units;
  const redList = redFlyers.length ? enemies.concat(redFlyers) : enemies;
  blue.update(blueList, t);
  red.update(redList, t);
  if (bossObj && boss.alive) {
    bossObj.position.set(boss.x, 0, boss.z);
    const walking = boss.active && cz - boss.z > 2.6 && state === 'play';
    const sw = walking ? Math.sin(t * 6) * 0.5 : 0;
    bossObj.userData.legs.forEach((l, i) => { _qx.setFromAxisAngle(_ax, i ? -sw : sw); l.node.quaternion.copy(l.base).multiply(_qx); });
    bossObj.position.y = walking ? Math.abs(Math.cos(t * 6)) * 0.12 : 0;
    const hs = boss.hit > 0 ? 1.05 : 1; bossObj.scale.setScalar(hs);
    for (const m of bossObj.userData.mats) {
      if (!m.emissive) continue;
      if (boss.hit > 0.1) { m.emissive.setRGB(1, 0.85, 0.8); m.emissiveIntensity = 0.35; }
      else if (boss.hit > 0) { m.emissive.setRGB(1, 0.6, 0.5); m.emissiveIntensity = 0.08; }
      else if (m.userData.baseEmissive) { m.emissive.copy(m.userData.baseEmissive); m.emissiveIntensity = m.userData.baseEI; }
    }
    boss.hit = Math.max(0, boss.hit - 1 / 60);
  }
  for (let i = 0; i < bullets.length; i++) { _m4.makeTranslation(bullets[i].x, 0.72, bullets[i].z); bulletMesh.setMatrixAt(i, _m4); }
  bulletMesh.count = bullets.length; bulletMesh.instanceMatrix.needsUpdate = true;
  for (let i = 0; i < parts.length; i++) {
    const p = parts[i], s = Math.max(0.2, Math.min(1, p.life * 1.8));
    _m4.makeScale(s, s, s); _m4.setPosition(p.x, p.y, p.z); partMesh.setMatrixAt(i, _m4);
    partMesh.setColorAt(i, _col.set(p.color));
  }
  partMesh.count = parts.length; partMesh.instanceMatrix.needsUpdate = true;
  if (partMesh.instanceColor) partMesh.instanceColor.needsUpdate = true;

  const R = SP * Math.sqrt(Math.max(units.length, 1));
  glow.visible = state === 'play' && units.length > 0;
  const gs = (R * 2.3 + 1.6) * (0.93 + Math.sin(t * 28) * 0.07);
  glow.scale.set(gs, gs * 1.25, 1); glow.position.x = cx; glow.position.z = cz - 0.4;

  sun.position.set(cx + 10, 32, cz + 8); sun.target.position.set(cx, 0, cz - 12);
  waterTex.offset.set(t * 0.004, t * 0.01);
  water.position.z = cz - 200;

  // HTML tags
  const sq = $('squadTag');
  if (units.length && (state === 'play' || (state === 'win' && $('win').hidden))) {
    _v.set(cx, 1.5 + Math.min(R, 4) * 0.2, cz - Math.min(R, 4) * 0.35).project(camera);
    sq.hidden = false; $('squadNum').textContent = units.length;
    const sc = tagBumpT > 0 ? 1.25 : 1;
    sq.style.transform = `translate(${(_v.x * 0.5 + 0.5) * W}px, ${(-_v.y * 0.5 + 0.5) * H}px) translate(-50%,-100%) scale(${sc})`;
  } else sq.hidden = true;
  const bb = $('bossBar');
  if (boss && boss.alive && boss.active && (state === 'play' || state === 'pause')) {
    if (bb.hidden) { bb.hidden = false; $('bossMax').textContent = Math.round(boss.max); bossTrail = boss.hp; }
    const hp = Math.max(0, boss.hp);
    if (Math.ceil(hp) !== bossShown) {
      if (hp < bossShown) { bb.classList.remove('hit'); void bb.offsetWidth; bb.classList.add('hit'); }
      bossShown = Math.ceil(hp); $('bossNum').textContent = bossShown;
    }
    bossTrail = Math.max(hp, bossTrail - boss.max * 0.35 * (1 / 60));
    $('bossFill').style.width = (hp / boss.max * 100) + '%';
    $('bossTrail').style.width = (bossTrail / boss.max * 100) + '%';
  } else { bb.hidden = true; bossShown = -1; }
  // obstacle HP plates, scaled by distance
  for (const o of obstacles) {
    if (!o.alive) continue;
    const ahead = cz - o.z;
    if (state === 'menu' || ahead < -2 || ahead > 46) { o.el.root.hidden = true; continue; }
    _v.set(o.x, 2.55, o.z).project(camera);
    if (_v.z > 1) { o.el.root.hidden = true; continue; }
    o.el.root.hidden = false;
    const d = camera.position.distanceTo(_w.set(o.x, 2.5, o.z));
    const sc = clamp(22 / d, 0.72, 1.2);
    o.el.root.style.transform = `translate(${(_v.x * 0.5 + 0.5) * W}px, ${(-_v.y * 0.5 + 0.5) * H}px) translate(-50%,-100%) scale(${sc})`;
  }
  $('prog').style.width = clamp(-cz / runLen * 100, 0, 100) + '%';
  $('hudDist').textContent = Math.max(0, Math.round(runLen + cz)) + ' м';

  // fade bridge towers the camera is flying through
  for (const tw of towers) {
    const a = camera.position.z - tw.z;           // >0: tower is ahead of the camera
    const op = a > 12 ? clamp((a - 12) / 8, 0, 1) : a < -1 ? clamp((-1 - a) / 3, 0, 1) : 0;
    tw.obj.visible = op > 0.04;
    const fade = op < 1;
    if (fade !== tw.faded) { tw.faded = fade; for (const m of tw.mats) { m.transparent = fade; m.depthWrite = !fade; m.needsUpdate = true; } tw.obj.traverse(o => { if (o.isMesh) o.castShadow = !fade; }); }
    if (fade) for (const m of tw.mats) m.opacity = op;
  }

  renderer.render(scene, camera);
}

let last = performance.now();
function frame(now) {
  const dt = Math.min(0.05, (now - last) / 1000); last = now;
  if (state !== 'pause' && state !== 'loading') update(dt);
  camTarget();
  const k = Math.min(1, dt * (state === 'menu' ? 2.5 : 4));
  camera.position.lerp(camPos, k);
  if (shake > 0) camera.position.add(_v.set(rand(-1, 1), rand(-1, 1), 0).multiplyScalar(shake * 0.5));
  camera.lookAt(camLook);
  if (M) render(); else renderer.render(scene, camera);
  requestAnimationFrame(frame);
}

// ---------------------------------------------------------------- boot
(async function boot() {
  ui.show('loading'); ui.sound();
  requestAnimationFrame(frame);
  try { await Promise.all([document.fonts.load(`700 20px ${FONT}`), document.fonts.load(`600 20px ${FONT}`), document.fonts.load(`800 20px 'JBMono'`)]); } catch (e) {}
  M = await loadModels(p => { $('loadBar').style.width = (5 + p * 95) + '%'; });
  for (const k of Object.keys(M)) tuneMaterials(M[k]);
  blue = new Crowd(scene, bakeCharacter(M.soldierBlue), MAXU + 130);
  red = new Crowd(scene, bakeCharacter(M.soldierRed), MAXE + 130);
  state = 'menu';
  buildLevel(save.level);
  ui.shop(); ui.coins(); ui.level();
  ui.show('menu');
  window.__game = { get state() { return state; }, get units() { return units.length; }, get cz() { return cz; }, get boss() { return boss; },
    setX(x) { targetX = x; }, get obstacles() { return obstacles.map(o => o.z); }, warp(z) { const d = z - cz; cz = z; for (const u of units) u.z += d; snapCamera(); }, cheat(n) { addUnits(n, cx, cz, true); }, kill() { removeUnits(units.length); } };
})();
