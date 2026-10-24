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
// Ab 1.18.1 auch die Signale (Kandidaten der Startseite, Signal-Einzelansicht): eigener Speicher je Signal-Stand.
// Bis 1.18.0 speicherte der Service Worker sie gar nicht – ohne Netz fehlten sie, und statt der Datei kam die Startseite.
const SIGNAL_PREFIX = 'tr-signale-';
const MAX_SIGNAL_CACHES = 2;

interface Store {
  prefix: string;
  /** Eintrag im Speicher „tr-meta“ mit der Reihenfolge der zuletzt benutzten Stände */
  order: string;
  max: number;
}

const SNAPSHOTS: Store = { prefix: DATA_PREFIX, order: '/__snapshot-reihenfolge__', max: MAX_SNAPSHOT_CACHES };
const SIGNALS: Store = { prefix: SIGNAL_PREFIX, order: '/__signal-reihenfolge__', max: MAX_SIGNAL_CACHES };

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

/** Nachrichten der Seite: „SKIP_WAITING“ (neue Version übernehmen) und ab 1.18.1 „MERKEN“ – beim ersten Besuch übernimmt
 * der Service Worker die Seite erst, nachdem sie schon Daten geladen hat (Status, Index, Schlüsselparameter, Kerndateien,
 * Signale). Diese Dateien nennt ihm die Seite danach; er legt sie in denselben Speicher wie jeden anderen Abruf. Bis
 * 1.18.0 fehlten sie ohne Netz, und die App meldete beim nächsten Öffnen „Keine Internetverbindung“ (gefunden am
 * 24.10.2026 im Android-Emulator mit echten Daten). */
self.addEventListener('message', (event) => {
  if (event.data === 'SKIP_WAITING') {
    void self.skipWaiting();
    return;
  }
  const message = event.data as { type?: unknown; urls?: unknown } | null;
  if (message && message.type === 'MERKEN' && Array.isArray(message.urls)) {
    const urls = message.urls.filter((url): url is string => typeof url === 'string').slice(0, 400);
    event.waitUntil(remember(urls));
  }
});

function scopePath(url: URL): string {
  const scope = new URL(self.registration.scope);
  return url.pathname.startsWith(scope.pathname) ? url.pathname.slice(scope.pathname.length) : url.pathname;
}

type Target =
  | { kind: 'meta' }
  | { kind: 'datei'; store: Store; id: string }
  | { kind: 'manifest' }
  | { kind: 'daten' }
  | { kind: 'huelle' };

/** Wohin ein Abruf gehört – dieselbe Zuordnung für Abrufe der Seite und für „MERKEN“. */
function targetOf(url: URL): Target | null {
  if (url.origin !== self.location.origin) return null;
  const path = scopePath(url);
  if (path === 'data/status.json' || path === 'data/crypto.json' || path === 'data/snapshots/index.json') return { kind: 'meta' };
  const snapshot = /^data\/snapshots\/([^/]+)\//.exec(path);
  if (snapshot) return { kind: 'datei', store: SNAPSHOTS, id: snapshot[1] };
  const signals = /^data\/signale\/([^/]+)\//.exec(path);
  if (signals) return { kind: 'datei', store: SIGNALS, id: signals[1] };
  if (path === 'manifest.webmanifest') return { kind: 'manifest' };
  if (path.startsWith('data/')) return { kind: 'daten' };
  return { kind: 'huelle' };
}

/** Antwort „nicht gespeichert und keine Verbindung“ – die App zeigt dann ihren Offline-Hinweis. */
function missing(): Response {
  return new Response('offline', { status: 503, headers: { 'x-tr-cache': 'fehlt' } });
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
    return missing();
  }
}

async function touch(store: Store, id: string): Promise<void> {
  const meta = await caches.open(META);
  const key = new Request(store.order);
  const stored = await meta.match(key);
  const order: string[] = stored ? await stored.json() : [];
  const next = [id, ...order.filter((x) => x !== id)];
  for (const old of next.slice(store.max)) await caches.delete(store.prefix + old);
  await meta.put(key, new Response(JSON.stringify(next.slice(0, store.max)), { headers: { 'content-type': 'application/json' } }));
}

async function trim(cache: Cache): Promise<void> {
  const keys = await cache.keys();
  if (keys.length <= MAX_ENTRIES_PER_SNAPSHOT) return;
  for (const request of keys.slice(0, keys.length - MAX_ENTRIES_PER_SNAPSHOT)) await cache.delete(request);
}

/** Datei eines Datenstands oder Signal-Stands: unveränderlich, also zuerst aus dem Speicher. */
async function storedFile(request: Request, store: Store, id: string): Promise<Response> {
  const cache = await caches.open(store.prefix + id);
  const cached = await cache.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok) {
      await cache.put(request, response.clone());
      void touch(store, id).then(() => trim(cache));
    }
    return response;
  } catch {
    return missing();
  }
}

/** Übrige Dateien unter data/: nur vom Server; ohne Verbindung ehrlich „fehlt“ – nie die Startseite statt Daten. */
async function dataOnly(request: Request): Promise<Response> {
  try {
    return await fetch(request);
  } catch {
    return missing();
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

/** App-Hülle aus dem Speicher; ohne Verbindung bekommt nur ein Seitenaufruf die gespeicherte Startseite (ab 1.18.1 –
 * bis dahin auch jede andere fehlende Datei). */
async function shell(request: Request, navigation: boolean): Promise<Response> {
  const cache = await caches.open(SHELL);
  const cached = await cache.match(request, { ignoreSearch: true });
  if (cached) return cached;
  try {
    return await fetch(request);
  } catch {
    const index = navigation ? await cache.match('./index.html') : undefined;
    return index ?? new Response('offline', { status: 503 });
  }
}

/** „MERKEN“: Dateien, die die Seite vor der Übernahme geladen hat, in den Speicher legen (was schon da ist, bleibt). */
async function remember(urls: string[]): Promise<void> {
  for (const text of new Set(urls)) {
    let url: URL;
    try {
      url = new URL(text);
    } catch {
      continue;
    }
    const target = targetOf(url);
    if (target === null) continue;
    try {
      if (target.kind === 'meta') await networkFirstMeta(new Request(url.toString()));
      else if (target.kind === 'datei') await storedFile(new Request(url.toString()), target.store, target.id);
    } catch {
      // ohne Verbindung bleibt die Datei ungespeichert – die Seite lädt sie beim nächsten Mal über den Service Worker
    }
  }
}

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const target = targetOf(new URL(request.url));
  if (target === null) return;
  if (target.kind === 'meta') event.respondWith(networkFirstMeta(request));
  else if (target.kind === 'datei') event.respondWith(storedFile(request, target.store, target.id));
  else if (target.kind === 'manifest') event.respondWith(manifestFirst(request));
  else if (target.kind === 'daten') event.respondWith(dataOnly(request));
  else if (request.mode === 'navigate') event.respondWith(shell(new Request('./index.html'), true));
  else event.respondWith(shell(request, false));
});
