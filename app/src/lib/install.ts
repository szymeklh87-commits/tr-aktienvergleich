/* Installationshilfe: fängt das „beforeinstallprompt“-Ereignis (Chrome/Samsung Internet) früh ab,
 * damit die Ansicht „Installieren“ später einen eigenen Knopf anbieten kann. */

import { useSyncExternalStore } from 'react';

interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

let deferred: BeforeInstallPromptEvent | null = null;
let installed = false;
const listeners = new Set<() => void>();

function notify(): void {
  for (const listener of listeners) listener();
}

export function initInstallCapture(): void {
  window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault();
    deferred = event as BeforeInstallPromptEvent;
    notify();
  });
  window.addEventListener('appinstalled', () => {
    deferred = null;
    installed = true;
    notify();
  });
}

export function isStandalone(): boolean {
  try {
    return window.matchMedia('(display-mode: standalone)').matches || (navigator as unknown as { standalone?: boolean }).standalone === true;
  } catch {
    return false;
  }
}

export async function promptInstall(): Promise<'angenommen' | 'abgelehnt' | 'nicht_verfuegbar'> {
  if (!deferred) return 'nicht_verfuegbar';
  const event = deferred;
  deferred = null;
  notify();
  await event.prompt();
  const choice = await event.userChoice;
  return choice.outcome === 'accepted' ? 'angenommen' : 'abgelehnt';
}

export function useInstallState(): { canPrompt: boolean; installed: boolean; standalone: boolean } {
  const canPrompt = useSyncExternalStore(
    (onChange) => {
      listeners.add(onChange);
      return () => listeners.delete(onChange);
    },
    () => deferred !== null,
  );
  return { canPrompt, installed, standalone: isStandalone() };
}
