self.addEventListener('install', (e) => {
  // Force the waiting service worker to become the active service worker.
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keyList) => {
      // Delete all existing caches
      return Promise.all(keyList.map((key) => caches.delete(key)));
    }).then(() => {
      // Unregister itself
      self.registration.unregister();
    })
  );
});

self.addEventListener('fetch', (e) => {
  // Immediately pass through all network requests without interception
  e.respondWith(fetch(e.request));
});
