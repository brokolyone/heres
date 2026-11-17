/* =====================================================================
   FONT — пиксельные шрифты «Слово защиты», нарисованные с нуля.
   small: основной шрифт диалогов (заглавные 7 px, строчные 5 px, строка 10 px)
   big:   жирный шрифт заголовков (заглавные 10 px, строка 14 px) — выводится из small
          растяжкой опорных строк и утолщением штрихов без слипания просветов
   title: дисплейный жирный (заглавные 14 px, строка 20 px) — small, увеличенный
          по алгоритму Scale2x (сглаженные диагонали) и утолщённый; только заглавные
   Разметка: *выделение* (красным), {p} и любые {..} — пауза, не рисуется, \* — звёздочка.
   ===================================================================== */
(function () {
'use strict';
const G = window.G;

/* ---------------------------------------------------------------------
   Глифы small. Формат: 'верхняя_строка:ряд/ряд/...' ('#' — пиксель).
   Ячейка 10 строк: 0 — диакритика заглавных, 1–7 — заглавные (база под 7),
   3–7 — строчные, 8–9 — выносные вниз.
   --------------------------------------------------------------------- */
const S = {
  // --- Кириллица, заглавные
  'А': '1:.###./#...#/#...#/#####/#...#/#...#/#...#',
  'Б': '1:#####/#..../#..../####./#...#/#...#/####.',
  'В': '1:####./#...#/#...#/####./#...#/#...#/####.',
  'Г': '1:#####/#..../#..../#..../#..../#..../#....',
  'Д': '1:..###./..#.#./..#.#./.#..#./.#..#./.#..#./######/#....#',
  'Е': '1:#####/#..../#..../####./#..../#..../#####',
  'Ё': '0:.#.#./...../#####/#..../####./#..../#..../#####',
  'Ж': '1:#..#..#/#..#..#/.#.#.#./..###../.#.#.#./#..#..#/#..#..#',
  'З': '1:.###./#...#/....#/..##./....#/#...#/.###.',
  'И': '1:#...#/#...#/#..##/#.#.#/##..#/#...#/#...#',
  'Й': '0:.###./...../#...#/#..##/#.#.#/#.#.#/##..#/#...#',
  'К': '1:#...#/#..#./#.#../##.../#.#../#..#./#...#',
  'Л': '1:..###/.#..#/.#..#/.#..#/.#..#/.#..#/#...#',
  'М': '1:#.....#/##...##/#.#.#.#/#..#..#/#.....#/#.....#/#.....#',
  'Н': '1:#...#/#...#/#...#/#####/#...#/#...#/#...#',
  'О': '1:.###./#...#/#...#/#...#/#...#/#...#/.###.',
  'П': '1:#####/#...#/#...#/#...#/#...#/#...#/#...#',
  'Р': '1:####./#...#/#...#/####./#..../#..../#....',
  'С': '1:.###./#...#/#..../#..../#..../#...#/.###.',
  'Т': '1:#####/..#../..#../..#../..#../..#../..#..',
  'У': '1:#...#/#...#/#...#/.####/....#/#...#/.###.',
  'Ф': '1:..#../.###./#.#.#/#.#.#/#.#.#/.###./..#..',
  'Х': '1:#...#/#...#/.#.#./..#../.#.#./#...#/#...#',
  'Ц': '1:#...#./#...#./#...#./#...#./#...#./#...#./######/.....#',
  'Ч': '1:#...#/#...#/#...#/.####/....#/....#/....#',
  'Ш': '1:#..#..#/#..#..#/#..#..#/#..#..#/#..#..#/#..#..#/#######',
  'Щ': '1:#..#..#./#..#..#./#..#..#./#..#..#./#..#..#./#..#..#./########/.......#',
  'Ъ': '1:##..../.#..../.#..../.####./.#...#/.#...#/.####.',
  'Ы': '1:#.....#/#.....#/#.....#/####..#/#...#.#/#...#.#/####..#',
  'Ь': '1:#..../#..../#..../####./#...#/#...#/####.',
  'Э': '1:.###./#...#/....#/..###/....#/#...#/.###.',
  'Ю': '1:#..###./#.#...#/#.#...#/###...#/#.#...#/#.#...#/#..###.',
  'Я': '1:.####/#...#/#...#/.####/..#.#/.#..#/#...#',
  // --- Кириллица, строчные
  'а': '3:.###./....#/.####/#...#/.####',
  'б': '1:.####/#..../####./#...#/#...#/#...#/.###.',
  'в': '3:####./#...#/####./#...#/####.',
  'г': '3:####/#.../#.../#.../#...',
  'д': '3:..##./.#.#./.#.#./.#.#./#####/#...#',
  'е': '3:.###./#...#/#####/#..../.###.',
  'ё': '1:.#.#./...../.###./#...#/#####/#..../.###.',
  'ж': '3:#.#.#/#.#.#/.###./#.#.#/#.#.#',
  'з': '3:.###./#...#/..##./#...#/.###.',
  'и': '3:#...#/#..##/#.#.#/##..#/#...#',
  'й': '1:.###./...../#...#/#..##/#.#.#/##..#/#...#',
  'к': '3:#..#/#.#./##../#.#./#..#',
  'л': '3:..###/.#..#/.#..#/.#..#/#...#',
  'м': '3:#...#/##.##/#.#.#/#...#/#...#',
  'н': '3:#...#/#...#/#####/#...#/#...#',
  'о': '3:.###./#...#/#...#/#...#/.###.',
  'п': '3:#####/#...#/#...#/#...#/#...#',
  'р': '3:####./#...#/#...#/#...#/####./#..../#....',
  'с': '3:.###./#...#/#..../#...#/.###.',
  'т': '3:#####/..#../..#../..#../..#..',
  'у': '3:#...#/#...#/#...#/#...#/.####/....#/.###.',
  'ф': '1:..#../..#../.###./#.#.#/#.#.#/#.#.#/.###./..#../..#..',
  'х': '3:#...#/.#.#./..#../.#.#./#...#',
  'ц': '3:#..#./#..#./#..#./#..#./#####/....#',
  'ч': '3:#...#/#...#/.####/....#/....#',
  'ш': '3:#.#.#/#.#.#/#.#.#/#.#.#/#####',
  'щ': '3:#.#.#./#.#.#./#.#.#./#.#.#./######/.....#',
  'ъ': '3:##.../.#.../.###./.#..#/.###.',
  'ы': '3:#....#/#....#/###..#/#..#.#/###..#',
  'ь': '3:#.../#.../###./#..#/###.',
  'э': '3:.###./#...#/..###/#...#/.###.',
  'ю': '3:#..##./#.#..#/###..#/#.#..#/#..##.',
  'я': '3:.####/#...#/.####/.#..#/#...#',
  // --- Латиница (совпадающие с кириллицей формы — ниже через псевдонимы)
  'D': '1:####./#...#/#...#/#...#/#...#/#...#/####.',
  'F': '1:#####/#..../#..../####./#..../#..../#....',
  'G': '1:.###./#...#/#..../#.###/#...#/#...#/.###.',
  'I': '1:###/.#./.#./.#./.#./.#./###',
  'J': '1:..###/...#./...#./...#./...#./#..#./.##..',
  'L': '1:#..../#..../#..../#..../#..../#..../#####',
  'N': '1:#...#/##..#/##..#/#.#.#/#..##/#..##/#...#',
  'Q': '1:.###./#...#/#...#/#...#/#.#.#/#..#./.##.#',
  'R': '1:####./#...#/#...#/####./#.#../#..#./#...#',
  'S': '1:.###./#...#/#..../.###./....#/#...#/.###.',
  'U': '1:#...#/#...#/#...#/#...#/#...#/#...#/.###.',
  'V': '1:#...#/#...#/#...#/#...#/.#.#./.#.#./..#..',
  'W': '1:#.....#/#.....#/#.....#/#..#..#/#..#..#/#.#.#.#/.#...#.',
  'Y': '1:#...#/#...#/.#.#./..#../..#../..#../..#..',
  'Z': '1:#####/....#/...#./..#../.#.../#..../#####',
  'b': '1:#..../#..../####./#...#/#...#/#...#/####.',
  'd': '1:....#/....#/.####/#...#/#...#/#...#/.####',
  'f': '1:..##/.#../####/.#../.#../.#../.#..',
  'g': '3:.####/#...#/#...#/#...#/.####/....#/.###.',
  'h': '1:#..../#..../####./#...#/#...#/#...#/#...#',
  'i': '1:#/./#/#/#/#/#',
  'j': '1:..#/.../..#/..#/..#/..#/..#/#.#/.#.',
  'k': '1:#.../#.../#..#/#.#./##../#.#./#..#',
  'l': '1:##./.#./.#./.#./.#./.#./###',
  'm': '3:####./#.#.#/#.#.#/#.#.#/#.#.#',
  'n': '3:####./#...#/#...#/#...#/#...#',
  'q': '3:.####/#...#/#...#/#...#/.####/....#/....#',
  'r': '3:#.##/##../#.../#.../#...',
  's': '3:.####/#..../.###./....#/####.',
  't': '1:.#../.#../###./.#../.#../.#../..##',
  'u': '3:#...#/#...#/#...#/#..##/.##.#',
  'v': '3:#...#/#...#/#...#/.#.#./..#..',
  'w': '3:#...#/#...#/#.#.#/#.#.#/.#.#.',
  'z': '3:#####/...#./..#../.#.../#####',
  // --- Цифры
  '0': '1:.###./#...#/#..##/#.#.#/##..#/#...#/.###.',
  '1': '1:..#../.##../#.#../..#../..#../..#../#####',
  '2': '1:.###./#...#/....#/...#./..#../.#.../#####',
  '3': '1:.###./#...#/....#/..##./....#/#...#/.###.',
  '4': '1:...#./..##./.#.#./#..#./#####/...#./...#.',
  '5': '1:#####/#..../####./....#/....#/#...#/.###.',
  '6': '1:.###./#..../#..../####./#...#/#...#/.###.',
  '7': '1:#####/....#/...#./..#../..#../..#../..#..',
  '8': '1:.###./#...#/#...#/.###./#...#/#...#/.###.',
  '9': '1:.###./#...#/#...#/.####/....#/....#/.###.',
  // --- Знаки
  '.': '7:#',
  ',': '7:.#/#.',
  '!': '1:#/#/#/#/#/./#',
  '?': '1:.###./#...#/....#/...#./..#../...../..#..',
  ':': '4:#/././#',
  ';': '4:.#/../../.#/#.',
  '-': '5:###',
  '–': '5:####',
  '—': '5:#######',
  '«': '4:.#.#/#.#./.#.#',
  '»': '4:#.#./.#.#/#.#.',
  '"': '1:#.#/#.#',
  "'": '1:#/#',
  '(': '1:.#/#./#./#./#./#./#./.#',
  ')': '1:#./.#/.#/.#/.#/.#/.#/#.',
  '[': '1:##/#./#./#./#./#./#./##',
  ']': '1:##/.#/.#/.#/.#/.#/.#/##',
  '/': '1:....#/...#./...#./..#../.#.../.#.../#....',
  '\\': '1:#..../.#.../.#.../..#../...#./...#./....#',
  '%': '1:##..#/##.#./...#./..#../.#.../.#.##/#..##',
  '№': '1:#..#..../##.#..#./##.#.#.#/#.##..#./#.##..../#..#.###/#..#....',
  '§': '1:.###/#.../.##./#..#/.##./...#/###.',
  '$': '0:..#../.####/#.#../#.#../.###./..#.#/..#.#/####./..#..',
  '+': '3:..#../..#../#####/..#../..#..',
  '=': '4:####/..../####',
  '*': '2:#.#.#/.###./#.#.#',
  '…': '7:#.#.#',
  '#': '2:.#.#./#####/.#.#./#####/.#.#.',
  '@': '1:.####./#....#/#.##.#/#.#.##/#..##./#...../.####.',
  '&': '1:.##../#..#./#.#../.#.../#.#.#/#..#./.##.#',
  '_': '8:#####',
  '<': '3:..#/.#./#../.#./..#',
  '>': '3:#../.#./..#/.#./#..',
  '•': '4:.#./###/.#.',
  '·': '5:#',
  '°': '1:.#./#.#/.#.',
  '^': '1:.#./#.#',
  '|': '1:#/#/#/#/#/#/#/#',
  '~': '4:.#.#/#.#.',
  '€': '1:..###/.#.../####./.#.../####./.#.../..###',
  '▼': '3:#####/.###./..#..',
  '►': '2:#.../##../###./##../#...',
  '◄': '2:...#/..##/.###/..##/...#',
  '▲': '3:..#../.###./#####',
  '▶': '2:#.../##../###./##../#...',
};
// Латиница и знаки, совпадающие по форме
const ALIAS = {
  A: 'А', B: 'В', C: 'С', E: 'Е', H: 'Н', K: 'К', M: 'М', O: 'О', P: 'Р', T: 'Т', X: 'Х',
  a: 'а', c: 'с', e: 'е', o: 'о', p: 'р', x: 'х', y: 'у',
  '’': "'", '‘': "'", '“': '"', '”': '"', '„': '"', '‑': '-', '−': '-', '×': 'х',
  ' ': ' ',
};
const SPACE_ADV = { small: 4, big: 5, title: 8 };
const GAP = { small: 1, big: 1, title: 2 };

function parseGlyph(def, H) {
  const k = def.indexOf(':');
  const top = +def.slice(0, k);
  const rows = def.slice(k + 1).split('/');
  const w = Math.max(...rows.map(r => r.length));
  const m = new Uint8Array(w * H);
  rows.forEach((r, j) => { for (let i = 0; i < r.length; i++) if (r[i] === '#') m[(top + j) * w + i] = 1; });
  return { w, h: H, m };
}

/* --- big: растяжка строк 1,4,7 (верх, середина, низ заглавных) и утолщение --- */
const BIG_DUP = new Set([1, 4, 7]);
function toBig(g) {
  const rowsMap = [];
  for (let r = 0; r < 10; r++) { rowsMap.push(r); if (BIG_DUP.has(r)) rowsMap.push(r); }
  const H = rowsMap.length; // 13
  const src = (x, y) => (x >= 0 && x < g.w && y >= 0 && y < 10) ? g.m[y * g.w + x] : 0;
  // 1) удваиваем «стволы» — столбцы с вертикальным штрихом >= 3 px
  const cols = [];
  for (let x = 0; x < g.w; x++) {
    let run = 0, best = 0;
    for (let y = 0; y < 10; y++) { run = src(x, y) ? run + 1 : 0; best = Math.max(best, run); }
    cols.push(x);
    if (best >= 3 || g.w <= 2) cols.push(x);
  }
  if (cols.length === g.w) cols.push(-1); // ни одного ствола — пустая колонка, ниже утолщим
  const w = cols.length;
  const t = new Uint8Array(w * H);
  for (let j = 0; j < H; j++) for (let i = 0; i < w; i++) t[j * w + i] = cols[i] < 0 ? 0 : src(cols[i], rowsMap[j]);
  // 2) утолщаем остальные пиксели вправо, если не слипается просвет
  const m = new Uint8Array(w * H);
  const T = (x, y) => (x >= 0 && x < w) ? t[y * w + x] : 0;
  for (let j = 0; j < H; j++) for (let x = 0; x < w; x++) {
    let on = T(x, j);
    if (!on && T(x - 1, j) && !T(x - 2, j) && !T(x + 1, j)) on = 1;
    m[j * w + x] = on;
  }
  return { w, h: H, m };
}

/* --- title: Scale2x + утолщение вправо --- */
function scale2x(g) {
  const w = g.w, h = g.h, W = w * 2, H = h * 2;
  const m = new Uint8Array(W * H);
  const P = (x, y) => (x < 0 || y < 0 || x >= w || y >= h) ? 0 : g.m[y * w + x];
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const E = P(x, y), B = P(x, y - 1), D = P(x - 1, y), F = P(x + 1, y), Hh = P(x, y + 1);
    let e0 = E, e1 = E, e2 = E, e3 = E;
    if (B !== Hh && D !== F) {
      e0 = D === B ? D : E; e1 = B === F ? F : E;
      e2 = D === Hh ? D : E; e3 = Hh === F ? F : E;
    }
    m[(2 * y) * W + 2 * x] = e0; m[(2 * y) * W + 2 * x + 1] = e1;
    m[(2 * y + 1) * W + 2 * x] = e2; m[(2 * y + 1) * W + 2 * x + 1] = e3;
  }
  return { w: W, h: H, m };
}
function toTitle(g) {
  const s = scale2x(g);
  const w = s.w + 1, H = s.h;
  const m = new Uint8Array(w * H);
  for (let y = 0; y < H; y++) for (let x = 0; x < w; x++) {
    const a = x < s.w ? s.m[y * s.w + x] : 0;
    const b = x > 0 ? s.m[y * s.w + x - 1] : 0;
    m[y * w + x] = a || b ? 1 : 0;
  }
  return { w, h: H, m };
}

/* --- сборка атласов --- */
const FONTS = {};
function buildFont(name, glyphs, H, lineH) {
  const chars = Object.keys(glyphs);
  let W = 0; for (const c of chars) W += glyphs[c].w + 1;
  const map = {};
  let x = 0;
  for (const c of chars) { map[c] = { x, w: glyphs[c].w }; x += glyphs[c].w + 1; }
  const paint = (ax) => {
    ax.fillStyle = '#ffffff';
    for (const c of chars) {
      const g = glyphs[c], gx = map[c].x;
      for (let j = 0; j < g.h; j++) for (let i = 0; i < g.w; i++) if (g.m[j * g.w + i]) ax.fillRect(gx + i, j, 1, 1);
    }
  };
  const atlas = G.cacheCanvas ? G.cacheCanvas('ui/font/' + name, Math.max(1, W), H, paint)
    : (() => { const a = G.makeCanvas(Math.max(1, W), H); paint(a.getContext('2d')); return a; })();
  FONTS[name] = { name, atlas, map, h: H, lineH, gap: GAP[name], space: SPACE_ADV[name], tints: {} };
}
const smallG = {};
for (const c in S) smallG[c] = parseGlyph(S[c], 10);
const bigG = {}, titleG = {};
for (const c in smallG) { bigG[c] = toBig(smallG[c]); }
for (const c in smallG) {
  // title — только заглавные (строчные подменяются заглавными при выводе)
  if (c !== c.toUpperCase() && c.toLowerCase() === c && /[a-zа-яё]/.test(c)) continue;
  titleG[c] = toTitle(smallG[c]);
}
buildFont('small', smallG, 10, 10);
buildFont('big', bigG, 13, 14);
buildFont('title', titleG, 20, 20);

function tinted(f, col) {
  let c = f.tints[col];
  if (c) return c;
  c = G.makeCanvas(f.atlas.width, f.atlas.height);
  const x = c.getContext('2d');
  x.drawImage(f.atlas, 0, 0);
  x.globalCompositeOperation = 'source-in';
  x.fillStyle = col; x.fillRect(0, 0, c.width, c.height);
  f.tints[col] = c;
  return c;
}

function glyphOf(f, ch) {
  if (f.map[ch]) return f.map[ch];
  if (ALIAS[ch] && f.map[ALIAS[ch]]) return f.map[ALIAS[ch]];
  if (f.name === 'title') {
    const u = ch.toUpperCase();
    if (f.map[u]) return f.map[u];
    if (ALIAS[u] && f.map[ALIAS[u]]) return f.map[ALIAS[u]];
  }
  return null;
}
function fontOf(o) { return FONTS[(o && o.font) || 'small'] || FONTS.small; }

/* Токенизация строки с разметкой: возвращает [{ch} | {emph:true} | {pause}] */
function tokens(text) {
  const out = [];
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (ch === '\\' && text[i + 1] === '*') { out.push({ ch: '*' }); i++; continue; }
    if (ch === '*') { out.push({ emph: true }); continue; }
    if (ch === '{') {
      const k = text.indexOf('}', i);
      if (k > i && k - i < 16) { out.push({ pause: text.slice(i + 1, k) }); i = k; continue; }
    }
    out.push({ ch });
  }
  return out;
}

/* --- CJK через G.FontCJK (готовит интегратор) --- */
const CJK_RE = /[\u2e80-\u9fff\uf900-\ufaff\u3000-\u303f\uff00-\uffef]/;
const isCJK = ch => CJK_RE.test(ch);
const cjkAdvCache = {};
let cjkDummy = null;
function cjkOK(ch) { return !!(G.FontCJK && isCJK(ch) && G.FontCJK.has(ch)); }
function cjkAdv(ch) {
  if (cjkAdvCache[ch] != null) return cjkAdvCache[ch];
  if (G.FontCJK.advance) return (cjkAdvCache[ch] = G.FontCJK.advance(ch));
  if (!cjkDummy) cjkDummy = G.makeCanvas(16, 16).getContext('2d');
  return (cjkAdvCache[ch] = G.FontCJK.draw(cjkDummy, ch, 0, 0, '#ffffff') || 12);
}
function cjkY(f) { const h = G.FontCJK.h || 12; return f.name === 'small' ? 0 : Math.max(0, (f.lineH - h) >> 1); }
function lineHOf(f) {
  if (G.FontCJK && G.lang && G.lang() === 'zh' && f.name !== 'title') return Math.max(f.lineH, (G.FontCJK.h || 12) + 2);
  return f.lineH;
}

function advance(f, ch) {
  if (cjkOK(ch)) return cjkAdv(ch);
  if (ch === ' ') return f.space;
  const g = glyphOf(f, ch);
  return g ? g.w + f.gap : f.space;
}
function measureLine(f, line) {
  let w = 0, last = 0;
  for (const tk of tokens(line)) {
    if (!tk.ch) continue;
    const a = advance(f, tk.ch);
    w += a; last = tk.ch === ' ' ? 0 : f.gap;
  }
  return Math.max(0, w - last);
}

const Font = G.Font = {
  lineH: 10,
  fonts: FONTS,
  height(o) { return lineHOf(fontOf(o)); },
  isCJK,
  strip(text) {
    let s = '';
    for (const tk of tokens(String(text))) if (tk.ch) s += tk.ch;
    return s;
  },
  length(text) { return Font.strip(text).length; },
  measure(text, o) {
    const f = fontOf(o);
    let m = 0;
    for (const line of String(text).split('\n')) m = Math.max(m, measureLine(f, line));
    return m;
  },
  /* draw(ctx, text, x, y, color, o) — y = верх строки. Возвращает число выведенных видимых символов */
  draw(ctx, text, x, y, color, o) {
    o = o || {};
    const f = fontOf(o);
    text = String(text);
    color = color || G.PAL.white;
    const emphCol = o.emph || G.PAL.stamp;
    const maxChars = o.maxChars == null ? Infinity : o.maxChars;
    const lines = text.split('\n');
    let shown = 0, emph = false, cy = y | 0;
    const lh = o.lineH || lineHOf(f);
    for (let li = 0; li < lines.length; li++) {
      const line = lines[li];
      let cx = x | 0;
      if (o.align === 'center' || o.align === 'right') {
        const w = measureLine(f, line);
        cx = o.align === 'center' ? (x - (w >> 1)) | 0 : (x - w) | 0;
      }
      for (const tk of tokens(line)) {
        if (tk.emph) { emph = !emph; continue; }
        if (!tk.ch) continue;
        if (shown >= maxChars) return shown;
        shown++;
        const ch = tk.ch;
        if (ch === ' ') { cx += f.space; continue; }
        if (cjkOK(ch)) {
          const cyy = cy + cjkY(f);
          if (o.shadow) G.FontCJK.draw(ctx, ch, cx + (o.shadowX == null ? 1 : o.shadowX), cyy + (o.shadowY == null ? 1 : o.shadowY), o.shadow);
          cx += G.FontCJK.draw(ctx, ch, cx, cyy, emph ? emphCol : color) + (o.spacing || 0);
          continue;
        }
        const g = glyphOf(f, ch);
        if (!g) { cx += f.space; continue; }
        if (o.shadow) ctx.drawImage(tinted(f, o.shadow), g.x, 0, g.w, f.h, cx + (o.shadowX == null ? 1 : o.shadowX), cy + (o.shadowY == null ? 1 : o.shadowY), g.w, f.h);
        ctx.drawImage(tinted(f, emph ? emphCol : color), g.x, 0, g.w, f.h, cx, cy, g.w, f.h);
        if (o.bold) ctx.drawImage(tinted(f, emph ? emphCol : color), g.x, 0, g.w, f.h, cx + 1, cy, g.w, f.h);
        cx += g.w + f.gap + (o.bold ? 1 : 0) + (o.spacing || 0);
      }
      if (li < lines.length - 1) { if (shown >= maxChars) return shown; shown++; }
      cy += lh;
    }
    return shown;
  },
  /* Перенос по словам, разметка *…* сохраняется (закрывается/открывается на стыках строк) */
  wrap(text, maxW, o) {
    const f = fontOf(o);
    const out = [];
    let emph = false;
    const toggles = s => { let n = 0; for (const tk of tokens(s)) if (tk.emph) n++; return n; };
    const finish = (line, startEmph) => {
      let s = (startEmph ? '*' : '') + line;
      const endEmph = (toggles(s) & 1) === 1;
      if (endEmph) s += '*';
      out.push(s);
      return endEmph;
    };
    for (const para of String(text).split('\n')) {
      // единицы переноса: слова (через пробел) и отдельные иероглифы
      const units = [];
      let cur = '', curSp = false, pend = false;
      const push = () => { if (cur !== '') { units.push({ t: cur, sp: curSp }); cur = ''; } };
      for (const ch of para) {
        if (ch === ' ') { push(); pend = true; continue; }
        if (isCJK(ch)) { push(); units.push({ t: ch, sp: pend }); pend = false; continue; }
        if (cur === '') { curSp = pend; pend = false; }
        cur += ch;
      }
      push();
      let line = '', start = emph;
      for (const u of units) {
        const test = line === '' ? u.t : line + (u.sp ? ' ' : '') + u.t;
        if (line !== '' && measureLine(f, (start ? '*' : '') + test) > maxW) {
          emph = finish(line, start);
          start = emph; line = u.t;
        } else line = test;
        // слишком длинное слово — режем посимвольно
        while (measureLine(f, line) > maxW && Font.strip(line).length > 1) {
          let cut = line.length - 1;
          while (cut > 1 && measureLine(f, line.slice(0, cut)) > maxW) cut--;
          emph = finish(line.slice(0, cut), start);
          start = emph; line = line.slice(cut);
        }
      }
      emph = finish(line, start);
    }
    return out;
  },
  has(ch, o) { return !!glyphOf(fontOf(o), ch); },
  /* Маска глифа small {w,h:10,m} — для логотипов/крупных надписей в UI */
  mask(ch) { return smallG[ch] || smallG[ALIAS[ch]] || smallG[String(ch).toUpperCase()] || null; },
  scale2x,
  /* Высота заглавных и их верх внутри строки шрифта */
  capTop(o) { const n = fontOf(o).name; return n === 'title' ? 2 : 1; },
  capH(o) { const n = fontOf(o).name; return n === 'title' ? 14 : n === 'big' ? 10 : 7; },
};
})();
