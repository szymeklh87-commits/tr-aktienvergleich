import { StrictMode, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import { PREVIEW } from './lib/env';
import { initInstallCapture } from './lib/install';
import { AppStateProvider } from './state/AppState';
import './styles.css';

function Root() {
  const [waiting, setWaiting] = useState<ServiceWorker | null>(null);

  useEffect(() => {
    if (PREVIEW || !('serviceWorker' in navigator) || location.protocol === 'file:') return;
    let refreshing = false;
    // Ab 1.15: nur nach einer Aktualisierung neu laden (alte Fassung → neue). Beim ersten Besuch übernimmt der Service
    // Worker die Seite ohne Neuladen – vorher lud die App dabei einmal neu, eine schon getippte Passphrase ging verloren.
    const hadController = Boolean(navigator.serviceWorker.controller);
    navigator.serviceWorker.addEventListener('controllerchange', () => {
      if (refreshing || !hadController) return;
      refreshing = true;
      window.location.reload();
    });
    navigator.serviceWorker
      .register('./sw.js', { scope: './' })
      .then((registration) => {
        if (registration.waiting && navigator.serviceWorker.controller) setWaiting(registration.waiting);
        registration.addEventListener('updatefound', () => {
          const worker = registration.installing;
          worker?.addEventListener('statechange', () => {
            if (worker.state === 'installed' && navigator.serviceWorker.controller) setWaiting(worker);
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
      <App swUpdate={waiting !== null} onUpdate={() => waiting?.postMessage('SKIP_WAITING')} />
    </AppStateProvider>
  );
}

initInstallCapture();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Root />
  </StrictMode>,
);
