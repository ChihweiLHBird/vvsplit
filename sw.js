// vvsplit service worker — the only JavaScript in this project.
//
// Why it exists: browsers only accept .js for service workers; PyScript
// has no equivalent. Scope is intentionally cache plumbing only — no app
// logic, no DOM/state access. The app remains 100% Python.
//
// Strategy:
//   - install:  pre-cache the app shell + PyScript runtime so the app
//               boots offline once it has been visited online.
//   - fetch:    GET-only, same-origin → cache-first w/ network fallback;
//               cross-origin (PyScript CDN, Google Fonts) → network-first
//               with stale-cache fallback so a new pinned version is
//               picked up without bricking offline users.
//   - activate: drop old cache buckets so a CACHE_VERSION bump fully
//               replaces the previous shell.
//
// To force a refresh after editing static files: bump CACHE_VERSION.

const CACHE_VERSION = 'vvsplit-v6';

// App shell — everything required for a cold-from-cache boot. Keep this
// in sync with files referenced by index.html / pyscript.toml.
const APP_SHELL = [
  './',
  './index.html',
  './styles.css',
  './main.py',
  './ui.py',
  './storage.py',
  './pyscript.toml',
  './splitcore/__init__.py',
  './splitcore/model.py',
  './splitcore/calc.py',
  './manifest.webmanifest',
  './icons/favicon.png',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/icon-512-maskable.png',
  './icons/apple-touch-icon.png',
];

// Cross-origin runtime assets to opportunistically warm during install.
// Failures are tolerated — the fetch handler will still cache them on
// first successful network hit.
const RUNTIME_WARMUP = [
  'https://pyscript.net/releases/2024.11.1/core.css',
  'https://pyscript.net/releases/2024.11.1/core.js',
];

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_VERSION);
    // cache.addAll is atomic: one failing URL aborts the whole install
    // and leaves the app with zero offline support. Cache entries
    // individually instead so a single stale or renamed path can't kill
    // the rest of the shell. Failures are surfaced to the console so
    // dev-time mistakes (typo in APP_SHELL) don't hide silently.
    const results = await Promise.allSettled(
      APP_SHELL.map((url) => cache.add(url))
    );
    const failed = results
      .map((r, i) => (r.status === 'rejected' ? APP_SHELL[i] : null))
      .filter(Boolean);
    if (failed.length) {
      console.warn('vvsplit sw: failed to precache', failed);
    }
    // Default (cors) mode: core.js is loaded as a module script, which
    // rejects the opaque response a no-cors fetch would cache — that broke
    // offline cold boot. pyscript.net sends CORS, so this caches a usable
    // response. Failures stay tolerated (allSettled).
    await Promise.allSettled(
      RUNTIME_WARMUP.map((url) =>
        fetch(url).then((r) => { if (r.ok) return cache.put(url, r); })
      )
    );
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(
      keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k))
    );
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  const sameOrigin = url.origin === self.location.origin;

  if (sameOrigin) {
    // Cache-first for the app shell.
    event.respondWith((async () => {
      const cache = await caches.open(CACHE_VERSION);
      const hit = await cache.match(req);
      if (hit) return hit;
      try {
        const res = await fetch(req);
        if (res && res.ok) cache.put(req, res.clone());
        return res;
      } catch (err) {
        // Last-ditch: serve index.html for navigation requests so the
        // app at least loads its own offline shell instead of a browser
        // error page.
        if (req.mode === 'navigate') {
          const fallback = await cache.match('./index.html');
          if (fallback) return fallback;
        }
        throw err;
      }
    })());
    return;
  }

  // Cross-origin (CDN, fonts) — network-first, fall back to cache.
  event.respondWith((async () => {
    const cache = await caches.open(CACHE_VERSION);
    try {
      const res = await fetch(req);
      if (res && (res.ok || res.type === 'opaque')) {
        cache.put(req, res.clone());
      }
      return res;
    } catch (err) {
      const hit = await cache.match(req);
      if (hit) return hit;
      throw err;
    }
  })());
});
