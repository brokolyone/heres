// Собрать все русские строки игры для перевода: node tools/extract_strings.js
// Пишет tools/out/strings_ru.json и для каждого языка tools/out/missing_<lang>.json
const fs = require('fs'), path = require('path');
const root = path.resolve(__dirname, '..');
const cyr = /[А-Яа-яЁё]/;
const set = new Set();
global.window = { G: {} }; global.G = window.G;
const load = f => { try { require(path.join(root, 'src', f)); } catch (e) { console.warn('skip', f, e.message); } };
['cases.js', 'remarks.js'].forEach(load);
const walk = v => {
  if (typeof v === 'string') { if (cyr.test(v)) set.add(v); return; }
  if (Array.isArray(v)) return v.forEach(walk);
  if (v && typeof v === 'object') for (const k in v) walk(v[k]);
};
walk(window.G.Cases); walk(window.G.Remarks); walk(window.G.CaseMeta);
// литералы из кода (режиссёр, персонажи)
for (const f of ['director.js', 'cast_main.js', 'cast_case.js', 'iso.js']) {
  const p = path.join(root, 'src', f); if (!fs.existsSync(p)) continue;
  const src = fs.readFileSync(p, 'utf8');
  for (const m of src.matchAll(/'((?:[^'\\\n]|\\.)*)'/g)) if (cyr.test(m[1]) && !m[1].includes("' +")) set.add(m[1].replace(/\\'/g, "'"));
}
const all = [...set].sort();
fs.mkdirSync(path.join(root, 'tools/out'), { recursive: true });
fs.writeFileSync(path.join(root, 'tools/out/strings_ru.json'), JSON.stringify(all, null, 0));
for (const lang of ['en', 'zh']) {
  window.G.L10N = {}; window.G.L10N[lang] = {};
  const lf = path.join(root, 'src/locale', lang + '.js');
  if (fs.existsSync(lf)) { delete require.cache[lf]; try { require(lf); } catch (e) { console.warn(lang, e.message); } }
  const have = window.G.L10N[lang] || {};
  const miss = all.filter(s => !(s in have));
  fs.writeFileSync(path.join(root, 'tools/out/missing_' + lang + '.json'), JSON.stringify(miss, null, 0));
  console.log(lang, 'total', all.length, 'missing', miss.length, 'chars', miss.join('').length);
}
