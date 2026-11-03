// Fluids and damage atmosphere: oil/coolant/fuel leaks, puddles on the ground, drips, steam, smoke, fire.
// OWNER: fluids agent. Interface: see SPEC.md §Car modules.
import { THREE, CG, gy, rnd } from './common.js';

export function createFluids(ctx) {
  const car = ctx.car; let smokeT = 0; const w = new THREE.Vector3();
  return {
    onImpact(ev) {},
    update(dt) {
      // baseline (moved from index.html): engine smoke / steam once the engine is hurt
      if (car.engine < 0.65) {
        smokeT += dt * (1 - car.engine) * 14;
        while (smokeT > 1) {
          smokeT -= 1; w.set(rnd(-.3, .3), gy(0.95), 1.45); ctx.group.localToWorld(w); const dark = car.engine < 0.2;
          ctx.fx.puff(w.clone(), { x: rnd(-.3, .3), y: rnd(.8, 1.6), z: rnd(-.3, .3) }, { life: rnd(2, 4), s0: 0.3, s1: 2.4, a: dark ? 0.4 : 0.22, c: dark ? 0.22 : 0.85 });
        }
      }
    },
    dispose() {},
  };
}
