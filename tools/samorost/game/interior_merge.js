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
  // the stove fire is split into three planes so the flames sit behind the logs and the grille in front
  'fire-back': { anim: 'fire', origin: [1305, 788] },
  'fire-logs': { anim: 'none', origin: [1305, 788] },
  'fire-grille': { anim: 'none', origin: [1305, 750] },
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
// split the agent's stovefire.svg into flames and logs, and lift the grille bars out of right.svg
{
  const sf = fs.readFileSync(path.join(src, 'parts', 'stovefire.svg'), 'utf8');
  const iLogs = sf.indexOf('<path d="M1262,778 Q1285,768');
  const iClipEnd = sf.lastIndexOf('</g>', sf.lastIndexOf('</g>') - 1);
  if (iLogs < 0 || iClipEnd < iLogs) throw new Error('unexpected stovefire.svg layout');
  const defs = sf.slice(sf.indexOf('<defs>'), sf.indexOf('</defs>') + 7);
  fs.writeFileSync(path.join(dir, 'iparts', 'fire-back.svg'), (sf.slice(0, iLogs) + sf.slice(iClipEnd)).replace(' mask="url(#stovefire-bars)"', ''));
  fs.writeFileSync(path.join(dir, 'iparts', 'fire-logs.svg'), wrap(`${defs}<g clip-path="url(#stovefire-clip)">${sf.slice(iLogs, iClipEnd)}</g>`));
  const right = fs.readFileSync(path.join(src, 'layers', 'right.svg'), 'utf8');
  const bars = right.match(/<rect[^>]*y="706"[^>]*>|<path d="M1263,752[^>]*>|<circle[^>]*cy="754.5"[^>]*>/g) || [];
  if (bars.length < 10) throw new Error('grille bars not found in right.svg');
  fs.writeFileSync(path.join(dir, 'iparts', 'fire-grille.svg'), wrap(bars.join('\n')));
}
const meta = [];
for (const [id, p] of Object.entries(PARTS)) {
  const f = ['fire-back', 'fire-logs', 'fire-grille'].includes(id) ? path.join(dir, 'iparts', `${id}.svg`) : path.join(src, 'parts', `${id}.svg`);
  if (!fs.existsSync(f)) { console.warn(`interior part missing: ${id}`); continue; }
  if (path.dirname(f) !== path.join(dir, 'iparts')) fs.copyFileSync(f, path.join(dir, 'iparts', `${id}.svg`));
  meta.push({ id, layer: 'interior', anim: p.anim, origin: p.origin, vars: p.vars || {}, front: !!p.front, parent: null, below: false, pos: meta.length });
}
fs.writeFileSync(path.join(dir, 'iparts.json'), JSON.stringify(meta, null, 1));
console.log(`interior: ${layers.length} layers, ${meta.length} parts`);
