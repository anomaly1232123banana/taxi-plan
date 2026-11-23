const CACHE = "taxi-plan-v1";
const key = url => { const u = new URL(url); u.search = ""; return u.href; };
const SHELL = ["./", "index.html", "style.css", "plan-view.js", "app.js", "strings.json", "plan.json", "manifest.webmanifest", "icon.svg"];

self.addEventListener("install", e => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())); });
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", e => {
  const r = e.request, u = new URL(r.url);
  if (r.method !== "GET" || u.origin !== location.origin) return;
  e.respondWith(fetch(r).then(res => {
    if (res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(key(r.url), copy)); }
    return res;
  }).catch(() => caches.match(r, {ignoreSearch: true})));
});
