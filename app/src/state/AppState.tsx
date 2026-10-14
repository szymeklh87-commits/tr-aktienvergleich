import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { checkStatus, loadEntry, NeedKeyError, OfflineError, SignalsClient, SnapshotClient } from '../lib/api';
import { deriveKey, verifyKey } from '../lib/container';
import { forgetKey, loadKey, saveKey } from '../lib/keystore';
import { buildSearchIndex, type SearchIndex } from '../lib/search';
import { loadChosenSnapshot, loadPrefs, loadWatchlist, savePrefs, saveWatchlist, saveChosenSnapshot, type Prefs } from '../lib/storage';
import type { CryptoDescriptor, Instruments, Manifest, SnapshotSummary, Status } from '../lib/types';
import { loadWait, outcomeFor, POLL_MS, saveWait, waitFrom, type UpdateResult, type UpdateWait } from '../lib/update';

export type Phase = 'laden' | 'bereit' | 'kein_stand' | 'schluessel' | 'offline_ohne_daten' | 'fehler';

export interface AppStateValue {
  phase: Phase;
  error: string | null;
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
  searchIndex: SearchIndex | null;
  isinIndex: Map<string, number>;
  newerId: string | null;
  prefs: Prefs;
  setPrefs: (changes: Partial<Prefs>) => void;
  watchlist: string[];
  toggleWatch: (isin: string) => void;
  setWatchlist: (list: string[]) => void;
  /** Auf diesem Gerät ist ein geprüfter Zugangsschlüssel gespeichert (auch schon vor dem ersten Datenstand). */
  hasKey: boolean;
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
}

const AppStateContext = createContext<AppStateValue | null>(null);

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
  const [error, setError] = useState<string | null>(null);
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
          setError(exc instanceof Error ? exc.message : String(exc));
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
        setPhase(exc instanceof OfflineError ? 'offline_ohne_daten' : 'fehler');
        setError(exc instanceof Error ? exc.message : String(exc));
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
    } catch {
      setOffline(true);
      return false;
    }
  }, [activeId, chosen, setUpdateWait]);

  // Beim Zurückkehren in die App und alle 15 Minuten prüfen; während eines angeforderten Updates jede Minute
  useEffect(() => {
    const check = () => {
      if (document.visibilityState === 'visible') void checkNow();
    };
    const onOnline = () => setOffline(false);
    const onOffline = () => setOffline(true);
    document.addEventListener('visibilitychange', check);
    window.addEventListener('online', onOnline);
    window.addEventListener('offline', onOffline);
    const timer = window.setInterval(check, updateWait ? POLL_MS : 15 * 60 * 1000);
    return () => {
      document.removeEventListener('visibilitychange', check);
      window.removeEventListener('online', onOnline);
      window.removeEventListener('offline', onOffline);
      window.clearInterval(timer);
    };
  }, [checkNow, updateWait]);

  const startUpdateWait = useCallback(() => {
    setUpdateResult(null);
    setUpdateWait(waitFrom(status));
  }, [status, setUpdateWait]);

  const stopUpdateWait = useCallback(() => setUpdateWait(null), [setUpdateWait]);
  const clearUpdateResult = useCallback(() => setUpdateResult(null), []);

  const unlock = useCallback(
    async (passphrase: string): Promise<string | null> => {
      if (!crypto?.enabled) return null;
      try {
        const derived = await deriveKey(passphrase, crypto);
        await verifyKey(derived, crypto);
        await saveKey(derived, crypto.salt_b64 ?? '');
        setKey(derived);
        setPhase(index.length ? 'bereit' : 'kein_stand');
        return null;
      } catch {
        return 'Der Zugangsschlüssel passt nicht. Bitte genau die Passphrase eingeben, die im GitHub-Secret DATA_PASSPHRASE hinterlegt ist.';
      }
    },
    [crypto, index],
  );

  const lock = useCallback(async () => {
    await forgetKey();
    setKey(null);
    setPhase(!index.length ? 'kein_stand' : crypto?.enabled ? 'schluessel' : 'bereit');
  }, [crypto, index]);

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

  const searchIndex = useMemo(() => (instruments ? buildSearchIndex(instruments) : null), [instruments]);
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
    searchIndex,
    isinIndex,
    newerId,
    prefs,
    setPrefs,
    watchlist,
    toggleWatch,
    setWatchlist,
    hasKey: key !== null,
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
  };
  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>;
}
