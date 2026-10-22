// Interior of the hollow-stump house, drawn to match the outside: open splintered top with the
// night sky and moon, a round plank door on the left, the plank patches on the left wall, the
// small window with the tin patch on the right, and the stove whose pipe leaves through the
// upper right wall where the chimney sticks out of the house.
// usage: node interior.js <buildDir>
// Writes static_interior.svg, iparts/<id>.svg and iparts.json (same sprite scheme as the island).
const fs = require('fs');
const path = require('path');

const dir = process.argv[2];
let seed = 7741;
const R = () => ((seed = (seed * 16807) % 2147483647) - 1) / 2147483646;
const r = (a, b) => a + (b - a) * R();
const f = v => (+v).toFixed(1);
const pick = a => a[Math.floor(R() * a.length)];

const W = 1600, H = 1000;
const junction = x => 770 + 115 * ((x - 800) / 800) ** 2; // where the back wall meets the floor
const FLOOR = 905; // the gnome's feet

const defs = `<defs>
<linearGradient id="i-sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0b2328"/><stop offset="1" stop-color="#1d4a4c"/></linearGradient>
<radialGradient id="i-moon" cx="0.4" cy="0.4" r="0.7"><stop offset="0" stop-color="#f6f2de"/><stop offset="0.7" stop-color="#d9d4ba"/><stop offset="1" stop-color="#b8b396"/></radialGradient>
<radialGradient id="i-moonhalo"><stop offset="0" stop-color="#f6f2de" stop-opacity="0.35"/><stop offset="1" stop-color="#f6f2de" stop-opacity="0"/></radialGradient>
<linearGradient id="i-wall" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="#1c120b"/><stop offset="0.18" stop-color="#4a3322"/><stop offset="0.5" stop-color="#6e5034"/>
  <stop offset="0.82" stop-color="#5a3f28"/><stop offset="1" stop-color="#1e140c"/></linearGradient>
<linearGradient id="i-wallv" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#000" stop-opacity="0.55"/><stop offset="0.35" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity="0.25"/></linearGradient>
<linearGradient id="i-floor" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3e2b1b"/><stop offset="1" stop-color="#22160d"/></linearGradient>
<linearGradient id="i-plank" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#8a6a46"/><stop offset="0.5" stop-color="#6e5234"/><stop offset="1" stop-color="#4e3a24"/></linearGradient>
<linearGradient id="i-plankv" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#5a4128"/><stop offset="0.5" stop-color="#7a5c3c"/><stop offset="1" stop-color="#4a3420"/></linearGradient>
<radialGradient id="i-iron" cx="0.35" cy="0.3" r="0.8"><stop offset="0" stop-color="#5a4a40"/><stop offset="0.6" stop-color="#2c2420"/><stop offset="1" stop-color="#140f0c"/></radialGradient>
<radialGradient id="i-brass" cx="0.35" cy="0.3" r="0.8"><stop offset="0" stop-color="#e8c47e"/><stop offset="0.6" stop-color="#a87a3a"/><stop offset="1" stop-color="#5a3a16"/></radialGradient>
<radialGradient id="i-fire" cx="0.5" cy="0.7" r="0.7"><stop offset="0" stop-color="#fff2b0"/><stop offset="0.35" stop-color="#ffb347"/><stop offset="0.75" stop-color="#d0501a"/><stop offset="1" stop-color="#5a1a08"/></radialGradient>
<radialGradient id="i-warm"><stop offset="0" stop-color="#ffcf7a" stop-opacity="0.55"/><stop offset="0.5" stop-color="#f0a050" stop-opacity="0.18"/><stop offset="1" stop-color="#f0a050" stop-opacity="0"/></radialGradient>
<radialGradient id="i-cool"><stop offset="0" stop-color="#cfe6e0" stop-opacity="0.32"/><stop offset="1" stop-color="#cfe6e0" stop-opacity="0"/></radialGradient>
<linearGradient id="i-shaft" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e8f0e4" stop-opacity="0.28"/><stop offset="1" stop-color="#e8f0e4" stop-opacity="0"/></linearGradient>
<linearGradient id="i-glass" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#122c33"/><stop offset="1" stop-color="#29585a"/></linearGradient>
<radialGradient id="i-jar"><stop offset="0" stop-color="#d4ffb0" stop-opacity="0.9"/><stop offset="0.5" stop-color="#8fd88a" stop-opacity="0.35"/><stop offset="1" stop-color="#8fd88a" stop-opacity="0"/></radialGradient>
<radialGradient id="i-vignette" cx="0.5" cy="0.55" r="0.75"><stop offset="0.5" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#050302" stop-opacity="0.75"/></radialGradient>
<filter id="i-grainv" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency="0.09 0.004" numOctaves="3" seed="4"/>
  <feColorMatrix type="matrix" values="0 0 0 0 0.08  0 0 0 0 0.05  0 0 0 0 0.02  0 0 0 2.2 -1.0"/><feComposite in2="SourceAlpha" operator="in"/></filter>
<filter id="i-grainh" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency="0.006 0.12" numOctaves="3" seed="9"/>
  <feColorMatrix type="matrix" values="0 0 0 0 0.08  0 0 0 0 0.05  0 0 0 0 0.02  0 0 0 2 -0.9"/><feComposite in2="SourceAlpha" operator="in"/></filter>
<filter id="i-speck" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency="0.8" numOctaves="2" seed="2"/>
  <feColorMatrix type="matrix" values="0 0 0 0 0.1  0 0 0 0 0.07  0 0 0 0 0.04  0 0 0 1.8 -0.8"/><feComposite in2="SourceAlpha" operator="in"/></filter>
<filter id="i-rough" x="-5%" y="-5%" width="110%" height="110%"><feTurbulence type="fractalNoise" baseFrequency="0.05" numOctaves="2" seed="3" result="n"/>
  <feDisplacementMap in="SourceGraphic" in2="n" scale="4" xChannelSelector="R" yChannelSelector="G"/></filter>
<filter id="i-moss" x="-10%" y="-30%" width="120%" height="160%"><feTurbulence type="fractalNoise" baseFrequency="0.3" numOctaves="3" seed="5" result="n"/>
  <feDisplacementMap in="SourceGraphic" in2="n" scale="8" xChannelSelector="R" yChannelSelector="G"/></filter>
<filter id="i-blur2"><feGaussianBlur stdDeviation="2"/></filter>
<filter id="i-blur6" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="6"/></filter>
<filter id="i-blur20" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="20"/></filter>
<filter id="i-grain" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="7"/>
  <feColorMatrix type="matrix" values="0 0 0 0 0.45  0 0 0 0 0.4  0 0 0 0 0.3  0 0 0 0.08 0"/></filter>
<clipPath id="i-windowclip"><path d="M1046,306 L1158,298 L1164,418 L1050,424 Z"/></clipPath>
</defs>`;

const out = [];
const add = s => out.push(s);
const parts = [];
const part = (id, svg, anim, opts = {}) => parts.push({ id, svg, anim, origin: opts.origin || null, vars: opts.vars || {}, front: !!opts.front, layer: 'interior', pos: parts.length, parent: null, below: false });

// ---------------- sky through the open top ----------------
add(`<rect width="${W}" height="420" fill="url(#i-sky)"/>`);
for (let i = 0; i < 140; i++) add(`<circle cx="${f(r(0, W))}" cy="${f(r(0, 300))}" r="${f(r(0.4, 1.4))}" fill="#eef2dc" opacity="${f(r(0.2, 0.8))}"/>`);
add(`<circle cx="1360" cy="70" r="220" fill="url(#i-moonhalo)"/>`);
add(`<circle cx="1360" cy="70" r="105" fill="url(#i-moon)"/>`);
for (let i = 0; i < 9; i++) { const a = r(0, 6.28), d = r(10, 85), rr = r(6, 18); add(`<circle cx="${f(1360 + Math.cos(a) * d)}" cy="${f(70 + Math.sin(a) * d)}" r="${f(rr)}" fill="#a9a48a" opacity="0.35"/>`); }
add(`<ellipse cx="500" cy="150" rx="420" ry="26" fill="#9ab8aa" opacity="0.12" filter="url(#i-blur20)"/>`);

// ---------------- back wall (inside of the stump) ----------------
let rim = 'M0,0 L0,250';
for (let x = 0; x <= W; x += 40) {
  const base = 205 + 40 * Math.abs((x - 800) / 800) ** 1.5 + r(-10, 10);
  const spike = R() < 0.35 ? r(30, 90) : r(0, 18);
  rim += ` L${f(x - 14)},${f(base)} L${f(x)},${f(base - spike)} L${f(x + 12)},${f(base + r(-4, 6))}`;
}
const wallTop = rim.replace('M0,0 L0,250', 'M0,260');
const wallD = `${wallTop} L${W},260 L${W},${H} L0,${H} Z`;
add(`<path d="${wallD}" fill="url(#i-wall)"/>`);
add(`<path d="${wallD}" fill="#000" filter="url(#i-grainv)" opacity="0.9"/>`);
add(`<path d="${wallD}" fill="url(#i-wallv)"/>`);
// fibres and cracks
for (let i = 0; i < 160; i++) {
  const x = r(0, W), y0 = r(220, 600), len = r(80, 420);
  add(`<path d="M${f(x)},${f(y0)} q${f(r(-6, 6))},${f(len / 2)} ${f(r(-4, 4))},${f(len)}" stroke="${pick(['#2a1c10', '#3a2818', '#8a6a46'])}" stroke-width="${f(r(0.5, 1.8))}" fill="none" opacity="${f(r(0.15, 0.45))}"/>`);
}
for (const [x, y, h] of [[700, 300, 260], [980, 260, 220], [250, 330, 300], [1320, 300, 180]]) {
  let d = `M${x},${y}`; let cx = x;
  for (let k = 1; k <= 8; k++) { cx += r(-6, 6); d += ` L${f(cx)},${f(y + (h * k) / 8)}`; }
  add(`<path d="${d}" stroke="#0e0905" stroke-width="3" fill="none" stroke-linejoin="round"/>`);
}
// splintered rim lit by the moon
add(`<path d="${wallTop}" fill="none" stroke="#c9b48a" stroke-width="3" opacity="0.5"/>`);
add(`<path d="${wallTop}" fill="none" stroke="#1a0f08" stroke-width="1.2" opacity="0.8" transform="translate(0,4)"/>`);

// cross beam (a branch) over the opening, from which the lamp hangs
add(`<path d="M300,232 C520,214 900,214 1300,240" stroke="#1a110a" stroke-width="22" fill="none" stroke-linecap="round"/>`);
add(`<path d="M300,232 C520,214 900,214 1300,240" stroke="#5a3e26" stroke-width="17" fill="none" stroke-linecap="round" filter="url(#i-rough)"/>`);
add(`<path d="M300,226 C520,208 900,208 1300,234" stroke="#c9a678" stroke-width="2.5" fill="none" opacity="0.4"/>`);
add(`<path d="M640,222 q16,-22 34,-30 M1080,226 q10,-16 26,-20" stroke="#4a3220" stroke-width="5" fill="none" stroke-linecap="round"/>`);

// ---------------- floor ----------------
let jun = `M0,${f(junction(0))}`;
for (let x = 20; x <= W; x += 20) jun += ` L${x},${f(junction(x))}`;
const floorD = `${jun} L${W},${H} L0,${H} Z`;
add(`<path d="${floorD}" fill="url(#i-floor)"/>`);
for (let i = -14; i <= 14; i++) {
  const x0 = 800 + i * 70, x1 = 800 + i * 160;
  add(`<path d="M${f(x0)},${f(junction(x0))} L${f(x1)},${H}" stroke="#1a110a" stroke-width="2" opacity="0.6"/>`);
  add(`<path d="M${f(x0 + 3)},${f(junction(x0 + 3))} L${f(x1 + 7)},${H}" stroke="#8a6a46" stroke-width="1" opacity="0.18"/>`);
}
add(`<path d="${floorD}" fill="#000" filter="url(#i-grainh)" opacity="0.6"/>`);
add(`<path d="${jun}" stroke="#0e0905" stroke-width="5" fill="none" opacity="0.7"/>`);
// moss and roots creeping along the wall foot
for (let i = 0; i < 70; i++) {
  const x = r(0, W), y = junction(x);
  add(`<ellipse cx="${f(x)}" cy="${f(y - r(0, 8))}" rx="${f(r(6, 26))}" ry="${f(r(3, 9))}" fill="${pick(['#4f5a2a', '#5e6a30', '#3e4a22'])}" opacity="${f(r(0.4, 0.8))}" filter="url(#i-moss)"/>`);
}
for (let i = 0; i < 6; i++) {
  const x = r(100, 1500), y = r(380, 700);
  add(`<path d="M${f(x)},${f(y)} c${f(r(-20, 20))},30 ${f(r(-30, 30))},50 ${f(r(-10, 10))},${f(r(80, 140))}" stroke="#3a2614" stroke-width="${f(r(3, 6))}" fill="none" stroke-linecap="round" opacity="0.8"/>`);
}

// ---------------- rug ----------------
const rugC = ['#6d3a22', '#a8742e', '#3e5a52', '#8a4a2a', '#c9a24a', '#4a3a5a'];
for (let k = 0; k < 7; k++) {
  const rx = 400 - k * 52, ry = 72 - k * 9.5;
  add(`<ellipse cx="800" cy="905" rx="${rx}" ry="${f(ry)}" fill="${rugC[k % rugC.length]}" opacity="0.92"/>`);
  add(`<ellipse cx="800" cy="905" rx="${rx - 6}" ry="${f(ry - 1.5)}" fill="none" stroke="#1a0f08" stroke-width="1" stroke-dasharray="3 4" opacity="0.4"/>`);
}
add(`<ellipse cx="800" cy="905" rx="400" ry="72" fill="#000" filter="url(#i-speck)" opacity="0.7"/>`);
for (let a = 0; a < Math.PI; a += 0.035) add(`<path d="M${f(800 + Math.cos(a) * 400)},${f(905 + Math.sin(a) * 72)} l${f(Math.cos(a) * 9)},${f(Math.sin(a) * 6 + 3)}" stroke="#c9a678" stroke-width="1.2" opacity="0.6"/>`);

// ---------------- left: door, coat hook, plank patches, dried mushroom garland ----------------
{ // round-topped plank door set into the curved wall
  const x0 = 95, x1 = 285, top = 585, base = FLOOR + 5, cx = (x0 + x1) / 2, rr = (x1 - x0) / 2;
  const arch = `M${x0},${base} L${x0},${top} A${rr},${rr} 0 0 1 ${x1},${top} L${x1},${base} Z`;
  add(`<path d="M${x0 - 16},${base} L${x0 - 16},${top} A${rr + 16},${rr + 16} 0 0 1 ${x1 + 16},${top} L${x1 + 16},${base} Z" fill="#24170d"/>`);
  add(`<path d="${arch}" fill="url(#i-plankv)"/>`);
  for (let x = x0 + 24; x < x1; x += 24) add(`<path d="M${x},${top - rr + 6} L${x},${base}" stroke="#2a1c10" stroke-width="2.2"/>`);
  add(`<path d="${arch}" fill="#000" filter="url(#i-grainv)" opacity="0.8"/>`);
  for (const y of [640, 820]) {
    add(`<rect x="${x0 + 4}" y="${y}" width="${x1 - x0 - 8}" height="14" rx="2" fill="#2e2620" stroke="#120c08"/>`);
    for (let x = x0 + 16; x < x1 - 8; x += 26) add(`<circle cx="${x}" cy="${y + 7}" r="2.6" fill="#5a4a40"/><circle cx="${x - 0.8}" cy="${y + 6}" r="0.9" fill="#bfae94"/>`);
  }
  add(`<circle cx="${x1 - 26}" cy="740" r="11" fill="none" stroke="#6a5a4a" stroke-width="4"/><circle cx="${x1 - 26}" cy="728" r="4" fill="#3a2e26"/>`);
  add(`<path d="${arch}" fill="none" stroke="#9fd0c8" stroke-width="2" opacity="0.25"/>`);
  add(`<path d="${arch}" fill="none" stroke="#120a05" stroke-width="5" opacity="0.8"/>`);
  add(`<rect x="${x0 - 22}" y="${base - 8}" width="${x1 - x0 + 44}" height="14" rx="3" fill="#4a3a2a"/>`);
}
// coat hook with the spare cap and a striped scarf
add(`<rect x="300" y="575" width="70" height="12" rx="3" fill="#5a3e26" stroke="#1a0f08"/><path d="M318,587 q-3,10 4,14 M352,587 q-3,10 4,14" stroke="#3a2e26" stroke-width="3" fill="none"/>`);
add(`<path d="M312,600 C300,650 306,700 300,740 L318,742 C324,700 318,650 330,602 Z" fill="#8a3a2a"/>`);
for (let y = 612; y < 740; y += 18) add(`<path d="M${f(300 + (y - 600) * 0.0)},${y} l26,1" stroke="#d9c49a" stroke-width="5" opacity="0.8" transform="rotate(-4 312 ${y})"/>`);
add(`<path d="M300,738 l4,14 M308,740 l2,14 M316,741 l1,13" stroke="#8a3a2a" stroke-width="2"/>`);
add(`<path d="M352,587 C336,592 330,612 334,632 C338,650 352,660 368,658 C384,654 390,636 386,618 C382,600 368,588 352,587 Z" fill="#e6dfc8" stroke="#a89c80"/>`);
add(`<path d="M334,630 C346,640 372,642 388,628 L388,636 C372,650 346,648 334,638 Z" fill="#f2eedf" stroke="#a89c80" stroke-width="0.8"/>`);
add(`<path d="M352,590 C352,612 354,630 352,646" stroke="#b9b09a" stroke-width="1" stroke-dasharray="2 2" fill="none"/>`);
add(`<path d="M386,618 C398,636 400,662 392,684" stroke="#e6dfc8" stroke-width="9" fill="none" stroke-linecap="round"/><circle cx="391" cy="690" r="9" fill="#f5f1e3" stroke="#c9bfa3"/>`);
add(`<path d="M338,606 C342,596 350,592 358,592" stroke="#fffbe8" stroke-width="2" fill="none" opacity="0.7"/>`);
// the plank patches seen from inside, with moonlight leaking through the gaps
for (const [x, y, w, h, a] of [[372, 350, 120, 34, -4], [366, 392, 130, 30, 3], [376, 430, 112, 32, -2]]) {
  add(`<g transform="rotate(${a} ${x + w / 2} ${y + h / 2})"><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="2" fill="url(#i-plank)" stroke="#1a0f08" stroke-width="1.2"/>
  <rect x="${x}" y="${y}" width="${w}" height="${h}" fill="#000" filter="url(#i-grainh)" opacity="0.7"/>
  <circle cx="${x + 8}" cy="${y + h / 2}" r="2.6" fill="#5a4a40"/><circle cx="${x + w - 8}" cy="${y + h / 2}" r="2.6" fill="#5a4a40"/></g>`);
}
add(`<path d="M380,388 L486,384 M378,428 L490,426" stroke="#cfe6e0" stroke-width="1.5" opacity="0.55"/>`);
// garland of dried mushrooms
add(`<path d="M120,300 Q270,350 430,312" stroke="#c9b48a" stroke-width="1.2" fill="none"/>`);
for (let t = 0.08; t < 1; t += 0.11) {
  const x = 120 + (430 - 120) * t, y = 300 + 50 * 4 * t * (1 - t) * 0.9 + (t > 0.5 ? -(t - 0.5) * 30 : 0);
  add(`<path d="M${f(x)},${f(y)} l0,10" stroke="#c9b48a" stroke-width="0.8"/><path d="M${f(x - 9)},${f(y + 16)} Q${f(x)},${f(y + 2)} ${f(x + 9)},${f(y + 16)} Z" fill="${pick(['#8a5a2b', '#a8742e', '#6d4a2a'])}"/><path d="M${f(x)},${f(y + 15)} l0,8" stroke="#d9c49a" stroke-width="2"/>`);
}

// ---------------- bed under a shelf ----------------
{
  add(`<rect x="430" y="470" width="290" height="12" rx="2" fill="url(#i-plank)" stroke="#1a0f08"/><path d="M450,482 l10,26 M700,482 l-10,26" stroke="#3a2614" stroke-width="5"/>`);
  // jars and books on the shelf
  add(`<rect x="452" y="420" width="34" height="50" rx="6" fill="#9fc8b8" opacity="0.35" stroke="#d9e6dc" stroke-width="1"/><rect x="456" y="414" width="26" height="8" rx="2" fill="#6d4a2a"/>`);
  add(`<rect x="500" y="430" width="26" height="40" rx="5" fill="#c9a24a" opacity="0.45" stroke="#e6d9b5"/><rect x="503" y="424" width="20" height="7" rx="2" fill="#5a3a20"/>`);
  for (const [x, w, h, c] of [[540, 12, 44, '#6d3a22'], [553, 10, 40, '#3e5a52'], [564, 14, 46, '#8a6a2a'], [579, 11, 38, '#4a3a5a']]) add(`<rect x="${x}" y="${470 - h}" width="${w}" height="${h}" fill="${c}" stroke="#1a0f08" stroke-width="0.8"/><path d="M${x + 2},${470 - h + 6} h${w - 4}" stroke="#d9c49a" opacity="0.5"/>`);
  add(`<path d="M640,470 q-10,-20 6,-34 q14,8 8,34 Z" fill="#7a8a3a"/><rect x="630" y="452" width="30" height="18" rx="3" fill="#8a4a2a"/>`);
  add(`<rect x="676" y="440" width="10" height="30" fill="#e6dfc8"/>`);
  // bed: a hollowed half-log on stubby legs
  add(`<path d="M420,780 L760,780 L756,850 Q590,872 424,850 Z" fill="#5a3e26" stroke="#1a0f08" stroke-width="2"/>`);
  add(`<path d="M420,780 L760,780 L756,850 Q590,872 424,850 Z" fill="#000" filter="url(#i-grainh)" opacity="0.7"/>`);
  add(`<path d="M424,850 Q590,872 756,850" stroke="#c9a678" stroke-width="2" fill="none" opacity="0.35"/>`);
  for (const x of [440, 740]) add(`<path d="M${x - 9},860 L${x + 9},860 L${x + 6},${FLOOR} L${x - 6},${FLOOR} Z" fill="#3a2818"/>`);
  add(`<path d="M410,700 Q406,640 440,632 Q474,640 470,700 L470,790 L410,790 Z" fill="#5a3e26" stroke="#1a0f08" stroke-width="2"/>`);
  add(`<path d="M430,778 Q590,760 750,778 L752,792 Q590,800 428,792 Z" fill="#d9cdb0"/>`);
  add(`<ellipse cx="490" cy="764" rx="44" ry="18" fill="#efe6cf" stroke="#b8a888"/>`);
  const quilt = ['#8a3a2a', '#a8742e', '#3e5a52', '#c9a24a', '#6d4a5a', '#5e6a30'];
  for (let i = 0; i < 7; i++) for (let j = 0; j < 2; j++) {
    const x = 530 + i * 32, y = 754 + j * 16;
    add(`<rect x="${x}" y="${y}" width="32" height="16" fill="${quilt[(i + j * 3) % quilt.length]}" stroke="#e6d9b5" stroke-width="0.8" stroke-dasharray="2 2"/>`);
  }
  add(`<path d="M530,786 Q640,800 754,786 L754,800 Q640,812 530,800 Z" fill="#6d3a22"/>`);
}

// ---------------- clock on the back wall ----------------
add(`<path d="M820,370 L880,370 L880,450 L850,470 L820,450 Z" fill="#5a3e26" stroke="#1a0f08" stroke-width="2"/><path d="M812,374 L850,340 L888,374 Z" fill="#3a2818" stroke="#1a0f08" stroke-width="2"/>`);
add(`<circle cx="850" cy="405" r="22" fill="#e6dfc8" stroke="#2a1a10" stroke-width="2"/>`);
for (let k = 0; k < 12; k++) { const a = (k / 12) * 6.283; add(`<path d="M${f(850 + Math.cos(a) * 17)},${f(405 + Math.sin(a) * 17)} L${f(850 + Math.cos(a) * 20)},${f(405 + Math.sin(a) * 20)}" stroke="#2a1a10" stroke-width="1.4"/>`); }
add(`<path d="M850,405 L850,391 M850,405 L860,409" stroke="#1a0f08" stroke-width="2" stroke-linecap="round"/>`);
part('pendulum', `<path d="M850,462 L850,540" stroke="#a87a3a" stroke-width="2"/><circle cx="850" cy="546" r="10" fill="url(#i-brass)" stroke="#5a3a16"/>`, 'pendulum', { origin: [850, 462] });

// ---------------- table with a music box, a cup and a candle ----------------
add(`<path d="M910,790 L900,${FLOOR} L940,${FLOOR} L930,790 Z" fill="#4a3220"/><ellipse cx="920" cy="${FLOOR}" rx="40" ry="7" fill="#2a1a10"/>`);
add(`<ellipse cx="920" cy="782" rx="110" ry="22" fill="#5a3e26" stroke="#1a0f08" stroke-width="2"/><ellipse cx="920" cy="776" rx="110" ry="22" fill="#8a6a46"/>`);
for (let k = 1; k < 6; k++) add(`<ellipse cx="920" cy="776" rx="${110 - k * 18}" ry="${f(22 - k * 3.6)}" fill="none" stroke="#5a3e26" stroke-width="1" opacity="0.6"/>`);
add(`<rect x="852" y="742" width="46" height="30" rx="3" fill="#6d3a22" stroke="#1a0f08" stroke-width="1.5"/><rect x="852" y="736" width="46" height="9" rx="2" fill="#8a4a2a" stroke="#1a0f08"/><path d="M862,756 h26 M862,762 h26" stroke="#c9a24a" stroke-width="1" opacity="0.7"/>`);
part('crank', `<path d="M898,754 l12,0" stroke="#a87a3a" stroke-width="2.5"/><path d="M910,754 l0,-10" stroke="#a87a3a" stroke-width="2.5"/><circle cx="910" cy="743" r="2.5" fill="#e8c47e"/>`, 'none', { origin: [904, 754] });
add(`<path d="M960,752 L986,752 L983,776 L963,776 Z" fill="#d9cdb0" stroke="#6a5a4a"/><path d="M986,758 q10,2 0,12" stroke="#d9cdb0" stroke-width="3" fill="none"/>`);
add(`<rect x="936" y="736" width="12" height="38" rx="2" fill="#efe6cf"/><ellipse cx="942" cy="774" rx="14" ry="4" fill="#a87a3a"/><path d="M942,736 l0,-5" stroke="#1a0f08" stroke-width="1.2"/>`);
part('candle', `<circle cx="942" cy="722" r="22" fill="url(#i-warm)"/><path d="M942,712 C946,720 946,726 942,731 C938,726 938,720 942,712 Z" fill="#ffe9a0"/><path d="M942,720 C943.5,724 943.5,727 942,730 C940.5,727 940.5,724 942,720 Z" fill="#ff9a40"/>`, 'candle', { origin: [942, 731] });

// ---------------- right: window, tin patch, stove with kettle and pipe, firewood, ladder ----------------
add(`<path d="M1036,296 L1168,288 L1176,428 L1040,436 Z" fill="#2a1c10" stroke="#120a05" stroke-width="2"/>`);
add(`<path d="M1046,306 L1158,298 L1164,418 L1050,424 Z" fill="url(#i-glass)"/>`);
add(`<g clip-path="url(#i-windowclip)">${Array.from({ length: 14 }, () => `<circle cx="${f(r(1046, 1164))}" cy="${f(r(298, 424))}" r="${f(r(0.5, 1.4))}" fill="#eef2dc" opacity="${f(r(0.3, 0.9))}"/>`).join('')}
  <path d="M1046,404 Q1080,380 1110,396 Q1140,380 1164,392 L1164,430 L1046,430 Z" fill="#0e2226" opacity="0.8"/></g>`);
add(`<path d="M1104,302 L1107,421 M1048,365 L1161,358" stroke="#2a1c10" stroke-width="5"/>`);
add(`<path d="M1056,316 L1058,356" stroke="#e8f0e4" stroke-width="2" opacity="0.4" stroke-linecap="round"/>`);
add(`<path d="M1036,436 L1180,428 L1182,442 L1034,450 Z" fill="#5a3e26" stroke="#1a0f08"/>`);
add(`<path d="M1192,318 L1246,314 L1250,384 L1196,388 Z" fill="#6d5a48" stroke="#2a1a10" stroke-width="1.5" filter="url(#i-rough)"/>`);
for (const [x, y] of [[1198, 322], [1240, 319], [1244, 378], [1201, 381]]) add(`<circle cx="${x}" cy="${y}" r="2" fill="#2a1a10"/>`);
add(`<path d="M1206,388 q2,14 -1,24 M1230,386 q1,10 0,16" stroke="#8c4519" stroke-width="2.5" opacity="0.5" fill="none"/>`);
// stove pipe: up from the stove, elbow, out through the upper right wall (where the chimney is outside)
const pipe = 'M1305,585 L1305,330 Q1305,300 1335,300 L1600,300';
add(`<path d="${pipe}" stroke="#120c08" stroke-width="34" fill="none"/>`);
add(`<path d="${pipe}" stroke="#3a302a" stroke-width="28" fill="none" filter="url(#i-rough)"/>`);
add(`<path d="${pipe}" stroke="#8a7a6a" stroke-width="3" fill="none" opacity="0.45" transform="translate(-8,-6)"/>`);
for (const y of [400, 500]) add(`<rect x="1286" y="${y}" width="38" height="9" rx="2" fill="#2a221c" stroke="#0e0905"/>`);
add(`<rect x="1430" y="282" width="10" height="36" rx="2" fill="#2a221c" stroke="#0e0905"/>`);
add(`<ellipse cx="1540" cy="300" rx="16" ry="30" fill="#2a1c10" stroke="#120a05" stroke-width="3"/>`);
add(`<path d="M1440,318 q4,12 0,26" stroke="#8c4519" stroke-width="3" opacity="0.4" fill="none"/>`);
// potbelly stove
add(`<ellipse cx="1305" cy="${FLOOR}" rx="120" ry="14" fill="#0e0905" opacity="0.6" filter="url(#i-blur6)"/>`);
for (const [x0, x1] of [[1236, 1222], [1374, 1388], [1305, 1305]]) add(`<path d="M${x0},840 Q${(x0 + x1) / 2 + (x1 - x0)},${FLOOR - 30} ${x1},${FLOOR}" stroke="#1a1410" stroke-width="10" fill="none" stroke-linecap="round"/>`);
add(`<path d="M1230,640 L1380,640 L1372,660 Q1410,740 1370,840 L1240,840 Q1200,740 1238,660 Z" fill="url(#i-iron)" stroke="#0a0705" stroke-width="3"/>`);
add(`<path d="M1230,640 L1380,640 L1372,660 Q1410,740 1370,840 L1240,840 Q1200,740 1238,660 Z" fill="#000" filter="url(#i-speck)" opacity="0.6"/>`);
add(`<rect x="1222" y="620" width="166" height="22" rx="4" fill="#2c2420" stroke="#0a0705" stroke-width="2"/><rect x="1240" y="598" width="130" height="24" rx="4" fill="#3a302a" stroke="#0a0705" stroke-width="2"/>`);
add(`<rect x="1228" y="836" width="154" height="16" rx="3" fill="#2c2420" stroke="#0a0705" stroke-width="2"/>`);
add(`<path d="M1252,700 Q1238,740 1250,800" stroke="#8a7a6a" stroke-width="4" fill="none" opacity="0.35" stroke-linecap="round"/>`);
add(`<path d="M1262,705 L1348,705 L1348,790 L1262,790 Z" fill="#1a0f08" stroke="#5a4a40" stroke-width="4"/>`);
part('stovefire', `<path d="M1264,707 L1346,707 L1346,788 L1264,788 Z" fill="url(#i-fire)"/>` +
  [0, 1, 2, 3, 4].map(k => `<path d="M${1270 + k * 16},788 q${f(r(-4, 4))},-22 ${f(r(2, 8))},-40 q4,18 6,40 Z" fill="#fff2b0" opacity="0.8"/>`).join(''), 'fire', { origin: [1305, 788] });
add(`<path d="M1262,722 h86 M1262,740 h86 M1262,758 h86 M1262,776 h86" stroke="#1a1410" stroke-width="6"/>`);
add(`<circle cx="1356" cy="748" r="5" fill="#5a4a40"/>`);
// kettle on the stove
part('kettle', `<path d="M1260,598 Q1258,560 1300,556 Q1342,560 1340,598 Z" fill="#7a8a8a" stroke="#1a1a18" stroke-width="2"/>
<path d="M1266,594 Q1266,566 1300,562" stroke="#e6efe8" stroke-width="3" fill="none" opacity="0.5"/>
<path d="M1338,580 L1366,566 L1370,572 L1342,590 Z" fill="#6a7878" stroke="#1a1a18" stroke-width="1.5"/>
<path d="M1276,560 Q1300,520 1324,560" stroke="#2a2420" stroke-width="5" fill="none"/>
<ellipse cx="1300" cy="557" rx="16" ry="5" fill="#5a6868" stroke="#1a1a18"/><circle cx="1300" cy="551" r="4" fill="#2a2420"/>`, 'none', { origin: [1300, 598] });
// firewood stack and a ladder up to the rim
for (let row = 0; row < 3; row++) for (let i = 0; i < 4 - row; i++) {
  const x = 1440 + i * 34 + row * 17, y = FLOOR - 16 - row * 28;
  add(`<rect x="${x - 40}" y="${y - 14}" width="40" height="28" fill="#5a3e26"/><ellipse cx="${x}" cy="${y}" rx="15" ry="14" fill="#a8845a" stroke="#3a2614" stroke-width="2"/><ellipse cx="${x}" cy="${y}" rx="8" ry="7" fill="none" stroke="#6d4a2a"/><circle cx="${x}" cy="${y}" r="2" fill="#6d4a2a"/>`);
}
add(`<path d="M1500,${FLOOR - 90} L1560,240 M1556,${FLOOR - 70} L1600,262" stroke="#4a3220" stroke-width="10" stroke-linecap="round"/>`);
for (let k = 0; k < 9; k++) { const t = k / 9; add(`<path d="M${f(1500 + 60 * t + 2)},${f(FLOOR - 90 - (FLOOR - 330) * t)} L${f(1556 + 44 * t)},${f(FLOOR - 70 - (FLOOR - 332) * t)}" stroke="#6d4a2a" stroke-width="6"/>`); }

// ---------------- lamp hanging from the beam (animated) ----------------
part('lamp', `<path d="M800,222 L800,420" stroke="#2a221c" stroke-width="2" stroke-dasharray="5 2"/>
<circle cx="800" cy="460" r="70" fill="url(#i-warm)"/>
<path d="M782,428 Q800,410 818,428 Z" fill="#5a3826" stroke="#140a05" stroke-width="1.5"/>
<rect x="776" y="428" width="48" height="6" rx="2" fill="#3a2418"/>
<path d="M780,434 L820,434 L824,486 L776,486 Z" fill="#ffd98a" opacity="0.92"/>
<ellipse cx="800" cy="462" rx="12" ry="16" fill="#fff6d0" opacity="0.9" filter="url(#i-blur2)"/>
<path d="M800,450 C805,458 806,465 800,472 C794,465 795,458 800,450 Z" fill="#fffbe0"/>
<path d="M780,434 L776,486 M820,434 L824,486 M800,434 L800,486" stroke="#2a1608" stroke-width="2.5"/>
<rect x="772" y="486" width="56" height="8" rx="2" fill="#3a2418"/><circle cx="800" cy="420" r="5" fill="none" stroke="#3a2418" stroke-width="2"/>`, 'swing', { origin: [800, 222], vars: { dur: '6s' } });

// glowing mushroom jar on the shelf (animated)
part('jar', `<circle cx="469" cy="446" r="40" fill="url(#i-jar)"/><path d="M462,468 q-2,-14 6,-20 q8,6 6,20 Z" fill="#cfe6c4"/><ellipse cx="468" cy="447" rx="8" ry="4" fill="#e6ffd8"/>`, 'glowpulse', { origin: [469, 446] });

// ---------------- lighting ----------------
add(`<path d="M1050,0 L1500,0 L1000,905 L520,905 Z" fill="url(#i-shaft)" filter="url(#i-blur20)"/>`);
add(`<circle cx="1305" cy="750" r="330" fill="url(#i-warm)" opacity="0.8"/>`);
add(`<circle cx="942" cy="730" r="180" fill="url(#i-warm)" opacity="0.5"/>`);
add(`<circle cx="800" cy="470" r="420" fill="url(#i-warm)" opacity="0.55"/>`);
add(`<circle cx="1100" cy="370" r="180" fill="url(#i-cool)"/>`);

// ---------------- foreground: mushrooms in the corners (drawn over the gnome) ----------------
const shroom = (x, y, h, cw, col) => `<path d="M${x - 4},${y} Q${x - 6},${y - h / 2} ${x - 2},${y - h} L${x + 2},${y - h} Q${x + 6},${y - h / 2} ${x + 4},${y} Z" fill="#d9cdb0" stroke="#3b2e1e" stroke-width="1"/>
<path d="M${x - cw / 2},${y - h + 4} C${x - cw / 2},${y - h - cw * 0.55} ${x + cw / 2},${y - h - cw * 0.55} ${x + cw / 2},${y - h + 4} Q${x},${y - h - 4} ${x - cw / 2},${y - h + 4} Z" fill="${col}" stroke="#2e2116" stroke-width="1.5"/>
<ellipse cx="${x - cw * 0.15}" cy="${y - h - cw * 0.22}" rx="${cw * 0.12}" ry="${cw * 0.06}" fill="#efe6cf" opacity="0.8"/>`;
part('front-left', [[40, 1000, 90, 70, '#a24a26'], [96, 1000, 60, 46, '#c08a3a'], [8, 1000, 40, 34, '#d6c8a4']].map(a => shroom(...a)).join(''), 'sway', { front: true, origin: [60, 1000], vars: { a: '1.5deg', dur: '6s' } });
part('front-right', [[1560, 1000, 110, 84, '#c08a3a'], [1500, 1000, 64, 50, '#a24a26']].map(a => shroom(...a)).join(''), 'sway', { front: true, origin: [1540, 1000], vars: { a: '-1.4deg', dur: '6s', delay: '-2s' } });

// overall vignette + grain
add(`<rect width="${W}" height="${H}" fill="url(#i-vignette)"/>`);

// ---------------- write ----------------
const wrap = inner => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">\n${defs}\n${inner}\n</svg>\n`;
fs.mkdirSync(path.join(dir, 'iparts'), { recursive: true });
fs.writeFileSync(path.join(dir, 'static_interior.svg'), wrap(out.join('\n')));
for (const p of parts) fs.writeFileSync(path.join(dir, 'iparts', `${p.id}.svg`), wrap(p.svg));
fs.writeFileSync(path.join(dir, 'iparts.json'), JSON.stringify(parts.map(({ svg, ...rest }) => rest), null, 1));
console.log(`interior: ${parts.length} parts`);
