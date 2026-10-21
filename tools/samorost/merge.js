// Merge layer SVGs (bottom→top) into one SVG with a final film-grain/vignette overlay.
// usage: node merge.js out.svg bg.svg island.svg structures.svg flora.svg characters.svg
const fs = require('fs');
const [out, ...layers] = process.argv.slice(2);
const inner = layers.map(f => {
  const s = fs.readFileSync(f, 'utf8').replace(/<\?xml[^>]*>/, '').replace(/<!DOCTYPE[^>]*>/i, '');
  const body = s.slice(s.indexOf('>', s.indexOf('<svg')) + 1, s.lastIndexOf('</svg>'));
  return `<!-- ${f.split('/').pop()} -->\n${body}`;
}).join('\n');
const overlay = `
<defs>
  <filter id="final-grain" x="0" y="0" width="100%" height="100%">
    <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="7" result="n"/>
    <feColorMatrix in="n" type="matrix" values="0 0 0 0 0.45  0 0 0 0 0.4  0 0 0 0 0.3  0 0 0 0.09 0"/>
  </filter>
  <radialGradient id="final-vignette" cx="0.52" cy="0.5" r="0.75">
    <stop offset="0.55" stop-color="#000" stop-opacity="0"/>
    <stop offset="1" stop-color="#05110f" stop-opacity="0.55"/>
  </radialGradient>
  <radialGradient id="final-warm" cx="0.5" cy="0.55" r="0.4">
    <stop offset="0" stop-color="#f3d27a" stop-opacity="0.08"/>
    <stop offset="1" stop-color="#f3d27a" stop-opacity="0"/>
  </radialGradient>
</defs>
<g id="layer-final">
  <rect width="1600" height="1000" fill="url(#final-warm)"/>
  <rect width="1600" height="1000" fill="url(#final-vignette)"/>
  <rect width="1600" height="1000" filter="url(#final-grain)" opacity="1"/>
</g>`;
fs.writeFileSync(out, `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 1600 1000" width="1600" height="1000">\n${inner}\n${overlay}\n</svg>\n`);
