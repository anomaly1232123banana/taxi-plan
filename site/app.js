(function () {
  const app = document.getElementById("app");
  const toggled = new Set();
  let S = null, plan = null, pos = null, last = "";

  function render() {
    if (!S || !plan) return;
    const html = window.PlanView.renderPage(plan, S, new Date(), pos, toggled);
    if (html !== last) { app.innerHTML = html; last = html; }
  }
  async function load() {
    try {
      if (!S) { S = (await (await fetch("strings.json")).json()).en; document.title = S.title; if (!plan) app.textContent = S.loading; }
      plan = await (await fetch("plan.json?t=" + Date.now(), {cache: "no-store"})).json();
      render();
    } catch (e) { /* offline or bad fetch: keep what is on screen */ }
    if (navigator.geolocation) navigator.geolocation.getCurrentPosition(
      p => { pos = {lat: p.coords.latitude, lon: p.coords.longitude}; render(); }, () => {}, {timeout: 10000, maximumAge: 300000});
  }

  // Capture: toggle does not bubble. Set from details.open (never flip) so a re-render keeps opened cards open.
  app.addEventListener("toggle", ev => {
    const d = ev.target; if (!d.dataset || !d.dataset.id) return;
    const isNow = d.classList.contains("now");
    if (d.open !== isNow) toggled.add(d.dataset.id); else toggled.delete(d.dataset.id);
    const tap = d.querySelector(".tap"); if (tap && S) tap.textContent = d.open ? S.tap_close : S.tap_open;
    if (plan && S) last = window.PlanView.renderPage(plan, S, new Date(), pos, toggled);   // DOM already matches; skip a rewrite
  }, true);

  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") load(); });
  setInterval(render, 60000);
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
  load();
})();
