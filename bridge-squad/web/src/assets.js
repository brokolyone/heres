import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';

import soldierBlue from '../../models/hero/hero_lo.glb';
import heroHi from '../../models/hero/hero_hi.glb';
import soldierRed from '../../models/soldier_red.glb';
import boss from '../../models/boss.glb';
import gate from '../../models/gate.glb';
import tires from '../../models/tires.glb';
import crate from '../../models/crate.glb';
import finish from '../../models/finish.glb';
import bridgeSegment from '../../models/bridge_segment.glb';
import tower from '../../models/tower.glb';
import skyline from '../../models/skyline.glb';

const SOURCES = { soldierBlue, heroHi, soldierRed, boss, gate, tires, crate, finish, bridgeSegment, tower, skyline };

export async function loadModels(onProgress) {
  const loader = new GLTFLoader();
  const out = {};
  const keys = Object.keys(SOURCES);
  for (let i = 0; i < keys.length; i++) {
    const bin = SOURCES[keys[i]];
    const buf = bin.buffer.slice(bin.byteOffset, bin.byteOffset + bin.byteLength);
    const gltf = await new Promise((res, rej) => loader.parse(buf, '', res, rej));
    const root = gltf.scene;
    root.updateMatrixWorld(true);
    root.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
    out[keys[i]] = root;
    onProgress && onProgress((i + 1) / keys.length);
    await new Promise(r => setTimeout(r, 0));
  }
  return out;
}

function findNode(root, name) {
  let hit = null;
  root.traverse(o => { if (!hit && o.name && o.name.replace(/[^a-z_]/gi, '').toLowerCase() === name.toLowerCase().replace(/[^a-z_]/g, '')) hit = o; });
  return hit;
}

// Flattens a character (body / leg_L / leg_R) into three vertex-coloured geometries so a whole
// crowd renders with three instanced draw calls.
export function bakeCharacter(root) {
  root.updateMatrixWorld(true);
  // Textured single-material characters (the hero) keep UVs and their PBR maps.
  let texMat = null;
  root.traverse(o => { if (o.isMesh && !texMat) { const m = [].concat(o.material)[0]; if (m && m.map) texMat = m; } });
  const parts = { texMat };
  const used = new Set();
  const bake = (node, pivot) => {
    const inv = pivot.clone().invert();
    const geos = [];
    node.traverse(o => {
      if (!o.isMesh || used.has(o)) return;
      used.add(o);
      let g = o.geometry.clone();
      g.applyMatrix4(new THREE.Matrix4().multiplyMatrices(inv, o.matrixWorld));
      if (g.index) g = g.toNonIndexed();
      if (!g.attributes.normal) g.computeVertexNormals();
      const mat = Array.isArray(o.material) ? o.material[0] : o.material;
      const c = mat.color ? mat.color.clone() : new THREE.Color(1, 1, 1);
      if (mat.emissive && (mat.emissiveIntensity || 0) > 0 && mat.emissive.getHex() !== 0) {
        c.lerp(mat.emissive.clone().multiplyScalar(Math.min(2, mat.emissiveIntensity)), 0.6);
      }
      if (texMat) {
        for (const k of Object.keys(g.attributes)) if (!['position', 'normal', 'uv'].includes(k)) g.deleteAttribute(k);
        if (!g.attributes.uv) g.setAttribute('uv', new THREE.BufferAttribute(new Float32Array(g.attributes.position.count * 2), 2));
        g.morphAttributes = {};
        geos.push(g);
        return;
      }
      const n = g.attributes.position.count;
      const col = new Float32Array(n * 3);
      const vc = g.attributes.color;
      for (let i = 0; i < n; i++) {
        let r = c.r, gg = c.g, b = c.b;
        if (vc) { r *= vc.getX(i); gg *= vc.getY(i); b *= vc.getZ(i); }
        col[i * 3] = r; col[i * 3 + 1] = gg; col[i * 3 + 2] = b;
      }
      for (const k of Object.keys(g.attributes)) if (k !== 'position' && k !== 'normal') g.deleteAttribute(k);
      g.setAttribute('color', new THREE.BufferAttribute(col, 3));
      g.morphAttributes = {};
      geos.push(g);
    });
    return geos.length ? mergeGeometries(geos) : null;
  };
  for (const name of ['leg_L', 'leg_R']) {
    const node = findNode(root, name);
    if (node) { const geo = bake(node, node.matrixWorld.clone()); if (geo) parts[name] = { geo, pivot: node.matrixWorld.clone() }; }
  }
  const body = findNode(root, 'body') || root;
  parts.body = { geo: bake(root === body ? root : body, new THREE.Matrix4()), pivot: new THREE.Matrix4() };
  // anything not under body/legs (stray meshes) gets folded into the body too
  const rest = bake(root, new THREE.Matrix4());
  if (rest) parts.body.geo = parts.body.geo ? mergeGeometries([parts.body.geo, rest]) : rest;
  const box = new THREE.Box3().setFromBufferAttribute(parts.body.geo.attributes.position);
  parts.height = box.max.y;
  return parts;
}

const _m = new THREE.Matrix4(), _b = new THREE.Matrix4(), _l = new THREE.Matrix4();
const _q = new THREE.Quaternion(), _e = new THREE.Euler(), _p = new THREE.Vector3(), _s = new THREE.Vector3();
const _c = new THREE.Color();

export class Crowd {
  constructor(scene, parts, max) {
    this.max = max;
    const t = parts.texMat;
    const mat = t ? new THREE.MeshStandardMaterial({ map: t.map, normalMap: t.normalMap || null, roughnessMap: t.roughnessMap || null,
      metalnessMap: t.metalnessMap || null, aoMap: null, roughness: t.roughnessMap ? 1 : 0.6, metalness: t.metalnessMap ? 1 : 0,
      emissiveMap: t.emissiveMap || null, emissive: t.emissiveMap ? new THREE.Color(1, 1, 1) : new THREE.Color(0, 0, 0) })
      : new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.55, metalness: 0.0 });
    const mk = geo => {
      const m = new THREE.InstancedMesh(geo, mat, max);
      m.castShadow = true; m.receiveShadow = false; m.frustumCulled = false; m.count = 0;
      for (let i = 0; i < max; i++) m.setColorAt(i, _c.setRGB(1, 1, 1));
      scene.add(m); return m;
    };
    this.body = mk(parts.body.geo);
    this.legs = ['leg_L', 'leg_R'].filter(n => parts[n]).map((n, i) => ({ mesh: mk(parts[n].geo), pivot: parts[n].pivot, sign: i ? -1 : 1 }));
    this.all = [this.body, ...this.legs.map(l => l.mesh)];
  }
  update(list, t) {
    const n = Math.min(list.length, this.max);
    for (let i = 0; i < n; i++) {
      const u = list[i], s = u.s || 1;
      _p.set(u.x, u.y || 0, u.z);
      _e.set(u.rx || 0, u.rot || 0, u.rz || 0, 'YXZ');
      _q.setFromEuler(_e); _s.set(s, s, s);
      _b.compose(_p, _q, _s);
      this.body.setMatrixAt(i, _b);
      const sw = u.run ? Math.sin(t * (u.legSpeed || 15) + (u.ph || 0)) * 0.75 : (u.fly ? 0.5 : 0);
      for (const leg of this.legs) {
        _l.makeRotationX(sw * leg.sign);
        _m.multiplyMatrices(_b, leg.pivot).multiply(_l);
        leg.mesh.setMatrixAt(i, _m);
      }
      const f = u.flash > 0 ? 1 + u.flash * 6 : 1;
      _c.setRGB(f, f, f);
      for (const m of this.all) m.setColorAt(i, _c);
    }
    for (const m of this.all) {
      m.count = n; m.instanceMatrix.needsUpdate = true;
      if (m.instanceColor) m.instanceColor.needsUpdate = true;
    }
  }
}

// Places many copies of a static model with one InstancedMesh per sub-mesh.
export function instanceStatic(root, matrices, { cast = true, receive = true } = {}) {
  const group = new THREE.Group();
  root.updateMatrixWorld(true);
  root.traverse(o => {
    if (!o.isMesh) return;
    const im = new THREE.InstancedMesh(o.geometry, o.material, matrices.length);
    for (let i = 0; i < matrices.length; i++) { _m.multiplyMatrices(matrices[i], o.matrixWorld); im.setMatrixAt(i, _m); }
    im.castShadow = cast; im.receiveShadow = receive;
    im.computeBoundingSphere();
    group.add(im);
  });
  return group;
}

// Material tweaks so exported PBR materials read well under our lights.
export function tuneMaterials(root) {
  root.traverse(o => {
    if (!o.isMesh) return;
    for (const m of [].concat(o.material)) {
      if (m.metalness > 0.6) m.metalness = 0.6;
      m.envMapIntensity = 0.8;
    }
  });
}
