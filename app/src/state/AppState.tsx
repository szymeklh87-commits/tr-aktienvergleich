import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { checkStatus, corePaths, loadEntry, NeedKeyError, NotFoundError, OfflineError, prefetch, SignalsClient, SnapshotClient } from '../lib/api';
import { canEncrypt, deriveKey, verifyKey } from '../lib/container';
import { forgetKey, loadKey, saveKey } from '../lib/keystore';
import { loadChosenSnapshot, loadPrefs, loadWatchlist, savePrefs, saveWatchlist, saveChosenSnapshot, type Prefs } from '../lib/storage';
import type { CryptoDescriptor, Instruments, Manifest, SnapshotSummary, Status } from '../lib/types';
import { loadWait, outcomeFor, POLL_MS, saveWait, waitFrom, type UpdateResult, type UpdateWait } from '../lib/update';

export type Phase = 'laden' | 'bereit' | 'kein_stand' | 'schluessel' | 'offline_ohne_daten' | 'fehler';

export interface AppStateValue {
  phase: Phase;
  /** Fehler beim Laden (Text in einfachem Deutsch: lib/errors.describeError) */
  error: unknown;
  status: Status | null;
  index: SnapshotSummary[];
  crypto: CryptoDescriptor | null;
  offline: boolean;
  activeId: string | null;
  active: SnapshotSummary | null;
  client: SnapshotClient | null;
  /** Signal-Stand (ab 1.6); null, solange keiner veröffentlicht ist. */
  signalsClient: SignalsClient | null;
  manifest: Manifest | null;
  instruments: Instruments | null;
  isinIndex: Map<string, number>;
  newerId: string | null;
  prefs: Prefs;
  setPrefs: (changes: Partial<Prefs>) => void;
  watchlist: string[];
  toggleWatch: (isin: string) => void;
  setWatchlist: (list: string[]) => void;
  /** Auf diesem Gerät ist ein geprüfter Zugangsschlüssel gespeichert (auch schon vor dem ersten Datenstand). */
  hasKey: boolean;
  /** Entsperrt, aber der Schlüssel ließ sich auf diesem Gerät nicht speichern (z. B. Inkognito) – ab 1.16 */
  keyNotStored: boolean;
  unlock: (passphrase: string) => Promise<string | null>;
  lock: () => Promise<void>;
  switchSnapshot: (id: string | null) => void;
  reload: () => void;
  isDemo: boolean;
  /** Aktualisierung auf Wunsch: Warten auf das Ergebnis eines auf GitHub gestarteten Laufs. */
  updateWait: UpdateWait | null;
  updateResult: UpdateResult | null;
  startUpdateWait: () => void;
  stopUpdateWait: () => void;
  clearUpdateResult: () => void;
  /** status.json sofort neu lesen; true = Server erreicht. */
  checkNow: () => Promise<boolean>;
  /** Datenschlüssel (nicht exportierbar) für Anfragen und Lieferungen von „Jetzt aktualisieren“ (ab 1.21). */
  dataKey: CryptoKey | null;
  /** Der Schlüssel kann auch verschlüsseln (Schlüssel aus Versionen vor 1.21 nur entschlüsseln). */
  keyCanEncrypt: boolean;
  /** Schlüssel mit der Passphrase neu ableiten (ab 1.21, für den Zugang „Jetzt aktualisieren“); Fehlertext oder null. */
  upgradeKey: (passphrase: string) => Promise<string | null>;
}

const AppStateContext = createContext<AppStateValue | null>(null);

/** Ab 1.21: status.json während der Nutzung jede Minute (vorher alle 15 Minuten) – automatische Aktualisierung. */
export const AUTO_STATUS_MS = 60_000;

export function useApp(): AppStateValue {
  const value = useContext(AppStateContext);
  if (!value) throw new Error('AppState fehlt');
  return value;
}

function applyTheme(theme: Prefs['theme']): void {
  const root = document.documentElement;
  // „Wie das Handy“: nur die eigenen Werte entfernen; ein vom umgebenden Rahmen gesetztes
  // light/dark (Vorschau in Claude) bleibt bestehen.
  if (theme === 'system') {
    if (root.dataset.theme === 'hell' || root.dataset.theme === 'dunkel') delete root.dataset.theme;
  } else root.dataset.theme = theme;
}

export function AppStateProvider({ children }: { children: ReactNode }) {
  const [phase, setPhase] = useState<Phase>('laden');
  const [error, setError] = useState<unknown>(null);
  const [keyNotStored, setKeyNotStored] = useState(false);
  // Ab 1.16: fehlt eine Datei des aktiven Stands (meist gerade ersetzt), einmal neu einlesen statt Fehler
  const healed = useRef(new Set<string>());
  const [status, setStatus] = useState<Status | null>(null);
  const [index, setIndex] = useState<SnapshotSummary[]>([]);
  const [crypto, setCrypto] = useState<CryptoDescriptor | null>(null);
  const [offline, setOffline] = useState(false);
  const [key, setKey] = useState<CryptoKey | null>(null);
  const [chosen, setChosen] = useState<string | null>(() => loadChosenSnapshot());
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [instruments, setInstruments] = useState<Instruments | null>(null);
  const [prefs, setPrefsState] = useState<Prefs>(() => loadPrefs());
  const [watchlist, setWatchlistState] = useState<string[]>(() => loadWatchlist());
  const [newerId, setNewerId] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const boundId = useRef<string | null>(null);
  const [updateWait, setUpdateWaitState] = useState<UpdateWait | null>(() => loadWait());
  const [updateResult, setUpdateResult] = useState<UpdateResult | null>(null);
  const waitRef = useRef<UpdateWait | null>(updateWait);
  const setUpdateWait = useCallback((wait: UpdateWait | null) => {
    waitRef.current = wait;
    saveWait(wait);
    setUpdateWaitState(wait);
  }, []);

  useEffect(() => applyTheme(prefs.theme), [prefs.theme]);

  const setPrefs = useCallback((changes: Partial<Prefs>) => {
    setPrefsState((previous) => {
      const next = { ...previous, ...changes };
      savePrefs(next);
      return next;
    });
  }, []);

  const setWatchlist = useCallback((list: string[]) => {
    const unique = [...new Set(list)];
    saveWatchlist(unique);
    setWatchlistState(unique);
  }, []);

  const toggleWatch = useCallback((isin: string) => {
    setWatchlistState((previous) => {
      const next = previous.includes(isin) ? previous.filter((x) => x !== isin) : [...previous, isin];
      saveWatchlist(next);
      return next;
    });
  }, []);

  // Einstieg: Status, Index, Schlüsselparameter
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setPhase('laden');
      setError(null);
      try {
        const entry = await loadEntry();
        if (cancelled) return;
        setStatus(entry.status);
        setIndex(entry.index);
        setCrypto(entry.crypto);
        setOffline(entry.fromCache || !navigator.onLine);
        const stored = entry.crypto.enabled ? await loadKey(entry.crypto.salt_b64 ?? '') : null;
        if (cancelled) return;
        if (stored) setKey(stored);
        if (!entry.index.length) {
          // Noch kein Datenstand: Der Zugangsschlüssel lässt sich trotzdem schon eingeben und prüfen.
          setPhase('kein_stand');
          return;
        }
        if (entry.crypto.enabled && !stored) {
          setPhase('schluessel');
          return;
        }
        setPhase('bereit');
      } catch (exc) {
        if (cancelled) return;
        if (exc instanceof OfflineError) {
          setPhase('offline_ohne_daten');
          setOffline(true);
        } else {
          setPhase('fehler');
          setError(exc);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [reloadToken]);

  const activeId = useMemo(() => {
    if (!index.length) return null;
    const ids = index.map((s) => s.snapshot_id);
    if (chosen && ids.includes(chosen)) return chosen;
    if (boundId.current && ids.includes(boundId.current)) return boundId.current;
    const latest = status?.latest_snapshot_id;
    return latest && ids.includes(latest) ? latest : ids[0];
  }, [index, chosen, status]);

  useEffect(() => {
    boundId.current = activeId;
  }, [activeId]);

  const client = useMemo(() => (phase === 'bereit' && activeId ? new SnapshotClient(activeId, key) : null), [phase, activeId, key]);
  const signalId = status?.signale?.id ?? null;
  const signalsClient = useMemo(() => (phase === 'bereit' && signalId ? new SignalsClient(signalId, key) : null), [phase, signalId, key]);

  // Ab 1.15: Kerndateien laden, sobald der Stand feststeht – schon während der Zugangsschlüssel eingegeben wird und
  // gleichzeitig mit Manifest und Instrumenten (vorher nacheinander: erst Manifest und Instrumente, dann der Rest)
  useEffect(() => {
    if (!activeId || (phase !== 'schluessel' && phase !== 'bereit')) return;
    prefetch(corePaths(activeId, signalId, prefs.h));
  }, [activeId, phase, signalId]);

  // Manifest und Instrumente des aktiven Stands
  useEffect(() => {
    if (!client) return;
    let cancelled = false;
    setManifest(null);
    setInstruments(null);
    (async () => {
      try {
        const [m, inst] = await Promise.all([client.manifest(), client.instruments()]);
        if (cancelled) return;
        setManifest(m);
        setInstruments(inst);
      } catch (exc) {
        if (cancelled) return;
        if (exc instanceof NeedKeyError) {
          setPhase('schluessel');
          return;
        }
        if (exc instanceof NotFoundError && !healed.current.has(client.id)) {
          // Stand vermutlich gerade ersetzt: Status und Index neu lesen, dann gilt der neueste Stand
          healed.current.add(client.id);
          setChosen(null);
          saveChosenSnapshot(null);
          boundId.current = null;
          setReloadToken((t) => t + 1);
          return;
        }
        setPhase(exc instanceof OfflineError ? 'offline_ohne_daten' : 'fehler');
        setError(exc);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [client]);

  // status.json neu lesen: neuen veröffentlichten Stand anbieten (ohne die Ansicht umzuschalten) und
  // ein angefordertes Update abschließen, sobald sich ein Lauf gemeldet hat.
  const checkNow = useCallback(async (): Promise<boolean> => {
    try {
      const result = await checkStatus();
      setOffline(result.offline || !navigator.onLine);
      const latest = result.status.latest_snapshot_id;
      setStatus(result.status);
      if (latest && activeId && latest !== activeId && !chosen) setNewerId(latest);
      const wait = waitRef.current;
      if (wait && !result.offline) {
        const outcome = outcomeFor(wait, result.status);
        if (outcome) {
          setUpdateResult({ outcome, at: Date.now(), status: result.status });
          setUpdateWait(null);
        } else {
          setUpdateWait({ ...wait, lastCheck: Date.now() });
        }
      }
      return !result.offline;
    } catch (exc) {
      // Nur eine fehlende Verbindung heißt „offline“; ein Serverfehler ändert daran nichts (ab 1.16)
      if (exc instanceof OfflineError) setOffline(true);
      return false;
    }
  }, [activeId, chosen, setUpdateWait]);

  // Beim Zurückkehren in die App und – ab 1.21 automatisch während der Nutzung – jede Minute prüfen (status.json ist klein);
  // während eines angeforderten Updates alle 15 Sekunden. Im Hintergrund keine Abfragen.
  useEffect(() => {
    const check = () => {
      if (document.visibilityState === 'visible') void checkNow();
    };
    const onOnline = () => setOffline(false);
    const onOffline = () => setOffline(true);
    document.addEventListener('visibilitychange', check);
    window.addEventListener('online', onOnline);
    window.addEventListener('offline', onOffline);
    const timer = window.setInterval(check, updateWait ? POLL_MS : AUTO_STATUS_MS);
    return () => {
      document.removeEventListener('visibilitychange', check);
      window.removeEventListener('online', onOnline);
      window.removeEventListener('offline', onOffline);
      window.clearInterval(timer);
    };
  }, [checkNow, updateWait]);

  // Ab 1.21: ein neu veröffentlichter Stand erscheint automatisch beim nächsten Seitenwechsel (nicht mitten im Lesen);
  // ausschaltbar unter Einstellungen. Ein bewusst gewählter älterer Stand bleibt.
  const newerRef = useRef<string | null>(null);
  newerRef.current = newerId;
  useEffect(() => {
    if (!prefs.autoStand) return;
    const onNavigate = () => {
      if (newerRef.current && !chosen) {
        setNewerId(null);
        boundId.current = null;
        setReloadToken((t) => t + 1);
      }
    };
    window.addEventListener('hashchange', onNavigate);
    return () => window.removeEventListener('hashchange', onNavigate);
  }, [prefs.autoStand, chosen]);

  const startUpdateWait = useCallback(() => {
    setUpdateResult(null);
    setUpdateWait(waitFrom(status));
  }, [status, setUpdateWait]);

  const stopUpdateWait = useCallback(() => setUpdateWait(null), [setUpdateWait]);
  const clearUpdateResult = useCallback(() => setUpdateResult(null), []);

  const unlock = useCallback(
    async (passphrase: string): Promise<string | null> => {
      if (!crypto?.enabled) return null;
      if (!passphrase) return 'Gib zuerst die Passphrase ein. Ohne sie lassen sich die Daten nicht öffnen.';
      if (typeof window.crypto?.subtle?.importKey !== 'function') {
        return 'Dieser Browser kann die Daten nicht entschlüsseln. Öffne die App in Chrome oder Samsung Internet über die normale https-Adresse.';
      }
      // Ab 1.16: Leerzeichen am Anfang oder Ende (z. B. von der Handy-Tastatur) zusätzlich ohne sie prüfen
      const trimmed = passphrase.trim();
      const candidates = trimmed && trimmed !== passphrase ? [passphrase, trimmed] : [passphrase];
      for (const candidate of candidates) {
        let derived: CryptoKey;
        try {
          derived = await deriveKey(candidate, crypto);
          await verifyKey(derived, crypto);
        } catch {
          continue;
        }
        const stored = await saveKey(derived, crypto.salt_b64 ?? '');
        setKeyNotStored(!stored);
        setKey(derived);
        setPhase(index.length ? 'bereit' : 'kein_stand');
        return null;
      }
      return 'Diese Passphrase passt nicht. Achte auf Groß- und Kleinschreibung. Tipp: Mit „Passphrase anzeigen“ siehst du, was du eingegeben hast.';
    },
    [crypto, index],
  );

  const lock = useCallback(async () => {
    await forgetKey();
    setKeyNotStored(false);
    setKey(null);
    setPhase(!index.length ? 'kein_stand' : crypto?.enabled ? 'schluessel' : 'bereit');
  }, [crypto, index]);

  const upgradeKey = useCallback(
    async (passphrase: string): Promise<string | null> => {
      if (!crypto?.enabled) return 'Diese Daten sind nicht verschlüsselt – ein Zugang für „Jetzt aktualisieren“ braucht den Datenschlüssel.';
      for (const candidate of [...new Set([passphrase, passphrase.trim()])].filter(Boolean)) {
        try {
          const derived = await deriveKey(candidate, crypto);
          await verifyKey(derived, crypto);
          const stored = await saveKey(derived, crypto.salt_b64 ?? '');
          setKeyNotStored(!stored);
          setKey(derived);
          return null;
        } catch {
          continue;
        }
      }
      return 'Diese Passphrase passt nicht. Achte auf Groß- und Kleinschreibung.';
    },
    [crypto],
  );

  const switchSnapshot = useCallback((id: string | null) => {
    saveChosenSnapshot(id);
    setChosen(id);
    setNewerId(null);
    if (id === null) setReloadToken((t) => t + 1);
  }, []);

  const reload = useCallback(() => {
    setNewerId(null);
    setChosen(null);
    saveChosenSnapshot(null);
    boundId.current = null;
    setReloadToken((t) => t + 1);
  }, []);

  const isinIndex = useMemo(() => {
    const map = new Map<string, number>();
    instruments?.isin.forEach((isin, i) => map.set(isin, i));
    return map;
  }, [instruments]);
  const active = index.find((s) => s.snapshot_id === activeId) ?? null;

  const value: AppStateValue = {
    phase,
    error,
    status,
    index,
    crypto,
    offline,
    activeId,
    active,
    client,
    signalsClient,
    manifest,
    instruments,
    isinIndex,
    newerId,
    prefs,
    setPrefs,
    watchlist,
    toggleWatch,
    setWatchlist,
    hasKey: key !== null,
    keyNotStored,
    unlock,
    lock,
    switchSnapshot,
    reload,
    isDemo: (manifest?.data_mode ?? status?.app_mode) === 'demo',
    updateWait,
    updateResult,
    startUpdateWait,
    stopUpdateWait,
    clearUpdateResult,
    checkNow,
    dataKey: key,
    keyCanEncrypt: canEncrypt(key),
    upgradeKey,
  };
  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>;
}
