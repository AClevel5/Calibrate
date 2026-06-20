/* Calibrate service worker: cache the app shell, network-first for everything
   else so logged data and lookups always hit the server when online. */
const CACHE = "calibrate-v13";
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

  // Cache-first for static shell assets.
  if (url.pathname.startsWith("/static/") || url.pathname === "/manifest.webmanifest") {
    e.respondWith(
      caches.match(request).then((hit) => hit || fetch(request).then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(request, copy));
        return res;
      }))
    );
    return;
  }

  // Network-first for pages, fall back to cache when offline.
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
