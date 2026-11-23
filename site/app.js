(function () {
  const app = document.getElementById("app");
  const toggled = new Map();   // card id -> open state he left it in
  let S = null, plan = null, pos = null, last = "", lastNow = new Date(), lastPosAt = 0;

  function render() {
    if (!S || !plan) return;
    const now = new Date(), html = window.PlanView.renderPage(plan, S, now, pos, toggled);
    if (html !== last) { app.innerHTML = html; last = html; lastNow = now; }
  }
  function getPos() {
    lastPosAt = Date.now();
    if (navigator.geolocation) navigator.geolocation.getCurrentPosition(
      p => { pos = {lat: p.coords.latitude, lon: p.coords.longitude}; render(); }, () => {}, {timeout: 10000, maximumAge: 60000});
  }
  function tick() { render(); if (window.PlanView.shouldRefreshPos(lastPosAt, Date.now())) getPos(); }
  async function load() {
    try {
      if (!S) { S = (await (await fetch("strings.json")).json()).en; document.title = S.title; if (!plan) app.textContent = S.loading; }
      plan = await (await fetch("plan.json?t=" + Date.now(), {cache: "no-store"})).json();
      render();
    } catch (e) { /* offline or bad fetch: keep what is on screen */ }
    getPos();
  }

  // Capture: toggle does not bubble. Set from details.open (never flip) so a re-render keeps opened cards open.
  app.addEventListener("toggle", ev => {
    const d = ev.target; if (!d.dataset || !d.dataset.id) return;
    toggled.set(d.dataset.id, d.open);
    const tap = d.querySelector(".tap"); if (tap && S) tap.textContent = d.open ? S.tap_close : S.tap_open;
    if (plan && S) last = window.PlanView.renderPage(plan, S, lastNow, pos, toggled);   // same time as the DOM drawn, so a stale DOM is still rewritten next tick
  }, true);

  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") load(); });
  setInterval(tick, 60000);
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
  load();
})();
