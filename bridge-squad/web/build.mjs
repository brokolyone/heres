// Bundles the game into one self-contained dist/index.html (models, fonts and code inlined),
// which the Android app loads from its assets.
import { build } from 'esbuild';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';

const res = await build({
  entryPoints: ['src/main.js'],
  bundle: true,
  minify: true,
  format: 'iife',
  target: ['chrome80'],
  loader: { '.glb': 'binary' },
  write: false,
  legalComments: 'none',
});
const js = res.outputFiles[0].text.replace(/<\/script/gi, '<\\/script');
const font = f => 'data:font/woff2;base64,' + readFileSync(f).toString('base64');
const css = readFileSync('src/style.css', 'utf8')
  .replace('__OSW_CYR__', font('src/fonts/oswald-cyr.woff2'))
  .replace('__OSW_LAT__', font('src/fonts/oswald-lat.woff2'))
  .replace('__MONO_CYR__', font('src/fonts/mono-cyr.woff2'))
  .replace('__MONO_LAT__', font('src/fonts/mono-lat.woff2'));
const html = readFileSync('src/index.html', 'utf8')
  .replace('/*__CSS__*/', () => css)
  .replace('/*__JS__*/', () => js);
mkdirSync('dist', { recursive: true });
writeFileSync('dist/index.html', html);
console.log('dist/index.html', (html.length / 1024).toFixed(0) + ' KB');
