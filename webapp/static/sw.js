/* Matevio service worker — makes the app installable and fast, while keeping
   updates instant. The API and WebSocket always go straight to the network;
   the HTML is network-first (so a new deploy's ?v= assets load immediately),
   and versioned static assets are cache-first. Bump CACHE to purge old caches. */
const CACHE = "matevio-v3";
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

  // HTML navigations: network-first, but only wait ~3.5s. If the server is cold
  // (Render free tier sleeps after ~15min and takes ~15s+ to wake), show the
  // cached app INSTANTLY instead of a blank loading screen; the fresh page is
  // still fetched and cached for next time. Falls back to cache when offline too.
  if (req.mode === "navigate") {
    e.respondWith((async () => {
      const cached = await caches.match("/");
      try {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 3500);
        const r = await fetch(req, { signal: controller.signal });
        clearTimeout(timer);
        const copy = r.clone(); caches.open(CACHE).then((c) => c.put("/", copy));
        return r;
      } catch (err) {
        // timed out (cold start) or offline → serve cached shell if we have it
        return cached || fetch(req);
      }
    })());
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
