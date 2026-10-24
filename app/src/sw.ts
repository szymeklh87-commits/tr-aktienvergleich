/// <reference lib="webworker" />
/* Service Worker: speichert die App-Hülle und bereits geladene Ergebnisse.
 * Er ist keine Rechenmaschine und ersetzt nicht den täglichen Serverlauf. */

export {};

declare const self: ServiceWorkerGlobalScope;
declare const __APP_VERSION__: string;
declare const __PRECACHE__: string[];

const VERSION = __APP_VERSION__;
const SHELL = `tr-huelle-${VERSION}`;
const META = 'tr-meta';
const DATA_PREFIX = 'tr-daten-';
const MAX_SNAPSHOT_CACHES = 3;
const MAX_ENTRIES_PER_SNAPSHOT = 1500;

self.addEventListener('install', (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(SHELL);
      await cache.addAll(__PRECACHE__.map((path) => new Request(path, { cache: 'reload' })));
    })(),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const names = await caches.keys();
      await Promise.all(names.filter((n) => n.startsWith('tr-huelle-') && n !== SHELL).map((n) => caches.delete(n)));
      await self.clients.claim();
    })(),
  );
});

self.addEventListener('message', (event) => {
  if (event.data === 'SKIP_WAITING') void self.skipWaiting();
});

function scopePath(url: URL): string {
  const scope = new URL(self.registration.scope);
  return url.pathname.startsWith(scope.pathname) ? url.pathname.slice(scope.pathname.length) : url.pathname;
}

async function markOffline(response: Response): Promise<Response> {
  const headers = new Headers(response.headers);
  headers.set('x-tr-cache', 'offline');
  return new Response(await response.arrayBuffer(), { status: response.status, statusText: response.statusText, headers });
}

async function networkFirstMeta(request: Request): Promise<Response> {
  const cache = await caches.open(META);
  try {
    const response = await fetch(request);
    // Ein Eintrag je Datei: Abfragen mit Zeitstempel (?t=…) umgehen nur den Zwischenspeicher des Servers
    if (response.ok) await cache.put(request.url.split('?')[0], response.clone());
    return response;
  } catch {
    const cached = await cache.match(request, { ignoreSearch: true });
    if (cached) return markOffline(cached);
    return new Response('offline', { status: 503, headers: { 'x-tr-cache': 'fehlt' } });
  }
}

async function touchSnapshot(id: string): Promise<void> {
  const meta = await caches.open(META);
  const key = new Request('/__snapshot-reihenfolge__');
  const stored = await meta.match(key);
  const order: string[] = stored ? await stored.json() : [];
  const next = [id, ...order.filter((x) => x !== id)];
  await meta.put(key, new Response(JSON.stringify(next), { headers: { 'content-type': 'application/json' } }));
  for (const old of next.slice(MAX_SNAPSHOT_CACHES)) await caches.delete(DATA_PREFIX + old);
  if (next.length > MAX_SNAPSHOT_CACHES) {
    await meta.put(key, new Response(JSON.stringify(next.slice(0, MAX_SNAPSHOT_CACHES)), { headers: { 'content-type': 'application/json' } }));
  }
}

async function trim(cache: Cache): Promise<void> {
  const keys = await cache.keys();
  if (keys.length <= MAX_ENTRIES_PER_SNAPSHOT) return;
  for (const request of keys.slice(0, keys.length - MAX_ENTRIES_PER_SNAPSHOT)) await cache.delete(request);
}

async function snapshotFile(request: Request, snapshotId: string): Promise<Response> {
  const cache = await caches.open(DATA_PREFIX + snapshotId);
  const cached = await cache.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok) {
      await cache.put(request, response.clone());
      void touchSnapshot(snapshotId).then(() => trim(cache));
    }
    return response;
  } catch {
    return new Response('offline', { status: 503, headers: { 'x-tr-cache': 'fehlt' } });
  }
}

/** Web-App-Manifest (ab 1.17) immer zuerst vom Server: Chrome prüft bei installierten Apps darüber, ob sich Name,
 * Symbole oder Farben geändert haben. Ohne Verbindung gilt die gespeicherte Fassung. */
async function manifestFirst(request: Request): Promise<Response> {
  const cache = await caches.open(SHELL);
  try {
    const response = await fetch(request, { cache: 'no-cache' });
    if (response.ok) await cache.put(request.url.split('?')[0], response.clone());
    return response;
  } catch {
    const cached = await cache.match(request, { ignoreSearch: true });
    return cached ?? new Response('offline', { status: 503 });
  }
}

async function shell(request: Request): Promise<Response> {
  const cache = await caches.open(SHELL);
  const cached = await cache.match(request, { ignoreSearch: true });
  if (cached) return cached;
  try {
    return await fetch(request);
  } catch {
    const index = await cache.match('./index.html');
    return index ?? new Response('offline', { status: 503 });
  }
}

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  const path = scopePath(url);
  if (path === 'data/status.json' || path === 'data/crypto.json' || path === 'data/snapshots/index.json') {
    event.respondWith(networkFirstMeta(request));
    return;
  }
  const match = /^data\/snapshots\/([^/]+)\//.exec(path);
  if (match) {
    event.respondWith(snapshotFile(request, match[1]));
    return;
  }
  if (path === 'manifest.webmanifest') {
    event.respondWith(manifestFirst(request));
    return;
  }
  if (request.mode === 'navigate') {
    event.respondWith(shell(new Request('./index.html')));
    return;
  }
  event.respondWith(shell(request));
});
