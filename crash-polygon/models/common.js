// Shared ground truth for every model module. Read SPEC.md before changing anything here.
import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js';
export { THREE };

// Chassis frame: +z forward, +y up, +x = car's LEFT. Origin = rigid-body centre, CG metres above flat ground at rest.
export const CG = 0.33 + 0.30 - 9.82 / (4 * 38) + 0.10;   // ≈ 0.665
export const ZF = 2.15, ZR = -2.15;                        // bumper tips
export const WHEEL_R = 0.33, WHEEL_W = 0.22;
export const WHEELS = [                                    // wheel centres (x,z); f = front (steered)
  { x: 0.79, z: 1.33, f: 1 }, { x: -0.79, z: 1.33, f: 1 },
  { x: 0.79, z: -1.28, f: 0 }, { x: -0.79, z: -1.28, f: 0 },
];
// Convert a height above ground (how the body was designed) into chassis-frame y.
export const gy = h => h - CG;

// Key body stations (z, metres): useful anchors for anything placed in or under the body.
export const STATIONS = {
  frontBumper: 2.15, grille: 2.13, radiatorZone: 1.95, frontAxle: 1.33, hoodRear: 0.97,
  firewall: 0.95, windshieldBase: 0.95, bPillar: -0.34, rearAxle: -1.28, trunkLid: -1.62, rearBumper: -2.15,
};
// Body envelope helpers (ground heights): floor ≈0.22, belt ≈0.82, hood top ≈0.90, roof ≈1.40, half width ≈0.88.
export const BODY = { floorH: 0.22, beltH: 0.82, hoodH: 0.90, roofH: 1.40, halfW: 0.88, halfWInner: 0.80 };

export const PALETTE = {
  steel: 0x7d8286, darkSteel: 0x3e4245, alu: 0xa9adb0, castIron: 0x4a4744, rubber: 0x1b1b1a,
  plasticBlack: 0x222221, hoseBlack: 0x161615, engineGrey: 0x5c5f60, rust: 0x6b4a33,
  oil: 0x0d0b08, coolant: 0x5aa86a, fuel: 0xb7a46a, dummy: 0xd8a531, seat: 0x2a2b2c, carpet: 0x232220,
  concrete: 0x9a968d, hazard: 0xe3ae1c,
};
export function STD(color, o = {}) {
  return new THREE.MeshStandardMaterial(Object.assign({ color, roughness: 0.8, metalness: 0.0, flatShading: true }, o));
}
export const rnd = (a = 0, b = 1) => a + Math.random() * (b - a);
export const clamp = (x, a, b) => (x < a ? a : x > b ? b : x);

// Canvas texture helper (sRGB, repeat optional). No text: the game shows no lettering anywhere.
export function canvasTex(w, h, draw, repeat) {
  const c = document.createElement('canvas'); c.width = w; c.height = h; draw(c.getContext('2d'), w, h);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8;
  if (repeat) t.wrapS = t.wrapT = THREE.RepeatWrapping; return t;
}

// Body cross-section at station z (ground heights, metres). Same numbers the game lofts the body from.
// yb: underside, ybelt: belt line, ytop: hood/roof/trunk top, w: half width at the side, wt: half width at the top edge.
const lerp = (a, b, t) => a + (b - a) * t;
function pw(z, k) { if (z <= k[0][0]) return k[0][1]; for (let i = 1; i < k.length; i++) { if (z <= k[i][0]) { const t = (z - k[i - 1][0]) / (k[i][0] - k[i - 1][0]); return lerp(k[i - 1][1], k[i][1], t); } } return k[k.length - 1][1]; }
export function bodySection(z) {
  const yb = pw(z, [[-2.15, 0.36], [-1.95, 0.24], [1.85, 0.22], [2.15, 0.34]]);
  const ytop = pw(z, [[-2.15, 0.84], [-2.0, 0.97], [-1.62, 1.0], [-1.0, 1.36], [-0.55, 1.41], [0.15, 1.40], [0.95, 0.96], [1.85, 0.87], [2.15, 0.74]]);
  const ybelt = Math.min(pw(z, [[-2.15, 0.76], [-2.0, 0.9], [2.0, 0.8], [2.15, 0.66]]), ytop - 0.03);
  const w = pw(z, [[-2.15, 0.79], [-2.0, 0.87], [-1.6, 0.89], [1.6, 0.885], [2.0, 0.84], [2.15, 0.74]]);
  const c = pw(z, [[-2.15, 0], [-1.62, 0], [-1.0, 1], [0.15, 1], [0.95, 0], [2.15, 0]]);
  return { yb, ytop, ybelt, w, wt: lerp(w - 0.07, 0.66, c) };
}
// Wheel arch: arch top height at z (ground), or -1 outside the arches. Arch radius 0.45 around each axle.
export function archTop(z) { let a = -1; for (const zw of [1.33, -1.28]) { const d = Math.abs(z - zw); if (d < 0.45) a = Math.max(a, 0.33 + Math.sqrt(0.45 * 0.45 - d * d) * 0.93); } return a; }
