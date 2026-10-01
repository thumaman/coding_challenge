{% load static %}// Service worker (owner: Joseph). Network-first for pages, cache-first for static/CDN assets.
const CACHE = "talentrate-v1";
const SHELL = [
    "{% static 'core/css/app.css' %}",
    "{% static 'core/js/app.js' %}",
    "{% static 'core/icons/icon.svg' %}",
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

self.addEventListener("fetch", (event) => {
    const request = event.request;
    if (request.method !== "GET") return;
    const url = new URL(request.url);
    const isAsset = url.pathname.startsWith("/static/") || url.host.includes("cdn") || url.host.includes("fonts");

    if (isAsset) {
        event.respondWith(
            caches.match(request).then((hit) => hit || fetch(request).then((res) => {
                const copy = res.clone();
                caches.open(CACHE).then((cache) => cache.put(request, copy));
                return res;
            }))
        );
    } else if (request.mode === "navigate") {
        event.respondWith(fetch(request).catch(() => caches.match(request)));
    }
});
