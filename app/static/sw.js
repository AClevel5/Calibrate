/* Calibrate service worker: network-first for all same-origin requests so a
   deploy is picked up immediately when online; the cache is only an offline
   fallback. This avoids stale JS/CSS (a fresh page + an old cached app.js). */
const CACHE = "calibrate-v19";
const SHELL = ["/static/styles.css", "/static/app.js", "/manifest.webmanifest"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  const { request } = e;
  if (request.method !== "GET") return;
  const url = new URL(request.url);

  // Let the browser handle cross-origin requests (e.g. the ZBar WASM module
  // from jsDelivr) directly — don't intercept or cache them.
  if (url.origin !== location.origin) return;

  // Never cache API calls.
  if (url.pathname.startsWith("/api/")) return;

  // Network-first for pages AND static assets: always current when online,
  // fall back to the cached copy only when offline.
  e.respondWith(
    fetch(request)
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(request, copy));
        return res;
      })
      .catch(() => caches.match(request))
  );
});
