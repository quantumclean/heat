/**
 * HEAT — Service Worker
 * Provides offline caching, background sync, and push notification support
 */

const CACHE_NAME = 'heat-v4.2';
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/styles.css',
  '/mobile.css',
  '/app.js',
  '/manifest.json',
  '/logo.svg'
];

const DATA_ASSETS = [
  '/data/clusters.json',
  '/data/timeline.json',
  '/data/keywords.json',
  '/data/alerts.json',
  '/data/latest_news.json'
];

// Install: cache static assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

// Activate: clean old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      );
    })
  );
  self.clients.claim();
});

// Fetch: network-first for data, cache-first for static
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Data files: network-first, fallback to cache
  if (url.pathname.startsWith('/data/')) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          return response;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  // Static assets: cache-first, fallback to network
  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request).then((response) => {
        if (response.ok && url.origin === self.location.origin) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return response;
      });
    }).catch(() => {
      // Offline fallback for navigation
      if (event.request.mode === 'navigate') {
        return caches.match('/index.html');
      }
    })
  );
});

// Push notifications
self.addEventListener('push', (event) => {
  const data = event.data ? event.data.json() : {};
  const title = data.title || 'HEAT Alert';
  const options = {
    body: data.body || 'New ICE activity reported in your area',
    icon: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96"><text y="72" font-size="72">🔥</text></svg>',
    badge: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96"><text y="72" font-size="72">⚠️</text></svg>',
    tag: data.tag || 'heat-alert',
    data: { url: data.url || '/' },
    actions: [
      { action: 'view', title: 'View Map' },
      { action: 'dismiss', title: 'Dismiss' }
    ]
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

// Notification click
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  if (event.action === 'dismiss') return;
  event.waitUntil(
    clients.openWindow(event.notification.data.url || '/')
  );
});
