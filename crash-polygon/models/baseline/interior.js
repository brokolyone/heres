// Cabin interior, crash-test dummies, underbody (floor pan, rails, exhaust, fuel tank).
// OWNER: interior/underbody agent. Interface: see SPEC.md §Car modules.
import { THREE, CG, gy, STD, PALETTE } from '../common.js';

export function createInterior(ctx) {
  const inner = new THREE.Group(); inner.name = 'interior'; inner.position.y = -CG; ctx.group.add(inner);  // children use ground heights
  const seatM = STD(PALETTE.seat), dumM = STD(PALETTE.dummy, { roughness: 0.5 }), trimM = STD(0x1e1e1d, { roughness: 0.6 });
  for (const x of [0.4, -0.4]) {
    const s = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.12, 0.5), seatM); s.position.set(x, 0.48, -0.25); inner.add(s);
    const b = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.65, 0.12), seatM); b.position.set(x, 0.85, -0.55); b.rotation.x = -0.18; inner.add(b);
  }
  const torso = new THREE.Mesh(new THREE.BoxGeometry(0.38, 0.5, 0.24), dumM); torso.position.set(0.4, 0.82, -0.38); torso.rotation.x = -0.15; inner.add(torso);
  const head = new THREE.Mesh(new THREE.IcosahedronGeometry(0.11, 1), dumM); head.position.set(0.4, 1.18, -0.42); inner.add(head);
  const sw = new THREE.Mesh(new THREE.TorusGeometry(0.17, 0.022, 5, 14), trimM); sw.position.set(0.4, 0.95, 0.32); sw.rotation.x = -0.45; inner.add(sw);
  const dash = new THREE.Mesh(new THREE.BoxGeometry(1.5, 0.22, 0.35), seatM); dash.position.set(0, 0.86, 0.65); inner.add(dash);
  return {
    root: inner,
    onImpact(ev) {},
    update(dt) {},
    dispose() { inner.traverse(o => o.geometry && o.geometry.dispose()); },
  };
}
