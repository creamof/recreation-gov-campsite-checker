/*
 * Service worker for the Trailhead PWA.
 *
 * Milestone 1 scope: make the app installable and give it an offline app shell.
 * This is deliberately the foundation for Milestone 2 (last-minute availability
 * alerts): the `push` and `notificationclick` handlers below are already wired
 * so that adding a backend Web Push subscription is the only remaining step.
 */

const CACHE = "trailhead-shell-v1";
const SHELL = ["/", "/index.html", "/icon.svg", "/manifest.webmanifest"];

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
  // Never cache API calls — always hit the network for live data.
  if (request.method !== "GET" || new URL(request.url).pathname.startsWith("/api")) {
    return;
  }
  event.respondWith(
    caches.match(request).then((cached) => cached || fetch(request).catch(() => caches.match("/")))
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
