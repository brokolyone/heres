// Split the painting into static backdrops and animated sprite parts.
// usage: node extract.js <layersDir> <outDir>
// Writes <outDir>/static_bg.svg, static_mid.svg, overlay.svg, parts/<id>.svg and parts.json.
const fs = require('fs');
const path = require('path');

const [layersDir, outDir] = process.argv.slice(2);
const LAYERS = ['bg', 'island', 'cave', 'structures', 'flora', 'characters', 'details'].filter(l => fs.existsSync(path.join(layersDir, `${l}.svg`)));
const body = {};
const orig = {};
for (const l of LAYERS) {
  const s = fs.readFileSync(path.join(layersDir, `${l}.svg`), 'utf8');
  body[l] = s.slice(s.indexOf('>', s.indexOf('<svg')) + 1, s.lastIndexOf('</svg>'));
  orig[l] = body[l];
}
const allDefs = LAYERS.map(l => (body[l].match(/<defs>[\s\S]*?<\/defs>/g) || []).join('\n')).join('\n');

// ---------- locating pieces of markup ----------
const find = (l, marker, from = 0) => {
  const i = body[l].indexOf(marker, from);
  if (i < 0) throw new Error(`marker not found in ${l}: ${marker}`);
  if (body[l].indexOf(marker, i + 1) >= 0 && !from) throw new Error(`marker not unique in ${l}: ${marker}`);
  return i;
};
// balanced <g>…</g> starting at the <g that `marker` begins with
const groupEnd = (s, i) => {
  const re = /<g[\s>]|<\/g>/g;
  re.lastIndex = i;
  let depth = 0, m;
  while ((m = re.exec(s))) {
    depth += m[0] === '</g>' ? -1 : 1;
    if (!depth) return m.index + 4;
  }
  throw new Error('unbalanced group');
};
const lineEnd = (s, i) => { const j = s.indexOf('\n', i); return j < 0 ? s.length : j; };

const parts = [];
const cut = (l, a, b) => { const piece = body[l].slice(a, b); body[l] = body[l].slice(0, a) + body[l].slice(b); return piece; };

// kinds of selection
const G = (l, marker) => { const i = find(l, marker); return cut(l, i, groupEnd(body[l], i)); };
const EL = (l, marker) => { const i = find(l, marker); return cut(l, i, body[l].indexOf('/>', i) + 2); };
const LINES = (l, startMarker, endMarker) => {
  const i = find(l, startMarker);
  const j = lineEnd(body[l], find(l, endMarker, i));
  return cut(l, i, j);
};

// a part: id, layer it belongs to (for z-order), svg markup, optional context wrapper,
// animation name + parameters, origin in canvas px, optional parent part id (nesting).
const part = (id, layer, svg, anim, opts = {}) => parts.push({ id, layer, svg, anim, ctx: opts.ctx || [], origin: opts.origin || null, parent: opts.parent || null, below: !!opts.below, front: !!opts.front, vars: opts.vars || {}, pos: orig[layer].indexOf(svg.slice(0, 80)) });

// ================= characters (sub-parts first, then parents) =================
const GRAIN = '<g filter="url(#characters-grain)">';
// In game mode the gnome becomes the playable character, so it leaves the painting entirely.
const GAME = !!process.env.GAME;
if (GAME) G('characters', '<g id="characters-gnome">');
// gnome eyes live inside the tilted head
const eyes = GAME ? null : LINES('characters', '<ellipse cx="776.5" cy="496.5"', '<circle cx="777.9" cy="494.8"');
if (!GAME) {
const head = G('characters', '<g transform="rotate(4 781 505)">');
part('gnome-head', 'characters', head, 'headtilt', { ctx: ['<g filter="url(#characters-grainlite)">'], origin: [781, 512] });
part('gnome-eyes', 'characters', eyes, 'blink', { ctx: ['<g filter="url(#characters-grainlite)">', '<g transform="rotate(4 781 505)">'], origin: [782, 496], parent: 'gnome-head' });
part('gnome-beam', 'characters', EL('characters', '<path d="M806,499 L898,392'), 'beam', { origin: [808, 501] });
}

// beast: sleep bubbles and nose drip, then the whole beast breathes
part('beast-bubbles', 'characters', LINES('characters', '<circle cx="1284" cy="560" r="3"', '<circle cx="1305" cy="528"'), 'bubbles', { origin: [1284, 562] });
part('beast-drip', 'characters', LINES('characters', '<path d="M1259,716 C1259,721', '<circle cx="1259" cy="731"'), 'drip', { origin: [1259, 716] });
part('beast', 'characters', G('characters', '<g id="characters-beast">'), 'breathe', { origin: [1185, 655] });

// propeller beetle: blades flicker, body flies
const blades = LINES('characters', '<ellipse cx="640" cy="179" rx="11"', '<ellipse cx="651" cy="180" rx="24"');
const beetle = G('characters', '<g id="characters-propbeetle"');
const exhaust = LINES('characters', '<circle cx="672" cy="205" r="3"', '<circle cx="694" cy="213"');
part('beetle', 'characters', beetle, 'flyBeetle', { origin: [650, 200] });
part('beetle-blades', 'characters', blades, 'prop', { ctx: ['<g transform="rotate(8 650 200)">'], origin: [651, 180], parent: 'beetle' });
part('beetle-exhaust', 'characters', exhaust, 'exhaust', { origin: [672, 205], parent: 'beetle' });

// moth: wings flap, whole moth wanders
const wings = LINES('characters', '<path d="M900,250 C890,228', '<path d="M900,250 L866,232');
const moth = G('characters', '<g id="characters-moth"');
const mothTrail = LINES('characters', '<circle cx="862" cy="278" r="1.2"', '<circle cx="820" cy="294"');
part('moth', 'characters', moth + mothTrail, 'flyMoth', { origin: [900, 252] });
part('moth-wings', 'characters', wings, 'flap', { ctx: ['<g transform="rotate(-12 900 250)">', GRAIN], origin: [900, 252], parent: 'moth', below: true });

part('jelly', 'characters', G('characters', '<g id="characters-jelly">'), 'jelly', { origin: [470, 283] });

// long-legged bug: antennae twitch
part('bug-antennae', 'characters', LINES('characters', '<path d="M579,522 C572,510', '<circle cx="562" cy="512" r="1.1"'), 'antennae',
  { ctx: ['<g transform="translate(592 556) scale(1.35) translate(-592 -556)">'], origin: [572, 547] });

// ================= structures =================
part('smoke', 'structures', G('structures', '<g filter="url(#structures-smoke)"'), 'smoke', { origin: [646, 334] });
if (GAME) {
  // the painted door opens in three frames (closed, ~40°, ~80°) over a view into the lit room
  const doorDir = path.join(layersDir, '..', 'door');
  const svgInner = f => { const t = fs.readFileSync(path.join(doorDir, f), 'utf8'); return t.slice(t.indexOf('>', t.indexOf('<svg')) + 1, t.lastIndexOf('</svg>')); };
  G('structures', '<g id="structures-doorleaf">');
  part('doorway', 'structures', svgInner('doorway.svg'), 'none', { origin: [538, 528] });
  for (const k of [0, 1, 2]) part(`door-${k}`, 'structures', svgInner(`leaf_${k}.svg`), 'none', { origin: [504, 528] });
}
part('propeller', 'structures', G('structures', '<g transform="translate(1079,300)">'), 'spin', { origin: [1079, 300], vars: { dur: '1.5s' } });
part('gear-a', 'structures', LINES('structures', '<path d="M1047.0,408.0 L1046.4', '<circle cx="1030" cy="408" r="2.7"'), 'spin', { origin: [1030, 408], vars: { dur: '6s' } });
part('gear-b', 'structures', LINES('structures', '<path d="M1023.6,433.0 L1022.0', '<circle cx="1014" cy="430" r="1.6"'), 'spinR', { origin: [1014, 430], vars: { dur: '3s' } });
part('gear-c', 'structures', LINES('structures', '<path d="M1122.9,387.1 L1122.1', '<circle cx="1112" cy="386" r="1.8"'), 'spinR', { origin: [1112, 386], vars: { dur: '4s' } });
part('gauge', 'structures', EL('structures', '<path d="M1062,398 L1066,393"'), 'needle', { origin: [1062, 398] });
part('flag', 'structures', LINES('structures', '<path d="M1077,318 C1090,314', '<path d="M1082,320 l20,2'), 'flag', { origin: [1077, 324] });
part('lantern', 'structures', LINES('structures', '<path d="M1164,362 C1165,380', '<path d="M1164,446 l0,6"'), 'swing', { origin: [1164, 362] });
for (const [i, [x, y]] of [['1093.8', '320.8'], ['1108.7', '332.6'], ['1123.5', '342.5'], ['1138.3', '350.3'], ['1153.2', '356.2']].entries()) {
  const m = `<circle cx="${x}" cy="${y}" r="2"`;
  part(`bulb-${i}`, 'structures', LINES('structures', m, m), 'twinkle', { origin: [+x, +y], vars: { delay: `${-i * 0.7}s`, dur: '3s' } });
}
part('ladder', 'structures', G('structures', '<g id="structures-ladder"'), 'ladder', { origin: [902, 852] });

// ================= flora =================
{
  const re = /^<g><ellipse cx="([\d.]+)" cy="([\d.]+)"/gm;
  const hits = [...body.flora.matchAll(re)].map(m => [m[0], +m[1], +m[2]]);
  hits.forEach(([marker, cx, cy], i) => {
    const glow = body.flora.slice(body.flora.indexOf(marker), body.flora.indexOf(marker) + 200).includes('flora-glow');
    if (glow) {
      part(`glowshrooms`, 'flora', G('flora', marker), 'glowpulse', { origin: [cx, cy] });
    } else {
      const durs = ['4s', '6s', '3s', '12s'];
      part(`shroom-${i}`, 'flora', G('flora', marker), 'sway', { origin: [cx, cy], vars: { a: `${(1 + (i % 4) * 0.5).toFixed(1)}deg`, dur: durs[i % 4], delay: `${-(i * 0.37) % 4}s` } });
    }
  });
}
part('vines', 'flora', G('flora', '<g filter="url(#flora-rough)"><path d="M411.2,606'), 'skew', { origin: [800, 606], vars: { a: '1.6deg', dur: '6s' } });

// ================= island =================
{ // the cave agent's flickering warm light
  const f = path.join(layersDir, '..', 'cave', 'light.svg');
  if (fs.existsSync(f) && body.cave !== undefined) { const t = fs.readFileSync(f, 'utf8'); part('cave-light', 'cave', t.slice(t.indexOf('>', t.indexOf('<svg')) + 1, t.lastIndexOf('</svg>')), 'flicker', { origin: [520, 745] }); }
}
part('roots', 'island', G('island', '<g id="island-roots">'), 'skew', { origin: [800, 845], vars: { a: '0.9deg', dur: '6s' } });

// ================= bg =================
{
  const lines = body.bg.split('\n');
  const isl = lines.filter(x => x.startsWith('<defs><linearGradient id="bg-isl'));
  isl.forEach((line, i) => {
    const i0 = find('bg', line);
    cut('bg', i0, i0 + line.length);
    const m = line.match(/<ellipse cx="([\d.]+)" cy="([\d.]+)"/) || line.match(/M([\d.]+),([\d.]+)/);
    part(`far-island-${i}`, 'bg', line, 'bob', { ctx: ['<g filter="url(#bg-blur1)">'], origin: m ? [+m[1], +m[2]] : [800, 500], vars: { dur: ['12s', '6s'][i % 2], delay: `${-i * 1.7}s`, dy: `${(3 + i).toFixed(0)}px` } });
  });
}

// ================= details (marked with data-anim) =================
{
  const re = /<g data-anim="([\w-]+)"(?: data-o="([\d.]+),([\d.]+)")?/g;
  let m, n = {};
  while ((m = re.exec(body.details))) {
    const [marker, kind, ox, oy] = m;
    const i = m.index;
    const svg = cut('details', i, groupEnd(body.details, i));
    re.lastIndex = i;
    n[kind] = (n[kind] || 0) + 1;
    const k = n[kind];
    const o = ox ? [+ox, +oy] : null;
    const id = `${kind}-${k}`;
    const D = (arr) => arr[k % arr.length];
    switch (kind) {
      case 'rays': part(id, 'details', svg, 'rays', { origin: [1260, 230] }); break;
      case 'spill-door': case 'spill-window': part(id, 'details', svg, 'flicker', { origin: [553, 386] }); break;
      case 'spill-lantern': part(id, 'details', svg, 'swing', { origin: [1164, 362] }); break;
      case 'spill-tower': part(id, 'details', svg, 'flicker', { origin: [1150, 555], vars: { delay: '-2s' } }); break;
      case 'spider': part(id, 'details', svg, 'spider', { origin: [1074, 466] }); break;
      case 'snail': part(id, 'details', svg, 'snail', { origin: [975, 716] }); break;
      case 'dew': part(id, 'details', svg, 'twinkle', { origin: o, vars: { dur: D(['3s', '4s', '6s']), delay: `${-(k * 0.83) % 6}s` } }); break;
      case 'leaf': part(id, 'details', svg, 'leaf', { origin: o, vars: { dur: D(['6s', '4s', '12s']), delay: `${-(k * 1.3) % 6}s`, a: `${8 + (k % 5) * 4}deg` } }); break;
      case 'fly': part(id, 'details', svg, D(['fly1', 'fly2', 'fly3']), { origin: o, vars: { dur: D(['6s', '4s', '12s', '3s']), delay: `${-(k * 0.61) % 6}s` } }); break;
      case 'frond-l': part(id, 'details', svg, 'frond', { origin: [0, 1000], front: true, vars: { a: '1.6deg', dur: '6s' } }); break;
      case 'frond-r': part(id, 'details', svg, 'frond', { origin: [1600, 1000], front: true, vars: { a: '-1.4deg', dur: '6s', delay: '-2s' } }); break;
      default: throw new Error('unknown data-anim ' + kind);
    }
  }
}

// ---------- write everything ----------
const wrap = inner => `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 1600 1000" width="1600" height="1000">\n${inner}\n</svg>\n`;
fs.mkdirSync(path.join(outDir, 'parts'), { recursive: true });
fs.writeFileSync(path.join(outDir, 'static_bg.svg'), wrap(body.bg));
fs.writeFileSync(path.join(outDir, 'static_mid.svg'), wrap(allDefs + '\n' + LAYERS.slice(1).map(l => body[l]).join('\n')));
for (const p of parts) {
  const open = p.ctx.join(''), close = '</g>'.repeat(p.ctx.length);
  fs.writeFileSync(path.join(outDir, 'parts', `${p.id}.svg`), wrap(`${allDefs}\n${open}${p.svg}${close}`));
}
fs.writeFileSync(path.join(outDir, 'parts.json'), JSON.stringify(parts.map(({ svg, ctx, ...rest }) => rest), null, 1));
console.log(`${parts.length} parts`);
