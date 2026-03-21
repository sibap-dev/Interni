// PM Internship Portal Service Worker
// Version: 1.0.0

const CACHE_NAME = 'pm-internship-v1.0.0';
const OFFLINE_URL = '/offline.html';

// Assets to cache for offline functionality
const CACHE_ASSETS = [
  '/',
  '/login',
  '/home',
  '/profile',
  '/static/css/home.css',
  '/static/css/login.css', 
  '/static/css/profile.css',
  '/static/css/ats.css',
  '/static/js/home.js',
  '/static/js/login.js',
  '/static/js/profile.js',
  '/static/js/ats.js',
  '/static/images/mca_logo_1.svg',
  '/static/images/pm_internship_logo_eng.svg',
  '/static/images/indian_flag.svg',
  '/static/manifest.json',
  OFFLINE_URL
];

// Install event - cache assets
self.addEventListener('install', (event) => {
  console.log('🔧 Service Worker: Installing...');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('📦 Service Worker: Caching assets');
        return cache.addAll(CACHE_ASSETS);
      })
      .then(() => {
        console.log('✅ Service Worker: Installation complete');
        return self.skipWaiting();
      })
      .catch((error) => {
        console.error('❌ Service Worker: Installation failed', error);
      })
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  console.log('🚀 Service Worker: Activating...');
  event.waitUntil(
    caches.keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames.map((cache) => {
            if (cache !== CACHE_NAME) {
              console.log('🗑️ Service Worker: Deleting old cache', cache);
              return caches.delete(cache);
            }
          })
        );
      })
      .then(() => {
        console.log('✅ Service Worker: Activation complete');
        return self.clients.claim();
      })
  );
});

// Fetch event - serve cached content when offline
self.addEventListener('fetch', (event) => {
  // Skip non-GET requests
  if (event.request.method !== 'GET') {
    return;
  }

  // Skip external URLs
  if (!event.request.url.startsWith(self.location.origin)) {
    return;
  }

  event.respondWith(
    caches.match(event.request)
      .then((cachedResponse) => {
        // Return cached version if available
        if (cachedResponse) {
          return cachedResponse;
        }

        // Try to fetch from network
        return fetch(event.request)
          .then((response) => {
            // Don't cache non-successful responses
            if (!response || response.status !== 200 || response.type !== 'basic') {
              return response;
            }

            // Clone the response for caching
            const responseToCache = response.clone();

            // Cache the new response
            caches.open(CACHE_NAME)
              .then((cache) => {
                cache.put(event.request, responseToCache);
              });

            return response;
          })
          .catch(() => {
            // If both cache and network fail, show offline page
            if (event.request.destination === 'document') {
              return caches.match(OFFLINE_URL);
            }
            
            // For other resources, return a basic offline response
            return new Response('Offline', {
              status: 408,
              statusText: 'Request Timeout'
            });
          });
      })
  );
});

// Background sync for form submissions when back online
self.addEventListener('sync', (event) => {
  if (event.tag === 'background-sync') {
    console.log('🔄 Service Worker: Background sync triggered');
    event.waitUntil(
      // Handle any pending form submissions or data sync
      syncData()
    );
  }
});

// Push notification handler
self.addEventListener('push', (event) => {
  console.log('📱 Service Worker: Push notification received');
  
  const options = {
    body: event.data ? event.data.text() : 'New update available!',
    icon: '/static/images/icons/icon-192x192.png',
    badge: '/static/images/icons/icon-72x72.png',
    vibrate: [100, 50, 100],
    data: {
      dateOfArrival: Date.now(),
      primaryKey: '2'
    },
    actions: [
      {
        action: 'explore',
        title: 'View Details',
        icon: '/static/images/icons/icon-96x96.png'
      },
      {
        action: 'close',
        title: 'Close',
        icon: '/static/images/icons/icon-96x96.png'
      }
    ]
  };

  event.waitUntil(
    self.registration.showNotification('PM Internship Portal', options)
  );
});

// Notification click handler
self.addEventListener('notificationclick', (event) => {
  console.log('🔔 Service Worker: Notification clicked');
  event.notification.close();

  if (event.action === 'explore') {
    // Open the app
    event.waitUntil(
      clients.openWindow('/')
    );
  }
});

// Helper function for background sync
async function syncData() {
  try {
    // Implement any background data synchronization logic here
    console.log('📊 Service Worker: Syncing data...');
    return Promise.resolve();
  } catch (error) {
    console.error('❌ Service Worker: Sync failed', error);
    return Promise.reject(error);
  }
}

// Share target handler (for receiving shared content)
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SHARE_TARGET') {
    console.log('📤 Service Worker: Share target activated');
    // Handle shared content
    event.ports[0].postMessage({
      status: 'received',
      data: event.data
    });
  }
});

console.log('🎯 Service Worker: Loaded and ready');