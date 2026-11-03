// Visual models of the proving ground. The game owns placement and physics colliders; every factory here returns an
// Object3D whose origin sits at the collider centre with the collider's orientation (see SPEC.md §Environment).
// OWNER: environment agent.
import { THREE, STD, PALETTE, canvasTex, rnd } from '../common.js';

export const hazardTex = canvasTex(256, 64, (x, w, h) => { x.fillStyle = '#161614'; x.fillRect(0, 0, w, h); x.fillStyle = '#e3ae1c';
  for (let i = -2; i < 12; i++) { x.beginPath(); x.moveTo(i * 32, h); x.lineTo(i * 32 + 16, h); x.lineTo(i * 32 + 16 + h, 0); x.lineTo(i * 32 + h, 0); x.fill(); } }, true);
const concreteMat = STD(PALETTE.concrete, { roughness: 0.95 });
const shadows = (o, recv = true) => { o.traverse(m => { if (m.isMesh) { m.castShadow = true; m.receiveShadow = recv; } }); return o; };

// Crash barrier block: collider half extents (4, 1.5, 1.2); impact face is local −z.
export function barrier() {
  const g = new THREE.Group();
  g.add(new THREE.Mesh(new THREE.BoxGeometry(8, 3, 2.4), concreteMat));
  const face = new THREE.Mesh(new THREE.BoxGeometry(8.02, 1.4, 0.06), STD(0x555a5c, { metalness: 0.6, roughness: 0.5 })); face.position.set(0, -0.6, -1.21); g.add(face);
  const t = hazardTex.clone(); t.needsUpdate = true; t.repeat.set(8, 1);
  const hz = new THREE.Mesh(new THREE.PlaneGeometry(8, 0.35), new THREE.MeshStandardMaterial({ map: t, roughness: 0.8 })); hz.position.set(0, 0.35, -1.205); hz.rotation.y = Math.PI; g.add(hz);
  return shadows(g);
}
// Vertical steel pole, radius r, height h, origin at mid height (collider: cylinder r,h).
export function pole(r, h, color = 0x6f7477) {
  const g = new THREE.Group();
  g.add(new THREE.Mesh(new THREE.CylinderGeometry(r, r, h, 10), STD(color, { metalness: 0.55, roughness: 0.5 })));
  const band = new THREE.Mesh(new THREE.CylinderGeometry(r * 1.01, r * 1.01, 0.8, 10), new THREE.MeshStandardMaterial({ map: hazardTex, flatShading: true })); band.position.y = -h / 2 + 1.2; g.add(band);
  return shadows(g, false);
}
// Lamp head that sits on top of a 9 m mast (origin at the head centre, mast top at y=-0.125).
export function lampHead() { return shadows(new THREE.Mesh(new THREE.BoxGeometry(1.4, 0.25, 0.5), STD(0x3c3f41)), false); }
// Jersey barrier segment: collider half (0.22, 0.405, 1.95).
const jerseyGeo = (() => { const s = new THREE.Shape(); s.moveTo(-0.3, 0); s.lineTo(0.3, 0); s.lineTo(0.3, 0.08); s.lineTo(0.14, 0.33); s.lineTo(0.1, 0.81); s.lineTo(-0.1, 0.81); s.lineTo(-0.14, 0.33); s.lineTo(-0.3, 0.08);
  const g = new THREE.ExtrudeGeometry(s, { depth: 3.9, bevelEnabled: false }); g.translate(0, -0.405, -1.95); return g; })();
export function jersey() { return shadows(new THREE.Mesh(jerseyGeo, concreteMat)); }
// Ramp / kicker slab: collider is a box of full size (w,h,l), already tilted by the game.
export function ramp(w, h, l) { return shadows(new THREE.Mesh(new THREE.BoxGeometry(w, h, l), STD(0x77736b, { roughness: 0.9 }))); }
// Hangar: collider box half (17, 6, 11) centred at y=6; origin of this model is on the GROUND under that centre. Door faces +z.
export function hangar() {
  const hg = new THREE.Group();
  const walls = new THREE.Mesh(new THREE.BoxGeometry(34, 7, 22), STD(0x8c9192, { metalness: 0.3, roughness: 0.6 })); walls.position.y = 3.5; hg.add(walls);
  const roof = new THREE.Mesh(new THREE.CylinderGeometry(11.6, 11.6, 34.4, 10, 1, false, 0, Math.PI), STD(0x6f7476, { metalness: 0.4, roughness: 0.55 })); roof.rotation.z = Math.PI / 2; roof.rotation.x = Math.PI / 2; roof.scale.set(1, 1, 0.42); roof.position.y = 7; hg.add(roof);
  const door = new THREE.Mesh(new THREE.PlaneGeometry(14, 6), STD(0x4b5052)); door.position.set(0, 3, 11.02); hg.add(door);
  return shadows(hg);
}
// Observation tower on 4 legs (no collider), origin on the ground.
export function tower() {
  const tw = new THREE.Group(); const legM = STD(0x55595b, { metalness: 0.5 });
  for (const [x, z] of [[-1.5, -1.5], [1.5, -1.5], [-1.5, 1.5], [1.5, 1.5]]) { const l = new THREE.Mesh(new THREE.BoxGeometry(0.3, 10, 0.3), legM); l.position.set(x, 5, z); tw.add(l); }
  const cab = new THREE.Mesh(new THREE.BoxGeometry(5, 3, 5), STD(0xb9b4a6)); cab.position.y = 11.5; tw.add(cab);
  const win = new THREE.Mesh(new THREE.BoxGeometry(5.05, 1.1, 5.05), STD(0x2a3236, { roughness: 0.15, metalness: 0.6 })); win.position.y = 11.9; tw.add(win);
  return shadows(tw, false);
}
// 40 ft shipping container: collider half (1.22, 1.3, 6.06), origin at centre.
export function container(color) { return shadows(new THREE.Mesh(new THREE.BoxGeometry(2.44, 2.6, 12.12), STD(color, { roughness: 0.7, metalness: 0.2 }))); }
// Dynamic props (origin at collider centre): cone = cannon Cylinder(0.04,0.18,0.62); drum = Cylinder(0.29,0.29,0.88);
// tyre = Cylinder(0.4,0.4,0.22) (axis vertical, lying flat).
export function cone() { const g = new THREE.Group(); g.add(new THREE.Mesh(new THREE.ConeGeometry(0.17, 0.62, 8), STD(0xd9612a, { roughness: 0.6 })));
  const b = new THREE.Mesh(new THREE.CylinderGeometry(0.075, 0.1, 0.09, 8), STD(0xe8e6de, { roughness: 0.6 })); b.position.y = 0.07; g.add(b);
  const base = new THREE.Mesh(new THREE.BoxGeometry(0.38, 0.03, 0.38), STD(0x2a2a28)); base.position.y = -0.31; g.add(base); return shadows(g); }
export function drum() { return shadows(new THREE.Mesh(new THREE.CylinderGeometry(0.29, 0.29, 0.88, 12), STD(0x2f5a8a, { roughness: 0.55 }))); }
const tyreGeo = (() => { const g = new THREE.TorusGeometry(0.29, 0.11, 6, 12); g.rotateX(Math.PI / 2); return g; })();
export function tyre() { return shadows(new THREE.Mesh(tyreGeo, STD(PALETTE.rubber, { roughness: 0.95 }))); }
// Non-colliding scenery outside the pad (|x|>120 or |z|>150): trees, hills, fences, buildings far away.
export function scenery(scene) {
  const n = 420; const tg = new THREE.ConeGeometry(2.4, 9, 6); tg.translate(0, 4.5, 0);
  const inst = new THREE.InstancedMesh(tg, STD(0x46553a), n); const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), s = new THREE.Vector3(), p = new THREE.Vector3();
  for (let i = 0; i < n; i++) { const a = Math.random() * Math.PI * 2, r = rnd(165, 260); p.set(Math.cos(a) * r, 0, Math.sin(a) * r); const k = rnd(0.7, 1.6); s.set(k, k * rnd(0.8, 1.3), k); q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), rnd(0, 6)); m4.compose(p, q, s); inst.setMatrixAt(i, m4); }
  scene.add(inst);
  const hm = STD(0x6c7258);
  for (let i = 0; i < 16; i++) { const a = i / 16 * Math.PI * 2 + rnd(-.1, .1), r = rnd(300, 360); const h = new THREE.Mesh(new THREE.IcosahedronGeometry(rnd(40, 80), 1), hm); h.scale.y = rnd(0.18, 0.32); h.position.set(Math.cos(a) * r, -6, Math.sin(a) * r); scene.add(h); }
}
