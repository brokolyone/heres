// Сборка в один HTML для публикации: node tools/build.js
const fs = require('fs'), path = require('path');
const root = path.resolve(__dirname, '..');
const ORDER = ['core', 'env', 'cast_main', 'cast_case', 'iso', 'icons', 'font', 'font_cjk', 'ui', 'locale/ui_strings', 'locale/eula', 'locale/en', 'locale/zh', 'audio', 'remarks', 'cases', 'reputation', 'director', 'main'];
const head = `<title>Слово защиты</title>
<meta name="description" content="Пиксельная судебная игра: вы адвокат защиты в Высшем суде Калифорнии.">
<style>
  html, body { height: 100%; margin: 0; background: #0d0b10; overflow: hidden; }
  body { touch-action: none; user-select: none; -webkit-user-select: none; }
  #game { position: fixed; inset: 0; }
  canvas { display: block; image-rendering: pixelated; image-rendering: crisp-edges; cursor: pointer; }
</style>
<div id="game"></div>
`;
const scripts = ORDER.map(n => {
  const f = path.join(root, 'src', n + '.js');
  if (!fs.existsSync(f)) { return ''; }
  return `<script>/* ${n}.js */\n${fs.readFileSync(f, 'utf8').replace(/<\/script/gi, '<\\/script')}\n</script>`;
}).join('\n');
fs.mkdirSync(path.join(root, 'dist'), { recursive: true });
const base = b => `<script>window.G = window.G || {}; G.ASSET_BASE = '${b}';</script>\n`;
const out = head + base('') + scripts + '\n';
fs.writeFileSync(path.join(root, 'dist', 'index.html'), out);
// локальная версия с doctype
fs.writeFileSync(path.join(root, 'dist', 'play.html'), '<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"></head><body>' + head + base('../') + scripts + '</body></html>');
console.log('dist/index.html', (out.length / 1024).toFixed(1) + ' KB');
