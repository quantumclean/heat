/**
 * HEAT — Service Worker
 * Provides offline caching, background sync, and push notification support
 */

const CACHE_NAME = 'heat-v4.3';

// Use the service worker's scope to build paths dynamically.
// This ensures the SW works whether served at domain root (/) or a
// GitHub Pages subpath (/heat/). self.registration.scope gives us
// the correct base URL including any path prefix.
function scopedPath(relative) {
  const base = self.registration ? self.registration.scope : './';
  return new URL(relative, base).href;
}

const STATIC_ASSETS = [
  './',
  './index.html',
  './styles.css',
  './mobile.css',
  './app.js',
  './manifest.json',
  './logo.svg'
];

const DATA_ASSETS = [
  './data/clusters.json',
  './data/timeline.json',
  './data/keywords.json',
  './data/alerts.json',
  './data/latest_news.json'
];

// Install: cache static assets (individual adds so one 404 doesn't break install)
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return Promise.all(
        STATIC_ASSETS.map((url) =>
          cache.add(url).catch((err) => console.warn('SW: failed to cache', url, err))
        )
      );
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
  const scope = self.registration ? self.registration.scope : self.location.origin + '/';
  const scopePath = new URL(scope).pathname;
  if (url.pathname.startsWith(scopePath + 'data/') || url.pathname.startsWith('/data/')) {
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
        return caches.match(scopedPath('index.html'));
      }
    })
  );
});

// Push notifications
self.addEventListener('push', (event) => {
  const data = event.data ? event.data.json() : {};
  const title = data.title || 'HEAT Update';
  const options = {
    body: data.body || 'New ICE-related reports in your area',
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

// ===== MASTODON / FEDIVERSE (User Posts, No Auth, Free) =====
    "mastodon_immigration": {
        "url": "https://mastodon.social/tags/immigration.rss",
        "source": "Mastodon #immigration",
        "category": "community",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },
    "mastodon_ice": {
        "url": "https://mastodon.social/tags/ICE.rss",
        "source": "Mastodon #ICE",
        "category": "community",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },
    "mastodon_sanctuary": {
        "url": "https://mastodon.social/tags/SanctuaryCity.rss",
        "source": "Mastodon #SanctuaryCity",
        "category": "community",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },
    "mastodon_deportation": {
        "url": "https://mastodon.social/tags/deportation.rss",
        "source": "Mastodon #deportation",
        "category": "community",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },
    "mastodon_newjersey": {
        "url": "https://mastodon.social/tags/NewJersey.rss",
        "source": "Mastodon #NewJersey",
        "category": "community",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },

    # ===== DOCUMENTED NY (Immigrant Community Journalism, NYC/NJ) =====
    "documented_ny": {
        "url": "https://documentedny.com/feed/",
        "source": "Documented NY",
        "category": "advocacy",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },

    # ===== NJ MONITOR (Nonprofit Civic Journalism) =====
    "nj_monitor": {
        "url": "https://newjerseymonitor.com/feed/",
        "source": "NJ Monitor",
        "category": "news",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },

    # ===== USER BLOGS VIA GOOGLE NEWS (Medium, Change.org) =====
    "google_news_medium_nj_immigration": {
        "url": "https://news.google.com/rss/search?q=site:medium.com+New+Jersey+immigration&hl=en-US&gl=US&ceid=US:en",
        "source": "Google News (Medium)",
        "category": "community",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },
    "google_news_medium_ice": {
        "url": "https://news.google.com/rss/search?q=site:medium.com+ICE+deportation+sanctuary&hl=en-US&gl=US&ceid=US:en",
        "source": "Google News (Medium)",
        "category": "community",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },
    "google_news_changeorg_nj": {
        "url": "https://news.google.com/rss/search?q=site:change.org+New+Jersey+immigration&hl=en-US&gl=US&ceid=US:en",
        "source": "Google News (Change.org)",
        "category": "community",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },
    "google_news_substack_nj_immigration": {
        "url": "https://news.google.com/rss/search?q=site:substack.com+New+Jersey+immigration&hl=en-US&gl=US&ceid=US:en",
        "source": "Google News (Substack)",
        "category": "community",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },

    # ===== DAILY TARGUM — Rutgers Student Paper (New Brunswick) =====
    "daily_targum": {
        "url": "https://dailytargum.com/feed/",
        "source": "Daily Targum (Rutgers)",
        "category": "community",
        "cities": ["new_brunswick"],
    },

    # ===== WNYC NJ NEWS (NPR Community Reporting) =====
    "wnyc_nj": {
        "url": "https://feeds.wnyc.org/nj-news",
        "source": "WNYC NJ",
        "category": "news",
        "cities": ["plainfield", "hoboken", "trenton", "new_brunswick"],
    },
