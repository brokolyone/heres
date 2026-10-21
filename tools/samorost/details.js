// Detail pass for the Samorost painting: foreground framing, fireflies, light spill,
// cobweb, snail, drifting leaves, moon rays and a barely visible carved signature.
// usage: node details.js out.svg
const fs = require('fs');

let seed = 20261021;
const rnd = () => ((seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296);
const r = (a, b) => a + rnd() * (b - a);
const f = n => n.toFixed(1);

const parts = [];
const add = s => parts.push(s);

// ---------- moon rays ----------
add(`<g opacity="0.55" filter="url(#details-soft)">`);
for (let i = 0; i < 6; i++) {
  const a = r(-0.35, 0.35) + 2.35, len = r(700, 1100), w = r(30, 80);
  const x1 = 1260 + Math.cos(a) * len, y1 = 230 + Math.sin(a) * len;
  const nx = -Math.sin(a) * w, ny = Math.cos(a) * w;
  add(`<path d="M1260,230 L${f(x1 + nx)},${f(y1 + ny)} L${f(x1 - nx)},${f(y1 - ny)} Z" fill="url(#details-ray)"/>`);
}
add(`</g>`);

// ---------- warm light spill from window, door and lantern ----------
add(`<ellipse cx="560" cy="566" rx="95" ry="16" fill="url(#details-warm)" opacity="0.7"/>`);
add(`<ellipse cx="1150" cy="555" rx="70" ry="12" fill="url(#details-warm)" opacity="0.45"/>`);
add(`<circle cx="1162" cy="428" r="46" fill="url(#details-warm)" opacity="0.5"/>`);
add(`<circle cx="553" cy="386" r="40" fill="url(#details-warm)" opacity="0.45"/>`);

// ---------- cobweb between the tower legs ----------
{
  const cx = 1068, cy = 470, spokes = 9, rad = 26;
  const pts = [];
  for (let i = 0; i < spokes; i++) {
    const a = (i / spokes) * Math.PI * 2 + r(-0.15, 0.15);
    pts.push([a, rad * r(0.85, 1.15)]);
  }
  add(`<g stroke="#e8efe6" stroke-width="0.45" fill="none" opacity="0.38">`);
  for (const [a, l] of pts) add(`<line x1="${cx}" y1="${cy}" x2="${f(cx + Math.cos(a) * l)}" y2="${f(cy + Math.sin(a) * l)}"/>`);
  for (let ring = 1; ring <= 5; ring++) {
    const k = ring / 5.5;
    const d = pts.map(([a, l], i) => `${i ? 'Q' + f(cx + Math.cos(a - 0.35) * l * k * 0.92) + ',' + f(cy + Math.sin(a - 0.35) * l * k * 0.92) + ' ' : 'M'}${f(cx + Math.cos(a) * l * k)},${f(cy + Math.sin(a) * l * k)}`).join(' ');
    add(`<path d="${d} Z"/>`);
  }
  add(`</g>`);
  for (let i = 0; i < 7; i++) {
    const [a, l] = pts[i];
    const k = r(0.3, 0.9);
    add(`<circle cx="${f(cx + Math.cos(a) * l * k)}" cy="${f(cy + Math.sin(a) * l * k)}" r="0.9" fill="#fff8d8" opacity="0.7"/>`);
  }
  // a tiny spider
  add(`<g transform="translate(${cx + 6},${cy - 4})"><circle r="2.2" fill="#2a1a12"/><circle cx="-2.6" cy="-0.6" r="1.4" fill="#2a1a12"/>` +
    [-1, 1].map(s => [0.4, 1.1, 1.8, 2.4].map(t => `<path d="M0,0 q${f(s * 3)},${f(-2 + t)} ${f(s * 4.5)},${f(t * 1.6)}" stroke="#2a1a12" stroke-width="0.5" fill="none"/>`).join('')).join('') + `</g>`);
}

// ---------- snail crawling up the island bark ----------
{
  // logarithmic spiral for the shell whorl
  const spiral = [];
  for (let t = 0; t <= 3.1 * Math.PI * 2; t += 0.12) {
    const rr = 10.5 * Math.exp(-0.16 * t);
    spiral.push(`${f(Math.cos(-t + 2.6) * rr)},${f(Math.sin(-t + 2.6) * rr * 0.92)}`);
  }
  const growth = [];
  for (let i = 0; i < 14; i++) {
    const t = i * 0.42, r1 = 10.5 * Math.exp(-0.16 * t), r2 = 10.5 * Math.exp(-0.16 * (t + Math.PI * 2));
    const a = -t + 2.6;
    growth.push(`<path d="M${f(Math.cos(a) * r1)},${f(Math.sin(a) * r1 * 0.92)} L${f(Math.cos(a) * r2)},${f(Math.sin(a) * r2 * 0.92)}" />`);
  }
  add(`<g transform="translate(975,716) rotate(-18) scale(0.4)">
  <path d="M-34,2.6 Q-27,1.6 -18,2" stroke="#dfeee6" stroke-width="2.4" stroke-linecap="round" fill="none" opacity="0.16"/>
  <path d="M-34,2.2 Q-27,1.2 -18,1.6" stroke="#ffffff" stroke-width="0.6" fill="none" opacity="0.28"/>
  <ellipse cx="2" cy="3.5" rx="21" ry="3" fill="#0d0805" opacity="0.45" filter="url(#details-blur1)"/>
  <path d="M-19,2 Q-17,-2 -10,-3 L8,-3.5 Q14,-4 17,-8 Q20,-13 24,-12.5 Q28,-11.5 27,-6.5 Q26,-2 21,0.5 Q14,3 0,3 Q-12,3.2 -19,2 Z" fill="url(#details-foot)"/>
  <path d="M-17,1.8 Q0,3.4 20,0.6" stroke="#5e4a34" stroke-width="0.7" fill="none" opacity="0.6"/>
  <path d="M-6,0 q2,-0.6 4,0 M2,-0.5 q2,-0.6 4,0 M9,-1 q2,-0.6 4,-0.2 M18,-5 q1.6,-0.8 3,0" stroke="#7a6248" stroke-width="0.5" fill="none" opacity="0.7"/>
  <path d="M23.5,-12 Q24.5,-18 26.5,-22" stroke="#b9a184" stroke-width="1.1" stroke-linecap="round" fill="none"/>
  <path d="M25.5,-11.5 Q28.5,-16.5 31.5,-19.5" stroke="#b9a184" stroke-width="1.1" stroke-linecap="round" fill="none"/>
  <circle cx="26.7" cy="-22.3" r="1.3" fill="#2b1c12"/><circle cx="31.8" cy="-19.8" r="1.3" fill="#2b1c12"/>
  <circle cx="26.4" cy="-22.7" r="0.4" fill="#fff" opacity="0.8"/><circle cx="31.5" cy="-20.2" r="0.4" fill="#fff" opacity="0.8"/>
  <path d="M26.5,-7 q3,0 4.5,1.5 M26,-5 q2.6,0.6 3.6,2.2" stroke="#b9a184" stroke-width="0.8" stroke-linecap="round" fill="none"/>
  <path d="M19,-9 Q22,-12.5 25,-11.5" stroke="#efe2c8" stroke-width="0.8" fill="none" opacity="0.6"/>
  <g transform="translate(-1,-12) rotate(-8)">
    <ellipse cx="0" cy="0" rx="11.6" ry="10.8" fill="url(#details-shell)"/>
    <g stroke="#5a3418" stroke-width="0.45" fill="none" opacity="0.55">${growth.join('')}</g>
    <path d="M${spiral.join(' L')}" stroke="#3e2210" stroke-width="1.1" fill="none" stroke-linecap="round"/>
    <path d="M${spiral.join(' L')}" stroke="#f0c98a" stroke-width="0.5" fill="none" opacity="0.45" transform="translate(-0.7,-0.6)"/>
    <ellipse cx="-11" cy="2" rx="1.6" ry="6.5" fill="#3a200e" opacity="0.5" transform="rotate(8 -11 2)"/>
    <ellipse cx="3.5" cy="-6" rx="3.8" ry="1.8" fill="#fff4dc" opacity="0.45" transform="rotate(25 3.5 -6)"/>
    <ellipse cx="0" cy="0" rx="11.6" ry="10.8" fill="url(#details-shellshade)"/>
  </g>
</g>`);
}

// ---------- dew drops on the moss line ----------
for (let i = 0; i < 26; i++) {
  const x = r(400, 1200);
  const t = (x - 380) / 850;
  const y = 600 - Math.sin(t * Math.PI) * 52 + r(4, 14);
  add(`<circle cx="${f(x)}" cy="${f(y)}" r="${f(r(0.8, 1.6))}" fill="#eef7f0" opacity="${f(r(0.35, 0.7))}"/>`);
}

// ---------- drifting leaves and seeds ----------
const leafCols = ['#b8742e', '#8a5a2b', '#c9a24a', '#7c6a34', '#a3502a'];
for (let i = 0; i < 16; i++) {
  let x, y;
  do { x = r(60, 1560); y = r(60, 960); } while ((x > 340 && x < 1270 && y > 330 && y < 990) || Math.hypot(x - 1260, y - 230) < 190);
  const s = r(0.6, 1.3), rot = r(0, 360), c = leafCols[i % leafCols.length];
  add(`<g transform="translate(${f(x)},${f(y)}) rotate(${f(rot)}) scale(${f(s)})" opacity="${f(r(0.55, 0.85))}">
    <path d="M0,-8 Q6,-2 0,8 Q-6,-2 0,-8 Z" fill="${c}"/><path d="M0,-7 L0,10" stroke="#3a2614" stroke-width="0.6"/></g>`);
}

// ---------- fireflies ----------
const swarms = [[1162, 430, 60, 10], [553, 390, 70, 8], [700, 470, 80, 9], [930, 500, 90, 7], [230, 300, 90, 6]];
for (const [cx, cy, rad, n] of swarms) {
  for (let i = 0; i < n; i++) {
    const a = r(0, Math.PI * 2), d = r(10, rad);
    const x = cx + Math.cos(a) * d, y = cy + Math.sin(a) * d * 0.7;
    add(`<circle cx="${f(x)}" cy="${f(y)}" r="${f(r(4, 8))}" fill="url(#details-fly)" opacity="${f(r(0.45, 0.9))}"/>`);
    add(`<circle cx="${f(x)}" cy="${f(y)}" r="${f(r(0.8, 1.4))}" fill="#fff6c8"/>`);
  }
}

// ---------- foreground framing silhouettes (out of focus) ----------
const frond = (x, y, ang, len, bend, leaves, side) => {
  let d = '', px = x, py = y, a = ang;
  const segs = [];
  for (let i = 0; i <= leaves; i++) {
    segs.push([px, py, a]);
    const step = len / leaves;
    px += Math.cos(a) * step; py += Math.sin(a) * step; a += bend;
  }
  d += `<path d="M${segs.map(s => f(s[0]) + ',' + f(s[1])).join(' L')}" stroke="#08171a" stroke-width="3" fill="none" stroke-linecap="round"/>`;
  segs.forEach(([sx, sy, sa], i) => {
    const l = (1 - i / leaves) * 58 + 14;
    for (const s of side) {
      const la = sa + s * 0.95 + 0.25;
      const ex = sx + Math.cos(la) * l, ey = sy + Math.sin(la) * l;
      const mx = sx + Math.cos(la + s * 0.25) * l * 0.55, my = sy + Math.sin(la + s * 0.25) * l * 0.55;
      d += `<path d="M${f(sx)},${f(sy)} Q${f(mx + 9)},${f(my - 9)} ${f(ex)},${f(ey)} Q${f(mx - 9)},${f(my + 9)} ${f(sx)},${f(sy)} Z" fill="#08171a"/>`;
    }
  });
  return d;
};
add(`<g filter="url(#details-dof)" opacity="0.92">`);
add(frond(-10, 1010, -1.05, 260, 0.06, 14, [-1, 1]));
add(frond(40, 1010, -1.35, 200, 0.09, 11, [-1, 1]));
add(frond(-20, 940, -0.55, 220, 0.05, 12, [-1, 1]));
add(frond(120, 1015, -1.75, 150, -0.1, 9, [-1, 1]));
add(`<path d="M-10,880 Q60,900 120,950 Q150,980 160,1010 L-10,1010 Z" fill="#08171a"/>`);
add(`<path d="M1610,890 Q1520,900 1430,940 Q1400,955 1370,1010 L1610,1010 Z" fill="#08171a"/>`);
add(frond(1610, 880, 3.75, 260, -0.05, 13, [-1, 1]));
add(frond(1560, 1015, -1.9, 230, -0.06, 12, [-1, 1]));
add(frond(1600, 1010, -2.2, 180, -0.08, 10, [-1, 1]));
for (let i = 0; i < 9; i++) {
  const x = r(1430, 1600), y0 = 900 + (1600 - x) * 0.25;
  add(`<path d="M${f(x)},${f(y0)} q${f(r(-6, 6))},${f(r(20, 40))} ${f(r(-4, 4))},${f(r(40, 90))}" stroke="#08171a" stroke-width="${f(r(1.5, 3))}" fill="none" stroke-linecap="round"/>`);
}
add(`</g>`);

// ---------- signature: barely visible, scratched into the dark bark under the island ----------
add(`<g transform="translate(793,779) rotate(-6)" font-family="Georgia, 'Times New Roman', serif" font-style="italic" font-size="11" letter-spacing="0.6">
  <text x="0.6" y="0.7" fill="#c9b48e" opacity="0.10">wlyffi</text>
  <text x="0" y="0" fill="#140c07" opacity="0.38">wlyffi</text>
</g>`);

const defs = `<defs>
  <filter id="details-soft" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="18"/></filter>
  <filter id="details-dof" x="-10%" y="-10%" width="120%" height="120%"><feGaussianBlur stdDeviation="2.2"/></filter>
  <linearGradient id="details-ray" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#f4f0dc" stop-opacity="0.10"/><stop offset="1" stop-color="#f4f0dc" stop-opacity="0"/>
  </linearGradient>
  <radialGradient id="details-warm"><stop offset="0" stop-color="#f3c66a" stop-opacity="0.55"/><stop offset="1" stop-color="#f3c66a" stop-opacity="0"/></radialGradient>
  <radialGradient id="details-fly"><stop offset="0" stop-color="#f6e48a" stop-opacity="0.8"/><stop offset="1" stop-color="#f6e48a" stop-opacity="0"/></radialGradient>
  <radialGradient id="details-shell" cx="0.4" cy="0.3" r="0.75"><stop offset="0" stop-color="#e6b06a"/><stop offset="0.55" stop-color="#b06a30"/><stop offset="1" stop-color="#5a3016"/></radialGradient>
  <radialGradient id="details-shellshade" cx="0.65" cy="0.25" r="0.9"><stop offset="0.5" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#1a0c04" stop-opacity="0.45"/></radialGradient>
  <linearGradient id="details-foot" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#d9c6a4"/><stop offset="0.6" stop-color="#b49a78"/><stop offset="1" stop-color="#7d6549"/></linearGradient>
  <filter id="details-blur1" x="-20%" y="-50%" width="140%" height="200%"><feGaussianBlur stdDeviation="1.2"/></filter>
</defs>`;

fs.writeFileSync(process.argv[2], `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1000" width="1600" height="1000">
${defs}
<g id="layer-details">
${parts.join('\n')}
</g>
</svg>
`);
