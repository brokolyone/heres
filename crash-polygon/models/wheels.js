// Wheels, tyres, brakes and suspension.
// OWNER: wheels agent. Interface: see SPEC.md §Car modules.
import { THREE, WHEELS, WHEEL_R, WHEEL_W, STD, PALETTE } from './common.js';

// One rolling wheel assembly (tyre + rim + brake disc...). Lives in the SCENE (world space): the game copies the
// cannon wheel transform onto `group` every frame. Local frame: axle along x, wheel centre at origin.
export function createWheel(ctx, i) {
  const g = new THREE.Group(); g.name = 'wheel' + i;
  const tyre = new THREE.Mesh(new THREE.CylinderGeometry(WHEEL_R, WHEEL_R, WHEEL_W, 16), STD(PALETTE.rubber, { roughness: 0.95 })); tyre.rotation.z = Math.PI / 2; g.add(tyre);
  const rim = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.2, WHEEL_W + 0.005, 8), STD(0x9a9ea0, { metalness: 0.7, roughness: 0.35 })); rim.rotation.z = Math.PI / 2; g.add(rim);
  const hub = new THREE.Mesh(new THREE.BoxGeometry(0.23, 0.06, 0.3), STD(0x5f6365, { metalness: 0.6 })); g.add(hub);
  g.traverse(o => { if (o.isMesh) o.castShadow = true; });
  return {
    group: g,
    // state: ctx.car.wheelState[i] = {dmg, broken, camber}; wi = cannon WheelInfo (suspensionLength, steering, rotation, skidInfo)
    update(dt, state, wi) {},
    onBreak() {},             // called right before the assembly becomes a loose debris body
    dispose() { g.traverse(o => o.geometry && o.geometry.dispose()); },
  };
}

// Parts fixed to the chassis (struts, springs, control arms, knuckles). Added to ctx.group (chassis frame).
export function createSuspension(ctx) {
  const root = new THREE.Group(); root.name = 'suspension'; ctx.group.add(root);
  return { root, onImpact(ev) {}, update(dt) {}, dispose() { root.traverse(o => o.geometry && o.geometry.dispose()); } };
}
