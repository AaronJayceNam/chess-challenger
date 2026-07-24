/* Matevio service worker — makes the app installable and fast, while keeping
   updates instant. The API and WebSocket always go straight to the network;
   the HTML is network-first (so a new deploy's ?v= assets load immediately),
   and versioned static assets are cache-first. Bump CACHE to purge old caches. */
const CACHE = "matevio-v21";
const SHELL = [
  "/",
  "/static/style.css",
  "/static/i18n.js",
  "/static/app.js",
  "/static/puzzles.json",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
];

self.addEventListener("install", (e) => {
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL).catch(() => {})));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  const url = new URL(req.url);
  // never cache: API calls, websockets, non-GET, cross-origin — always live
  if (req.method !== "GET" || url.origin !== location.origin) return;
  if (url.pathname.startsWith("/api/") || url.pathname === "/ws" || url.pathname === "/sw.js") return;

  // HTML navigations: network-first so the newest page (and its ?v= links) win,
  // and live data is never stale; fall back to the cached shell only when offline.
  if (req.mode === "navigate") {
    e.respondWith(
      fetch(req)
        .then((r) => { const copy = r.clone(); caches.open(CACHE).then((c) => c.put("/", copy)); return r; })
        .catch(() => caches.match("/"))
    );
    return;
  }

  // versioned assets + icons: cache-first, then network (and store it)
  e.respondWith(
    caches.match(req).then((hit) =>
      hit ||
      fetch(req).then((r) => {
        if (r && r.ok) { const copy = r.clone(); caches.open(CACHE).then((c) => c.put(req, copy)); }
        return r;
      })
    )
  );
});
