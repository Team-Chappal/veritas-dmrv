/**
 * VERITAS dMRV service worker.
 *
 * SCOPE, DELIBERATELY NARROW.
 *
 * This worker caches the APP SHELL and the public Cloudinary demo assets. It
 * does NOT cache, replay or authorise API responses. Three reasons:
 *
 *   1. A cached `/api/v1/assets` response would let a reviewer see yesterday's
 *      collection while believing it is today's, which is the exact confusion
 *      every panel's source badge exists to prevent.
 *   2. Provenance, triage and campaign data are not static. Serving a stale
 *      copy with a 200 is worse than an error.
 *   3. The demo-cache mode is an EXPLICIT user choice, made in the UI, not a
 *      silent network side effect.
 *
 * Capture queue durability lives in IndexedDB (lib/offline.ts) rather than here,
 * so it can be tested directly. Background Sync is used to nudge a flush, and its
 * absence is reported rather than papered over.
 */

const SHELL_CACHE = "veritas-shell-v1";
const MEDIA_CACHE = "veritas-media-v1";

/** Same-origin app shell. Precise, so an API path is never matched. */
const SHELL_ASSETS = ["/", "/manifest.webmanifest"];

/** Media origins allowed to be cached. Explicit allow-list, not a regex. */
const CACHEABLE_MEDIA = [
  "res.cloudinary.com",
  "images.unsplash.com",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      .then((c) => c.addAll(SHELL_ASSETS))
      .catch(() => undefined)
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((k) => k !== SHELL_CACHE && k !== MEDIA_CACHE)
            .map((k) => caches.delete(k))
        )
      )
      .then(() => self.clients.claim())
  );
});

/**
 * @param {Request} request
 * @returns {string|null} a cache name if this request may be cached
 */
function cacheNameFor(request) {
  const url = new URL(request.url);
  if (url.origin === self.location.origin) {
    // Never cache an API response. See the header note.
    if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/v1/")) {
      return null;
    }
    return SHELL_CACHE;
  }
  return CACHEABLE_MEDIA.includes(url.hostname) ? MEDIA_CACHE : null;
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const cacheName = cacheNameFor(request);
  if (!cacheName) return;

  event.respondWith(
    caches.open(cacheName).then(async (cache) => {
      const hit = await cache.match(request);
      if (hit) return hit;
      try {
        const response = await fetch(request);
        // Opaque and error responses are not worth storing; a cached 404 becomes
        // a ghost asset that never appears again in that session.
        if (response.ok || response.type === "opaque") {
          cache.put(request, response.clone()).catch(() => undefined);
        }
        return response;
      } catch (err) {
        const fallback = await cache.match("/");
        if (fallback && new URL(request.url).origin === self.location.origin) {
          return fallback;
        }
        throw err;
      }
    })
  );
});

/** Background Sync: nudge the page to drain the IndexedDB capture queue. */
self.addEventListener("sync", (event) => {
  if (event.tag !== "veritas-capture-sync") return;
  event.waitUntil(
    self.clients
      .matchAll({ includeUncontrolled: true })
      .then((clients) => {
        for (const client of clients) {
          client.postMessage({ type: "flush-capture-queue" });
        }
      })
      .catch(() => undefined)
  );
});
