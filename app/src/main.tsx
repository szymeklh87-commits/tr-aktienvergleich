import { StrictMode, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import { PREVIEW } from './lib/env';
import { initInstallCapture } from './lib/install';
import { AppStateProvider } from './state/AppState';
import { UpdateStateProvider } from './state/UpdateState';
import './styles.css';

/** Datendateien, die diese Seite schon geladen hat (Adressen aus den Ladezeiten des Browsers, ohne Inhalte). */
function loadedDataFiles(): string[] {
  const urls = performance
    .getEntriesByType('resource')
    .map((entry) => entry.name)
    .filter((url) => url.startsWith(location.origin) && new URL(url).pathname.includes('/data/'));
  return [...new Set(urls)];
}

/** Ab 1.18.1: dem Service Worker, der die Seite gerade erst übernommen hat, die schon geladenen Daten zum Speichern nennen. */
function handOverLoadedData(): void {
  const worker = navigator.serviceWorker.controller;
  const urls = loadedDataFiles();
  if (worker && urls.length) worker.postMessage({ type: 'MERKEN', urls });
}

/** Ab 1.23: Wann darf eine neue App-Version ohne Rückfrage übernommen werden? Nie während einer Eingabe (z. B. Passphrase). */
function typing(): boolean {
  const el = document.activeElement;
  return el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement || el instanceof HTMLSelectElement || (el instanceof HTMLElement && el.isContentEditable);
}

const STARTED = performance.now();
/** Zeit nach dem Öffnen, in der eine neue Version sofort übernommen wird (noch keine Bedienung, nichts geht verloren). */
const START_WINDOW_MS = 15_000;
let interacted = false;
/** Diese Seite hat eine wartende neue Version selbst übernommen – dann nach dem Wechsel immer neu laden (auch beim ersten Besuch). */
let takingOver = false;
function takeOver(worker: ServiceWorker): void {
  takingOver = true;
  worker.postMessage('SKIP_WAITING');
}
for (const kind of ['pointerdown', 'keydown'] as const) {
  window.addEventListener(kind, () => (interacted = true), { capture: true, once: true, passive: true });
}

function Root() {
  const [waiting, setWaiting] = useState<ServiceWorker | null>(null);

  useEffect(() => {
    if (PREVIEW || !('serviceWorker' in navigator) || location.protocol === 'file:') return;
    let refreshing = false;
    // Ab 1.15: nur nach einer Aktualisierung neu laden (alte Fassung → neue). Beim ersten Besuch übernimmt der Service
    // Worker die Seite ohne Neuladen – vorher lud die App dabei einmal neu, eine schon getippte Passphrase ging verloren.
    // Ab 1.18.1 bekommt er dabei die schon geladenen Daten (Status, Index, Schlüsselparameter, Kerndateien, Signale)
    // genannt – sonst fehlten sie ohne Netz, bis die App einmal mit Verbindung neu geöffnet wurde. Zweimal: sofort und
    // nach einigen Sekunden für Abrufe, die vor der Übernahme begonnen und erst danach fertig wurden.
    const hadController = Boolean(navigator.serviceWorker.controller);
    navigator.serviceWorker.addEventListener('controllerchange', () => {
      if (!hadController && !takingOver) {
        handOverLoadedData();
        window.setTimeout(handOverLoadedData, 5000);
        return;
      }
      if (refreshing) return;
      refreshing = true;
      window.location.reload();
    });
    // Ab 1.23 (Auftrag vom 07.11.2026, 16:52 Uhr: neue Version ohne Cache-Löschen): Eine neue Version wird automatisch
    // übernommen und die Seite einmal neu geladen – sofort, wenn sie gleich nach dem Öffnen bereitsteht und noch nichts
    // bedient wurde, sonst beim nächsten Wechsel in den Hintergrund (nie während einer Eingabe). Der Hinweis mit dem Knopf
    // „Aktualisieren“ bleibt bis dahin sichtbar.
    const offer = (worker: ServiceWorker) => {
      setWaiting(worker);
      if (!interacted && performance.now() - STARTED < START_WINDOW_MS && !typing()) {
        takeOver(worker);
        return;
      }
      const onHide = () => {
        if (document.visibilityState !== 'hidden' || typing()) return;
        document.removeEventListener('visibilitychange', onHide);
        takeOver(worker);
      };
      document.addEventListener('visibilitychange', onHide);
    };
    navigator.serviceWorker
      .register('./sw.js', { scope: './' })
      .then((registration) => {
        if (registration.waiting && navigator.serviceWorker.controller) offer(registration.waiting);
        registration.addEventListener('updatefound', () => {
          const worker = registration.installing;
          worker?.addEventListener('statechange', () => {
            if (worker.state === 'installed' && navigator.serviceWorker.controller) offer(worker);
          });
        });
        document.addEventListener('visibilitychange', () => {
          if (document.visibilityState === 'visible') void registration.update().catch(() => undefined);
        });
      })
      .catch(() => undefined);
  }, []);

  return (
    <AppStateProvider>
      <UpdateStateProvider>
        <App swUpdate={waiting !== null} onUpdate={() => (waiting ? takeOver(waiting) : undefined)} />
      </UpdateStateProvider>
    </AppStateProvider>
  );
}

initInstallCapture();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Root />
  </StrictMode>,
);
