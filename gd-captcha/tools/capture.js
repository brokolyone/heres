// Снимает части настоящего виджета reCAPTCHA с демо-страницы Google:
// плашку (с подписью «captcha»), окно 4x4 со своей сценой, кнопки,
// сообщения об ошибках и вид выбранной клетки. Пишет PNG и layout.json.
// Запуск: PW=$(npm root -g)/playwright node capture.js <scene.png> <outdir>
const { chromium } = require(process.env.PW || 'playwright');
const fs = require('fs');
const path = require('path');

const [scenePath, out] = process.argv.slice(2);
const SCALE = 2;

(async () => {
  fs.mkdirSync(out, { recursive: true });
  const sceneUrl = 'data:image/png;base64,' + fs.readFileSync(scenePath).toString('base64');
  const b = await chromium.launch();
  const p = await b.newPage({ deviceScaleFactor: SCALE, viewport: { width: 1000, height: 900 } });
  await p.goto('https://www.google.com/recaptcha/api2/demo', { waitUntil: 'networkidle', timeout: 60000 });
  const anchorEl = await p.waitForSelector('iframe[title="reCAPTCHA"]');
  const anchor = await anchorEl.contentFrame();
  await p.waitForTimeout(1500);

  // Плашка: подпись меняем на «captcha», ссылки Privacy/Terms оставляем как есть.
  await anchor.evaluate(() => {
    const t = document.querySelector('.rc-anchor-logo-text');
    if (t) t.textContent = 'captcha';
  });
  await p.mouse.move(5, 5);
  await p.waitForTimeout(500);
  const ab = await anchorEl.boundingBox();
  const widgetGeo = await anchor.evaluate(() => {
    const r = s => { const e = document.querySelector(s); if (!e) return null; const b = e.getBoundingClientRect(); return { x: b.x, y: b.y, w: b.width, h: b.height }; };
    const cs = getComputedStyle(document.querySelector('.recaptcha-checkbox-border'));
    const ck = getComputedStyle(document.querySelector('.recaptcha-checkbox-checkmark'));
    return {
      anchor: r('.rc-anchor'), checkbox: r('.recaptcha-checkbox-border'),
      spinner: r('.recaptcha-checkbox-spinner'), checkmark: r('.recaptcha-checkbox-checkmark'),
      borderColor: cs.borderColor, checkmarkBg: ck.backgroundImage, checkmarkPos: ck.backgroundPosition,
      checkmarkSize: ck.backgroundSize,
    };
  });
  await anchorEl.screenshot({ path: path.join(out, 'widget_full.png') });
  await anchor.evaluate(() => { document.querySelector('.recaptcha-checkbox-border').style.visibility = 'hidden'; });
  await anchorEl.screenshot({ path: path.join(out, 'widget_base.png') });
  await anchor.evaluate(() => { document.querySelector('.recaptcha-checkbox-border').style.visibility = ''; });

  // Открываем задание и перезагружаем, пока не выпадут светофоры 4x4.
  await p.mouse.move(ab.x + 20, ab.y + 30, { steps: 10 });
  await p.mouse.click(ab.x + 28, ab.y + 39);
  let chEl;
  for (let i = 0; i < 40 && !chEl; i++) {
    for (const el of await p.$$('iframe')) {
      if (/challenge/i.test((await el.getAttribute('title')) || '') && (await el.boundingBox())?.height > 100) chEl = el;
    }
    if (!chEl) await p.waitForTimeout(500);
  }
  if (!chEl) throw new Error('challenge did not open');
  const ch = await chEl.contentFrame();
  let ok = false;
  for (let i = 0; i < 80 && !ok; i++) {
    await p.waitForTimeout(2500);
    const t = await ch.evaluate(() => document.querySelector('.rc-imageselect-desc-wrapper')?.innerText || '');
    const n = await ch.evaluate(() => document.querySelectorAll('.rc-imageselect-tile').length);
    console.log(i, JSON.stringify(t), n);
    if (/traffic lights/i.test(t) && n === 16) ok = true;
    else await ch.click('#recaptcha-reload-button').catch(() => {});
  }
  if (!ok) throw new Error('no 4x4 traffic lights challenge');
  await p.waitForTimeout(2500);

  // Свою сцену ставим во все клетки (там одна картинка со смещениями).
  await ch.evaluate(url => {
    for (const img of document.querySelectorAll('.rc-imageselect-tile img')) {
      img.src = url;
      img.style.imageRendering = 'pixelated';
    }
  }, sceneUrl);
  await p.waitForTimeout(1000);

  const pageGeo = async () => ({
    anchor: await anchorEl.boundingBox(),
    challenge: await chEl.boundingBox(),
  });
  const chGeo = () => ch.evaluate(() => {
    const r = e => { if (!e) return null; const b = e.getBoundingClientRect(); return { x: b.x, y: b.y, w: b.width, h: b.height }; };
    const q = s => document.querySelector(s);
    return {
      tiles: [...document.querySelectorAll('.rc-imageselect-tile')].map(r),
      tileWrappers: [...document.querySelectorAll('.rc-image-tile-wrapper')].map(r),
      verify: r(q('#recaptcha-verify-button')),
      reload: r(q('#recaptcha-reload-button')),
      footer: r(q('.rc-footer')),
      table: r(q('table')),
      desc: r(q('.rc-imageselect-desc-wrapper')),
      payload: r(q('.rc-imageselect-payload')),
      checkbox: r(q('.rc-imageselect-checkbox')),
      buttonText: q('#recaptcha-verify-button')?.innerText,
    };
  });

  // Полная страница вокруг виджета и окна: стрелка, тень и белая подложка.
  const pg = await pageGeo();
  const clip = {
    x: Math.max(0, pg.anchor.x - 20), y: Math.max(0, Math.min(pg.anchor.y, pg.challenge.y) - 20),
  };
  clip.w = Math.max(pg.anchor.x + pg.anchor.width, pg.challenge.x + pg.challenge.width) + 20 - clip.x;
  clip.h = Math.max(pg.anchor.y + pg.anchor.height, pg.challenge.y + pg.challenge.height) + 20 - clip.y;
  const overlayInfo = await p.evaluate(() => {
    const out = [];
    for (const d of document.querySelectorAll('body > div')) {
      const s = getComputedStyle(d);
      out.push({ z: s.zIndex, pos: s.position, vis: s.visibility, op: s.opacity, kids: [...d.children].map(k => { const ks = getComputedStyle(k); const b = k.getBoundingClientRect(); return { tag: k.tagName, bg: ks.backgroundColor, op: ks.opacity, w: b.width, h: b.height, x: b.x, y: b.y, border: ks.border, shadow: ks.boxShadow }; }) });
    }
    return out;
  });
  const shot = name => p.screenshot({ path: path.join(out, name), clip: { x: clip.x, y: clip.y, width: clip.w, height: clip.h } });
  await shot('page_challenge.png');
  const g0 = await chGeo();

  // Кнопка: SKIP (ничего не выбрано) и VERIFY.
  await chEl.screenshot({ path: path.join(out, 'challenge_skip.png') });
  await ch.evaluate(() => {
    const b = document.querySelector('#recaptcha-verify-button');
    b.dataset.orig = b.textContent; b.textContent = 'Verify';
  });
  await chEl.screenshot({ path: path.join(out, 'challenge_verify.png') });
  await ch.evaluate(() => { const b = document.querySelector('#recaptcha-verify-button'); b.textContent = b.dataset.orig; });

  // Сообщения об ошибках: показываем по одному.
  const errs = await ch.evaluate(() => [...document.querySelectorAll('[class*="rc-imageselect-error"], .rc-imageselect-incorrect-response')].map(e => e.className));
  console.log('errors', errs);
  const errGeo = {};
  for (const cls of errs) {
    const sel = '.' + cls.trim().split(/\s+/)[0];
    const g = await ch.evaluate(sel => {
      const e = document.querySelector(sel);
      e.style.display = 'block';
      const b = e.getBoundingClientRect();
      return { text: e.innerText, x: b.x, y: b.y, w: b.width, h: b.height, color: getComputedStyle(e).color, font: getComputedStyle(e).font };
    }, sel);
    errGeo[cls] = g;
    if (g.h > 0) {
      await p.waitForTimeout(200);
      const cb = await chEl.boundingBox();
      await chEl.screenshot({ path: path.join(out, 'err_' + sel.slice(1) + '.png') });
      errGeo[cls].frameH = cb.height;
    }
    await ch.evaluate(sel => { document.querySelector(sel).style.display = ''; }, sel);
  }
  await p.waitForTimeout(300);

  // Выбранная клетка: кликаем первую и снимаем.
  const t0 = g0.tiles[0];
  const cbx = await chEl.boundingBox();
  await p.mouse.click(cbx.x + t0.x + t0.w / 2, cbx.y + t0.y + t0.h / 2);
  await p.waitForTimeout(1200);
  await chEl.screenshot({ path: path.join(out, 'challenge_selected.png') });
  const g1 = await chGeo();
  const selStyle = await ch.evaluate(() => {
    const t = document.querySelector('.rc-imageselect-tileselected');
    if (!t) return null;
    const img = t.querySelector('img'); const w = t.querySelector('.rc-image-tile-wrapper');
    const ck = t.querySelector('.rc-imageselect-checkbox');
    const r = e => { const b = e.getBoundingClientRect(); return { x: b.x, y: b.y, w: b.width, h: b.height }; };
    return { wrapper: r(w), wrapperTransform: getComputedStyle(w).transform, img: r(img), check: ck ? r(ck) : null, checkBg: ck ? getComputedStyle(ck).backgroundImage : null, tileBg: getComputedStyle(t).backgroundColor, wrapperBg: getComputedStyle(w).backgroundColor };
  });

  // Картинки галочек и спиннера: забираем спрайты, на которые ссылается CSS.
  const fetchSprite = async (frame, css, name) => {
    const m = /url\("?(.*?)"?\)/.exec(css || '');
    if (!m) return null;
    const buf = await frame.evaluate(async u => {
      const r = await fetch(u); const a = new Uint8Array(await r.arrayBuffer());
      let s = ''; for (const x of a) s += String.fromCharCode(x); return btoa(s);
    }, m[1]).catch(e => null);
    if (buf) fs.writeFileSync(path.join(out, name), Buffer.from(buf, 'base64'));
    return m[1];
  };
  const checkmarkUrl = await fetchSprite(anchor, widgetGeo.checkmarkBg, 'sprite_checkmark.png');
  const tileCheckUrl = await fetchSprite(ch, selStyle?.checkBg, 'sprite_tilecheck.png');
  const spinnerCss = await anchor.evaluate(() => {
    const out = {};
    for (const s of ['.recaptcha-checkbox-spinner', '.recaptcha-checkbox-spinner-overlay', '.recaptcha-checkbox-spinner-gif', '.recaptcha-checkbox-checkmark']) {
      const e = document.querySelector(s); if (!e) continue; const c = getComputedStyle(e);
      out[s] = { bg: c.backgroundImage, pos: c.backgroundPosition, size: c.backgroundSize, w: c.width, h: c.height, border: c.border, borderColor: c.borderColor, anim: c.animation };
    }
    return out;
  });

  fs.writeFileSync(path.join(out, 'layout.json'), JSON.stringify({
    scale: SCALE, clip, page: pg, widget: widgetGeo, challenge: g0, challengeSelected: g1,
    selStyle, errGeo, overlayInfo, checkmarkUrl, tileCheckUrl, spinnerCss,
  }, null, 1));
  await b.close();
})().catch(e => { console.error(e); process.exit(1); });
