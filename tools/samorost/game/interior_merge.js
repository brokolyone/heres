// Stack the agents' interior layers into one backdrop and lay out the animated interior parts
// in the sprite scheme the game expects.
// usage: node interior_merge.js <interiorDir> <buildDir>
// Reads <interiorDir>/layers/*.svg and <interiorDir>/parts/*.svg (see art/samorost/interior/SPEC.md);
// writes <buildDir>/static_interior.svg, <buildDir>/iparts/<id>.svg and <buildDir>/iparts.json.
const fs = require('fs');
const path = require('path');

const [src, dir] = process.argv.slice(2);
const LAYERS = ['shell', 'walls_detail', 'left', 'center', 'right', 'atmos'];
const PARTS = {
  jar: { anim: 'glowpulse', origin: [469, 446] },
  pendulum: { anim: 'pendulum', origin: [850, 462] },
  lamp: { anim: 'swing', origin: [800, 222], vars: { dur: '6s' } },
  crank: { anim: 'none', origin: [904, 754] },
  candle: { anim: 'candle', origin: [942, 731] },
  stovefire: { anim: 'fire', origin: [1305, 788] },
  kettle: { anim: 'none', origin: [1300, 598] },
  pet: { anim: 'breathe', origin: [1170, 898] },
  'front-left': { anim: 'sway', origin: [60, 1000], front: true, vars: { a: '1.5deg', dur: '6s' } },
  'front-right': { anim: 'sway', origin: [1540, 1000], front: true, vars: { a: '-1.4deg', dur: '6s', delay: '-2s' } },
};
const inner = file => {
  const s = fs.readFileSync(file, 'utf8');
  return s.slice(s.indexOf('>', s.indexOf('<svg')) + 1, s.lastIndexOf('</svg>'));
};
const wrap = body => `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 1600 1000" width="1600" height="1000">\n${body}\n</svg>\n`;

fs.mkdirSync(path.join(dir, 'iparts'), { recursive: true });
const layers = LAYERS.filter(l => fs.existsSync(path.join(src, 'layers', `${l}.svg`)));
fs.writeFileSync(path.join(dir, 'static_interior.svg'), wrap(layers.map(l => `<!-- ${l} -->\n${inner(path.join(src, 'layers', `${l}.svg`))}`).join('\n')));
const meta = [];
for (const [id, p] of Object.entries(PARTS)) {
  const f = path.join(src, 'parts', `${id}.svg`);
  if (!fs.existsSync(f)) { console.warn(`interior part missing: ${id}`); continue; }
  fs.copyFileSync(f, path.join(dir, 'iparts', `${id}.svg`));
  meta.push({ id, layer: 'interior', anim: p.anim, origin: p.origin, vars: p.vars || {}, front: !!p.front, parent: null, below: false, pos: meta.length });
}
fs.writeFileSync(path.join(dir, 'iparts.json'), JSON.stringify(meta, null, 1));
console.log(`interior: ${layers.length} layers, ${meta.length} parts`);
