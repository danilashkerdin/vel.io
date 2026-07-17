const CACHE_NAME = 'velio-pwa-v1';
const ASSETS_TO_CACHE = [
  '/',
  '/index.html',
  '/css/base.css',
  '/css/main.css',
  '/css/auth.css',
  '/css/public.css',
  '/js/app.js',
  '/js/api.js',
  '/js/auth.js',
  '/js/config.js',
  '/js/map.js',
  '/js/activity.js',
  '/js/leaderboard.js',
  '/js/notifications.js',
  '/js/editor.js',
  '/js/upload.js',
  '/js/recorder.js',
  '/js/ui.js',
  '/js/profile.js',
  '/js/admin.js',
  '/js/advertiser.js',
  '/js/share.js',
  '/js/telegram.js',
  '/js/territories.js',
  '/manifest.json',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
  '/icons/icon-192.svg',
  '/icons/icon-512.svg'
];

const VERSION = '2';
const NEW_CACHE = `velio-pwa-${VERSION}`;

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(NEW_CACHE).then((cache) => {
      console.log('[SW] Caching app assets');
      return cache.addAll(ASSETS_TO_CACHE);
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((k) => k !== NEW_CACHE && k.startsWith('velio-pwa-'))
            .map((k) => caches.delete(k))
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  if (event.request.method !== 'GET') return;

  if (url.pathname.startsWith('/api/')) {
    event.respondWith(handleNetworkFirst(event.request));
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) {
        fetch(event.request).catch(() => {});
        return cached;
      }
      return fetch(event.request).then((response) => {
        if (response && response.status === 200 && response.type === 'basic') {
          const clone = response.clone();
          caches.open(NEW_CACHE).then((cache) => {
            cache.put(event.request, clone);
          });
        }
        return response;
      }).catch(() => {
        if (event.request.headers.get('accept')?.includes('text/html')) {
          return caches.match('/index.html');
        }
        return new Response('Offline', { status: 503, statusText: 'Service Unavailable' });
      });
    })
  );
});

async function handleNetworkFirst(request) {
  try {
    const networkResponse = await fetch(request);
    if (networkResponse && networkResponse.status === 200) {
      const clone = networkResponse.clone();
      caches.open(NEW_CACHE).then((cache) => {
        cache.put(request, clone);
      });
    }
    return networkResponse;
  } catch {
    return caches.match(request).then((cached) => {
      return cached || new Response(JSON.stringify({ error: 'offline' }), {
        status: 503,
        headers: { 'Content-Type': 'application/json' }
      });
    });
  }
}

self.addEventListener('push', (event) => {
  if (!event.data) return;

  let title = 'Velo.io';
  let options = {
    body: 'Новое событие!',
    icon: '/icons/icon-192.png',
    badge: '/icons/icon-192.png',
    data: { url: '/' }
  };

  try {
    const data = event.data.json();
    title = data.title || title;
    options.body = data.body || options.body;
    if (data.url) options.data.url = data.url;
  } catch {
    options.body = event.data.text();
  }

  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true })
      .then((clients) => {
        for (const client of clients) {
          if (client.url && 'focus' in client) return client.focus();
        }
        return self.clients.openWindow(event.notification.data?.url || '/');
      })
  );
});
