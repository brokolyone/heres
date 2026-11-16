/* MAIN — точка входа */
(function () {
  const G = window.G;
  G.mountCanvas(document.getElementById('game') || document.body);
  const first = G.UI && G.UI.TitleScene;
  if (!first) { console.error('UI не загружен'); }
  G.start(first);
})();
