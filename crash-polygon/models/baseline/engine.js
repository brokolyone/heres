// Engine bay: engine block, gearbox, radiator, battery, intake, exhaust manifold, hoses, firewall, rails.
// OWNER: engine agent. Interface: see SPEC.md §Car modules.
import { THREE, CG, gy, STD, PALETTE } from '../common.js';

export function createEngineBay(ctx) {
  const root = new THREE.Group(); root.name = 'engineBay'; ctx.group.add(root);
  // baseline: nothing modelled yet
  return {
    root,
    onImpact(ev) {},          // ev: {pL, nL, depth, v, frontal, rear, side, scrape}
    update(dt) {},
    dispose() { root.traverse(o => o.geometry && o.geometry.dispose()); },
  };
}
