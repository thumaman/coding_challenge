{% load static %}// Service worker (owner: Joseph).
// - Our own pages and /static/ files: network-first, so code changes show up immediately;
//   the cache is only a fallback when offline.
// - CDN libraries (incl. Tailwind) and fonts (versioned URLs that never change): cache-first.
// Bump CACHE when changing this file, so old caches are deleted on activate.
const CACHE = "talentrate-v5";
const SHELL = [
    "{% static 'core/js/app.js' %}",
    "{% static 'core/icons/icon.svg' %}",
    "{% static 'core/icons/icon-192.png' %}",
];

self.addEventListener("install", (event) => {
    event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)));
    self.skipWaiting();
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    );
    self.clients.claim();
});

function networkFirst(request, init) {
    return fetch(request, init)
        .then((response) => {
            if (response.ok) {
                const copy = response.clone();
                caches.open(CACHE).then((cache) => cache.put(request, copy));
            }
            return response;
        })
        .catch(() => caches.match(request));
}

function cacheFirst(request) {
    return caches.match(request).then((hit) => hit || fetch(request).then((response) => {
        const copy = response.clone();
        caches.open(CACHE).then((cache) => cache.put(request, copy));
        return response;
    }));
}

self.addEventListener("fetch", (event) => {
    const request = event.request;
    if (request.method !== "GET") return;
    const url = new URL(request.url);

    if (url.origin !== self.location.origin) {
        event.respondWith(cacheFirst(request)); // CDN / fonts
    } else if (url.pathname.startsWith("/static/")) {
        // no-cache: always revalidate, so the browser's HTTP cache never serves a stale script after a change
        event.respondWith(networkFirst(request, {cache: "no-cache"}));
    } else if (request.mode === "navigate") {
        event.respondWith(networkFirst(request));
    }
    // Everything else (JSON APIs, modal partials) goes straight to the network.
});
