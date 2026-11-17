/* MAIN — загрузка ассетов (атласы PNG, китайский шрифт, инструменты) и запуск */
(function () {
  const G = window.G;
  const base = G.ASSET_BASE || '';
  const params = new URLSearchParams(location.search);
  G.Save.load();
  G.mountCanvas(document.getElementById('game') || document.body);
  if (params.has('bake')) { window.__bakeReady = true; return; }   // режим запекания: tools/bake.js

  let progress = 0, ready = false, t0 = 0;
  const Boot = {
    enter() { t0 = G.time; },
    update() {
      if (ready && G.time - t0 > 0.6) {
        const first = !G.Save.data.langChosen && G.UI.LanguageScene ? G.UI.LanguageScene : G.UI.TitleScene;
        G.setScene(first);
      }
    },
    draw(ctx) {
      G.rect(ctx, 0, 0, G.W, G.H, G.PAL.black);
      const w = 160, x = (G.W - w) / 2, y = 120;
      if (G.Font) G.Font.draw(ctx, 'COURTROOM LOADING…', G.W / 2, y - 18, G.RAMP.gold[4], { align: 'center' });
      G.rect(ctx, x - 1, y - 1, w + 2, 8, G.RAMP.gold[2]);
      G.rect(ctx, x, y, w, 6, G.RAMP.neutral[1]);
      G.rect(ctx, x, y, Math.round(w * progress), 6, G.RAMP.gold[4]);
    },
  };
  G.start(Boot);
  (async () => {
    const jobs = [
      (params.has('noatlas') ? Promise.resolve() : G.Assets.load(base, p => { progress = p * 0.8; })),
      G.FontCJK ? G.FontCJK.load(base) : Promise.resolve(),
    ];
    await Promise.all(jobs);
    progress = 1; ready = true;
  })();
})();
