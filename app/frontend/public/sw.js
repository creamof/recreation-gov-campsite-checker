/*
 * Service worker for the Trailhead PWA.
 *
 * Milestone 1 scope: make the app installable and give it an offline app shell.
 * This is deliberately the foundation for Milestone 2 (last-minute availability
 * alerts): the `push` and `notificationclick` handlers below are already wired
 * so that adding a backend Web Push subscription is the only remaining step.
 *
 * IMPORTANT — do not cache "/" or "/index.html" and do not serve HTML
 * cache-first. Vite fingerprints built JS/CSS with a content hash
 * (assets/index-XXXXXXXX.js). If a cached index.html ever wins over the
 * network, a client stays pinned to a previous deploy's hashed filenames
 * forever — and once those files are replaced by the next deploy, the
 * <script> tag 404s and the app never mounts (blank page, styles only).
 * HTML navigations are network-first below specifically to prevent that.
 */

const CACHE = "trailhead-shell-v2";
const SHELL = ["/icon.svg", "/manifest.webmanifest"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).catch(() => {}));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);
  // Never cache API calls — always hit the network for live data.
  if (request.method !== "GET" || url.pathname.startsWith("/api")) return;

  // HTML page loads: always prefer the network so a new deploy's index.html
  // (and the hashed asset filenames it references) is picked up immediately.
  // Fall back to the cache only when fully offline.
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(request, copy)).catch(() => {});
          return res;
        })
        .catch(() => caches.match(request).then((cached) => cached || caches.match("/icon.svg")))
    );
    return;
  }

  // Everything else (hashed JS/CSS, icons, manifest): cache-first, and
  // actually populate the cache as new hashed assets are fetched.
  event.respondWith(
    caches.match(request).then(
      (cached) =>
        cached ||
        fetch(request).then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(request, copy)).catch(() => {});
          }
          return res;
        })
    )
  );
});

// --- Web Push foundation (Milestone 2) -----------------------------------
self.addEventListener("push", (event) => {
  let data = { title: "Campsite available!", body: "A site opened up for your watch." };
  try {
    if (event.data) data = { ...data, ...event.data.json() };
  } catch (_) {
    /* keep defaults */
  }
  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: "/icon.svg",
      badge: "/icon.svg",
      data: { url: data.url || "/" },
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/";
  event.waitUntil(self.clients.openWindow(url));
});
